#!/usr/bin/env python3
"""Matrice déterministe de l'orchestrateur stock-derived hors imprimante."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "stock_derived_orchestrator_offline_v1",
    HERE / "orchestrator.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("orchestrator_import_spec_missing")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def material(
    reference_id: str = "pla-black",
    color: str = "black",
    recipe: str = "pla-190",
) -> Dict[str, Any]:
    return {
        "reference_id": reference_id,
        "material_type": "PLA",
        "color": color,
        "diameter_mm": 1.75,
        "thermal_recipe_id": recipe,
        "user_approved": True,
    }


def job(**changes: Any) -> Dict[str, Any]:
    result = {
        "job_id": "job-stock-v1",
        "filename": "K1-STOCK-DERIVED-TEST.gcode",
        "initial_route": "T1A",
        "mesh_profile": "k1_p001_t055_r001_n11x11",
        "accepted_z_mm": -0.04,
        "bed_c": 55,
        "probe_nozzle_c": 140,
        "first_nozzle_c": 190,
        "load_c": 200,
        "unload_c": 195,
        "purge_c": 205,
        "purge_mm": 20,
        "material_min_c": 180,
        "material_max_c": 230,
        "release_trips": 4,
    }
    result.update(changes)
    return result


def inventory(*, duplicate_spare: bool = False, near_only: bool = False):
    source = material()
    spare = material(color="charcoal") if near_only else material()
    result = [
        {"route": "T1A", "available": True, "material": source},
        {"route": "T1B", "available": True, "material": material("petg-red", "red", "petg-240")},
        {"route": "T2D", "available": True, "material": spare},
    ]
    if duplicate_spare:
        result.append({"route": "T2C", "available": True, "material": material()})
    return result


def proof(**changes: Any) -> Dict[str, Any]:
    result = {
        "outcome": "proved",
        "attempt_count": 1,
        "automatic_retry_count": 0,
    }
    result.update(changes)
    return result


def loaded_proof(route: str, **changes: Any) -> Dict[str, Any]:
    result = proof(
        route_after=route,
        head_sensor=True,
        after_cutter_sensor=True,
        purge_release_round_trips=4,
        probe_count=0,
        mesh_recalculated=False,
    )
    result.update(changes)
    return result


def prepare_printing(
    *,
    inventory_value=None,
    auto_refill_previous: int = 1,
):
    owner = MODULE.StockDerivedOrchestrator(job(), inventory_value or inventory())
    owner.acquire_owner(auto_refill_previous, 0, True)
    owner.observe_initial_filament([], False, False)
    owner.confirm_manual_clean(fresh=True, filament_loaded=False)
    geometry = owner.plan_geometry()
    owner.complete_geometry(
        geometry["ticket_id"],
        proof(
            filament_loaded=False,
            routes=[],
            reference_axes=["X", "Y", "Z"],
            mesh_recalculated=False,
            mesh_profile="k1_p001_t055_r001_n11x11",
            accepted_z_mm=-0.04,
            geometry_token="geometry_ready_for_stock_cycle",
        ),
    )
    load = owner.plan_initial_load_purge()
    owner.complete_initial_load_purge(load["ticket_id"], loaded_proof("T1A"))
    owner.confirm_release_camera("PASS", "camera-release-001")
    prime = owner.plan_initial_prime()
    owner.complete_initial_prime(
        prime["ticket_id"],
        proof(
            stock_prime_exact=True,
            relative_positive_z_mm=5,
            probe_count=0,
            mesh_recalculated=False,
        ),
    )
    owner.confirm_prime_camera("PASS", "camera-prime-001")
    owner.mark_print_started(
        {
            "filename": "K1-STOCK-DERIVED-TEST.gcode",
            "virtual_sd_state": "printing",
            "mesh_profile": "k1_p001_t055_r001_n11x11",
            "accepted_z_mm": -0.04,
            "route": "T1A",
            "probe_count": 0,
            "mesh_recalculated": False,
        }
    )
    return owner


def expect_error(call, code: str) -> None:
    try:
        call()
    except MODULE.OrchestratorError as error:
        if error.code != code:
            raise AssertionError("wrong_error:%s" % error.code)
        return
    raise AssertionError("expected_error_missing:%s" % code)


def pause_context(route: str = "T1A") -> Dict[str, Any]:
    return {
        "pause_latched": True,
        "engaged_route": route,
        "nozzle_target_c": 205.0,
        "bed_target_c": 55.0,
        "mesh_profile": "k1_p001_t055_r001_n11x11",
        "accepted_z_mm": -0.04,
        "file_position": 123456,
        "xyz": {"x": 100.0, "y": 120.0, "z": 2.4},
        "e": 42.0,
        "motion_modes": {"axes": "absolute", "extruder": "relative"},
        "fans": {"part": 0.6, "aux": 0.0},
    }


def scenario_complete_start_and_end_restores_auto_refill() -> None:
    owner = prepare_printing()
    ticket = owner.plan_end()
    assert ticket["command"].startswith("KCTRL_STOCK_CYCLE_END_V1 ROUTE=T1A")
    owner.complete_end(
        ticket["ticket_id"],
        proof(
            route_after=None,
            head_sensor=False,
            after_cutter_sensor=False,
            safe_park=True,
            heater_targets_zero=True,
            fans_zero=True,
            motors_released=True,
            probe_count=0,
            mesh_recalculated=False,
        ),
    )
    result = owner.release_owner(1, True)
    assert result["phase"] == "closed_safe"
    assert result["stock_auto_refill_owned"] is False
    assert result["active_route"] is None


def scenario_preclean_unloads_at_cutter_before_clean() -> None:
    owner = MODULE.StockDerivedOrchestrator(job(), inventory())
    owner.acquire_owner(1, 0, True)
    owner.observe_initial_filament(["T1A"], True, True)
    ticket = owner.plan_preclean_unload()
    assert "KCTRL_STOCK_CYCLE_CUT_UNLOAD_V1 ROUTE=T1A" in ticket["command"]
    owner.complete_preclean_unload(
        ticket["ticket_id"],
        proof(route_after=None, head_sensor=False, after_cutter_sensor=False),
    )
    assert owner.snapshot()["phase"] == "await_manual_clean"


def scenario_geometry_is_before_any_load_and_current_profile_only() -> None:
    owner = MODULE.StockDerivedOrchestrator(job(), inventory())
    owner.acquire_owner(1, 0, True)
    owner.observe_initial_filament([], False, False)
    owner.confirm_manual_clean(fresh=True, filament_loaded=False)
    ticket = owner.plan_geometry()
    assert ticket["kind"] == "geometry_before_filament"
    assert "KCTRL_PREPARE_GEOMETRY_BEFORE_INSERTION_R4" in ticket["command"]
    assert not any(word in ticket["command"] for word in ("LOAD_PURGE", "BOX_"))


def scenario_unqualified_thermal_geometry_is_closed_before_command() -> None:
    owner = MODULE.StockDerivedOrchestrator(
        job(mesh_profile="k1_p001_t060_r001_n11x11", bed_c=60), inventory()
    )
    owner.acquire_owner(1, 0, True)
    owner.observe_initial_filament([], False, False)
    owner.confirm_manual_clean(fresh=True, filament_loaded=False)
    expect_error(owner.plan_geometry, "thermal_geometry_runtime_not_qualified")
    assert owner.snapshot()["tickets"] == {}


def scenario_initial_load_uses_gcode_temperatures_and_four_release_trips() -> None:
    owner = MODULE.StockDerivedOrchestrator(job(), inventory())
    owner.acquire_owner(0, 0, True)
    owner.observe_initial_filament([], False, False)
    owner.confirm_manual_clean(fresh=True, filament_loaded=False)
    geometry = owner.plan_geometry()
    owner.complete_geometry(
        geometry["ticket_id"],
        proof(
            filament_loaded=False,
            routes=[],
            reference_axes=["X", "Y", "Z"],
            mesh_recalculated=False,
            mesh_profile="k1_p001_t055_r001_n11x11",
            accepted_z_mm=-0.04,
            geometry_token="geometry_ready_for_stock_cycle",
        ),
    )
    ticket = owner.plan_initial_load_purge()
    assert "LOAD_C=200 PURGE_C=205 PURGE_MM=20 TRIPS=4" in ticket["command"]
    assert "BOX_" not in ticket["command"]


def scenario_post_filament_probe_is_rejected() -> None:
    owner = MODULE.StockDerivedOrchestrator(job(), inventory())
    owner.acquire_owner(1, 0, True)
    owner.observe_initial_filament([], False, False)
    owner.confirm_manual_clean(fresh=True, filament_loaded=False)
    geometry = owner.plan_geometry()
    owner.complete_geometry(
        geometry["ticket_id"],
        proof(
            filament_loaded=False,
            routes=[],
            reference_axes=["X", "Y", "Z"],
            mesh_recalculated=False,
            mesh_profile="k1_p001_t055_r001_n11x11",
            accepted_z_mm=-0.04,
            geometry_token="geometry_ready_for_stock_cycle",
        ),
    )
    load = owner.plan_initial_load_purge()
    expect_error(
        lambda: owner.complete_initial_load_purge(
            load["ticket_id"], loaded_proof("T1A", probe_count=1)
        ),
        "contact_after_filament_forbidden",
    )


def scenario_tool_change_is_atomic_cut_unload_load_purge() -> None:
    owner = prepare_printing()
    ticket = owner.plan_tool_change("T1B")
    lines = ticket["command"].splitlines()
    assert lines[0].startswith("KCTRL_STOCK_CYCLE_CUT_UNLOAD_V1 ROUTE=T1A")
    assert lines[1].startswith("KCTRL_STOCK_CYCLE_LOAD_PURGE_V1 ROUTE=T1B")
    owner.complete_tool_change(ticket["ticket_id"], loaded_proof("T1B"))
    owner.confirm_tool_change_camera("PASS", "camera-change-001")
    result = owner.snapshot()
    assert result["phase"] == "printing" and result["active_route"] == "T1B"
    assert result["tool_changes"] == 1


def scenario_unique_identical_refill_crosses_cfs_and_resumes() -> None:
    owner = prepare_printing()
    context = pause_context()
    ticket = owner.plan_equivalent_refill(context)
    lines = ticket["command"].splitlines()
    assert lines[0].startswith("KCTRL_STOCK_CYCLE_REFILL_GUARD_V1 FROM=T1A TO=T2D")
    assert "CANDIDATES=1 PAUSE_LATCHED=1" in lines[0]
    owner.complete_equivalent_refill(
        ticket["ticket_id"],
        loaded_proof("T2D", pause_still_latched=True, active_nozzle_target_c=205),
    )
    owner.confirm_refill_camera_and_resume(
        "PASS", "camera-refill-001", context
    )
    result = owner.snapshot()
    assert result["phase"] == "printing" and result["active_route"] == "T2D"
    assert result["equivalent_refills"] == 1


def scenario_near_match_refill_is_rejected() -> None:
    owner = prepare_printing(inventory_value=inventory(near_only=True))
    expect_error(
        lambda: owner.plan_equivalent_refill(pause_context()),
        "identical_replacement_missing",
    )


def scenario_ambiguous_identical_refill_is_rejected() -> None:
    owner = prepare_printing(inventory_value=inventory(duplicate_spare=True))
    expect_error(
        lambda: owner.plan_equivalent_refill(pause_context()),
        "identical_replacement_ambiguous",
    )


def scenario_refill_resume_context_must_be_exact() -> None:
    owner = prepare_printing()
    context = pause_context()
    ticket = owner.plan_equivalent_refill(context)
    owner.complete_equivalent_refill(
        ticket["ticket_id"],
        loaded_proof("T2D", pause_still_latched=True, active_nozzle_target_c=205),
    )
    changed = dict(context)
    changed["file_position"] += 1
    expect_error(
        lambda: owner.confirm_refill_camera_and_resume(
            "PASS", "camera-refill-context", changed
        ),
        "runout_resume_context_changed",
    )


def scenario_claimed_ticket_recovery_blocks_without_replay() -> None:
    owner = prepare_printing()
    ticket = owner.plan_tool_change("T1B")
    persisted = owner.snapshot()
    expect_error(
        lambda: MODULE.StockDerivedOrchestrator(job(), inventory(), persisted),
        "claimed_ticket_recovered_without_outcome",
    )
    assert ticket["attempt_count"] == 1 and ticket["automatic_retry_count"] == 0


def scenario_explicit_unknown_outcome_blocks_without_retry() -> None:
    owner = prepare_printing()
    ticket = owner.plan_tool_change("T1B")
    expect_error(
        lambda: owner.mark_ticket_uncertain(ticket["ticket_id"]),
        "effect_outcome_unknown_no_retry",
    )
    result = owner.snapshot()
    assert result["phase"] == "blocked_uncertain"
    assert result["tickets"][ticket["ticket_id"]]["attempt_count"] == 1


def scenario_camera_failure_never_opens_model() -> None:
    owner = prepare_printing()
    ticket = owner.plan_tool_change("T1B")
    owner.complete_tool_change(ticket["ticket_id"], loaded_proof("T1B"))
    expect_error(
        lambda: owner.confirm_tool_change_camera("FAIL", "camera-fail"),
        "camera_proof_missing",
    )
    assert owner.snapshot()["phase"] == "failed_safe"


def scenario_no_stock_box_or_contact_command_is_encoded_after_geometry() -> None:
    owner = prepare_printing()
    change = owner.plan_tool_change("T1B")
    for forbidden in ("BOX_", "G28", "BED_MESH_CALIBRATE", "CX_PRINT_LEVELING_CALIBRATION"):
        assert forbidden not in change["command"]


def scenario_boolean_stock_policy_is_rejected() -> None:
    owner = MODULE.StockDerivedOrchestrator(job(), inventory())
    expect_error(
        lambda: owner.acquire_owner(True, 0, True),
        "stock_auto_refill_previous_invalid",
    )


def scenario_stock_owner_exclusion_must_be_proven_zero() -> None:
    owner = MODULE.StockDerivedOrchestrator(job(), inventory())
    expect_error(
        lambda: owner.acquire_owner(1, 1, True),
        "stock_auto_refill_exclusion_not_proven",
    )


def scenario_tool_change_target_must_be_available() -> None:
    slots = inventory()
    for slot in slots:
        if slot["route"] == "T1B":
            slot["available"] = False
    owner = prepare_printing(inventory_value=slots)
    expect_error(
        lambda: owner.plan_tool_change("T1B"),
        "target_route_not_available",
    )


def scenario_persistent_state_rejects_inventory_and_ticket_tampering() -> None:
    owner = prepare_printing()
    owner.plan_tool_change("T1B")
    persisted = owner.snapshot()
    changed_inventory = inventory()
    changed_inventory[1]["available"] = False
    expect_error(
        lambda: MODULE.StockDerivedOrchestrator(job(), changed_inventory, persisted),
        "persistent_state_invalid",
    )
    tampered = dict(persisted)
    tampered["tickets"] = {
        key: dict(value) for key, value in persisted["tickets"].items()
    }
    pending = tampered["pending_ticket"]
    tampered["tickets"][pending]["command"] += " EXTRA=1"
    expect_error(
        lambda: MODULE.StockDerivedOrchestrator(job(), inventory(), tampered),
        "persistent_ticket_invalid",
    )


SCENARIOS = (
    scenario_complete_start_and_end_restores_auto_refill,
    scenario_preclean_unloads_at_cutter_before_clean,
    scenario_geometry_is_before_any_load_and_current_profile_only,
    scenario_unqualified_thermal_geometry_is_closed_before_command,
    scenario_initial_load_uses_gcode_temperatures_and_four_release_trips,
    scenario_post_filament_probe_is_rejected,
    scenario_tool_change_is_atomic_cut_unload_load_purge,
    scenario_unique_identical_refill_crosses_cfs_and_resumes,
    scenario_near_match_refill_is_rejected,
    scenario_ambiguous_identical_refill_is_rejected,
    scenario_refill_resume_context_must_be_exact,
    scenario_claimed_ticket_recovery_blocks_without_replay,
    scenario_explicit_unknown_outcome_blocks_without_retry,
    scenario_camera_failure_never_opens_model,
    scenario_no_stock_box_or_contact_command_is_encoded_after_geometry,
    scenario_boolean_stock_policy_is_rejected,
    scenario_stock_owner_exclusion_must_be_proven_zero,
    scenario_tool_change_target_must_be_available,
    scenario_persistent_state_rejects_inventory_and_ticket_tampering,
)


def run() -> Dict[str, Any]:
    cases = []
    for scenario in SCENARIOS:
        try:
            scenario()
            cases.append({"name": scenario.__name__.replace("scenario_", ""), "passed": True})
        except Exception as error:
            cases.append(
                {
                    "name": scenario.__name__.replace("scenario_", ""),
                    "passed": False,
                    "error": repr(error),
                }
            )
    passed = sum(1 for case in cases if case["passed"])
    return {
        "status": "OK" if passed == len(cases) else "KO",
        "passed": passed,
        "total": len(cases),
        "cases": cases,
        "printer_transport": False,
        "physical_action": False,
        "deployment_candidate": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True))
