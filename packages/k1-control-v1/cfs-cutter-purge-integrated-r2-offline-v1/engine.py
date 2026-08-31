#!/usr/bin/env python3
"""Validateur pur du delta appliqué à la séquence stock K1/CFS observée.

Ce module ne contient aucun transport, aucune écriture distante et aucune
commande exécutable sur l'imprimante. Il n'invente pas la chorégraphie : la
source de vérité est ``stock-sequence-delta.json``. Il valide seulement un
contrat ordonné et fermé : toutes les références avant filament, puis les
mouvements stock conservés cutter/retrait et chargement/purge indissociables.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
import re
from typing import Any, Mapping, Optional, Sequence


ROUTE = re.compile(r"^T[12][ABCD]$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
EPS = 0.001
PURGE_POSITION = [185.5, 305.0, 30.0]
PURGE_APPROACH = [203.0, 273.0, 32.0]
CUTTER = {
    "pre_cut_xy_mm": [38.0, 230.0],
    "cut_xy_mm": [38.0, 303.2],
    "cut_pos_offset_mm": 1.3,
    "velocity_mm_min": 7000,
    "run_count": 1,
}
PRIME_POINTS = [
    [0.1, 20.0, 0.3],
    [0.1, 180.0, 0.3],
    [0.4, 180.0, 0.3],
    [0.4, 20.0, 0.3],
    [0.4, 10.0, 0.3],
]
IDENTICAL_MATERIAL_FIELDS = (
    "reference_id",
    "material_type",
    "color",
    "diameter_mm",
    "thermal_recipe_id",
)


class ContractError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def number(value: Any, code: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ContractError(code)
    if not math.isfinite(result):
        raise ContractError(code)
    return result


def same_number(left: Any, right: float, tolerance: float = EPS) -> bool:
    try:
        return abs(float(left) - right) <= tolerance
    except (TypeError, ValueError):
        return False


def same_point(left: Any, right: Sequence[float]) -> bool:
    return (
        isinstance(left, list)
        and len(left) == len(right)
        and all(same_number(a, b) for a, b in zip(left, right))
    )


@dataclass(frozen=True)
class GeometryProfile:
    profile_id: str
    plate_id: str
    bed_first_c: float
    nozzle_first_c: float
    probe_nozzle_c: float
    mesh_profile: str
    accepted_z_mm: float

    @classmethod
    def select(
        cls,
        registry: Sequence[Mapping[str, Any]],
        plate_id: str,
        bed_first_c: float,
        nozzle_first_c: float,
    ) -> "GeometryProfile":
        matches = []
        for item in registry:
            if item.get("status") != "qualified":
                continue
            if item.get("plate_id") != plate_id:
                continue
            if not same_number(item.get("bed_first_c"), bed_first_c):
                continue
            if not same_number(item.get("nozzle_first_c"), nozzle_first_c):
                continue
            matches.append(item)
        if not matches:
            raise ContractError("exact_thermal_geometry_profile_missing")
        if len(matches) != 1:
            raise ContractError("thermal_geometry_profile_ambiguous")
        item = matches[0]
        if item.get("mesh_points") != [11, 11]:
            raise ContractError("mesh_not_11x11")
        profile_id = str(item.get("profile_id", ""))
        mesh_profile = str(item.get("mesh_profile", ""))
        if not SAFE_ID.fullmatch(profile_id) or not SAFE_ID.fullmatch(mesh_profile):
            raise ContractError("geometry_profile_identity_invalid")
        if item.get("accepted_z_status") != "qualified":
            raise ContractError("canonical_z_not_qualified")
        accepted_z = number(item.get("accepted_z_mm"), "canonical_z_invalid")
        probe_nozzle_c = number(item.get("probe_nozzle_c"), "probe_nozzle_c_invalid")
        if not same_number(probe_nozzle_c, 140.0):
            raise ContractError("probe_nozzle_temperature_unqualified")
        return cls(
            profile_id=profile_id,
            plate_id=plate_id,
            bed_first_c=bed_first_c,
            nozzle_first_c=nozzle_first_c,
            probe_nozzle_c=probe_nozzle_c,
            mesh_profile=mesh_profile,
            accepted_z_mm=accepted_z,
        )


@dataclass(frozen=True)
class FilamentRules:
    source: str
    load_c: float
    unload_c: float
    purge_c: float
    purge_mm: float

    @classmethod
    def resolve(
        cls,
        gcode_rules: Optional[Mapping[str, Any]],
        cfs_rules: Optional[Mapping[str, Any]],
    ) -> "FilamentRules":
        required = ("load_c", "unload_c", "purge_c", "purge_mm")
        gcode_rules = dict(gcode_rules or {})
        cfs_rules = dict(cfs_rules or {})
        present = [name for name in required if name in gcode_rules]
        if present:
            if len(present) != len(required):
                raise ContractError("partial_gcode_filament_rules_forbidden")
            source = "gcode"
            chosen = gcode_rules
        else:
            if any(name not in cfs_rules for name in required):
                raise ContractError("complete_cfs_fallback_missing")
            source = "cfs_fallback"
            chosen = cfs_rules
        values = {name: number(chosen[name], "%s_invalid" % name) for name in required}
        for name in ("load_c", "unload_c", "purge_c"):
            if not 150.0 <= values[name] <= 320.0:
                raise ContractError("%s_out_of_range" % name)
        if not 0.1 <= values["purge_mm"] <= 80.0:
            raise ContractError("purge_mm_out_of_range")
        return cls(source=source, **values)


@dataclass(frozen=True)
class JobTicket:
    job_id: str
    filename: str
    initial_route: str
    plate_id: str
    bed_first_c: float
    nozzle_first_c: float
    profile: GeometryProfile
    filament: FilamentRules

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
        registry: Sequence[Mapping[str, Any]],
    ) -> "JobTicket":
        if payload.get("contract_version") != 2:
            raise ContractError("job_contract_version_invalid")
        job_id = str(payload.get("job_id", ""))
        filename = str(payload.get("filename", ""))
        initial_route = str(payload.get("initial_route", ""))
        plate_id = str(payload.get("plate_id", ""))
        if not SAFE_ID.fullmatch(job_id) or not SAFE_ID.fullmatch(plate_id):
            raise ContractError("job_identity_invalid")
        if not filename or ".." in filename or filename.startswith(("/", "\\")):
            raise ContractError("filename_invalid")
        if not ROUTE.fullmatch(initial_route):
            raise ContractError("initial_route_invalid")
        gcode = payload.get("gcode")
        if not isinstance(gcode, Mapping):
            raise ContractError("gcode_ticket_missing")
        bed_first_c = number(gcode.get("bed_first_c"), "bed_first_c_invalid")
        nozzle_first_c = number(gcode.get("nozzle_first_c"), "nozzle_first_c_invalid")
        if not 0.0 < bed_first_c <= 130.0 or not 150.0 <= nozzle_first_c <= 320.0:
            raise ContractError("print_temperature_out_of_range")
        profile = GeometryProfile.select(registry, plate_id, bed_first_c, nozzle_first_c)
        filament = FilamentRules.resolve(gcode.get("filament_rules"), payload.get("cfs_fallback"))
        return cls(
            job_id=job_id,
            filename=filename,
            initial_route=initial_route,
            plate_id=plate_id,
            bed_first_c=bed_first_c,
            nozzle_first_c=nozzle_first_c,
            profile=profile,
            filament=filament,
        )


class IntegratedCycleR2:
    def __init__(self, job: JobTicket):
        self.job = job
        self.phase = "idle"
        self.failure_code: Optional[str] = None
        self.route: Optional[str] = None
        self.filament_loaded = False
        self.loaded_once = False
        self.geometry_applied = False
        self.effect_ids: set[str] = set()
        self.tool_changes = 0
        self.equivalent_refills = 0
        self.trace: list[dict[str, Any]] = []

    def result(self) -> dict[str, Any]:
        return {
            "job_id": self.job.job_id,
            "phase": self.phase,
            "failure_code": self.failure_code,
            "route": self.route,
            "filament_loaded": self.filament_loaded,
            "geometry_profile": self.job.profile.profile_id,
            "mesh_profile": self.job.profile.mesh_profile,
            "accepted_z_mm": self.job.profile.accepted_z_mm,
            "filament_rule_source": self.job.filament.source,
            "tool_changes": self.tool_changes,
            "equivalent_refills": self.equivalent_refills,
            "effect_ids": sorted(self.effect_ids),
            "trace": deepcopy(self.trace),
            "printer_transport": False,
            "physical_action": False,
            "deployment_candidate": False,
        }

    def apply(self, event: Mapping[str, Any]) -> dict[str, Any]:
        if self.phase in {"closed_safe", "failed_safe"}:
            return self.result()
        try:
            kind = str(event.get("kind", ""))
            handler = {
                "prepare": self._prepare,
                "clean_nozzle_confirmed": self._clean,
                "references_complete": self._references,
                "geometry_applied": self._geometry,
                "heat_complete": self._heat,
                "load_complete": self._load,
                "bin_purge_release_complete": self._bin_purge,
                "prime_line_complete": self._prime,
                "print_started": self._print_started,
                "tool_change_complete": self._tool_change,
                "equivalent_refill_complete": self._equivalent_refill,
                "print_completed": self._print_completed,
                "end_unload_complete": self._end,
                "abort": self._abort,
            }.get(kind)
            if handler is None:
                raise ContractError("event_unknown")
            handler(event)
        except ContractError as error:
            self._fail(error.code)
        return self.result()

    def _prepare(self, event: Mapping[str, Any]) -> None:
        self._require("idle")
        if event.get("printer_state") != "standby" or event.get("klippy_ready") is not True:
            raise ContractError("printer_not_ready")
        if event.get("routes") != []:
            raise ContractError("filament_route_present_before_references")
        if event.get("head_sensor") is not False or event.get("after_cutter_sensor") is not False:
            raise ContractError("filament_present_before_references")
        if not same_number(event.get("bed_target_c"), 0.0) or not same_number(event.get("nozzle_target_c"), 0.0):
            raise ContractError("heater_target_active_at_prepare")
        self.phase = "await_clean_confirmation"
        self.trace.append({"kind": "prepare", "no_filament": True})

    def _clean(self, event: Mapping[str, Any]) -> None:
        self._require("await_clean_confirmation")
        if event.get("manual_clean") is not True or event.get("fresh") is not True:
            raise ContractError("fresh_manual_clean_missing")
        if event.get("filament_loaded") is not False:
            raise ContractError("clean_confirmation_with_filament")
        self.phase = "await_references"
        self.trace.append({"kind": "clean_nozzle_confirmed"})

    def _references(self, event: Mapping[str, Any]) -> None:
        self._require("await_references")
        if event.get("filament_loaded") is not False or event.get("routes") != []:
            raise ContractError("references_with_filament_forbidden")
        if event.get("reference_axes") != ["X", "Y", "Z"]:
            raise ContractError("XYZ_references_incomplete")
        if event.get("mesh_calibrated") is not False:
            raise ContractError("daily_mesh_recalculation_forbidden")
        if event.get("contact_after_clean") is not True:
            raise ContractError("reference_cleanliness_not_proven")
        if not same_number(event.get("probe_nozzle_c"), self.job.profile.probe_nozzle_c):
            raise ContractError("reference_probe_temperature_mismatch")
        self.phase = "await_geometry_apply"
        self.trace.append({"kind": "references_complete", "before_filament": True})

    def _geometry(self, event: Mapping[str, Any]) -> None:
        self._require("await_geometry_apply")
        if event.get("profile_id") != self.job.profile.profile_id:
            raise ContractError("thermal_geometry_profile_changed")
        if event.get("mesh_profile") != self.job.profile.mesh_profile:
            raise ContractError("mesh_profile_changed")
        if event.get("mesh_points") != [11, 11]:
            raise ContractError("mesh_not_11x11")
        if not same_number(event.get("accepted_z_mm"), self.job.profile.accepted_z_mm):
            raise ContractError("canonical_z_changed")
        if event.get("actions") != ["load_exact_11x11_profile", "apply_exact_canonical_z"]:
            raise ContractError("geometry_apply_order_invalid")
        self._no_contact(event)
        self.geometry_applied = True
        self.phase = "await_heat"
        self.trace.append({"kind": "geometry_applied", "exact_thermal_match": True})

    def _heat(self, event: Mapping[str, Any]) -> None:
        self._require("await_heat")
        if not same_number(event.get("bed_target_c"), self.job.bed_first_c):
            raise ContractError("bed_temperature_mismatch")
        if not same_number(event.get("nozzle_target_c"), self.job.nozzle_first_c):
            raise ContractError("nozzle_temperature_mismatch")
        if event.get("targets_reached") is not True:
            raise ContractError("temperatures_not_reached")
        self._no_contact(event)
        self.phase = "await_load_at_purge"
        self.trace.append({"kind": "heat_complete"})

    def _load(self, event: Mapping[str, Any]) -> None:
        self._require("await_load_at_purge")
        self._effect(event, "initial-load")
        self._forbid_stock(event)
        self._no_contact(event)
        if event.get("route") != self.job.initial_route:
            raise ContractError("initial_route_changed")
        if not same_point(event.get("head_xyz_mm"), PURGE_POSITION):
            raise ContractError("load_not_at_purge_position")
        if event.get("bed_lowered_for_load") is not True:
            raise ContractError("bed_not_lowered_for_load")
        if event.get("direct_owner") is not True or event.get("automatic_retry") is not False:
            raise ContractError("direct_load_owner_invalid")
        if event.get("filament_rule_source") != self.job.filament.source:
            raise ContractError("filament_rule_precedence_changed")
        if not same_number(event.get("load_c"), self.job.filament.load_c):
            raise ContractError("load_temperature_mismatch")
        if event.get("head_sensor_after") is not True or event.get("after_cutter_sensor_after") is not True:
            raise ContractError("load_sensor_proof_missing")
        self.route = self.job.initial_route
        self.filament_loaded = True
        self.loaded_once = True
        self.phase = "await_bin_purge_release"
        self.trace.append({"kind": "load_complete", "route": self.route})

    def _bin_purge(self, event: Mapping[str, Any]) -> None:
        self._require("await_bin_purge_release")
        self._effect(event, "initial-bin-purge")
        self._validate_bin_purge(event, self.route)
        self.phase = "await_prime_line"
        self.trace.append({"kind": "bin_purge_release_complete"})

    def _prime(self, event: Mapping[str, Any]) -> None:
        self._require("await_prime_line")
        self._effect(event, "prime-line")
        self._no_contact(event)
        if event.get("path_xyz_mm") != PRIME_POINTS:
            raise ContractError("prime_line_geometry_unqualified")
        if event.get("extrusion_mm") != [0.0, 10.0, 0.0, 10.0, 0.0]:
            raise ContractError("prime_line_extrusion_invalid")
        if event.get("feedrate_mm_min") != [6000, 3000, 3000, 3000, 3000]:
            raise ContractError("prime_line_feedrate_invalid")
        if not same_number(event.get("bed_lower_relative_mm"), 5.0):
            raise ContractError("post_prime_bed_lower_5mm_missing")
        if event.get("relative_z_direction") != "positive_toolhead_Z_lowers_bed":
            raise ContractError("post_prime_Z_direction_ambiguous")
        self.phase = "ready_to_print"
        self.trace.append({"kind": "prime_line_complete", "stock_geometry": True})

    def _print_started(self, event: Mapping[str, Any]) -> None:
        self._require("ready_to_print")
        self._no_contact(event)
        if event.get("filename") != self.job.filename or event.get("virtual_sd_state") != "printing":
            raise ContractError("print_start_not_proven")
        if event.get("mesh_profile") != self.job.profile.mesh_profile:
            raise ContractError("mesh_changed_at_print_start")
        if not same_number(event.get("accepted_z_mm"), self.job.profile.accepted_z_mm):
            raise ContractError("canonical_z_changed_at_print_start")
        self.phase = "printing"
        self.trace.append({"kind": "print_started"})

    def _tool_change(self, event: Mapping[str, Any]) -> None:
        self._require("printing")
        self._effect(event, "tool-change")
        self._no_contact(event)
        self._forbid_stock(event)
        if event.get("from_route") != self.route:
            raise ContractError("tool_change_source_route_invalid")
        target = str(event.get("to_route", ""))
        if not ROUTE.fullmatch(target) or target == self.route:
            raise ContractError("tool_change_target_route_invalid")
        self._validate_cutter(event.get("cutter"))
        if event.get("direct_unload") is not True or event.get("direct_load") is not True:
            raise ContractError("tool_change_direct_owner_incomplete")
        if event.get("atomic_no_resume_between_steps") is not True:
            raise ContractError("tool_change_not_atomic")
        self._validate_bin_purge(event.get("purge", {}), target)
        if event.get("head_sensor_after") is not True or event.get("after_cutter_sensor_after") is not True:
            raise ContractError("tool_change_sensor_proof_missing")
        self.route = target
        self.tool_changes += 1
        self.trace.append({"kind": "tool_change_complete", "route": target})

    def _equivalent_refill(self, event: Mapping[str, Any]) -> None:
        self._require("printing")
        self._effect(event, "equivalent-refill")
        self._no_contact(event)
        self._forbid_stock(event)
        if event.get("runout_detected") is not True or event.get("pause_latched") is not True:
            raise ContractError("equivalent_refill_runout_not_latched")
        if event.get("stock_auto_refill_disabled") is not True:
            raise ContractError("stock_auto_refill_owner_conflict")
        if event.get("from_route") != self.route:
            raise ContractError("equivalent_refill_source_route_invalid")
        target = str(event.get("to_route", ""))
        if not ROUTE.fullmatch(target) or target == self.route:
            raise ContractError("equivalent_refill_target_route_invalid")
        if event.get("available_equivalent_routes") != [target]:
            raise ContractError("equivalent_refill_candidate_not_unique")
        exhausted = event.get("exhausted_material")
        replacement = event.get("replacement_material")
        if not isinstance(exhausted, Mapping) or not isinstance(replacement, Mapping):
            raise ContractError("equivalent_refill_material_identity_missing")
        if exhausted.get("user_approved") is not True or replacement.get("user_approved") is not True:
            raise ContractError("equivalent_refill_material_identity_unapproved")
        if any(exhausted.get(field) != replacement.get(field) for field in IDENTICAL_MATERIAL_FIELDS):
            raise ContractError("equivalent_refill_material_not_identical")
        if event.get("firmware_equivalence_group_configured") is not True:
            raise ContractError("equivalent_refill_group_not_configured")
        if event.get("tail_state_resolved") is not True:
            raise ContractError("equivalent_refill_tail_unresolved")
        if not same_number(event.get("active_nozzle_target_c"), event.get("resume_nozzle_target_c")):
            raise ContractError("equivalent_refill_temperature_changed")
        self._validate_cutter(event.get("cutter"))
        if event.get("direct_unload") is not True or event.get("direct_load") is not True:
            raise ContractError("equivalent_refill_direct_owner_incomplete")
        if event.get("atomic_no_resume_between_steps") is not True:
            raise ContractError("equivalent_refill_not_atomic")
        self._validate_bin_purge(event.get("purge", {}), target)
        if event.get("head_sensor_after") is not True or event.get("after_cutter_sensor_after") is not True:
            raise ContractError("equivalent_refill_sensor_proof_missing")
        if event.get("resume_context_preserved") is not True or event.get("pause_still_latched_before_resume") is not True:
            raise ContractError("equivalent_refill_resume_context_invalid")
        self.route = target
        self.equivalent_refills += 1
        self.trace.append({"kind": "equivalent_refill_complete", "route": target})

    def _print_completed(self, event: Mapping[str, Any]) -> None:
        self._require("printing")
        self._no_contact(event)
        if event.get("virtual_sd_state") != "complete":
            raise ContractError("print_completion_not_proven")
        self.phase = "await_end_unload"
        self.trace.append({"kind": "print_completed"})

    def _end(self, event: Mapping[str, Any]) -> None:
        self._require("await_end_unload")
        self._effect(event, "end-unload")
        self._no_contact(event)
        self._forbid_stock(event)
        if event.get("g28_count") != 0:
            raise ContractError("end_full_homing_forbidden")
        if event.get("actions") != [
            "safe_lift_and_lower_bed",
            "move_to_cutter",
            "cut_filament",
            "direct_cfs_unload",
            "safe_park",
            "turn_off_heaters_and_fans",
            "release_motors",
        ]:
            raise ContractError("end_order_invalid")
        self._validate_cutter(event.get("cutter"))
        if event.get("route_before") != self.route or event.get("direct_unload") is not True:
            raise ContractError("end_unload_route_invalid")
        if event.get("head_sensor_after") is not False or event.get("after_cutter_sensor_after") is not False:
            raise ContractError("end_unload_sensor_proof_missing")
        if event.get("safe_park_verified") is not True:
            raise ContractError("safe_park_not_proven")
        if event.get("heater_targets_zero") is not True or event.get("fans_zero") is not True:
            raise ContractError("terminal_cooling_not_proven")
        if event.get("motors_released") is not True or event.get("automatic_retry") is not False:
            raise ContractError("terminal_release_invalid")
        self.route = None
        self.filament_loaded = False
        self.phase = "closed_safe"
        self.trace.append({"kind": "end_unload_complete"})

    def _validate_cutter(self, value: Any) -> None:
        if not isinstance(value, Mapping):
            raise ContractError("cutter_proof_missing")
        for name, expected in CUTTER.items():
            actual = value.get(name)
            if isinstance(expected, list):
                if not same_point(actual, expected):
                    raise ContractError("cutter_geometry_changed")
            elif not same_number(actual, expected):
                raise ContractError("cutter_geometry_changed")
        if value.get("cutter_choreography_qualified") is not True or value.get("cut_observed") is not True:
            raise ContractError("cutter_effect_not_proven")

    def _validate_bin_purge(self, event: Mapping[str, Any], route: Optional[str]) -> None:
        self._no_contact(event)
        self._forbid_stock(event)
        if event.get("route") != route or route is None:
            raise ContractError("purge_route_invalid")
        if not same_point(event.get("purge_xyz_mm"), PURGE_POSITION):
            raise ContractError("purge_not_in_bin")
        if not same_point(event.get("safe_approach_xyz_mm"), PURGE_APPROACH):
            raise ContractError("purge_safe_approach_changed")
        if not same_number(event.get("purge_c"), self.job.filament.purge_c):
            raise ContractError("purge_temperature_mismatch")
        if not same_number(event.get("purge_mm"), self.job.filament.purge_mm):
            raise ContractError("purge_length_mismatch")
        count = event.get("release_round_trips")
        if count not in (3, 4):
            raise ContractError("release_requires_3_or_4_round_trips")
        lanes = event.get("release_lanes_y_mm")
        expected_lanes = [305.0 if index % 2 == 0 else 304.0 for index in range(count)]
        if lanes != expected_lanes:
            raise ContractError("release_lane_sequence_invalid")
        if event.get("release_x_mm") != [203.0, 206.0, 203.0]:
            raise ContractError("release_x_path_invalid")
        if not same_number(event.get("release_z_mm"), 32.0):
            raise ContractError("release_z_invalid")
        if not same_number(event.get("release_feedrate_mm_min"), 180.0):
            raise ContractError("release_feedrate_unqualified")
        if event.get("continuous_round_trips") is not True:
            raise ContractError("release_motion_not_frank")
        if event.get("camera_verdict") != "PASS" or event.get("purge_ball_dropped") is not True:
            raise ContractError("purge_release_not_visually_proven")

    def _no_contact(self, event: Mapping[str, Any]) -> None:
        if event.get("probe_count", 0) != 0 or event.get("mesh_recalculated", False) is not False:
            if self.loaded_once or self.filament_loaded:
                raise ContractError("contact_after_filament_forbidden")
            raise ContractError("unexpected_contact_or_mesh_recalculation")

    def _forbid_stock(self, event: Mapping[str, Any]) -> None:
        commands = event.get("commands", [])
        if not isinstance(commands, list):
            raise ContractError("commands_invalid")
        if any(str(command).strip().upper().startswith("BOX_") for command in commands):
            raise ContractError("stock_BOX_effect_forbidden")

    def _effect(self, event: Mapping[str, Any], operation: str) -> None:
        if event.get("operation") != operation:
            raise ContractError("operation_mismatch")
        effect_id = str(event.get("effect_id", ""))
        if not SAFE_ID.fullmatch(effect_id):
            raise ContractError("effect_id_invalid")
        if effect_id in self.effect_ids:
            raise ContractError("duplicate_effect_rejected")
        if event.get("effect_observed") is not True:
            raise ContractError("effect_not_proven")
        self.effect_ids.add(effect_id)

    def _abort(self, event: Mapping[str, Any]) -> None:
        if event.get("automatic_retry") is not False:
            raise ContractError("automatic_retry_forbidden")
        self._fail(str(event.get("reason", "operator_abort")))

    def _require(self, phase: str) -> None:
        if self.phase != phase:
            raise ContractError("phase_order_invalid")

    def _fail(self, code: str) -> None:
        self.failure_code = code
        self.phase = "failed_safe"
        self.trace.append({"kind": "failed_safe", "code": code, "automatic_retry": False})


def simulate(
    job_payload: Mapping[str, Any],
    registry: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    try:
        cycle = IntegratedCycleR2(JobTicket.from_mapping(job_payload, registry))
    except ContractError as error:
        return {
            "phase": "failed_safe",
            "failure_code": error.code,
            "printer_transport": False,
            "physical_action": False,
            "deployment_candidate": False,
        }
    result = cycle.result()
    for event in events:
        result = cycle.apply(event)
        if result["phase"] in {"closed_safe", "failed_safe"}:
            break
    return result
