from __future__ import print_function

import hashlib
import json
import os
import socket
import sys
from urllib.request import Request, urlopen


MISSION = "G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1"
BASE_URL = "http://127.0.0.1:7125"
TIMEOUT_S = 5.0
ROBUST_PROFILE = "k1_p001_t055_r001_n06x06"
PREVIOUS_PROFILE = "k1_p001_t055_r001_n11x11"
DEFAULT_PROFILE = "default"
ROBUST_PROFILE_SHA256 = "c3c7a2ba89f8094328bc5d8b3936b16dbd1de46f4a80bde87cba3d17cfab5f8f"
PREVIOUS_PROFILE_SHA256 = "58fd96c55129bf7a17ba890d309cb3cd5e2926ec271d735b60392f8369da0a61"
DEFAULT_PROFILE_SHA256 = "ca13f9a7904fad990b8fc72f7e4ec5cf95b55694cc93b325850241ab1506b5f8"

EXPECTED_HASHES = {
    "/usr/data/printer_data/config/printer.cfg": "f88d6b52477592805384fca2b4d7abd00298deecd82227af2fa580085fe26fa2",
    "/usr/data/printer_data/config/box.cfg": "e7a6b26df58a9fa8e49d3af6845f5a0937a790c8ef494b96ec72fd7392abc7a7",
    "/usr/data/printer_data/config/gcode_macro.cfg": "864fedde88fbb345c220ae5658f7b04779b3981bd78d68eda6fa63c59c79a04f",
    "/usr/data/printer_data/config/k1-control-z-mesh.cfg": "dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113",
    "/usr/data/printer_data/config/k1-control-calibration-path.cfg": "825aadac8679e0d0e9be140cc5ba4e7656b2bff0d197d1683a73d2b5be4e364e",
    "/usr/data/k1-control-v1/current/config/moonraker.conf": "950dc211e0b7cd8990a8bb131062f633cd9bddfdd75cc6168a10149356ed5761",
    "/usr/data/k1-control-v1/current/moonraker/moonraker/moonraker/components/k1_control.py": "27c0734f149ea89a8ba0d5e17f7f65aecc95c1383c359662cb366a687bb7d303",
    "/usr/data/k1-control-v1/current/moonraker/moonraker/moonraker/components/k1_control_calibration_core.py": "9a6a24195b504a82f88e3b7464c508eaf49f8450169578257c8fe98a5d5f4e97",
    "/usr/data/k1-control-v1/current/moonraker/moonraker/moonraker/components/k1_control_probe_count.py": "8c8c4aaf20856be1880cea56badd2fe81bd488966eab0d55e7672f73eb1db7b0",
    "/usr/data/k1-control-v1/current/www/mainsail/k1-control/index.html": "4892294d278497f2f4215564b3e70fcedb354fb880f306641a29a03042ad1abc",
    "/usr/data/k1-control-v1/current/www/mainsail/k1-control/app.js": "001a31fe7357b0031bfbfa5f6856f8436315cf9640f5a61b2f6121766c985554",
    "/usr/data/k1-control-v1/current/www/mainsail/k1-control/styles.css": "a7c27fbcdc07f24b00b6d47cc1d9aa8570b9483bcf4dd3615419de579f9aaa12",
}

QUERY_PATH = (
    "/printer/objects/query?"
    "print_stats=state,filename"
    "&extruder=temperature,target"
    "&heater_bed=temperature,target"
    "&toolhead=homed_axes,position"
    "&bed_mesh=profile_name,probed_matrix,mesh_matrix,profiles"
    "&box=state,t_command,T1,T2,T3,T4"
    "&gcode_move=homing_origin"
    "&gcode_macro+KCTRL_STATE=ready,session_active,accepted_z_valid,accepted_z_offset,low_moves_armed"
    "&k1_control_store=integrity"
    "&gcode_macro+KCTRL_CAL_PATH_STATE=phase,motion_armed,commit_ready"
)


class GateError(RuntimeError):
    pass


def child(mapping, key):
    value = mapping.get(key)
    return value if isinstance(value, dict) else {}


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


def collect_hashes():
    return {path: hash_file(path) for path in EXPECTED_HASHES}


def fetch_json(path):
    request = Request(BASE_URL + path, method="GET")
    with urlopen(request, timeout=TIMEOUT_S) as response:
        body = response.read()
        status_code = response.getcode()
    if status_code != 200:
        raise GateError("http_status_%s" % status_code)
    return json.loads(body.decode("utf-8"))


def collect_live():
    server = child(fetch_json("/server/info"), "result")
    status = child(child(fetch_json(QUERY_PATH), "result"), "status")
    if not server or not status:
        raise GateError("live_response_incomplete")
    return server, status, collect_hashes()


