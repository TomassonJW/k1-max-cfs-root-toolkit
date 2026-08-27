from __future__ import print_function

import hashlib
import json
import os
import socket
import sys
from urllib.request import Request, urlopen


MISSION = "G4-K1-CONTROL-CLEAN-MOTION-V1"
BASE_URL = "http://127.0.0.1:7125"
TIMEOUT_S = 5.0
BEST_PROFILE = "k1_p001_t055_r001_n11x11"
BEST_PROFILE_SHA256 = "58fd96c55129bf7a17ba890d309cb3cd5e2926ec271d735b60392f8369da0a61"

CHECKPOINTS = {
    "d1": {
        "before": [156.657, 142.271, 50.0],
        "after": [81.0, 280.0, 50.0],
        "script": "G90\nG1 X81 Y280 Z50 F1200\nM400",
        "description": "high_clearance_staging_24_5mm_before_stock_brush_zone",
    },
    "d2": {
        "before": [81.0, 280.0, 50.0],
        "after": [81.0, 300.0, 50.0],
        "script": "G90\nG1 X81 Y300 Z50 F600\nM400",
        "description": "high_clearance_staging_4_5mm_before_stock_brush_zone",
    },
    "d3": {
        "before": [81.0, 300.0, 50.0],
        "after": [81.0, 303.0, 50.0],
        "script": "G90\nG1 X81 Y303 Z50 F300\nM400",
        "description": "high_clearance_staging_1_5mm_before_stock_brush_zone",
    },
}

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
    "&extruder=target"
    "&heater_bed=target"
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


def best_profile_summary(status):
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
            "extruder_target": child(status, "extruder").get("target"),
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
            "best_profile": best_profile_summary(status),
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


def validate_common(snapshot):
    require_equal(snapshot["server"]["klippy_state"], "ready", "klippy_not_ready")
    require_equal(snapshot["server"]["failed_components"], [], "failed_components")
    require_equal(snapshot["server"]["warnings"], [], "server_warnings")
    require_equal(snapshot["print"]["state"], "standby", "printer_not_standby")
    require_equal(snapshot["print"]["filename_present"], False, "print_filename_present")
    require_equal(float(snapshot["heaters"]["extruder_target"]), 0.0, "extruder_target_nonzero")
    require_equal(float(snapshot["heaters"]["bed_target"]), 0.0, "bed_target_nonzero")
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
    require_equal(snapshot["bed_mesh"]["profile_name"], BEST_PROFILE, "active_profile_drift")
    expected_mesh = {"rows": 11, "columns": [11] * 11, "sha256": BEST_PROFILE_SHA256}
    require_equal(snapshot["bed_mesh"]["best_profile"], expected_mesh, "best_profile_drift")
    require_equal(snapshot["bed_mesh"]["probed_matrix"], expected_mesh, "active_matrix_drift")


def validate_position(snapshot, expected, code):
    validate_common(snapshot)
    gcode_position = snapshot["toolhead"]["gcode_position"]
    physical_position = snapshot["toolhead"]["position"]
    if not isinstance(gcode_position, list) or len(gcode_position) < 3:
        raise GateError("gcode_position_missing")
    if not isinstance(physical_position, list) or len(physical_position) < 3:
        raise GateError("toolhead_position_missing")
    for index in range(3):
        if abs(float(gcode_position[index]) - float(expected[index])) > 0.02:
            raise GateError("%s_axis_%s" % (code, index))
    if abs(float(physical_position[2]) - float(gcode_position[2])) > 0.5:
        raise GateError("mesh_compensated_z_out_of_bounds")


def send_reviewed_script(script):
    allowed = set(item["script"] for item in CHECKPOINTS.values())
    if script not in allowed:
        raise GateError("gcode_not_reviewed")
    request = {"id": 5803, "method": "gcode/script", "params": {"script": script}}
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(45.0)
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


def effects(attempted, motion):
    return {
        "gcode_commands_attempted": attempted,
        "remote_files_written": False,
        "service_actions": False,
        "heating": False,
        "extrusion": False,
        "cfs_action": False,
        "homing": False,
        "xy_motion_at_z50": motion,
        "mesh_measurement": False,
        "z_offset_write": False,
    }


def run_preflight(checkpoint_id):
    spec = CHECKPOINTS[checkpoint_id]
    before = capture_snapshot()
    validate_position(before, spec["before"], "unexpected_preflight_position")
    return {
        "schema": 1,
        "mission": MISSION,
        "action": "%s_preflight" % checkpoint_id,
        "status": "%s_PREFLIGHT_OK" % checkpoint_id.upper(),
        "checkpoint": spec,
        "before": before,
        "effects": effects([], False),
    }


def run_checkpoint(checkpoint_id):
    spec = CHECKPOINTS[checkpoint_id]
    before = capture_snapshot()
    validate_position(before, spec["before"], "unexpected_start_position")
    attempted = spec["script"].split("\n")
    try:
        send_reviewed_script(spec["script"])
        after = capture_snapshot()
        validate_position(after, spec["after"], "unexpected_end_position")
        require_equal(after["hashes"], before["hashes"], "configuration_changed")
        return {
            "schema": 1,
            "mission": MISSION,
            "action": checkpoint_id,
            "status": "%s_TECHNICAL_OK_AWAITING_HUMAN_VERDICT" % checkpoint_id.upper(),
            "checkpoint": spec,
            "before": before,
            "after": after,
            "effects": effects(attempted, True),
        }
    except Exception as exc:
        recovery = None
        recovery_error = None
        try:
            recovery = capture_snapshot()
            validate_common(recovery)
        except Exception as exc2:
            recovery_error = "%s:%s" % (type(exc2).__name__, exc2)
        return {
            "schema": 1,
            "mission": MISSION,
            "action": checkpoint_id,
            "status": "%s_KO_NO_RETRY_STATE_SAFE" % checkpoint_id.upper() if recovery_error is None else "%s_KO_STATE_UNCERTAIN" % checkpoint_id.upper(),
            "checkpoint": spec,
            "before": before,
            "recovery_read": recovery,
            "primary_error": "%s:%s" % (type(exc).__name__, exc),
            "recovery_error": recovery_error,
            "effects": effects(attempted, True),
        }


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 2 or arguments[0] not in ("preflight", "run") or arguments[1] not in CHECKPOINTS:
        print(json.dumps({"mission": MISSION, "status": "INVALID_ACTION"}, sort_keys=True))
        return 2
    mode, checkpoint_id = arguments
    try:
        result = run_preflight(checkpoint_id) if mode == "preflight" else run_checkpoint(checkpoint_id)
    except Exception as exc:
        result = {
            "schema": 1,
            "mission": MISSION,
            "action": "%s_%s" % (checkpoint_id, mode),
            "status": "%s_PREFLIGHT_KO" % checkpoint_id.upper(),
            "error": "%s:%s" % (type(exc).__name__, exc),
            "effects": effects([], False),
        }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print("CLEAN_MOTION_V1_%s" % result["status"])
    return 0 if result["status"] in (
        "%s_PREFLIGHT_OK" % checkpoint_id.upper(),
        "%s_TECHNICAL_OK_AWAITING_HUMAN_VERDICT" % checkpoint_id.upper(),
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
