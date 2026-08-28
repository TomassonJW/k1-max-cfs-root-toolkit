from __future__ import print_function

import json
import os
import socket
import sys
import time


SOCKET_PATH = "/tmp/klippy_uds"
ALLOWED_ACTIONS = {
    "objects",
    "generation",
    "snapshot",
    "restart",
    "restore_mesh",
    "selftest",
    "reset",
}
BEST_CURRENT_PROFILE = "k1_p001_t055_r001_n11x11"


def rpc(method, params=None, wait_response=True):
    request = {"id": 7301, "method": method, "params": params or {}}
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(5.0)
    client.connect(SOCKET_PATH)
    client.sendall((json.dumps(request) + "\x03").encode("utf-8"))
    if not wait_response:
        time.sleep(0.2)
        client.close()
        return {"sent": True}
    data = b""
    while b"\x03" not in data:
        chunk = client.recv(65536)
        if not chunk:
            break
        data += chunk
    client.close()
    if not data:
        return {"closed_without_response": True}
    message = json.loads(data.split(b"\x03", 1)[0].decode("utf-8"))
    if message.get("error"):
        raise RuntimeError(message["error"])
    return message.get("result", {})


def object_names():
    return sorted(rpc("objects/list").get("objects", []))


def generation():
    socket_stat = os.stat(SOCKET_PATH)
    return {
        "socket_inode": socket_stat.st_ino,
        "socket_mtime_ns": socket_stat.st_mtime_ns,
    }


def _box_projection(box):
    units = {}
    for unit_name in ("T1", "T2", "T3", "T4"):
        unit = box.get(unit_name, {}) if isinstance(box, dict) else {}
        units[unit_name] = {
            "state": unit.get("state"),
            "filament": unit.get("filament"),
        }
    return {
        "state": box.get("state") if isinstance(box, dict) else None,
        "t_command": box.get("t_command") if isinstance(box, dict) else None,
        "auto_refill": box.get("auto_refill") if isinstance(box, dict) else None,
        "enable": box.get("enable") if isinstance(box, dict) else None,
        "units": units,
    }


def snapshot():
    names = set(object_names())
    objects = {
        "webhooks": ["state", "state_message"],
        "print_stats": ["state", "filename"],
        "extruder": ["target", "temperature"],
        "heater_bed": ["target", "temperature"],
        "toolhead": ["homed_axes", "position", "axis_minimum", "axis_maximum", "estimated_print_time"],
        "gcode_move": ["homing_origin"],
        "bed_mesh": ["profile_name"],
        "box": None,
        "configfile": ["settings", "warnings"],
        "gcode_macro KCTRL_STATE": None,
        "k1_control_store": None,
    }
    if "gcode_macro KCTRL_START_OWNER_STATE" in names:
        objects["gcode_macro KCTRL_START_OWNER_STATE"] = None
    status = rpc("objects/query", {"objects": objects}).get("status", {})
    config = status.get("configfile", {}).get("settings", {})
    bounds = {}
    for section in ("stepper_x", "stepper_y", "stepper_z"):
        values = config.get(section, {}) if isinstance(config, dict) else {}
        bounds[section] = {
            "position_min": values.get("position_min"),
            "position_max": values.get("position_max"),
        }
    result = {
        "webhooks": status.get("webhooks", {}),
        "print_state": status.get("print_stats", {}).get("state"),
        "extruder": status.get("extruder", {}),
        "heater_bed": status.get("heater_bed", {}),
        "toolhead": status.get("toolhead", {}),
        "homing_origin": status.get("gcode_move", {}).get("homing_origin"),
        "mesh_profile": status.get("bed_mesh", {}).get("profile_name"),
        "box": _box_projection(status.get("box", {})),
        "runtime": status.get("gcode_macro KCTRL_STATE", {}),
        "store": status.get("k1_control_store", {}),
        "start_owner": status.get("gcode_macro KCTRL_START_OWNER_STATE"),
        "bounds": bounds,
        "config_warning_count": len(status.get("configfile", {}).get("warnings", []) or []),
        "object_requirements": {
            "mcu": "mcu" in names,
            "virtual_sdcard": "virtual_sdcard" in names,
            "accurate_g28": "gcode_macro ACCURATE_G28" in names,
            "kctrl_production_arm": "gcode_macro KCTRL_PRODUCTION_ARM" in names,
            "kctrl_production_assert_armed": "gcode_macro KCTRL_PRODUCTION_ASSERT_ARMED" in names,
            "start_owner_loaded": "gcode_macro KCTRL_START_OWNER_STATE" in names,
            "watchdog_loaded": "delayed_gcode kctrl_start_watchdog_v1" in config,
        },
        "identity_values_exported": False,
    }
    return result


def gcode(script, wait_response=True):
    return rpc("gcode/script", {"script": script}, wait_response=wait_response)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ALLOWED_ACTIONS:
        raise RuntimeError("unsupported_action")
    action = sys.argv[1]
    if action == "objects":
        result = object_names()
    elif action == "generation":
        result = generation()
    elif action == "snapshot":
        result = snapshot()
    elif action == "restart":
        result = gcode("RESTART", wait_response=False)
    elif action == "restore_mesh":
        result = gcode("BED_MESH_PROFILE LOAD=%s" % BEST_CURRENT_PROFILE)
    elif action == "selftest":
        result = gcode("KCTRL_START_WATCHDOG_SELFTEST_V1")
    elif action == "reset":
        result = gcode("KCTRL_RESET_START_OWNER_V1")
    else:
        raise RuntimeError("unsupported_action")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
