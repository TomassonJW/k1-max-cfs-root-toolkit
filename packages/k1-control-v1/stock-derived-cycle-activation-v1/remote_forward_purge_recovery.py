#!/usr/bin/env python3
"""Recuperation bornee d'un segment coupe reste dans la tete.

Ce pilote est execute depuis stdin sur la K1. Il ne connait qu'une action
physique : pousser localement 80 mm vers la buse dans le bac de purge, puis
effectuer quatre passages de decrochage. Il n'envoie aucune trame CFS et ne
fait aucune palpation.
"""

from __future__ import print_function

import json
import socket
import sys
import time


SOCKET_PATH = "/tmp/klippy_uds"
BEST_MESH = "k1_p001_t055_r001_n11x11"
NOZZLE_C = 190.0
FORWARD_MM = 80.0
FORWARD_FEED_MM_MIN = 180.0


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
    require(not response.get("error"), "klipper_command_rejected")
    return response.get("result", {})


OBJECTS = {
    "webhooks": ["state", "state_message"],
    "print_stats": ["state", "filename"],
    "extruder": ["target", "temperature", "can_extrude"],
    "heater_bed": ["target", "temperature"],
    "toolhead": ["homed_axes", "position"],
    "bed_mesh": ["profile_name"],
    "box": None,
    "filament_switch_sensor filament_sensor": ["filament_detected", "enabled"],
    "filament_switch_sensor filament_sensor_2": ["filament_detected", "enabled"],
    "k1_control_cfs_direct_owner": None,
    "k1_control_stock_cycle_owner": None,
}


def snapshot():
    status = rpc(9101, "objects/query", {"objects": OBJECTS}).get("status", {})
    box = status.get("box", {})
    routes = []
    for unit_name in ("T1", "T2"):
        unit = box.get(unit_name, {}) if isinstance(box, dict) else {}
        filament = unit.get("filament") if isinstance(unit, dict) else None
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
            "auto_refill": box.get("auto_refill") if isinstance(box, dict) else None,
            "enable": box.get("enable") if isinstance(box, dict) else None,
            "t_command": box.get("t_command") if isinstance(box, dict) else None,
            "logical_routes": routes,
        },
        "sensors": {
            "head": status.get("filament_switch_sensor filament_sensor", {}).get("filament_detected"),
            "after_cutter": status.get("filament_switch_sensor filament_sensor_2", {}).get("filament_detected"),
        },
        "direct_owner": status.get("k1_control_cfs_direct_owner", {}),
        "stock_owner": status.get("k1_control_stock_cycle_owner", {}),
    }


def require_preflight(value):
    require(value["webhooks"].get("state") == "ready", "klipper_not_ready")
    require(value["print_state"] == "standby", "printer_not_standby")
    require(float(value["extruder"].get("target", -1)) == 0.0, "nozzle_target_nonzero")
    require(float(value["heater_bed"].get("target", -1)) == 0.0, "bed_target_nonzero")
    require(value["toolhead"].get("homed_axes") in ("", []), "axes_not_released")
    # Le G28 X/Y de la tentative fautive a recharge le profil constructeur
    # `default`. C'est le seul etat d'incident accepte ; le script remet le
    # 11x11 explicitement, sans aucune nouvelle palpation.
    require(
        value["mesh_profile"] in (BEST_MESH, "default"),
        "mesh_profile_incident_state_unexpected",
    )
    require(value["box"]["auto_refill"] == 0, "stock_auto_refill_not_disabled")
    require(value["box"]["enable"] in (1, True), "cfs_interface_disabled")
    require(value["box"]["t_command"] == "", "stock_command_active")
    require(value["box"]["logical_routes"] == [], "stock_route_present")
    require(value["sensors"]["head"] is True, "head_segment_not_detected")
    require(value["sensors"]["after_cutter"] is False, "upstream_path_not_clear")
    direct = value["direct_owner"]
    require(direct.get("enabled") is True, "direct_owner_not_enabled")
    require(direct.get("stock_commands_blocked") is True, "stock_commands_not_blocked")
    require(direct.get("phase") == "failed_safe", "direct_owner_phase_unexpected")
    require(direct.get("failure_code") == "head_sensor_not_cleared_after_unload", "direct_failure_unexpected")
    require(direct.get("last_operation") == "unload", "direct_last_operation_unexpected")
    require(direct.get("tip_pull_count") == 1, "tip_pull_count_unexpected")
    require(direct.get("automatic_retry_count") == 0, "automatic_retry_detected")


