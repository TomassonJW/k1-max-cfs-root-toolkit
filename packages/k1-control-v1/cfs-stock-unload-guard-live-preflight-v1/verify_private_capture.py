#!/usr/bin/env python3
"""Verify private live/pre-existing captures without emitting CFS identities."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def marked_block(lines: Iterable[str], name: str) -> str:
    values = list(lines)
    begin = "=== %s_BEGIN ===" % name
    end = "=== %s_END ===" % name
    if values.count(begin) != 1 or values.count(end) != 1:
        raise ValueError("capture_block_invalid:%s" % name)
    start_index = values.index(begin) + 1
    end_index = values.index(end)
    if end_index <= start_index:
        raise ValueError("capture_block_empty:%s" % name)
    return "\n".join(values[start_index:end_index])


def parse_hashes(text: str) -> Dict[str, str]:
    hashes = {}
    for line in text.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and len(parts[0]) == 64:
            hashes[parts[1].strip()] = parts[0].lower()
    return hashes


def safe_state(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    status = payload["result"]["status"]
    box = status["box"]
    connected = []
    routes = []
    unit_states = {}
    for unit in ("T1", "T2", "T3", "T4"):
        raw = box.get(unit, {})
        state = raw.get("state")
        filament = raw.get("filament")
        unit_states[unit] = {"state": state, "filament": filament}
        if state == "connect":
            connected.append(unit)
        if state == "connect" and filament in ("A", "B", "C", "D"):
            routes.append(unit + filament)
    return {
        "print_state": status["print_stats"]["state"],
        "extruder_target_c": status["extruder"]["target"],
        "bed_target_c": status["heater_bed"]["target"],
        "can_extrude": status["extruder"]["can_extrude"],
        "box_state": box.get("state"),
        "active_cfs_command": box.get("t_command"),
        "connected_cfs_units": connected,
        "engaged_routes": routes,
        "unit_states": unit_states,
        "toolhead_sensor": status["filament_switch_sensor filament_sensor"],
        "secondary_sensor": status["filament_switch_sensor filament_sensor_2"],
        "stock_unload_state_field_present": "stock_unload_state" in box,
    }


def historical_t_commands(path: Path) -> set[str]:
    result = set()
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if not line.startswith("STATE|"):
                continue
            status = json.loads(line.split("|", 2)[2])["status"]
            result.add(str(status.get("box", {}).get("t_command", "")))
    return result


def verify(repo_root: Path) -> Mapping[str, Any]:
    package = Path(__file__).resolve().parent
    evidence = load_json(package / "evidence-map.json")
    paths = {}
    for name, source in evidence["private_sources"].items():
        path = repo_root / source["path"]
        if not path.is_file():
            raise FileNotFoundError("private_source_missing:%s" % name)
        if sha256_file(path) != source["sha256"]:
            raise ValueError("private_source_hash_mismatch:%s" % name)
        paths[name] = path

    lines = paths["valid_live_capture"].read_text(
        encoding="utf-8-sig", errors="replace"
    ).splitlines()
    if "LIVE_PREFLIGHT_READ_ONLY_OK" not in lines:
        raise ValueError("live_capture_terminal_marker_missing")

    before_hashes = parse_hashes(marked_block(lines, "HASHES_BEFORE"))
    after_hashes = parse_hashes(marked_block(lines, "HASHES_AFTER"))
    if before_hashes != after_hashes or len(before_hashes) != 3:
        raise ValueError("configuration_hashes_changed_or_incomplete")

    server = json.loads(marked_block(lines, "SERVER_INFO"))["result"]
    if server.get("klippy_state") != "ready":
        raise ValueError("klippy_not_ready")
    if server.get("failed_components") or server.get("warnings"):
        raise ValueError("moonraker_component_health_not_clean")

    objects = set(json.loads(marked_block(lines, "OBJECT_LIST"))["result"]["objects"])
    required_objects = {
        "print_stats",
        "extruder",
        "heater_bed",
        "box",
        "filament_switch_sensor filament_sensor",
        "filament_switch_sensor filament_sensor_2",
    }
    if not required_objects.issubset(objects):
        raise ValueError("required_live_objects_missing")

    states = [
        safe_state(json.loads(marked_block(lines, name)))
        for name in ("STATE_1", "STATE_2")
    ]
    if states[0] != states[1]:
        raise ValueError("live_state_not_stable")
    state = states[0]
    expected = evidence["live_findings"]
    for key in (
        "print_state",
        "box_state",
        "connected_cfs_units",
        "active_cfs_command",
        "engaged_routes",
        "extruder_target_c",
        "bed_target_c",
        "stock_unload_state_field_present",
    ):
        if state[key] != expected[key]:
            raise ValueError("live_finding_mismatch:%s" % key)
    if state["toolhead_sensor"] != {"enabled": True, "filament_detected": True}:
        raise ValueError("toolhead_sensor_state_mismatch")
    if state["secondary_sensor"] != {"enabled": False, "filament_detected": False}:
        raise ValueError("secondary_sensor_state_mismatch")

    before_box = load_json(paths["historical_box_before"])["result"]["status"]["box"]
    after_box = load_json(paths["historical_box_after"])["result"]["status"]["box"]
    if before_box["T1"]["filament"] != "A" or after_box["T1"]["filament"] != "None":
        raise ValueError("historical_route_transition_mismatch")
    t_commands = historical_t_commands(paths["historical_stock_capture"])
    if t_commands != {""}:
        raise ValueError("historical_t_command_not_stably_empty")

    return {
        "status": "OK_WITH_GUARD_CORRECTION",
        "live_snapshots": 2,
        "klippy_state": "ready",
        "print_state": state["print_state"],
        "connected_cfs_units": state["connected_cfs_units"],
        "engaged_routes": state["engaged_routes"],
        "active_cfs_command": state["active_cfs_command"],
        "extruder_target_c": state["extruder_target_c"],
        "bed_target_c": state["bed_target_c"],
        "toolhead_filament_present": True,
        "direct_stock_unload_state_field": False,
        "historical_route_transition": "T1A_to_none",
        "historical_t_command_distinct_values": [""],
        "configuration_hashes_unchanged": True,
        "current_guard_readiness": "BLOCKED_NO_ENGAGED_ROUTE",
        "remote_writes": False,
        "gcode_sent": False,
        "privacy": "no_CFS_identity_payload_emitted",
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    print(json.dumps(verify(repo_root), indent=2, sort_keys=True, ensure_ascii=False))
    print("VERIFY_CFS_STOCK_UNLOAD_GUARD_LIVE_PREFLIGHT_V1_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
