"""Verrou Klipper du runout CFS possede par K1 Control.

Le G-code stock du capteur ``filament_sensor_2`` appelle historiquement
``BOX_CHECK_MATERIAL_REFILL`` apres avoir mis l'impression en pause et avance
le dernier segment de 30 mm. Ce composant remplace uniquement ce point
d'entree, sans appeler le handler stock. Il publie un signal monotone que
Moonraker peut consommer apres avoir persiste son ticket.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, Optional


OWNER_NAME = "k1_control_cfs_runout_owner"
ROUTE = re.compile(r"T[12][ABCD]")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}")


class RuntimeGateError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _route(value: Any, code: str) -> str:
    result = str(value).upper()
    if ROUTE.fullmatch(result) is None:
        raise RuntimeGateError(code)
    return result


def _safe_id(value: Any, code: str) -> str:
    result = str(value)
    if SAFE_ID.fullmatch(result) is None:
        raise RuntimeGateError(code)
    return result


def _temperature(
    value: Any,
    code: str,
    *,
    minimum_c: float,
    maximum_c: float,
    allow_zero: bool = False,
) -> float:
    if isinstance(value, bool):
        raise RuntimeGateError(code)
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise RuntimeGateError(code)
    if not math.isfinite(result):
        raise RuntimeGateError(code)
    if allow_zero and result == 0.0:
        return result
    if not minimum_c <= result <= maximum_c:
        raise RuntimeGateError(code)
    return result


class K1ControlCfsRunoutOwner:
    cmd_LATCH_help = "Capture sans effet le runout emis par filament_sensor_2"
    cmd_ARM_help = "Arme le prochain signal runout apres preuve de chargement"
    cmd_DISARM_help = "Desarme le runout avant un retrait intentionnel"
    cmd_RELEASE_help = "Libere logiquement une route reellement epuisee, sans moteur"
    cmd_STATUS_help = "Etat du verrou runout possede par K1 Control"

    def __init__(self, config) -> None:
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.enabled = config.getboolean("enabled", False)
        self.direct_owner_name = config.get(
            "direct_owner", "k1_control_cfs_direct_owner"
        )
        self.sensor_name = config.get(
            "runout_sensor", "filament_switch_sensor filament_sensor_2"
        )
        self.head_sensor_name = config.get(
            "head_sensor", "filament_switch_sensor filament_sensor"
        )
        self.print_stats_name = config.get("print_stats", "print_stats")
        self.bed_name = config.get("heater_bed", "heater_bed")
        self.pause_macro_name = config.get(
            "pause_macro", "gcode_macro PRINTER_PARAM"
        )

        self.ready_verified = False
        self.stock_handler_isolated = False
        self.public_box_check_owned = False
        self.armed = False
        self.event_seq = 0
        self.consumed_seq = 0
        self.last_route: Optional[str] = None
        self.last_nozzle_target_c: Optional[float] = None
        self.last_bed_target_c: Optional[float] = None
        self.last_failure: Optional[str] = None
        self.latch_count = 0
        self.arm_count = 0
        self.disarm_count = 0
        self.logical_release_count = 0
        self.claimed_effect_ids = set()

        previous = self.gcode.register_command("BOX_CHECK_MATERIAL_REFILL", None)
        if previous is None:
            raise config.error(
                "K1 Control runout: direct owner load order is required"
            )
        previous_owner = getattr(previous, "__self__", None)
        if previous_owner is None or not hasattr(previous_owner, "get_status"):
            raise config.error(
                "K1 Control runout: previous BOX_CHECK owner is not inspectable"
            )
        status = previous_owner.get_status(self.reactor.monotonic())
        if status.get("owner") != "k1_control_cfs_direct_owner":
            raise config.error(
                "K1 Control runout: stock BOX_CHECK was not isolated first"
            )
        self.stock_handler_isolated = True
        self.gcode.register_command(
            "BOX_CHECK_MATERIAL_REFILL", self.cmd_LATCH, desc=self.cmd_LATCH_help
        )
        self.public_box_check_owned = True
        self.gcode.register_command(
            "KCTRL_CFS_RUNOUT_ARM_V1", self.cmd_ARM, desc=self.cmd_ARM_help
        )
        self.gcode.register_command(
            "KCTRL_CFS_RUNOUT_DISARM_V1",
            self.cmd_DISARM,
            desc=self.cmd_DISARM_help,
        )
        self.gcode.register_command(
            "KCTRL_CFS_RUNOUT_RELEASE_V1",
            self.cmd_RELEASE,
            desc=self.cmd_RELEASE_help,
        )
        self.gcode.register_command(
            "KCTRL_CFS_RUNOUT_STATUS_V1", self.cmd_STATUS, desc=self.cmd_STATUS_help
        )
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _object(self, name: str, code: str):
        value = self.printer.lookup_object(name, None)
        if value is None:
            raise RuntimeGateError(code)
        return value

    def _status(self, name: str, code: str) -> Dict[str, Any]:
        value = self._object(name, code).get_status(self.reactor.monotonic())
        if not isinstance(value, dict):
            raise RuntimeGateError(code)
        return value

    def _direct(self):
        return self._object(self.direct_owner_name, "direct_owner_missing")

    def _direct_status(self) -> Dict[str, Any]:
        value = self._direct().get_status(self.reactor.monotonic())
        if (
            value.get("enabled") is not True
            or value.get("stock_commands_blocked") is not True
            or value.get("failure_code") is not None
        ):
            raise RuntimeGateError("direct_owner_not_ready")
        return value

    def _sensor(self, name: str, code: str) -> Dict[str, Any]:
        value = self._status(name, code)
        if value.get("filament_detected") not in (True, False):
            raise RuntimeGateError(code)
        return value

    def _handle_ready(self) -> None:
        try:
            if not self.enabled:
                raise RuntimeGateError("runout_owner_disabled")
            self._direct_status()
            self._sensor(self.sensor_name, "runout_sensor_invalid")
            self._sensor(self.head_sensor_name, "head_sensor_invalid")
            self.ready_verified = True
            self.last_failure = None
        except RuntimeGateError as error:
            self.ready_verified = False
            self.last_failure = error.code
            logging.exception("K1 Control runout owner failed at ready")
            self.printer.invoke_shutdown(
                "K1 Control runout owner startup failure: %s" % error.code
            )

    def _require_enabled_ready(self) -> None:
        if not self.enabled:
            raise RuntimeGateError("runout_owner_disabled")
        if not self.ready_verified:
            raise RuntimeGateError("runout_owner_not_ready")
        if not self.stock_handler_isolated or not self.public_box_check_owned:
            raise RuntimeGateError("stock_runout_handler_not_isolated")

    def cmd_ARM(self, gcmd) -> None:
        try:
            self._require_enabled_ready()
            route = _route(gcmd.get("ROUTE"), "runout_arm_route_invalid")
            direct = self._direct_status()
            if direct.get("active_route") != route or direct.get("phase") != "loaded":
                raise RuntimeGateError("runout_arm_route_not_loaded")
            head = self._sensor(self.head_sensor_name, "head_sensor_invalid")
            runout = self._sensor(self.sensor_name, "runout_sensor_invalid")
            if head.get("enabled") is not True or runout.get("enabled") is not True:
                raise RuntimeGateError("runout_arm_sensor_disabled")
            if head["filament_detected"] is not True or runout["filament_detected"] is not True:
                raise RuntimeGateError("runout_arm_filament_proof_missing")
            state = self._status(self.print_stats_name, "print_stats_invalid").get("state")
            if state not in ("standby", "paused"):
                raise RuntimeGateError("runout_arm_print_state_invalid")
            if self.event_seq != self.consumed_seq:
                raise RuntimeGateError("runout_event_not_consumed")
            self.armed = True
            self.arm_count += 1
            self.last_failure = None
        except RuntimeGateError as error:
            self.last_failure = error.code
            raise gcmd.error("K1 Control runout: %s" % error.code)
        gcmd.respond_info("KCTRL_CFS_RUNOUT_ARM_V1_OK route=%s" % route)

    def cmd_LATCH(self, gcmd) -> None:
        try:
            self._require_enabled_ready()
            if not self.armed:
                raise RuntimeGateError("runout_not_armed")
            state = self._status(self.print_stats_name, "print_stats_invalid").get("state")
            if state != "paused":
                raise RuntimeGateError("runout_pause_not_latched")
            runout = self._sensor(self.sensor_name, "runout_sensor_invalid")
            if runout["filament_detected"] is not False:
                raise RuntimeGateError("runout_sensor_not_clear")
            direct = self._direct_status()
            route = _route(direct.get("active_route"), "runout_active_route_missing")
            pause = self._status(self.pause_macro_name, "pause_context_missing")
            nozzle_target = _temperature(
                pause.get("hotend_temp"),
                "runout_original_nozzle_target_invalid",
                minimum_c=150.0,
                maximum_c=320.0,
            )
            bed = self._status(self.bed_name, "heater_bed_invalid")
            bed_target = _temperature(
                bed.get("target"),
                "runout_bed_target_invalid",
                minimum_c=1.0,
                maximum_c=130.0,
                allow_zero=True,
            )
            self.event_seq += 1
            self.last_route = route
            self.last_nozzle_target_c = nozzle_target
            self.last_bed_target_c = bed_target
            self.armed = False
            self.latch_count += 1
            self.last_failure = None
        except RuntimeGateError as error:
            self.last_failure = error.code
            raise gcmd.error("K1 Control runout: %s" % error.code)
        gcmd.respond_info(
            "KCTRL_CFS_RUNOUT_LATCH_V1_OK seq=%d route=%s" % (self.event_seq, route)
        )

    def cmd_DISARM(self, gcmd) -> None:
        try:
            self._require_enabled_ready()
            if self.event_seq != self.consumed_seq:
                raise RuntimeGateError("runout_event_not_consumed")
            self.armed = False
            self.disarm_count += 1
            self.last_failure = None
        except RuntimeGateError as error:
            self.last_failure = error.code
            raise gcmd.error("K1 Control runout: %s" % error.code)
        gcmd.respond_info("KCTRL_CFS_RUNOUT_DISARM_V1_OK")

    def cmd_RELEASE(self, gcmd) -> None:
        try:
            self._require_enabled_ready()
            route = _route(gcmd.get("ROUTE"), "runout_release_route_invalid")
            effect_id = _safe_id(gcmd.get("EFFECT_ID"), "effect_id_invalid")
            if effect_id in self.claimed_effect_ids:
                raise RuntimeGateError("effect_id_already_claimed_no_retry")
            if self.event_seq <= self.consumed_seq or self.last_route != route:
                raise RuntimeGateError("runout_event_missing_or_consumed")
            state = self._status(self.print_stats_name, "print_stats_invalid").get("state")
            if state != "paused":
                raise RuntimeGateError("runout_pause_not_latched")
            head = self._sensor(self.head_sensor_name, "head_sensor_invalid")
            runout = self._sensor(self.sensor_name, "runout_sensor_invalid")
            if head["filament_detected"] is not False or runout["filament_detected"] is not False:
                raise RuntimeGateError("runout_tail_not_clear")
            direct = self._direct()
            direct_status = self._direct_status()
            if direct_status.get("active_route") != route or direct_status.get("phase") != "loaded":
                raise RuntimeGateError("runout_source_route_not_loaded")
            owner = getattr(direct, "owner", None)
            if owner is None or owner.active_route != route or owner.phase != "loaded":
                raise RuntimeGateError("direct_owner_internal_state_invalid")
            self.claimed_effect_ids.add(effect_id)
            owner.active_route = None
            owner.phase = "idle"
            owner.trace.append({
                "kind": "exhausted_route_released_without_motor",
                "route": route,
                "effect_id": effect_id,
                "automatic_retry": False,
            })
            direct.last_result = owner.result()
            direct.last_operation = "runout_release"
            direct.last_effect_id = effect_id
            self.consumed_seq = self.event_seq
            self.logical_release_count += 1
            self.last_failure = None
        except RuntimeGateError as error:
            self.last_failure = error.code
            raise gcmd.error("K1 Control runout: %s" % error.code)
        gcmd.respond_info(
            "KCTRL_CFS_RUNOUT_RELEASE_V1_OK seq=%d route=%s no_motor=1"
            % (self.consumed_seq, route)
        )

    def cmd_STATUS(self, gcmd) -> None:
        status = self.get_status(self.reactor.monotonic())
        gcmd.respond_info(
            "KCTRL_CFS_RUNOUT_STATUS_V1 ready=%d armed=%d seq=%d consumed=%d route=%s"
            % (
                1 if status["ready_verified"] else 0,
                1 if status["armed"] else 0,
                status["event_seq"],
                status["consumed_seq"],
                status["last_route"] or "none",
            )
        )

    def get_status(self, eventtime) -> Dict[str, Any]:
        return {
            "owner": OWNER_NAME,
            "version": "activation-v1",
            "enabled": self.enabled,
            "ready_verified": self.ready_verified,
            "stock_handler_isolated": self.stock_handler_isolated,
            "public_box_check_owned": self.public_box_check_owned,
            "armed": self.armed,
            "event_seq": self.event_seq,
            "consumed_seq": self.consumed_seq,
            "last_route": self.last_route,
            "last_nozzle_target_c": self.last_nozzle_target_c,
            "last_bed_target_c": self.last_bed_target_c,
            "last_failure": self.last_failure,
            "latch_count": self.latch_count,
            "arm_count": self.arm_count,
            "disarm_count": self.disarm_count,
            "logical_release_count": self.logical_release_count,
            "claimed_effect_count": len(self.claimed_effect_ids),
            "automatic_retry_count": 0,
            "cfs_frame_count": 0,
            "motor_effect_count": 0,
            "heater_effect_count": 0,
            "motion_effect_count": 0,
            "probe_count": 0,
            "mesh_recalculation_count": 0,
        }


def load_config(config):
    return K1ControlCfsRunoutOwner(config)
