#!/usr/bin/env python3
"""Vérifie la capture privée sans connexion K1 et sans publier d'identité CFS."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterable, Mapping, Tuple


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_selected_lines(path: Path, numbers: Iterable[int]) -> Tuple[int, Dict[int, str]]:
    wanted = set(numbers)
    found: Dict[int, str] = {}
    count = 0
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for count, line in enumerate(stream, 1):
            if count in wanted:
                found[count] = line.rstrip("\r\n")
    if set(found) != wanted:
        raise ValueError("selected_capture_lines_missing")
    return count, found


def state_from_line(line: str) -> Mapping[str, Any]:
    if not line.startswith("STATE|"):
        raise ValueError("expected_state_line")
    return json.loads(line.split("|", 2)[2])["status"]


def parse_hash_lines(lines: Iterable[str]) -> Dict[str, str]:
    result = {}
    for line in lines:
        match = re.match(r"([0-9a-f]{64})\s+(.+)$", line.strip())
        if match:
            result[match.group(2)] = match.group(1)
    return result


def count_diagnostics(path: Path, start_line: int, finish_line: int) -> Mapping[str, int]:
    counts = {
        "error_level_lines_before": 0,
        "error_level_lines_during": 0,
        "error_level_lines_after": 0,
        "no_response_lines_before": 0,
        "no_response_lines_during": 0,
        "no_response_lines_after": 0,
    }
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line_number, line in enumerate(stream, 1):
            period = (
                "before"
                if line_number < start_line
                else "during"
                if line_number <= finish_line
                else "after"
            )
            if "|[ERROR] " in line:
                counts["error_level_lines_%s" % period] += 1
            if "Error: no response" in line:
                counts["no_response_lines_%s" % period] += 1
    return counts


def verify(repo_root: Path) -> Mapping[str, Any]:
    package = Path(__file__).resolve().parent
    evidence = load_json(package / "evidence-map.json")
    sources = evidence["private_sources"]
    paths = {}
    verified_hashes = {}
    for name, source in sources.items():
        path = repo_root / source["path"]
        if not path.is_file():
            raise FileNotFoundError("missing_private_capture_source:%s" % name)
        actual = sha256_file(path)
        if actual != source["sha256"]:
            raise ValueError("private_capture_hash_mismatch:%s" % name)
        paths[name] = path
        verified_hashes[name] = actual

    required_lines = {
        4,
        5,
        6,
        13,
        6500,
        6719,
        6729,
        6739,
        6741,
        9940,
        9995,
        9997,
        9999,
        10071,
        11162,
        11163,
        12176,
        12177,
        12178,
    }
    line_count, lines = read_selected_lines(paths["capture"], required_lines)
    if line_count != sources["capture"]["line_count"]:
        raise ValueError("private_capture_line_count_mismatch")

    expected_fragments = {
        6500: "received {'script': 'BOX_QUIT_MATERIAL'}",
        6719: "data_send: 0x1 0x5 0xff 0x11 0x1 0x0",
        6739: "msg: 0xf7 0x1 0x3 0x0 0x11 0xca",
        6741: "cmd: RETRUDE_PROCESS",
        9940: "data_send: 0x1 0x5 0xff 0x11 0x1 0x1",
        9995: "msg: 0xf7 0x1 0x3 0x0 0x11 0xca",
        9997: "cmd: RETRUDE_PROCESS",
        9999: "filament_sensor false",
        10071: "finished {'script': 'BOX_QUIT_MATERIAL'}",
        11162: "received {'script': 'M104%20S0'}",
        11163: "Unknown command:M104%20",
        12176: "received {'script': 'TURN_OFF_HEATERS'}",
        12177: "finished {'script': 'TURN_OFF_HEATERS'}",
    }
    for line_number, fragment in expected_fragments.items():
        if fragment not in lines[line_number]:
            raise ValueError("capture_marker_mismatch:%s" % line_number)

    initial_state = state_from_line(lines[13])
    stock_target_state = state_from_line(lines[6729])
    safe_target_state = state_from_line(lines[12178])
    if initial_state["extruder"]["target"] != 0:
        raise ValueError("initial_extruder_target_not_zero")
    if stock_target_state["extruder"]["target"] != 220:
        raise ValueError("stock_cycle_target_not_220")
    if safe_target_state["extruder"]["target"] != 0:
        raise ValueError("cleanup_target_not_zero")

    before_box = load_json(paths["box_before"])["result"]["status"]["box"]
    after_box = load_json(paths["box_after"])["result"]["status"]["box"]
    if before_box["T1"]["filament"] != "A":
        raise ValueError("fresh_route_before_is_not_T1A")
    if after_box["T1"]["filament"] != "None":
        raise ValueError("T1_route_not_cleared_after_stock_unload")

    final_status = load_json(paths["final_status"])["result"]["status"]
    if final_status["print_stats"]["state"] != "standby":
        raise ValueError("final_print_state_not_standby")
    if final_status["extruder"]["target"] != 0:
        raise ValueError("final_extruder_target_not_zero")
    if final_status["heater_bed"]["target"] != 0:
        raise ValueError("final_bed_target_not_zero")
    if final_status["box"]["state"] != "connect":
        raise ValueError("final_box_state_not_connected")
    if final_status["box"]["t_command"] != "":
        raise ValueError("final_box_command_not_empty")
    if final_status["filament_switch_sensor filament_sensor"]["filament_detected"] is not True:
        raise ValueError("toolhead_segment_not_detected_as_expected")

    initial_hashes = parse_hash_lines(lines[index] for index in (4, 5, 6))
    final_hashes = parse_hash_lines(
        paths["final_config_hashes"].read_text(
            encoding="utf-8-sig", errors="replace"
        ).splitlines()
    )
    if initial_hashes != final_hashes or len(final_hashes) != 3:
        raise ValueError("configuration_hashes_changed_or_incomplete")

    diagnostics = count_diagnostics(
        paths["capture"],
        evidence["official_action"]["macro_received_line"],
        evidence["official_action"]["macro_finished_line"],
    )
    expected_diagnostics = evidence["background_diagnostics"]
    for key, value in diagnostics.items():
        if value != expected_diagnostics[key]:
            raise ValueError("background_diagnostic_count_mismatch:%s" % key)

    return {
        "status": "OK",
        "capture_verdict": "OK",
        "protocol_gate_verdict": "KO_BOUNDED",
        "route": "T1A_to_none",
        "stock_macro_completed": True,
        "successful_retract_phases": 2,
        "stock_target_celsius": 220,
        "stock_macro_left_target_active": True,
        "cleanup_target_zero": True,
        "toolhead_segment_still_detected": True,
        "config_hashes_unchanged": True,
        "background_diagnostics": diagnostics,
        "callable_messages": [],
        "raw_serial_frames_sent_by_codex": False,
        "verified_private_hashes": verified_hashes,
        "privacy": "no_CFS_identity_payload_emitted",
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    print(json.dumps(verify(repo_root), indent=2, sort_keys=True, ensure_ascii=False))
    print("VERIFY_CFS_MINIMAL_OWNER_PASSIVE_CAPTURE_V1_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
