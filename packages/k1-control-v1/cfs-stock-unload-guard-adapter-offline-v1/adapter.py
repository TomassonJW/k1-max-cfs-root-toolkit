#!/usr/bin/env python3
"""Translate a redacted K1 object query into the stock-unload guard format.

This module is deliberately pure: it has no network, printer, process or G-code
surface. Unknown input fields are ignored and never copied to the result.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Mapping


UNIT_NAMES = ("T1", "T2", "T3", "T4")
SUPPORTED_CONNECTED_UNITS = {"T1", "T2"}
UNIT_STATES = {"connect", "disconnect", "None"}
FILAMENT_SLOTS = {"A", "B", "C", "D"}
NO_FILAMENT = "None"


class AdapterInputError(ValueError):
    """A redacted query is incomplete, ambiguous or unsafe to translate."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AdapterInputError("object_required:%s" % path)
    return value


def _field(value: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in value:
        raise AdapterInputError("field_missing:%s.%s" % (path, key))
    return value[key]


def _child(value: Mapping[str, Any], key: str, path: str) -> Mapping[str, Any]:
    return _mapping(_field(value, key, path), "%s.%s" % (path, key))


def _text(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise AdapterInputError("text_invalid:%s" % path)
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise AdapterInputError("boolean_invalid:%s" % path)
    return value


def _temperature(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AdapterInputError("temperature_invalid:%s" % path)
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise AdapterInputError("temperature_invalid:%s" % path)
    return number


def adapt_query_response(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Return only the eight fields consumed by the offline unload guard."""

    root = _mapping(payload, "payload")
    result = _child(root, "result", "payload")
    status = _child(result, "status", "payload.result")
    print_stats = _child(status, "print_stats", "payload.result.status")
    extruder = _child(status, "extruder", "payload.result.status")
    heater_bed = _child(status, "heater_bed", "payload.result.status")
    box = _child(status, "box", "payload.result.status")
    sensor = _child(
        status,
        "filament_switch_sensor filament_sensor",
        "payload.result.status",
    )

    connected_units = []
    engaged_routes = []
    for unit_name in UNIT_NAMES:
        unit_path = "payload.result.status.box.%s" % unit_name
        unit = _child(box, unit_name, "payload.result.status.box")
        unit_state = _text(_field(unit, "state", unit_path), "%s.state" % unit_path)
        filament = _text(
            _field(unit, "filament", unit_path), "%s.filament" % unit_path
        )
        if unit_state not in UNIT_STATES:
            raise AdapterInputError("unit_state_invalid:%s" % unit_name)
        if unit_state == NO_FILAMENT and unit_name in SUPPORTED_CONNECTED_UNITS:
            raise AdapterInputError("unit_state_invalid:%s" % unit_name)
        if filament not in FILAMENT_SLOTS and filament != NO_FILAMENT:
            raise AdapterInputError("filament_value_invalid:%s" % unit_name)
        if unit_state == "connect":
            if unit_name not in SUPPORTED_CONNECTED_UNITS:
                raise AdapterInputError("connected_unit_unsupported:%s" % unit_name)
            connected_units.append(unit_name)
            if filament in FILAMENT_SLOTS:
                engaged_routes.append(unit_name + filament)
        elif filament != NO_FILAMENT:
            raise AdapterInputError(
                "filament_on_disconnected_unit:%s" % unit_name
            )

    if len(engaged_routes) > 1:
        raise AdapterInputError("engaged_routes_ambiguous")

    sensor_enabled = _boolean(
        _field(sensor, "enabled", "payload.result.status.filament_sensor"),
        "payload.result.status.filament_sensor.enabled",
    )
    sensor_detected = _boolean(
        _field(
            sensor,
            "filament_detected",
            "payload.result.status.filament_sensor",
        ),
        "payload.result.status.filament_sensor.filament_detected",
    )

    return {
        "print_state": _text(
            _field(print_stats, "state", "payload.result.status.print_stats"),
            "payload.result.status.print_stats.state",
        ),
        "box_state": _text(
            _field(box, "state", "payload.result.status.box"),
            "payload.result.status.box.state",
        ),
        "connected_cfs_units": connected_units,
        "active_cfs_command": _text(
            _field(box, "t_command", "payload.result.status.box"),
            "payload.result.status.box.t_command",
            allow_empty=True,
        ),
        "engaged_routes": engaged_routes,
        "extruder_target_c": _temperature(
            _field(extruder, "target", "payload.result.status.extruder"),
            "payload.result.status.extruder.target",
        ),
        "bed_target_c": _temperature(
            _field(heater_bed, "target", "payload.result.status.heater_bed"),
            "payload.result.status.heater_bed.target",
        ),
        "toolhead_filament_present": sensor_detected if sensor_enabled else None,
    }
