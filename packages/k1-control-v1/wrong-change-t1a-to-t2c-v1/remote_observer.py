"""Passive observer for the one-shot human stock change from T1A to T2C."""

from __future__ import print_function

import hashlib
import json
import math
import os
import sys
import time
from urllib.request import Request, urlopen


MISSION = "G4-K1-CONTROL-WRONG-CHANGE-T1A-TO-T2C-V1"
BASE_URL = "http://127.0.0.1:7125"
TIMEOUT_S = 5.0
POLL_S = 0.5
BEST_PROFILE = "k1_p001_t055_r001_n11x11"
ACCEPTED_Z = -0.04
EXPECTED_HASHES = {
    "/usr/data/printer_data/config/printer.cfg": "a79c8c917d8eee2575939ade4907640c2b2cf7ff59283d28def895b020e127af",
    "/usr/data/printer_data/config/box.cfg": "e7a6b26df58a9fa8e49d3af6845f5a0937a790c8ef494b96ec72fd7392abc7a7",
    "/usr/data/printer_data/config/gcode_macro.cfg": "864fedde88fbb345c220ae5658f7b04779b3981bd78d68eda6fa63c59c79a04f",
    "/usr/data/printer_data/config/k1-control-z-mesh.cfg": "dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113",
    "/usr/data/printer_data/config/k1-control-calibration-path.cfg": "825aadac8679e0d0e9be140cc5ba4e7656b2bff0d197d1683a73d2b5be4e364e",
    "/usr/data/printer_data/config/k1-control-start-sequence-owner-v1.cfg": "678582e808d74f6b720ef3d6b52dc2c443c7a0652a62c484319e2b22fba7b0bc",
}
QUERY = (
    "/printer/objects/query?print_stats=state,filename"
    "&extruder=temperature,target,can_extrude&heater_bed=temperature,target"
    "&toolhead=homed_axes&gcode_move=gcode_position,homing_origin"
    "&bed_mesh=profile_name&box=state,t_command,T1,T2"
    "&filament_switch_sensor+filament_sensor=filament_detected,enabled"
    "&filament_switch_sensor+filament_sensor_2=filament_detected,enabled"
    "&gcode_macro+KCTRL_STATE=accepted_z_valid,accepted_z_offset,low_moves_armed,armed_mesh_profile"
    "&gcode_macro+KCTRL_START_OWNER_STATE=phase,watchdog_armed,manual_clean_token"
)


class ObserverError(RuntimeError):
    pass


def emit(value):
    print(json.dumps(value, sort_keys=True, separators=(",", ":")), flush=True)


def child(mapping, key):
    value = mapping.get(key)
    return value if isinstance(value, dict) else {}


def finite(value, code):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ObserverError(code)
    value = float(value)
    if not math.isfinite(value):
        raise ObserverError(code)
    return value


def fetch_json(path):
    request = Request(BASE_URL + path, method="GET")
    with urlopen(request, timeout=TIMEOUT_S) as response:
        body = response.read()
        code = response.getcode()
    if code != 200:
        raise ObserverError("http_status_%s" % code)
    return json.loads(body.decode("utf-8"))


