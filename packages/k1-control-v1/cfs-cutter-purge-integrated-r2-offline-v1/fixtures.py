"""Fixtures purement synthétiques du moteur R2 hors imprimante."""

from __future__ import annotations

from copy import deepcopy

from engine import CUTTER, PRIME_POINTS


REGISTRY = [
    {
        "profile_id": "synthetic_p001_b055_n220_r001",
        "plate_id": "PEI_TEXTURED_A",
        "bed_first_c": 55.0,
        "nozzle_first_c": 220.0,
        "probe_nozzle_c": 140.0,
        "mesh_profile": "synthetic_p001_b055_n220_n11x11",
        "mesh_points": [11, 11],
        "accepted_z_mm": -0.04,
        "accepted_z_status": "qualified",
        "status": "qualified",
        "synthetic_test_only": True,
    }
]

JOB = {
    "contract_version": 2,
    "job_id": "offline-reference",
    "filename": "offline-reference.gcode",
    "initial_route": "T1A",
    "plate_id": "PEI_TEXTURED_A",
    "gcode": {
        "bed_first_c": 55.0,
        "nozzle_first_c": 220.0,
        "filament_rules": {
            "load_c": 220.0,
            "unload_c": 220.0,
            "purge_c": 220.0,
            "purge_mm": 20.0,
        },
    },
    "cfs_fallback": {
        "load_c": 215.0,
        "unload_c": 210.0,
        "purge_c": 225.0,
        "purge_mm": 24.0,
    },
}


def cutter() -> dict:
    value = deepcopy(CUTTER)
    value.update({"cutter_choreography_qualified": True, "cut_observed": True})
    return value


def purge(route: str = "T1A", round_trips: int = 3) -> dict:
    return {
        "route": route,
        "purge_xyz_mm": [185.5, 305.0, 30.0],
        "safe_approach_xyz_mm": [203.0, 273.0, 32.0],
        "purge_c": 220.0,
        "purge_mm": 20.0,
        "release_round_trips": round_trips,
        "release_lanes_y_mm": [305.0 if index % 2 == 0 else 304.0 for index in range(round_trips)],
        "release_x_mm": [203.0, 206.0, 203.0],
        "release_z_mm": 32.0,
        "release_feedrate_mm_min": 180.0,
        "continuous_round_trips": True,
        "camera_verdict": "PASS",
        "purge_ball_dropped": True,
        "probe_count": 0,
        "mesh_recalculated": False,
        "commands": [],
    }


def material_identity() -> dict:
    return {
        "reference_id": "PLA-BLACK-001",
        "material_type": "PLA",
        "color": "000000",
        "diameter_mm": 1.75,
        "thermal_recipe_id": "PLA-220-V1",
        "user_approved": True,
    }