def profile_summaries(status):
    profiles = child(status, "bed_mesh").get("profiles")
    if not isinstance(profiles, dict):
        raise GateError("mesh_profiles_missing")
    summaries = {}
    for name in sorted(profiles):
        profile = profiles.get(name)
        points = profile.get("points") if isinstance(profile, dict) else None
        summaries[name] = matrix_summary(points)
    return summaries


def safe_projection(server, status, hashes):
    bed_mesh = child(status, "bed_mesh")
    box = child(status, "box")
    runtime = child(status, "gcode_macro KCTRL_STATE")
    store = child(status, "k1_control_store")
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
            "extruder_target": child(status, "extruder").get("target"),
            "bed_target": child(status, "heater_bed").get("target"),
        },
        "toolhead": {
            "homed_axes": child(status, "toolhead").get("homed_axes"),
            "position": child(status, "toolhead").get("position"),
            "homing_origin": child(status, "gcode_move").get("homing_origin"),
        },
        "bed_mesh": {
            "profile_name": bed_mesh.get("profile_name"),
            "probed_matrix": matrix_summary(bed_mesh.get("probed_matrix")),
            "mesh_matrix": matrix_summary(bed_mesh.get("mesh_matrix")),
            "profiles": profile_summaries(status),
        },
        "box": {
            "state": box.get("state"),
            "t_command": box.get("t_command"),
            "T1": {
                "state": child(box, "T1").get("state"),
                "filament": child(box, "T1").get("filament"),
            },
            "T2": {
                "state": child(box, "T2").get("state"),
                "filament": child(box, "T2").get("filament"),
            },
            "T3": {
                "state": child(box, "T3").get("state"),
                "filament": child(box, "T3").get("filament"),
            },
            "T4": {
                "state": child(box, "T4").get("state"),
                "filament": child(box, "T4").get("filament"),
            },
        },
        "runtime": {
            key: runtime.get(key)
            for key in (
                "ready",
                "session_active",
                "accepted_z_valid",
                "accepted_z_offset",
                "low_moves_armed",
            )
        },
        "store": {"integrity": store.get("integrity")},
        "calibration_path": {
            key: path_state.get(key)
            for key in ("phase", "motion_armed", "commit_ready")
        },
        "hashes": hashes,
    }


def _assert_equal(actual, expected, code):
    if actual != expected:
        raise GateError(code)


def validate_common(snapshot):
    _assert_equal(snapshot["server"]["klippy_state"], "ready", "klippy_not_ready")
    _assert_equal(snapshot["server"]["failed_components"], [], "failed_components")
    _assert_equal(snapshot["server"]["warnings"], [], "server_warnings")
    _assert_equal(snapshot["print"]["state"], "standby", "printer_not_standby")
    _assert_equal(snapshot["print"]["filename_present"], False, "print_filename_present")
    _assert_equal(float(snapshot["heaters"]["extruder_target"]), 0.0, "extruder_target_nonzero")
    _assert_equal(float(snapshot["heaters"]["bed_target"]), 0.0, "bed_target_nonzero")
    if snapshot["toolhead"]["homed_axes"] not in ("", []):
        raise GateError("axes_still_homed")
    _assert_equal(snapshot["runtime"]["ready"], 1, "runtime_not_ready")
    _assert_equal(snapshot["runtime"]["session_active"], 0, "runtime_session_active")
    _assert_equal(snapshot["runtime"]["accepted_z_valid"], 1, "accepted_z_invalid")
    if abs(float(snapshot["runtime"]["accepted_z_offset"]) - (-0.04)) > 0.0005:
        raise GateError("accepted_z_drift")
    _assert_equal(snapshot["runtime"]["low_moves_armed"], 0, "low_moves_armed")
    _assert_equal(snapshot["store"]["integrity"], "ok", "store_not_ok")
    if snapshot["calibration_path"]["phase"] not in ("idle", "committed", "cancelled"):
        raise GateError("calibration_path_open")
    _assert_equal(snapshot["calibration_path"]["motion_armed"], 0, "calibration_motion_armed")
    _assert_equal(snapshot["calibration_path"]["commit_ready"], 0, "calibration_commit_ready")
    _assert_equal(snapshot["box"]["state"], "connect", "cfs_root_disconnected")
    _assert_equal(snapshot["box"]["t_command"], "", "cfs_command_active")
    for unit in ("T1", "T2"):
        _assert_equal(snapshot["box"][unit].get("state"), "connect", "%s_disconnected" % unit)
        if snapshot["box"][unit].get("filament") not in (None, "None"):
            raise GateError("cfs_route_engaged")
    _assert_equal(snapshot["hashes"], EXPECTED_HASHES, "configuration_hash_drift")
    profiles = snapshot["bed_mesh"]["profiles"]
    _assert_equal(set(profiles), {DEFAULT_PROFILE, ROBUST_PROFILE, PREVIOUS_PROFILE}, "profile_set_drift")
    _assert_equal(profiles[DEFAULT_PROFILE], {"rows": 6, "columns": [6] * 6, "sha256": DEFAULT_PROFILE_SHA256}, "default_matrix_drift")
    _assert_equal(profiles[ROBUST_PROFILE], {"rows": 6, "columns": [6] * 6, "sha256": ROBUST_PROFILE_SHA256}, "robust_matrix_drift")
    _assert_equal(profiles[PREVIOUS_PROFILE], {"rows": 11, "columns": [11] * 11, "sha256": PREVIOUS_PROFILE_SHA256}, "previous_matrix_drift")


