"""Passive observer for the physical print lifecycle checkpoints.

Streamed over SSH stdin; only local Moonraker GET requests and configuration
hash reads are available. There is no command, write or service path.
"""

from __future__ import print_function

import hashlib
import json
import math
import os
import sys
import time
from urllib.request import Request, urlopen


MISSION = "G4-K1-CONTROL-JOB-LIFECYCLE-OBSERVER-V1"
BASE_URL = "http://127.0.0.1:7125"
TIMEOUT_S = 5.0
POLL_INTERVAL_S = 0.25
BEST_PROFILE = "k1_p001_t055_r001_n11x11"
ACCEPTED_Z_OFFSET = -0.04
ALLOWED_CHECKPOINTS = (
    "FULL_CYCLE",
    "TOOL_CHANGE",
    "RUNOUT_RECOVERY",
    "PAUSE_RESUME",
    "CANCEL",
    "NORMAL_END",
    "DISENGAGE",
)
EXPECTED_HASHES = {
    "/usr/data/printer_data/config/printer.cfg": "f88d6b52477592805384fca2b4d7abd00298deecd82227af2fa580085fe26fa2",
    "/usr/data/printer_data/config/box.cfg": "e7a6b26df58a9fa8e49d3af6845f5a0937a790c8ef494b96ec72fd7392abc7a7",
    "/usr/data/printer_data/config/gcode_macro.cfg": "864fedde88fbb345c220ae5658f7b04779b3981bd78d68eda6fa63c59c79a04f",
    "/usr/data/printer_data/config/k1-control-z-mesh.cfg": "dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113",
    "/usr/data/printer_data/config/k1-control-calibration-path.cfg": "825aadac8679e0d0e9be140cc5ba4e7656b2bff0d197d1683a73d2b5be4e364e",
}
QUERY_PATH = (
    "/printer/objects/query?"
    "print_stats=state,total_duration,print_duration,filament_used,power_loss,z_pos"
    "&pause_resume=is_paused"
    "&virtual_sdcard=progress,is_active,file_position,file_size,first_layer_stop,layer,layer_count,run_dis"
    "&idle_timeout=state,printing_time"
    "&extruder=temperature,target,can_extrude"
    "&heater_bed=temperature,target"
    "&toolhead=homed_axes,position"
    "&gcode_move=gcode_position,homing_origin"
    "&bed_mesh=profile_name"
    "&box=state,t_command,T1,T2"
    "&filament_switch_sensor+filament_sensor=filament_detected,enabled"
    "&filament_switch_sensor+filament_sensor_2=filament_detected,enabled"
    "&gcode_macro+KCTRL_STATE=accepted_z_valid,accepted_z_offset"
)


class ObserverError(RuntimeError):
    pass


def child(mapping, key):
    value = mapping.get(key)
    return value if isinstance(value, dict) else {}


def finite(value, code):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ObserverError(code)
    result = float(value)
    if not math.isfinite(result):
        raise ObserverError(code)
    return result


def fetch_json(path):
    request = Request(BASE_URL + path, method="GET")
    with urlopen(request, timeout=TIMEOUT_S) as response:
        body = response.read()
        status_code = response.getcode()
    if status_code != 200:
        raise ObserverError("http_status_%s" % status_code)
    return json.loads(body.decode("utf-8"))


