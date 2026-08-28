"""Bounded live gate for the first physical KEEP_CORRECT_T1A owned start."""

from __future__ import print_function

import hashlib
import json
import math
import os
import sys
import time
from urllib.parse import quote
from urllib.request import Request, urlopen


MISSION = "G4-K1-CONTROL-START-SEQUENCE-OWNER-PHYSICAL-KEEP-CORRECT-T1A-V1"
BASE_URL = "http://127.0.0.1:7125"
TIMEOUT_S = 5.0
POLL_S = 0.5
BEST_PROFILE = "k1_p001_t055_r001_n11x11"
ACCEPTED_Z = -0.04
GCODE_NAME = "K1-START-OWNER-T1A-2LAYER.gcode"
EXPECTED_HASHES = {
    "/usr/data/printer_data/config/printer.cfg": "a79c8c917d8eee2575939ade4907640c2b2cf7ff59283d28def895b020e127af",
    "/usr/data/printer_data/config/box.cfg": "e7a6b26df58a9fa8e49d3af6845f5a0937a790c8ef494b96ec72fd7392abc7a7",
    "/usr/data/printer_data/config/gcode_macro.cfg": "864fedde88fbb345c220ae5658f7b04779b3981bd78d68eda6fa63c59c79a04f",
    "/usr/data/printer_data/config/k1-control-z-mesh.cfg": "dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113",
    "/usr/data/printer_data/config/k1-control-calibration-path.cfg": "825aadac8679e0d0e9be140cc5ba4e7656b2bff0d197d1683a73d2b5be4e364e",
    "/usr/data/printer_data/config/k1-control-start-sequence-owner-v1.cfg": "25291e1534f0ba100d3171b983796089a24cd49fdfcef76817406d325e6d8e03",
}
QUERY = (
    "/printer/objects/query?print_stats=state,filename,message,total_duration,print_duration"
    "&extruder=temperature,target,can_extrude&heater_bed=temperature,target"
    "&toolhead=homed_axes,position&gcode_move=gcode_position,homing_origin"
    "&bed_mesh=profile_name&box=state,t_command,T1,T2"
    "&gcode_macro+KCTRL_STATE=accepted_z_valid,accepted_z_offset,low_moves_armed,armed_mesh_profile"
    "&gcode_macro+KCTRL_START_OWNER_STATE=phase,watchdog_armed,abort_latched,manual_clean_token"
)


class GateError(RuntimeError):
    pass


def emit(value):
    print(json.dumps(value, sort_keys=True, separators=(",", ":")), flush=True)


def child(mapping, key):
    value = mapping.get(key)
    return value if isinstance(value, dict) else {}


def finite(value, code):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GateError(code)
    value = float(value)
    if not math.isfinite(value):
        raise GateError(code)
    return value


