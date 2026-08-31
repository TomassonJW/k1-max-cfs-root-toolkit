"""Composant Moonraker stock-derived posé immuablement désactivé.

Cette version charge le cœur pur et expose son état, mais ne lit aucun fichier
d'état, ne se connecte pas à Klipper et refuse chaque endpoint d'effet avant de
lire les arguments de la requête. Une activation exigera un nouveau paquet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from ..common import RequestType, WebRequest
from . import k1_control_stock_cycle_core as stock_cycle_core

if TYPE_CHECKING:
    from ..confighelper import ConfigHelper


EFFECT_ENDPOINT_COUNT = 6


class K1ControlStockCycle:
    def __init__(self, config: "ConfigHelper") -> None:
        self.server = config.get_server()
        raw_enabled = str(config.get("enabled", "false")).strip().lower()
        if raw_enabled not in {"true", "false"}:
            raise config.error("enabled must be true or false")
        self.enabled = raw_enabled == "true"
        if self.enabled:
            raise config.error(
                "install-disabled-v1 cannot be enabled; use a reviewed activation package"
            )
        self.state_path = str(config.get(
            "state_path",
            "/usr/data/k1-control-v1/state/stock-derived-cycle-state.json",
        ))
        self.disabled_selftest_count = 0
        self.effect_request_count = 0
        self.server.register_notification("k1_control:stock_cycle_update")
        self.server.register_endpoint(
            "/machine/k1_control/stock-cycle/status",
            RequestType.GET,
            self._status,
        )
        self.server.register_endpoint(
            "/machine/k1_control/stock-cycle/disabled-selftest",
            RequestType.GET,
            self._disabled_selftest,
        )
        self.server.register_endpoint(
            "/machine/k1_control/stock-cycle/begin",
            RequestType.POST,
            self._begin,
        )
        self.server.register_endpoint(
            "/machine/k1_control/stock-cycle/clean-confirm",
            RequestType.POST,
            self._clean_confirm,
        )
        self.server.register_endpoint(
            "/machine/k1_control/stock-cycle/camera-verdict",
            RequestType.POST,
            self._camera_verdict,
        )
        self.server.register_endpoint(
            "/machine/k1_control/stock-cycle/tool-change",
            RequestType.POST,
            self._tool_change,
        )
        self.server.register_endpoint(
            "/machine/k1_control/stock-cycle/runout",
            RequestType.POST,
            self._runout,
        )
        self.server.register_endpoint(
            "/machine/k1_control/stock-cycle/end",
            RequestType.POST,
            self._end,
        )

    def component_init(self) -> None:
        return None

    def _public_state(self) -> Dict[str, Any]:
        return {
            "owner": "k1_control_stock_cycle",
            "version": "install-disabled-v1",
            "enabled": self.enabled,
            "phase": "disabled",
            "core_profile": stock_cycle_core.CURRENT_PROFILE,
            "core_bed_c": stock_cycle_core.CURRENT_BED_C,
            "core_probe_c": stock_cycle_core.CURRENT_PROBE_C,
            "core_first_c": stock_cycle_core.CURRENT_FIRST_C,
            "core_z_mm": stock_cycle_core.CURRENT_Z_MM,
            "effect_endpoint_count": EFFECT_ENDPOINT_COUNT,
            "effect_request_count": self.effect_request_count,
            "disabled_selftest_count": self.disabled_selftest_count,
            "state_file_read_count": 0,
            "state_file_write_count": 0,
            "klippy_query_count": 0,
            "gcode_dispatch_count": 0,
            "camera_request_count": 0,
            "automatic_retry_count": 0,
            "stock_BOX_effect_count": 0,
        }

    async def _status(self, web_request: WebRequest) -> Dict[str, Any]:
        return self._public_state()

    async def _disabled_selftest(self, web_request: WebRequest) -> Dict[str, Any]:
        if self.enabled:
            raise self.server.error(
                "disabled selftest requires disabled component", 409
            )
        for _index in range(EFFECT_ENDPOINT_COUNT):
            try:
                self._require_enabled()
            except Exception as error:
                if "stock_cycle_disabled" not in str(error):
                    raise
            else:
                raise self.server.error("disabled effect guard did not refuse", 500)
        state = self._public_state()
        if any(state[field] != 0 for field in (
            "effect_request_count",
            "state_file_read_count",
            "state_file_write_count",
            "klippy_query_count",
            "gcode_dispatch_count",
            "camera_request_count",
            "automatic_retry_count",
            "stock_BOX_effect_count",
        )):
            raise self.server.error("disabled component has effect history", 500)
        self.disabled_selftest_count += 1
        result = self._public_state()
        result["status"] = "K1_CONTROL_STOCK_CYCLE_DISABLED_SELFTEST_V1_OK"
        result["refused_effect_endpoints"] = EFFECT_ENDPOINT_COUNT
        return result

    async def _begin(self, web_request: WebRequest) -> Dict[str, Any]:
        self._require_enabled()
        raise self.server.error("runtime activation is not installed", 503)

    async def _clean_confirm(self, web_request: WebRequest) -> Dict[str, Any]:
        self._require_enabled()
        raise self.server.error("runtime activation is not installed", 503)

    async def _camera_verdict(self, web_request: WebRequest) -> Dict[str, Any]:
        self._require_enabled()
        raise self.server.error("runtime activation is not installed", 503)

    async def _tool_change(self, web_request: WebRequest) -> Dict[str, Any]:
        self._require_enabled()
        raise self.server.error("runtime activation is not installed", 503)

    async def _runout(self, web_request: WebRequest) -> Dict[str, Any]:
        self._require_enabled()
        raise self.server.error("runtime activation is not installed", 503)

    async def _end(self, web_request: WebRequest) -> Dict[str, Any]:
        self._require_enabled()
        raise self.server.error("runtime activation is not installed", 503)

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise self.server.error("stock_cycle_disabled", 409)


def load_component(config: "ConfigHelper") -> K1ControlStockCycle:
    return K1ControlStockCycle(config)