def hash_file(path):
    if not os.path.isfile(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def configuration_hashes():
    return {path: hash_file(path) for path in EXPECTED_HASHES}


def route(unit_name, unit):
    slot = unit.get("filament")
    if unit.get("state") == "connect" and slot in ("A", "B", "C", "D"):
        return unit_name + slot
    return None


def snapshot(elapsed_s):
    status = child(child(fetch_json(QUERY), "result"), "status")
    if not status:
        raise ObserverError("status_missing")
    box = child(status, "box")
    t1 = child(box, "T1")
    t2 = child(box, "T2")
    routes = [item for item in (route("T1", t1), route("T2", t2)) if item]
    return {
        "kind": "snapshot",
        "elapsed_s": round(elapsed_s, 3),
        "print_state": child(status, "print_stats").get("state"),
        "filename_present": bool(child(status, "print_stats").get("filename")),
        "nozzle": child(status, "extruder"),
        "bed": child(status, "heater_bed"),
        "motion": {
            "homed_axes": child(status, "toolhead").get("homed_axes"),
            "gcode_position": child(status, "gcode_move").get("gcode_position"),
            "homing_origin": child(status, "gcode_move").get("homing_origin"),
        },
        "calibration": {
            "active_profile": child(status, "bed_mesh").get("profile_name"),
            "accepted_z_valid": child(status, "gcode_macro KCTRL_STATE").get("accepted_z_valid"),
            "accepted_z_offset": child(status, "gcode_macro KCTRL_STATE").get("accepted_z_offset"),
            "low_moves_armed": child(status, "gcode_macro KCTRL_STATE").get("low_moves_armed"),
            "armed_mesh_profile": child(status, "gcode_macro KCTRL_STATE").get("armed_mesh_profile"),
        },
        "owner": child(status, "gcode_macro KCTRL_START_OWNER_STATE"),
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


def validate_static(item):
    if item["print_state"] not in ("standby", "complete"):
        raise ObserverError("printer_not_terminal")
    if item["print_state"] == "standby" and item["filename_present"]:
        raise ObserverError("standby_filename_present")
    if item["print_state"] == "complete" and not item["filename_present"]:
        raise ObserverError("complete_filename_missing")
    if item["cfs"]["state"] != "connect" or item["cfs"]["T1_state"] != "connect" or item["cfs"]["T2_state"] != "connect":
        raise ObserverError("cfs_disconnected")
    if item["calibration"]["active_profile"] != BEST_PROFILE:
        raise ObserverError("active_profile_drift")
    if item["calibration"]["accepted_z_valid"] != 1:
        raise ObserverError("accepted_z_invalid")
    if abs(finite(item["calibration"]["accepted_z_offset"], "accepted_z_invalid") - ACCEPTED_Z) > 0.0005:
        raise ObserverError("accepted_z_drift")
    if item["calibration"]["low_moves_armed"] not in (0, 0.0):
        raise ObserverError("low_moves_still_armed")
    if item["owner"].get("phase") != "idle" or item["owner"].get("watchdog_armed") not in (0, 0.0):
        raise ObserverError("start_owner_not_idle")
    finite(item["nozzle"].get("temperature"), "nozzle_temperature_invalid")
    finite(item["nozzle"].get("target"), "nozzle_target_invalid")
    finite(item["bed"].get("temperature"), "bed_temperature_invalid")
    finite(item["bed"].get("target"), "bed_target_invalid")


def validate_preflight(item):
    server = child(fetch_json("/server/info"), "result")
    if server.get("klippy_state") != "ready" or server.get("failed_components") != [] or server.get("warnings") != []:
        raise ObserverError("server_not_clean_ready")
    validate_static(item)
    if item["cfs"]["active_command"] not in (None, ""):
        raise ObserverError("cfs_command_active")
    if item["cfs"]["engaged_routes"] != ["T1A"]:
        raise ObserverError("starting_route_not_T1A")
    if finite(item["nozzle"].get("target"), "nozzle_target_invalid") != 0.0 or finite(item["bed"].get("target"), "bed_target_invalid") != 0.0:
        raise ObserverError("heater_target_not_zero")
    if configuration_hashes() != EXPECTED_HASHES:
        raise ObserverError("configuration_hash_drift")


def preflight():
    item = snapshot(0.0)
    validate_preflight(item)
    emit({
        "kind": "preflight", "mission": MISSION,
        "status": "WRONG_CHANGE_T1A_TO_T2C_PREFLIGHT_OK",
        "snapshot": item,
        "effects": {"gcode": False, "cfs_action": False, "remote_write": False},
    })


def observe(duration_s):
    started = time.monotonic()
    first = snapshot(0.0)
    validate_preflight(first)
    before = configuration_hashes()
    emit({
        "kind": "header", "schema": 1, "mission": MISSION,
        "duration_s": duration_s, "poll_interval_s": POLL_S,
        "operator_action": "stock_ui_change_T1A_to_T2C_once",
        "automatic_retry": False, "hashes_before": before,
        "effects": {"gcode": False, "cfs_action_by_observer": False, "remote_write": False},
    })
    emit(first)
    count = 1
    while time.monotonic() - started < duration_s:
        time.sleep(POLL_S)
        item = snapshot(time.monotonic() - started)
        validate_static(item)
        emit(item)
        count += 1
    after = configuration_hashes()
    emit({
        "kind": "footer", "snapshot_count": count,
        "configuration_unchanged": after == before,
        "hashes_after": after,
        "status": "WRONG_CHANGE_OBSERVATION_OK" if after == before else "WRONG_CHANGE_OBSERVATION_KO_CONFIGURATION_DRIFT",
    })
    return after == before


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) not in (1, 2) or args[0] not in ("preflight", "observe"):
        emit({"status": "INVALID_ARGUMENTS"})
        return 2
    try:
        if args[0] == "preflight":
            preflight()
        else:
            if len(args) != 2:
                raise ObserverError("duration_missing")
            duration_s = float(args[1])
            if not 180.0 <= duration_s <= 600.0:
                raise ObserverError("duration_out_of_bounds")
            if not observe(duration_s):
                return 1
    except Exception as exc:
        emit({"kind": "error", "status": "WRONG_CHANGE_OBSERVATION_KO", "error": "%s:%s" % (type(exc).__name__, exc)})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
