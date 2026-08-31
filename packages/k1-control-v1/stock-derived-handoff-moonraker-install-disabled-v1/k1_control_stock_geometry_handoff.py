"""Handoff borné entre la géométrie R4 et le cycle stock-derived.

La configuration de cette gate garde ``enabled: false``. Le seul effet futur
consomme le token R4 après avoir prouvé que XYZ, le 11x11 et le Z canonique
sont prêts alors qu'aucun filament n'est encore engagé.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional


EFFECT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
PROFILE = "k1_p001_t055_r001_n11x11"
ACCEPTED_Z = -0.04


class HandoffError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class K1ControlStockGeometryHandoff:
    cmd_STATUS_help = "Etat du handoff R4 vers le cycle stock-derived"
    cmd_DISABLED_SELFTEST_help = "Prouve que le handoff installé reste inerte"
    cmd_TAKE_help = "Consomme une géométrie R4 exacte avant toute insertion"

    def __init__(self, config) -> None:
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.enabled = config.getboolean("enabled", False)
        self.last_effect_id: Optional[str] = None
        self.last_token: Optional[str] = None
        self.last_failure: Optional[str] = None
        self.claimed_effect_ids = set()
        self.command_journal = []
        self.handoff_count = 0
        self.disabled_selftest_count = 0
        self.gcode.register_command(
            "KCTRL_STOCK_GEOMETRY_HANDOFF_STATUS_V1",
            self.cmd_STATUS,
            desc=self.cmd_STATUS_help,
        )
        self.gcode.register_command(
            "KCTRL_STOCK_GEOMETRY_HANDOFF_DISABLED_SELFTEST_V1",
            self.cmd_DISABLED_SELFTEST,
            desc=self.cmd_DISABLED_SELFTEST_help,
        )
        self.gcode.register_command(
            "KCTRL_STOCK_GEOMETRY_HANDOFF_TAKE_V1",
            self.cmd_TAKE,
            desc=self.cmd_TAKE_help,
        )
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _handle_ready(self) -> None:
        logging.info(
            "K1 Control stock geometry handoff ready enabled=%s", self.enabled
        )

    def cmd_STATUS(self, gcmd) -> None:
        status = self.get_status(self.reactor.monotonic())
        gcmd.respond_info(
            "KCTRL_STOCK_GEOMETRY_HANDOFF_STATUS_V1 enabled=%d handoffs=%d token=%s failure=%s"
            % (
                1 if status["enabled"] else 0,
                status["handoff_count"],
                status["last_token"] or "none",
                status["last_failure"] or "none",
            )
        )

    def cmd_DISABLED_SELFTEST(self, gcmd) -> None:
        if self.enabled:
            raise gcmd.error(
                "K1 Control stock geometry: disabled_selftest_requires_disabled"
            )
        try:
            self._require_enabled()
        except HandoffError as error:
            if error.code != "stock_geometry_handoff_disabled":
                raise gcmd.error(
                    "K1 Control stock geometry: disabled_guard_invalid"
                )
        else:
            raise gcmd.error(
                "K1 Control stock geometry: disabled_guard_did_not_refuse"
            )
        if self.claimed_effect_ids or self.command_journal or self.handoff_count:
            raise gcmd.error(
                "K1 Control stock geometry: disabled_install_has_effect_history"
            )
        self.disabled_selftest_count += 1
        gcmd.respond_info(
            "KCTRL_STOCK_GEOMETRY_HANDOFF_DISABLED_SELFTEST_V1_OK refused=1"
        )

    def cmd_TAKE(self, gcmd) -> None:
        try:
            self._require_enabled()
            effect_id = str(gcmd.get("EFFECT_ID"))
            if not EFFECT_ID.fullmatch(effect_id):
                raise HandoffError("effect_id_invalid")
            self._require_context()
            self._claim(effect_id)
            self._run_many(
                [
                    "UPDATE_DELAYED_GCODE ID=KCTRL_START_WATCHDOG_V1 DURATION=0",
                    "SET_GCODE_VARIABLE MACRO=KCTRL_START_OWNER_STATE VARIABLE=geometry_ready_token VALUE=0",
                    "SET_GCODE_VARIABLE MACRO=KCTRL_START_OWNER_STATE VARIABLE=geometry_ready_deadline VALUE=0.0",
                    "SET_GCODE_VARIABLE MACRO=KCTRL_START_OWNER_STATE VARIABLE=watchdog_armed VALUE=0",
                    "SET_GCODE_VARIABLE MACRO=KCTRL_START_OWNER_STATE VARIABLE=watchdog_deadline VALUE=0.0",
                    "SET_GCODE_VARIABLE MACRO=KCTRL_START_OWNER_STATE VARIABLE=phase VALUE='\"geometry_handed_to_stock_cycle\"'",
                ]
            )
            self.last_effect_id = effect_id
            self.last_token = "geometry_ready_for_stock_cycle"
            self.last_failure = None
            self.handoff_count += 1
        except HandoffError as error:
            self.last_failure = error.code
            raise gcmd.error("K1 Control stock geometry: %s" % error.code)
        gcmd.respond_info(
            "KCTRL_STOCK_GEOMETRY_HANDOFF_TAKE_V1_OK token=geometry_ready_for_stock_cycle"
        )

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise HandoffError("stock_geometry_handoff_disabled")

    def _lookup_status(self, name: str) -> Dict[str, Any]:
        obj = self.printer.lookup_object(name, None)
        if obj is None:
            raise HandoffError("runtime_dependency_missing")
        status = obj.get_status(self.reactor.monotonic())
        if not isinstance(status, dict):
            raise HandoffError("runtime_status_invalid")
        return status

    def _require_context(self) -> None:
        owner = self._lookup_status("gcode_macro KCTRL_START_OWNER_STATE")
        runtime = self._lookup_status("gcode_macro KCTRL_STATE")
        box = self._lookup_status("box")
        toolhead = self._lookup_status("toolhead")
        mesh = self._lookup_status("bed_mesh")
        move = self._lookup_status("gcode_move")
        if (
            owner.get("phase") != "geometry_ready_for_insertion"
            or owner.get("geometry_ready_token") != 1
            or owner.get("watchdog_armed") != 1
        ):
            raise HandoffError("R4_geometry_token_missing")
        expected = {
            "job_bed": 55.0,
            "job_probe_nozzle": 140.0,
            "job_first_nozzle": 190.0,
            "job_plate": 1,
            "job_probe_rev": 1,
            "job_nozzle_id": 1,
            "job_config_id": 1,
            "job_x_count": 11,
            "job_y_count": 11,
        }
        for field, value in expected.items():
            if owner.get(field) != value:
                raise HandoffError("R4_geometry_context_changed")
        if runtime.get("accepted_z_valid") != 1 or runtime.get("low_moves_armed") != 1:
            raise HandoffError("accepted_geometry_not_armed")
        if toolhead.get("homed_axes") != "xyz":
            raise HandoffError("XYZ_reference_missing")
        if mesh.get("profile_name") != PROFILE:
            raise HandoffError("mesh_profile_changed")
        origin = move.get("homing_origin")
        try:
            origin_z = float(origin[2])
            accepted_z = float(runtime.get("accepted_z_offset"))
        except (TypeError, ValueError, IndexError):
            raise HandoffError("accepted_Z_status_invalid")
        if abs(origin_z - ACCEPTED_Z) > 0.0005 or abs(accepted_z - ACCEPTED_Z) > 0.0005:
            raise HandoffError("accepted_Z_changed")
        units = []
        for name in ("T1", "T2"):
            unit = box.get(name)
            if not isinstance(unit, dict) or unit.get("state") != "connect":
                raise HandoffError("CFS_unit_not_ready")
            units.append(unit.get("filament"))
        if (
            box.get("t_command") != ""
            or box.get("auto_refill") not in (0, False)
            or any(value not in (None, "None", "none", "") for value in units)
        ):
            raise HandoffError("filament_or_stock_owner_present_before_handoff")

    def _claim(self, effect_id: str) -> None:
        if effect_id in self.claimed_effect_ids:
            raise HandoffError("effect_id_already_claimed_no_retry")
        self.claimed_effect_ids.add(effect_id)

    def _run_many(self, commands) -> None:
        for command in commands:
            try:
                self.gcode.run_script_from_command(command)
            except Exception:
                logging.exception(
                    "K1 Control stock geometry handoff command failed after claim"
                )
                raise HandoffError("command_failed_uncertain_no_retry")
            self.command_journal.append(command)

    def get_status(self, eventtime) -> Dict[str, Any]:
        return {
            "owner": "k1_control_stock_geometry_handoff",
            "version": "install-disabled-v1",
            "enabled": self.enabled,
            "handoff_count": self.handoff_count,
            "disabled_selftest_count": self.disabled_selftest_count,
            "last_effect_id": self.last_effect_id,
            "last_token": self.last_token,
            "last_failure": self.last_failure,
            "claimed_effect_count": len(self.claimed_effect_ids),
            "command_count": len(self.command_journal),
            "automatic_retry_count": 0,
            "heat_command_count": 0,
            "motion_command_count": 0,
            "probe_command_count": 0,
            "mesh_recalculation_count": 0,
            "cfs_frame_count": 0,
        }


def load_config(config):
    return K1ControlStockGeometryHandoff(config)
