"""Moonraker API for the bounded K1 Control calibration workflow."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from ..common import RequestType, WebRequest
from .k1_control_calibration_core import (
    AtomicJsonStore,
    BackupManager,
    CalibrationError,
    CalibrationOrchestrator,
)

if TYPE_CHECKING:
    from ..confighelper import ConfigHelper


QUERY_OBJECTS = {
    "print_stats": ["state", "filename"],
    "extruder": ["target", "temperature"],
    "heater_bed": ["target", "temperature"],
    "toolhead": ["homed_axes", "position"],
    "gcode_move": ["homing_origin"],
    "bed_mesh": None,
    "box": None,
    "gcode_macro KCTRL_STATE": None,
    "k1_control_store": None,
    "gcode_macro KCTRL_CAL_PATH_STATE": None,
}


class MoonrakerBackend:
    def __init__(self, server: Any) -> None:
        self.server = server
        self.klippy_apis = server.lookup_component("klippy_apis")
        self.klippy_connection = server.lookup_component("klippy_connection")

    async def query_status(self) -> Dict[str, Any]:
        return await self.klippy_apis.query_objects(QUERY_OBJECTS)

    async def run_gcode(self, script: str, disconnect_ok: bool = False) -> Any:
        try:
            return await self.klippy_apis.run_gcode(script)
        except self.server.error as error:
            if disconnect_ok and str(error) == "Klippy Disconnected":
                return "disconnected_after_reviewed_restart"
            raise

    async def update_mesh(self, matrix: Any) -> Any:
        request = WebRequest("update_mesh", {"probed_matrix": matrix})
        try:
            return await self.klippy_connection.request(request)
        except self.server.error as error:
            if str(error) == "Klippy Disconnected":
                return "disconnected_after_reviewed_restart"
            raise

    async def wait_klippy_ready(self, timeout: int) -> None:
        await asyncio.sleep(2)
        deadline = asyncio.get_running_loop().time() + timeout
        last_error = "Klipper non disponible"
        while asyncio.get_running_loop().time() < deadline:
            try:
                status = await self.query_status()
                if status.get("print_stats", {}).get("state"):
                    return
            except Exception as error:
                last_error = str(error)
            await asyncio.sleep(1)
        raise CalibrationError("Klipper non stabilisé : %s" % last_error)


class K1ControlCalibration:
    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        state_path = Path(config.get(
            "state_path",
            "/usr/data/k1-control-v1/state/k1-control-calibration-workflow.json",
        ))
        printer_config = Path(config.get(
            "printer_config_path",
            "/usr/data/printer_data/config/printer.cfg",
        ))
        z_state = Path(config.get(
            "z_state_path",
            "/usr/data/k1-control-v1/state/k1-control-z-state.json",
        ))
        backup_root = Path(config.get(
            "backup_root",
            "/usr/data/k1-control-v1/backups/calibration-ui-v1",
        ))
        backend = MoonrakerBackend(self.server)
        self.orchestrator = CalibrationOrchestrator(
            backend,
            AtomicJsonStore(state_path),
            BackupManager(printer_config, z_state, backup_root),
        )
        self.task: Optional[asyncio.Task[Any]] = None
        self.server.register_notification("k1_control:calibration_update")
        self.server.register_endpoint(
            "/machine/k1_control/status", RequestType.GET, self._status
        )
        self.server.register_endpoint(
            "/machine/k1_control/calibration/start", RequestType.POST, self._start
        )
        self.server.register_endpoint(
            "/machine/k1_control/calibration/cancel", RequestType.POST, self._cancel
        )
        self.server.register_endpoint(
            "/machine/k1_control/calibration/rollback", RequestType.POST, self._rollback
        )
        self.server.register_endpoint(
            "/machine/k1_control/z/start", RequestType.POST, self._begin_z
        )
        self.server.register_endpoint(
            "/machine/k1_control/z/step", RequestType.POST, self._step_z
        )
        self.server.register_endpoint(
            "/machine/k1_control/z/adjust", RequestType.POST, self._adjust_z
        )
        self.server.register_endpoint(
            "/machine/k1_control/z/confirm", RequestType.POST, self._confirm_z
        )
        self.server.register_endpoint(
            "/machine/k1_control/z/accept", RequestType.POST, self._accept_z
        )
        self.server.register_endpoint(
            "/machine/k1_control/z/restore", RequestType.POST, self._restore_z
        )

    def component_init(self) -> None:
        if self.orchestrator.state.get("busy"):
            self.task = asyncio.create_task(self._recover_interrupted_campaign())

    async def _recover_interrupted_campaign(self) -> None:
        try:
            await self.orchestrator.cancel()
        except Exception as error:
            self.orchestrator._transition(
                "failed", busy=False,
                last_error="Reprise de sécurité incomplète : %s" % error,
            )
            logging.exception("K1 Control calibration recovery failed")
        self._notify()

    def _notify(self) -> None:
        self.server.send_event(
            "k1_control:calibration_update", self.orchestrator.public_state()
        )

    def _task_done(self, task: asyncio.Task[Any]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logging.exception("K1 Control calibration task failed")
        self._notify()

    async def _status(self, web_request: WebRequest) -> Dict[str, Any]:
        result = self.orchestrator.public_state()
        status = await self.orchestrator.backend.query_status()
        runtime = status.get("gcode_macro KCTRL_STATE", {})
        previous_available = int(runtime.get("previous_z_valid", 0)) == 1
        accepted_available = int(runtime.get("accepted_z_valid", 0)) == 1
        try:
            accepted_offset = float(runtime.get("accepted_z_offset"))
        except (TypeError, ValueError):
            accepted_offset = None
            accepted_available = False
        result["accepted_z_valid"] = accepted_available
        result["accepted_z_offset_mm"] = (
            accepted_offset if accepted_available else None
        )
        result["previous_z_available"] = previous_available
        result["previous_z_restorable"] = (
            previous_available
            and status.get("print_stats", {}).get("state") == "standby"
            and "xyz" in str(status.get("toolhead", {}).get("homed_axes", ""))
            and not result.get("busy")
        )
        return result

    async def _start(self, web_request: WebRequest) -> Dict[str, Any]:
        if self.task is not None and not self.task.done():
            raise self.server.error("Une calibration est déjà en cours.", 409)
        args = dict(web_request.get_args())
        plate_clear = web_request.get_boolean("plate_clear", False)
        self.task = asyncio.create_task(
            self.orchestrator.run_mesh_campaign(args, plate_clear)
        )
        self.task.add_done_callback(self._task_done)
        await asyncio.sleep(0)
        self._notify()
        return self.orchestrator.public_state()

    async def _cancel(self, web_request: WebRequest) -> Dict[str, Any]:
        if self.task is not None and not self.task.done():
            result = self.orchestrator.request_cancel()
        else:
            result = await self.orchestrator.cancel()
        self._notify()
        return result

    async def _begin_z(self, web_request: WebRequest) -> Dict[str, Any]:
        if self.task is not None and not self.task.done():
            raise self.server.error("Une calibration est déjà en cours.", 409)
        self.task = asyncio.create_task(
            self.orchestrator.begin_z(
                web_request.get_boolean("plate_clear", False),
                web_request.get_boolean("nozzle_clean", False),
            )
        )
        self.task.add_done_callback(self._task_done)
        await asyncio.sleep(0)
        result = self.orchestrator.public_state()
        self._notify()
        return result

    async def _rollback(self, web_request: WebRequest) -> Dict[str, Any]:
        result = await self.orchestrator.rollback_campaign()
        self._notify()
        return result

    async def _step_z(self, web_request: WebRequest) -> Dict[str, Any]:
        result = await self.orchestrator.step_z()
        self._notify()
        return result

    async def _adjust_z(self, web_request: WebRequest) -> Dict[str, Any]:
        result = await self.orchestrator.adjust_z(web_request.get_float("delta"))
        self._notify()
        return result

    async def _confirm_z(self, web_request: WebRequest) -> Dict[str, Any]:
        result = await self.orchestrator.confirm_gap(
            web_request.get_boolean("observed", False)
        )
        self._notify()
        return result

    async def _accept_z(self, web_request: WebRequest) -> Dict[str, Any]:
        result = await self.orchestrator.accept_z()
        self._notify()
        return result

    async def _restore_z(self, web_request: WebRequest) -> Dict[str, Any]:
        result = await self.orchestrator.restore_previous_z()
        self._notify()
        return result


def load_component(config: ConfigHelper) -> K1ControlCalibration:
    return K1ControlCalibration(config)
