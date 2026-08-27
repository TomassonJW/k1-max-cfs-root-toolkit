#!/usr/bin/env python3
"""Fail-closed offline controller for the official Creality CFS unload.

The controller depends on a small injected API. This module contains no
network, SSH, serial, subprocess, or printer-specific transport.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Any, Dict, Mapping, Optional, Sequence


STOCK_UNLOAD_COMMAND = "BOX_QUIT_MATERIAL"
HEATER_SHUTDOWN_COMMAND = "TURN_OFF_HEATERS"
ROUTE_TOKEN = re.compile(r"^T[12][ABCD]$")
SAFE_PRINT_STATE = "standby"
CONNECTED_BOX_STATE = "connect"


class GuardInputError(ValueError):
    """Invalid caller input detected before any printer effect."""


@dataclass(frozen=True)
class GuardResult:
    verdict: str
    code: str
    expected_route: str
    primary_error: Optional[str]
    cleanup_error: Optional[str]
    stock_command_attempted: bool
    stock_command_acknowledged: bool
    stock_completion_observed: bool
    route_clear_observed: bool
    heater_shutdown_attempted: bool
    heater_shutdown_acknowledged: bool
    heater_shutdown_verified: bool
    stock_command_count: int
    heater_shutdown_count: int
    polls_used: int
    toolhead_filament_present_after: Optional[bool]
    operator_message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _finite_non_negative(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GuardInputError("%s must be a finite non-negative number" % field)
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise GuardInputError("%s must be a finite non-negative number" % field)
    return number


def _snapshot(raw: Mapping[str, Any]) -> Dict[str, Any]:
    required = {
        "print_state",
        "box_state",
        "connected_cfs_units",
        "active_cfs_command",
        "engaged_routes",
        "extruder_target_c",
        "bed_target_c",
        "toolhead_filament_present",
    }
    if not isinstance(raw, Mapping):
        raise GuardInputError("snapshot must be an object")
    missing = sorted(required.difference(raw))
    if missing:
        raise GuardInputError("snapshot missing: %s" % ", ".join(missing))
    units = raw["connected_cfs_units"]
    routes = raw["engaged_routes"]
    if not isinstance(units, Sequence) or isinstance(units, (str, bytes)):
        raise GuardInputError("connected_cfs_units must be a list")
    if not isinstance(routes, Sequence) or isinstance(routes, (str, bytes)):
        raise GuardInputError("engaged_routes must be a list")
    clean_units = [str(item) for item in units]
    clean_routes = [str(item) for item in routes]
    if len(set(clean_units)) != len(clean_units):
        raise GuardInputError("connected_cfs_units contains duplicates")
    if len(set(clean_routes)) != len(clean_routes):
        raise GuardInputError("engaged_routes contains duplicates")
    if any(not ROUTE_TOKEN.fullmatch(route) for route in clean_routes):
        raise GuardInputError("engaged_routes contains an invalid route")
    present = raw["toolhead_filament_present"]
    if present is not None and not isinstance(present, bool):
        raise GuardInputError("toolhead_filament_present must be boolean or null")
    return {
        "print_state": str(raw["print_state"]),
        "box_state": str(raw["box_state"]),
        "connected_cfs_units": clean_units,
        "active_cfs_command": str(raw["active_cfs_command"]),
        "engaged_routes": clean_routes,
        "extruder_target_c": _finite_non_negative(
            raw["extruder_target_c"], "extruder_target_c"
        ),
        "bed_target_c": _finite_non_negative(raw["bed_target_c"], "bed_target_c"),
        "toolhead_filament_present": present,
    }


class StockUnloadGuard:
    """Run the stock unload once and prove its postconditions."""

    def __init__(self, api: Any, *, max_polls: int = 8, cleanup_polls: int = 4):
        if (
            isinstance(max_polls, bool)
            or not isinstance(max_polls, int)
            or max_polls < 1
        ):
            raise GuardInputError("max_polls must be a positive integer")
        if (
            isinstance(cleanup_polls, bool)
            or not isinstance(cleanup_polls, int)
            or cleanup_polls < 1
        ):
            raise GuardInputError("cleanup_polls must be a positive integer")
        self.api = api
        self.max_polls = max_polls
        self.cleanup_polls = cleanup_polls

    @staticmethod
    def _preflight_error(
        state: Mapping[str, Any], expected_route: str
    ) -> Optional[str]:
        if state["print_state"] != SAFE_PRINT_STATE:
            return "printer_not_standby"
        if state["box_state"] != CONNECTED_BOX_STATE:
            return "cfs_not_connected"
        if set(state["connected_cfs_units"]) != {"T1", "T2"}:
            return "two_cfs_units_not_confirmed"
        if state["active_cfs_command"]:
            return "cfs_command_already_active"
        if state["engaged_routes"] != [expected_route]:
            return "expected_route_not_uniquely_engaged"
        return None

    def run(self, expected_route: str) -> GuardResult:
        if not isinstance(expected_route, str) or not ROUTE_TOKEN.fullmatch(
            expected_route
        ):
            raise GuardInputError("expected_route must match T1A..T2D")
        stock_attempted = stock_ack = stock_complete = route_clear = False
        cleanup_attempted = cleanup_ack = cleanup_verified = False
        stock_count = cleanup_count = 0
        primary_error: Optional[str] = None
        cleanup_error: Optional[str] = None
        polls_used = 0
        final_toolhead: Optional[bool] = None
        try:
            initial = _snapshot(self.api.snapshot())
        except Exception as exc:
            return self._result(
                expected_route,
                "preflight_snapshot_invalid:%s" % type(exc).__name__,
                None,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                0,
                None,
                stock_count,
                cleanup_count,
            )
        primary_error = self._preflight_error(initial, expected_route)
        if primary_error is not None:
            return self._result(
                expected_route,
                primary_error,
                None,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                0,
                initial["toolhead_filament_present"],
                stock_count,
                cleanup_count,
            )
        try:
            stock_attempted = True
            stock_count += 1
            stock_ack = self._acknowledged(self.api.run_gcode(STOCK_UNLOAD_COMMAND))
            for polls_used in range(1, self.max_polls + 1):
                state = _snapshot(self.api.snapshot())
                final_toolhead = state["toolhead_filament_present"]
                if state["print_state"] != SAFE_PRINT_STATE:
                    primary_error = "printer_left_standby"
                    break
                if state["box_state"] != CONNECTED_BOX_STATE:
                    primary_error = "cfs_disconnected_during_unload"
                    break
                if set(state["connected_cfs_units"]) != {"T1", "T2"}:
                    primary_error = "cfs_unit_lost_during_unload"
                    break
                if state["engaged_routes"] not in ([expected_route], []):
                    primary_error = "engaged_route_changed_unexpectedly"
                    break
                route_clear = state["engaged_routes"] == []
                command_clear = state["active_cfs_command"] == ""
                stock_complete = route_clear and command_clear
                if stock_complete and route_clear and command_clear:
                    break
            else:
                primary_error = "stock_unload_timeout"
            if primary_error is None and not (stock_complete and route_clear):
                primary_error = "stock_unload_effect_unproven"
        except Exception as exc:
            primary_error = "stock_unload_transport_error:%s" % type(exc).__name__
        finally:
            if stock_attempted:
                cleanup_attempted = True
                cleanup_count += 1
                try:
                    cleanup_ack = self._acknowledged(
                        self.api.run_gcode(HEATER_SHUTDOWN_COMMAND)
                    )
                    for _ in range(self.cleanup_polls):
                        state = _snapshot(self.api.snapshot())
                        final_toolhead = state["toolhead_filament_present"]
                        if (
                            state["extruder_target_c"] == 0
                            and state["bed_target_c"] == 0
                        ):
                            cleanup_verified = True
                            break
                    if not cleanup_verified:
                        cleanup_error = "heater_shutdown_effect_unproven"
                except Exception as exc:
                    cleanup_error = "heater_shutdown_error:%s" % type(exc).__name__
        return self._result(
            expected_route,
            primary_error,
            cleanup_error,
            stock_attempted,
            stock_ack,
            stock_complete,
            route_clear,
            cleanup_attempted,
            cleanup_ack,
            cleanup_verified,
            polls_used,
            final_toolhead,
            stock_count,
            cleanup_count,
        )

    @staticmethod
    def _acknowledged(value: Any) -> bool:
        return isinstance(value, Mapping) and value.get("result") == "ok"

    def _result(
        self,
        expected_route: str,
        primary_error: Optional[str],
        cleanup_error: Optional[str],
        stock_attempted: bool,
        stock_ack: bool,
        stock_complete: bool,
        route_clear: bool,
        cleanup_attempted: bool,
        cleanup_ack: bool,
        cleanup_verified: bool,
        polls_used: int,
        final_toolhead: Optional[bool],
        stock_count: int,
        cleanup_count: int,
    ) -> GuardResult:
        ok = (
            primary_error is None
            and cleanup_error is None
            and stock_attempted
            and stock_complete
            and route_clear
            and cleanup_verified
            and stock_count == 1
            and cleanup_count == 1
        )
        if ok:
            code = "stock_unload_guard_ok"
            message = (
                "Retrait CFS confirmé. Le segment situé après le cutter peut "
                "rester présent dans la tête. Chauffes vérifiées à zéro."
            )
        else:
            code = cleanup_error or primary_error or "guard_invariant_failed"
            if cleanup_error:
                message = (
                    "Retrait non validé et arrêt des chauffes non prouvé. "
                    "Ne pas relancer automatiquement ; vérifier la K1."
                )
            elif stock_attempted:
                message = (
                    "Retrait non validé. Aucun nouvel essai automatique. "
                    "Les chauffes ont été vérifiées à zéro."
                    if cleanup_verified
                    else "Retrait non validé. Vérification humaine requise."
                )
            else:
                message = "Retrait refusé avant toute commande : %s." % code
        return GuardResult(
            "OK" if ok else "KO",
            code,
            expected_route,
            primary_error,
            cleanup_error,
            stock_attempted,
            stock_ack,
            stock_complete,
            route_clear,
            cleanup_attempted,
            cleanup_ack,
            cleanup_verified,
            stock_count,
            cleanup_count,
            polls_used,
            final_toolhead,
            message,
        )
