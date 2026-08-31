#!/usr/bin/env python3
"""Valide l'activation au repos sans appeler aucune entree d'effet."""

import json
import os
import socket
from urllib.request import urlopen


SOCKET = "/tmp/klippy_uds"
BASE_URL = "http://127.0.0.1:7125"
RUN_PATH = "/usr/data/k1-control-v1/state/stock-derived-cycle-state.json"
SELECTION_PATH = "/usr/data/k1-control-v1/state/stock-derived-selection.json"


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


def get_json(path):
    response = urlopen(BASE_URL + path, timeout=10.0)
    try:
        return json.loads(response.read().decode("utf-8"))
    finally:
        response.close()


objects = {
    "webhooks": ["state"],
    "print_stats": ["state", "filename"],
    "extruder": ["target"],
    "heater_bed": ["target"],
    "toolhead": ["homed_axes"],
    "bed_mesh": ["profile_name"],
    "gcode_move": ["homing_origin"],
    "box": None,
    "gcode_macro KCTRL_START_OWNER_STATE": None,
    "k1_control_cfs_startup_exclusion": None,
    "k1_control_cfs_direct_owner": None,
    "k1_control_cfs_runout_owner": None,
    "k1_control_stock_cycle_owner": None,
    "k1_control_stock_geometry_handoff": None,
}
result = rpc(1, "objects/query", {"objects": objects})
status = result.get("status", {})

startup = status.get("k1_control_cfs_startup_exclusion", {})
direct = status.get("k1_control_cfs_direct_owner", {})
runout = status.get("k1_control_cfs_runout_owner", {})
cycle = status.get("k1_control_stock_cycle_owner", {})
geometry = status.get("k1_control_stock_geometry_handoff", {})
box = status.get("box", {})

if status.get("webhooks", {}).get("state") != "ready":
    raise RuntimeError("klippy_not_ready")
if status.get("print_stats", {}).get("state") != "standby":
    raise RuntimeError("printer_not_standby")
if float(status.get("extruder", {}).get("target", -1.0)) != 0.0:
    raise RuntimeError("nozzle_target_not_zero")
if float(status.get("heater_bed", {}).get("target", -1.0)) != 0.0:
    raise RuntimeError("bed_target_not_zero")
if status.get("toolhead", {}).get("homed_axes") != "":
    raise RuntimeError("axes_not_released")
if status.get("bed_mesh", {}).get("profile_name") != "k1_p001_t055_r001_n11x11":
    raise RuntimeError("best_mesh_not_active")
origin = status.get("gcode_move", {}).get("homing_origin", [None, None, None])
if len(origin) < 3 or abs(float(origin[2]) + 0.04) > 0.0005:
    raise RuntimeError("accepted_z_changed")
if box.get("auto_refill") != 0 or box.get("t_command") != "" or box.get("enable") != 1:
    raise RuntimeError("stock_exclusion_not_proven")
for unit in ("T1", "T2"):
    if box.get(unit, {}).get("state") != "connect":
        raise RuntimeError("cfs_not_connected:%s" % unit)

expected_startup = {
    "enabled": True,
    "ready_verified": True,
    "captured_policy_handler": True,
    "last_failure": None,
    "automatic_retry_count": 0,
    "heat_command_count": 0,
    "motion_command_count": 0,
    "extrusion_command_count": 0,
    "cfs_frame_count": 0,
    "other_stock_handler_call_count": 0,
}
for key, value in expected_startup.items():
    if startup.get(key) != value:
        raise RuntimeError("startup_status_invalid:%s" % key)
if startup.get("policy_attempted") is not True:
    raise RuntimeError("startup_policy_was_not_attempted")
if int(startup.get("ready_poll_count", 0)) < 1:
    raise RuntimeError("startup_ready_poll_missing")
if float(startup.get("ready_deadline", 0.0)) <= 0.0:
    raise RuntimeError("startup_ready_deadline_missing")
if startup.get("policy_call_count", 0) + startup.get("policy_already_zero_count", 0) != 1:
    raise RuntimeError("startup_policy_call_count_invalid")

expected_direct = {
    "enabled": True,
    "phase": "idle",
    "active_route": None,
    "failure_code": None,
    "transport_bound": False,
    "stock_commands_blocked": True,
    "automatic_retry_count": 0,
    "frames_sent_count": 0,
    "tip_pull_count": 0,
    "load_count": 0,
    "unload_count": 0,
}
for key, value in expected_direct.items():
    if direct.get(key) != value:
        raise RuntimeError("direct_status_invalid:%s" % key)

expected_runout = {
    "enabled": True,
    "ready_verified": True,
    "stock_handler_isolated": True,
    "public_box_check_owned": True,
    "armed": False,
    "event_seq": 0,
    "consumed_seq": 0,
    "last_route": None,
    "last_failure": None,
    "latch_count": 0,
    "arm_count": 0,
    "disarm_count": 0,
    "logical_release_count": 0,
    "claimed_effect_count": 0,
    "automatic_retry_count": 0,
    "cfs_frame_count": 0,
    "motor_effect_count": 0,
    "heater_effect_count": 0,
    "motion_effect_count": 0,
    "probe_count": 0,
    "mesh_recalculation_count": 0,
}
for key, value in expected_runout.items():
    if runout.get(key) != value:
        raise RuntimeError("runout_status_invalid:%s" % key)

for label, value in (("cycle", cycle), ("geometry", geometry)):
    if value.get("enabled") is not True:
        raise RuntimeError("component_not_active:%s" % label)
    for key in (
        "effect_count", "handoff_count", "command_count", "claimed_effect_count",
        "heat_command_count", "motion_command_count", "probe_command_count",
        "mesh_recalculation_count", "cfs_frame_count",
    ):
        if key in value and value.get(key) != 0:
            raise RuntimeError("component_effect_history:%s:%s" % (label, key))

moon_response = get_json("/machine/k1_control/stock-cycle/status")
moon = moon_response.get("result", moon_response)
expected_moon = {
    "enabled": True,
    "phase": "idle",
    "pending_ticket": None,
    "active_route": None,
    "filament_loaded": False,
    "effect_dispatch_count": 0,
    "automatic_retry_count": 0,
    "camera_pass_count": 0,
    "camera_fail_count": 0,
    "state_write_count": 0,
    "stock_BOX_effect_count": 0,
    "post_filament_probe_count": 0,
    "mesh_recalculation_count": 0,
    "run_state_present": False,
}
for key, value in expected_moon.items():
    if moon.get(key) != value:
        raise RuntimeError("moonraker_status_invalid:%s" % key)

if os.path.exists(RUN_PATH) or os.path.exists(SELECTION_PATH):
    raise RuntimeError("activation_created_persistent_state")

safe = {
    "startup": startup,
    "direct": direct,
    "runout": runout,
    "cycle": cycle,
    "geometry": geometry,
    "moonraker": moon,
    "run_state_exists": False,
    "selection_state_exists": False,
}
print(json.dumps(safe, sort_keys=True, separators=(",", ":")))
print("REMOTE_STOCK_DERIVED_CYCLE_ACTIVATION_IDLE_VALIDATE_OK")
