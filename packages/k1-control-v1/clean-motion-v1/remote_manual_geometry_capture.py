from __future__ import print_function

import hashlib
import json
import sys
import time
from urllib.request import Request, urlopen


MISSION = "G4-K1-CONTROL-CLEAN-MOTION-V1-MANUAL-GEOMETRY-CAPTURE"
BASE_URL = "http://127.0.0.1:7125"
TIMEOUT_S = 5.0
BEST_PROFILE = "k1_p001_t055_r001_n11x11"
BEST_PROFILE_SHA256 = "58fd96c55129bf7a17ba890d309cb3cd5e2926ec271d735b60392f8369da0a61"
QUERY_PATH = (
    "/printer/objects/query?"
    "print_stats=state,filename"
    "&extruder=target"
    "&heater_bed=target"
    "&toolhead=homed_axes,position"
    "&gcode_move=gcode_position"
    "&bed_mesh=profile_name,probed_matrix,profiles"
    "&box=state,t_command,T1,T2"
)


class CaptureError(RuntimeError):
    pass


def child(mapping, key):
    value = mapping.get(key)
    return value if isinstance(value, dict) else {}


def fetch_json(path):
    request = Request(BASE_URL + path, method="GET")
    with urlopen(request, timeout=TIMEOUT_S) as response:
        body = response.read()
        status_code = response.getcode()
    if status_code != 200:
        raise CaptureError("http_status_%s" % status_code)
    return json.loads(body.decode("utf-8"))


def matrix_sha256(value):
    if not isinstance(value, list) or len(value) != 11:
        return None
    if any(not isinstance(row, list) or len(row) != 11 for row in value):
        return None
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def snapshot():
    server = child(fetch_json("/server/info"), "result")
    status = child(child(fetch_json(QUERY_PATH), "result"), "status")
    if not server or not status:
        raise CaptureError("live_response_incomplete")
    bed_mesh = child(status, "bed_mesh")
    profiles = bed_mesh.get("profiles")
    profile = profiles.get(BEST_PROFILE) if isinstance(profiles, dict) else None
    box = child(status, "box")
    return {
        "klippy_state": server.get("klippy_state"),
        "failed_components": server.get("failed_components"),
        "warnings": server.get("warnings"),
        "print_state": child(status, "print_stats").get("state"),
        "filename_present": bool(child(status, "print_stats").get("filename")),
        "extruder_target": child(status, "extruder").get("target"),
        "bed_target": child(status, "heater_bed").get("target"),
        "homed_axes": child(status, "toolhead").get("homed_axes"),
        "physical_position": child(status, "toolhead").get("position"),
        "gcode_position": child(status, "gcode_move").get("gcode_position"),
        "profile_name": bed_mesh.get("profile_name"),
        "active_matrix_sha256": matrix_sha256(bed_mesh.get("probed_matrix")),
        "best_profile_sha256": matrix_sha256(profile.get("points")) if isinstance(profile, dict) else None,
        "box_state": box.get("state"),
        "t_command": box.get("t_command"),
        "T1_state": child(box, "T1").get("state"),
        "T1_filament": child(box, "T1").get("filament"),
        "T2_state": child(box, "T2").get("state"),
        "T2_filament": child(box, "T2").get("filament"),
    }


def require_safe(value):
    checks = {
        "klippy_not_ready": value["klippy_state"] == "ready",
        "failed_components": value["failed_components"] == [],
        "server_warnings": value["warnings"] == [],
        "printer_not_standby": value["print_state"] == "standby",
        "print_filename_present": value["filename_present"] is False,
        "extruder_target_nonzero": float(value["extruder_target"]) == 0.0,
        "bed_target_nonzero": float(value["bed_target"]) == 0.0,
        "axes_not_homed_xyz": value["homed_axes"] == "xyz",
        "active_profile_drift": value["profile_name"] == BEST_PROFILE,
        "active_matrix_drift": value["active_matrix_sha256"] == BEST_PROFILE_SHA256,
        "best_profile_drift": value["best_profile_sha256"] == BEST_PROFILE_SHA256,
        "cfs_root_disconnected": value["box_state"] == "connect",
        "cfs_command_active": value["t_command"] == "",
        "cfs_t1_disconnected": value["T1_state"] == "connect",
        "cfs_t2_disconnected": value["T2_state"] == "connect",
        "cfs_route_engaged": value["T1_filament"] in (None, "None") and value["T2_filament"] in (None, "None"),
    }
    for code, passed in checks.items():
        if not passed:
            raise CaptureError(code)


def position3(value, key):
    position = value.get(key)
    if not isinstance(position, list) or len(position) < 3:
        raise CaptureError("%s_missing" % key)
    return [round(float(position[index]), 5) for index in range(3)]


def emit(value):
    print(json.dumps(value, sort_keys=True, separators=(",", ":")), flush=True)


def capture(duration_s, interval_s):
    initial = snapshot()
    require_safe(initial)
    emit(
        {
            "schema": 1,
            "mission": MISSION,
            "record": "control",
            "event": "ready",
            "duration_s": duration_s,
            "interval_s": interval_s,
            "initial_gcode_xyz": position3(initial, "gcode_position"),
            "initial_physical_xyz": position3(initial, "physical_position"),
            "effects": {
                "http_methods": ["GET"],
                "gcode": False,
                "remote_file_read": False,
                "remote_file_write": False,
                "service_action": False,
                "codex_motion": False,
                "heating": False,
                "extrusion": False,
                "cfs_action": False,
            },
        }
    )
    start = time.monotonic()
    next_heartbeat = 10.0
    sample_index = 0
    while True:
        elapsed = time.monotonic() - start
        if elapsed > duration_s:
            break
        current = snapshot()
        require_safe(current)
        emit(
            {
                "schema": 1,
                "mission": MISSION,
                "record": "sample",
                "sample_index": sample_index,
                "elapsed_s": round(elapsed, 3),
                "gcode_xyz": position3(current, "gcode_position"),
                "physical_xyz": position3(current, "physical_position"),
            }
        )
        sample_index += 1
        if elapsed >= next_heartbeat:
            emit(
                {
                    "schema": 1,
                    "mission": MISSION,
                    "record": "control",
                    "event": "heartbeat",
                    "elapsed_s": round(elapsed, 1),
                    "sample_count": sample_index,
                }
            )
            next_heartbeat += 10.0
        remaining = interval_s - ((time.monotonic() - start) - elapsed)
        if remaining > 0:
            time.sleep(remaining)
    final = snapshot()
    require_safe(final)
    emit(
        {
            "schema": 1,
            "mission": MISSION,
            "record": "control",
            "event": "complete",
            "elapsed_s": round(time.monotonic() - start, 3),
            "sample_count": sample_index,
            "final_gcode_xyz": position3(final, "gcode_position"),
            "final_physical_xyz": position3(final, "physical_position"),
        }
    )


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 2:
        emit({"mission": MISSION, "status": "INVALID_ARGUMENTS"})
        return 2
    try:
        duration_s = float(arguments[0])
        interval_s = float(arguments[1])
        if duration_s < 60.0 or duration_s > 1800.0:
            raise CaptureError("duration_out_of_bounds")
        if interval_s < 0.2 or interval_s > 2.0:
            raise CaptureError("interval_out_of_bounds")
        capture(duration_s, interval_s)
    except Exception as exc:
        emit(
            {
                "schema": 1,
                "mission": MISSION,
                "record": "control",
                "event": "aborted",
                "error": "%s:%s" % (type(exc).__name__, exc),
            }
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
