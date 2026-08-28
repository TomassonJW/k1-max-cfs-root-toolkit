#!/usr/bin/env python3
"""Run the canonical pure-offline CFS owner-core scenario matrix."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Mapping, Sequence


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

from engine import matches_expected, simulate  # noqa: E402


CONTRACT = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
MATRIX = json.loads((PACKAGE / "scenarios.json").read_text(encoding="utf-8"))


def material(
    reference_id: str = "geetech-pla-black",
    material_type: str = "PLA",
    color: str = "black",
    diameter_mm: float = 1.75,
    thermal_recipe_id: str = "geetech-pla-v1",
    user_approved: bool = True,
) -> Dict[str, Any]:
    return {
        "reference_id": reference_id,
        "material_type": material_type,
        "color": color,
        "diameter_mm": diameter_mm,
        "thermal_recipe_id": thermal_recipe_id,
        "user_approved": user_approved,
    }


def base_snapshot(
    *,
    stock_auto_refill: int = 1,
    engaged_routes: Sequence[str] = (),
    active_command: str = "",
    head_sensor_present: bool = False,
    after_cutter_sensor_present: bool = False,
) -> Dict[str, Any]:
    return {
        "schema": 1,
        "mapping_revision": "s12-owner-map-r1",
        "connection_epoch": 7,
        "printer_state": "standby",
        "connected_units": ["T1", "T2"],
        "active_command": active_command,
        "stock_auto_refill": stock_auto_refill,
        "stock_cfs_print_enable": 1,
        "engaged_routes": list(engaged_routes),
        "head_sensor_present": head_sensor_present,
        "after_cutter_sensor_present": after_cutter_sensor_present,
        "protected": {
            "mesh_profile": "k1_p001_t055_r001_n11x11",
            "accepted_z_revision": "accepted-z-r1",
            "effective_z_offset_mm": -0.04,
            "homed_axes": "xyz",
            "nozzle_target_c": 220.0,
            "bed_target_c": 55.0,
        },
    }


def base_inventory() -> Dict[str, Any]:
    primary = material()
    other = material(
        reference_id="generic-petg-blue",
        material_type="PETG",
        color="blue",
        thermal_recipe_id="generic-petg-v1",
    )
    return {
        "schema": 1,
        "mapping_revision": "s12-owner-map-r1",
        "connection_epoch": 7,
        "slots": [
            {
                "route": "T1A",
                "enabled": True,
                "available": True,
                "sensor_present": True,
                "material": deepcopy(primary),
            },
            {
                "route": "T1B",
                "enabled": True,
                "available": False,
                "sensor_present": True,
                "material": deepcopy(primary),
            },
            {
                "route": "T1D",
                "enabled": True,
                "available": True,
                "sensor_present": True,
                "material": deepcopy(other),
            },
            {
                "route": "T2A",
                "enabled": True,
                "available": True,
                "sensor_present": True,
                "material": deepcopy(primary),
            },
            {
                "route": "T2B",
                "enabled": True,
                "available": False,
                "sensor_present": True,
                "material": deepcopy(other),
            },
            {
                "route": "T2C",
                "enabled": True,
                "available": True,
                "sensor_present": True,
                "material": material(color="grey"),
            },
        ],
    }


def observed(
    snapshot: Mapping[str, Any],
    routes: Sequence[str],
    *,
    stock_auto_refill: int = 0,
) -> Dict[str, Any]:
    result = deepcopy(dict(snapshot))
    result["active_command"] = ""
    result["stock_auto_refill"] = stock_auto_refill
    result["engaged_routes"] = list(routes)
    return result


def lease_events(snapshot: Mapping[str, Any], lease_id: str = "lease-001") -> List[Dict[str, Any]]:
    attempts = 1 if snapshot["stock_auto_refill"] == 1 else 0
    return [
        {"kind": "prepare_lease", "job_id": "job-001", "lease_id": lease_id},
        {
            "kind": "confirm_lease",
            "intent_id": "%s:owner-exclusion" % lease_id,
            "synthetic_observation": True,
            "attempt_count": attempts,
            "stock_owner_boundary_verified": True,
            "configuration_unchanged": True,
            "observed": observed(snapshot, snapshot["engaged_routes"]),
        },
    ]


def plan_start_event(
    snapshot: Mapping[str, Any],
    *,
    intended_route: str = "T1A",
    engaged_identity_confirmed: bool = True,
) -> Dict[str, Any]:
    return {
        "kind": "plan_start",
        "intended_route": intended_route,
        "intended_material": material(),
        "engaged_material_identity_confirmed": engaged_identity_confirmed,
        "observed": observed(snapshot, snapshot["engaged_routes"]),
    }


def intent_id(lease_id: str, plan_sequence: int, index: int, operation: str) -> str:
    return "%s:plan-%d:%d-%s" % (lease_id, plan_sequence, index, operation)


def observe_intent_event(
    snapshot: Mapping[str, Any],
    *,
    lease_id: str,
    plan_sequence: int,
    index: int,
    operation: str,
    current_route: str,
    target_route: str,
    outcome: str = "proved",
) -> Dict[str, Any]:
    routes = [current_route] if current_route else []
    event: Dict[str, Any] = {
        "kind": "observe_intent",
        "intent_id": intent_id(lease_id, plan_sequence, index, operation),
        "synthetic_observation": True,
        "attempt_count": 1,
        "automatic_retry_count": 0,
        "outcome": outcome,
        "configuration_unchanged": True,
        "protected_state_unchanged": True,
        "stock_callback_seen": False,
    }
    if operation == "cut_current_filament":
        event["cut_observed"] = True
    elif operation in {"retract_current_filament", "resolve_runout_tail"}:
        routes = []
        event["route_released"] = True
        if operation == "resolve_runout_tail":
            event["tail_state_resolved"] = True
    elif operation == "load_selected_route":
        routes = [target_route]
        event["route_sensor_present"] = True
    elif operation == "purge_visible":
        routes = [target_route]
        event["visible_flow"] = True
    event["observed"] = observed(snapshot, routes)
    return event


def complete_plan_events(
    snapshot: Mapping[str, Any],
    *,
    lease_id: str,
    plan_sequence: int,
    operations: Sequence[str],
    current_route: str,
    target_route: str,
    refill: bool = False,
) -> List[Dict[str, Any]]:
    events = []
    route = current_route
    for index, operation in enumerate(operations, 1):
        events.append(
            observe_intent_event(
                snapshot,
                lease_id=lease_id,
                plan_sequence=plan_sequence,
                index=index,
                operation=operation,
                current_route=route,
                target_route=target_route,
            )
        )
        if operation in {"retract_current_filament", "resolve_runout_tail"}:
            route = ""
        elif operation == "load_selected_route":
            route = target_route
    verify = {
        "kind": "verify_plan",
        "observed": observed(snapshot, [target_route]),
        "visible_flow": True,
        "protected_state_unchanged": True,
        "stock_callback_seen": False,
        "automatic_retry_count": 0,
    }
    if refill:
        verify["pause_still_latched"] = True
    events.append(verify)
    return events


def full_start_events(snapshot: Mapping[str, Any]) -> List[Dict[str, Any]]:
    events = lease_events(snapshot)
    events.append(plan_start_event(snapshot))
    events.extend(
        complete_plan_events(
            snapshot,
            lease_id="lease-001",
            plan_sequence=1,
            operations=["purge_visible"],
            current_route="T1A",
            target_route="T1A",
        )
    )
    events.append(
        {
            "kind": "begin_print",
            "observed": observed(snapshot, ["T1A"]),
            "full_state_verified": True,
            "stock_start_command": False,
            "mesh_and_z_unchanged": True,
        }
    )
    return events


def paused_context(snapshot: Mapping[str, Any], route: str = "T1A") -> Dict[str, Any]:
    return {
        "resume_position_xyz_mm": {"x": 125.0, "y": 125.0, "z": 0.3},
        "motion_modes": {"axes": "absolute", "extruder": "absolute"},
        "extruder_e_position": 18.5,
        "protected": deepcopy(snapshot["protected"]),
        "fans": {"part": 0.5, "auxiliary": 0.0, "chamber": 0.0},
        "speed_factor_percent": 100.0,
        "flow_factor_percent": 100.0,
        "pressure_advance": 0.04,
        "logical_tool": "job-tool-primary",
        "engaged_route": route,
        "head_sensor_present": snapshot["head_sensor_present"],
        "after_cutter_sensor_present": snapshot["after_cutter_sensor_present"],
        "mapping_revision": snapshot["mapping_revision"],
        "connection_epoch": snapshot["connection_epoch"],
    }


def pause_and_plan_runout_events(snapshot: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "kind": "pause_runout",
            "observed": observed(snapshot, ["T1A"]),
            "pause_latched": True,
            "paused_context": paused_context(snapshot),
            "stock_pause_command": False,
            "stock_callback_seen": False,
        },
        {
            "kind": "plan_runout",
            "exhausted_route": "T1A",
            "observed": observed(snapshot, ["T1A"]),
        },
    ]


def build_case(scenario_id: str) -> Dict[str, Any]:
    snapshot = base_snapshot()
    inventory = base_inventory()
    events: List[Dict[str, Any]] = []

    if scenario_id == "s12_snapshot_requests_stock_owner_exclusion":
        events = [{"kind": "prepare_lease", "job_id": "job-001", "lease_id": "lease-001"}]
    elif scenario_id == "lease_activates_only_after_verified_exclusion":
        events = lease_events(snapshot)
    elif scenario_id == "lease_rejects_active_cfs_command":
        snapshot = base_snapshot(active_command="T0")
        events = [{"kind": "prepare_lease", "job_id": "job-001", "lease_id": "lease-001"}]
    elif scenario_id == "start_keeps_confirmed_route_without_cut_or_load":
        snapshot = base_snapshot(engaged_routes=["T1A"], head_sensor_present=True)
        events = lease_events(snapshot) + [plan_start_event(snapshot)]
    elif scenario_id == "start_absent_plans_load_then_purge":
        events = lease_events(snapshot) + [plan_start_event(snapshot)]
    elif scenario_id == "start_wrong_plans_cut_retract_load_purge":
        snapshot = base_snapshot(engaged_routes=["T1D"], head_sensor_present=True)
        events = lease_events(snapshot) + [plan_start_event(snapshot)]
    elif scenario_id == "start_unknown_material_blocks":
        snapshot = base_snapshot(engaged_routes=["T1A"], head_sensor_present=True)
        events = lease_events(snapshot) + [
            plan_start_event(snapshot, engaged_identity_confirmed=False)
        ]
    elif scenario_id == "multiple_engaged_routes_block":
        snapshot = base_snapshot(engaged_routes=["T1A", "T2A"], head_sensor_present=True)
        events = lease_events(snapshot) + [plan_start_event(snapshot)]
    elif scenario_id == "runout_requires_latched_pause":
        snapshot = base_snapshot(engaged_routes=["T1A"], head_sensor_present=True)
        events = full_start_events(snapshot) + [
            {
                "kind": "pause_runout",
                "observed": observed(snapshot, ["T1A"]),
                "pause_latched": False,
                "paused_context": paused_context(snapshot),
                "stock_pause_command": False,
                "stock_callback_seen": False,
            }
        ]
    elif scenario_id == "runout_selects_unique_identical_cross_cfs":
        snapshot = base_snapshot(engaged_routes=["T1A"], head_sensor_present=True)
        events = full_start_events(snapshot) + pause_and_plan_runout_events(snapshot)
        events.extend(
            complete_plan_events(
                snapshot,
                lease_id="lease-001",
                plan_sequence=2,
                operations=["resolve_runout_tail", "load_selected_route", "purge_visible"],
                current_route="T1A",
                target_route="T2A",
                refill=True,
            )
        )
        events.append(
            {
                "kind": "owned_resume",
                "observed": observed(snapshot, ["T2A"]),
                "owner": "k1_control",
                "stock_resume_command": False,
                "homing": False,
                "z_reference": False,
                "mesh_mutation": False,
                "paused_context": paused_context(snapshot),
            }
        )
    elif scenario_id in {
        "runout_rejects_no_identical_candidate",
        "runout_rejects_multiple_identical_candidates",
        "runout_rejects_near_match",
    }:
        snapshot = base_snapshot(engaged_routes=["T1A"], head_sensor_present=True)
        if scenario_id == "runout_rejects_no_identical_candidate":
            next(slot for slot in inventory["slots"] if slot["route"] == "T2A")["available"] = False
        elif scenario_id == "runout_rejects_multiple_identical_candidates":
            next(slot for slot in inventory["slots"] if slot["route"] == "T1B")["available"] = True
        else:
            next(slot for slot in inventory["slots"] if slot["route"] == "T2A")["material"] = material(color="grey")
        events = full_start_events(snapshot) + pause_and_plan_runout_events(snapshot)
    elif scenario_id == "stale_mapping_blocks_before_plan":
        events = lease_events(snapshot)
        stale = plan_start_event(snapshot)
        stale["observed"]["mapping_revision"] = "s12-owner-map-r2"
        events.append(stale)
    elif scenario_id == "connection_epoch_change_invalidates_lease":
        events = lease_events(snapshot) + [
            {"kind": "connection_epoch_changed", "new_connection_epoch": 8}
        ]
    elif scenario_id == "stock_callback_conflict_blocks":
        events = lease_events(snapshot) + [
            {"kind": "stock_callback", "callback": "material_auto_refill"}
        ]
    elif scenario_id == "unknown_effect_never_retries":
        events = lease_events(snapshot) + [plan_start_event(snapshot)]
        events.append(
            observe_intent_event(
                snapshot,
                lease_id="lease-001",
                plan_sequence=1,
                index=1,
                operation="load_selected_route",
                current_route="",
                target_route="T1A",
                outcome="unknown",
            )
        )
    elif scenario_id == "completed_intent_cannot_replay":
        events = lease_events(snapshot) + [plan_start_event(snapshot)]
        first = observe_intent_event(
            snapshot,
            lease_id="lease-001",
            plan_sequence=1,
            index=1,
            operation="load_selected_route",
            current_route="",
            target_route="T1A",
        )
        events.extend([first, deepcopy(first)])
    elif scenario_id == "owned_resume_requires_full_verification":
        snapshot = base_snapshot(engaged_routes=["T1A"], head_sensor_present=True)
        events = full_start_events(snapshot) + pause_and_plan_runout_events(snapshot)
        events.extend(
            complete_plan_events(
                snapshot,
                lease_id="lease-001",
                plan_sequence=2,
                operations=["resolve_runout_tail", "load_selected_route", "purge_visible"],
                current_route="T1A",
                target_route="T2A",
                refill=True,
            )
        )
        events.append(
            {
                "kind": "owned_resume",
                "observed": observed(snapshot, ["T2A"]),
                "owner": "k1_control",
                "stock_resume_command": False,
                "homing": False,
                "z_reference": False,
                "mesh_mutation": False,
                "paused_context": paused_context(snapshot),
            }
        )
        events[-1]["paused_context"]["pressure_advance"] = 0.05
    elif scenario_id in {
        "lease_release_restores_saved_stock_policy",
        "lease_release_preserves_pre_disabled_stock_policy",
    }:
        initial_value = 0 if scenario_id.endswith("pre_disabled_stock_policy") else 1
        snapshot = base_snapshot(stock_auto_refill=initial_value)
        events = lease_events(snapshot)
        events.append(
            {
                "kind": "close_job",
                "observed": observed(snapshot, []),
                "stock_end_command": False,
                "heater_targets_zero_verified": True,
                "resume_closed": True,
            }
        )
        events.append(
            {
                "kind": "confirm_release",
                "intent_id": "lease-001:owner-release",
                "synthetic_observation": True,
                "attempt_count": 1 if initial_value == 1 else 0,
                "stock_owner_boundary_verified": True,
                "configuration_unchanged": True,
                "observed": observed(snapshot, [], stock_auto_refill=initial_value),
            }
        )
    else:
        raise KeyError(scenario_id)
    return {"snapshot": snapshot, "inventory": inventory, "events": events}


def verify_s12_source() -> Dict[str, Any]:
    evidence_path = ROOT / CONTRACT["sources"]["s12_safe_evidence"]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    observations = evidence["safe_observations"]
    checks = {
        "private_capture_hash_pinned": evidence["private_source"]["sha256"]
        == CONTRACT["sources"]["s12_private_capture_sha256"],
        "safe_result_hash_pinned": evidence["safe_result_sha256"]
        == CONTRACT["sources"]["s12_safe_result_sha256"],
        "two_units": observations["connected_units"] == ["T1", "T2"],
        "stock_auto_refill_observed_enabled": observations["stock_auto_refill_value"] == 1,
        "no_identical_pair_in_capture": evidence["safe_observations"][
            "same_material_groups_without_identity"
        ]
        == [["T1A"], ["T1D"], ["T2A"], ["T2B"], ["T2C"], ["T2D"]],
        "capture_had_no_effect": all(value is False for value in evidence["boundaries"].values()),
    }
    return {"status": "OK" if all(checks.values()) else "KO", "checks": checks}


def run_one(scenario_id: str) -> Dict[str, Any]:
    case = build_case(scenario_id)
    return simulate(CONTRACT, case["snapshot"], case["inventory"], case["events"])


def run() -> Dict[str, Any]:
    source = verify_s12_source()
    expected_ids = CONTRACT["required_scenarios"]
    matrix_ids = [scenario["id"] for scenario in MATRIX["scenarios"]]
    if expected_ids != matrix_ids:
        return {
            "verdict": "KO",
            "reason": "scenario_order_or_coverage_mismatch",
            "passed": 0,
            "total": len(matrix_ids),
            "results": [],
            "printer_connection": False,
            "physical_action": False,
        }
    results = []
    for scenario in MATRIX["scenarios"]:
        result = run_one(scenario["id"])
        passed, detail = matches_expected(result, scenario["expected"])
        results.append(
            {
                "id": scenario["id"],
                "passed": passed,
                "detail": detail,
                "result": result,
            }
        )
    passed = sum(item["passed"] for item in results)
    all_green = passed == len(results) and source["status"] == "OK"
    return {
        "verdict": "OK" if all_green else "KO",
        "passed": passed,
        "total": len(results),
        "source_verification": source,
        "results": results,
        "printer_connection": False,
        "gcode_sent": False,
        "physical_action": False,
        "deployment_candidate": False,
    }


def main() -> int:
    result = run()
    for item in result["results"]:
        print("%s %s: %s" % ("OK" if item["passed"] else "KO", item["id"], item["detail"]))
    print("SOURCE %s" % result["source_verification"]["status"])
    print("TOTAL %d/%d" % (result["passed"], result["total"]))
    print("CFS_OWNER_CORE_OFFLINE_V1_%s" % result["verdict"])
    return 0 if result["verdict"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
