#!/usr/bin/env python3
"""Récupération bornée d'un cutter qui ne déclenche pas à Y304,5.

La tête essaie d'abord la position stock observée, puis avance par pas de 0,5 mm
jusqu'à la limite Y réelle publiée par la K1, 307,5 mm. Si le capteur déclenche,
elle reste en butée pendant tout le retrait T1A. Sinon elle ressort sans
rétraction. Aucun palpage n'est exécuté.
"""

from __future__ import print_function

import json
import socket
import sys
import time


SOCKET_PATH = "/tmp/klippy_uds"
BEST_MESH = "k1_p001_t055_r001_n11x11"
EFFECT_ID = "cutter-reach-t1a-r2-20260901"
UNLOAD_C = 190.0


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
    "filament_switch_sensor filament_sensor": ["filament_detected"],
    "filament_switch_sensor filament_sensor_2": ["filament_detected"],
    "k1_control_cfs_direct_owner": None,
}


def snapshot():
    status = rpc(9901, "objects/query", {"objects": OBJECTS}).get("status", {})
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
            "cut_pos": box.get("cut_pos") if isinstance(box, dict) else None,
            "logical_routes": routes,
        },
        "sensors": {
            "head": status.get("filament_switch_sensor filament_sensor", {}).get("filament_detected"),
            "after_cutter": status.get("filament_switch_sensor filament_sensor_2", {}).get("filament_detected"),
        },
        "direct": status.get("k1_control_cfs_direct_owner", {}),
    }


def cut_active(value):
    try:
        return abs(float(value) - 1.0) <= 0.001
    except (TypeError, ValueError):
        raise RecoveryError("cutter_sensor_status_invalid")


def require_preflight(value):
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
    require(not cut_active(value["box"]["cut_pos"]), "cutter_already_triggered")
    require(value["sensors"]["head"] is True, "head_sensor_not_detected")
    require(value["sensors"]["after_cutter"] is True, "after_cutter_sensor_not_detected")
    require(value["direct"].get("enabled") is True, "direct_owner_not_enabled")
    require(value["direct"].get("stock_commands_blocked") is True, "stock_commands_not_blocked")
    require(value["direct"].get("phase") == "loaded", "direct_owner_not_loaded")
    require(value["direct"].get("active_route") == "T1A", "direct_route_not_t1a")
    require(value["direct"].get("failure_code") is None, "direct_owner_failure_present")


def gcode(request_id, script, timeout_s=30.0):
    return rpc(request_id, "gcode/script", {"script": script}, timeout_s=timeout_s)


def read_cut_samples(count=4):
    samples = []
    for _index in range(count):
        current = snapshot()
        samples.append(current["box"]["cut_pos"])
        if cut_active(samples[-1]):
            return True, samples
        time.sleep(0.5)
    return False, samples


def safe_release():
    try:
        gcode(9997, "G90\nG1 X38 Y230 F1200\nM400", timeout_s=20.0)
    except Exception:
        pass
    try:
        gcode(9998, "TURN_OFF_HEATERS\nM84", timeout_s=20.0)
    except Exception:
        pass


def run():
    before = snapshot()
    require_preflight(before)
    contact_y = None
    stock_samples = []
    extension_samples = {}
    try:
        gcode(
            9910,
            "G28 X Y\n"
            "SET_KINEMATIC_POSITION Z=50\n"
            "BED_MESH_PROFILE LOAD=%s\n"
            "G90\n"
            "G1 X38 Y230 F1200\n"
            "M104 S190\n"
            "M109 S190\n"
            "G1 X38 Y304.5 F1200\n"
            "M400\n"
            "G4 P1500" % BEST_MESH,
            timeout_s=180.0,
        )
        triggered, stock_samples = read_cut_samples()
        if triggered:
            contact_y = 304.5
        else:
            for index, candidate_y in enumerate((305.0, 305.5, 306.0, 306.5, 307.0, 307.5)):
                gcode(
                    9920 + index,
                    "G90\nG1 X38 Y%.1f F300\nM400\nG4 P750" % candidate_y,
                    timeout_s=20.0,
                )
                triggered, samples = read_cut_samples(count=3)
                extension_samples["%.1f" % candidate_y] = samples
                if triggered:
                    contact_y = candidate_y
                    break
            require(contact_y is not None, "cutter_not_triggered_at_y307_5_limit")
        gcode(
            9930,
            "KCTRL_CFS_DIRECT_UNLOAD ROUTE=T1A EFFECT_ID=%s "
            "EXPECTED_C=190 MATERIAL_MIN_C=180 MATERIAL_MAX_C=230" % EFFECT_ID,
            timeout_s=180.0,
        )
        held = snapshot()
        require(cut_active(held["box"]["cut_pos"]), "cutter_released_during_unload")
        require(held["direct"].get("phase") == "idle", "direct_owner_not_idle_after_unload")
        require(held["direct"].get("active_route") is None, "direct_route_not_released")
        require(held["sensors"]["head"] is False, "head_sensor_not_cleared")
        require(held["sensors"]["after_cutter"] is False, "after_cutter_sensor_not_cleared")
    finally:
        safe_release()
    time.sleep(2.0)
    after = snapshot()
    require(not cut_active(after["box"]["cut_pos"]), "cutter_sensor_not_released")
    require(float(after["extruder"].get("target", -1)) == 0.0, "nozzle_shutdown_unproven")
    require(float(after["heater_bed"].get("target", -1)) == 0.0, "bed_shutdown_unproven")
    require(after["toolhead"].get("homed_axes") in ("", []), "motors_not_released")
    require(after["mesh_profile"] == BEST_MESH, "mesh_not_restored")
    return {
        "mission": "G4-K1-CONTROL-CUTTER-REACH-RECOVERY-V1",
        "status": "COMPLETED_T1A_CUT_AND_FULLY_UNLOADED",
        "contact_y_mm": contact_y,
        "stock_position_samples": stock_samples,
        "extension_samples_by_y": extension_samples,
        "cutter_held_during_unload": True,
        "probe": False,
        "mesh_recalculation": False,
        "before": before,
        "after": after,
    }


if __name__ == "__main__":
    try:
        require(len(sys.argv) == 2 and sys.argv[1] == "run", "action_invalid")
        print(json.dumps(run(), sort_keys=True, separators=(",", ":")))
    except Exception as error:
        safe_release()
        print(json.dumps({"error": getattr(error, "args", [str(error)])[0]}))
        sys.exit(1)
