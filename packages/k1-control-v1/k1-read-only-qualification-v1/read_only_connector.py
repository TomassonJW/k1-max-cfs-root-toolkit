#!/usr/bin/env python3
"""Translate a sanitized live K1 observation without exposing an effect path.

The live PowerShell collector owns the HTTP GET calls.  This module only
validates their already-redacted result and projects it to the fields needed by
the offline lifecycle contract.  It deliberately has no socket, process,
filesystem, G-code or service-control API.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, Mapping, Sequence


ROBUST_PROFILE = "k1_p001_t055_r001_n06x06"
UNIT_NAMES = ("T1", "T2", "T3", "T4")
CONNECTED_UNITS = ("T1", "T2")
SLOTS = {"A", "B", "C", "D"}
NO_FILAMENT = "None"


class ReadOnlyInputError(ValueError):
    """The sanitized observation is incomplete, ambiguous or inconsistent."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReadOnlyInputError("object_required:%s" % path)
    return value


def _exact_keys(value: Mapping[str, Any], expected: Sequence[str], path: str) -> None:
    actual = set(value)
    wanted = set(expected)
    if actual != wanted:
        raise ReadOnlyInputError(
            "schema_drift:%s:missing=%s:extra=%s"
            % (path, sorted(wanted - actual), sorted(actual - wanted))
        )


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReadOnlyInputError("number_invalid:%s" % path)
    number = float(value)
    if not math.isfinite(number):
        raise ReadOnlyInputError("number_invalid:%s" % path)
    return number


def _integer_flag(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1):
        raise ReadOnlyInputError("flag_invalid:%s" % path)
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ReadOnlyInputError("boolean_invalid:%s" % path)
    return value


def _text(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ReadOnlyInputError("text_invalid:%s" % path)
    return value


def _matrix_summary(value: Any, path: str) -> Mapping[str, Any]:
    summary = _mapping(value, path)
    _exact_keys(summary, ("rows", "columns", "sha256"), path)
    rows = summary["rows"]
    columns = summary["columns"]
    digest = summary["sha256"]
    if isinstance(rows, bool) or not isinstance(rows, int) or rows < 0:
        raise ReadOnlyInputError("matrix_rows_invalid:%s" % path)
    if not isinstance(columns, list) or len(columns) != rows:
        raise ReadOnlyInputError("matrix_columns_invalid:%s" % path)
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in columns):
        raise ReadOnlyInputError("matrix_columns_invalid:%s" % path)
    if rows == 0:
        if digest is not None:
            raise ReadOnlyInputError("matrix_hash_invalid:%s" % path)
    elif not isinstance(digest, str) or len(digest) != 64:
        raise ReadOnlyInputError("matrix_hash_invalid:%s" % path)
    return summary


def mapping_fingerprint(snapshot: Mapping[str, Any]) -> str:
    """Fingerprint only observable connection and route fields."""

    box = _mapping(snapshot.get("box"), "snapshot.box")
    payload: Dict[str, Any] = {
        "state": box.get("state"),
        "units": {},
    }
    for unit_name in UNIT_NAMES:
        unit = _mapping(box.get(unit_name), "snapshot.box.%s" % unit_name)
        payload["units"][unit_name] = {
            "state": unit.get("state"),
            "filament": unit.get("filament"),
        }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def mapping_cache_valid(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
    *,
    connection_epoch_changed: bool,
) -> bool:
    """A reconnect event or any observable mapping change invalidates the cache.

    Polling cannot prove that a very short disconnect/reconnect did not happen
    between two identical snapshots.  Future Moonraker wiring must therefore
    supply an explicit connection epoch from notifications.
    """

    if connection_epoch_changed:
        return False
    return mapping_fingerprint(previous) == mapping_fingerprint(current)