RECOVERY_GCODE = """G28 X Y
SET_KINEMATIC_POSITION Z=50
BED_MESH_PROFILE LOAD=k1_p001_t055_r001_n11x11
G90
G1 X203 Y273 F1200
G1 X185.5 Y305 F1200
M104 S190
M109 S190
SAVE_GCODE_STATE NAME=KCTRL_FORWARD_PURGE_RECOVERY
M83
G1 E80 F180
RESTORE_GCODE_STATE NAME=KCTRL_FORWARD_PURGE_RECOVERY MOVE=0
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
        rpc(9199, "gcode/script", {"script": "TURN_OFF_HEATERS\nM84"}, timeout_s=20.0)
    except Exception:
        pass


def run():
    before = snapshot()
    require_preflight(before)
    try:
        rpc(9120, "gcode/script", {"script": RECOVERY_GCODE}, timeout_s=240.0)
    except Exception:
        safe_stop()
        raise
    time.sleep(4.0)
    after = snapshot()
    require(float(after["extruder"].get("target", -1)) == 0.0, "nozzle_shutdown_unproven")
    require(float(after["heater_bed"].get("target", -1)) == 0.0, "bed_shutdown_unproven")
    require(after["toolhead"].get("homed_axes") in ("", []), "motors_not_released")
    require(after["mesh_profile"] == BEST_MESH, "mesh_profile_not_restored")
    require(after["box"]["logical_routes"] == [], "unexpected_cfs_route")
    require(after["sensors"]["after_cutter"] is False, "upstream_path_changed")
    return {
        "mission": "K1-CONTROL-FORWARD-PURGE-RECOVERY-V1",
        "status": "COMPLETED_FORWARD_ONLY",
        "forward_mm": FORWARD_MM,
        "forward_feed_mm_min": FORWARD_FEED_MM_MIN,
        "cfs_effect": False,
        "retraction_effect": False,
        "probe_effect": False,
        "release_round_trips": 4,
        "before": before,
        "after": after,
        "head_sensor_cleared": after["sensors"]["head"] is False,
    }


def inspect_position():
    before = snapshot()
    require(before["webhooks"].get("state") == "ready", "klipper_not_ready")
    require(before["print_state"] == "standby", "printer_not_standby")
    require(float(before["extruder"].get("target", -1)) == 0.0, "nozzle_target_nonzero")
    require(float(before["heater_bed"].get("target", -1)) == 0.0, "bed_target_nonzero")
    require(before["box"]["logical_routes"] == [], "stock_route_present")
    require(before["box"]["t_command"] == "", "stock_command_active")
    require(before["mesh_profile"] == BEST_MESH, "mesh_profile_drift")
    script = """G28 X Y
SET_KINEMATIC_POSITION Z=50
BED_MESH_PROFILE LOAD=k1_p001_t055_r001_n11x11
G90
G1 X150 Y150 F1800
M400
TURN_OFF_HEATERS
M84"""
    rpc(9150, "gcode/script", {"script": script}, timeout_s=90.0)
    time.sleep(1.0)
    after = snapshot()
    require(float(after["extruder"].get("target", -1)) == 0.0, "nozzle_shutdown_unproven")
    require(float(after["heater_bed"].get("target", -1)) == 0.0, "bed_shutdown_unproven")
    require(after["toolhead"].get("homed_axes") in ("", []), "motors_not_released")
    require(after["mesh_profile"] == BEST_MESH, "mesh_profile_not_restored")
    return {
        "mission": "K1-CONTROL-FORWARD-PURGE-RECOVERY-V1",
        "status": "CAMERA_INSPECTION_POSITION_READY",
        "heat": False,
        "extrusion": False,
        "cfs_effect": False,
        "probe_effect": False,
        "before": before,
        "after": after,
    }


def main():
    require(
        len(sys.argv) == 2 and sys.argv[1] in ("snapshot", "run", "inspect"),
        "action_invalid",
    )
    if sys.argv[1] == "snapshot":
        result = snapshot()
    elif sys.argv[1] == "inspect":
        result = inspect_position()
    else:
        result = run()
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        safe_stop()
        print(json.dumps({"error": getattr(error, "args", [str(error)])[0]}))
        sys.exit(1)
