#!/usr/bin/env python3
"""Contrôle manuel, froid et sans effet du capteur du cutter K1."""

from __future__ import print_function

import json
import socket
import sys
import time


SOCKET_PATH = "/tmp/klippy_uds"
MONITOR_SECONDS = 90.0
POLL_SECONDS = 0.1
MAX_SAFE_NOZZLE_C = 50.0


class CheckError(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise CheckError(code)


def rpc(request_id, method, params=None):
    request = {"id": request_id, "method": method, "params": params or {}}
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(5.0)
    try:
        client.connect(SOCKET_PATH)
        client.sendall((json.dumps(request) + "\x03").encode("utf-8"))
        data = b""
        while b"\x03" not in data:
            chunk = client.recv(65536)
            if not chunk:
                break
            data += chunk
    finally:
        client.close()
    require(bool(data), "klipper_response_missing")
    response = json.loads(data.split(b"\x03", 1)[0].decode("utf-8"))
    require(not response.get("error"), "klipper_query_rejected")
    return response.get("result", {})


def snapshot(request_id):
    objects = {
        "webhooks": ["state"],
        "print_stats": ["state"],
        "extruder": ["target", "temperature"],
        "heater_bed": ["target", "temperature"],
        "toolhead": ["homed_axes", "position"],
        "box": ["cut_pos", "t_command"],
        "filament_switch_sensor filament_sensor": ["filament_detected"],
        "filament_switch_sensor filament_sensor_2": ["filament_detected"],
    }
    return rpc(request_id, "objects/query", {"objects": objects}).get("status", {})


def cut_active(value):
    try:
        return abs(float(value) - 1.0) <= 0.001
    except (TypeError, ValueError):
        raise CheckError("cutter_sensor_status_invalid")


def require_cold_idle(status):
    require(status.get("webhooks", {}).get("state") == "ready", "klipper_not_ready")
    require(status.get("print_stats", {}).get("state") == "standby", "printer_not_standby")
    extruder = status.get("extruder", {})
    bed = status.get("heater_bed", {})
    toolhead = status.get("toolhead", {})
    box = status.get("box", {})
    require(float(extruder.get("target", -1)) == 0.0, "nozzle_target_nonzero")
    require(float(bed.get("target", -1)) == 0.0, "bed_target_nonzero")
    require(float(extruder.get("temperature", 999)) <= MAX_SAFE_NOZZLE_C, "nozzle_not_cold")
    require(toolhead.get("homed_axes") in ("", []), "axes_not_released")
    require(box.get("t_command") == "", "stock_command_active")
    require(not cut_active(box.get("cut_pos")), "cutter_sensor_already_active")


def compact(status):
    return {
        "cut_pos": status.get("box", {}).get("cut_pos"),
        "nozzle_c": status.get("extruder", {}).get("temperature"),
        "nozzle_target_c": status.get("extruder", {}).get("target"),
        "bed_target_c": status.get("heater_bed", {}).get("target"),
        "homed_axes": status.get("toolhead", {}).get("homed_axes"),
        "position": status.get("toolhead", {}).get("position"),
        "head_filament": status.get(
            "filament_switch_sensor filament_sensor", {}
        ).get("filament_detected"),
        "after_cutter_filament": status.get(
            "filament_switch_sensor filament_sensor_2", {}
        ).get("filament_detected"),
    }


def run():
    before = snapshot(8400)
    require_cold_idle(before)
    print(
        json.dumps(
            {
                "event": "MANUAL_CUTTER_SENSOR_MONITOR_READY",
                "window_seconds": MONITOR_SECONDS,
                "before": compact(before),
                "physical_effect": False,
            },
            sort_keys=True,
        )
    )
    sys.stdout.flush()

    started = time.monotonic()
    active_at = None
    released_at = None
    request_id = 8401
    while time.monotonic() - started < MONITOR_SECONDS:
        current = snapshot(request_id)
        request_id += 1
        elapsed = round(time.monotonic() - started, 3)
        active = cut_active(current.get("box", {}).get("cut_pos"))
        if active_at is None and active:
            active_at = elapsed
            print(json.dumps({"event": "CUTTER_SENSOR_ACTIVE", "at_seconds": active_at}))
            sys.stdout.flush()
        elif active_at is not None and not active:
            released_at = elapsed
            print(json.dumps({"event": "CUTTER_SENSOR_RELEASED", "at_seconds": released_at}))
            sys.stdout.flush()
            break
        time.sleep(POLL_SECONDS)

    after = snapshot(request_id + 1)
    require_cold_idle(after)
    require(active_at is not None, "cutter_sensor_not_triggered_manually")
    require(released_at is not None, "cutter_sensor_not_released_manually")
    return {
        "status": "MANUAL_CUTTER_SENSOR_QUALIFIED",
        "active_at_seconds": active_at,
        "released_at_seconds": released_at,
        "duration_active_seconds": round(released_at - active_at, 3),
        "before": compact(before),
        "after": compact(after),
        "heat": False,
        "axis_motion": False,
        "filament_motion": False,
        "gcode": False,
    }


if __name__ == "__main__":
    try:
        require(len(sys.argv) == 2 and sys.argv[1] == "monitor", "action_invalid")
        print(json.dumps(run(), sort_keys=True, separators=(",", ":")))
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "MANUAL_CUTTER_SENSOR_CHECK_FAILED",
                    "error": getattr(error, "args", [str(error)])[0],
                    "heat": False,
                    "axis_motion": False,
                    "filament_motion": False,
                    "gcode": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        sys.exit(1)
