"""Moonraker component for the integrated K1 Control production cycle.

This source is installed as ``moonraker.components.k1_control_cycle`` with its
three prefixed support modules beside it.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

from ..common import RequestType, WebRequest
from .k1_control_cycle_job_contract import JobContractError, build_job_contract
from .k1_control_cycle_orchestrator import CycleOrchestrator, OrchestrationError

if TYPE_CHECKING:
    from ..confighelper import ConfigHelper


QUERY_OBJECTS = {
    "webhooks": ["state", "state_message"],
    "print_stats": ["state", "filename"],
    "extruder": ["target", "temperature"],
    "heater_bed": ["target", "temperature"],
    "toolhead": ["homed_axes", "position"],
    "gcode_move": ["homing_origin"],
    "bed_mesh": ["profile_name"],
    "box": None,
    "filament_switch_sensor filament_sensor": ["enabled", "filament_detected"],
    "filament_switch_sensor filament_sensor_2": ["enabled", "filament_detected"],
    "gcode_macro KCTRL_STATE": None,
    "gcode_macro KCTRL_START_OWNER_STATE": None,
    "gcode_macro KCTRL_CYCLE_STATE": None,
}

PREPARATION_PHASES = {
    "unload_before_clean",
    "await_manual_clean",
    "await_geometry",
    "await_t1a_load",
    "await_purge_proof",
    "camera_purge_check",
    "ready_to_print",
}


class MoonrakerCycleBackend:
    def __init__(self, server: Any, selected_job_provider: Any) -> None:
        self.server = server
        self.klippy_apis = server.lookup_component("klippy_apis")
        self._selected_job_provider = selected_job_provider
        self._camera_event = asyncio.Event()
        self._camera_value: Optional[str] = None
        self._camera_evidence_id: Optional[str] = None

    async def selected_job(self) -> Optional[Dict[str, Any]]:
        selected = self._selected_job_provider()
        return deepcopy(selected) if selected is not None else None

    async def query_status(self) -> Dict[str, Any]:
        raw = await self.klippy_apis.query_objects(QUERY_OBJECTS)
        box = raw.get("box", {})
        cycle = raw.get("gcode_macro KCTRL_CYCLE_STATE", {})
        runtime = raw.get("gcode_macro KCTRL_STATE", {})
        print_stats = raw.get("print_stats", {})
        toolhead = raw.get("toolhead", {})
        origin = raw.get("gcode_move", {}).get("homing_origin", [0.0, 0.0, 0.0])
        routes: List[str] = []
        for unit_name in ("T1", "T2"):
            unit = box.get(unit_name, {}) if isinstance(box, Mapping) else {}
            filament = unit.get("filament") if isinstance(unit, Mapping) else None
            if filament in ("A", "B", "C", "D"):
                routes.append(unit_name + str(filament))
        accepted_valid = int(runtime.get("accepted_z_valid", 0)) == 1
        try:
            accepted_z = float(runtime.get("accepted_z_offset"))
            origin_z = float(origin[2])
        except (TypeError, ValueError, IndexError):
            accepted_z = None
            origin_z = None
            accepted_valid = False
        cycle_phase = str(cycle.get("phase", "idle"))
        position = toolhead.get("position", [None, None, None])
        try:
            x, y, z = (float(position[0]), float(position[1]), float(position[2]))
        except (TypeError, ValueError, IndexError):
            x = y = z = float("nan")
        closed = cycle_phase == "closed_safe"
        nozzle_target = float(raw.get("extruder", {}).get("target", 0.0))
        bed_target = float(raw.get("heater_bed", {}).get("target", 0.0))
        last_owner = str(cycle.get("last_effect_owner", "none"))
        return {
            "printer_state": print_stats.get("state"),
            "filename": print_stats.get("filename"),
            "klippy_ready": raw.get("webhooks", {}).get("state") == "ready",
            "nozzle_target_c": nozzle_target,
            "bed_target_c": bed_target,
            "cfs_command": box.get("t_command") if isinstance(box, Mapping) else None,
            "routes": routes,
            "head_sensor": raw.get(
                "filament_switch_sensor filament_sensor", {}
            ).get("filament_detected"),
            "after_cutter_sensor": raw.get(
                "filament_switch_sensor filament_sensor_2", {}
            ).get("filament_detected"),
            "cycle_phase": cycle_phase,
            "mesh_profile": raw.get("bed_mesh", {}).get("profile_name"),
            "accepted_z_valid": accepted_valid,
            "accepted_z_mm": accepted_z,
            "hidden_z_offset_present": not (
                accepted_valid and origin_z is not None and abs(origin_z - accepted_z) <= 0.0005
            ),
            "reference_nozzle_temperature_c": 140.0,
            "bed_temperature_c": 55.0,
            "last_cfs_effect_target_c": cycle.get("last_effect_target"),
            "cfs_temperature_command": False if last_owner == "k1_control" else None,
            "purge_effect_observed": cycle_phase == "camera_purge_check",
            "park_verified": closed and abs(x - 203.0) <= 0.5 and abs(y - 273.0) <= 0.5,
            "bed_lowered_verified": closed and z >= 50.0,
            "heater_targets_zero": closed and nozzle_target == 0.0 and bed_target == 0.0,
            "fans_zero": closed,
            "motors_released": closed,
            "homed_axes": toolhead.get("homed_axes"),
        }

    async def run_gcode(self, script: str) -> Any:
        if script == "KCTRL_CYCLE_SINGLE_PURGE_V1":
            self._camera_event.clear()
            self._camera_value = None
            self._camera_evidence_id = None
        return await self.klippy_apis.run_gcode(script)

    async def start_print(self, filename: str) -> Any:
        return await self.klippy_apis.start_print(filename)

    def submit_camera_verdict(self, verdict: str, evidence_id: str) -> None:
        self._camera_value = verdict
        self._camera_evidence_id = evidence_id
        self._camera_event.set()

    async def camera_verdict(self, checkpoint: str) -> str:
        if checkpoint != "ORIGIN_EDGE_PURGE":
            return "FAIL"
        try:
            await asyncio.wait_for(self._camera_event.wait(), timeout=180.0)
        except asyncio.TimeoutError:
            return "FAIL"
        return self._camera_value or "FAIL"


class K1ControlCycle:
    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.file_manager = self.server.lookup_component("file_manager")
        self.state_path = Path(config.get(
            "state_path", "/usr/data/k1-control-v1/state/integrated-cycle-selected-job.json"
        ))
        self.authority_mode = config.get("authority_mode", "offline").strip().lower()
        if self.authority_mode not in {"offline", "qualification", "production"}:
            raise config.error("authority_mode must be offline, qualification or production")
        self.selected_job: Optional[Dict[str, Any]] = self._load_selected_job()
        self.backend = MoonrakerCycleBackend(self.server, lambda: self.selected_job)
        self.orchestrator = CycleOrchestrator(
            self.backend,
            effects_enabled=self.authority_mode in {"qualification", "production"},
            poll_s=0.5,
        )
        self.task: Optional[asyncio.Task[Any]] = None
        self.server.register_notification("k1_control:cycle_update")
        self.server.register_endpoint(
            "/machine/k1_control/cycle/status", RequestType.GET, self._status
        )
        self.server.register_endpoint(
            "/machine/k1_control/cycle/files", RequestType.GET, self._files
        )
        self.server.register_endpoint(
            "/machine/k1_control/cycle/select", RequestType.POST, self._select
        )
        self.server.register_endpoint(
            "/machine/k1_control/cycle/prepare", RequestType.POST, self._prepare
        )
        self.server.register_endpoint(
            "/machine/k1_control/cycle/clean-confirm", RequestType.POST, self._clean_confirm
        )
        self.server.register_endpoint(
            "/machine/k1_control/cycle/camera-verdict", RequestType.POST, self._camera_verdict
        )
        self.server.register_endpoint(
            "/machine/k1_control/cycle/abort", RequestType.POST, self._abort
        )

    def component_init(self) -> None:
        self.task = asyncio.create_task(self._recover_if_needed())
        self.task.add_done_callback(self._task_done)

    async def _recover_if_needed(self) -> None:
        snapshot = await self.backend.query_status()
        if snapshot.get("cycle_phase") in PREPARATION_PHASES:
            await self.backend.run_gcode("KCTRL_CYCLE_ABORT_V1")

    def _load_selected_job(self) -> Optional[Dict[str, Any]]:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def _persist_selected_job(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.selected_job, sort_keys=True, ensure_ascii=True),
            encoding="utf-8",
        )
        os.replace(str(temporary), str(self.state_path))

    def _notify(self) -> None:
        async def send() -> None:
            self.server.send_event("k1_control:cycle_update", await self.orchestrator.public_state())
        asyncio.create_task(send())

    def _task_done(self, task: asyncio.Task[Any]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logging.exception("K1 Control integrated cycle task failed")
        self._notify()

    def _start_task(self, coroutine: Any) -> None:
        if self.task is not None and not self.task.done():
            raise self.server.error("Une étape du cycle est déjà en cours.", 409)
        self.task = asyncio.create_task(coroutine)
        self.task.add_done_callback(self._task_done)

    async def _status(self, web_request: WebRequest) -> Dict[str, Any]:
        result = await self.orchestrator.public_state()
        result["authority_mode"] = self.authority_mode
        return result

    async def _files(self, web_request: WebRequest) -> Dict[str, Any]:
        storage = self.file_manager.get_metadata_storage()
        files = self.file_manager.get_file_list("gcodes", list_format=True)
        result = []
        for item in sorted(files, key=lambda row: row.get("modified", 0), reverse=True)[:50]:
            filename = item.get("path")
            metadata = storage.get(filename, {}) if isinstance(filename, str) else {}
            result.append({
                "filename": filename,
                "modified": item.get("modified"),
                "size": item.get("size"),
                "filament_type": metadata.get("filament_type"),
                "first_layer_extr_temp": metadata.get("first_layer_extr_temp"),
                "first_layer_bed_temp": metadata.get("first_layer_bed_temp"),
            })
        return {"files": result, "selected": deepcopy(self.selected_job)}

    async def _select(self, web_request: WebRequest) -> Dict[str, Any]:
        snapshot = await self.backend.query_status()
        if snapshot.get("cycle_phase") not in {"idle", "closed_safe"}:
            raise self.server.error("Le cycle courant doit être terminé avant de changer de fichier.", 409)
        filename = web_request.get_str("filename")
        if not self.file_manager.check_file_exists("gcodes", filename):
            raise self.server.error("Le fichier G-code n’existe plus.", 404)
        metadata = self.file_manager.get_metadata_storage().get(filename, None)
        if metadata is None:
            raise self.server.error("Les informations Orca du fichier sont absentes.", 422)
        gcode_root = Path(self.file_manager.get_directory("gcodes")).resolve()
        full_path = gcode_root.joinpath(filename).resolve()
        if gcode_root not in full_path.parents:
            raise self.server.error("Le chemin du fichier sort du dossier G-code.", 422)
        try:
            selected = await self.server.get_event_loop().run_in_thread(
                build_job_contract, filename, metadata, full_path
            )
        except JobContractError as error:
            raise self.server.error("Fichier refusé : %s" % error.code, 422)
        self.selected_job = selected
        self._persist_selected_job()
        self._notify()
        return await self._status(web_request)

    async def _prepare(self, web_request: WebRequest) -> Dict[str, Any]:
        if self.selected_job is None:
            raise self.server.error("Choisis d’abord un fichier compatible.", 409)
        snapshot = await self.backend.query_status()
        if snapshot.get("cycle_phase") == "closed_safe":
            await self.backend.run_gcode("KCTRL_CYCLE_RESET_V1")
        self._start_task(self.orchestrator.prepare(self.selected_job))
        await asyncio.sleep(0)
        return await self._status(web_request)

    async def _clean_confirm(self, web_request: WebRequest) -> Dict[str, Any]:
        if not all((
            web_request.get_boolean("operator_confirmed", False),
            web_request.get_boolean("nozzle_visibly_clean", False),
            web_request.get_boolean("confirmation_fresh", False),
        )):
            raise self.server.error("Confirme seulement après avoir réellement nettoyé la buse.", 422)
        self._start_task(self._continue_through_normal_end())
        await asyncio.sleep(0)
        return await self._status(web_request)

    async def _continue_through_normal_end(self) -> None:
        await self.orchestrator.confirm_clean_and_start()
        await self.orchestrator.observe_normal_end()

    async def _camera_verdict(self, web_request: WebRequest) -> Dict[str, Any]:
        verdict = web_request.get_str("verdict").upper()
        evidence_id = web_request.get_str("evidence_id")
        if verdict not in {"PASS", "FAIL"} or not evidence_id:
            raise self.server.error("Verdict caméra invalide.", 422)
        snapshot = await self.backend.query_status()
        if snapshot.get("cycle_phase") != "camera_purge_check":
            raise self.server.error("Aucun contrôle caméra de purge n’est attendu.", 409)
        self.backend.submit_camera_verdict(verdict, evidence_id)
        return {"accepted": True, "verdict": verdict, "evidence_id": evidence_id}

    async def _abort(self, web_request: WebRequest) -> Dict[str, Any]:
        if self.task is not None and not self.task.done():
            self.task.cancel()
        result = await self.orchestrator.abort("operator_abort")
        self._notify()
        return result


def load_component(config: ConfigHelper) -> K1ControlCycle:
    return K1ControlCycle(config)
