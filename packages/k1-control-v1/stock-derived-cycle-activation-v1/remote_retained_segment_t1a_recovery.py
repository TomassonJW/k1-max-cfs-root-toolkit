#!/usr/bin/env python3
"""Pousse T1A derrière un segment coupé confirmé dans la tête, sans palpage."""

from __future__ import print_function

import json
import socket
import sys
import time


SOCKET_PATH = "/tmp/klippy_uds"
BEST_MESH = "k1_p001_t055_r001_n11x11"
RECOVERY_ID = "retained-segment-t1a-r2-20260901"


class RecoveryError(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise RecoveryError(code)


def rpc(request_id, method, params=None, timeout_s=30.0):
    request = {"id": request_id, "method": method, "params": params or {}}
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout_s)
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
    require(not response.get("error"), "klipper_command_rejected:%s" % response.get("error"))
    return response.get("result", {})


OBJECTS = {
    "webhooks": ["state", "state_message"],
    "print_stats": ["state", "filename"],
    "extruder": ["target", "temperature", "can_extrude"],
    "heater_bed": ["target", "temperature"],
    "toolhead": ["homed_axes", "position"],
    "bed_mesh": ["profile_name"],
    "box": None,
    "filament_switch_sensor filament_sensor": ["filament_detected"],
    "filament_switch_sensor filament_sensor_2": ["filament_detected"],
    "k1_control_cfs_direct_owner": None,
}


def snapshot():
    status = rpc(9401, "objects/query", {"objects": OBJECTS}).get("status", {})
    box = status.get("box", {})
    routes = []
    for unit_name in ("T1", "T2"):
        filament = box.get(unit_name, {}).get("filament")
        if filament in ("A", "B", "C", "D"):
            routes.append(unit_name + filament)
    return {
        "webhooks": status.get("webhooks", {}),
        "print_state": status.get("print_stats", {}).get("state"),
        "extruder": status.get("extruder", {}),
        "heater_bed": status.get("heater_bed", {}),
        "toolhead": status.get("toolhead", {}),
        "mesh_profile": status.get("bed_mesh", {}).get("profile_name"),
        "box": {
            "auto_refill": box.get("auto_refill"),
            "enable": box.get("enable"),
            "t_command": box.get("t_command"),
            "logical_routes": routes,
        },
        "sensors": {
            "head": status.get("filament_switch_sensor filament_sensor", {}).get("filament_detected"),
            "after_cutter": status.get("filament_switch_sensor filament_sensor_2", {}).get("filament_detected"),
        },
        "direct_owner": status.get("k1_control_cfs_direct_owner", {}),
    }


def require_before(value):
    require(value["webhooks"].get("state") == "ready", "klipper_not_ready")
    require(value["print_state"] == "standby", "printer_not_standby")
    require(float(value["extruder"].get("target", -1)) == 0.0, "nozzle_target_nonzero")
    require(float(value["heater_bed"].get("target", -1)) == 0.0, "bed_target_nonzero")
    require(value["toolhead"].get("homed_axes") in ("", []), "axes_not_released")
    require(value["mesh_profile"] == BEST_MESH, "mesh_profile_drift")
    require(value["box"]["auto_refill"] == 0, "stock_auto_refill_not_disabled")
    require(value["box"]["enable"] in (1, True), "cfs_interface_disabled")
    require(value["box"]["t_command"] == "", "stock_command_active")
    require(value["box"]["logical_routes"] == [], "stock_route_present")
    require(value["sensors"]["head"] is True, "head_segment_not_detected")
    require(value["sensors"]["after_cutter"] is False, "upstream_path_not_clear")
    owner = value["direct_owner"]
    require(owner.get("enabled") is True, "direct_owner_not_enabled")
    require(owner.get("stock_commands_blocked") is True, "stock_commands_not_blocked")
    require(owner.get("phase") == "idle", "direct_owner_not_reset")
    require(owner.get("failure_code") is None, "direct_owner_failure_present")
    require(owner.get("active_route") is None, "direct_owner_route_present")


RECOVERY_GCODE = """G28 X Y
SET_KINEMATIC_POSITION Z=50
BED_MESH_PROFILE LOAD=k1_p001_t055_r001_n11x11
G90
G1 Z32 F600
G1 X185.5 Y305 F1200
G1 Z30 F600
M104 S190
M109 S190
KCTRL_CFS_DIRECT_ADOPT_RETAINED_SEGMENT RECOVERY_ID=retained-segment-t1a-r2-20260901 CONFIRM=1
KCTRL_CFS_DIRECT_LOAD ROUTE=T1A EFFECT_ID=retained-segment-t1a-load-r2-20260901 EXPECTED_C=190 MATERIAL_MIN_C=180 MATERIAL_MAX_C=230
SAVE_GCODE_STATE NAME=KCTRL_RETAINED_SEGMENT_T1A_PURGE
M83
G1 E20 F360
RESTORE_GCODE_STATE NAME=KCTRL_RETAINED_SEGMENT_T1A_PURGE MOVE=0
G1 Z32 F600
G1 X203 Y273 F1200
G1 Y305 F600
G1 X206 F180
G1 X203 F180
G1 Y304 F600
G1 X206 F180
G1 X203 F180
G1 Y305 F600
G1 X206 F180
G1 X203 F180
G1 Y304 F600
G1 X206 F180
G1 X203 F180
G1 X203 Y273 F1200
M400
TURN_OFF_HEATERS
M84"""


def safe_stop():
    try:
        rpc(9499, "gcode/script", {"script": "TURN_OFF_HEATERS\nM84"}, timeout_s=20.0)
    except Exception:
        pass


def run():
    before = snapshot()
    require_before(before)
    try:
        rpc(9420, "gcode/script", {"script": RECOVERY_GCODE}, timeout_s=300.0)
    except Exception:
        safe_stop()
        raise
    time.sleep(3.0)
    after = snapshot()
    require(float(after["extruder"].get("target", -1)) == 0.0, "nozzle_shutdown_unproven")
    require(float(after["heater_bed"].get("target", -1)) == 0.0, "bed_shutdown_unproven")
    require(after["toolhead"].get("homed_axes") in ("", []), "motors_not_released")
    require(after["mesh_profile"] == BEST_MESH, "mesh_profile_not_restored")
    require(after["box"]["logical_routes"] == ["T1A"], "T1A_route_not_latched")
    require(after["sensors"]["head"] is True, "head_sensor_not_present_after_load")
    require(after["sensors"]["after_cutter"] is True, "upstream_sensor_not_present_after_load")
    require(after["direct_owner"].get("phase") == "loaded", "direct_owner_not_loaded")
    require(after["direct_owner"].get("active_route") == "T1A", "direct_owner_route_not_T1A")
    require(after["direct_owner"].get("retained_head_segment") is False, "retained_segment_not_consumed")
    return {
        "mission": "K1-CONTROL-RETAINED-SEGMENT-T1A-RECOVERY-V1",
        "status": "T1A_LOADED_AND_FORWARD_PURGED",
        "route": "T1A",
        "purge_mm": 140.0,
        "release_trips": 4,
        "retraction_effect": False,
        "probe_effect": False,
        "before": before,
        "after": after,
    }


if __name__ == "__main__":
    try:
        require(len(sys.argv) == 2 and sys.argv[1] == "run", "action_invalid")
        print(json.dumps(run(), sort_keys=True, separators=(",", ":")))
    except Exception as error:
        safe_stop()
        print(json.dumps({"error": str(error)}))
        sys.exit(1)
