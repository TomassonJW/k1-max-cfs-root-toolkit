#!/usr/bin/env python3
"""Vérifie les preuves privées sans charger le module MIPS ni exposer d'identité."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
from typing import Any, Dict, Iterable, Mapping, Tuple


HEX = re.compile(r"0x[0-9a-fA-F]+")
DATA_SEND = re.compile(r"data_send:\s*((?:0x[0-9a-fA-F]+\s*)+)")
PARSED_RESPONSE = re.compile(
    r"(?:cmd_485_send_data_with_response params|msg):\s*"
    r"((?:0x[0-9a-fA-F]+\s*)+)"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def parse_hex(text: str) -> Tuple[int, ...]:
    return tuple(int(token, 16) for token in HEX.findall(text))


def read_selected_lines(path: Path, numbers: Iterable[int]) -> Tuple[int, Dict[int, str]]:
    wanted = set(numbers)
    found: Dict[int, str] = {}
    line_count = 0
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line_count, line in enumerate(stream, 1):
            if line_count in wanted:
                found[line_count] = line.rstrip("\r\n")
    if set(found) != wanted:
        raise ValueError("selected_private_log_lines_missing")
    return line_count, found


def exact_prefix(prefix: Path, candidate: Path) -> bool:
    if prefix.stat().st_size > candidate.stat().st_size:
        return False
    with prefix.open("rb") as left, candidate.open("rb") as right:
        while chunk := left.read(1024 * 1024):
            if right.read(len(chunk)) != chunk:
                return False
    return True


def crc8(data: Iterable[int], poly: int = 0x07) -> int:
    crc = 0
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def inspect_elf32(path: Path) -> Dict[str, Any]:
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 1:
        raise ValueError("box_wrapper_is_not_ELF32")
    endian = "<" if data[5] == 1 else ">"
    header = struct.unpack_from(endian + "HHIIIIIHHHHHH", data, 16)
    machine = header[1]
    section_offset = header[5]
    section_entry_size = header[10]
    section_count = header[11]
    sections = []
    for index in range(section_count):
        offset = section_offset + index * section_entry_size
        fields = struct.unpack_from(endian + "IIIIIIIIII", data, offset)
        sections.append(
            {
                "type": fields[1],
                "offset": fields[4],
                "size": fields[5],
                "link": fields[6],
                "entry_size": fields[9],
            }
        )
    dynamic_symbols = sum(
        section["size"] // section["entry_size"]
        for section in sections
        if section["type"] == 11 and section["entry_size"]
    )
    return {
        "class": 32,
        "endianness": "little" if endian == "<" else "big",
        "machine": machine,
        "section_count": section_count,
        "dynamic_symbol_count": dynamic_symbols,
    }


def verify(repo_root: Path) -> Dict[str, Any]:
    package = Path(__file__).resolve().parent
    evidence: Mapping[str, Any] = json.loads(
        (package / "evidence-map.json").read_text(encoding="utf-8")
    )
    sources = evidence["private_sources"]
    verified_sources = {}
    paths = {}
    for name, source in sources.items():
        path = repo_root / source["private_path"]
        if not path.is_file():
            raise FileNotFoundError("missing_private_source:%s" % name)
        actual_hash = sha256_file(path)
        if actual_hash != source["sha256"]:
            raise ValueError("private_source_hash_mismatch:%s" % name)
        if "size_bytes" in source and path.stat().st_size != source["size_bytes"]:
            raise ValueError("private_source_size_mismatch:%s" % name)
        paths[name] = path
        verified_sources[name] = {"sha256": actual_hash, "status": "OK"}

    if not exact_prefix(paths["historical_log_prefix"], paths["historical_log_superset"]):
        raise ValueError("historical_logs_are_not_exact_prefix_and_superset")

    wanted = {
        1029159,
        1029258,
        1029260,
        1029261,
        1029287,
        1029288,
        1029290,
        1029291,
        1029390,
        1029391,
        1029430,
        1029431,
        1029433,
        1029434,
        1029435,
    }
    line_count, lines = read_selected_lines(paths["historical_log_prefix"], wanted)
    if line_count != sources["historical_log_prefix"]["line_count"]:
        raise ValueError("historical_log_line_count_mismatch")

    cycle = evidence["observed_retract_cycle"]
    buffer_request = parse_hex(DATA_SEND.search(lines[1029260]).group(1))
    material_request = parse_hex(DATA_SEND.search(lines[1029390]).group(1))
    expected_buffer = tuple(cycle["buffer_trigger"]["request"])
    expected_material = tuple(cycle["material_trigger"]["request"])
    if buffer_request != expected_buffer or material_request != expected_material:
        raise ValueError("retract_request_frame_mismatch")

    expected_response = tuple(cycle["buffer_trigger"]["response"])
    for number in (1029287, 1029288, 1029430, 1029431):
        match = PARSED_RESPONSE.search(lines[number])
        if not match or parse_hex(match.group(1)) != expected_response:
            raise ValueError("retract_response_frame_mismatch:%s" % number)
    if "timeout = 150" not in lines[1029261] or "timeout = 150" not in lines[1029391]:
        raise ValueError("retract_timeout_mismatch")
    if "cmd: RETRUDE_PROCESS" not in lines[1029290] or "cmd: RETRUDE_PROCESS" not in lines[1029433]:
        raise ValueError("retract_named_result_missing")
    if "filament_sensor true" not in lines[1029258] or "filament_sensor false" not in lines[1029435]:
        raise ValueError("local_filament_sensor_transition_mismatch")

    trailer = expected_response[-1]
    calculated_crc = crc8(expected_response[2:-1])
    if trailer != calculated_crc or calculated_crc != evidence["integrity"]["candidate_rule_result"]:
        raise ValueError("captured_response_crc_candidate_mismatch")

    config_lines = paths["stock_box_config"].read_text(
        encoding="utf-8", errors="replace"
    ).splitlines()
    if len(config_lines) != sources["stock_box_config"]["line_count"]:
        raise ValueError("stock_box_config_line_count_mismatch")
    config_text = "\n".join(config_lines)
    required_macros = {
        "[gcode_macro BOX_LOAD_MATERIAL_WITH_MATERIAL]",
        "[gcode_macro BOX_LOAD_MATERIAL_WITHOUT_MATERIAL]",
        "[gcode_macro BOX_QUIT_MATERIAL]",
        "BOX_CUT_MATERIAL",
        "BOX_RETRUDE_MATERIAL",
        "BOX_EXTRUDE_MATERIAL",
        "BOX_EXTRUDER_EXTRUDE",
        "BOX_MATERIAL_FLUSH",
    }
    if any(item not in config_text for item in required_macros):
        raise ValueError("stock_box_choreography_marker_missing")

    elf = inspect_elf32(paths["box_wrapper_binary"])
    expected_elf = sources["box_wrapper_binary"]["elf"]
    for key in ("class", "endianness", "machine", "section_count", "dynamic_symbol_count"):
        if elf[key] != expected_elf[key]:
            raise ValueError("box_wrapper_ELF_metadata_mismatch:%s" % key)

    return {
        "status": "OK",
        "sources": verified_sources,
        "source_independence": "one_underlying_historical_retract_run",
        "retract_observation": {
            "request_frames": 2,
            "matched_success_responses": 2,
            "host_timeout_seconds": 150,
            "local_sensor_transition": "present_to_clear",
            "scope": "T1A_historical_stock_non_isolated_not_callable",
        },
        "integrity": {
            "captured_response_crc8_poly_0x07": "OK",
            "request_side_full_wire_capture": "MISSING",
        },
        "binary_handling": "ELF_metadata_only_never_loaded_imported_or_executed",
        "privacy": "no_private_identity_payload_emitted",
        "gate_verdict": "KO_BOUNDED",
        "callable_messages": [],
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    result = verify(repo_root)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    print("VERIFY_CFS_MINIMAL_OWNER_EVIDENCE_V1_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