def control_projection(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """Remove values allowed to drift naturally between two safe reads."""

    projected = json.loads(json.dumps(snapshot))
    projected.pop("eventtime", None)
    projected["extruder"].pop("temperature", None)
    projected["heater_bed"].pop("temperature", None)
    return projected


def adapt_snapshot(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate one safe live snapshot and expose conservative lifecycle facts."""

    root = _mapping(snapshot, "snapshot")
    _exact_keys(
        root,
        (
            "eventtime",
            "print_stats",
            "extruder",
            "heater_bed",
            "toolhead",
            "bed_mesh",
            "box",
            "sensors",
            "gcode_move",
            "runtime",
            "store",
            "calibration_path",
        ),
        "snapshot",
    )
    _number(root["eventtime"], "snapshot.eventtime")

    print_stats = _mapping(root["print_stats"], "snapshot.print_stats")
    _exact_keys(print_stats, ("state", "filename_present"), "snapshot.print_stats")
    print_state = _text(print_stats["state"], "snapshot.print_stats.state")
    filename_present = _boolean(
        print_stats["filename_present"], "snapshot.print_stats.filename_present"
    )

    extruder = _mapping(root["extruder"], "snapshot.extruder")
    _exact_keys(
        extruder, ("temperature", "target", "can_extrude"), "snapshot.extruder"
    )
    extruder_target = _number(extruder["target"], "snapshot.extruder.target")
    _number(extruder["temperature"], "snapshot.extruder.temperature")
    can_extrude = _boolean(extruder["can_extrude"], "snapshot.extruder.can_extrude")

    bed = _mapping(root["heater_bed"], "snapshot.heater_bed")
    _exact_keys(bed, ("temperature", "target"), "snapshot.heater_bed")
    bed_target = _number(bed["target"], "snapshot.heater_bed.target")
    _number(bed["temperature"], "snapshot.heater_bed.temperature")

    box = _mapping(root["box"], "snapshot.box")
    _exact_keys(box, ("state", "t_command") + UNIT_NAMES, "snapshot.box")
    box_state = _text(box["state"], "snapshot.box.state")
    active_command = _text(
        box["t_command"], "snapshot.box.t_command", allow_empty=True
    )
    connected_units = []
    engaged_routes = []
    for unit_name in UNIT_NAMES:
        unit = _mapping(box[unit_name], "snapshot.box.%s" % unit_name)
        _exact_keys(unit, ("state", "filament"), "snapshot.box.%s" % unit_name)
        state = _text(unit["state"], "snapshot.box.%s.state" % unit_name)
        filament = _text(unit["filament"], "snapshot.box.%s.filament" % unit_name)
        if state not in {"connect", "disconnect", "None"}:
            raise ReadOnlyInputError("unit_state_invalid:%s" % unit_name)
        if filament not in SLOTS and filament != NO_FILAMENT:
            raise ReadOnlyInputError("unit_filament_invalid:%s" % unit_name)
        if state == "connect":
            connected_units.append(unit_name)
            if filament in SLOTS:
                engaged_routes.append(unit_name + filament)
        elif filament != NO_FILAMENT:
            raise ReadOnlyInputError("filament_on_inactive_unit:%s" % unit_name)
    if len(engaged_routes) > 1:
        raise ReadOnlyInputError("engaged_routes_ambiguous")

    sensors = _mapping(root["sensors"], "snapshot.sensors")
    _exact_keys(
        sensors, ("filament_sensor", "filament_sensor_2"), "snapshot.sensors"
    )
    detected = False
    for sensor_name in ("filament_sensor", "filament_sensor_2"):
        sensor = _mapping(sensors[sensor_name], "snapshot.sensors.%s" % sensor_name)
        _exact_keys(
            sensor,
            ("enabled", "filament_detected"),
            "snapshot.sensors.%s" % sensor_name,
        )
        enabled = _boolean(sensor["enabled"], "snapshot.sensors.%s.enabled" % sensor_name)
        present = _boolean(
            sensor["filament_detected"],
            "snapshot.sensors.%s.filament_detected" % sensor_name,
        )
        detected = detected or (enabled and present)

    runtime = _mapping(root["runtime"], "snapshot.runtime")
    _exact_keys(
        runtime,
        (
            "ready",
            "session_active",
            "accepted_z_valid",
            "accepted_z_offset",
            "low_moves_armed",
        ),
        "snapshot.runtime",
    )
    runtime_ready = _integer_flag(runtime["ready"], "snapshot.runtime.ready")
    session_active = _integer_flag(
        runtime["session_active"], "snapshot.runtime.session_active"
    )
    accepted_z_valid = _integer_flag(
        runtime["accepted_z_valid"], "snapshot.runtime.accepted_z_valid"
    )
    accepted_z = _number(
        runtime["accepted_z_offset"], "snapshot.runtime.accepted_z_offset"
    )
    low_moves_armed = _integer_flag(
        runtime["low_moves_armed"], "snapshot.runtime.low_moves_armed"
    )

    calibration_path = _mapping(
        root["calibration_path"], "snapshot.calibration_path"
    )
    _exact_keys(
        calibration_path,
        ("phase", "motion_armed", "commit_ready"),
        "snapshot.calibration_path",
    )
    calibration_phase = _text(
        calibration_path["phase"], "snapshot.calibration_path.phase"
    )
    motion_armed = _integer_flag(
        calibration_path["motion_armed"],
        "snapshot.calibration_path.motion_armed",
    )
    _integer_flag(
        calibration_path["commit_ready"],
        "snapshot.calibration_path.commit_ready",
    )

    mesh = _mapping(root["bed_mesh"], "snapshot.bed_mesh")
    _exact_keys(
        mesh,
        ("profile_name", "probed_matrix", "mesh_matrix", "profiles"),
        "snapshot.bed_mesh",
    )
    active_profile = _text(mesh["profile_name"], "snapshot.bed_mesh.profile_name")
    active_matrix = _matrix_summary(
        mesh["probed_matrix"], "snapshot.bed_mesh.probed_matrix"
    )
    _matrix_summary(mesh["mesh_matrix"], "snapshot.bed_mesh.mesh_matrix")
    profiles = _mapping(mesh["profiles"], "snapshot.bed_mesh.profiles")
    for name, summary in profiles.items():
        _matrix_summary(summary, "snapshot.bed_mesh.profiles.%s" % name)
    robust = profiles.get(ROBUST_PROFILE)
    robust_hash = robust.get("sha256") if isinstance(robust, Mapping) else None
    active_hash = active_matrix.get("sha256")

    if detected and not engaged_routes:
        filament_state = "engaged_unknown"
    elif detected and engaged_routes:
        filament_state = "engaged_known"
    elif not detected and engaged_routes:
        filament_state = "fault"
    else:
        filament_state = "absent_confirmed"

    robust_mesh_active = (
        active_profile == ROBUST_PROFILE and active_hash == robust_hash
    )
    safe_idle = (
        print_state == "standby"
        and not filename_present
        and extruder_target == 0.0
        and bed_target == 0.0
        and not can_extrude
        and box_state == "connect"
        and tuple(connected_units) == CONNECTED_UNITS
        and not active_command
        and runtime_ready == 1
        and session_active == 0
        and accepted_z_valid == 1
        and low_moves_armed == 0
        and calibration_phase == "idle"
        and motion_armed == 0
    )

    return {
        "print_state": print_state,
        "box_state": box_state,
        "connected_cfs_units": connected_units,
        "active_cfs_command": active_command,
        "engaged_routes": engaged_routes,
        "filament_state": filament_state,
        "extruder_target_c": extruder_target,
        "bed_target_c": bed_target,
        "accepted_z_valid": bool(accepted_z_valid),
        "accepted_z_offset_mm": accepted_z,
        "low_moves_armed": bool(low_moves_armed),
        "active_mesh_profile": active_profile,
        "active_mesh_sha256": active_hash,
        "robust_mesh_sha256": robust_hash,
        "robust_mesh_active": robust_mesh_active,
        "safe_idle": safe_idle,
        "mapping_fingerprint": mapping_fingerprint(root),
        "offline_contract_ready": safe_idle and robust_mesh_active,
    }
