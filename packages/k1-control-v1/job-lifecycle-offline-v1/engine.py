#!/usr/bin/env python3
"""Complete deterministic offline state machine for the K1 Control V1 cycle.

The engine records intended effects and validates synthetic evidence. It has no
printer, network, serial, subprocess, filesystem, heater, movement, or G-code
transport. Every hazardous boundary is explicit, timed, single-shot and
fail-closed.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Optional, Sequence

from contract_model import (
    JobContract,
    LifecycleError,
    MachineSnapshot,
    ROUTE_TOKEN,
    SAFE_ID,
    finite,
)


THERMAL_TOLERANCE_C = 0.001
Z_TOLERANCE_MM = 0.000001


def same_number(left: Any, right: Any, tolerance: float) -> bool:
    try:
        return abs(float(left) - float(right)) <= tolerance
    except (TypeError, ValueError):
        return False


class JobLifecycleSimulator:
    """Run one synthetic job lifecycle against immutable contracts."""

    def __init__(
        self,
        lifecycle_contract: Mapping[str, Any],
        job: JobContract,
        machine: MachineSnapshot,
    ):
        self.contract = lifecycle_contract
        self.job = job
        self.machine = machine
        self.phase = "idle"
        self.print_phase = "first_layer"
        self.nozzle_target_c = machine.nozzle_target_c
        self.bed_target_c = machine.bed_target_c
        self.target_owner = "initial_snapshot"
        self.filament_state = machine.filament_state
        self.engaged_tool = machine.engaged_tool
        self.engaged_route = machine.engaged_route
        self.engaged_material = machine.engaged_material
        self.mapping_revision = machine.mapping_revision
        self.homed_axes = machine.homed_axes
        self.mesh_profile = machine.mesh_profile
        self.accepted_z_revision = machine.accepted_z_revision
        self.effective_z_offset_mm = machine.effective_z_offset_mm
        self.final_reference_done = False
        self.low_moves_armed = False
        self.flow_proven = False
        self.pressure_primed = False
        self.resume_armed = False
        self.paused_snapshot: Optional[Dict[str, Any]] = None
        self.pending_transition: Optional[tuple[str, str]] = None
        self.trace: list[Dict[str, Any]] = []
        self.used_route_proofs: set[str] = set()
        self.effect_ids: set[str] = set()
        self.cfs_effects = 0
        self.cut_count = 0
        self.unload_count = 0
        self.load_count = 0
        self.purge_count = 0
        self.persisted_filament_record: Optional[Dict[str, Any]] = None
        self.failure_code: Optional[str] = None
        self.disengage_guard_used = False
        self.printer_transport = False
        self.deployment_candidate = False

    def run(self, events: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        try:
            for event in events:
                self._apply(event)
                if self.phase in {"failed_safe", "cancelled_safe"}:
                    break
        except LifecycleError as error:
            self._safe_stop(error.code)
        return self.result()

    def result(self) -> Dict[str, Any]:
        if self.phase == "failed_safe":
            verdict = "blocked_safe"
        elif self.phase == "cancelled_safe":
            verdict = "cancelled_safe"
        elif self.phase == "closed_safe":
            verdict = "closed_safe"
        else:
            verdict = "pass_offline"
        return {
            "contract_id": self.contract["contract_id"],
            "job_id": self.job.job_id,
            "verdict": verdict,
            "reason_code": self.failure_code,
            "phase": self.phase,
            "print_phase": self.print_phase,
            "filament_state": self.filament_state,
            "engaged_tool": self.engaged_tool,
            "engaged_route": self.engaged_route,
            "engaged_material": self.engaged_material,
            "mapping_revision": self.mapping_revision,
            "nozzle_target_c": self.nozzle_target_c,
            "bed_target_c": self.bed_target_c,
            "target_owner": self.target_owner,
            "mesh_profile": self.mesh_profile,
            "accepted_z_revision": self.accepted_z_revision,
            "effective_z_offset_mm": self.effective_z_offset_mm,
            "homed_axes": self.homed_axes,
            "low_moves_armed": self.low_moves_armed,
            "flow_proven": self.flow_proven,
            "pressure_primed": self.pressure_primed,
            "resume_armed": self.resume_armed,
            "cfs_effects": self.cfs_effects,
            "cut_count": self.cut_count,
            "unload_count": self.unload_count,
            "load_count": self.load_count,
            "purge_count": self.purge_count,
            "effect_ids": sorted(self.effect_ids),
            "route_proofs_used": sorted(self.used_route_proofs),
            "persisted_filament_record": deepcopy(self.persisted_filament_record),
            "disengage_guard_used": self.disengage_guard_used,
            "trace": deepcopy(self.trace),
            "printer_transport": False,
            "gcode_sent": False,
            "physical_action": False,
            "deployment_candidate": False,
        }

    def _apply(self, event: Mapping[str, Any]) -> None:
        if not isinstance(event, Mapping):
            raise LifecycleError("event_invalid")
        kind = str(event.get("kind"))
        handlers = {
            "admit": self._admit,
            "reconcile_filament": self._reconcile_filament,
            "start_bed_heating": self._start_bed_heating,
            "rough_reference": self._rough_reference,
            "clean_nozzle": self._clean_nozzle,
            "reference_temperature_ready": self._reference_temperature_ready,
            "final_reference": self._final_reference,
            "arm_mesh_z": self._arm_mesh_z,
            "resolve_initial_filament": self._resolve_initial_filament,
            "purge": self._purge,
            "prime": self._prime,
            "start_print": self._start_print,
            "set_print_phase": self._set_print_phase,
            "pause_normal": self._pause_normal,
            "adjust_z": self._adjust_z,
            "resume_normal": self._resume_normal,
            "tool_change": self._tool_change,
            "runout": self._runout,
            "end": self._end,
            "cancel": self._cancel,
            "reboot": self._reboot,
            "disengage_and_clean": self._disengage_and_clean,
            "reconnect_cfs": self._reconnect_cfs,
        }
        handler = handlers.get(kind)
        if handler is None:
            raise LifecycleError("event_unknown", kind)
        handler(event)

    def _admit(self, event: Mapping[str, Any]) -> None:
        self._require_phase("idle")
        if self.machine.print_state != "standby":
            raise LifecycleError("printer_not_standby")
        if self.machine.calibration_active:
            raise LifecycleError("calibration_active")
        if self.machine.plate_id != self.job.plate_id:
            raise LifecycleError("plate_mismatch")
        if not self.machine.accepted_z_valid:
            raise LifecycleError("accepted_z_invalid")
        if self.machine.accepted_z_revision != self.job.accepted_z_revision:
            raise LifecycleError("accepted_z_revision_mismatch")
        if not self.machine.sensors_consistent:
            raise LifecycleError("sensor_disagreement")
        if self.filament_state == "engaged_unknown":
            raise LifecycleError("filament_identity_unknown")
        if self.filament_state == "transitioning":
            raise LifecycleError("cfs_transition_active")
        if self.filament_state == "fault":
            raise LifecycleError("filament_state_fault")
        material = self.machine.previous_material_id
        if material is None or material not in self.job.cleaning_recipes:
            if event.get("explicit_cleaning_recipe_confirmation") is not True:
                raise LifecycleError("cleaning_recipe_unknown")
            confirmed = str(event.get("confirmed_previous_material_id"))
            if confirmed not in self.job.cleaning_recipes:
                raise LifecycleError("cleaning_recipe_unknown")
            material = confirmed
        self.previous_material_id = material
        self.phase = "admitted"
        self.trace.append({"kind": "admit", "previous_material_id": material})

    def _reconcile_filament(self, event: Mapping[str, Any]) -> None:
        self._require_phase("admitted")
        if event.get("classification") != self.filament_state:
            raise LifecycleError("filament_classification_mismatch")
        self.phase = "filament_reconciled"
        self.trace.append({"kind": "reconcile_filament", "state": self.filament_state})

    def _start_bed_heating(self, event: Mapping[str, Any]) -> None:
        self._require_phase("filament_reconciled")
        if not same_number(event.get("target_c"), self.job.bed_first_c, THERMAL_TOLERANCE_C):
            raise LifecycleError("bed_target_mismatch")
        self.bed_target_c = self.job.bed_first_c
        self.target_owner = "job_contract"
        self.phase = "bed_heating"
        self.trace.append({"kind": "start_bed_heating", "target_c": self.bed_target_c})

    def _rough_reference(self, event: Mapping[str, Any]) -> None:
        self._require_phase("bed_heating")
        self._timed(event, "rough_reference")
        if event.get("coarse_only") is not True:
            raise LifecycleError("rough_reference_not_coarse")
        if event.get("accepted_z_written") is not False or event.get("mesh_written") is not False:
            raise LifecycleError("rough_reference_mutated_persistent_state")
        if event.get("collision_free") is not True:
            raise LifecycleError("rough_reference_path_unsafe")
        if event.get("homing_performed") is True:
            self.homed_axes = "xyz"
        self.phase = "coarse_reference"
        self.trace.append(
            {"kind": "rough_reference", "homing_performed": event.get("homing_performed") is True}
        )

    def _clean_nozzle(self, event: Mapping[str, Any]) -> None:
        self._require_phase("coarse_reference")
        self._timed(event, "clean_nozzle")
        recipe = self.job.cleaning_recipes[self.previous_material_id]
        if event.get("material_id") != self.previous_material_id:
            raise LifecycleError("cleaning_material_mismatch")
        if not same_number(event.get("target_c"), recipe.nominal_c, THERMAL_TOLERANCE_C):
            raise LifecycleError("cleaning_target_mismatch")
        if finite(event.get("elapsed_s"), "elapsed_s", minimum=0) > recipe.max_hold_s:
            raise LifecycleError("cleaning_hold_timeout")
        required = {
            "brush_plane_source": "versioned_human_calibration",
            "brush_z_probed": False,
            "extrusion": False,
            "filament_change": False,
            "heated_over_waste_chute": True,
            "motion_safe": True,
            "lifted_before_exit": True,
        }
        for field, expected in required.items():
            if event.get(field) != expected:
                raise LifecycleError("cleaning_evidence_invalid:%s" % field)
        self.nozzle_target_c = recipe.probe_c
        self.target_owner = "explicit_cleaning_recipe_then_probe_recipe"
        self.phase = "nozzle_cleaning"
        self.trace.append(
            {
                "kind": "clean_nozzle",
                "cleaning_target_c": recipe.nominal_c,
                "probe_target_c": recipe.probe_c,
                "brush_z_probed": False,
            }
        )

    def _reference_temperature_ready(self, event: Mapping[str, Any]) -> None:
        self._require_phase("nozzle_cleaning")
        recipe = self.job.cleaning_recipes[self.previous_material_id]
        if event.get("stable") is not True:
            raise LifecycleError("reference_temperature_unstable")
        if not same_number(event.get("observed_bed_target_c"), self.job.bed_first_c, THERMAL_TOLERANCE_C):
            raise LifecycleError("bed_target_rewritten")
        if not same_number(event.get("observed_nozzle_target_c"), recipe.probe_c, THERMAL_TOLERANCE_C):
            raise LifecycleError("probe_target_rewritten")
        self.phase = "thermal_reference_ready"
        self.trace.append({"kind": "reference_temperature_ready"})

    def _final_reference(self, event: Mapping[str, Any]) -> None:
        self._require_phase("thermal_reference_ready")
        self._timed(event, "final_reference")
        if event.get("clean_nozzle_confirmed") is not True:
            raise LifecycleError("final_reference_nozzle_not_clean")
        if event.get("precise_reference_count") != 1:
            raise LifecycleError("final_reference_count_invalid")
        if event.get("accepted_z_written") is not False or event.get("mesh_loaded") is not False:
            raise LifecycleError("final_reference_mutated_calibration")
        if event.get("probe_reference_revision") != self.job.mesh_reference_revision:
            raise LifecycleError("probe_reference_revision_mismatch")
        self.homed_axes = "xyz"
        self.final_reference_done = True
        self.phase = "final_reference"
        self.trace.append(
            {"kind": "final_reference", "probe_reference_revision": self.job.mesh_reference_revision}
        )

    def _arm_mesh_z(self, event: Mapping[str, Any]) -> None:
        self._require_phase("final_reference")
        if not self.final_reference_done:
            raise LifecycleError("final_reference_missing")
        if event.get("loaded_after_final_reference") is not True:
            raise LifecycleError("mesh_load_order_invalid")
        if event.get("mesh_profile") != self.job.mesh_profile:
            raise LifecycleError("mesh_profile_mismatch")
        if event.get("mesh_verified") is not True:
            raise LifecycleError("mesh_effect_unproven")
        if event.get("accepted_z_revision") != self.job.accepted_z_revision:
            raise LifecycleError("accepted_z_revision_mismatch")
        if event.get("accepted_z_verified") is not True:
            raise LifecycleError("accepted_z_effect_unproven")
        if event.get("hidden_z_offset_present") is not False:
            raise LifecycleError("hidden_z_offset_detected")
        z_offset = finite(event.get("effective_z_offset_mm"), "effective_z_offset_mm")
        if not same_number(z_offset, self.machine.effective_z_offset_mm, Z_TOLERANCE_MM):
            raise LifecycleError("effective_z_mismatch")
        self.mesh_profile = self.job.mesh_profile
        self.accepted_z_revision = self.job.accepted_z_revision
        self.effective_z_offset_mm = z_offset
        self.low_moves_armed = True
        self.phase = "mesh_z_armed"
        self.trace.append(
            {
                "kind": "arm_mesh_z",
                "mesh_profile": self.mesh_profile,
                "effective_z_offset_mm": self.effective_z_offset_mm,
            }
        )

    def _resolve_initial_filament(self, event: Mapping[str, Any]) -> None:
        self._require_phase("mesh_z_armed")
        branch = str(event.get("branch"))
        initial = self.job.initial_tool
        initial_recipe = self.job.tools[initial]
        boundaries = event.get("boundaries", [])
        if not isinstance(boundaries, Sequence) or isinstance(boundaries, (str, bytes)):
            raise LifecycleError("boundary_list_invalid")
        if self.filament_state == "engaged_known" and self.engaged_tool == initial and self.engaged_material == initial_recipe.material_id:
            if branch != "keep_correct" or boundaries:
                raise LifecycleError("keep_correct_branch_invalid")
            if event.get("cut") is not False or event.get("unload") is not False:
                raise LifecycleError("correct_filament_would_be_removed")
            self.pending_transition = None
        elif self.filament_state == "absent_confirmed":
            if branch != "load_absent" or len(boundaries) != 1:
                raise LifecycleError("load_absent_branch_invalid")
            self._boundary(
                boundaries[0],
                "initial_load",
                initial,
                initial_recipe.nozzle_first_c,
                require_flow=False,
            )
            self.pending_transition = None
        elif self.filament_state == "engaged_known":
            outgoing = self.engaged_tool
            if outgoing is None or outgoing == initial:
                raise LifecycleError("engaged_identity_inconsistent")
            if branch != "change_wrong" or len(boundaries) != 2:
                raise LifecycleError("change_wrong_branch_invalid")
            transition = self.job.transition(outgoing, initial)
            self._boundary(
                boundaries[0],
                "intentional_unload",
                outgoing,
                transition.unload_c,
                require_flow=False,
            )
            self._boundary(
                boundaries[1],
                "intentional_load",
                initial,
                transition.load_c,
                require_flow=False,
            )
            self.pending_transition = (outgoing, initial)
        else:
            raise LifecycleError("filament_state_not_actionable")
        self.nozzle_target_c = initial_recipe.nozzle_first_c
        self.target_owner = "job_contract"
        self.filament_state = "engaged_known"
        self.phase = "filament_ready"
        self.trace.append({"kind": "resolve_initial_filament", "branch": branch})

    def _purge(self, event: Mapping[str, Any]) -> None:
        self._require_phase("filament_ready")
        boundary = event.get("boundary")
        if not isinstance(boundary, Mapping):
            raise LifecycleError("boundary_evidence_missing")
        if self.engaged_tool is None:
            raise LifecycleError("purge_without_tool")
        if self.pending_transition is None:
            target = self.job.tools[self.engaged_tool].nozzle_first_c
            volume = self.job.initial_purge_volumes_mm3[self.engaged_tool]
        else:
            outgoing, incoming = self.pending_transition
            transition = self.job.transition(outgoing, incoming)
            target = transition.purge_c
            volume = transition.purge_volume_mm3
        self._boundary(
            boundary,
            "purge",
            self.engaged_tool,
            target,
            require_flow=True,
            expected_volume=volume,
        )
        self.flow_proven = True
        self.pending_transition = None
        self.phase = "purge_verified"
        self.trace.append({"kind": "purge", "target_c": target, "volume_mm3": volume})

    def _prime(self, event: Mapping[str, Any]) -> None:
        self._require_phase("purge_verified")
        self._timed(event, "prime")
        if not self.low_moves_armed or not self.flow_proven:
            raise LifecycleError("prime_not_armed")
        if event.get("safe_plate_zone") is not True:
            raise LifecycleError("prime_zone_unsafe")
        if event.get("hidden_z_offset_present") is not False:
            raise LifecycleError("hidden_z_offset_detected")
        recipe = self.job.tools[self.engaged_tool]
        if not same_number(event.get("nozzle_target_c"), recipe.nozzle_first_c, THERMAL_TOLERANCE_C):
            raise LifecycleError("prime_nozzle_target_mismatch")
        if not same_number(event.get("bed_target_c"), self.job.bed_first_c, THERMAL_TOLERANCE_C):
            raise LifecycleError("prime_bed_target_mismatch")
        self.nozzle_target_c = recipe.nozzle_first_c
        self.bed_target_c = self.job.bed_first_c
        self.pressure_primed = True
        self.phase = "primed"
        self.trace.append({"kind": "prime"})

    def _start_print(self, event: Mapping[str, Any]) -> None:
        self._require_phase("primed")
        if not (
            self.low_moves_armed
            and self.flow_proven
            and self.pressure_primed
            and self.filament_state == "engaged_known"
            and self.mesh_profile == self.job.mesh_profile
            and self.accepted_z_revision == self.job.accepted_z_revision
        ):
            raise LifecycleError("print_invariants_not_met")
        if event.get("cfs_transition_active") is not False:
            raise LifecycleError("cfs_transition_active")
        self.phase = "printing"
        self.resume_armed = True
        self.trace.append({"kind": "start_print"})

    def _set_print_phase(self, event: Mapping[str, Any]) -> None:
        self._require_phase("printing")
        phase = str(event.get("phase"))
        if phase not in {"first_layer", "normal"}:
            raise LifecycleError("print_phase_unknown")
        self.print_phase = phase
        self.bed_target_c = self.job.bed_target(phase)
        self.nozzle_target_c = self.job.tools[self.engaged_tool].print_target(phase)
        self.target_owner = "job_contract"
        self.trace.append(
            {
                "kind": "set_print_phase",
                "phase": phase,
                "nozzle_target_c": self.nozzle_target_c,
                "bed_target_c": self.bed_target_c,
            }
        )

    def _pause_normal(self, event: Mapping[str, Any]) -> None:
        self._require_phase("printing")
        if event.get("cfs_effect") is not False or event.get("purge") is not False:
            raise LifecycleError("normal_pause_called_cfs")
        self.paused_snapshot = {
            "mesh_profile": self.mesh_profile,
            "accepted_z_revision": self.accepted_z_revision,
            "effective_z_offset_mm": self.effective_z_offset_mm,
            "nozzle_target_c": self.nozzle_target_c,
            "bed_target_c": self.bed_target_c,
            "engaged_tool": self.engaged_tool,
            "engaged_route": self.engaged_route,
            "print_phase": self.print_phase,
            "cfs_effects": self.cfs_effects,
        }
        self.phase = "paused_normal"
        self.trace.append({"kind": "pause_normal", "cfs_effect": False})

    def _adjust_z(self, event: Mapping[str, Any]) -> None:
        self._require_phase("paused_normal")
        if event.get("explicit_operator_action") is not True:
            raise LifecycleError("z_adjust_not_explicit")
        revision = str(event.get("accepted_z_revision"))
        if not SAFE_ID.fullmatch(revision):
            raise LifecycleError("accepted_z_revision_invalid")
        self.effective_z_offset_mm = finite(
            event.get("effective_z_offset_mm"), "effective_z_offset_mm"
        )
        self.accepted_z_revision = revision
        self.trace.append(
            {
                "kind": "adjust_z",
                "effective_z_offset_mm": self.effective_z_offset_mm,
                "accepted_z_revision": revision,
            }
        )

    def _resume_normal(self, event: Mapping[str, Any]) -> None:
        self._require_phase("paused_normal")
        snapshot = self.paused_snapshot
        if snapshot is None:
            raise LifecycleError("pause_snapshot_missing")
        if self.mesh_profile != snapshot["mesh_profile"]:
            raise LifecycleError("resume_mesh_mismatch")
        if self.engaged_tool != snapshot["engaged_tool"] or self.engaged_route != snapshot["engaged_route"]:
            raise LifecycleError("resume_tool_mismatch")
        if event.get("homing") is not False:
            raise LifecycleError("resume_homing_forbidden")
        reprime = event.get("reprime") is True
        boundary = event.get("boundary")
        if reprime:
            if not isinstance(boundary, Mapping):
                raise LifecycleError("reprime_boundary_missing")
            volume = finite(event.get("purge_volume_mm3"), "purge_volume_mm3", minimum=0.001)
            self._boundary(
                boundary,
                "purge",
                self.engaged_tool,
                self.nozzle_target_c,
                require_flow=True,
                expected_volume=volume,
            )
        elif boundary is not None:
            raise LifecycleError("implicit_reprime_forbidden")
        if self.cfs_effects != snapshot["cfs_effects"] + (1 if reprime else 0):
            raise LifecycleError("resume_cfs_effect_count_invalid")
        self.phase = "printing"
        self.paused_snapshot = None
        self.resume_armed = True
        self.trace.append(
            {
                "kind": "resume_normal",
                "reprime": reprime,
                "effective_z_offset_mm": self.effective_z_offset_mm,
                "accepted_z_revision": self.accepted_z_revision,
            }
        )

    def _tool_change(self, event: Mapping[str, Any]) -> None:
        self._require_phase("printing")
        if event.get("path_clear") is not True:
            raise LifecycleError("rear_path_blocked")
        if event.get("homing") is not False:
            raise LifecycleError("tool_change_homing_forbidden")
        incoming = str(event.get("incoming_tool"))
        outgoing = self.engaged_tool
        if outgoing is None or incoming not in self.job.tools or incoming == outgoing:
            raise LifecycleError("tool_change_invalid")
        boundaries = event.get("boundaries")
        if not isinstance(boundaries, Sequence) or isinstance(boundaries, (str, bytes)) or len(boundaries) != 3:
            raise LifecycleError("tool_change_boundaries_invalid")
        before = self._protected()
        transition = self.job.transition(outgoing, incoming)
        self.phase = "tool_changing"
        self._boundary(
            boundaries[0],
            "intentional_unload",
            outgoing,
            transition.unload_c,
            require_flow=False,
        )
        self._boundary(
            boundaries[1],
            "intentional_load",
            incoming,
            transition.load_c,
            require_flow=False,
        )
        self._boundary(
            boundaries[2],
            "purge",
            incoming,
            transition.purge_c,
            require_flow=True,
            expected_volume=transition.purge_volume_mm3,
        )
        incoming_target = self.job.tools[incoming].print_target(self.print_phase)
        if not same_number(event.get("incoming_print_target_c"), incoming_target, THERMAL_TOLERANCE_C):
            raise LifecycleError("incoming_print_target_mismatch")
        self.nozzle_target_c = incoming_target
        self.target_owner = "job_contract"
        self.flow_proven = True
        if self._protected() != before:
            raise LifecycleError("protected_state_changed")
        self.phase = "printing"
        self.trace.append(
            {"kind": "tool_change", "outgoing_tool": outgoing, "incoming_tool": incoming}
        )

    def _runout(self, event: Mapping[str, Any]) -> None:
        self._require_phase("printing")
        if event.get("phase_known") is not True:
            raise LifecycleError("runout_phase_unknown")
        if event.get("equivalent_material") is not True:
            raise LifecycleError("runout_material_not_equivalent")
        if event.get("homing") is not False:
            raise LifecycleError("runout_homing_forbidden")
        boundary = event.get("boundary")
        if not isinstance(boundary, Mapping):
            raise LifecycleError("boundary_evidence_missing")
        active_target = self.nozzle_target_c
        self.phase = "runout_recovery"
        self._boundary(
            boundary,
            "runout_equivalent",
            self.engaged_tool,
            active_target,
            require_flow=True,
            expected_volume=finite(
                event.get("purge_volume_mm3"), "purge_volume_mm3", minimum=0.001
            ),
        )
        self.nozzle_target_c = active_target
        self.target_owner = "preserved_active_target"
        self.flow_proven = True
        self.phase = "printing"
        self.trace.append({"kind": "runout", "equivalent_material": True})

    def _end(self, event: Mapping[str, Any]) -> None:
        self._require_phase("printing")
        if event.get("policy") != "keep_engaged":
            raise LifecycleError("end_policy_mismatch")
        if event.get("cut") is not False or event.get("unload") is not False:
            raise LifecycleError("end_would_remove_correct_filament")
        if event.get("heater_targets_zero_verified") is not True:
            raise LifecycleError("end_heater_shutdown_unproven")
        if event.get("resume_closed") is not True:
            raise LifecycleError("end_resume_still_armed")
        self.persisted_filament_record = {
            "logical_tool": self.engaged_tool,
            "route": self.engaged_route,
            "material_id": self.engaged_material,
            "last_explicit_nozzle_temperature_c": self.nozzle_target_c,
            "mapping_revision": self.mapping_revision,
            "engagement_state": "engaged",
            "flow_proven": self.flow_proven,
            "job_id": self.job.job_id,
        }
        self.nozzle_target_c = 0.0
        self.bed_target_c = 0.0
        self.target_owner = "safe_end"
        self.resume_armed = False
        self.phase = "closed_safe"
        self.trace.append({"kind": "end", "policy": "keep_engaged"})

    def _cancel(self, event: Mapping[str, Any]) -> None:
        if self.phase in {"idle", "closed_safe", "failed_safe", "cancelled_safe"}:
            raise LifecycleError("cancel_phase_invalid")
        if event.get("automatic_cycle_replay") is not False:
            raise LifecycleError("cancel_would_replay_cycle")
        self.nozzle_target_c = 0.0
        self.bed_target_c = 0.0
        self.target_owner = "explicit_cancel"
        self.resume_armed = False
        self.phase = "cancelled_safe"
        self.trace.append({"kind": "cancel", "automatic_cycle_replay": False})

    def _reboot(self, event: Mapping[str, Any]) -> None:
        if self.phase in {"closed_safe", "failed_safe", "cancelled_safe"}:
            raise LifecycleError("reboot_phase_invalid")
        if event.get("automatic_cycle_replay") is not False:
            raise LifecycleError("reboot_would_replay_cycle")
        self.nozzle_target_c = 0.0
        self.bed_target_c = 0.0
        self.target_owner = "reboot_safe_recovery"
        self.resume_armed = False
        self.phase = "failed_safe"
        self.failure_code = "reboot_requires_explicit_recovery"
        self.trace.append({"kind": "reboot", "automatic_cycle_replay": False})

    def _disengage_and_clean(self, event: Mapping[str, Any]) -> None:
        self._require_phase("closed_safe")
        evidence = event.get("guard_result")
        if not isinstance(evidence, Mapping):
            raise LifecycleError("stock_guard_evidence_missing")
        required = {
            "verdict": "OK",
            "stock_count": 1,
            "cleanup_count": 1,
            "route_clear_observed": True,
            "heater_shutdown_verified": True,
        }
        for field, expected in required.items():
            if evidence.get(field) != expected:
                raise LifecycleError("stock_guard_evidence_invalid:%s" % field)
        if event.get("operator_present") is not True:
            raise LifecycleError("disengage_requires_operator")
        if event.get("cleaning_recipe_material_id") != self.engaged_material:
            raise LifecycleError("cleaning_material_mismatch")
        if event.get("cleaning_motion_offline_validated") is not True:
            raise LifecycleError("cleaning_motion_offline_not_validated")
        if event.get("extrusion") is not False:
            raise LifecycleError("cleaning_extrusion_forbidden")
        self.disengage_guard_used = True
        self.engaged_tool = None
        self.engaged_route = None
        self.engaged_material = None
        self.filament_state = (
            "engaged_unknown"
            if evidence.get("toolhead_filament_present_after") is True
            else "absent_confirmed"
        )
        self.nozzle_target_c = 0.0
        self.bed_target_c = 0.0
        self.persisted_filament_record = {
            "logical_tool": None,
            "route": None,
            "material_id": None,
            "engagement_state": "unknown"
            if self.filament_state == "engaged_unknown"
            else "absent",
            "job_id": self.job.job_id,
        }
        self.trace.append(
            {
                "kind": "disengage_and_clean",
                "guard": "stock_unload_guard_transport_offline_v1",
                "filament_state": self.filament_state,
            }
        )

    def _reconnect_cfs(self, event: Mapping[str, Any]) -> None:
        if event.get("new_mapping_revision") != self.mapping_revision + 1:
            raise LifecycleError("mapping_revision_invalid")
        self.mapping_revision += 1
        self.filament_state = "engaged_unknown"
        self.engaged_tool = None
        self.engaged_route = None
        self.engaged_material = None
        self.flow_proven = False
        self.pressure_primed = False
        self.resume_armed = False
        self.trace.append({"kind": "reconnect_cfs", "mapping_revision": self.mapping_revision})
        raise LifecycleError("cfs_reconnect_requires_explicit_recovery")

    def _boundary(
        self,
        evidence: Mapping[str, Any],
        operation: str,
        logical_tool: Optional[str],
        target_c: float,
        *,
        require_flow: bool,
        expected_volume: Optional[float] = None,
    ) -> None:
        if logical_tool is None or logical_tool not in self.job.tools:
            raise LifecycleError("boundary_tool_invalid")
        self._timed(evidence, "cfs_boundary")
        if evidence.get("operation") != operation:
            raise LifecycleError("boundary_operation_mismatch")
        effect_id = str(evidence.get("effect_id"))
        if not SAFE_ID.fullmatch(effect_id):
            raise LifecycleError("effect_id_invalid")
        if effect_id in self.effect_ids:
            raise LifecycleError("duplicate_effect_rejected")
        route = evidence.get("route")
        if not isinstance(route, Mapping):
            raise LifecycleError("route_proof_missing")
        proof_id = str(route.get("proof_id"))
        if not SAFE_ID.fullmatch(proof_id):
            raise LifecycleError("route_proof_invalid")
        if proof_id in self.used_route_proofs:
            raise LifecycleError("route_proof_reused")
        if route.get("mapping_revision") != self.mapping_revision:
            raise LifecycleError("route_stale")
        if route.get("logical_tool") != logical_tool:
            raise LifecycleError("route_tool_mismatch")
        if route.get("cfs_unit") not in self.contract["route_proof"]["allowed_cfs_units"]:
            raise LifecycleError("route_cfs_invalid")
        if route.get("slot") not in self.contract["route_proof"]["allowed_slots"]:
            raise LifecycleError("route_slot_invalid")
        route_token = "%s%s" % (route["cfs_unit"], route["slot"])
        if not ROUTE_TOKEN.fullmatch(route_token):
            raise LifecycleError("route_token_invalid")
        material_id = self.job.tools[logical_tool].material_id
        if route.get("material_id") != material_id:
            raise LifecycleError("route_material_mismatch")
        if evidence.get("target_armed_before_first_effect") is not True:
            raise LifecycleError("target_not_armed_before_effect")
        if not same_number(evidence.get("nozzle_target_before_c"), target_c, THERMAL_TOLERANCE_C):
            raise LifecycleError("phase_temperature_mismatch")
        if not same_number(evidence.get("nozzle_target_during_c"), target_c, THERMAL_TOLERANCE_C):
            raise LifecycleError("late_temperature_rewrite")
        if not same_number(evidence.get("bed_target_during_c"), self.bed_target_c, THERMAL_TOLERANCE_C):
            raise LifecycleError("bed_target_changed")
        forbidden = {
            "cfs_nozzle_command": False,
            "cfs_bed_command": False,
            "geometry_command": False,
            "homing": False,
            "protected_state_unchanged": True,
        }
        for field, expected in forbidden.items():
            if evidence.get(field) != expected:
                raise LifecycleError("boundary_invariant_failed:%s" % field)
        if evidence.get("request_returned") is not True:
            raise LifecycleError("boundary_transport_uncertain")
        if evidence.get("effect_observed") is not True:
            raise LifecycleError("boundary_effect_unproven")
        if require_flow and evidence.get("flow_proven") is not True:
            raise LifecycleError("flow_not_proven")
        if expected_volume is not None and not same_number(
            evidence.get("purge_volume_mm3"), expected_volume, 0.000001
        ):
            raise LifecycleError("purge_volume_mismatch")

        self.effect_ids.add(effect_id)
        self.used_route_proofs.add(proof_id)
        self.cfs_effects += 1
        self.nozzle_target_c = target_c
        self.target_owner = "job_contract"
        if operation == "intentional_unload":
            self.cut_count += 1
            self.unload_count += 1
            self.engaged_tool = None
            self.engaged_route = None
            self.engaged_material = None
            self.filament_state = "absent_confirmed"
        elif operation in {"initial_load", "intentional_load", "runout_equivalent"}:
            self.load_count += 1
            self.engaged_tool = logical_tool
            self.engaged_route = route_token
            self.engaged_material = material_id
            self.filament_state = "engaged_known"
        elif operation == "purge":
            self.purge_count += 1
            self.flow_proven = require_flow
        self.trace.append(
            {
                "kind": "cfs_boundary",
                "operation": operation,
                "effect_id": effect_id,
                "proof_id": proof_id,
                "route": route_token,
                "logical_tool": logical_tool,
                "target_c": target_c,
                "purge_volume_mm3": expected_volume,
            }
        )

    def _timed(self, event: Mapping[str, Any], phase: str) -> None:
        elapsed = finite(event.get("elapsed_s"), "elapsed_s", minimum=0)
        deadline = float(self.contract["phase_deadlines_s"][phase])
        if elapsed > deadline:
            raise LifecycleError("phase_timeout:%s" % phase)
        if event.get("completed") is not True:
            raise LifecycleError("phase_effect_unproven:%s" % phase)

    def _protected(self) -> Dict[str, Any]:
        return {
            "mesh_profile": self.mesh_profile,
            "accepted_z_revision": self.accepted_z_revision,
            "effective_z_offset_mm": self.effective_z_offset_mm,
            "homed_axes": self.homed_axes,
        }

    def _safe_stop(self, code: str) -> None:
        self.failure_code = code
        self.nozzle_target_c = 0.0
        self.bed_target_c = 0.0
        self.target_owner = "safe_stop"
        self.resume_armed = False
        self.low_moves_armed = False
        self.phase = "failed_safe"
        self.trace.append({"kind": "safe_stop", "code": code})

    def _require_phase(self, expected: str) -> None:
        if self.phase != expected:
            raise LifecycleError(
                "phase_order_invalid", "expected %s got %s" % (expected, self.phase)
            )


def simulate_scenario(
    lifecycle_contract: Mapping[str, Any],
    job_payload: Mapping[str, Any],
    machine_payload: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Validate inputs and always return a deterministic safe result."""

    try:
        job = JobContract.from_mapping(job_payload, lifecycle_contract)
        machine = MachineSnapshot.from_mapping(machine_payload)
        simulator = JobLifecycleSimulator(lifecycle_contract, job, machine)
    except LifecycleError as error:
        return {
            "contract_id": lifecycle_contract["contract_id"],
            "job_id": str(job_payload.get("job_id", "invalid")),
            "verdict": "blocked_safe",
            "reason_code": error.code,
            "phase": "failed_safe",
            "nozzle_target_c": 0.0,
            "bed_target_c": 0.0,
            "cfs_effects": 0,
            "cut_count": 0,
            "unload_count": 0,
            "load_count": 0,
            "purge_count": 0,
            "effect_ids": [],
            "route_proofs_used": [],
            "trace": [{"kind": "safe_stop", "code": error.code}],
            "printer_transport": False,
            "gcode_sent": False,
            "physical_action": False,
            "deployment_candidate": False,
        }
    return simulator.run(events)
