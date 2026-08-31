"""Exclusion persistante du petit propriétaire stock ``auto_refill``.

Ce composant doit être chargé immédiatement avant le propriétaire CFS direct.
Il capture le handler stock déjà qualifié, ferme sa surface publique, puis
impose une fois ``ENABLE=0`` à ``klippy:ready``. Aucun autre handler stock
n'est conservé ou appelé.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional


class StartupExclusionError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class K1ControlCfsStartupExclusion:
    cmd_STATUS_help = "Etat de l'exclusion persistante auto_refill"
    cmd_SELFTEST_help = "Valide l'exclusion active sans nouvel effet"

    def __init__(self, config) -> None:
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.enabled = config.getboolean("enabled", False)
        self.box_name = config.get("box", "box")
        self.captured_handler = None
        self.policy_call_count = 0
        self.policy_already_zero_count = 0
        self.selftest_count = 0
        self.ready_verified = False
        self.last_failure: Optional[str] = None

        self.gcode.register_command(
            "KCTRL_CFS_STARTUP_EXCLUSION_STATUS_V1",
            self.cmd_STATUS,
            desc=self.cmd_STATUS_help,
        )
        self.gcode.register_command(
            "KCTRL_CFS_STARTUP_EXCLUSION_SELFTEST_V1",
            self.cmd_SELFTEST,
            desc=self.cmd_SELFTEST_help,
        )
        if self.enabled:
            original = self.gcode.register_command("BOX_ENABLE_AUTO_REFILL", None)
            if original is None:
                raise config.error("stock_auto_refill_handler_missing_or_load_order_invalid")
            self.captured_handler = original
            self.gcode.register_command(
                "BOX_ENABLE_AUTO_REFILL", self.cmd_STOCK_POLICY_BLOCKED
            )
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _handle_ready(self) -> None:
        if not self.enabled:
            logging.info("K1 Control CFS startup exclusion disabled")
            return
        try:
            box = self.printer.lookup_object(self.box_name, None)
            if box is None:
                raise StartupExclusionError("box_status_object_missing")
            before = self._box_status(box)
            if before.get("auto_refill") == 1:
                gcmd = self.gcode.create_gcode_command(
                    "BOX_ENABLE_AUTO_REFILL",
                    "BOX_ENABLE_AUTO_REFILL ENABLE=0",
                    {"ENABLE": "0"},
                )
                self.captured_handler(gcmd)
                self.policy_call_count += 1
            elif before.get("auto_refill") == 0:
                self.policy_already_zero_count += 1
            else:
                raise StartupExclusionError("stock_auto_refill_initial_value_invalid")
            self._require_excluded(self._box_status(box))
            self.ready_verified = True
            self.last_failure = None
            logging.info(
                "K1 Control CFS startup exclusion ready calls=%d already_zero=%d",
                self.policy_call_count,
                self.policy_already_zero_count,
            )
        except StartupExclusionError as error:
            self.last_failure = error.code
            self.printer.invoke_shutdown(
                "K1 Control CFS startup exclusion: %s" % error.code
            )
        except Exception:
            self.last_failure = "stock_auto_refill_private_handler_failed"
            logging.exception("K1 Control CFS startup exclusion failed")
            self.printer.invoke_shutdown(
                "K1 Control CFS startup exclusion: stock_auto_refill_private_handler_failed"
            )

    def _box_status(self, box) -> Dict[str, Any]:
        status = box.get_status(self.reactor.monotonic())
        if not isinstance(status, dict):
            raise StartupExclusionError("box_status_invalid")
        return status

    def _require_excluded(self, status: Dict[str, Any]) -> None:
        if status.get("auto_refill") != 0:
            raise StartupExclusionError("stock_auto_refill_not_zero_after_private_call")
        if status.get("t_command") != "" or status.get("enable") not in (1, True):
            raise StartupExclusionError("stock_owner_boundary_not_idle")
        for name in ("T1", "T2"):
            unit = status.get(name)
            if not isinstance(unit, dict) or unit.get("state") != "connect":
                raise StartupExclusionError("%s_not_connected" % name)

    def cmd_STOCK_POLICY_BLOCKED(self, gcmd) -> None:
        raise gcmd.error("K1 Control CFS startup exclusion: stock_policy_publicly_blocked")

    def cmd_STATUS(self, gcmd) -> None:
        status = self.get_status(self.reactor.monotonic())
        gcmd.respond_info(
            "KCTRL_CFS_STARTUP_EXCLUSION_STATUS_V1 enabled=%d ready=%d calls=%d failure=%s"
            % (
                1 if status["enabled"] else 0,
                1 if status["ready_verified"] else 0,
                status["policy_call_count"],
                status["last_failure"] or "none",
            )
        )

    def cmd_SELFTEST(self, gcmd) -> None:
        if not self.enabled or not self.ready_verified or self.last_failure is not None:
            raise gcmd.error("K1 Control CFS startup exclusion: active_exclusion_not_ready")
        box = self.printer.lookup_object(self.box_name, None)
        if box is None:
            raise gcmd.error("K1 Control CFS startup exclusion: box_status_object_missing")
        try:
            self._require_excluded(self._box_status(box))
        except StartupExclusionError as error:
            raise gcmd.error("K1 Control CFS startup exclusion: %s" % error.code)
        if self.policy_call_count > 1:
            raise gcmd.error("K1 Control CFS startup exclusion: policy_called_more_than_once")
        self.selftest_count += 1
        gcmd.respond_info(
            "KCTRL_CFS_STARTUP_EXCLUSION_SELFTEST_V1_OK policy_calls=%d no_physical_effect=1"
            % self.policy_call_count
        )

    def get_status(self, eventtime) -> Dict[str, Any]:
        return {
            "owner": "k1_control_cfs_startup_exclusion",
            "version": "activation-v1",
            "enabled": self.enabled,
            "ready_verified": self.ready_verified,
            "policy_call_count": self.policy_call_count,
            "policy_already_zero_count": self.policy_already_zero_count,
            "selftest_count": self.selftest_count,
            "last_failure": self.last_failure,
            "captured_policy_handler": self.captured_handler is not None,
            "automatic_retry_count": 0,
            "heat_command_count": 0,
            "motion_command_count": 0,
            "extrusion_command_count": 0,
            "cfs_frame_count": 0,
            "other_stock_handler_call_count": 0,
        }


def load_config(config):
    return K1ControlCfsStartupExclusion(config)
