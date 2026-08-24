"""Moonraker endpoint for the reviewed four-pass composite mesh campaign."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from ..common import RequestType, WebRequest
from .k1_control import MoonrakerBackend
from .k1_control_calibration_core import AtomicJsonStore, BackupManager, CalibrationError
from .k1_control_composite_mesh_compose import compose_11x11
from .k1_control_composite_mesh_core import CompositeMeshOrchestrator
from .k1_control_composite_mesh_render import append_profile

if TYPE_CHECKING:
    from ..confighelper import ConfigHelper


class CompositeMeshStateStore(AtomicJsonStore):
    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("version") != 1:
            raise CalibrationError("État de campagne composite illisible.")
        return value


class K1ControlCompositeMesh:
    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        state_path = Path(config.get(
            "state_path", "/usr/data/k1-control-v1/state/k1-control-composite-mesh.json"
        ))
        printer_config = Path(config.get(
            "printer_config_path", "/usr/data/printer_data/config/printer.cfg"
        ))
        z_state = Path(config.get(
            "z_state_path", "/usr/data/k1-control-v1/state/k1-control-z-state.json"
        ))
        backup_root = Path(config.get(
            "backup_root", "/usr/data/k1-control-v1/backups/composite-mesh-v1"
        ))
        self.orchestrator = CompositeMeshOrchestrator(
            MoonrakerBackend(self.server),
            CompositeMeshStateStore(state_path),
            BackupManager(printer_config, z_state, backup_root),
            compose_11x11,
            append_profile,
        )
        self.task: Optional[asyncio.Task[Any]] = None
        self.server.register_notification("k1_control:composite_mesh_update")
        self.server.register_endpoint(
            "/machine/k1_control/composite_mesh/status", RequestType.GET, self._status
        )
        self.server.register_endpoint(
            "/machine/k1_control/composite_mesh/start", RequestType.POST, self._start
        )
        self.server.register_endpoint(
            "/machine/k1_control/composite_mesh/cancel", RequestType.POST, self._cancel
        )
        self.server.register_endpoint(
            "/machine/k1_control/composite_mesh/recover", RequestType.POST, self._recover_capture
        )

    def component_init(self) -> None:
        if self.orchestrator.state.get("busy"):
            self.task = asyncio.create_task(self._recover())

    async def _recover(self) -> None:
        try:
            await self.orchestrator.recover_interrupted()
        except Exception as error:
            self.orchestrator._transition(
                "failed", busy=False, last_error="Reprise composite KO: %s" % error
            )
            logging.exception("K1 Control composite mesh recovery failed")
        self._notify()

    def _notify(self) -> None:
        self.server.send_event(
            "k1_control:composite_mesh_update", self.orchestrator.public_state()
        )

    def _task_done(self, task: asyncio.Task[Any]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logging.exception("K1 Control composite mesh task failed")
        self._notify()

    async def _status(self, web_request: WebRequest) -> Dict[str, Any]:
        return self.orchestrator.public_state()

    async def _start(self, web_request: WebRequest) -> Dict[str, Any]:
        if self.task is not None and not self.task.done():
            raise self.server.error("Une campagne composite est déjà en cours.", 409)
        self.task = asyncio.create_task(self.orchestrator.run(
            str(web_request.get_str("gate", "")),
            web_request.get_boolean("plate_clear", False),
        ))
        self.task.add_done_callback(self._task_done)
        await asyncio.sleep(0)
        self._notify()
        return self.orchestrator.public_state()

    async def _cancel(self, web_request: WebRequest) -> Dict[str, Any]:
        result = self.orchestrator.request_cancel()
        self._notify()
        return result

    async def _recover_capture(self, web_request: WebRequest) -> Dict[str, Any]:
        if self.task is not None and not self.task.done():
            raise self.server.error("Une campagne composite est déjà en cours.", 409)
        self.task = asyncio.create_task(self.orchestrator.recover_complete_capture(
            str(web_request.get_str("gate", ""))
        ))
        self.task.add_done_callback(self._task_done)
        await asyncio.sleep(0)
        self._notify()
        return self.orchestrator.public_state()


def load_component(config: ConfigHelper) -> K1ControlCompositeMesh:
    return K1ControlCompositeMesh(config)
