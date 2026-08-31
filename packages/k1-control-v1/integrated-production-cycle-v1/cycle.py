#!/usr/bin/env python3
"""Pure fail-closed owner for the integrated daily K1 production cycle.

This module has no network, file, subprocess or printer transport. It validates
ordered evidence and exposes the next required action. The runtime connector is
kept separate so an uncertain physical effect can never be replayed by the
state machine.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
import re
from typing import Any, Dict, Mapping, Optional, Sequence


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
PROFILE = "k1_p001_t055_r001_n11x11"
ROUTE = "T1A"
BED_C = 55.0
PROBE_C = 140.0
TOLERANCE_C = 0.5
TOLERANCE_Z = 0.0005


class CycleError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def number(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise CycleError("%s_invalid" % name)
    if not math.isfinite(result):
        raise CycleError("%s_invalid" % name)
    return result


def close(left: Any, right: float, tolerance: float = TOLERANCE_C) -> bool:
    try:
        return abs(float(left) - right) <= tolerance
    except (TypeError, ValueError):
        return False


@dataclass(frozen=True)
class Job:
    job_id: str
    filename: str
    material_id: str
    nozzle_first_c: float
    nozzle_normal_c: float
    load_c: float
    unload_c: float
    purge_c: float
    purge_mm: float

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Job":
        if value.get("contract_version") != 1:
            raise CycleError("job_contract_version_invalid")
        job_id = str(value.get("job_id", ""))
        filename = str(value.get("filename", ""))
        material_id = str(value.get("material_id", ""))
        for name, item in (("job_id", job_id), ("material_id", material_id)):
            if not SAFE_ID.fullmatch(item):
                raise CycleError("%s_invalid" % name)
        if not filename or ".." in filename or filename.startswith(("/", "\\")):
            raise CycleError("filename_invalid")
        if value.get("route") != ROUTE:
            raise CycleError("route_not_T1A")
        if value.get("mesh_profile") != PROFILE:
            raise CycleError("mesh_profile_invalid")
        if value.get("legacy_z_offset_removed") is not True:
            raise CycleError("legacy_z_offset_present")
        if not close(value.get("bed_first_c"), BED_C, 0.001):
            raise CycleError("bed_first_invalid")
        if not close(value.get("probe_nozzle_c"), PROBE_C, 0.001):
            raise CycleError("probe_temperature_invalid")
        values = {
            key: number(value.get(key), key)
            for key in (
                "nozzle_first_c",
                "nozzle_normal_c",
                "load_c",
                "unload_c",
                "purge_c",
                "purge_mm",
            )
        }
        material_min = number(value.get("material_min_c"), "material_min_c")
        material_max = number(value.get("material_max_c"), "material_max_c")
        if not 150.0 <= material_min <= material_max <= 320.0:
            raise CycleError("material_temperature_bounds_invalid")
        for key in ("nozzle_first_c", "nozzle_normal_c", "load_c", "unload_c", "purge_c"):
            if not material_min <= values[key] <= material_max:
                raise CycleError("%s_out_of_material_bounds" % key)
        if not 0.1 <= values["purge_mm"] <= 40.0:
            raise CycleError("purge_length_invalid")
        return cls(job_id=job_id, filename=filename, material_id=material_id, **values)


class IntegratedCycle:
    def __init__(self, job: Job):
        self.job = job
        self.phase = "idle"
        self.failure_code: Optional[str] = None
        self.route: Optional[str] = None
        self.mesh_profile: Optional[str] = None
        self.accepted_z_mm: Optional[float] = None
        self.targets = {"nozzle": 0.0, "bed": 0.0}
        self.effect_ids: set[str] = set()
        self.purge_count = 0
        self.unload_count = 0
        self.load_count = 0
        self.trace: list[Dict[str, Any]] = []

    def apply(self, event: Mapping[str, Any]) -> Dict[str, Any]:
        if self.phase in {"closed_safe", "failed_safe"}:
            return self.result()
        try:
            kind = str(event.get("kind", ""))
            handler = {
                "prepare": self._prepare,
                "reconcile_before_clean_complete": self._reconcile_before_clean_complete,
                "unload_before_clean_complete": self._unload_before_clean_complete,
                "manual_clean_confirmed": self._manual_clean_confirmed,
                "geometry_complete": self._geometry_complete,
                "t1a_load_complete": self._t1a_load_complete,
                "purge_complete": self._purge_complete,
                "print_started": self._print_started,
                "normal_end_complete": self._normal_end_complete,
                "abort": self._abort,
            }.get(kind)
            if handler is None:
                raise CycleError("event_unknown")
            handler(event)
        except CycleError as error:
            self._fail(error.code)
        return self.result()

    def result(self) -> Dict[str, Any]:
        return {
            "job_id": self.job.job_id,
            "phase": self.phase,
            "failure_code": self.failure_code,
            "route": self.route,
            "mesh_profile": self.mesh_profile,
            "accepted_z_mm": self.accepted_z_mm,
            "targets": deepcopy(self.targets),
            "load_count": self.load_count,
            "unload_count": self.unload_count,
            "purge_count": self.purge_count,
            "effect_ids": sorted(self.effect_ids),
            "next_action": self.next_action(),
            "trace": deepcopy(self.trace),
            "printer_transport": False,
            "physical_action": False,
            "deployment_candidate": False,
        }

    def next_action(self) -> str:
        return {
            "idle": "prepare",
            "reconcile_before_clean": "reengage_declared_T1A_once_before_unload",
            "unload_before_clean": "execute_bounded_cut_and_unload",
            "await_manual_clean": "operator_clean_nozzle_then_confirm",
            "await_geometry": "execute_R4_XY_Z_and_rearm_11x11",
            "await_t1a_load": "execute_bounded_T1A_load",
            "await_purge_proof": "execute_one_origin_edge_purge_and_camera_check",
            "ready_to_print": "start_selected_virtual_SD_job",
            "printing": "model_or_normal_end",
            "ending": "verify_terminal_state",
            "closed_safe": "none",
            "failed_safe": "manual_recovery_only",
        }[self.phase]

    def _prepare(self, event: Mapping[str, Any]) -> None:
        self._require("idle")
        if event.get("printer_state") != "standby":
            raise CycleError("printer_not_standby")
        if event.get("klippy_ready") is not True:
            raise CycleError("klippy_not_ready")
        if not close(event.get("nozzle_target_c"), 0.0, 0.001) or not close(event.get("bed_target_c"), 0.0, 0.001):
            raise CycleError("heaters_not_idle")
        if event.get("cfs_command") not in (None, ""):
            raise CycleError("cfs_command_active")
        routes = event.get("routes")
        if routes not in ([], [ROUTE]):
            raise CycleError("route_state_unsupported")
        head_sensor = event.get("head_sensor")
        after_cutter = event.get("after_cutter_sensor")
        if head_sensor not in (True, False) or after_cutter not in (True, False):
            raise CycleError("filament_sensor_state_missing")
        if routes == [ROUTE] and (head_sensor is not True or after_cutter is not True):
            raise CycleError("engaged_route_sensor_inconsistent")
        self.route = ROUTE if routes == [ROUTE] else None
        if self.route:
            self.phase = "unload_before_clean"
        elif head_sensor is True and after_cutter is True:
            self.phase = "reconcile_before_clean"
        elif head_sensor is False and after_cutter is False:
            self.phase = "await_manual_clean"
        else:
            raise CycleError("residual_filament_state_ambiguous")
        self.trace.append({"kind": "prepare", "route": self.route})

    def _reconcile_before_clean_complete(self, event: Mapping[str, Any]) -> None:
        self._require("reconcile_before_clean")
        self._effect(event, "preclean-T1A-reconcile")
        if event.get("commands") != ["KCTRL_CFS_DIRECT_RECONCILE ROUTE=T1A"]:
            raise CycleError("reconcile_commands_invalid")
        self._direct_cfs_owner(event, "reconcile", "loaded", ROUTE)
        if event.get("route_after") != ROUTE:
            raise CycleError("T1A_reconcile_not_proven")
        if event.get("head_sensor_after") is not True or event.get("after_cutter_sensor_after") is not True:
            raise CycleError("T1A_reconcile_sensor_proof_missing")
        if event.get("automatic_retry") is not False:
            raise CycleError("automatic_retry_forbidden")
        self.route = ROUTE
        self.phase = "unload_before_clean"
        self.trace.append({"kind": "reconcile_before_clean_complete"})

    def _unload_before_clean_complete(self, event: Mapping[str, Any]) -> None:
        self._require("unload_before_clean")
        self._effect(event, "preclean-unload")
        self._temperature_boundary(event, self.job.unload_c)
        if event.get("commands") != ["KCTRL_CFS_DIRECT_UNLOAD ROUTE=T1A"]:
            raise CycleError("unload_commands_invalid")
        self._direct_cfs_owner(event, "unload", "idle", None)
        if (
            event.get("route_after") is not None
            or event.get("head_sensor_after") is not False
            or event.get("after_cutter_sensor_after") is not False
        ):
            raise CycleError("preclean_unload_not_proven")
        if event.get("automatic_retry") is not False:
            raise CycleError("automatic_retry_forbidden")
        self.unload_count += 1
        self.route = None
        self.targets = {"nozzle": 0.0, "bed": 0.0}
        self.phase = "await_manual_clean"
        self.trace.append({"kind": "unload_before_clean_complete"})

    def _manual_clean_confirmed(self, event: Mapping[str, Any]) -> None:
        self._require("await_manual_clean")
        if self.route is not None:
            raise CycleError("clean_confirmation_with_route")
        if event.get("operator_confirmed") is not True or event.get("nozzle_visibly_clean") is not True:
            raise CycleError("manual_clean_missing")
        if event.get("confirmation_fresh") is not True:
            raise CycleError("manual_clean_stale")
        self.phase = "await_geometry"
        self.trace.append({"kind": "manual_clean_confirmed"})

    def _geometry_complete(self, event: Mapping[str, Any]) -> None:
        self._require("await_geometry")
        if self.route is not None:
            raise CycleError("geometry_with_engaged_route")
        if event.get("commands") != ["G28 X Y", "ACCURATE_G28", "KCTRL_PRODUCTION_ARM"]:
            raise CycleError("geometry_order_invalid")
        if event.get("mesh_calibrated") is not False:
            raise CycleError("mesh_calibration_forbidden")
        if event.get("xy_reference_count") != 1 or event.get("precise_z_reference_count") != 1:
            raise CycleError("reference_count_invalid")
        if not close(event.get("bed_c"), BED_C) or not close(event.get("nozzle_c"), PROBE_C):
            raise CycleError("reference_temperature_mismatch")
        if event.get("mesh_profile") != PROFILE or event.get("mesh_verified") is not True:
            raise CycleError("mesh_not_verified")
        accepted_z = number(event.get("accepted_z_mm"), "accepted_z_mm")
        if abs(accepted_z - (-0.04)) > TOLERANCE_Z or event.get("accepted_z_verified") is not True:
            raise CycleError("accepted_z_not_verified")
        if event.get("hidden_z_offset_present") is not False:
            raise CycleError("hidden_z_offset_present")
        self.mesh_profile = PROFILE
        self.accepted_z_mm = accepted_z
        self.targets = {"nozzle": 0.0, "bed": 0.0}
        self.phase = "await_t1a_load"
        self.trace.append({"kind": "geometry_complete", "profile": PROFILE})

    def _t1a_load_complete(self, event: Mapping[str, Any]) -> None:
        self._require("await_t1a_load")
        self._effect(event, "T1A-load")
        self._temperature_boundary(event, self.job.load_c)
        if event.get("commands") != ["KCTRL_CFS_DIRECT_LOAD ROUTE=T1A"]:
            raise CycleError("load_commands_invalid")
        self._direct_cfs_owner(event, "load", "loaded", ROUTE)
        if event.get("route_after") != ROUTE:
            raise CycleError("T1A_load_not_proven")
        if event.get("head_sensor_after") is not True or event.get("after_cutter_sensor_after") is not True:
            raise CycleError("T1A_sensor_proof_missing")
        if event.get("automatic_retry") is not False:
            raise CycleError("automatic_retry_forbidden")
        self.load_count += 1
        self.route = ROUTE
        self.phase = "await_purge_proof"
        self.trace.append({"kind": "t1a_load_complete"})

    def _purge_complete(self, event: Mapping[str, Any]) -> None:
        self._require("await_purge_proof")
        self._effect(event, "single-purge")
        self._temperature_boundary(event, self.job.purge_c)
        if event.get("route") != ROUTE:
            raise CycleError("purge_route_invalid")
        if event.get("zone") != "origin_edge_outside_model":
            raise CycleError("purge_zone_invalid")
        if not close(event.get("purge_mm"), self.job.purge_mm, 0.001):
            raise CycleError("purge_length_mismatch")
        if event.get("flow_visible") is not True or event.get("camera_verdict") != "PASS":
            raise CycleError("purge_not_proven")
        self.purge_count += 1
        if self.purge_count != 1:
            raise CycleError("multiple_purges_forbidden")
        self.targets = {"nozzle": self.job.nozzle_first_c, "bed": BED_C}
        self.phase = "ready_to_print"
        self.trace.append({"kind": "purge_complete", "purge_mm": self.job.purge_mm})

    def _print_started(self, event: Mapping[str, Any]) -> None:
        self._require("ready_to_print")
        if event.get("filename") != self.job.filename or event.get("virtual_sd_state") != "printing":
            raise CycleError("print_start_not_proven")
        if event.get("mesh_profile") != PROFILE or event.get("route") != ROUTE:
            raise CycleError("print_start_context_changed")
        if event.get("hidden_z_offset_present") is not False:
            raise CycleError("hidden_z_offset_present")
        self.phase = "printing"
        self.trace.append({"kind": "print_started", "filename": self.job.filename})

    def _normal_end_complete(self, event: Mapping[str, Any]) -> None:
        self._require("printing")
        self.phase = "ending"
        self._effect(event, "normal-end-unload")
        self._temperature_boundary(event, self.job.unload_c)
        required_order = [
            "safe_lift",
            "lower_bed",
            "set_unload_temperature",
            "KCTRL_CFS_DIRECT_UNLOAD ROUTE=T1A",
            "park_head",
            "TURN_OFF_HEATERS",
            "FANS_ZERO",
            "M84",
        ]
        if event.get("commands") != required_order:
            raise CycleError("normal_end_order_invalid")
        self._direct_cfs_owner(event, "unload", "idle", None)
        if (
            event.get("route_after") is not None
            or event.get("head_sensor_after") is not False
            or event.get("after_cutter_sensor_after") is not False
        ):
            raise CycleError("normal_end_unload_not_proven")
        if event.get("park_verified") is not True or event.get("bed_lowered_verified") is not True:
            raise CycleError("normal_end_park_not_proven")
        if event.get("heater_targets_zero") is not True or event.get("fans_zero") is not True:
            raise CycleError("normal_end_cooling_not_proven")
        if event.get("motors_released") is not True or event.get("automatic_retry") is not False:
            raise CycleError("normal_end_release_invalid")
        self.unload_count += 1
        self.route = None
        self.targets = {"nozzle": 0.0, "bed": 0.0}
        self.phase = "closed_safe"
        self.trace.append({"kind": "normal_end_complete"})

    def _abort(self, event: Mapping[str, Any]) -> None:
        if event.get("automatic_retry") is not False:
            raise CycleError("automatic_retry_forbidden")
        self._fail(str(event.get("reason", "operator_abort")))

    def _temperature_boundary(self, event: Mapping[str, Any], expected: float) -> None:
        if not close(event.get("target_before_c"), expected) or not close(event.get("target_during_c"), expected):
            raise CycleError("phase_temperature_mismatch")
        if event.get("cfs_temperature_command") is not False:
            raise CycleError("CFS_temperature_ownership_detected")
        if close(event.get("target_during_c"), 220.0) and not close(expected, 220.0):
            raise CycleError("hidden_220_rewrite")

    def _effect(self, event: Mapping[str, Any], operation: str) -> None:
        if event.get("operation") != operation:
            raise CycleError("operation_mismatch")
        effect_id = str(event.get("effect_id", ""))
        if not SAFE_ID.fullmatch(effect_id):
            raise CycleError("effect_id_invalid")
        if effect_id in self.effect_ids:
            raise CycleError("duplicate_effect_rejected")
        if event.get("effect_observed") is not True:
            raise CycleError("effect_unproven")
        self.effect_ids.add(effect_id)

    def _direct_cfs_owner(
        self,
        event: Mapping[str, Any],
        operation: str,
        phase: str,
        route: Optional[str],
    ) -> None:
        if event.get("cfs_owner") != "k1_control_direct":
            raise CycleError("direct_CFS_owner_missing")
        if event.get("cfs_owner_operation") != operation:
            raise CycleError("direct_CFS_operation_mismatch")
        if event.get("cfs_owner_phase") != phase:
            raise CycleError("direct_CFS_phase_mismatch")
        if event.get("cfs_owner_route") != route:
            raise CycleError("direct_CFS_route_mismatch")
        if event.get("cfs_owner_failure_code") is not None:
            raise CycleError("direct_CFS_failure_present")
        if event.get("cfs_owner_automatic_retry_count") != 0:
            raise CycleError("direct_CFS_retry_detected")
        for name in (
            "temperature_commands",
            "geometry_commands",
            "mesh_commands",
            "purge_commands",
        ):
            if event.get("cfs_owner_%s" % name) != []:
                raise CycleError("direct_CFS_hidden_%s" % name)

    def _require(self, phase: str) -> None:
        if self.phase != phase:
            raise CycleError("phase_order_invalid")

    def _fail(self, code: str) -> None:
        self.failure_code = code
        self.targets = {"nozzle": 0.0, "bed": 0.0}
        self.phase = "failed_safe"
        self.trace.append({"kind": "failed_safe", "code": code, "automatic_retry": False})


def simulate(job_payload: Mapping[str, Any], events: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    try:
        cycle = IntegratedCycle(Job.from_mapping(job_payload))
    except CycleError as error:
        return {
            "phase": "failed_safe",
            "failure_code": error.code,
            "targets": {"nozzle": 0.0, "bed": 0.0},
            "effect_ids": [],
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
