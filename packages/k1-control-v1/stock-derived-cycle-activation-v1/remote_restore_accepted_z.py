#!/usr/bin/env python3
"""Restaure le Z accepté après un restart hôte, sans mouvement ni palpage."""

import json
import socket


SOCKET = "/tmp/klippy_uds"
EXPECTED_Z = -0.04
EXPECTED_PROFILE = "k1_p001_t055_r001_n11x11"


def rpc(request_id, method, params=None):
    request = {"id": request_id, "method": method}
    if params is not None:
        request["params"] = params
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(15.0)
    try:
        client.connect(SOCKET)
        client.sendall((json.dumps(request) + "\x03").encode("utf-8"))
        data = b""
        while b"\x03" not in data:
            chunk = client.recv(65536)
            if not chunk:
                break
            data += chunk
    finally:
        client.close()
    if not data:
        raise RuntimeError("klippy_response_missing")
    response = json.loads(data.split(b"\x03", 1)[0].decode("utf-8"))
    if response.get("error"):
        raise RuntimeError("klippy_rpc_error:%s" % response["error"])
    return response.get("result", {})


OBJECTS = {
    "webhooks": ["state"],
    "print_stats": ["state", "filename"],
    "extruder": ["target"],
    "heater_bed": ["target"],
    "toolhead": ["homed_axes", "position"],
    "gcode_move": ["homing_origin"],
    "bed_mesh": ["profile_name"],
    "box": None,
    "gcode_macro KCTRL_STATE": None,
    "k1_control_store": None,
}


def snapshot(request_id):
    return rpc(request_id, "objects/query", {"objects": OBJECTS}).get("status", {})


def z_value(status):
    origin = status.get("gcode_move", {}).get("homing_origin", [])
    if len(origin) < 3:
        raise RuntimeError("effective_z_missing")
    return float(origin[2])


def require_safe(status):
    if status.get("webhooks", {}).get("state") != "ready":
        raise RuntimeError("klippy_not_ready")
    if status.get("print_stats", {}).get("state") != "standby":
        raise RuntimeError("printer_not_standby")
    if status.get("print_stats", {}).get("filename") not in (None, ""):
        raise RuntimeError("virtual_sd_job_present")
    if float(status.get("extruder", {}).get("target", -1.0)) != 0.0:
        raise RuntimeError("nozzle_target_not_zero")
    if float(status.get("heater_bed", {}).get("target", -1.0)) != 0.0:
        raise RuntimeError("bed_target_not_zero")
    if status.get("toolhead", {}).get("homed_axes") != "":
        raise RuntimeError("axes_not_released")
    if status.get("bed_mesh", {}).get("profile_name") != EXPECTED_PROFILE:
        raise RuntimeError("best_mesh_not_active")
    runtime = status.get("gcode_macro KCTRL_STATE", {})
    if runtime.get("accepted_z_valid") != 1:
        raise RuntimeError("accepted_z_not_valid")
    if abs(float(runtime.get("accepted_z_offset", 99.0)) - EXPECTED_Z) > 0.0005:
        raise RuntimeError("accepted_z_record_changed")
    if runtime.get("session_active") != 0 or runtime.get("low_moves_armed") != 0:
        raise RuntimeError("z_runtime_not_idle")
    store = status.get("k1_control_store", {})
    record = store.get("record", [])
    if store.get("integrity") != "ok" or len(record) != 17:
        raise RuntimeError("z_store_invalid")
    if int(record[1]) != 1 or abs(float(record[2]) - EXPECTED_Z) > 0.0005:
        raise RuntimeError("persisted_z_changed")
    box = status.get("box", {})
    if box.get("t_command") != "":
        raise RuntimeError("cfs_command_active")
    for name in ("T1", "T2"):
        route = box.get(name, {}).get("filament")
        if route not in (None, "", "None", "none"):
            raise RuntimeError("cfs_route_engaged:%s" % name)


before = snapshot(1)
require_safe(before)
before_position = list(before.get("toolhead", {}).get("position", []))
rpc(2, "gcode/script", {"script": "SET_GCODE_OFFSET Z=-0.04 MOVE=0"})
after = snapshot(3)
require_safe(after)
if abs(z_value(after) - EXPECTED_Z) > 0.0005:
    raise RuntimeError("effective_z_restore_failed")
if list(after.get("toolhead", {}).get("position", [])) != before_position:
    raise RuntimeError("toolhead_position_changed")

print(json.dumps({
    "status": "OK",
    "before_z": z_value(before),
    "after_z": z_value(after),
    "accepted_z": EXPECTED_Z,
    "mesh_profile": EXPECTED_PROFILE,
    "move": False,
    "probe": False,
    "mesh_recalculation": False,
    "heat": False,
    "filament": False,
}, sort_keys=True, separators=(",", ":")))
print("REMOTE_RESTORE_ACCEPTED_Z_NO_MOVE_OK")
