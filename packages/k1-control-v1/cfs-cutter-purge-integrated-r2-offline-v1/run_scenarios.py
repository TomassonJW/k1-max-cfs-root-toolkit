#!/usr/bin/env python3
"""Exécute la matrice déterministe du cycle R2, sans effet externe."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Callable, Optional

from engine import simulate
from fixtures import JOB, REGISTRY, events


PACKAGE = Path(__file__).resolve().parent


def by_kind(values: list[dict], kind: str) -> dict:
    return next(item for item in values if item["kind"] == kind)


def execute(
    name: str,
    mutate: Optional[Callable[[dict, list[dict], list[dict]], None]],
    expected_phase: str,
    expected_code: Optional[str] = None,
    *,
    round_trips: int = 3,
    include_tool_change: bool = True,
    include_equivalent_refill: bool = False,
) -> dict:
    job = deepcopy(JOB)
    registry = deepcopy(REGISTRY)
    flow = events(
        include_tool_change=include_tool_change,
        round_trips=round_trips,
        include_equivalent_refill=include_equivalent_refill,
    )
    if mutate:
        mutate(job, registry, flow)
    result = simulate(job, registry, flow)
    passed = result.get("phase") == expected_phase and result.get("failure_code") == expected_code
    return {
        "name": name,
        "passed": passed,
        "expected_phase": expected_phase,
        "expected_code": expected_code,
        "actual_phase": result.get("phase"),
        "actual_code": result.get("failure_code"),
        "printer_transport": result.get("printer_transport"),
        "physical_action": result.get("physical_action"),
    }


def run() -> dict:
    cases: list[dict] = []
    add = cases.append
    add(execute("happy_gcode_rules_3_round_trips", None, "closed_safe"))
    add(execute("happy_gcode_rules_4_round_trips", None, "closed_safe", round_trips=4))

    def cfs_fallback(job, _registry, flow):
        del job["gcode"]["filament_rules"]
        load = by_kind(flow, "load_complete")
        load["filament_rule_source"] = "cfs_fallback"
        load["load_c"] = 215.0
        for item in (by_kind(flow, "bin_purge_release_complete"), by_kind(flow, "tool_change_complete")["purge"]):
            item["purge_c"] = 225.0
            item["purge_mm"] = 24.0

    add(execute("happy_complete_cfs_fallback", cfs_fallback, "closed_safe"))

    add(
        execute(
            "happy_equivalent_refill_keeps_printing",
            None,
            "closed_safe",
            include_tool_change=False,
            include_equivalent_refill=True,
        )
    )

    def refill_near_match(_job, _registry, flow):
        by_kind(flow, "equivalent_refill_complete")["replacement_material"]["color"] = "FFFFFF"

    add(
        execute(
            "equivalent_refill_near_match_rejected",
            refill_near_match,
            "failed_safe",
            "equivalent_refill_material_not_identical",
            include_tool_change=False,
            include_equivalent_refill=True,
        )
    )

    def refill_ambiguous(_job, _registry, flow):
        by_kind(flow, "equivalent_refill_complete")["available_equivalent_routes"] = ["T2D", "T1D"]

    add(
        execute(
            "equivalent_refill_ambiguous_candidate_rejected",
            refill_ambiguous,
            "failed_safe",
            "equivalent_refill_candidate_not_unique",
            include_tool_change=False,
            include_equivalent_refill=True,
        )
    )

    def refill_stock_owner_conflict(_job, _registry, flow):
        by_kind(flow, "equivalent_refill_complete")["stock_auto_refill_disabled"] = False

    add(
        execute(
            "equivalent_refill_stock_owner_conflict_rejected",
            refill_stock_owner_conflict,
            "failed_safe",
            "stock_auto_refill_owner_conflict",
            include_tool_change=False,
            include_equivalent_refill=True,
        )
    )

    def no_profile(_job, registry, _flow):
        registry.clear()

    add(execute("missing_exact_thermal_profile", no_profile, "failed_safe", "exact_thermal_geometry_profile_missing"))

    def duplicate_profile(_job, registry, _flow):
        registry.append(deepcopy(registry[0]))

    add(execute("ambiguous_exact_thermal_profile", duplicate_profile, "failed_safe", "thermal_geometry_profile_ambiguous"))

    def mesh_6x6(_job, registry, _flow):
        registry[0]["mesh_points"] = [6, 6]

    add(execute("mesh_6x6_rejected", mesh_6x6, "failed_safe", "mesh_not_11x11"))

    def partial_rules(job, _registry, _flow):
        del job["gcode"]["filament_rules"]["purge_mm"]

    add(execute("partial_gcode_rules_rejected", partial_rules, "failed_safe", "partial_gcode_filament_rules_forbidden"))

    def no_fallback(job, _registry, _flow):
        del job["gcode"]["filament_rules"]
        job["cfs_fallback"] = {}

    add(execute("missing_cfs_fallback_rejected", no_fallback, "failed_safe", "complete_cfs_fallback_missing"))

    def route_before(_job, _registry, flow):
        by_kind(flow, "prepare")["routes"] = ["T1A"]

    add(execute("filament_route_before_references_rejected", route_before, "failed_safe", "filament_route_present_before_references"))

    def sensor_before(_job, _registry, flow):
        by_kind(flow, "prepare")["head_sensor"] = True

    add(execute("filament_sensor_before_references_rejected", sensor_before, "failed_safe", "filament_present_before_references"))

    def stale_clean(_job, _registry, flow):
        by_kind(flow, "clean_nozzle_confirmed")["fresh"] = False

    add(execute("stale_clean_confirmation_rejected", stale_clean, "failed_safe", "fresh_manual_clean_missing"))

    def wrong_probe_temperature(_job, _registry, flow):
        by_kind(flow, "references_complete")["probe_nozzle_c"] = 220.0

    add(execute("wrong_reference_probe_temperature_rejected", wrong_probe_temperature, "failed_safe", "reference_probe_temperature_mismatch"))

    def recalibrate(_job, _registry, flow):
        by_kind(flow, "references_complete")["mesh_calibrated"] = True

    add(execute("mesh_recalculation_in_daily_references_rejected", recalibrate, "failed_safe", "daily_mesh_recalculation_forbidden"))

    def wrong_profile(_job, _registry, flow):
        by_kind(flow, "geometry_applied")["profile_id"] = "other-profile"

    add(execute("wrong_geometry_profile_rejected", wrong_profile, "failed_safe", "thermal_geometry_profile_changed"))

    def wrong_heat(_job, _registry, flow):
        by_kind(flow, "heat_complete")["nozzle_target_c"] = 140.0

    add(execute("wrong_heat_target_rejected", wrong_heat, "failed_safe", "nozzle_temperature_mismatch"))

    def wrong_load_position(_job, _registry, flow):
        by_kind(flow, "load_complete")["head_xyz_mm"] = [0.0, 0.0, 30.0]

    add(execute("load_away_from_purge_station_rejected", wrong_load_position, "failed_safe", "load_not_at_purge_position"))

    def box_load(_job, _registry, flow):
        by_kind(flow, "load_complete")["commands"] = ["BOX_EXTRUDE_MATERIAL"]

    add(execute("stock_BOX_load_rejected", box_load, "failed_safe", "stock_BOX_effect_forbidden"))

    def release_2(_job, _registry, flow):
        item = by_kind(flow, "bin_purge_release_complete")
        item["release_round_trips"] = 2
        item["release_lanes_y_mm"] = [305.0, 304.0]

    add(execute("two_release_round_trips_rejected", release_2, "failed_safe", "release_requires_3_or_4_round_trips"))

    def release_5(_job, _registry, flow):
        item = by_kind(flow, "bin_purge_release_complete")
        item["release_round_trips"] = 5
        item["release_lanes_y_mm"] = [305.0, 304.0, 305.0, 304.0, 305.0]

    add(execute("five_release_round_trips_rejected", release_5, "failed_safe", "release_requires_3_or_4_round_trips"))

    def camera_ko(_job, _registry, flow):
        by_kind(flow, "bin_purge_release_complete")["camera_verdict"] = "FAIL"

    add(execute("camera_failure_rejected", camera_ko, "failed_safe", "purge_release_not_visually_proven"))

    def y120(_job, _registry, flow):
        by_kind(flow, "prime_line_complete")["path_xyz_mm"][1][1] = 120.0

    add(execute("Y120_prime_memory_rejected", y120, "failed_safe", "prime_line_geometry_unqualified"))

    def missing_z5(_job, _registry, flow):
        by_kind(flow, "prime_line_complete")["bed_lower_relative_mm"] = 0.0

    add(execute("missing_relative_5mm_release_rejected", missing_z5, "failed_safe", "post_prime_bed_lower_5mm_missing"))

    def probe_after(_job, _registry, flow):
        by_kind(flow, "print_started")["probe_count"] = 1

    add(execute("probe_after_load_rejected", probe_after, "failed_safe", "contact_after_filament_forbidden"))

    def no_cutter_change(_job, _registry, flow):
        by_kind(flow, "tool_change_complete")["cutter"] = None

    add(execute("tool_change_without_cutter_rejected", no_cutter_change, "failed_safe", "cutter_proof_missing"))

    def non_atomic_change(_job, _registry, flow):
        by_kind(flow, "tool_change_complete")["atomic_no_resume_between_steps"] = False

    add(execute("tool_change_without_atomic_purge_rejected", non_atomic_change, "failed_safe", "tool_change_not_atomic"))

    def box_change(_job, _registry, flow):
        by_kind(flow, "tool_change_complete")["commands"] = ["BOX_QUIT_MATERIAL"]

    add(execute("tool_change_stock_BOX_rejected", box_change, "failed_safe", "stock_BOX_effect_forbidden"))

    def end_g28(_job, _registry, flow):
        by_kind(flow, "end_unload_complete")["g28_count"] = 1

    add(execute("end_full_G28_rejected", end_g28, "failed_safe", "end_full_homing_forbidden"))

    def no_end_cutter(_job, _registry, flow):
        by_kind(flow, "end_unload_complete")["cutter"] = None

    add(execute("end_without_cutter_rejected", no_end_cutter, "failed_safe", "cutter_proof_missing"))

    def wrong_end_order(_job, _registry, flow):
        by_kind(flow, "end_unload_complete")["actions"][1:4] = [
            "direct_cfs_unload",
            "move_to_cutter",
            "cut_filament",
        ]

    add(execute("end_wrong_order_rejected", wrong_end_order, "failed_safe", "end_order_invalid"))

    def residual_end(_job, _registry, flow):
        by_kind(flow, "end_unload_complete")["head_sensor_after"] = True

    add(execute("end_sensor_residual_rejected", residual_end, "failed_safe", "end_unload_sensor_proof_missing"))

    def duplicate_effect(_job, _registry, flow):
        by_kind(flow, "end_unload_complete")["effect_id"] = "effect-initial-load"

    add(execute("duplicate_effect_rejected", duplicate_effect, "failed_safe", "duplicate_effect_rejected"))

    manifest = json.loads((PACKAGE / "scenarios.json").read_text(encoding="utf-8"))
    names = [item["name"] for item in cases]
    return {
        "status": "OK" if all(item["passed"] for item in cases) else "KO",
        "passed": sum(1 for item in cases if item["passed"]),
        "total": len(cases),
        "manifest_names_match": names == manifest["scenario_names"],
        "expected_total_match": len(cases) == manifest["expected_total"],
        "printer_transport": False,
        "physical_action": False,
        "cases": cases,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True))