def events(
    include_tool_change: bool = True,
    round_trips: int = 3,
    include_equivalent_refill: bool = False,
) -> list[dict]:
    values = [
        {
            "kind": "prepare",
            "printer_state": "standby",
            "klippy_ready": True,
            "routes": [],
            "head_sensor": False,
            "after_cutter_sensor": False,
            "bed_target_c": 0.0,
            "nozzle_target_c": 0.0,
        },
        {
            "kind": "clean_nozzle_confirmed",
            "manual_clean": True,
            "fresh": True,
            "filament_loaded": False,
        },
        {
            "kind": "references_complete",
            "filament_loaded": False,
            "routes": [],
            "reference_axes": ["X", "Y", "Z"],
            "mesh_calibrated": False,
            "contact_after_clean": True,
            "probe_nozzle_c": 140.0,
        },
        {
            "kind": "geometry_applied",
            "profile_id": "synthetic_p001_b055_n220_r001",
            "mesh_profile": "synthetic_p001_b055_n220_n11x11",
            "mesh_points": [11, 11],
            "accepted_z_mm": -0.04,
            "actions": ["load_exact_11x11_profile", "apply_exact_canonical_z"],
            "probe_count": 0,
            "mesh_recalculated": False,
        },
        {
            "kind": "heat_complete",
            "bed_target_c": 55.0,
            "nozzle_target_c": 220.0,
            "targets_reached": True,
            "probe_count": 0,
            "mesh_recalculated": False,
        },
        {
            "kind": "load_complete",
            "operation": "initial-load",
            "effect_id": "effect-initial-load",
            "effect_observed": True,
            "route": "T1A",
            "head_xyz_mm": [185.5, 305.0, 30.0],
            "bed_lowered_for_load": True,
            "direct_owner": True,
            "automatic_retry": False,
            "filament_rule_source": "gcode",
            "load_c": 220.0,
            "head_sensor_after": True,
            "after_cutter_sensor_after": True,
            "probe_count": 0,
            "mesh_recalculated": False,
            "commands": ["KCTRL_DIRECT_LOAD"],
        },
        {
            "kind": "bin_purge_release_complete",
            "operation": "initial-bin-purge",
            "effect_id": "effect-initial-bin-purge",
            "effect_observed": True,
            **purge("T1A", round_trips),
        },
        {
            "kind": "prime_line_complete",
            "operation": "prime-line",
            "effect_id": "effect-prime-line",
            "effect_observed": True,
            "path_xyz_mm": deepcopy(PRIME_POINTS),
            "extrusion_mm": [0.0, 10.0, 0.0, 10.0, 0.0],
            "feedrate_mm_min": [6000, 3000, 3000, 3000, 3000],
            "bed_lower_relative_mm": 5.0,
            "relative_z_direction": "positive_toolhead_Z_lowers_bed",
            "probe_count": 0,
            "mesh_recalculated": False,
        },
        {
            "kind": "print_started",
            "filename": "offline-reference.gcode",
            "virtual_sd_state": "printing",
            "mesh_profile": "synthetic_p001_b055_n220_n11x11",
            "accepted_z_mm": -0.04,
            "probe_count": 0,
            "mesh_recalculated": False,
        },
    ]
    if include_tool_change:
        values.append(
            {
                "kind": "tool_change_complete",
                "operation": "tool-change",
                "effect_id": "effect-tool-change-1",
                "effect_observed": True,
                "from_route": "T1A",
                "to_route": "T2C",
                "cutter": cutter(),
                "direct_unload": True,
                "direct_load": True,
                "atomic_no_resume_between_steps": True,
                "purge": purge("T2C", round_trips),
                "head_sensor_after": True,
                "after_cutter_sensor_after": True,
                "probe_count": 0,
                "mesh_recalculated": False,
                "commands": ["KCTRL_DIRECT_UNLOAD", "KCTRL_DIRECT_LOAD"],
            }
        )
    if include_equivalent_refill:
        if include_tool_change:
            raise ValueError("synthetic_fixture_combines_tool_change_and_refill")
        values.append(
            {
                "kind": "equivalent_refill_complete",
                "operation": "equivalent-refill",
                "effect_id": "effect-equivalent-refill-1",
                "effect_observed": True,
                "runout_detected": True,
                "pause_latched": True,
                "stock_auto_refill_disabled": True,
                "from_route": "T1A",
                "to_route": "T2D",
                "available_equivalent_routes": ["T2D"],
                "exhausted_material": material_identity(),
                "replacement_material": material_identity(),
                "firmware_equivalence_group_configured": True,
                "tail_state_resolved": True,
                "active_nozzle_target_c": 220.0,
                "resume_nozzle_target_c": 220.0,
                "cutter": cutter(),
                "direct_unload": True,
                "direct_load": True,
                "atomic_no_resume_between_steps": True,
                "purge": purge("T2D", round_trips),
                "head_sensor_after": True,
                "after_cutter_sensor_after": True,
                "resume_context_preserved": True,
                "pause_still_latched_before_resume": True,
                "probe_count": 0,
                "mesh_recalculated": False,
                "commands": ["KCTRL_DIRECT_UNLOAD", "KCTRL_DIRECT_LOAD"],
            }
        )
    final_route = "T2C" if include_tool_change else "T2D" if include_equivalent_refill else "T1A"
    values.extend(
        [
            {
                "kind": "print_completed",
                "virtual_sd_state": "complete",
                "probe_count": 0,
                "mesh_recalculated": False,
            },
            {
                "kind": "end_unload_complete",
                "operation": "end-unload",
                "effect_id": "effect-end-unload",
                "effect_observed": True,
                "g28_count": 0,
                "actions": [
                    "safe_lift_and_lower_bed",
                    "move_to_cutter",
                    "cut_filament",
                    "direct_cfs_unload",
                    "safe_park",
                    "turn_off_heaters_and_fans",
                    "release_motors",
                ],
                "cutter": cutter(),
                "route_before": final_route,
                "direct_unload": True,
                "head_sensor_after": False,
                "after_cutter_sensor_after": False,
                "safe_park_verified": True,
                "heater_targets_zero": True,
                "fans_zero": True,
                "motors_released": True,
                "automatic_retry": False,
                "probe_count": 0,
                "mesh_recalculated": False,
                "commands": ["KCTRL_DIRECT_UNLOAD"],
            },
        ]
    )
    return values


def clone() -> tuple[dict, list[dict], list[dict]]:
    return deepcopy(JOB), deepcopy(REGISTRY), events()
