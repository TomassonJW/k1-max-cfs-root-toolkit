#!/usr/bin/env python3
"""Vérifie localement les captures privées sans charger le module MIPS.

La sortie est volontairement nettoyée : empreintes, compteurs, commandes et
adresses seulement. Aucun identifiant matériel ni payload de réponse privé
n'est recopié.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Set, Tuple


HEX_BYTES = re.compile(r"0x[0-9a-fA-F]+")
DATA_SEND = re.compile(r"data_send:\s*((?:0x[0-9a-fA-F]+\s*)+)")
PARSED_RESPONSE = re.compile(
    r"(?:cmd_485_send_data_with_response params|msg):\s*"
    r"((?:0x[0-9a-fA-F]+\s*)+)"
)
COMMAND_NAME = re.compile(r"\bcmd:\s*([A-Z][A-Z0-9_]+)\s*$")
ROUTE_NAME = re.compile(r"\btnn:\s*(T\d[A-D])\b", re.IGNORECASE)


def parse_hex(text: str) -> Tuple[int, ...]:
    return tuple(int(token, 16) for token in HEX_BYTES.findall(text))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def parse_range(proof: str) -> Tuple[int, int]:
    _, value = proof.split(":", 1)
    if "-" in value:
        start, end = value.split("-", 1)
        return int(start), int(end)
    line = int(value)
    return line, line


def _expected_by_line(items: Iterable[Mapping[str, Any]]) -> Dict[int, Tuple[int, ...]]:
    result = {}
    for item in items:
        start, end = parse_range(str(item["proof"]))
        if start != end:
            continue
        result[start] = tuple(int(value) for value in item["frame"])
    return result


def inspect_full_log(path: Path, evidence: Mapping[str, Any]) -> Dict[str, Any]:
    expected_requests = _expected_by_line(evidence["observed_request_frames"])
    response_ranges = [
        (
            str(item["evidence_id"]),
            parse_range(str(item["proof"])),
            tuple(int(value) for value in item["frame"]),
        )
        for item in evidence["observed_response_frames"]
    ]
    request_counts: Counter[Tuple[int, ...]] = Counter()
    command_addresses: MutableMapping[int, Set[int]] = defaultdict(set)
    response_proofs: Set[str] = set()
    named_commands: Set[str] = set()
    routes: Set[str] = set()
    exact_request_lines: Set[int] = set()
    line_count = 0

    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line_count, line in enumerate(stream, 1):
            request_match = DATA_SEND.search(line)
            if request_match:
                frame = parse_hex(request_match.group(1))
                request_counts[frame] += 1
                if len(frame) >= 4:
                    command_addresses[frame[3]].add(frame[0])
                if expected_requests.get(line_count) == frame:
                    exact_request_lines.add(line_count)

            response_match = PARSED_RESPONSE.search(line)
            if response_match:
                frame = parse_hex(response_match.group(1))
                for evidence_id, bounds, expected in response_ranges:
                    if bounds[0] <= line_count <= bounds[1] and frame == expected:
                        response_proofs.add(evidence_id)

            command_match = COMMAND_NAME.search(line)
            if command_match:
                named_commands.add(command_match.group(1))
            route_match = ROUTE_NAME.search(line)
            if route_match:
                routes.add(route_match.group(1).upper())

    missing_frames = [
        item["evidence_id"]
        for item in evidence["observed_request_frames"]
        if tuple(item["frame"]) not in request_counts
    ]
    missing_exact_lines = [
        line for line in sorted(expected_requests) if line not in exact_request_lines
    ]
    missing_responses = [
        item["evidence_id"]
        for item in evidence["observed_response_frames"]
        if item["evidence_id"] not in response_proofs
    ]
    return {
        "line_count": line_count,
        "missing_frames": missing_frames,
        "missing_exact_request_lines": missing_exact_lines,
        "missing_response_proofs": missing_responses,
        "command_counts": {
            str(command): sum(
                count for frame, count in request_counts.items() if len(frame) >= 4 and frame[3] == command
            )
            for command in sorted(command_addresses)
        },
        "command_addresses": {
            str(command): sorted(addresses)
            for command, addresses in sorted(command_addresses.items())
        },
        "named_commands": sorted(named_commands),
        "routes": sorted(routes),
    }


def verify_static_strings(path: Path, evidence: Mapping[str, Any]) -> Dict[str, Any]:
    expected: Dict[int, str] = {}
    for item in evidence["method_name_only"]:
        for line in item["strings_lines"]:
            expected[int(line)] = str(item["symbol"])
    found: Set[int] = set()
    line_count = 0
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line_count, line in enumerate(stream, 1):
            symbol = expected.get(line_count)
            if symbol and symbol in line:
                found.add(line_count)
    return {
        "line_count": line_count,
        "missing_symbol_lines": sorted(set(expected) - found),
    }


def verify(repo_root: Path) -> Dict[str, Any]:
    package = Path(__file__).resolve().parent
    evidence = json.loads((package / "evidence-map.json").read_text(encoding="utf-8"))
    source_results: Dict[str, Any] = {}
    for name, source in evidence["sources"].items():
        path = repo_root / source["private_path"]
        if not path.is_file():
            raise FileNotFoundError("missing_private_source:%s" % name)
        actual = sha256_file(path)
        if actual.lower() != str(source["sha256"]).lower():
            raise ValueError("private_source_hash_mismatch:%s" % name)
        source_results[name] = {"sha256": actual, "status": "OK"}

    full_path = repo_root / evidence["sources"]["full_log"]["private_path"]
    full = inspect_full_log(full_path, evidence)
    if full["line_count"] != evidence["sources"]["full_log"]["line_count"]:
        raise ValueError("full_log_line_count_mismatch")
    if full["missing_frames"] or full["missing_exact_request_lines"]:
        raise ValueError("request_frame_evidence_mismatch")
    if full["missing_response_proofs"]:
        raise ValueError("response_frame_evidence_mismatch")
    forbidden_named = {
        "RETRUDE_PROCESS",
        "CTRL_CONNECTION_MOTOR_ACTION",
        "EXTRUDE2_PROCESS",
        "CUT_MATERIAL",
    }
    if forbidden_named.intersection(full["named_commands"]):
        raise ValueError("declared_absent_command_was_found")
    if full["command_addresses"].get("16") != [1]:
        raise ValueError("extrude_process_address_scope_changed")
    if full["routes"] != ["T1A"]:
        raise ValueError("action_route_scope_changed")

    strings_path = repo_root / evidence["sources"]["static_strings"]["private_path"]
    strings = verify_static_strings(strings_path, evidence)
    if strings["line_count"] != evidence["sources"]["static_strings"]["line_count"]:
        raise ValueError("strings_line_count_mismatch")
    if strings["missing_symbol_lines"]:
        raise ValueError("static_symbol_evidence_mismatch")

    incident_path = repo_root / evidence["sources"]["incident_log"]["private_path"]
    incident_lines = 0
    heartbeat_disabled = 0
    with incident_path.open("r", encoding="utf-8", errors="replace") as stream:
        for incident_lines, line in enumerate(stream, 1):
            if "box heart process not enable" in line:
                heartbeat_disabled += 1
    if incident_lines != evidence["sources"]["incident_log"]["line_count"]:
        raise ValueError("incident_log_line_count_mismatch")
    if heartbeat_disabled != 2:
        raise ValueError("heartbeat_observation_changed")

    return {
        "status": "OK",
        "sources": source_results,
        "full_log": {
            "line_count": full["line_count"],
            "command_counts": full["command_counts"],
            "command_addresses": full["command_addresses"],
            "routes": full["routes"],
        },
        "static_strings": {
            "line_count": strings["line_count"],
            "method_only_symbols_verified": len(evidence["method_name_only"]) - 1
        },
        "incident_log": {
            "line_count": incident_lines,
            "heartbeat_disabled_observations": heartbeat_disabled
        },
        "privacy": "no_private_identity_payload_emitted"
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    result = verify(repo_root)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    print("VERIFY_CFS_MINIMAL_OWNER_PROTOCOL_V1_EVIDENCE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
