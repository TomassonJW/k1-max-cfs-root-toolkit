#!/usr/bin/env python3
"""Reprise physique unique du handoff T1A après EXTRUDE_ERR8.

La reprise ne renvoie aucun stage 5. Elle place la tête dans le bac, chauffe à
190 C, demande au propriétaire direct la seule fin 4 -> 6 observée dans la
trace stock, puis fait prendre 30 mm par l'extrudeur et exécute quatre passages
de décrochage. Aucun Z n'est palpé.
"""

from __future__ import print_function

import json
import socket
import sys
import time


SOCKET_PATH = "/tmp/klippy_uds"
BEST_MESH = "k1_p001_t055_r001_n11x11"
RECOVERY_ID = "err8-tail-t1a-r1-20260901"
NOZZLE_C = 190.0
LOCAL_FORWARD_MM = 30.0
LOCAL_FORWARD_FEED = 120.0


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
    status = rpc(9301, "objects/query", {"objects": OBJECTS}).get("status", {})
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


def require_common(value):
    require(value["webhooks"].get("state") == "ready", "klipper_not_ready")
    require(value["print_state"] == "standby", "printer_not_standby")
    require(value["mesh_profile"] == BEST_MESH, "mesh_profile_drift")
    require(value["box"]["auto_refill"] == 0, "stock_auto_refill_not_disabled")
    require(value["box"]["enable"] in (1, True), "cfs_interface_disabled")
    require(value["box"]["t_command"] == "", "stock_command_active")
    require(value["box"]["logical_routes"] == [], "stock_route_present")
    require(value["sensors"]["head"] is True, "head_sensor_not_detected")
    require(value["sensors"]["after_cutter"] is True, "after_cutter_sensor_not_detected")
    direct = value["direct_owner"]
    require(direct.get("enabled") is True, "direct_owner_not_enabled")
    require(direct.get("stock_commands_blocked") is True, "stock_commands_not_blocked")


def require_preflight(value):
    require_common(value)
    require(float(value["extruder"].get("target", -1)) == 0.0, "nozzle_target_nonzero")
    require(float(value["heater_bed"].get("target", -1)) == 0.0, "bed_target_nonzero")
    require(value["toolhead"].get("homed_axes") in ("", []), "axes_not_released")
    direct = value["direct_owner"]
    require(direct.get("phase") == "idle", "direct_owner_not_idle")
    require(direct.get("active_route") is None, "direct_route_present")
    require(direct.get("load_tail_recovery_count") == 0, "err8_recovery_already_used")
    require(direct.get("cfs_direct_owner_err8_load_tail_recovery_id") is None, "err8_recovery_id_already_used")


def require_takeover_preflight(value):
    require_common(value)
    require(float(value["extruder"].get("target", -1)) == 0.0, "nozzle_target_nonzero")
    require(float(value["heater_bed"].get("target", -1)) == 0.0, "bed_target_nonzero")
    require(value["toolhead"].get("homed_axes") in ("", []), "axes_not_released")
    direct = value["direct_owner"]
    require(direct.get("phase") == "failed_safe", "takeover_owner_phase_invalid")
    require(direct.get("failure_code") == "buffer_not_middle_after_load", "takeover_failure_code_invalid")
    require(direct.get("active_route") is None, "takeover_direct_route_present")
    require(direct.get("frames_sent_count") == 9, "takeover_frame_count_invalid")
    require(direct.get("retained_head_segment") is True, "takeover_segment_state_invalid")
    require(
        direct.get("cfs_direct_owner_err8_load_tail_recovery_id") == RECOVERY_ID,
        "takeover_recovery_id_invalid",
    )


def require_finalize_preflight(value):
    require_common(value)
    require(float(value["extruder"].get("target", -1)) == 0.0, "nozzle_target_nonzero")
    require(float(value["heater_bed"].get("target", -1)) == 0.0, "bed_target_nonzero")
    require(value["toolhead"].get("homed_axes") in ("", []), "axes_not_released")
    direct = value["direct_owner"]
    require(direct.get("phase") == "idle", "finalize_owner_not_idle")
    require(direct.get("active_route") is None, "finalize_route_present")
    require(direct.get("takeover_finalize_count") == 0, "finalize_already_used")
    require(
        direct.get("cfs_direct_owner_takeover_finalize_recovery_id") is None,
        "finalize_recovery_id_already_used",
    )


POSITION_AND_HEAT = """G28 X Y
SET_KINEMATIC_POSITION Z=30
BED_MESH_PROFILE LOAD=k1_p001_t055_r001_n11x11
G90
G1 X203 Y273 F1200
G1 X185.5 Y305 F1200
M104 S190
M109 S190
M400"""

RECOVER_TAIL = """KCTRL_CFS_DIRECT_RECOVER_EXTRUDE_ERROR_LOAD_TAIL ROUTE=T1A RECOVERY_ID=err8-tail-t1a-r1-20260901 CONFIRM=1 EXPECTED_C=190 MATERIAL_MIN_C=170 MATERIAL_MAX_C=240"""

FINALIZE_TAKEOVER = """KCTRL_CFS_DIRECT_FINALIZE_LOAD_TAKEOVER ROUTE=T1A RECOVERY_ID=takeover-finalize-t1a-r1-20260901 CONFIRM=1"""

