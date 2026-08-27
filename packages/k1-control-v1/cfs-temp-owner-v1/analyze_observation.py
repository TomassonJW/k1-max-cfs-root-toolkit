"""Analyze one sanitized CFS temperature-owner observation."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict, List


MISSION = "G4-K1-CONTROL-CFS-TEMP-OWNER-V1"
ALLOWED_CHECKPOINTS = {
    "CLEANING_PREP",
    "KEEP_CORRECT",
    "EMPTY_LOAD",
    "WRONG_CHANGE",
    "CROSS_CFS",
}
FORBIDDEN_IDENTITY_KEYS = {"sn", "uuid", "rfid", "serial", "serial_number"}


class AnalysisError(ValueError):
    pass


def compressed(values: List[Any]) -> List[Any]:
    result: List[Any] = []
    for value in values:
        if not result or result[-1] != value:
            result.append(value)
    return result


def contains_forbidden_identity(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_IDENTITY_KEYS or contains_forbidden_identity(child):
                return True
    elif isinstance(value, list):
        return any(contains_forbidden_identity(child) for child in value)
    return False


def numeric(value: Any, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnalysisError(code)
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise AnalysisError(code)
    return result


def analyze(path: Path) -> Dict[str, Any]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if len(records) < 3 or records[0].get("kind") != "header" or records[-1].get("kind") != "footer":
        raise AnalysisError("capture_shape_invalid")
    header = records[0]
    footer = records[-1]
    snapshots = [record for record in records[1:-1] if record.get("kind") == "snapshot"]
    if not snapshots:
        raise AnalysisError("snapshots_missing")
    if header.get("schema") != 1 or header.get("mission") != MISSION:
        raise AnalysisError("capture_contract_invalid")
    if header.get("checkpoint") not in ALLOWED_CHECKPOINTS:
        raise AnalysisError("checkpoint_invalid")
    if header.get("effects") != {"gcode": False, "remote_write": False, "service_action": False}:
        raise AnalysisError("observer_effect_contract_invalid")
    if contains_forbidden_identity(records):
        raise AnalysisError("identity_field_exported")
    if footer.get("status") != "CFS_TEMP_OWNER_OBSERVATION_OK":
        raise AnalysisError("terminal_status_invalid")
    if footer.get("snapshot_count") != len(snapshots):
        raise AnalysisError("snapshot_count_mismatch")
    hashes_unchanged = header.get("hashes_before") == footer.get("hashes_after") and footer.get("configuration_unchanged") is True
    if not hashes_unchanged:
        raise AnalysisError("configuration_changed")
    elapsed_values = [numeric(snapshot.get("elapsed_s"), "elapsed_invalid") for snapshot in snapshots]
    if elapsed_values != sorted(elapsed_values):
        raise AnalysisError("elapsed_not_monotonic")
    for snapshot in snapshots:
        routes = snapshot.get("cfs", {}).get("engaged_routes")
        if not isinstance(routes, list) or any(route not in {"T1A", "T1B", "T1C", "T1D", "T2A", "T2B", "T2C", "T2D"} for route in routes):
            raise AnalysisError("engaged_routes_invalid")
    route_states = compressed([snapshot["cfs"]["engaged_routes"] for snapshot in snapshots])
    command_states = compressed([snapshot["cfs"]["active_command"] for snapshot in snapshots])
    nozzle_targets = [numeric(snapshot["nozzle"]["target_c"], "nozzle_target_invalid") for snapshot in snapshots]
    nozzle_temperatures = [numeric(snapshot["nozzle"]["temperature_c"], "nozzle_temperature_invalid") for snapshot in snapshots]
    bed_targets = [numeric(snapshot["bed"]["target_c"], "bed_target_invalid") for snapshot in snapshots]
    return {
        "schema": 1,
        "status": "CFS_TEMP_OWNER_ANALYSIS_OK",
        "checkpoint": header.get("checkpoint"),
        "snapshot_count": len(snapshots),
        "configuration_unchanged": hashes_unchanged,
        "route_states": route_states,
        "route_transition_count": max(0, len(route_states) - 1),
        "active_command_states": command_states,
        "ambiguous_route_observed": any(len(routes) > 1 for routes in route_states),
        "maximum_nozzle_target_c": max(nozzle_targets),
        "final_nozzle_target_c": nozzle_targets[-1],
        "maximum_nozzle_temperature_c": max(nozzle_temperatures),
        "maximum_bed_target_c": max(bed_targets),
        "final_bed_target_c": bed_targets[-1],
        "head_sensor_states": compressed([snapshot["sensors"]["head"] for snapshot in snapshots]),
        "after_cutter_sensor_states": compressed([snapshot["sensors"]["after_cutter"] for snapshot in snapshots]),
        "human_physical_verdict_required": True,
        "terminal_heater_targets_zero": nozzle_targets[-1] == 0.0 and bed_targets[-1] == 0.0,
        "identity_fields_exported": False,
        "observer_effect": False,
    }


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        print("usage: analyze_observation.py <safe-jsonl>", file=sys.stderr)
        return 2
    try:
        result = analyze(Path(arguments[0]))
    except Exception as exc:
        print(json.dumps({"status": "CFS_TEMP_OWNER_ANALYSIS_KO", "error": "%s:%s" % (type(exc).__name__, exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
