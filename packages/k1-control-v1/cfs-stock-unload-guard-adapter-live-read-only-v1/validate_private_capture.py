#!/usr/bin/env python3
"""Validate a private live capture without publishing CFS identities."""

from __future__ import annotations

import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, Mapping, Set


PACKAGE = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE.parents[2]
ADAPTER_PATH = (
    PACKAGE.parent / "cfs-stock-unload-guard-adapter-offline-v1" / "adapter.py"
)


def _load_adapter():
    spec = spec_from_file_location("cfs_stock_unload_guard_adapter_live", ADAPTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("adapter_import_failed")
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


adapter = _load_adapter()


EXPECTED_STATUS_KEYS = {
    "box",
    "extruder",
    "filament_switch_sensor filament_sensor",
    "filament_switch_sensor filament_sensor_2",
    "heater_bed",
    "print_stats",
}
EXPECTED_BOX_KEYS = {
    "T1",
    "T2",
    "T3",
    "T4",
    "auto_refill",
    "custom_command_result",
    "cut_pos",
    "enable",
    "filament",
    "filament_useup",
    "same_material",
    "state",
    "t_command",
}
EXPECTED_UNIT_KEYS = {
    "color_value",
    "dry_and_humidity",
    "filament",
    "filament_detected",
    "material_type",
    "measuring_wheel",
    "mode",
    "remain_len",
    "sn",
    "state",
    "temperature",
    "uuid",
    "vender",
    "version",
}
IDENTITY_FIELDS = {"sn", "uuid"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("object_required:%s" % path)
    return value


def _exact_keys(value: Mapping[str, Any], expected: Set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(
            "schema_drift:%s:missing=%s:extra=%s" % (path, missing, extra)
        )


def sanitize_query_response(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Project the exact known K1 shape to the adapter allowlist."""

    root = _mapping(payload, "payload")
    _exact_keys(root, {"result"}, "payload")
    result = _mapping(root["result"], "payload.result")
    _exact_keys(result, {"eventtime", "status"}, "payload.result")
    eventtime = result["eventtime"]
    if isinstance(eventtime, bool) or not isinstance(eventtime, (int, float)):
        raise ValueError("eventtime_invalid")
    if not math.isfinite(float(eventtime)):
        raise ValueError("eventtime_invalid")

    status = _mapping(result["status"], "payload.result.status")
    _exact_keys(status, EXPECTED_STATUS_KEYS, "payload.result.status")
    print_stats = _mapping(status["print_stats"], "print_stats")
    extruder = _mapping(status["extruder"], "extruder")
    heater_bed = _mapping(status["heater_bed"], "heater_bed")
    sensor = _mapping(
        status["filament_switch_sensor filament_sensor"], "toolhead_sensor"
    )
    secondary_sensor = _mapping(
        status["filament_switch_sensor filament_sensor_2"], "secondary_sensor"
    )
    _exact_keys(print_stats, {"filename", "state"}, "print_stats")
    _exact_keys(extruder, {"can_extrude", "target", "temperature"}, "extruder")
    _exact_keys(heater_bed, {"target", "temperature"}, "heater_bed")
    _exact_keys(sensor, {"enabled", "filament_detected"}, "toolhead_sensor")
    _exact_keys(
        secondary_sensor,
        {"enabled", "filament_detected"},
        "secondary_sensor",
    )

    box = _mapping(status["box"], "box")
    _exact_keys(box, EXPECTED_BOX_KEYS, "box")
    safe_box: Dict[str, Any] = {
        "state": box["state"],
        "t_command": box["t_command"],
    }
    for unit_name in ("T1", "T2", "T3", "T4"):
        unit = _mapping(box[unit_name], "box.%s" % unit_name)
        _exact_keys(unit, EXPECTED_UNIT_KEYS, "box.%s" % unit_name)
        safe_box[unit_name] = {
            "state": unit["state"],
            "filament": unit["filament"],
        }

    return {
        "result": {
            "status": {
                "print_stats": {"state": print_stats["state"]},
                "extruder": {"target": extruder["target"]},
                "heater_bed": {"target": heater_bed["target"]},
                "box": safe_box,
                "filament_switch_sensor filament_sensor": {
                    "enabled": sensor["enabled"],
                    "filament_detected": sensor["filament_detected"],
                },
            }
        }
    }


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


def verify_capture(path: Path, terminal_marker: str) -> Mapping[str, Any]:
    lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    if terminal_marker not in lines:
        raise ValueError("terminal_marker_missing")

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
    if not EXPECTED_STATUS_KEYS.issubset(objects):
        raise ValueError("required_live_objects_missing")

    raw_states = [
        json.loads(marked_block(lines, name)) for name in ("STATE_1", "STATE_2")
    ]
    safe_states = [sanitize_query_response(state) for state in raw_states]
    snapshots = [adapter.adapt_query_response(state) for state in safe_states]
    if snapshots[0] != snapshots[1]:
        raise ValueError("adapted_live_state_not_stable")
    snapshot = snapshots[0]

    if snapshot["engaged_routes"]:
        readiness = "NOT_EVALUATED_ROUTE_PRESENT"
    else:
        readiness = "BLOCKED_NO_ENGAGED_ROUTE"

    rendered_safe = json.dumps(safe_states, sort_keys=True)
    for identity_field in IDENTITY_FIELDS:
        if '"%s"' % identity_field in rendered_safe:
            raise ValueError("identity_not_removed:%s" % identity_field)

    return {
        "status": "OK",
        "live_snapshots": 2,
        "klippy_state": "ready",
        "adapted_snapshot": snapshot,
        "configuration_hashes_unchanged": True,
        "identity_fields_removed_before_adapter": sorted(IDENTITY_FIELDS),
        "schema_drift_detected": False,
        "current_guard_readiness_without_guard_call": readiness,
        "guard_run_called": False,
        "remote_writes": False,
        "gcode_sent": False,
    }


def verify_evidence(repo_root: Path = REPO_ROOT) -> Mapping[str, Any]:
    evidence = json.loads((PACKAGE / "evidence-map.json").read_text(encoding="utf-8"))
    source = evidence["private_source"]
    path = repo_root / source["path"]
    if not path.is_file():
        raise FileNotFoundError("private_source_missing")
    if sha256_file(path) != source["sha256"]:
        raise ValueError("private_source_hash_mismatch")
    result = verify_capture(path, "LIVE_ADAPTER_READ_ONLY_OK")
    if result != evidence["safe_result"]:
        raise ValueError("safe_result_mismatch")
    return result


def main() -> int:
    print(json.dumps(verify_evidence(), indent=2, sort_keys=True, ensure_ascii=False))
    print("VALIDATE_CFS_STOCK_UNLOAD_GUARD_ADAPTER_LIVE_READ_ONLY_V1_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
