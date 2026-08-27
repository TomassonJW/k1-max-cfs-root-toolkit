from __future__ import print_function

import hashlib
import json
import math
import os
import re
import socket
import sys
import time
from urllib.request import Request, urlopen


MISSION = "G4-K1-CONTROL-CLEAN-AND-REFERENCE-V1"
BASE_URL = "http://127.0.0.1:7125"
TIMEOUT_S = 5.0
BEST_PROFILE = "k1_p001_t055_r001_n11x11"
BEST_PROFILE_SHA256 = "58fd96c55129bf7a17ba890d309cb3cd5e2926ec271d735b60392f8369da0a61"
REFERENCE_NOZZLE_C = 140.0
REFERENCE_BED_C = 55.0
BRUSH_CONTACT_Z_MM = 32.0
BRUSH_RELEASE_Z_MM = 34.0
HOT_ROUND_TRIPS = 6
COOLING_TIMEOUT_S = 300.0
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")

EXPECTED_HASHES = {
    "/usr/data/printer_data/config/printer.cfg": "f88d6b52477592805384fca2b4d7abd00298deecd82227af2fa580085fe26fa2",
    "/usr/data/printer_data/config/box.cfg": "e7a6b26df58a9fa8e49d3af6845f5a0937a790c8ef494b96ec72fd7392abc7a7",
    "/usr/data/printer_data/config/gcode_macro.cfg": "864fedde88fbb345c220ae5658f7b04779b3981bd78d68eda6fa63c59c79a04f",
    "/usr/data/printer_data/config/k1-control-z-mesh.cfg": "dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113",
    "/usr/data/printer_data/config/k1-control-calibration-path.cfg": "825aadac8679e0d0e9be140cc5ba4e7656b2bff0d197d1683a73d2b5be4e364e",
}

QUERY_PATH = (
    "/printer/objects/query?"
    "print_stats=state,filename"
    "&extruder=temperature,target,can_extrude"
    "&heater_bed=temperature,target"
    "&toolhead=homed_axes,position"
    "&gcode_move=gcode_position,homing_origin"
    "&bed_mesh=profile_name,probed_matrix,profiles"
    "&box=state,t_command,T1,T2"
    "&gcode_macro+KCTRL_STATE=ready,session_active,accepted_z_valid,accepted_z_offset,low_moves_armed"
    "&k1_control_store=integrity"
    "&gcode_macro+KCTRL_CAL_PATH_STATE=phase,motion_armed,commit_ready"
)


class GateError(RuntimeError):
    pass


def child(mapping, key):
    value = mapping.get(key)
    return value if isinstance(value, dict) else {}


def finite(value, code):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GateError(code)
    number = float(value)
    if not math.isfinite(number):
        raise GateError(code)
    return number