def request_json(path, method="GET", payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(BASE_URL + path, data=data, headers=headers, method=method)
    with urlopen(request, timeout=TIMEOUT_S) as response:
        body = response.read()
        code = response.getcode()
    if code != 200:
        raise GateError("http_status_%s" % code)
    return json.loads(body.decode("utf-8")) if body else {}


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


def hashes():
    return {path: hash_file(path) for path in EXPECTED_HASHES}


def route(unit_name, unit):
    slot = unit.get("filament")
    if unit.get("state") == "connect" and slot in ("A", "B", "C", "D"):
        return unit_name + slot
    return None


def snapshot(elapsed):
    status = child(child(request_json(QUERY), "result"), "status")
    if not status:
        raise GateError("status_missing")
    box = child(status, "box")
    t1 = child(box, "T1")
    t2 = child(box, "T2")
    routes = [item for item in (route("T1", t1), route("T2", t2)) if item]
    return {
        "kind": "snapshot",
        "elapsed_s": round(elapsed, 3),
        "print": child(status, "print_stats"),
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
    }


def validate_server():
    server = child(request_json("/server/info"), "result")
    if server.get("klippy_state") != "ready":
        raise GateError("klippy_not_ready")
    if server.get("failed_components") != [] or server.get("warnings") != []:
        raise GateError("server_not_clean")


def validate_common(item):
    if item["cfs"]["state"] != "connect":
        raise GateError("cfs_root_disconnected")
    if item["cfs"]["T1_state"] != "connect" or item["cfs"]["T2_state"] != "connect":
        raise GateError("cfs_unit_disconnected")
    if item["cfs"]["active_command"] not in (None, ""):
        raise GateError("cfs_command_active")
    if item["cfs"]["engaged_routes"] != ["T1A"]:
        raise GateError("t1a_route_not_unique")
    if item["calibration"]["accepted_z_valid"] != 1:
        raise GateError("accepted_z_invalid")
    if abs(finite(item["calibration"]["accepted_z_offset"], "accepted_z_invalid") - ACCEPTED_Z) > 0.0005:
        raise GateError("accepted_z_drift")
    if finite(item["nozzle"].get("target"), "nozzle_target_invalid") > 200.5:
        raise GateError("nozzle_target_above_reviewed_limit")
    if finite(item["bed"].get("target"), "bed_target_invalid") > 55.5:
        raise GateError("bed_target_above_reviewed_limit")


def validate_preflight(item, expected_gcode_sha):
    validate_server()
    validate_common(item)
    if item["print"].get("state") != "standby" or item["print"].get("filename"):
        raise GateError("printer_not_standby")
    if finite(item["nozzle"].get("target"), "nozzle_target_invalid") != 0.0:
        raise GateError("nozzle_target_not_zero")
    if finite(item["bed"].get("target"), "bed_target_invalid") != 0.0:
        raise GateError("bed_target_not_zero")
    if item["motion"]["homed_axes"] not in (None, ""):
        raise GateError("axes_not_released")
    if item["calibration"]["active_profile"] != BEST_PROFILE:
        raise GateError("active_profile_drift")
    if item["owner"].get("phase") != "idle" or item["owner"].get("watchdog_armed") not in (0, 0.0):
        raise GateError("start_owner_not_idle")
    if hashes() != EXPECTED_HASHES:
        raise GateError("configuration_hash_drift")
    gcode_path = "/usr/data/printer_data/gcodes/" + GCODE_NAME
    if expected_gcode_sha != "none" and hash_file(gcode_path) != expected_gcode_sha:
        raise GateError("gcode_hash_mismatch")


def validate_terminal(item):
    validate_common(item)
    if item["print"].get("state") not in ("complete", "standby"):
        raise GateError("print_not_terminal")
    if finite(item["nozzle"].get("target"), "nozzle_target_invalid") != 0.0:
        raise GateError("nozzle_target_not_zero_after_run")
    if finite(item["bed"].get("target"), "bed_target_invalid") != 0.0:
        raise GateError("bed_target_not_zero_after_run")
    if item["calibration"]["active_profile"] != BEST_PROFILE:
        raise GateError("active_profile_drift_after_run")
    if item["calibration"]["low_moves_armed"] not in (0, 0.0):
        raise GateError("low_moves_still_armed_after_run")
    if item["calibration"]["armed_mesh_profile"] not in (None, "", "none"):
        raise GateError("armed_mesh_profile_not_cleared_after_run")
    if item["owner"].get("phase") != "idle":
        raise GateError("start_owner_not_idle_after_run")
    if item["owner"].get("watchdog_armed") not in (0, 0.0):
        raise GateError("watchdog_still_armed_after_run")
    if item["owner"].get("manual_clean_token") not in (0, 0.0):
        raise GateError("manual_clean_token_not_cleared_after_run")
    if item["motion"]["homed_axes"] not in (None, ""):
        raise GateError("axes_not_released_after_run")


def preflight(expected_gcode_sha):
    item = snapshot(0.0)
    validate_preflight(item, expected_gcode_sha)
    emit({
        "kind": "preflight",
        "mission": MISSION,
        "status": "KEEP_CORRECT_T1A_PHYSICAL_PREFLIGHT_OK",
        "gcode_sha256": None if expected_gcode_sha == "none" else expected_gcode_sha,
        "snapshot": item,
        "effects": {"gcode": False, "print_start": False, "remote_write": False},
    })


def safety_stop(reason):
    actions = []
    try:
        current = snapshot(0.0)
        if current["print"].get("state") in ("printing", "paused"):
            request_json("/printer/print/cancel", method="POST")
            actions.append("cancel_print_once")
    except Exception as exc:
        actions.append("cancel_check_failed:%s" % type(exc).__name__)
    try:
        request_json("/printer/gcode/script", method="POST", payload={"script": "TURN_OFF_HEATERS\nM84"})
        actions.append("turn_off_heaters_and_release_axes_once")
    except Exception as exc:
        actions.append("safety_gcode_failed:%s" % type(exc).__name__)
    emit({"kind": "safety_stop", "reason": reason, "actions": actions})


def execute(expected_gcode_sha, duration_s):
    start = time.monotonic()
    first = snapshot(0.0)
    validate_preflight(first, expected_gcode_sha)
    emit({
        "kind": "header", "mission": MISSION, "schema": 1,
        "gcode_name": GCODE_NAME, "gcode_sha256": expected_gcode_sha,
        "maximum_duration_s": duration_s, "automatic_retry": False,
        "allowed_effects": ["manual_clean_token_once", "print_start_once", "safety_stop_once_on_failure"],
        "hashes_before": hashes(),
    })
    emit(first)
    request_json("/printer/gcode/script", method="POST", payload={"script": "KCTRL_CONFIRM_MANUAL_NOZZLE_CLEAN_V1"})
    token = snapshot(time.monotonic() - start)
    if token["owner"].get("phase") != "manual_clean_confirmed" or token["owner"].get("manual_clean_token") != 1:
        raise GateError("manual_clean_token_not_confirmed")
    emit({"kind": "effect", "effect": "manual_clean_token_once"})
    emit(token)
    request_json("/printer/print/start?filename=" + quote(GCODE_NAME), method="POST")
    emit({"kind": "effect", "effect": "print_start_once", "filename": GCODE_NAME})
    seen_printing = False
    seen_terminal = False
    last = token
    while time.monotonic() - start <= duration_s:
        time.sleep(POLL_S)
        last = snapshot(time.monotonic() - start)
        validate_common(last)
        emit(last)
        state = last["print"].get("state")
        if state == "printing":
            seen_printing = True
        if seen_printing and state in ("complete", "standby"):
            seen_terminal = True
            break
        if state in ("error", "cancelled"):
            raise GateError("print_terminal_%s" % state)
    if not seen_printing:
        raise GateError("printing_state_not_observed")
    if not seen_terminal:
        raise GateError("terminal_state_not_observed")
    deadline = time.monotonic() + 90.0
    while time.monotonic() < deadline:
        if finite(last["nozzle"].get("target"), "nozzle_target_invalid") == 0.0 and finite(last["bed"].get("target"), "bed_target_invalid") == 0.0:
            break
        time.sleep(POLL_S)
        last = snapshot(time.monotonic() - start)
        validate_common(last)
        emit(last)
    final_hashes = hashes()
    if final_hashes != EXPECTED_HASHES:
        raise GateError("configuration_hash_drift_after_run")
    validate_terminal(last)
    emit({
        "kind": "footer", "status": "KEEP_CORRECT_T1A_PHYSICAL_AUTOMATION_OK",
        "automatic_retry": False, "hashes_after": final_hashes, "final_snapshot": last,
    })


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) not in (2, 3) or args[0] not in ("preflight", "execute"):
        emit({"status": "INVALID_ARGUMENTS"})
        return 2
    action, expected_sha = args[:2]
    try:
        if action == "preflight":
            preflight(expected_sha)
        else:
            if len(args) != 3:
                raise GateError("duration_missing")
            duration_s = float(args[2])
            if not 300.0 <= duration_s <= 1200.0:
                raise GateError("duration_out_of_bounds")
            execute(expected_sha, duration_s)
    except Exception as exc:
        error = "%s:%s" % (type(exc).__name__, exc)
        if action == "execute":
            safety_stop(error)
        emit({"kind": "error", "status": "KEEP_CORRECT_T1A_PHYSICAL_KO", "error": error, "automatic_retry": False})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
