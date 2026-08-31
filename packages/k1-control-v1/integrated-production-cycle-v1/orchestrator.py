#!/usr/bin/env python3
"""Async orchestration seam for the integrated K1 production cycle.

The class is transport-agnostic. A future Moonraker component supplies the
backend, while offline tests use a deterministic fake. Effects are disabled by
default and must never be enabled before the four BOX primitives are physically
qualified on the target K1.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any, Dict, Mapping, Optional

try:
    from .k1_control_cycle_core import IntegratedCycle, Job
except ImportError:  # Offline package execution and unit tests.
    from cycle import IntegratedCycle, Job


PROFILE = "k1_p001_t055_r001_n11x11"


class OrchestrationError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class CycleOrchestrator:
    def __init__(self, backend: Any, *, effects_enabled: bool = False, poll_s: float = 0.05):
        self.backend = backend
        self.effects_enabled = effects_enabled
        self.poll_s = poll_s
        self.cycle: Optional[IntegratedCycle] = None
        self.job: Optional[Job] = None
        self.busy = False
        self.last_error: Optional[str] = None

    async def public_state(self) -> Dict[str, Any]:
        snapshot = await self.backend.query_status()
        if self.cycle is None:
            return {
                "phase": snapshot.get("cycle_phase", "idle"),
                "job": await self.backend.selected_job(),
                "route": self._single_route(snapshot),
                "mesh_profile": snapshot.get("mesh_profile"),
                "busy": self.busy,
                "last_error": self.last_error,
                "effects_enabled": self.effects_enabled,
            }
        result = self.cycle.result()
        result.update({
            "job": self._job_public(),
            "busy": self.busy,
            "last_error": self.last_error,
            "effects_enabled": self.effects_enabled,
        })
        return result

    async def prepare(self, job_payload: Mapping[str, Any]) -> Dict[str, Any]:
        if self.busy:
            raise OrchestrationError("cycle_busy")
        self.job = Job.from_mapping(job_payload)
        self.cycle = IntegratedCycle(self.job)
        self.busy = True
        self.last_error = None
        try:
            snapshot = await self.backend.query_status()
            result = self.cycle.apply({
                "kind": "prepare",
                "printer_state": snapshot.get("printer_state"),
                "klippy_ready": snapshot.get("klippy_ready"),
                "nozzle_target_c": snapshot.get("nozzle_target_c"),
                "bed_target_c": snapshot.get("bed_target_c"),
                "cfs_command": snapshot.get("cfs_command"),
                "routes": snapshot.get("routes"),
                "head_sensor": snapshot.get("head_sensor"),
                "after_cutter_sensor": snapshot.get("after_cutter_sensor"),
            })
            self._raise_if_failed(result)
            self._require_effects()
            await self.backend.run_gcode(
                "KCTRL_CYCLE_PREPARE_V1 "
                "UNLOAD_NOZZLE={0.unload_c} LOAD_NOZZLE={0.load_c} "
                "FIRST_NOZZLE={0.nozzle_first_c} PURGE_NOZZLE={0.purge_c} "
                "PURGE_MM={0.purge_mm} JOB={0.job_id}".format(self.job)
            )
            await self._wait_phase(result["phase"], 10)
            if result["phase"] == "reconcile_before_clean":
                await self.backend.run_gcode("KCTRL_CYCLE_RECONCILE_SLOT_A_BEFORE_CLEAN_V1")
                observed = await self._wait_phase("unload_before_clean", 300)
                result = self.cycle.apply(self._reconcile_event(observed, "reconcile-1"))
                self._raise_if_failed(result)
            if result["phase"] == "unload_before_clean":
                await self.backend.run_gcode("KCTRL_CYCLE_UNLOAD_BEFORE_CLEAN_V1")
                observed = await self._wait_phase("await_manual_clean", 300)
                result = self.cycle.apply(self._unload_event(observed, "preclean-1"))
                self._raise_if_failed(result)
            return await self.public_state()
        except Exception as error:
            await self._safe_fail(error)
            raise
        finally:
            self.busy = False

    async def confirm_clean_and_start(self) -> Dict[str, Any]:
        if self.busy:
            raise OrchestrationError("cycle_busy")
        if self.cycle is None or self.job is None:
            raise OrchestrationError("cycle_not_prepared")
        self._require_effects()
        self.busy = True
        try:
            result = self.cycle.apply({
                "kind": "manual_clean_confirmed",
                "operator_confirmed": True,
                "nozzle_visibly_clean": True,
                "confirmation_fresh": True,
            })
            self._raise_if_failed(result)
            await self.backend.run_gcode("KCTRL_CYCLE_CONFIRM_CLEAN_AND_REFERENCE_V1")
            geometry = await self._wait_phase("await_t1a_load", 900)
            result = self.cycle.apply({
                "kind": "geometry_complete",
                "commands": ["G28 X Y", "ACCURATE_G28", "KCTRL_PRODUCTION_ARM"],
                "mesh_calibrated": False,
                "xy_reference_count": 1,
                "precise_z_reference_count": 1,
                "bed_c": geometry.get("bed_temperature_c"),
                "nozzle_c": geometry.get("reference_nozzle_temperature_c"),
                "mesh_profile": geometry.get("mesh_profile"),
                "mesh_verified": geometry.get("mesh_profile") == PROFILE,
                "accepted_z_mm": geometry.get("accepted_z_mm"),
                "accepted_z_verified": geometry.get("accepted_z_valid") is True,
                "hidden_z_offset_present": geometry.get("hidden_z_offset_present"),
            })
            self._raise_if_failed(result)

            await self.backend.run_gcode("KCTRL_CYCLE_LOAD_SLOT_A_V1")
            loaded = await self._wait_phase("await_purge_proof", 300)
            result = self.cycle.apply({
                "kind": "t1a_load_complete",
                "operation": "T1A-load",
                "effect_id": "load-1",
                "effect_observed": loaded.get("routes") == ["T1A"],
                "target_before_c": self.job.load_c,
                "target_during_c": loaded.get("last_cfs_effect_target_c"),
                "cfs_temperature_command": loaded.get("cfs_temperature_command"),
                "commands": ["BOX_EXTRUDE_MATERIAL TNN=T1A", "BOX_EXTRUDER_EXTRUDE TNN=T1A"],
                "route_after": self._single_route(loaded),
                "head_sensor_after": loaded.get("head_sensor"),
                "after_cutter_sensor_after": loaded.get("after_cutter_sensor"),
                "automatic_retry": False,
            })
            self._raise_if_failed(result)

            await self.backend.run_gcode("KCTRL_CYCLE_SINGLE_PURGE_V1")
            purged = await self._wait_phase("camera_purge_check", 300)
            camera = await self.backend.camera_verdict("ORIGIN_EDGE_PURGE")
            result = self.cycle.apply({
                "kind": "purge_complete",
                "operation": "single-purge",
                "effect_id": "purge-1",
                "effect_observed": purged.get("purge_effect_observed") is True,
                "target_before_c": self.job.purge_c,
                "target_during_c": purged.get("last_cfs_effect_target_c"),
                "cfs_temperature_command": False,
                "commands": [],
                "route": self._single_route(purged),
                "zone": "origin_edge_outside_model",
                "purge_mm": self.job.purge_mm,
                "flow_visible": camera == "PASS",
                "camera_verdict": camera,
            })
            self._raise_if_failed(result)
            await self.backend.run_gcode("KCTRL_CYCLE_CONFIRM_PURGE_CAMERA_V1")
            await self._wait_phase("ready_to_print", 180)
            await self.backend.start_print(self.job.filename)
            printing = await self._wait_printer_state("printing", 30)
            result = self.cycle.apply({
                "kind": "print_started",
                "filename": self.job.filename,
                "virtual_sd_state": printing.get("printer_state"),
                "mesh_profile": printing.get("mesh_profile"),
                "route": self._single_route(printing),
                "hidden_z_offset_present": printing.get("hidden_z_offset_present"),
            })
            self._raise_if_failed(result)
            return await self.public_state()
        except Exception as error:
            await self._safe_fail(error)
            raise
        finally:
            self.busy = False

    async def observe_normal_end(self, timeout_s: float = 604800.0) -> Dict[str, Any]:
        if self.cycle is None or self.job is None:
            raise OrchestrationError("cycle_not_prepared")
        terminal = await self._wait_phase("closed_safe", timeout_s)
        result = self.cycle.apply({
            "kind": "normal_end_complete",
            "operation": "normal-end-unload",
            "effect_id": "end-unload-1",
            "effect_observed": terminal.get("routes") == [],
            "target_before_c": self.job.unload_c,
            "target_during_c": terminal.get("last_cfs_effect_target_c"),
            "cfs_temperature_command": terminal.get("cfs_temperature_command"),
            "commands": [
                "safe_lift", "lower_bed", "set_unload_temperature",
                "BOX_CUT_MATERIAL", "local_tip_retract", "BOX_RETRUDE_MATERIAL", "park_head",
                "TURN_OFF_HEATERS", "FANS_ZERO", "M84",
            ],
            "route_after": self._single_route(terminal),
            "after_cutter_sensor_after": terminal.get("after_cutter_sensor"),
            "park_verified": terminal.get("park_verified"),
            "bed_lowered_verified": terminal.get("bed_lowered_verified"),
            "heater_targets_zero": terminal.get("heater_targets_zero"),
            "fans_zero": terminal.get("fans_zero"),
            "motors_released": terminal.get("motors_released"),
            "automatic_retry": False,
        })
        self._raise_if_failed(result)
        return await self.public_state()

    async def abort(self, reason: str = "operator_abort") -> Dict[str, Any]:
        if self.cycle is not None:
            self.cycle.apply({"kind": "abort", "reason": reason, "automatic_retry": False})
        await self.backend.run_gcode("KCTRL_CYCLE_ABORT_V1")
        return await self.public_state()

    async def _wait_phase(self, expected: str, timeout_s: float) -> Mapping[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout_s
        while asyncio.get_running_loop().time() < deadline:
            snapshot = await self.backend.query_status()
            if snapshot.get("cycle_phase") == expected:
                return snapshot
            if snapshot.get("cycle_phase") == "failed_safe":
                raise OrchestrationError("printer_cycle_failed")
            await asyncio.sleep(self.poll_s)
        raise OrchestrationError("phase_timeout:%s" % expected)

    async def _wait_printer_state(self, expected: str, timeout_s: float) -> Mapping[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout_s
        while asyncio.get_running_loop().time() < deadline:
            snapshot = await self.backend.query_status()
            if snapshot.get("printer_state") == expected:
                return snapshot
            await asyncio.sleep(self.poll_s)
        raise OrchestrationError("printer_state_timeout:%s" % expected)

    def _unload_event(self, snapshot: Mapping[str, Any], effect_id: str) -> Dict[str, Any]:
        assert self.job is not None
        return {
            "kind": "unload_before_clean_complete",
            "operation": "preclean-unload",
            "effect_id": effect_id,
            "effect_observed": snapshot.get("routes") == [],
            "target_before_c": self.job.unload_c,
            "target_during_c": snapshot.get("last_cfs_effect_target_c"),
            "cfs_temperature_command": snapshot.get("cfs_temperature_command"),
            "commands": ["BOX_CUT_MATERIAL", "local_tip_retract", "BOX_RETRUDE_MATERIAL"],
            "route_after": self._single_route(snapshot),
            "after_cutter_sensor_after": snapshot.get("after_cutter_sensor"),
            "automatic_retry": False,
        }

    def _reconcile_event(self, snapshot: Mapping[str, Any], effect_id: str) -> Dict[str, Any]:
        assert self.job is not None
        return {
            "kind": "reconcile_before_clean_complete",
            "operation": "preclean-T1A-reconcile",
            "effect_id": effect_id,
            "effect_observed": snapshot.get("routes") == ["T1A"],
            "target_before_c": self.job.load_c,
            "target_during_c": snapshot.get("last_cfs_effect_target_c"),
            "cfs_temperature_command": snapshot.get("cfs_temperature_command"),
            "commands": [
                "BOX_EXTRUDE_MATERIAL TNN=T1A",
                "BOX_EXTRUDER_EXTRUDE TNN=T1A",
            ],
            "route_after": self._single_route(snapshot),
            "head_sensor_after": snapshot.get("head_sensor"),
            "after_cutter_sensor_after": snapshot.get("after_cutter_sensor"),
            "automatic_retry": False,
        }

    def _job_public(self) -> Optional[Dict[str, Any]]:
        if self.job is None:
            return None
        return {
            "job_id": self.job.job_id,
            "filename": self.job.filename,
            "material_id": self.job.material_id,
            "bed_first_c": 55.0,
            "nozzle_first_c": self.job.nozzle_first_c,
        }

    @staticmethod
    def _single_route(snapshot: Mapping[str, Any]) -> Optional[str]:
        routes = snapshot.get("routes")
        return routes[0] if isinstance(routes, list) and len(routes) == 1 else None

    def _require_effects(self) -> None:
        if not self.effects_enabled:
            raise OrchestrationError("CFS_primitives_not_physically_qualified")

    @staticmethod
    def _raise_if_failed(result: Mapping[str, Any]) -> None:
        if result.get("phase") == "failed_safe":
            raise OrchestrationError(str(result.get("failure_code")))

    async def _safe_fail(self, error: Exception) -> None:
        self.last_error = getattr(error, "code", type(error).__name__)
        if self.cycle is not None and self.cycle.phase != "failed_safe":
            self.cycle.apply({"kind": "abort", "reason": self.last_error, "automatic_retry": False})
        try:
            await self.backend.run_gcode("KCTRL_CYCLE_ABORT_V1")
        except Exception:
            pass
