"""Adaptateur Klipper du propriétaire CFS direct K1 Control.

La configuration livrée par cette gate garde `enabled: false`. Dans cet état,
le module n'acquiert pas le transport série, ne remplace aucune commande stock
et refuse les trois entrées susceptibles d'envoyer une trame CFS.

Une gate physique ultérieure pourra poser `enabled: true`. Au redémarrage, les
entrées CFS stock connues sont alors remplacées par des refus, l'auto-remplacement
stock doit déjà être à zéro et chaque effet reste borné par le coeur hors ligne.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from .k1_control_cfs_direct import owner as owner_core
from .k1_control_cfs_direct import runtime_adapter


OWNER_NAME = "k1_control_direct"

# Ces entrées sont les surfaces stock observées ou inventoriées qui peuvent
# lancer, reprendre ou modifier un mouvement filament. Une commande absente est
# déjà exclue ; une commande présente est remplacée uniquement quand le
# propriétaire direct est activé au démarrage de Klipper.
STOCK_EFFECT_COMMANDS = (
    "BOX_CHECK_MATERIAL_REFILL",
    "BOX_CUT_MATERIAL",
    "BOX_ENABLE_AUTO_REFILL",
    "BOX_ENABLE_CFS_PRINT",
    "BOX_END_PRINT",
    "BOX_ERROR_CLEAR",
    "BOX_EXTRUDE_MATERIAL",
    "BOX_EXTRUDER_EXTRUDE",
    "BOX_EXTRUSION_ALL_MATERIALS",
    "BOX_MATERIAL_CHANGE_FLUSH",
    "BOX_MATERIAL_FLUSH",
    "BOX_NOZZLE_CLEAN",
    "BOX_POWER_LOSS_RESTORE",
    "BOX_RESUME_EXTRUDE",
    "BOX_RETRUDE_MATERIAL",
    "BOX_RETRUDE_MATERIAL_WITH_TNN",
    "BOX_START_PRINT",
    "BOX_TNN_RETRY_PROCESS",
    "BOX_UPDATE_SAME_MATERIAL_LIST",
)


class RuntimeGateError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _connected_boxes(value: str) -> Tuple[int, ...]:
    try:
        result = tuple(sorted(set(int(item.strip()) for item in value.split(","))))
    except (TypeError, ValueError):
        raise RuntimeGateError("connected_boxes_invalid")
    if not result or any(item not in (1, 2) for item in result):
        raise RuntimeGateError("connected_boxes_invalid")
    return result


class K1ControlCfsDirectOwner:
    cmd_STATUS_help = "Etat du propriétaire CFS direct K1 Control"
    cmd_DISABLED_SELFTEST_help = "Prouve que la pose désactivée reste sans effet"
    cmd_PREFLIGHT_help = "Préflight sans trame du propriétaire CFS direct activé"
    cmd_RECONCILE_help = "Réassocie une route chargée avec une seule lecture CFS"
    cmd_ADOPT_RETAINED_SEGMENT_help = (
        "Confirme sans mouvement un segment coupé resté dans la tête"
    )
    cmd_RECOVER_EXTRUDE_ERROR_LOAD_TAIL_help = (
        "Termine une insertion EXTRUDE_ERR8 déjà arrivée aux deux capteurs"
    )
    cmd_FINALIZE_LOAD_TAKEOVER_help = (
        "Valide le buffer après prise locale et verrouille la route sans moteur"
    )
    cmd_LOAD_help = "Charge une route CFS par les trames directes bornées"
    cmd_UNLOAD_help = "Retire une route CFS par les trames directes bornées"

    def __init__(self, config) -> None:
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.enabled = config.getboolean("enabled", False)
        self.connected_boxes = _connected_boxes(
            config.get("connected_boxes", "1, 2")
        )
        self.head_sensor_name = config.get(
            "head_sensor", "filament_switch_sensor filament_sensor"
        )
        self.after_cutter_sensor_name = config.get(
            "after_cutter_sensor",
            "filament_switch_sensor filament_sensor_2",
        )
        self.max_pushes = config.getint("max_pushes", 8, minval=1, maxval=20)

        self.owner: Optional[owner_core.DirectCfsOwner] = None
        self.transport_bound = False
        self.stock_commands_blocked = False
        self.stock_commands_replaced = []
        self.stock_commands_absent = []
        self.stock_surface_present = []
        self.disabled_selftest_count = 0
        self.preflight_count = 0
        self.last_operation: Optional[str] = None
        self.last_effect_id: Optional[str] = None
        self.last_result: Dict[str, Any] = {}
        self.last_box_proof: Dict[str, Any] = {}
        self.retained_segment_recovery_id: Optional[str] = None
        self.err8_load_tail_recovery_id: Optional[str] = None
        self.takeover_finalize_recovery_id: Optional[str] = None

        self.gcode.register_command(
            "KCTRL_CFS_DIRECT_STATUS",
            self.cmd_STATUS,
            desc=self.cmd_STATUS_help,
        )
        self.gcode.register_command(
            "KCTRL_CFS_DIRECT_DISABLED_SELFTEST",
            self.cmd_DISABLED_SELFTEST,
            desc=self.cmd_DISABLED_SELFTEST_help,
        )
        self.gcode.register_command(
            "KCTRL_CFS_DIRECT_PREFLIGHT",
            self.cmd_PREFLIGHT,
            desc=self.cmd_PREFLIGHT_help,
        )
        self.gcode.register_command(
            "KCTRL_CFS_DIRECT_RECONCILE",
            self.cmd_RECONCILE,
            desc=self.cmd_RECONCILE_help,
        )
        self.gcode.register_command(
            "KCTRL_CFS_DIRECT_ADOPT_RETAINED_SEGMENT",
            self.cmd_ADOPT_RETAINED_SEGMENT,
            desc=self.cmd_ADOPT_RETAINED_SEGMENT_help,
        )
        self.gcode.register_command(
            "KCTRL_CFS_DIRECT_RECOVER_EXTRUDE_ERROR_LOAD_TAIL",
            self.cmd_RECOVER_EXTRUDE_ERROR_LOAD_TAIL,
            desc=self.cmd_RECOVER_EXTRUDE_ERROR_LOAD_TAIL_help,
        )
        self.gcode.register_command(
            "KCTRL_CFS_DIRECT_FINALIZE_LOAD_TAKEOVER",
            self.cmd_FINALIZE_LOAD_TAKEOVER,
            desc=self.cmd_FINALIZE_LOAD_TAKEOVER_help,
        )
        self.gcode.register_command(
            "KCTRL_CFS_DIRECT_LOAD",
            self.cmd_LOAD,
            desc=self.cmd_LOAD_help,
        )
        self.gcode.register_command(
            "KCTRL_CFS_DIRECT_UNLOAD",
            self.cmd_UNLOAD,
            desc=self.cmd_UNLOAD_help,
        )

        if self.enabled:
            self._replace_stock_effect_commands()
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _handle_ready(self) -> None:
        handlers = getattr(self.gcode, "ready_gcode_handlers", {})
        self.stock_surface_present = sorted(
            name for name in STOCK_EFFECT_COMMANDS if name in handlers
        )
        logging.info(
            "K1 Control CFS direct ready enabled=%s stock_blocked=%s",
            self.enabled,
            self.stock_commands_blocked,
        )

    def _replace_stock_effect_commands(self) -> None:
        replaced = []
        absent = []
        for name in STOCK_EFFECT_COMMANDS:
            old_handler = self.gcode.register_command(name, None)
            if old_handler is None:
                absent.append(name)
                continue
            self.gcode.register_command(name, self.cmd_STOCK_EFFECT_BLOCKED)
            replaced.append(name)
        self.stock_commands_replaced = sorted(replaced)
        self.stock_commands_absent = sorted(absent)
        self.stock_commands_blocked = True

    def cmd_STOCK_EFFECT_BLOCKED(self, gcmd) -> None:
        raise gcmd.error(
            "K1 Control CFS direct: stock_effect_command_blocked"
        )

    def cmd_STATUS(self, gcmd) -> None:
        status = self.get_status(self.reactor.monotonic())
        gcmd.respond_info(
            "KCTRL_CFS_DIRECT_STATUS enabled=%d phase=%s route=%s "
            "transport_bound=%d stock_blocked=%d failure=%s"
            % (
                1 if status["enabled"] else 0,
                status["phase"],
                status["active_route"] or "none",
                1 if status["transport_bound"] else 0,
                1 if status["stock_commands_blocked"] else 0,
                status["failure_code"] or "none",
            )
        )

    def cmd_DISABLED_SELFTEST(self, gcmd) -> None:
        if self.enabled:
            raise gcmd.error(
                "K1 Control CFS direct: disabled_selftest_requires_disabled_owner"
            )
        if self.transport_bound or self.owner is not None:
            raise gcmd.error(
                "K1 Control CFS direct: disabled_owner_bound_runtime"
            )
        if self.stock_commands_blocked or self.stock_commands_replaced:
            raise gcmd.error(
                "K1 Control CFS direct: disabled_owner_replaced_stock_commands"
            )
        refused = 0
        for _operation in (
            "reconcile",
            "adopt_retained_segment",
            "recover_err8_load_tail",
            "finalize_load_takeover",
            "load",
            "unload",
        ):
            try:
                self._require_enabled()
            except RuntimeGateError as error:
                if error.code != "direct_owner_disabled":
                    raise gcmd.error(
                        "K1 Control CFS direct: disabled_guard_invalid"
                    )
                refused += 1
        if refused != 6:
            raise gcmd.error(
                "K1 Control CFS direct: disabled_guard_count_invalid"
            )
        self.disabled_selftest_count += 1
        gcmd.respond_info("KCTRL_CFS_DIRECT_DISABLED_SELFTEST_OK refused=6")

    def cmd_PREFLIGHT(self, gcmd) -> None:
        try:
            self._require_enabled()
            self._ensure_runtime()
            self._assert_stock_excluded()
        except RuntimeGateError as error:
            raise gcmd.error("K1 Control CFS direct: %s" % error.code)
        self.preflight_count += 1
        gcmd.respond_info(
            "KCTRL_CFS_DIRECT_PREFLIGHT_OK boxes=%s no_frame=1"
            % ",".join(str(item) for item in self.connected_boxes)
        )

    def cmd_RECONCILE(self, gcmd) -> None:
        try:
            self._prepare_effect()
            route = gcmd.get("ROUTE")
            observation_id = gcmd.get("OBSERVATION_ID")
            result = self.owner.reconcile_loaded(route, observation_id)
            self._record_result("reconcile", observation_id, result)
            self._raise_result_failure()
        except RuntimeGateError as error:
            raise gcmd.error("K1 Control CFS direct: %s" % error.code)
        gcmd.respond_info("KCTRL_CFS_DIRECT_RECONCILE_OK route=%s" % route)

    def cmd_ADOPT_RETAINED_SEGMENT(self, gcmd) -> None:
        """Adopte uniquement l'état physique confirmé, sans trame ni moteur."""
        try:
            self._require_enabled()
            recovery_id = gcmd.get("RECOVERY_ID")
            if not recovery_id or recovery_id == self.retained_segment_recovery_id:
                raise RuntimeGateError("retained_segment_recovery_id_invalid_or_used")
            if str(gcmd.get("CONFIRM")) != "1":
                raise RuntimeGateError("retained_segment_human_confirmation_missing")
            self._ensure_runtime()
            self._assert_stock_excluded()
            if self.owner.active_route is not None:
                raise RuntimeGateError("retained_segment_route_not_clear")
            if self.owner.phase not in ("idle", "failed_safe"):
                raise RuntimeGateError("retained_segment_owner_busy")
            if not self._head_sensor() or self._after_cutter_sensor():
                raise RuntimeGateError("retained_segment_sensor_shape_invalid")
            self.owner.active_route = None
            self.owner.retained_head_segment = True
            self.owner.phase = "idle"
            self.owner.failure_code = None
            self.owner.trace.append(
                {
                    "kind": "retained_head_segment_adopted",
                    "recovery_id": recovery_id,
                    "human_confirmed": True,
                    "physical_effect": False,
                }
            )
            self.retained_segment_recovery_id = recovery_id
            self._record_result(
                "adopt_retained_segment", recovery_id, self.owner.result()
            )
        except RuntimeGateError as error:
            raise gcmd.error("K1 Control CFS direct: %s" % error.code)
        gcmd.respond_info(
            "KCTRL_CFS_DIRECT_ADOPT_RETAINED_SEGMENT_OK recovery_id=%s no_effect=1"
            % recovery_id
        )

    def cmd_LOAD(self, gcmd) -> None:
        try:
            self._prepare_effect()
            route = gcmd.get("ROUTE")
            effect_id = gcmd.get("EFFECT_ID")
            result = self.owner.load(
                route,
                effect_id,
                self._temperature_proof(gcmd),
            )
            self._record_result("load", effect_id, result)
            self._raise_result_failure()
        except RuntimeGateError as error:
            raise gcmd.error("K1 Control CFS direct: %s" % error.code)
        gcmd.respond_info("KCTRL_CFS_DIRECT_LOAD_OK route=%s" % route)

    def cmd_RECOVER_EXTRUDE_ERROR_LOAD_TAIL(self, gcmd) -> None:
        """Reprise explicite, unique et sans nouvelle poussée stage 5."""
        try:
            self._require_enabled()
            route = gcmd.get("ROUTE")
            recovery_id = gcmd.get("RECOVERY_ID")
            if route != "T1A":
                raise RuntimeGateError("err8_recovery_route_not_t1a")
            if not recovery_id or recovery_id == self.err8_load_tail_recovery_id:
                raise RuntimeGateError("err8_recovery_id_invalid_or_used")
            if str(gcmd.get("CONFIRM")) != "1":
                raise RuntimeGateError("err8_recovery_confirmation_missing")
            self._ensure_runtime()
            self._assert_stock_excluded()
            self._assert_no_stock_route()
            if self.owner.active_route is not None or self.owner.phase != "idle":
                raise RuntimeGateError("err8_recovery_owner_not_idle")
            if not self._head_sensor() or not self._after_cutter_sensor():
                raise RuntimeGateError("err8_recovery_sensor_shape_invalid")

            # Le restart nécessaire à la pose a réinitialisé l'objet Python.
            # L'état physique est donc réadopté uniquement sous cette forme
            # exacte, avant l'unique fin 4 -> 6 qualifiée hors imprimante.
            self.owner.retained_head_segment = True
            self.owner.trace.append(
                {
                    "kind": "err8_handoff_state_adopted",
                    "route": route,
                    "recovery_id": recovery_id,
                    "human_confirmed": True,
                    "physical_effect": False,
                }
            )
            self.err8_load_tail_recovery_id = recovery_id
            result = self.owner.recover_load_tail(
                route,
                recovery_id,
                self._temperature_proof(gcmd),
            )
            self._record_result("recover_err8_load_tail", recovery_id, result)
            self._raise_result_failure()
        except RuntimeGateError as error:
            raise gcmd.error("K1 Control CFS direct: %s" % error.code)
        gcmd.respond_info(
            "KCTRL_CFS_DIRECT_RECOVER_EXTRUDE_ERROR_LOAD_TAIL_OK route=%s stages=4,6 stage5=0"
            % route
        )

    def cmd_FINALIZE_LOAD_TAKEOVER(self, gcmd) -> None:
        """Clôture après prise locale : lectures puis mode impression."""
        try:
            self._require_enabled()
            route = gcmd.get("ROUTE")
            recovery_id = gcmd.get("RECOVERY_ID")
            if route != "T1A":
                raise RuntimeGateError("takeover_finalize_route_not_t1a")
            if not recovery_id or recovery_id == self.takeover_finalize_recovery_id:
                raise RuntimeGateError("takeover_finalize_id_invalid_or_used")
            if str(gcmd.get("CONFIRM")) != "1":
                raise RuntimeGateError("takeover_finalize_confirmation_missing")
            self._ensure_runtime()
            self._assert_stock_excluded()
            self._assert_no_stock_route()
            if self.owner.active_route is not None or self.owner.phase != "idle":
                raise RuntimeGateError("takeover_finalize_owner_not_idle")
            if not self._head_sensor() or not self._after_cutter_sensor():
                raise RuntimeGateError("takeover_finalize_sensor_shape_invalid")

            self.owner.retained_head_segment = True
            self.owner.trace.append(
                {
                    "kind": "load_takeover_state_adopted",
                    "route": route,
                    "recovery_id": recovery_id,
                    "human_confirmed": True,
                    "physical_effect": False,
                }
            )
            self.takeover_finalize_recovery_id = recovery_id
            result = self.owner.finalize_load_takeover(route, recovery_id)
            self._record_result("finalize_load_takeover", recovery_id, result)
            self._raise_result_failure()
        except RuntimeGateError as error:
            raise gcmd.error("K1 Control CFS direct: %s" % error.code)
        gcmd.respond_info(
            "KCTRL_CFS_DIRECT_FINALIZE_LOAD_TAKEOVER_OK route=%s buffer=0 motor=0"
            % route
        )

    def cmd_UNLOAD(self, gcmd) -> None:
        try:
            self._prepare_effect()
            route = gcmd.get("ROUTE")
            effect_id = gcmd.get("EFFECT_ID")
            result = self.owner.unload(
                route,
                effect_id,
                self._temperature_proof(gcmd),
            )
            self._record_result("unload", effect_id, result)
            self._raise_result_failure()
        except RuntimeGateError as error:
            raise gcmd.error("K1 Control CFS direct: %s" % error.code)
        gcmd.respond_info("KCTRL_CFS_DIRECT_UNLOAD_OK route=%s" % route)

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise RuntimeGateError("direct_owner_disabled")

    def _prepare_effect(self) -> None:
        self._require_enabled()
        self._ensure_runtime()
        self._assert_stock_excluded()

    def _ensure_runtime(self) -> None:
        if self.owner is not None:
            return
        serial_object = self.printer.lookup_object(
            "serial_485 serial485", None
        )
        head_sensor = self.printer.lookup_object(self.head_sensor_name, None)
        after_cutter_sensor = self.printer.lookup_object(
            self.after_cutter_sensor_name, None
        )
        extruder = self.printer.lookup_object("extruder", None)
        box = self.printer.lookup_object("box", None)
        if serial_object is None:
            raise RuntimeGateError("serial_485_interface_missing")
        if head_sensor is None:
            raise RuntimeGateError("head_sensor_object_missing")
        if after_cutter_sensor is None:
            raise RuntimeGateError("after_cutter_sensor_object_missing")
        if extruder is None:
            raise RuntimeGateError("extruder_object_missing")
        if box is None:
            raise RuntimeGateError("box_status_object_missing")
        self._serial_object = serial_object
        self._head_sensor_object = head_sensor
        self._after_cutter_sensor_object = after_cutter_sensor
        self._extruder_object = extruder
        self._box_object = box
        transport = runtime_adapter.StockSerial485Transport(serial_object)
        self.owner = owner_core.DirectCfsOwner(
            transport,
            self._head_sensor,
            self._after_cutter_sensor,
            tip_pull=self._tip_pull,
            connected_boxes=self.connected_boxes,
            max_pushes=self.max_pushes,
        )
        self.transport_bound = True

    def _sensor_value(self, sensor, code: str) -> bool:
        status = sensor.get_status(self.reactor.monotonic())
        value = status.get("filament_detected")
        if value not in (True, False):
            raise RuntimeGateError(code)
        return bool(value)

    def _head_sensor(self) -> bool:
        return self._sensor_value(
            self._head_sensor_object, "head_sensor_status_invalid"
        )

    def _after_cutter_sensor(self) -> bool:
        return self._sensor_value(
            self._after_cutter_sensor_object,
            "after_cutter_sensor_status_invalid",
        )

    def _assert_stock_excluded(self) -> None:
        if not self.stock_commands_blocked:
            raise RuntimeGateError("stock_effect_commands_not_blocked")
        status = self._box_object.get_status(self.reactor.monotonic())
        if status.get("auto_refill") not in (0, False):
            raise RuntimeGateError("stock_auto_refill_not_disabled")
        if status.get("t_command") != "":
            raise RuntimeGateError("stock_command_active")
        if status.get("enable") not in (1, True):
            raise RuntimeGateError("cfs_print_interface_disabled")
        connected = []
        for address in self.connected_boxes:
            item = status.get("T%d" % address)
            if not isinstance(item, dict) or item.get("state") != "connect":
                raise RuntimeGateError("CFS_T%d_not_connected" % address)
            connected.append("T%d" % address)
        self.last_box_proof = {
            "auto_refill": 0,
            "enable": 1,
            "t_command": "",
            "connected": connected,
        }

    def _assert_no_stock_route(self) -> None:
        status = self._box_object.get_status(self.reactor.monotonic())
        routes = []
        for address in self.connected_boxes:
            item = status.get("T%d" % address)
            filament = item.get("filament") if isinstance(item, dict) else None
            if filament in ("A", "B", "C", "D"):
                routes.append("T%d%s" % (address, filament))
        if routes:
            raise RuntimeGateError("err8_recovery_stock_route_present")
        self.last_box_proof["logical_routes"] = []

    def _temperature_proof(self, gcmd) -> Dict[str, Any]:
        expected = gcmd.get_float("EXPECTED_C", minval=170.0, maxval=320.0)
        material_min = gcmd.get_float(
            "MATERIAL_MIN_C", minval=170.0, maxval=320.0
        )
        material_max = gcmd.get_float(
            "MATERIAL_MAX_C", minval=170.0, maxval=320.0
        )
        status = self._extruder_object.get_status(self.reactor.monotonic())
        if status.get("can_extrude") is not True:
            raise RuntimeGateError("extruder_not_ready")
        return {
            "owner": "k1_control",
            "expected_c": expected,
            "target_c": status.get("target"),
            "actual_c": status.get("temperature"),
            "material_min_c": material_min,
            "material_max_c": material_max,
            "cfs_temperature_command": False,
        }

    def _tip_pull(self, distance_mm: float, velocity_mm_s: float) -> bool:
        if abs(float(distance_mm) - (-20.0)) > 0.001:
            raise RuntimeGateError("tip_pull_distance_invalid")
        if abs(float(velocity_mm_s) - 140.0) > 0.001:
            raise RuntimeGateError("tip_pull_velocity_invalid")
        saved = False
        try:
            self.gcode.run_script_from_command(
                "SAVE_GCODE_STATE NAME=KCTRL_CFS_DIRECT_PULL"
            )
            saved = True
            self.gcode.run_script_from_command("M83")
            self.gcode.run_script_from_command("G1 E-20 F8400")
            self.gcode.run_script_from_command("M400")
        finally:
            if saved:
                self.gcode.run_script_from_command(
                    "RESTORE_GCODE_STATE NAME=KCTRL_CFS_DIRECT_PULL MOVE=0"
                )
        return True

    def _record_result(
        self,
        operation: str,
        effect_id: str,
        result: Dict[str, Any],
    ) -> None:
        self.last_operation = operation
        self.last_effect_id = effect_id
        self.last_result = dict(result)

    def _raise_result_failure(self) -> None:
        failure = self.last_result.get("failure_code")
        if failure is not None:
            raise RuntimeGateError(str(failure))

    def get_status(self, eventtime) -> Dict[str, Any]:
        result = self.last_result
        if self.owner is not None and not result:
            result = self.owner.result()
        phase = result.get("phase")
        if phase is None:
            phase = "idle" if self.enabled else "disabled"
        return {
            "owner": OWNER_NAME,
            "version": "install-disabled-v1",
            "enabled": self.enabled,
            "phase": phase,
            "active_route": result.get("active_route"),
            "failure_code": result.get("failure_code"),
            "transport_bound": self.transport_bound,
            "stock_commands_blocked": self.stock_commands_blocked,
            "stock_commands_replaced": list(self.stock_commands_replaced),
            "stock_commands_absent": list(self.stock_commands_absent),
            "stock_surface_present": list(self.stock_surface_present),
            "disabled_selftest_count": self.disabled_selftest_count,
            "preflight_count": self.preflight_count,
            "last_operation": self.last_operation,
            "last_effect_id": self.last_effect_id,
            "automatic_retry_count": result.get("automatic_retry_count", 0),
            "frames_sent_count": len(result.get("frames", [])),
            "tip_pull_count": result.get("tip_pull_count", 0),
            "load_count": result.get("load_count", 0),
            "load_tail_recovery_count": result.get(
                "load_tail_recovery_count", 0
            ),
            "takeover_finalize_count": result.get("takeover_finalize_count", 0),
            "last_buffer_state": result.get("last_buffer_state"),
            "unload_count": result.get("unload_count", 0),
            "retained_head_segment": result.get("retained_head_segment", False),
            "temperature_commands": list(result.get("temperature_commands", [])),
            "geometry_commands": list(result.get("geometry_commands", [])),
            "mesh_commands": list(result.get("mesh_commands", [])),
            "purge_commands": list(result.get("purge_commands", [])),
            "last_box_proof": dict(self.last_box_proof),
            "cfs_direct_owner": OWNER_NAME,
            "cfs_direct_owner_operation": self.last_operation,
            "cfs_direct_owner_phase": phase,
            "cfs_direct_owner_route": result.get("active_route"),
            "cfs_direct_owner_failure_code": result.get("failure_code"),
            "cfs_direct_owner_retained_head_segment": result.get(
                "retained_head_segment", False
            ),
            "cfs_direct_owner_retained_segment_recovery_id": (
                self.retained_segment_recovery_id
            ),
            "cfs_direct_owner_err8_load_tail_recovery_id": (
                self.err8_load_tail_recovery_id
            ),
            "cfs_direct_owner_takeover_finalize_recovery_id": (
                self.takeover_finalize_recovery_id
            ),
            "cfs_direct_owner_automatic_retry_count": result.get(
                "automatic_retry_count", 0
            ),
            "cfs_direct_owner_temperature_commands": list(
                result.get("temperature_commands", [])
            ),
            "cfs_direct_owner_geometry_commands": list(
                result.get("geometry_commands", [])
            ),
            "cfs_direct_owner_mesh_commands": list(
                result.get("mesh_commands", [])
            ),
            "cfs_direct_owner_purge_commands": list(
                result.get("purge_commands", [])
            ),
        }


def load_config(config):
    return K1ControlCfsDirectOwner(config)
