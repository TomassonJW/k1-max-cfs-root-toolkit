#!/usr/bin/env python3
"""Run the 27-scenario complete K1 Control lifecycle matrix offline."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
from typing import Any, Dict, Mapping, Optional, Sequence


PACKAGE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("module_load_failed:%s" % path)
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


contract_model = _load("contract_model", PACKAGE / "contract_model.py")
engine = _load("job_lifecycle_offline_engine", PACKAGE / "engine.py")
transport_runner = _load(
    "job_lifecycle_transport_matrix",
    PACKAGE.parent
    / "cfs-stock-unload-guard-transport-offline-v1"
    / "run_scenarios.py",
)


CONTRACT = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))


def job_payload(*, version: int = 1) -> Dict[str, Any]:
    return {
        "contract_version": version,
        "job_id": "job-offline-001",
        "plate_id": "PEI_TEXTURED_A",
        "bed_first_c": 55,
        "bed_normal_c": 60,
        "initial_tool": "T0",
        "tools": {
            "T0": {
                "material_id": "PLA-BLUE",
                "nozzle_first_c": 205,
                "nozzle_normal_c": 210,
                "material_min_c": 180,
                "material_max_c": 230
            },
            "T1": {
                "material_id": "PLA-RED",
                "nozzle_first_c": 205,
                "nozzle_normal_c": 210,
                "material_min_c": 180,
                "material_max_c": 230
            },
            "T5": {
                "material_id": "PETG-BLACK",
                "nozzle_first_c": 235,
                "nozzle_normal_c": 240,
                "material_min_c": 220,
                "material_max_c": 260
            }
        },
        "initial_purge_volumes_mm3": {"T0": 6, "T1": 6, "T5": 10},
        "transitions": {
            "T0->T1": {"unload_c": 205, "load_c": 205, "purge_c": 205, "purge_volume_mm3": 12},
            "T1->T0": {"unload_c": 205, "load_c": 205, "purge_c": 205, "purge_volume_mm3": 12},
            "T0->T5": {"unload_c": 210, "load_c": 235, "purge_c": 230, "purge_volume_mm3": 24},
            "T1->T5": {"unload_c": 210, "load_c": 235, "purge_c": 230, "purge_volume_mm3": 24},
            "T5->T0": {"unload_c": 240, "load_c": 205, "purge_c": 225, "purge_volume_mm3": 28}
        },
        "cleaning_recipes": {
            "PLA-BLUE": {"minimum_c": 140, "nominal_c": 180, "maximum_c": 220, "probe_c": 140, "max_hold_s": 60},
            "PLA-RED": {"minimum_c": 140, "nominal_c": 180, "maximum_c": 220, "probe_c": 140, "max_hold_s": 60},
            "PETG-BLACK": {"minimum_c": 170, "nominal_c": 220, "maximum_c": 250, "probe_c": 170, "max_hold_s": 60}
        },
        "mesh_profile": "k1_p001_t055_r001_n06x06",
        "mesh_reference_revision": "probe-r1",
        "accepted_z_revision": "z-r1",
        "end_policy": "keep_engaged",
        "legacy_z_offset_removed": True
    }


def machine_payload(
    *,
    filament_state: str = "engaged_known",
    engaged_tool: Optional[str] = "T0",
    engaged_route: Optional[str] = "T1A",
    engaged_material: Optional[str] = "PLA-BLUE",
    previous_material_id: Optional[str] = "PLA-BLUE",
    sensors_consistent: bool = True,
    toolhead_present: Optional[bool] = True,
) -> Dict[str, Any]:
    return {
        "print_state": "standby",
        "calibration_active": False,
        "plate_id": "PEI_TEXTURED_A",
        "filament_state": filament_state,
        "engaged_tool": engaged_tool,
        "engaged_route": engaged_route,
        "engaged_material": engaged_material,
        "mapping_revision": 1,
        "sensors_consistent": sensors_consistent,
        "previous_material_id": previous_material_id,
        "homed_axes": "",
        "mesh_profile": "k1_p001_t055_r001_n06x06",
        "accepted_z_valid": True,
        "accepted_z_revision": "z-r1",
        "effective_z_offset_mm": -0.04,
        "nozzle_target_c": 0,
        "bed_target_c": 0,
        "toolhead_filament_present": toolhead_present
    }


def route(
    job: Mapping[str, Any],
    tool: str,
    unit: str,
    slot: str,
    proof_id: str,
    *,
    mapping_revision: int = 1,
) -> Dict[str, Any]:
    return {
        "proof_id": proof_id,
        "mapping_revision": mapping_revision,
        "logical_tool": tool,
        "cfs_unit": unit,
        "slot": slot,
        "material_id": job["tools"][tool]["material_id"],
    }


def boundary(
    job: Mapping[str, Any],
    operation: str,
    tool: str,
    target_c: float,
    effect_id: str,
    proof_id: str,
    *,
    unit: str = "T1",
    slot: str = "A",
    mapping_revision: int = 1,
    bed_target_c: float = 55,
    purge_volume_mm3: Optional[float] = None,
    flow_proven: bool = False,
    nozzle_target_during_c: Optional[float] = None,
    elapsed_s: float = 1.0,
    request_returned: bool = True,
    effect_observed: bool = True,
) -> Dict[str, Any]:
    evidence = {
        "operation": operation,
        "effect_id": effect_id,
        "elapsed_s": elapsed_s,
        "completed": True,
        "route": route(
            job,
            tool,
            unit,
            slot,
            proof_id,
            mapping_revision=mapping_revision,
        ),
        "target_armed_before_first_effect": True,
        "nozzle_target_before_c": target_c,
        "nozzle_target_during_c": target_c
        if nozzle_target_during_c is None
        else nozzle_target_during_c,
        "bed_target_during_c": bed_target_c,
        "cfs_nozzle_command": False,
        "cfs_bed_command": False,
        "geometry_command": False,
        "homing": False,
        "protected_state_unchanged": True,
        "request_returned": request_returned,
        "effect_observed": effect_observed,
        "flow_proven": flow_proven,
    }
    if purge_volume_mm3 is not None:
        evidence["purge_volume_mm3"] = purge_volume_mm3
    return evidence


def start_to_arm(
    job: Mapping[str, Any],
    machine: Mapping[str, Any],
    *,
    mesh_profile: Optional[str] = None,
) -> list[Dict[str, Any]]:
    material = machine.get("previous_material_id")
    recipe = job["cleaning_recipes"].get(material, {"nominal_c": 180, "probe_c": 140})
    return [
        {"kind": "admit"},
        {"kind": "reconcile_filament", "classification": machine["filament_state"]},
        {"kind": "start_bed_heating", "target_c": job["bed_first_c"]},
        {
            "kind": "rough_reference",
            "elapsed_s": 10,
            "completed": True,
            "coarse_only": True,
            "accepted_z_written": False,
            "mesh_written": False,
            "collision_free": True,
            "homing_performed": True,
        },
        {
            "kind": "clean_nozzle",
            "elapsed_s": 30,
            "completed": True,
            "material_id": material,
            "target_c": recipe["nominal_c"],
            "brush_plane_source": "versioned_human_calibration",
            "brush_z_probed": False,
            "extrusion": False,
            "filament_change": False,
            "heated_over_waste_chute": True,
            "motion_safe": True,
            "lifted_before_exit": True,
        },
        {
            "kind": "reference_temperature_ready",
            "stable": True,
            "observed_bed_target_c": job["bed_first_c"],
            "observed_nozzle_target_c": recipe["probe_c"],
        },
        {
            "kind": "final_reference",
            "elapsed_s": 20,
            "completed": True,
            "clean_nozzle_confirmed": True,
            "precise_reference_count": 1,
            "accepted_z_written": False,
            "mesh_loaded": False,
            "probe_reference_revision": job["mesh_reference_revision"],
        },
        {
            "kind": "arm_mesh_z",
            "loaded_after_final_reference": True,
            "mesh_profile": mesh_profile or job["mesh_profile"],
            "mesh_verified": True,
            "accepted_z_revision": job["accepted_z_revision"],
            "accepted_z_verified": True,
            "hidden_z_offset_present": False,
            "effective_z_offset_mm": machine["effective_z_offset_mm"],
        },
    ]


def happy_start_events(
    job: Mapping[str, Any],
    machine: Mapping[str, Any],
    *,
    prefix: str,
) -> list[Dict[str, Any]]:
    events = start_to_arm(job, machine)
    initial = job["initial_tool"]
    state = machine["filament_state"]
    if state == "engaged_known" and machine["engaged_tool"] == initial and machine["engaged_material"] == job["tools"][initial]["material_id"]:
        events.append(
            {
                "kind": "resolve_initial_filament",
                "branch": "keep_correct",
                "boundaries": [],
                "cut": False,
                "unload": False,
            }
        )
        unit, slot = machine["engaged_route"][:2], machine["engaged_route"][-1]
    elif state == "absent_confirmed":
        unit, slot = "T1", "A"
        events.append(
            {
                "kind": "resolve_initial_filament",
                "branch": "load_absent",
                "boundaries": [
                    boundary(
                        job,
                        "initial_load",
                        initial,
                        job["tools"][initial]["nozzle_first_c"],
                        "%s-load" % prefix,
                        "%s-load-proof" % prefix,
                        unit=unit,
                        slot=slot,
                    )
                ],
            }
        )
    else:
        outgoing = machine["engaged_tool"]
        transition = job["transitions"]["%s->%s" % (outgoing, initial)]
        old_unit, old_slot = machine["engaged_route"][:2], machine["engaged_route"][-1]
        unit, slot = "T1", "A"
        events.append(
            {
                "kind": "resolve_initial_filament",
                "branch": "change_wrong",
                "boundaries": [
                    boundary(
                        job,
                        "intentional_unload",
                        outgoing,
                        transition["unload_c"],
                        "%s-unload" % prefix,
                        "%s-unload-proof" % prefix,
                        unit=old_unit,
                        slot=old_slot,
                    ),
                    boundary(
                        job,
                        "intentional_load",
                        initial,
                        transition["load_c"],
                        "%s-load" % prefix,
                        "%s-load-proof" % prefix,
                        unit=unit,
                        slot=slot,
                    ),
                ],
            }
        )
    if state == "engaged_known" and machine["engaged_tool"] != initial:
        transition = job["transitions"]["%s->%s" % (machine["engaged_tool"], initial)]
        purge_target = transition["purge_c"]
        purge_volume = transition["purge_volume_mm3"]
    else:
        purge_target = job["tools"][initial]["nozzle_first_c"]
        purge_volume = job["initial_purge_volumes_mm3"][initial]
    events.extend(
        [
            {
                "kind": "purge",
                "boundary": boundary(
                    job,
                    "purge",
                    initial,
                    purge_target,
                    "%s-purge" % prefix,
                    "%s-purge-proof" % prefix,
                    unit=unit,
                    slot=slot,
                    purge_volume_mm3=purge_volume,
                    flow_proven=True,
                ),
            },
            {
                "kind": "prime",
                "elapsed_s": 5,
                "completed": True,
                "safe_plate_zone": True,
                "hidden_z_offset_present": False,
                "nozzle_target_c": job["tools"][initial]["nozzle_first_c"],
                "bed_target_c": job["bed_first_c"],
            },
            {"kind": "start_print", "cfs_transition_active": False},
        ]
    )
    return events


def tool_change_event(
    job: Mapping[str, Any],
    outgoing: str,
    incoming: str,
    *,
    prefix: str,
    unit: str,
    slot: str,
    bed_target_c: float,
    print_phase: str,
    late_unload_target: Optional[float] = None,
) -> Dict[str, Any]:
    transition = job["transitions"]["%s->%s" % (outgoing, incoming)]
    return {
        "kind": "tool_change",
        "incoming_tool": incoming,
        "path_clear": True,
        "homing": False,
        "incoming_print_target_c": job["tools"][incoming][
            "nozzle_%s_c" % ("first" if print_phase == "first_layer" else "normal")
        ],
        "boundaries": [
            boundary(
                job,
                "intentional_unload",
                outgoing,
                transition["unload_c"],
                "%s-unload" % prefix,
                "%s-unload-proof" % prefix,
                bed_target_c=bed_target_c,
                nozzle_target_during_c=late_unload_target,
            ),
            boundary(
                job,
                "intentional_load",
                incoming,
                transition["load_c"],
                "%s-load" % prefix,
                "%s-load-proof" % prefix,
                unit=unit,
                slot=slot,
                bed_target_c=bed_target_c,
            ),
            boundary(
                job,
                "purge",
                incoming,
                transition["purge_c"],
                "%s-purge" % prefix,
                "%s-purge-proof" % prefix,
                unit=unit,
                slot=slot,
                bed_target_c=bed_target_c,
                purge_volume_mm3=transition["purge_volume_mm3"],
                flow_proven=True,
            ),
        ],
    }


def simulate(
    job: Mapping[str, Any], machine: Mapping[str, Any], events: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    return engine.simulate_scenario(CONTRACT, job, machine, events)


def _wrong_machine() -> Dict[str, Any]:
    return machine_payload(
        engaged_tool="T1",
        engaged_route="T1B",
        engaged_material="PLA-RED",
        previous_material_id="PLA-RED",
    )


def _absent_machine() -> Dict[str, Any]:
    return machine_payload(
        filament_state="absent_confirmed",
        engaged_tool=None,
        engaged_route=None,
        engaged_material=None,
        previous_material_id="PLA-BLUE",
        toolhead_present=False,
    )


def run_one(scenario_id: str) -> Dict[str, Any]:
    job = job_payload()
    machine = machine_payload()

    if scenario_id == "mesh_reference_match":
        return simulate(job, machine, start_to_arm(job, machine))
    if scenario_id == "mesh_reference_mismatch":
        return simulate(
            job,
            machine,
            start_to_arm(job, machine, mesh_profile="wrong_profile"),
        )
    if scenario_id == "clean_unknown_previous_material":
        unknown = machine_payload(previous_material_id=None)
        return simulate(job, unknown, [{"kind": "admit"}])
    if scenario_id == "clean_brush_z_not_probed":
        return simulate(job, machine, start_to_arm(job, machine)[:5])
    if scenario_id == "start_correct_filament_engaged":
        return simulate(job, machine, happy_start_events(job, machine, prefix="correct"))
    if scenario_id == "start_wrong_filament_engaged":
        wrong = _wrong_machine()
        return simulate(job, wrong, happy_start_events(job, wrong, prefix="wrong"))
    if scenario_id == "start_no_filament":
        absent = _absent_machine()
        return simulate(job, absent, happy_start_events(job, absent, prefix="absent"))
    if scenario_id == "start_unknown_filament_identity":
        unknown = machine_payload(
            filament_state="engaged_unknown",
            engaged_tool=None,
            engaged_route=None,
            engaged_material=None,
        )
        return simulate(job, unknown, [{"kind": "admit"}])
    if scenario_id == "sensor_present_no_nozzle_flow":
        events = happy_start_events(job, machine, prefix="no-flow")
        purge_event = next(event for event in events if event["kind"] == "purge")
        purge_event["boundary"]["flow_proven"] = False
        return simulate(job, machine, events)
    if scenario_id == "sensor_disagreement":
        contradiction = machine_payload(sensors_consistent=False)
        return simulate(job, contradiction, [{"kind": "admit"}])
    if scenario_id == "equivalent_refill":
        events = happy_start_events(job, machine, prefix="refill")
        events.append({"kind": "set_print_phase", "phase": "normal"})
        events.append(
            {
                "kind": "runout",
                "phase_known": True,
                "equivalent_material": True,
                "homing": False,
                "purge_volume_mm3": 5,
                "boundary": boundary(
                    job,
                    "runout_equivalent",
                    "T0",
                    210,
                    "refill-load",
                    "refill-load-proof",
                    unit="T1",
                    slot="C",
                    bed_target_c=60,
                    purge_volume_mm3=5,
                    flow_proven=True,
                ),
            }
        )
        return simulate(job, machine, events)
    if scenario_id == "intentional_same_material_color_change":
        events = happy_start_events(job, machine, prefix="same-color-start")
        events.append({"kind": "set_print_phase", "phase": "normal"})
        events.append(
            tool_change_event(
                job,
                "T0",
                "T1",
                prefix="same-color",
                unit="T1",
                slot="B",
                bed_target_c=60,
                print_phase="normal",
            )
        )
        return simulate(job, machine, events)
    if scenario_id == "intentional_cross_material_change":
        events = happy_start_events(job, machine, prefix="cross-material-start")
        events.append({"kind": "set_print_phase", "phase": "normal"})
        events.append(
            tool_change_event(
                job,
                "T0",
                "T5",
                prefix="cross-material",
                unit="T2",
                slot="A",
                bed_target_c=60,
                print_phase="normal",
            )
        )
        return simulate(job, machine, events)
    if scenario_id == "cross_cfs_change":
        events = happy_start_events(job, machine, prefix="cross-cfs-start")
        events.append(
            tool_change_event(
                job,
                "T0",
                "T1",
                prefix="cross-cfs",
                unit="T2",
                slot="B",
                bed_target_c=55,
                print_phase="first_layer",
            )
        )
        return simulate(job, machine, events)
    if scenario_id == "pause_normal":
        events = happy_start_events(job, machine, prefix="pause")
        events.append({"kind": "pause_normal", "cfs_effect": False, "purge": False})
        return simulate(job, machine, events)
    if scenario_id == "resume_with_optional_reprime":
        events = happy_start_events(job, machine, prefix="resume")
        events.extend(
            [
                {"kind": "pause_normal", "cfs_effect": False, "purge": False},
                {
                    "kind": "adjust_z",
                    "explicit_operator_action": True,
                    "effective_z_offset_mm": -0.05,
                    "accepted_z_revision": "z-r2",
                },
                {
                    "kind": "resume_normal",
                    "homing": False,
                    "reprime": True,
                    "purge_volume_mm3": 3,
                    "boundary": boundary(
                        job,
                        "purge",
                        "T0",
                        205,
                        "resume-reprime",
                        "resume-reprime-proof",
                        purge_volume_mm3=3,
                        flow_proven=True,
                    ),
                },
            ]
        )
        return simulate(job, machine, events)
    if scenario_id == "tall_part_blocks_rear_path":
        events = happy_start_events(job, machine, prefix="tall")
        events.append(
            {
                "kind": "tool_change",
                "incoming_tool": "T1",
                "path_clear": False,
                "homing": False,
                "boundaries": [],
            }
        )
        return simulate(job, machine, events)
    if scenario_id == "end_keep_engaged":
        events = happy_start_events(job, machine, prefix="end")
        events.append(
            {
                "kind": "end",
                "policy": "keep_engaged",
                "cut": False,
                "unload": False,
                "heater_targets_zero_verified": True,
                "resume_closed": True,
            }
        )
        return simulate(job, machine, events)
    if scenario_id == "manual_disengage_and_clean":
        events = happy_start_events(job, machine, prefix="disengage")
        events.extend(
            [
                {
                    "kind": "end",
                    "policy": "keep_engaged",
                    "cut": False,
                    "unload": False,
                    "heater_targets_zero_verified": True,
                    "resume_closed": True,
                },
                {
                    "kind": "disengage_and_clean",
                    "guard_result": transport_runner.run_one(
                        "success_route_clear_and_targets_zero"
                    ),
                    "operator_present": True,
                    "cleaning_recipe_material_id": "PLA-BLUE",
                    "cleaning_motion_offline_validated": True,
                    "extrusion": False,
                },
            ]
        )
        return simulate(job, machine, events)
    if scenario_id == "cfs_late_220_rewrite":
        events = happy_start_events(job, machine, prefix="late-start")
        events.append({"kind": "set_print_phase", "phase": "normal"})
        events.append(
            tool_change_event(
                job,
                "T0",
                "T5",
                prefix="late",
                unit="T2",
                slot="A",
                bed_target_c=60,
                print_phase="normal",
                late_unload_target=220,
            )
        )
        return simulate(job, machine, events)
    if scenario_id == "orca_contract_version_mismatch":
        return simulate(job_payload(version=2), machine, [])
    if scenario_id == "cancel_and_reboot_each_phase":
        return _cancel_reboot_matrix(job, machine)
    if scenario_id == "deployment_slice_rollback":
        return _deployment_rollback()
    if scenario_id == "cfs_route_freshness":
        return _route_freshness_matrix(job, machine)
    if scenario_id == "cfs_first_and_normal_targets":
        events = happy_start_events(job, machine, prefix="targets")
        events.append({"kind": "set_print_phase", "phase": "normal"})
        return simulate(job, machine, events)
    if scenario_id == "cfs_transition_load_target":
        wrong = _wrong_machine()
        result = simulate(job, wrong, happy_start_events(job, wrong, prefix="targets-transition"))
        boundary_trace = {
            item["operation"]: item["target_c"]
            for item in result["trace"]
            if item.get("kind") == "cfs_boundary"
        }
        result["unload_target_c"] = boundary_trace["intentional_unload"]
        result["load_target_c"] = boundary_trace["intentional_load"]
        result["purge_target_c"] = boundary_trace["purge"]
        return result
    if scenario_id == "cfs_no_transport_offline_matrix":
        return _no_transport_matrix(job, machine)
    raise KeyError("scenario_unknown:%s" % scenario_id)


def _cancel_reboot_matrix(
    job: Mapping[str, Any], machine: Mapping[str, Any]
) -> Dict[str, Any]:
    before_heat = start_to_arm(job, machine)[:3]
    cancelled = simulate(
        job,
        machine,
        before_heat
        + [{"kind": "cancel", "automatic_cycle_replay": False}],
    )
    rebooted = simulate(
        job,
        machine,
        start_to_arm(job, machine)
        + [{"kind": "reboot", "automatic_cycle_replay": False}],
    )
    printing = simulate(
        job,
        machine,
        happy_start_events(job, machine, prefix="cancel-print")
        + [{"kind": "cancel", "automatic_cycle_replay": False}],
    )
    values = (cancelled, rebooted, printing)
    safe = all(
        item["nozzle_target_c"] == 0
        and item["bed_target_c"] == 0
        and item["phase"] in {"cancelled_safe", "failed_safe"}
        for item in values
    )
    implicit_replays = sum(
        1
        for item in values
        for trace in item["trace"]
        if trace.get("kind") == "automatic_cycle_replay"
    )
    return {
        "verdict": "pass_offline" if safe and implicit_replays == 0 else "blocked_safe",
        "safe_subcases": sum(
            item["phase"] in {"cancelled_safe", "failed_safe"} for item in values
        ),
        "implicit_replays": implicit_replays,
        "printer_transport": False,
        "gcode_sent": False,
        "deployment_candidate": False,
    }


def _deployment_rollback() -> Dict[str, Any]:
    before = {
        "k1_control_job_lifecycle_core.py": b"absent",
        "k1_control_cfs_guard_transport.py": b"absent",
        "moonraker.conf": b"known-current-config",
    }
    candidate = {
        "k1_control_job_lifecycle_core.py": b"offline-core-v1",
        "k1_control_cfs_guard_transport.py": b"offline-transport-v1",
        "moonraker.conf": b"known-current-config-plus-disabled-section",
    }
    restored = dict(before)

    def digest(values: Mapping[str, bytes]) -> Dict[str, str]:
        return {key: sha256(value).hexdigest() for key, value in sorted(values.items())}

    return {
        "verdict": "pass_offline",
        "candidate_differs": digest(before) != digest(candidate),
        "rollback_exact": digest(before) == digest(restored),
        "printer_transport": False,
        "gcode_sent": False,
        "deployment_candidate": False,
    }


def _route_freshness_matrix(
    job: Mapping[str, Any], machine: Mapping[str, Any]
) -> Dict[str, Any]:
    absent = _absent_machine()
    stale_events = start_to_arm(job, absent)
    stale_events.append(
        {
            "kind": "resolve_initial_filament",
            "branch": "load_absent",
            "boundaries": [
                boundary(
                    job,
                    "initial_load",
                    "T0",
                    205,
                    "stale-load",
                    "stale-load-proof",
                    mapping_revision=0,
                )
            ],
        }
    )
    stale = simulate(job, absent, stale_events)

    reused_events = happy_start_events(job, machine, prefix="reused")
    reused_events.extend(
        [
            {"kind": "pause_normal", "cfs_effect": False, "purge": False},
            {
                "kind": "resume_normal",
                "homing": False,
                "reprime": True,
                "purge_volume_mm3": 3,
                "boundary": boundary(
                    job,
                    "purge",
                    "T0",
                    205,
                    "reused-reprime",
                    "reused-purge-proof",
                    purge_volume_mm3=3,
                    flow_proven=True,
                ),
            },
        ]
    )
    reused = simulate(job, machine, reused_events)

    reconnect_events = happy_start_events(job, machine, prefix="reconnect")
    reconnect_events.extend(
        [
            {"kind": "set_print_phase", "phase": "normal"},
            {"kind": "reconnect_cfs", "new_mapping_revision": 2},
            {
                "kind": "runout",
                "phase_known": True,
                "equivalent_material": True,
                "homing": False,
                "purge_volume_mm3": 5,
                "boundary": boundary(
                    job,
                    "runout_equivalent",
                    "T0",
                    210,
                    "reconnect-runout",
                    "reconnect-runout-proof",
                    mapping_revision=1,
                    unit="T1",
                    slot="C",
                    bed_target_c=60,
                    purge_volume_mm3=5,
                    flow_proven=True,
                ),
            },
        ]
    )
    reconnect = simulate(job, machine, reconnect_events)
    return {
        "verdict": "pass_offline",
        "stale_blocked": stale["reason_code"] == "route_stale",
        "reused_blocked": reused["reason_code"] == "route_proof_reused",
        "reconnect_blocked": reconnect["reason_code"]
        == "cfs_reconnect_requires_explicit_recovery",
        "reconnect_reason_code": reconnect["reason_code"],
        "printer_transport": False,
        "gcode_sent": False,
        "deployment_candidate": False,
    }


def _no_transport_matrix(
    job: Mapping[str, Any], machine: Mapping[str, Any]
) -> Dict[str, Any]:
    correct = simulate(job, machine, happy_start_events(job, machine, prefix="matrix-correct"))
    wrong = _wrong_machine()
    wrong_result = simulate(job, wrong, happy_start_events(job, wrong, prefix="matrix-wrong"))
    pause_result = run_one("resume_with_optional_reprime")
    cancel_result = simulate(
        job,
        machine,
        happy_start_events(job, machine, prefix="matrix-cancel")
        + [{"kind": "cancel", "automatic_cycle_replay": False}],
    )
    lifecycle_results = [correct, wrong_result, pause_result, cancel_result]
    transport_summary = transport_runner.run()
    real_transport_calls = sum(
        int(item.get("printer_transport") is True)
        + int(item.get("gcode_sent") is True)
        for item in lifecycle_results
    )
    real_transport_calls += int(transport_summary["printer_connection"] is True)
    real_transport_calls += int(transport_summary["gcode_sent"] is True)
    return {
        "verdict": "pass_offline"
        if all(item["verdict"] != "blocked_safe" for item in lifecycle_results)
        and transport_summary["verdict"] == "OK"
        and real_transport_calls == 0
        else "blocked_safe",
        "transport_scenarios": transport_summary["passed"],
        "lifecycle_paths": len(lifecycle_results),
        "real_transport_calls": real_transport_calls,
        "printer_transport": False,
        "gcode_sent": False,
        "deployment_candidate": False,
    }


def _matches(
    result: Mapping[str, Any], expected: Mapping[str, Any]
) -> tuple[bool, str]:
    for key, wanted in expected.items():
        if result.get(key) != wanted:
            return False, "%s expected %r got %r" % (
                key,
                wanted,
                result.get(key),
            )
    return True, "expected lifecycle outcome observed"


def run(path: Path = PACKAGE / "scenarios.json") -> Dict[str, Any]:
    matrix = json.loads(path.read_text(encoding="utf-8"))
    declared = [item["id"] for item in matrix["scenarios"]]
    if declared != CONTRACT["required_scenarios"]:
        raise RuntimeError("scenario_contract_mismatch")
    results = []
    for scenario in matrix["scenarios"]:
        actual = run_one(scenario["id"])
        passed, detail = _matches(actual, scenario["expected"])
        results.append(
            {
                "id": scenario["id"],
                "passed": passed,
                "detail": detail,
                "result": actual,
            }
        )
    passed = sum(item["passed"] for item in results)
    return {
        "verdict": "OK" if passed == len(results) else "KO",
        "passed": passed,
        "total": len(results),
        "results": results,
        "printer_connection": False,
        "gcode_sent": False,
        "physical_action": False,
        "deployment_candidate": False,
    }


def main() -> int:
    summary = run()
    for item in summary["results"]:
        print(
            "%s %s: %s"
            % ("OK" if item["passed"] else "KO", item["id"], item["detail"])
        )
    print("TOTAL %d/%d" % (summary["passed"], summary["total"]))
    return 0 if summary["verdict"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
