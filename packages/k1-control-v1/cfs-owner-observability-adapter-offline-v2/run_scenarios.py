#!/usr/bin/env python3
"""Run the canonical offline V2 observability matrix."""

from __future__ import annotations

from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
from typing import Any, Dict, Mapping, Sequence


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
CONTRACT = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
SCENARIOS = json.loads((PACKAGE / "scenarios.json").read_text(encoding="utf-8"))
GUARD_CONTRACT = json.loads(
    (ROOT / CONTRACT["source_pins"]["guard_contract"]).read_text(encoding="utf-8")
)


def _load_adapter():
    spec = spec_from_file_location("cfs_owner_observability_adapter_v2_runner", PACKAGE / "adapter_v2.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("adapter_import_failed")
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


adapter = _load_adapter()


def observation(sample_seq: int, eventtime: float) -> Dict[str, Any]:
    return {
        "schema": 2,
        "sample_seq": sample_seq,
        "observer_connection_id": 424242,
        "observer_connection_live": True,
        "observer_eventtime": eventtime,
        "cfs_transition_seq": 0,
        "cfs_transition_digest": "cfs-state:" + ("a" * 64),
        "mapping_revision": "mapping:" + ("b" * 64),
        "printer_state": "standby",
        "connected_units": ["T1", "T2"],
        "active_command": "",
        "stock_auto_refill": 1,
        "stock_cfs_print_enable": 1,
        "engaged_routes": [],
        "protected": {
            "mesh_profile": "k1_p001_t055_r001_n11x11",
            "runtime_accepted_z_valid": 1,
            "runtime_accepted_z_offset_mm": -0.04,
            "store_ready": None,
            "store_integrity": "ok",
            "store_accepted_z_valid": None,
            "store_accepted_z_offset_mm": None,
            "homed_axes": "",
            "nozzle_target_c": 0,
            "bed_target_c": 0,
        },
    }


def pair() -> Sequence[Mapping[str, Any]]:
    return [observation(1, 100.0), observation(2, 102.0)]


def mutate(scenario_id: str) -> Sequence[Mapping[str, Any]]:
    reads = deepcopy(pair())
    if scenario_id == "stable_observation_projects_to_guard_snapshot":
        return reads
    if scenario_id == "observer_connection_change_rejected":
        reads[1]["observer_connection_id"] = 424243
    elif scenario_id == "observer_connection_closed_rejected":
        reads[1]["observer_connection_live"] = False
    elif scenario_id == "reported_cfs_transition_rejected":
        reads[1]["cfs_transition_seq"] = 1
    elif scenario_id == "transition_digest_drift_rejected":
        reads[1]["cfs_transition_digest"] = "cfs-state:" + ("c" * 64)
    elif scenario_id == "eventtime_order_rejected":
        reads[1]["observer_eventtime"] = 100.0
    elif scenario_id == "interval_too_long_rejected":
        reads[1]["observer_eventtime"] = 111.0
    elif scenario_id == "runtime_z_missing_rejected":
        reads[1]["protected"]["runtime_accepted_z_offset_mm"] = None
    elif scenario_id == "store_integrity_invalid_rejected":
        reads[1]["protected"]["store_integrity"] = "broken"
    elif scenario_id == "store_shape_drift_rejected":
        reads[1]["protected"]["store_accepted_z_offset_mm"] = -0.04
    elif scenario_id == "homing_origin_substitution_rejected":
        del reads[1]["protected"]["runtime_accepted_z_offset_mm"]
        reads[1]["protected"]["homing_origin_z_mm"] = -0.04
    elif scenario_id == "unknown_field_rejected":
        reads[1]["unexpected"] = True
    else:
        raise ValueError("scenario_unknown:%s" % scenario_id)
    return reads


def run() -> Mapping[str, Any]:
    results = []
    for scenario in SCENARIOS["scenarios"]:
        scenario_id = scenario["id"]
        expected = scenario["expected"]
        actual = "pass"
        projection = None
        try:
            projection = adapter.adapt_observation_pair(CONTRACT, GUARD_CONTRACT, mutate(scenario_id))
        except adapter.ObservationError as exc:
            actual = exc.code
        passed = actual == expected
        results.append({
            "id": scenario_id,
            "expected": expected,
            "actual": actual,
            "passed": passed,
            "projection": projection if scenario_id == "stable_observation_projects_to_guard_snapshot" else None,
        })
    return {
        "schema": 1,
        "mission": CONTRACT["mission"],
        "total": len(results),
        "passed": sum(1 for item in results if item["passed"]),
        "failed": sum(1 for item in results if not item["passed"]),
        "results": results,
        "printer_connection": False,
        "gcode_sent": False,
        "physical_action": False,
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    if result["failed"]:
        return 1
    print("CFS_OWNER_OBSERVABILITY_ADAPTER_OFFLINE_V2_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