def validate_active(snapshot, expected_profile):
    validate_common(snapshot)
    _assert_equal(snapshot["bed_mesh"]["profile_name"], expected_profile, "active_profile_drift")
    expected = snapshot["bed_mesh"]["profiles"][expected_profile]
    _assert_equal(snapshot["bed_mesh"]["probed_matrix"], expected, "active_probed_matrix_drift")


def send_gcode(script):
    allowed = {
        "BED_MESH_PROFILE LOAD=%s" % ROBUST_PROFILE,
        "BED_MESH_PROFILE LOAD=%s" % PREVIOUS_PROFILE,
    }
    if script not in allowed:
        raise GateError("gcode_not_reviewed")
    request = {"id": 5701, "method": "gcode/script", "params": {"script": script}}
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(15.0)
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
    return {"response_received": True, "error": False}


def capture_snapshot():
    server, status, hashes = collect_live()
    return safe_projection(server, status, hashes)


def run_preflight():
    before = capture_snapshot()
    validate_active(before, PREVIOUS_PROFILE)
    return {
        "schema": 1,
        "mission": MISSION,
        "action": "preflight",
        "status": "PREFLIGHT_OK",
        "before": before,
        "effects": {
            "gcode_commands_attempted": [],
            "remote_files_written": False,
            "service_actions": False,
            "heater_or_motion_actions": False,
        },
    }


def run_activation():
    before = capture_snapshot()
    validate_active(before, PREVIOUS_PROFILE)
    attempted = []
    after = None
    rollback = None
    try:
        command = "BED_MESH_PROFILE LOAD=%s" % ROBUST_PROFILE
        attempted.append(command)
        send_gcode(command)
        after = capture_snapshot()
        validate_active(after, ROBUST_PROFILE)
        _assert_equal(after["hashes"], before["hashes"], "configuration_changed_after_activation")
        return {
            "schema": 1,
            "mission": MISSION,
            "action": "activate",
            "status": "ACTIVATION_OK",
            "before": before,
            "after": after,
            "rollback": None,
            "effects": {
                "gcode_commands_attempted": attempted,
                "remote_files_written": False,
                "service_actions": False,
                "heater_or_motion_actions": False,
            },
        }
    except Exception as exc:
        primary_error = "%s:%s" % (type(exc).__name__, exc)
        rollback_error = None
        try:
            rollback_command = "BED_MESH_PROFILE LOAD=%s" % PREVIOUS_PROFILE
            attempted.append(rollback_command)
            send_gcode(rollback_command)
            rollback = capture_snapshot()
            validate_active(rollback, PREVIOUS_PROFILE)
            _assert_equal(rollback["hashes"], before["hashes"], "configuration_changed_after_rollback")
        except Exception as exc2:
            rollback_error = "%s:%s" % (type(exc2).__name__, exc2)
        return {
            "schema": 1,
            "mission": MISSION,
            "action": "activate",
            "status": "ACTIVATION_KO_ROLLED_BACK" if rollback_error is None else "ACTIVATION_KO_ROLLBACK_UNCERTAIN",
            "before": before,
            "after": after,
            "rollback": rollback,
            "primary_error": primary_error,
            "rollback_error": rollback_error,
            "effects": {
                "gcode_commands_attempted": attempted,
                "remote_files_written": False,
                "service_actions": False,
                "heater_or_motion_actions": False,
            },
        }


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments not in (["preflight"], ["activate"]):
        print(json.dumps({"mission": MISSION, "status": "INVALID_ACTION"}, sort_keys=True))
        return 2
    try:
        result = run_preflight() if arguments[0] == "preflight" else run_activation()
    except Exception as exc:
        result = {
            "schema": 1,
            "mission": MISSION,
            "action": arguments[0],
            "status": "PREFLIGHT_KO",
            "error": "%s:%s" % (type(exc).__name__, exc),
            "effects": {
                "gcode_commands_attempted": [],
                "remote_files_written": False,
                "service_actions": False,
                "heater_or_motion_actions": False,
            },
        }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print("ROBUST_MESH_ACTIVATION_V1_%s" % result["status"])
    return 0 if result["status"] in ("PREFLIGHT_OK", "ACTIVATION_OK") else 1


if __name__ == "__main__":
    raise SystemExit(main())