def matrix_summary(value):
    if not isinstance(value, list) or not value:
        return {"rows": 0, "columns": [], "sha256": None}
    columns = [len(row) if isinstance(row, list) else -1 for row in value]
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return {
        "rows": len(value),
        "columns": columns,
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


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


def fetch_json(path):
    request = Request(BASE_URL + path, method="GET")
    with urlopen(request, timeout=TIMEOUT_S) as response:
        body = response.read()
        status_code = response.getcode()
    if status_code != 200:
        raise GateError("http_status_%s" % status_code)
    return json.loads(body.decode("utf-8"))


def profile_summary(status):
    profiles = child(status, "bed_mesh").get("profiles")
    if not isinstance(profiles, dict):
        raise GateError("mesh_profiles_missing")
    profile = profiles.get(BEST_PROFILE)
    if not isinstance(profile, dict):
        raise GateError("best_profile_missing")
    return matrix_summary(profile.get("points"))


def capture_snapshot():
    server = child(fetch_json("/server/info"), "result")
    status = child(child(fetch_json(QUERY_PATH), "result"), "status")
    if not server or not status:
        raise GateError("live_response_incomplete")
    bed_mesh = child(status, "bed_mesh")
    box = child(status, "box")
    runtime = child(status, "gcode_macro KCTRL_STATE")
    path_state = child(status, "gcode_macro KCTRL_CAL_PATH_STATE")
    return {
        "server": {
            "klippy_state": server.get("klippy_state"),
            "failed_components": server.get("failed_components"),
            "warnings": server.get("warnings"),
        },
        "print": {
            "state": child(status, "print_stats").get("state"),
            "filename_present": bool(child(status, "print_stats").get("filename")),
        },
        "heaters": {
            "extruder_temperature": child(status, "extruder").get("temperature"),
            "extruder_target": child(status, "extruder").get("target"),
            "bed_temperature": child(status, "heater_bed").get("temperature"),
            "bed_target": child(status, "heater_bed").get("target"),
        },
        "toolhead": {
            "homed_axes": child(status, "toolhead").get("homed_axes"),
            "position": child(status, "toolhead").get("position"),
            "gcode_position": child(status, "gcode_move").get("gcode_position"),
            "homing_origin": child(status, "gcode_move").get("homing_origin"),
        },
        "bed_mesh": {
            "profile_name": bed_mesh.get("profile_name"),
            "probed_matrix": matrix_summary(bed_mesh.get("probed_matrix")),
            "best_profile": profile_summary(status),
        },
        "box": {
            "state": box.get("state"),
            "t_command": box.get("t_command"),
            "T1": {"state": child(box, "T1").get("state"), "filament": child(box, "T1").get("filament")},
            "T2": {"state": child(box, "T2").get("state"), "filament": child(box, "T2").get("filament")},
        },
        "runtime": {
            key: runtime.get(key)
            for key in ("ready", "session_active", "accepted_z_valid", "accepted_z_offset", "low_moves_armed")
        },
        "store": {"integrity": child(status, "k1_control_store").get("integrity")},
        "calibration_path": {
            key: path_state.get(key)
            for key in ("phase", "motion_armed", "commit_ready")
        },
        "hashes": {path: hash_file(path) for path in EXPECTED_HASHES},
    }


def require_equal(actual, expected, code):
    if actual != expected:
        raise GateError(code)


def validate_base(snapshot, require_homed=True):
    require_equal(snapshot["server"]["klippy_state"], "ready", "klippy_not_ready")
    require_equal(snapshot["server"]["failed_components"], [], "failed_components")
    require_equal(snapshot["server"]["warnings"], [], "server_warnings")
    require_equal(snapshot["print"]["state"], "standby", "printer_not_standby")
    require_equal(snapshot["print"]["filename_present"], False, "print_filename_present")
    if require_homed:
        require_equal(snapshot["toolhead"]["homed_axes"], "xyz", "axes_not_homed_xyz")
    require_equal(snapshot["runtime"]["ready"], 1, "runtime_not_ready")
    require_equal(snapshot["runtime"]["session_active"], 0, "runtime_session_active")
    require_equal(snapshot["runtime"]["accepted_z_valid"], 1, "accepted_z_invalid")
    if abs(float(snapshot["runtime"]["accepted_z_offset"]) - (-0.04)) > 0.0005:
        raise GateError("accepted_z_drift")
    require_equal(snapshot["runtime"]["low_moves_armed"], 0, "low_moves_armed")
    require_equal(snapshot["store"]["integrity"], "ok", "store_not_ok")
    if snapshot["calibration_path"]["phase"] not in ("idle", "committed", "cancelled"):
        raise GateError("calibration_path_open")
    require_equal(snapshot["calibration_path"]["motion_armed"], 0, "calibration_motion_armed")
    require_equal(snapshot["calibration_path"]["commit_ready"], 0, "calibration_commit_ready")
    require_equal(snapshot["box"]["state"], "connect", "cfs_root_disconnected")
    require_equal(snapshot["box"]["t_command"], "", "cfs_command_active")
    for unit in ("T1", "T2"):
        require_equal(snapshot["box"][unit]["state"], "connect", "%s_disconnected" % unit)
        if snapshot["box"][unit]["filament"] not in (None, "None"):
            raise GateError("cfs_route_engaged")
    require_equal(snapshot["hashes"], EXPECTED_HASHES, "configuration_hash_drift")
    expected_mesh = {"rows": 11, "columns": [11] * 11, "sha256": BEST_PROFILE_SHA256}
    require_equal(snapshot["bed_mesh"]["best_profile"], expected_mesh, "best_profile_drift")
    require_equal(snapshot["bed_mesh"]["profile_name"], BEST_PROFILE, "active_profile_drift")
    require_equal(snapshot["bed_mesh"]["probed_matrix"], expected_mesh, "active_matrix_drift")


def validate_position(snapshot, expected, code):
    actual = snapshot["toolhead"]["gcode_position"]
    if not isinstance(actual, list) or len(actual) < 3:
        raise GateError("gcode_position_missing")
    for index in range(3):
        if abs(float(actual[index]) - float(expected[index])) > 0.03:
            raise GateError("%s_axis_%s" % (code, index))


def validate_known_clean_cycle_start(snapshot):
    actual = snapshot["toolhead"]["gcode_position"]
    if not isinstance(actual, list) or len(actual) < 3:
        raise GateError("gcode_position_missing")
    accepted = ([203.0, 273.0, 32.0], [204.5, 304.5, 35.0])
    if not any(all(abs(float(actual[index]) - expected[index]) <= 0.03 for index in range(3)) for expected in accepted):
        raise GateError("clean_cycle_start_position_unknown")


def validate_targets(snapshot, nozzle, bed, actual_window=None):
    if abs(finite(snapshot["heaters"]["extruder_target"], "extruder_target_invalid") - nozzle) > 0.01:
        raise GateError("extruder_target_drift")
    if abs(finite(snapshot["heaters"]["bed_target"], "bed_target_invalid") - bed) > 0.01:
        raise GateError("bed_target_drift")
    if actual_window is not None:
        nozzle_actual = finite(snapshot["heaters"]["extruder_temperature"], "extruder_temperature_invalid")
        if not actual_window[0] <= nozzle_actual <= actual_window[1]:
            raise GateError("extruder_temperature_outside_window")


def scripts(cleaning_target):
    return {
        "clean-cycle-heat": "\n".join((
            "G90",
            "G1 Z35 F300",
            "G1 X203 Y273 F600",
            "G1 X204.5 Y304.5 F600",
            "M104 S%.1f" % cleaning_target,
            "TEMPERATURE_WAIT SENSOR=extruder MINIMUM=%.1f MAXIMUM=%.1f" % (cleaning_target - 2.0, cleaning_target + 2.0),
            "M400",
        )),
        "clean-cycle-start": hot_zigzag(),
        "clean-cycle-finish": "\n".join((
            "G90",
            "G1 X203 Y304 Z34 F30",
            "TURN_OFF_HEATERS",
            "M400",
        )),
        "reference": "\n".join((
            "M104 S140.0",
            "M140 S55.0",
            "TEMPERATURE_WAIT SENSOR=extruder MINIMUM=138.0 MAXIMUM=142.0",
            "TEMPERATURE_WAIT SENSOR=heater_bed MINIMUM=54.0 MAXIMUM=56.0",
            "ACCURATE_G28",
            "BED_MESH_PROFILE LOAD=%s" % BEST_PROFILE,
            "TURN_OFF_HEATERS",
            "M400",
        )),
        "stop": "TURN_OFF_HEATERS",
    }


def hot_zigzag():
    lines = [
        "G90",
        "G1 X203 Y273 Z35 F600",
        "G1 Z32 F300",
        "G1 Y305 F600",
    ]
    for index in range(HOT_ROUND_TRIPS):
        y_value = 305 if index % 2 == 0 else 304
        lines.append("G1 X206 Y%d Z32 F600" % y_value)
        lines.append("G1 X203 Y%d Z32 F600" % y_value)
    lines.extend(("M104 S0", "M400"))
    return "\n".join(lines)


def cooling_z_for_temperature(temperature_c, cleaning_target_c):
    if cleaning_target_c <= REFERENCE_NOZZLE_C:
        raise GateError("cleaning_target_must_exceed_reference")
    progress = (cleaning_target_c - temperature_c) / (cleaning_target_c - REFERENCE_NOZZLE_C)
    progress = min(1.0, max(0.0, progress))
    raw_z = BRUSH_CONTACT_Z_MM + (BRUSH_RELEASE_Z_MM - BRUSH_CONTACT_Z_MM) * progress
    return round(raw_z * 20.0) / 20.0


def cooling_move(index, z_mm):
    if not BRUSH_CONTACT_Z_MM <= z_mm <= BRUSH_RELEASE_Z_MM:
        raise GateError("cooling_z_out_of_bounds")
    x_value = 206 if index % 2 == 0 else 203
    y_value = 305 if (index // 2) % 2 == 0 else 304
    return "\n".join((
        "G90",
        "G1 X%d Y%d Z%.2f F30" % (x_value, y_value, z_mm),
        "M400",
    ))


def reviewed_cooling_moves():
    return {
        cooling_move(index, 32.0 + step * 0.05)
        for index in range(4)
        for step in range(41)
    }


def send_reviewed_script(script, allowed):
    if script not in allowed:
        raise GateError("gcode_not_reviewed")
    request = {"id": 6101, "method": "gcode/script", "params": {"script": script}}
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(180.0)
    try:
        client.connect("/tmp/klippy_uds")
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
        raise GateError("gcode_response_missing")
    response = json.loads(data.split(b"\x03", 1)[0].decode("utf-8"))
    if response.get("error"):
        raise GateError("gcode_rejected")


def effects(action, attempted, recovery_stop_attempted=False):
    return {
        "gcode_attempted": attempted,
        "heating": action in ("clean-cycle", "reference") and attempted,
        "motion": action in ("clean-cycle", "reference") and attempted,
        "final_z_reference": action == "reference" and attempted,
        "heater_stop": action in ("clean-cycle", "reference", "stop") and attempted or recovery_stop_attempted,
        "extrusion": False,
        "cfs_action": False,
        "remote_write": False,
        "service_action": False,
        "automatic_retry": False,
    }


def validate_action_state(action, snapshot, target, before):
    validate_base(snapshot)
    if action in ("preflight", "clean-cycle"):
        validate_targets(snapshot, 0.0, 0.0)
        validate_known_clean_cycle_start(snapshot)
    elif action == "reference":
        validate_targets(snapshot, 0.0, 0.0)
        validate_position(snapshot, [203.0, 304.0, 34.0], "clean_cool_end_position")
    elif action == "validate":
        validate_targets(snapshot, 0.0, 0.0)
    elif action == "stop":
        pass
    else:
        raise GateError("action_invalid")

    if before is not None:
        require_equal(snapshot["hashes"], before["hashes"], "configuration_changed")


def validate_after(action, snapshot, target, before):
    validate_base(snapshot)
    require_equal(snapshot["hashes"], before["hashes"], "configuration_changed")
    if action == "clean-cycle":
        validate_targets(snapshot, 0.0, 0.0)
        nozzle_actual = finite(snapshot["heaters"]["extruder_temperature"], "extruder_temperature_invalid")
        if not 134.0 <= nozzle_actual <= 142.0:
            raise GateError("clean_cycle_finish_temperature_outside_window")
        validate_position(snapshot, [203.0, 304.0, 34.0], "clean_cool_end_position")
    elif action in ("reference", "stop"):
        validate_targets(snapshot, 0.0, 0.0)
    else:
        raise GateError("after_action_invalid")


def run(action, material_id, cleaning_target):
    reviewed = scripts(cleaning_target)
    before = capture_snapshot()
    validate_action_state(action, before, cleaning_target, None)
    if action in ("preflight", "validate"):
        return {
            "schema": 1,
            "mission": MISSION,
            "action": action,
            "status": "%s_OK" % action.upper(),
            "material_id": material_id,
            "cleaning_target_c": cleaning_target,
            "snapshot": before,
            "effects": effects(action, False),
        }

    attempted = False
    recovery_stop_attempted = False
    try:
        attempted = True
        if action == "clean-cycle":
            allowed = set(reviewed.values()) | reviewed_cooling_moves()
            send_reviewed_script(reviewed["clean-cycle-heat"], allowed)
            send_reviewed_script(reviewed["clean-cycle-start"], allowed)
            deadline = time.monotonic() + COOLING_TIMEOUT_S
            last_z = BRUSH_CONTACT_Z_MM
            move_index = 0
            while True:
                current = capture_snapshot()
                validate_base(current)
                validate_targets(current, 0.0, 0.0)
                temperature = finite(current["heaters"]["extruder_temperature"], "extruder_temperature_invalid")
                if temperature <= 142.0:
                    break
                if time.monotonic() >= deadline:
                    raise GateError("sensor_controlled_cooling_timeout")
                next_z = max(last_z, cooling_z_for_temperature(temperature, cleaning_target))
                move_script = cooling_move(move_index, next_z)
                send_reviewed_script(move_script, allowed)
                last_z = next_z
                move_index += 1
            send_reviewed_script(reviewed["clean-cycle-finish"], allowed)
        else:
            send_reviewed_script(reviewed[action], set(reviewed.values()))
        after = capture_snapshot()
        validate_after(action, after, cleaning_target, before)
        return {
            "schema": 1,
            "mission": MISSION,
            "action": action,
            "status": "%s_TECHNICAL_OK_AWAITING_HUMAN_VERDICT" % action.upper().replace("-", "_"),
            "material_id": material_id,
            "cleaning_target_c": cleaning_target,
            "before": before,
            "after": after,
            "effects": effects(action, attempted),
        }
    except Exception as exc:
        recovery = None
        recovery_error = None
        if action != "stop":
            try:
                recovery_stop_attempted = True
                send_reviewed_script(reviewed["stop"], set(reviewed.values()))
                recovery = capture_snapshot()
                validate_base(recovery)
                validate_targets(recovery, 0.0, 0.0)
            except Exception as recovery_exc:
                recovery_error = "%s:%s" % (type(recovery_exc).__name__, recovery_exc)
        return {
            "schema": 1,
            "mission": MISSION,
            "action": action,
            "status": "%s_KO_NO_RETRY" % action.upper().replace("-", "_"),
            "material_id": material_id,
            "cleaning_target_c": cleaning_target,
            "before": before,
            "primary_error": "%s:%s" % (type(exc).__name__, exc),
            "recovery": recovery,
            "recovery_error": recovery_error,
            "effects": effects(action, attempted, recovery_stop_attempted),
        }


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 3:
        print(json.dumps({"mission": MISSION, "status": "INVALID_ARGUMENTS"}, sort_keys=True))
        return 2
    action, material_id, target_text = arguments
    if action not in ("preflight", "clean-cycle", "reference", "stop", "validate"):
        print(json.dumps({"mission": MISSION, "status": "INVALID_ACTION"}, sort_keys=True))
        return 2
    if not SAFE_ID.fullmatch(material_id) or material_id.lower() in ("unknown", "none"):
        print(json.dumps({"mission": MISSION, "status": "INVALID_MATERIAL"}, sort_keys=True))
        return 2
    try:
        cleaning_target = float(target_text)
    except ValueError:
        print(json.dumps({"mission": MISSION, "status": "INVALID_TARGET"}, sort_keys=True))
        return 2
    if not math.isfinite(cleaning_target) or not 160.0 <= cleaning_target <= 300.0:
        print(json.dumps({"mission": MISSION, "status": "INVALID_TARGET"}, sort_keys=True))
        return 2
    try:
        result = run(action, material_id, cleaning_target)
    except Exception as exc:
        result = {
            "schema": 1,
            "mission": MISSION,
            "action": action,
            "status": "%s_PREFLIGHT_KO" % action.upper().replace("-", "_"),
            "error": "%s:%s" % (type(exc).__name__, exc),
            "effects": effects(action, False),
        }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print("CLEAN_AND_REFERENCE_V1_%s" % result["status"])
    return 0 if result["status"].endswith("_OK") or "TECHNICAL_OK_AWAITING_HUMAN_VERDICT" in result["status"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
