"""Primitives Klipper du cycle CFS dérivé de la séquence Creality observée.

La configuration de cette gate fixe ``enabled: false``. Dans cet état, aucune
commande d'effet ne lit ses paramètres, ne chauffe, ne déplace la tête et
n'appelle le propriétaire CFS direct. Le code actif est préparé pour une gate
ultérieure distincte ; son installation désactivée ne l'autorise pas.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional


ROUTE = re.compile(r"^T[12][ABCD]$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
OWNER_NAME = "k1_control_stock_derived_cycle"

EFFECT_COMMANDS = (
    "cut_unload",
    "load_purge",
    "prime",
    "refill_guard",
    "end",
)


class RuntimeGateError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _route(value: Any, code: str) -> str:
    result = str(value)
    if not ROUTE.fullmatch(result):
        raise RuntimeGateError(code)
    return result


def _safe_id(value: Any, code: str) -> str:
    result = str(value)
    if not SAFE_ID.fullmatch(result):
        raise RuntimeGateError(code)
    return result


class K1ControlStockCycleOwner:
    cmd_STATUS_help = "Etat du cycle CFS dérivé de la séquence stock"
    cmd_DISABLED_SELFTEST_help = "Prouve que la pose désactivée refuse tout effet"
    cmd_CUT_UNLOAD_help = "Coupe au cutter puis retire une route par le propriétaire direct"
    cmd_LOAD_PURGE_help = "Charge au bac, purge et décroche la boule"
    cmd_PRIME_help = "Trace la ligne stock exacte puis abaisse le plateau de 5 mm"
    cmd_REFILL_GUARD_help = "Valide un remplacement par une unique bobine strictement identique"
    cmd_END_help = "Termine sans palpage, coupe, retire, gare, refroidit et libère"

    def __init__(self, config) -> None:
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.enabled = config.getboolean("enabled", False)
        self.direct_owner_name = config.get(
            "direct_owner", "k1_control_cfs_direct_owner"
        )
        self.box_name = config.get("box", "box")
        self.toolhead_name = config.get("toolhead", "toolhead")
        self.last_operation: Optional[str] = None
        self.last_effect_id: Optional[str] = None
        self.last_route: Optional[str] = None
        self.last_failure: Optional[str] = None
        self.effect_count = 0
        self.disabled_selftest_count = 0
        self.command_journal: List[str] = []
        self.claimed_effect_ids = set()

        self._register("KCTRL_STOCK_CYCLE_STATUS_V1", self.cmd_STATUS, self.cmd_STATUS_help)
        self._register(
            "KCTRL_STOCK_CYCLE_DISABLED_SELFTEST_V1",
            self.cmd_DISABLED_SELFTEST,
            self.cmd_DISABLED_SELFTEST_help,
        )
        self._register(
            "KCTRL_STOCK_CYCLE_CUT_UNLOAD_V1",
            self.cmd_CUT_UNLOAD,
            self.cmd_CUT_UNLOAD_help,
        )
        self._register(
            "KCTRL_STOCK_CYCLE_LOAD_PURGE_V1",
            self.cmd_LOAD_PURGE,
            self.cmd_LOAD_PURGE_help,
        )
        self._register("KCTRL_STOCK_CYCLE_PRIME_V1", self.cmd_PRIME, self.cmd_PRIME_help)
        self._register(
            "KCTRL_STOCK_CYCLE_REFILL_GUARD_V1",
            self.cmd_REFILL_GUARD,
            self.cmd_REFILL_GUARD_help,
        )
        self._register("KCTRL_STOCK_CYCLE_END_V1", self.cmd_END, self.cmd_END_help)
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _register(self, name: str, handler, description: str) -> None:
        self.gcode.register_command(name, handler, desc=description)

    def _handle_ready(self) -> None:
        logging.info(
            "K1 Control stock-derived cycle ready enabled=%s", self.enabled
        )

    def cmd_STATUS(self, gcmd) -> None:
        status = self.get_status(self.reactor.monotonic())
        gcmd.respond_info(
            "KCTRL_STOCK_CYCLE_STATUS_V1 enabled=%d effects=%d last=%s failure=%s"
            % (
                1 if status["enabled"] else 0,
                status["effect_count"],
                status["last_operation"] or "none",
                status["last_failure"] or "none",
            )
        )

    def cmd_DISABLED_SELFTEST(self, gcmd) -> None:
        if self.enabled:
            raise gcmd.error(
                "K1 Control stock cycle: disabled_selftest_requires_disabled_owner"
            )
        refused = 0
        for _name in EFFECT_COMMANDS:
            try:
                self._require_enabled()
            except RuntimeGateError as error:
                if error.code != "stock_derived_cycle_disabled":
                    raise gcmd.error(
                        "K1 Control stock cycle: disabled_guard_invalid"
                    )
                refused += 1
        if refused != len(EFFECT_COMMANDS):
            raise gcmd.error(
                "K1 Control stock cycle: disabled_guard_count_invalid"
            )
        if self.effect_count != 0 or self.command_journal or self.claimed_effect_ids:
            raise gcmd.error(
                "K1 Control stock cycle: disabled_install_has_effect_history"
            )
        self.disabled_selftest_count += 1
        gcmd.respond_info(
            "KCTRL_STOCK_CYCLE_DISABLED_SELFTEST_V1_OK refused=%d" % refused
        )

    def cmd_CUT_UNLOAD(self, gcmd) -> None:
        try:
            self._require_enabled()
            route = _route(gcmd.get("ROUTE"), "unload_route_invalid")
            effect_id = _safe_id(gcmd.get("EFFECT_ID"), "effect_id_invalid")
            unload_c, material_min, material_max = self._temperatures(
                gcmd, "UNLOAD_C"
            )
            self._prepare_effect()
            self._claim_effect(effect_id)
            self._cut_and_unload(
                route, effect_id, unload_c, material_min, material_max
            )
            self._complete("cut_unload", effect_id, None)
        except RuntimeGateError as error:
            self._fail(gcmd, error)
        gcmd.respond_info("KCTRL_STOCK_CYCLE_CUT_UNLOAD_V1_OK route=%s" % route)

    def cmd_LOAD_PURGE(self, gcmd) -> None:
        try:
            self._require_enabled()
            route = _route(gcmd.get("ROUTE"), "load_route_invalid")
            effect_id = _safe_id(gcmd.get("EFFECT_ID"), "effect_id_invalid")
            load_c, material_min, material_max = self._temperatures(gcmd, "LOAD_C")
            purge_c = gcmd.get_float("PURGE_C", minval=150.0, maxval=320.0)
            # 140 mm est la purge initiale stock observee. Les transitions
            # couleur Orca peuvent depasser 300 mm ; elles restent bornees.
            purge_mm = gcmd.get_float("PURGE_MM", minval=0.1, maxval=400.0)
            trips = gcmd.get_int("TRIPS", minval=3, maxval=4)
            if not material_min <= purge_c <= material_max:
                raise RuntimeGateError("purge_temperature_out_of_bounds")
            self._prepare_effect()
            self._claim_effect(effect_id)
            self._load_and_purge(
                route,
                effect_id,
                load_c,
                purge_c,
                purge_mm,
                trips,
                material_min,
                material_max,
            )
            self._complete("load_purge", effect_id, route)
        except RuntimeGateError as error:
            self._fail(gcmd, error)
        gcmd.respond_info(
            "KCTRL_STOCK_CYCLE_LOAD_PURGE_V1_OK route=%s trips=%d"
            % (route, trips)
        )

    def cmd_PRIME(self, gcmd) -> None:
        try:
            self._require_enabled()
            effect_id = _safe_id(gcmd.get("EFFECT_ID"), "effect_id_invalid")
            first_c = gcmd.get_float("FIRST_C", minval=150.0, maxval=320.0)
            self._prepare_effect()
            self._claim_effect(effect_id)
            self._heat_nozzle(first_c)
            self._run_many(
                [
                    "SAVE_GCODE_STATE NAME=KCTRL_STOCK_PRIME",
                    "G90",
                    "M83",
                    "G1 X0.1 Y20 Z0.3 F6000",
                    "G1 X0.1 Y180 Z0.3 F3000 E10",
                    "G1 X0.4 Y180 Z0.3 F3000",
                    "G1 X0.4 Y20 Z0.3 F3000 E10",
                    "G1 Y10 F3000",
                    "G91",
                    "G1 Z5 F1200",
                    "G90",
                    "M400",
                    "RESTORE_GCODE_STATE NAME=KCTRL_STOCK_PRIME MOVE=0",
                ]
            )
            self._complete("prime", effect_id, self.last_route)
        except RuntimeGateError as error:
            self._fail(gcmd, error)
        gcmd.respond_info("KCTRL_STOCK_CYCLE_PRIME_V1_OK")

    def cmd_REFILL_GUARD(self, gcmd) -> None:
        try:
            self._require_enabled()
            source = _route(gcmd.get("FROM"), "refill_source_route_invalid")
            target = _route(gcmd.get("TO"), "refill_target_route_invalid")
            source_hash = _safe_id(
                gcmd.get("SOURCE_IDENTITY"), "refill_source_identity_invalid"
            )
            target_hash = _safe_id(
                gcmd.get("TARGET_IDENTITY"), "refill_target_identity_invalid"
            )
            candidates = gcmd.get_int("CANDIDATES", minval=0, maxval=8)
            paused = gcmd.get_int("PAUSE_LATCHED", minval=0, maxval=1)
            if source == target:
                raise RuntimeGateError("refill_target_same_as_source")
            if candidates != 1:
                raise RuntimeGateError("refill_candidate_not_unique")
            if source_hash != target_hash:
                raise RuntimeGateError("refill_material_not_identical")
            if paused != 1:
                raise RuntimeGateError("refill_pause_not_latched")
            self._prepare_effect()
            self.last_operation = "refill_guard"
            self.last_route = source
        except RuntimeGateError as error:
            self._fail(gcmd, error)
        gcmd.respond_info(
            "KCTRL_STOCK_CYCLE_REFILL_GUARD_V1_OK from=%s to=%s" % (source, target)
        )

    def cmd_END(self, gcmd) -> None:
        try:
            self._require_enabled()
            route = _route(gcmd.get("ROUTE"), "end_route_invalid")
            effect_id = _safe_id(gcmd.get("EFFECT_ID"), "effect_id_invalid")
            unload_c, material_min, material_max = self._temperatures(
                gcmd, "UNLOAD_C"
            )
            self._prepare_effect()
            self._claim_effect(effect_id)
            self._run_many(
                [
                    "SAVE_GCODE_STATE NAME=KCTRL_STOCK_END",
                    "G91",
                    "G1 Z5 F1200",
                    "G90",
                ]
            )
            self._cut_and_unload(
                route, effect_id, unload_c, material_min, material_max
            )
            self._run_many(
                [
                    "G90",
                    "G1 X203 Y273 F1200",
                    "M400",
                    "RESTORE_GCODE_STATE NAME=KCTRL_STOCK_END MOVE=0",
                    "TURN_OFF_HEATERS",
                    "M107 P1",
                    "M107 P2",
                    "M84",
                ]
            )
            self._complete("end", effect_id, None)
        except RuntimeGateError as error:
            self._fail(gcmd, error)
        gcmd.respond_info("KCTRL_STOCK_CYCLE_END_V1_OK")

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise RuntimeGateError("stock_derived_cycle_disabled")

    def _prepare_effect(self) -> None:
        self._require_enabled()
        toolhead = self.printer.lookup_object(self.toolhead_name, None)
        box = self.printer.lookup_object(self.box_name, None)
        direct = self.printer.lookup_object(self.direct_owner_name, None)
        if toolhead is None or box is None or direct is None:
            raise RuntimeGateError("runtime_dependency_missing")
        toolhead_status = toolhead.get_status(self.reactor.monotonic())
        if toolhead_status.get("homed_axes") != "xyz":
            raise RuntimeGateError("XYZ_reference_missing")
        box_status = box.get_status(self.reactor.monotonic())
        if box_status.get("auto_refill") not in (0, False):
            raise RuntimeGateError("stock_auto_refill_not_disabled")
        if box_status.get("t_command") != "":
            raise RuntimeGateError("stock_command_active")
        direct_status = direct.get_status(self.reactor.monotonic())
        if direct_status.get("enabled") is not True:
            raise RuntimeGateError("direct_owner_not_enabled")
        if direct_status.get("stock_commands_blocked") is not True:
            raise RuntimeGateError("stock_effect_commands_not_blocked")
        if direct_status.get("failure_code") is not None:
            raise RuntimeGateError("direct_owner_failure_present")

    def _claim_effect(self, effect_id: str) -> None:
        if effect_id in self.claimed_effect_ids:
            raise RuntimeGateError("effect_id_already_claimed_no_retry")
        self.claimed_effect_ids.add(effect_id)

    def _temperatures(self, gcmd, target_name: str):
        target = gcmd.get_float(target_name, minval=150.0, maxval=320.0)
        material_min = gcmd.get_float("MATERIAL_MIN_C", minval=150.0, maxval=320.0)
        material_max = gcmd.get_float("MATERIAL_MAX_C", minval=150.0, maxval=320.0)
        if material_min > material_max or not material_min <= target <= material_max:
            raise RuntimeGateError("material_temperature_bounds_invalid")
        return target, material_min, material_max

    def _heat_nozzle(self, target: float) -> None:
        self._run_many(["M104 S%.3f" % target, "M109 S%.3f" % target])

    def _cut_and_unload(
        self,
        route: str,
        effect_id: str,
        unload_c: float,
        material_min: float,
        material_max: float,
    ) -> None:
        self._heat_nozzle(unload_c)
        saved = False
        try:
            self._run_many(["SAVE_GCODE_STATE NAME=KCTRL_STOCK_CUT"])
            saved = True
            self._run_many(
                [
                    "G90",
                    "G1 X38 Y230 F7000",
                    "G1 X38 Y304.5 F7000",
                    "M400",
                    "G4 P1500",
                ]
            )
            self._require_cut_sensor(True)
            # La trace stock garde la tete a la butee pendant tout le retrait.
            # Quitter Y304.5 avant cette commande casse la preuve de coupe.
            self._run_many(
                [
                    (
                        "KCTRL_CFS_DIRECT_UNLOAD ROUTE=%s EFFECT_ID=%s "
                        "EXPECTED_C=%.3f MATERIAL_MIN_C=%.3f MATERIAL_MAX_C=%.3f"
                        % (route, effect_id, unload_c, material_min, material_max)
                    )
                ]
            )
        finally:
            if saved:
                self._run_many(
                    [
                        "G90",
                        "G1 X38 Y230 F7000",
                        "M400",
                        "G4 P1000",
                        "RESTORE_GCODE_STATE NAME=KCTRL_STOCK_CUT MOVE=0",
                    ]
                )
                self._require_cut_sensor(False)

    def _require_cut_sensor(self, expected: bool) -> None:
        box = self.printer.lookup_object(self.box_name, None)
        if box is None:
            raise RuntimeGateError("cutter_sensor_owner_missing")
        value = box.get_status(self.reactor.monotonic()).get("cut_pos")
        try:
            active = abs(float(value) - 1.0) <= 0.001
            inactive = abs(float(value)) <= 0.001
        except (TypeError, ValueError):
            raise RuntimeGateError("cutter_sensor_status_invalid")
        if not (active if expected else inactive):
            raise RuntimeGateError(
                "cutter_sensor_not_triggered"
                if expected
                else "cutter_sensor_not_released"
            )

    def _load_and_purge(
        self,
        route: str,
        effect_id: str,
        load_c: float,
        purge_c: float,
        purge_mm: float,
        trips: int,
        material_min: float,
        material_max: float,
    ) -> None:
        self._heat_nozzle(load_c)
        self._run_many(
            [
                "SAVE_GCODE_STATE NAME=KCTRL_STOCK_LOAD_PURGE",
                "G90",
                "M83",
                "G1 Z32 F600",
                "G1 X185.5 Y305 F1200",
                "G1 Z30 F600",
                (
                    "KCTRL_CFS_DIRECT_LOAD ROUTE=%s EFFECT_ID=%s "
                    "EXPECTED_C=%.3f MATERIAL_MIN_C=%.3f MATERIAL_MAX_C=%.3f"
                    % (route, effect_id, load_c, material_min, material_max)
                ),
            ]
        )
        if abs(load_c - purge_c) > 0.001:
            self._heat_nozzle(purge_c)
        self._run_many(
            [
                "G1 E%.3f F360" % purge_mm,
                "G1 E-1.2 F1800",
                "G1 Z32 F600",
                "G1 X203 Y273 F1200",
            ]
        )
        for index in range(trips):
            lane = 305 if index % 2 == 0 else 304
            self._run_many(
                [
                    "G1 Y%d F600" % lane,
                    "G1 X206 F180",
                    "G1 X203 F180",
                ]
            )
        self._run_many(
            [
                "G1 X203 Y273 F1200",
                "M400",
                "RESTORE_GCODE_STATE NAME=KCTRL_STOCK_LOAD_PURGE MOVE=0",
            ]
        )

    def _run_many(self, commands: List[str]) -> None:
        for command in commands:
            try:
                self.gcode.run_script_from_command(command)
            except Exception:
                logging.exception(
                    "K1 Control stock-derived command failed after ticket claim"
                )
                raise RuntimeGateError("command_failed_uncertain_no_retry")
            self.command_journal.append(command)

    def _complete(
        self, operation: str, effect_id: str, route: Optional[str]
    ) -> None:
        self.last_operation = operation
        self.last_effect_id = effect_id
        self.last_route = route
        self.last_failure = None
        self.effect_count += 1

    def _fail(self, gcmd, error: RuntimeGateError) -> None:
        self.last_failure = error.code
        raise gcmd.error("K1 Control stock cycle: %s" % error.code)

    def get_status(self, eventtime) -> Dict[str, Any]:
        return {
            "owner": OWNER_NAME,
            "version": "install-disabled-v1",
            "enabled": self.enabled,
            "effect_count": self.effect_count,
            "disabled_selftest_count": self.disabled_selftest_count,
            "last_operation": self.last_operation,
            "last_effect_id": self.last_effect_id,
            "last_route": self.last_route,
            "last_failure": self.last_failure,
            "automatic_retry_count": 0,
            "stock_BOX_effect_count": 0,
            "probe_command_count": 0,
            "mesh_recalculation_count": 0,
            "command_count": len(self.command_journal),
            "claimed_effect_count": len(self.claimed_effect_ids),
        }


def load_config(config):
    return K1ControlStockCycleOwner(config)
