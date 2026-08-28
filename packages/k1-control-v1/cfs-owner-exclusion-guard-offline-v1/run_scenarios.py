#!/usr/bin/env python3
"""Run the canonical synthetic exclusion-guard matrix."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Mapping


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from guard import Guard  # noqa: E402


CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
MATRIX = json.loads((HERE / "scenarios.json").read_text(encoding="utf-8"))


def snapshot(auto_refill: Any = 1, seq: int = 1) -> Dict[str, Any]:
    return {
        "schema": 1,
        "sample_seq": seq,
        "mapping_revision": "s12-map-v1",
        "connection_epoch": "synthetic-epoch-001",
        "printer_state": "standby",
        "connected_units": ["T1", "T2"],
        "active_command": "",
        "stock_auto_refill": auto_refill,
        "stock_cfs_print_enable": 1,
        "engaged_routes": [],
        "protected": {
            "mesh_profile": "k1_p001_t055_r001_n11x11",
            "accepted_z_revision": "accepted-z-v1",
            "effective_z_offset_mm": -0.04,
            "homed_axes": "",
            "nozzle_target_c": 0,
            "bed_target_c": 0
        }
    }


def pair(auto_refill: Any = 1, seq: int = 1) -> List[Dict[str, Any]]:
    return [snapshot(auto_refill, seq), snapshot(auto_refill, seq + 1)]


def acquired(saved: int = 1) -> Guard:
    guard = Guard(CONTRACT)
    guard.prepare_acquire(pair(saved, 1))
    if saved == 1:
        guard.observe_disable("accepted", pair(0, 3))
    return guard


def _invalid(mutator) -> Dict[str, Any]:
    reads = pair(1, 1)
    mutator(reads)
    return Guard(CONTRACT).prepare_acquire(reads)


def run_one(scenario_id: str) -> Dict[str, Any]:
    guard = Guard(CONTRACT)
    if scenario_id == "already_disabled_grants_without_intent":
        return guard.prepare_acquire(pair(0))
    if scenario_id == "enabled_prepares_single_disable":
        return guard.prepare_acquire(pair(1))
    if scenario_id == "disable_verified_grants_owner":
        guard.prepare_acquire(pair(1))
        return guard.observe_disable("accepted", pair(0, 3))
    if scenario_id == "disable_ack_without_effect_blocks":
        guard.prepare_acquire(pair(1))
        return guard.observe_disable("accepted", pair(1, 3))
    if scenario_id == "disable_rejected_unchanged_closes_safe":
        guard.prepare_acquire(pair(1))
        return guard.observe_disable("rejected", pair(1, 3))
    if scenario_id == "disable_unknown_then_zero_prepares_rollback":
        guard.prepare_acquire(pair(1))
        return guard.observe_disable("unknown", pair(0, 3))
    if scenario_id == "disable_unknown_then_prior_closes_safe":
        guard.prepare_acquire(pair(1))
        return guard.observe_disable("unknown", pair(1, 3))
    if scenario_id == "disable_retry_forbidden":
        guard.prepare_acquire(pair(1))
        guard.observe_disable("accepted", pair(0, 3))
        return guard.observe_disable("accepted", pair(0, 5))
    if scenario_id == "release_restores_saved_one":
        return acquired(1).prepare_release(pair(0, 5))
    if scenario_id == "release_saved_zero_closes_without_intent":
        return acquired(0).prepare_release(pair(0, 3))
    if scenario_id == "restore_verified_closes_safe":
        guard = acquired(1)
        guard.prepare_release(pair(0, 5))
        return guard.observe_restore("accepted", pair(1, 7))
    if scenario_id == "restore_ack_without_effect_blocks":
        guard = acquired(1)
        guard.prepare_release(pair(0, 5))
        return guard.observe_restore("accepted", pair(0, 7))
    if scenario_id == "restore_unknown_then_saved_closes_safe_ko":
        guard = acquired(1)
        guard.prepare_release(pair(0, 5))
        return guard.observe_restore("unknown", pair(1, 7))
    if scenario_id == "restore_unknown_then_zero_blocks":
        guard = acquired(1)
        guard.prepare_release(pair(0, 5))
        return guard.observe_restore("unknown", pair(0, 7))
    if scenario_id == "restore_retry_forbidden":
        guard = acquired(1)
        guard.prepare_release(pair(0, 5))
        guard.observe_restore("accepted", pair(1, 7))
        return guard.observe_restore("accepted", pair(1, 9))
    if scenario_id == "missing_field_rejected":
        return _invalid(lambda reads: [item.pop("mapping_revision") for item in reads])
    if scenario_id == "unknown_field_rejected":
        return _invalid(lambda reads: [item.__setitem__("serial", "forbidden") for item in reads])
    if scenario_id == "boolean_policy_rejected":
        return guard.prepare_acquire(pair(True))
    if scenario_id == "unstable_pair_rejected":
        reads = pair(1)
        reads[1]["stock_auto_refill"] = 0
        return guard.prepare_acquire(reads)
    if scenario_id == "printer_busy_rejected":
        return _invalid(lambda reads: [item.__setitem__("printer_state", "printing") for item in reads])
    if scenario_id == "unit_disconnect_rejected":
        return _invalid(lambda reads: [item.__setitem__("connected_units", ["T1"]) for item in reads])
    if scenario_id == "active_command_rejected":
        return _invalid(lambda reads: [item.__setitem__("active_command", "busy") for item in reads])
    if scenario_id == "multiple_routes_rejected":
        return _invalid(lambda reads: [item.__setitem__("engaged_routes", ["T1A", "T2A"]) for item in reads])
    if scenario_id == "protected_drift_blocks":
        guard.prepare_acquire(pair(1))
        reads = pair(0, 3)
        for item in reads:
            item["protected"]["mesh_profile"] = "default"
        return guard.observe_disable("accepted", reads)
    if scenario_id == "mapping_epoch_or_print_policy_drift_blocks":
        guard.prepare_acquire(pair(1))
        reads = pair(0, 3)
        for item in reads:
            item["connection_epoch"] = "synthetic-epoch-002"
        return guard.observe_disable("accepted", reads)
    raise KeyError(scenario_id)


def matches_expected(result: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    return result.get("phase") == expected["phase"] and (
        "reason_code" not in expected or result.get("reason_code") == expected["reason_code"]
    )


def run() -> Dict[str, Any]:
    details = []
    for expected in MATRIX["scenarios"]:
        result = run_one(expected["id"])
        details.append({"id": expected["id"], "ok": matches_expected(result, expected), "result": result})
    passed = sum(1 for item in details if item["ok"])
    return {
        "verdict": "OK" if passed == len(details) else "KO",
        "passed": passed,
        "total": len(details),
        "details": details,
        "printer_connection": False,
        "gcode_sent": False,
        "physical_action": False,
        "deployment_candidate": False
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2, sort_keys=True))