LOCAL_PURGE_AND_RELEASE = """SAVE_GCODE_STATE NAME=KCTRL_ERR8_TAIL_PURGE
M83
G1 E30 F120
RESTORE_GCODE_STATE NAME=KCTRL_ERR8_TAIL_PURGE MOVE=0
G90
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
        rpc(9399, "gcode/script", {"script": "TURN_OFF_HEATERS\nM84"}, timeout_s=20.0)
    except Exception:
        pass


def run():
    before = snapshot()
    require_preflight(before)
    try:
        rpc(9320, "gcode/script", {"script": POSITION_AND_HEAT}, timeout_s=180.0)
        rpc(9321, "gcode/script", {"script": RECOVER_TAIL}, timeout_s=60.0)
        middle = snapshot()
        require_common(middle)
        require(middle["direct_owner"].get("phase") == "loaded", "tail_route_not_loaded")
        require(middle["direct_owner"].get("active_route") == "T1A", "tail_route_not_t1a")
        require(middle["direct_owner"].get("failure_code") is None, "tail_recovery_failed")
        require(middle["direct_owner"].get("load_tail_recovery_count") == 1, "tail_recovery_count_invalid")
        rpc(9322, "gcode/script", {"script": LOCAL_PURGE_AND_RELEASE}, timeout_s=120.0)
    except Exception:
        safe_stop()
        raise
    time.sleep(3.0)
    after = snapshot()
    require_common(after)
    require(float(after["extruder"].get("target", -1)) == 0.0, "nozzle_shutdown_unproven")
    require(float(after["heater_bed"].get("target", -1)) == 0.0, "bed_shutdown_unproven")
    require(after["toolhead"].get("homed_axes") in ("", []), "motors_not_released")
    require(after["direct_owner"].get("phase") == "loaded", "direct_owner_not_loaded")
    require(after["direct_owner"].get("active_route") == "T1A", "direct_route_not_t1a")
    require(after["direct_owner"].get("load_tail_recovery_count") == 1, "tail_recovery_count_lost")
    return {
        "mission": "G4-K1-CONTROL-CFS-ERR8-LOAD-TAIL-RECOVERY-V1",
        "status": "COMPLETED_NEEDS_HUMAN_PURGE_VIEW",
        "recovery_id": RECOVERY_ID,
        "serial_tail_stages": [4, 6],
        "serial_stage5_count": 0,
        "local_forward_mm": LOCAL_FORWARD_MM,
        "local_forward_feed_mm_min": LOCAL_FORWARD_FEED,
        "release_round_trips": 4,
        "probe_effect": False,
        "before": before,
        "middle": middle,
        "after": after,
    }


def takeover():
    before = snapshot()
    require_takeover_preflight(before)
    try:
        rpc(9340, "gcode/script", {"script": POSITION_AND_HEAT}, timeout_s=180.0)
        rpc(9341, "gcode/script", {"script": LOCAL_PURGE_AND_RELEASE}, timeout_s=120.0)
    except Exception:
        safe_stop()
        raise
    time.sleep(3.0)
    after = snapshot()
    require_common(after)
    require(float(after["extruder"].get("target", -1)) == 0.0, "nozzle_shutdown_unproven")
    require(float(after["heater_bed"].get("target", -1)) == 0.0, "bed_shutdown_unproven")
    require(after["toolhead"].get("homed_axes") in ("", []), "motors_not_released")
    require(after["direct_owner"].get("phase") == "failed_safe", "takeover_owner_state_changed")
    require(
        after["direct_owner"].get("failure_code") == "buffer_not_middle_after_load",
        "takeover_failure_state_changed",
    )
    require(after["direct_owner"].get("frames_sent_count") == 9, "takeover_sent_cfs_frame")
    return {
        "mission": "G4-K1-CONTROL-CFS-ERR8-LOCAL-TAKEOVER-V1",
        "status": "COMPLETED_NEEDS_HUMAN_PURGE_VIEW",
        "local_forward_mm": LOCAL_FORWARD_MM,
        "local_forward_feed_mm_min": LOCAL_FORWARD_FEED,
        "release_round_trips": 4,
        "cfs_frame_count_before": 9,
        "cfs_frame_count_after": 9,
        "probe_effect": False,
        "before": before,
        "after": after,
    }


def finalize():
    before = snapshot()
    require_finalize_preflight(before)
    rpc(9360, "gcode/script", {"script": FINALIZE_TAKEOVER}, timeout_s=30.0)
    time.sleep(1.0)
    after = snapshot()
    require_common(after)
    direct = after["direct_owner"]
    require(direct.get("phase") == "loaded", "finalize_route_not_loaded")
    require(direct.get("active_route") == "T1A", "finalize_route_not_t1a")
    require(direct.get("failure_code") is None, "finalize_failed")
    require(direct.get("last_buffer_state") == 0, "finalize_buffer_not_middle")
    require(direct.get("takeover_finalize_count") == 1, "finalize_count_invalid")
    require(direct.get("frames_sent_count") == 3, "finalize_frame_count_invalid")
    return {
        "mission": "G4-K1-CONTROL-CFS-ERR8-TAKEOVER-FINALIZE-V1",
        "status": "COMPLETED_BUFFER_MIDDLE_T1A_LATCHED",
        "buffer_state": 0,
        "direct_route": "T1A",
        "serial_query_count": 2,
        "serial_mode_frame_count": 1,
        "serial_motor_frame_count": 0,
        "heat": False,
        "motion": False,
        "probe_effect": False,
        "before": before,
        "after": after,
    }


def main():
    require(len(sys.argv) == 2 and sys.argv[1] in ("run", "takeover", "finalize"), "action_invalid")
    if sys.argv[1] == "takeover":
        result = takeover()
    elif sys.argv[1] == "finalize":
        result = finalize()
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