def hash_file(path):
    if not os.path.isfile(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def configuration_hashes():
    return {path: hash_file(path) for path in EXPECTED_HASHES}


def route_for(unit_name, unit):
    slot = unit.get("filament")
    if unit.get("state") == "connect" and slot in ("A", "B", "C", "D"):
        return "%s%s" % (unit_name, slot)
    return None


def safe_snapshot(elapsed_s, payload):
    status = child(child(payload, "result"), "status")
    if not status:
        raise ObserverError("status_missing")
    box = child(status, "box")
    t1 = child(box, "T1")
    t2 = child(box, "T2")
    routes = [route for route in (route_for("T1", t1), route_for("T2", t2)) if route]
    virtual_sd = child(status, "virtual_sdcard")
    print_stats = child(status, "print_stats")
    return {
        "kind": "snapshot",
        "elapsed_s": round(elapsed_s, 3),
        "job": {
            "print_state": print_stats.get("state"),
            "total_duration_s": print_stats.get("total_duration"),
            "print_duration_s": print_stats.get("print_duration"),
            "filament_used_mm": print_stats.get("filament_used"),
            "power_loss": print_stats.get("power_loss"),
            "reported_z_mm": print_stats.get("z_pos"),
            "is_paused": child(status, "pause_resume").get("is_paused"),
            "virtual_sd_active": virtual_sd.get("is_active"),
            "progress": virtual_sd.get("progress"),
            "file_position": virtual_sd.get("file_position"),
            "file_size": virtual_sd.get("file_size"),
            "first_layer_stop": virtual_sd.get("first_layer_stop"),
            "layer": virtual_sd.get("layer"),
            "layer_count": virtual_sd.get("layer_count"),
            "run_distance_mm": virtual_sd.get("run_dis"),
            "idle_state": child(status, "idle_timeout").get("state"),
            "idle_printing_time_s": child(status, "idle_timeout").get("printing_time"),
        },
        "heaters": {
            "nozzle_temperature_c": child(status, "extruder").get("temperature"),
            "nozzle_target_c": child(status, "extruder").get("target"),
            "nozzle_can_extrude": child(status, "extruder").get("can_extrude"),
            "bed_temperature_c": child(status, "heater_bed").get("temperature"),
            "bed_target_c": child(status, "heater_bed").get("target"),
        },
        "motion": {
            "homed_axes": child(status, "toolhead").get("homed_axes"),
            "toolhead_position": child(status, "toolhead").get("position"),
            "gcode_position": child(status, "gcode_move").get("gcode_position"),
            "homing_origin": child(status, "gcode_move").get("homing_origin"),
        },
        "calibration": {
            "active_profile": child(status, "bed_mesh").get("profile_name"),
            "accepted_z_valid": child(status, "gcode_macro KCTRL_STATE").get("accepted_z_valid"),
            "accepted_z_offset": child(status, "gcode_macro KCTRL_STATE").get("accepted_z_offset"),
        },
        "cfs": {
            "state": box.get("state"),
            "active_command": box.get("t_command"),
            "T1_state": t1.get("state"),
            "T2_state": t2.get("state"),
            "engaged_routes": routes,
        },
        "sensors": {
            "head": child(status, "filament_switch_sensor filament_sensor").get("filament_detected"),
            "after_cutter": child(status, "filament_switch_sensor filament_sensor_2").get("filament_detected"),
        },
    }


def validate_preflight(server, snapshot, hashes):
    if server.get("klippy_state") != "ready":
        raise ObserverError("klippy_not_ready")
    if server.get("failed_components") != [] or server.get("warnings") != []:
        raise ObserverError("server_not_clean")
    if snapshot["job"]["print_state"] not in ("standby", "printing", "paused"):
        raise ObserverError("print_state_not_observable")
    if snapshot["cfs"]["state"] != "connect":
        raise ObserverError("cfs_root_disconnected")
    if snapshot["cfs"]["T1_state"] != "connect" or snapshot["cfs"]["T2_state"] != "connect":
        raise ObserverError("cfs_unit_disconnected")
    if snapshot["cfs"]["active_command"] not in (None, ""):
        raise ObserverError("cfs_command_already_active")
    if snapshot["motion"]["homed_axes"] != "xyz":
        raise ObserverError("axes_not_homed_xyz")
    if snapshot["calibration"]["active_profile"] != BEST_PROFILE:
        raise ObserverError("active_profile_drift")
    if snapshot["calibration"]["accepted_z_valid"] != 1:
        raise ObserverError("accepted_z_invalid")
    accepted_z = finite(snapshot["calibration"]["accepted_z_offset"], "accepted_z_invalid")
    if abs(accepted_z - ACCEPTED_Z_OFFSET) > 0.0005:
        raise ObserverError("accepted_z_drift")
    for key in ("nozzle_temperature_c", "nozzle_target_c", "bed_temperature_c", "bed_target_c"):
        finite(snapshot["heaters"][key], "%s_invalid" % key)
    if hashes != EXPECTED_HASHES:
        raise ObserverError("configuration_hash_drift")


def run(duration_s, checkpoint):
    started = time.monotonic()
    hashes_before = configuration_hashes()
    server = child(fetch_json("/server/info"), "result")
    first = safe_snapshot(0.0, fetch_json(QUERY_PATH))
    validate_preflight(server, first, hashes_before)
    print(json.dumps({
        "kind": "header",
        "schema": 1,
        "mission": MISSION,
        "checkpoint": checkpoint,
        "duration_s": duration_s,
        "poll_interval_s": POLL_INTERVAL_S,
        "hashes_before": hashes_before,
        "effects": {"gcode": False, "remote_write": False, "service_action": False},
    }, sort_keys=True, separators=(",", ":")), flush=True)
    print(json.dumps(first, sort_keys=True, separators=(",", ":")), flush=True)
    count = 1
    while time.monotonic() - started < duration_s:
        time.sleep(POLL_INTERVAL_S)
        elapsed = time.monotonic() - started
        print(json.dumps(safe_snapshot(elapsed, fetch_json(QUERY_PATH)), sort_keys=True, separators=(",", ":")), flush=True)
        count += 1
    hashes_after = configuration_hashes()
    unchanged = hashes_after == hashes_before
    print(json.dumps({
        "kind": "footer",
        "status": "JOB_LIFECYCLE_OBSERVATION_OK" if unchanged else "JOB_LIFECYCLE_OBSERVATION_KO_CONFIGURATION_DRIFT",
        "snapshot_count": count,
        "hashes_after": hashes_after,
        "configuration_unchanged": unchanged,
    }, sort_keys=True, separators=(",", ":")), flush=True)
    return unchanged


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 2:
        print(json.dumps({"status": "INVALID_ARGUMENTS"}, sort_keys=True))
        return 2
    checkpoint = arguments[0]
    if checkpoint not in ALLOWED_CHECKPOINTS:
        print(json.dumps({"status": "INVALID_CHECKPOINT"}, sort_keys=True))
        return 2
    try:
        duration_s = float(arguments[1])
    except ValueError:
        print(json.dumps({"status": "INVALID_DURATION"}, sort_keys=True))
        return 2
    if not 5.0 <= duration_s <= 900.0:
        print(json.dumps({"status": "INVALID_DURATION"}, sort_keys=True))
        return 2
    try:
        unchanged = run(duration_s, checkpoint)
    except Exception as exc:
        print(json.dumps({"status": "JOB_LIFECYCLE_OBSERVATION_KO", "error": "%s:%s" % (type(exc).__name__, exc)}, sort_keys=True))
        return 1
    return 0 if unchanged else 1


if __name__ == "__main__":
    raise SystemExit(main())
