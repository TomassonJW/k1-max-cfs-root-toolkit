from __future__ import print_function

import hashlib
import json
import re
import sys
from urllib.request import Request, urlopen


MISSION = "G4-K1-CONTROL-CLEAN-MOTION-V1-READ-ONLY-SOURCES"
BASE_URL = "http://127.0.0.1:7125"
TIMEOUT_S = 5.0
ROBUST_PROFILE = "k1_p001_t055_r001_n06x06"
ROBUST_PROFILE_SHA256 = "c3c7a2ba89f8094328bc5d8b3936b16dbd1de46f4a80bde87cba3d17cfab5f8f"
QUERY_PATH = (
    "/printer/objects/query?"
    "configfile=settings"
    "&print_stats=state,filename"
    "&extruder=target"
    "&heater_bed=target"
    "&toolhead=axis_minimum,axis_maximum,homed_axes,position"
    "&bed_mesh=profile_name,probed_matrix,profiles"
    "&box=state,t_command,T1,T2,T3,T4"
)

SELECTED_AXIS_FIELDS = (
    "position_min",
    "position_max",
    "position_endstop",
    "homing_speed",
    "second_homing_speed",
    "homing_retract_dist",
)
SELECTED_MACROS = (
    "gcode_macro cx_nozzle_clear",
    "gcode_macro nozzle_clear",
    "gcode_macro cx_rough_g28",
    "gcode_macro accurate_g28",
)
DISCOVERY_PATTERN = re.compile(
    r"(nozzle|clear|clean|wipe|brush|rough|accurate|prtouch|probe)", re.IGNORECASE
)
SELECTED_CLEANING_FIELDS = (
    "clr_noz_start_x",
    "clr_noz_start_y",
    "clr_noz_len_x",
    "clr_noz_len_y",
    "pa_clr_dis_mm",
    "pa_clr_down_mm",
    "bed_max_err",
    "g29_xy_speed",
    "g29_speed",
    "g29_rdy_speed",
    "s_hot_min_temp",
    "s_hot_max_temp",
    "s_bed_max_temp",
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


def selected_axis_settings(settings):
    output = {}
    for section_name in ("stepper_x", "stepper_y", "stepper_z"):
        section = child(settings, section_name)
        output[section_name] = {
            key: section.get(key) for key in SELECTED_AXIS_FIELDS if key in section
        }
    return output


def selected_cleaning_settings(settings):
    output = {}
    for section_name, raw_section in settings.items():
        if not isinstance(raw_section, dict):
            continue
        selected = {
            key: raw_section.get(key)
            for key in SELECTED_CLEANING_FIELDS
            if key in raw_section
        }
        if selected:
            output[section_name] = selected
    return output


def motion_line_summaries(gcode):
    summaries = []
    for line_number, raw_line in enumerate(gcode.splitlines(), 1):
        stripped = raw_line.strip()
        match = re.match(r"^(G0|G1)\b", stripped, re.IGNORECASE)
        if not match:
            continue
        literals = {}
        for axis, value in re.findall(
            r"\b([XYZEF])\s*(-?\d+(?:\.\d+)?)\b", stripped, re.IGNORECASE
        ):
            literals[axis.upper()] = float(value)
        summaries.append(
            {
                "line_number": line_number,
                "opcode": match.group(1).upper(),
                "literal_values": literals,
                "contains_template": "{" in stripped or "%" in stripped,
                "line_sha256": hashlib.sha256(stripped.encode("utf-8")).hexdigest(),
            }
        )
    return summaries


def macro_summary(settings, section_name):
    section = child(settings, section_name)
    gcode = section.get("gcode")
    if not isinstance(gcode, str):
        return {
            "present": bool(section),
            "gcode_present": False,
            "gcode_sha256": None,
            "line_count": 0,
            "motion_lines": [],
        }
    normalized = gcode.replace("\r\n", "\n")
    return {
        "present": True,
        "gcode_present": True,
        "gcode_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "line_count": len(normalized.splitlines()),
        "motion_lines": motion_line_summaries(normalized),
    }


def robust_profile_summary(status):
    profiles = child(status, "bed_mesh").get("profiles")
    if not isinstance(profiles, dict):
        raise CaptureError("mesh_profiles_missing")
    robust = profiles.get(ROBUST_PROFILE)
    points = robust.get("points") if isinstance(robust, dict) else None
    summary = matrix_summary(points)
    if summary["sha256"] != ROBUST_PROFILE_SHA256:
        raise CaptureError("robust_profile_matrix_drift")
    return summary


def capture():
    server = child(fetch_json("/server/info"), "result")
    object_names = child(fetch_json("/printer/objects/list"), "result").get(
        "objects", []
    )
    gcode_help = child(fetch_json("/printer/gcode/help"), "result")
    status = child(child(fetch_json(QUERY_PATH), "result"), "status")
    settings = child(child(status, "configfile"), "settings")
    if not server or not status or not settings:
        raise CaptureError("live_response_incomplete")
    print_stats = child(status, "print_stats")
    if server.get("klippy_state") != "ready":
        raise CaptureError("klippy_not_ready")
    if server.get("failed_components") != [] or server.get("warnings") != []:
        raise CaptureError("server_health_not_clean")
    if print_stats.get("state") != "standby" or bool(print_stats.get("filename")):
        raise CaptureError("printer_not_standby")
    if float(child(status, "extruder").get("target")) != 0.0:
        raise CaptureError("extruder_target_nonzero")
    if float(child(status, "heater_bed").get("target")) != 0.0:
        raise CaptureError("bed_target_nonzero")
    box = child(status, "box")
    if box.get("t_command") != "":
        raise CaptureError("cfs_command_active")

    toolhead = child(status, "toolhead")
    bed_mesh = child(status, "bed_mesh")
    return {
        "schema": 1,
        "mission": MISSION,
        "status": "CAPTURE_OK",
        "authority": "strict_read_only",
        "server": {
            "klippy_state": server.get("klippy_state"),
            "failed_components": server.get("failed_components"),
            "warnings": server.get("warnings"),
        },
        "safe_state": {
            "print_state": print_stats.get("state"),
            "filename_present": bool(print_stats.get("filename")),
            "extruder_target": child(status, "extruder").get("target"),
            "bed_target": child(status, "heater_bed").get("target"),
            "cfs_command": box.get("t_command"),
        },
        "toolhead": {
            "axis_minimum": toolhead.get("axis_minimum"),
            "axis_maximum": toolhead.get("axis_maximum"),
            "homed_axes": toolhead.get("homed_axes"),
            "position": toolhead.get("position"),
        },
        "axis_settings": selected_axis_settings(settings),
        "cleaning_settings": selected_cleaning_settings(settings),
        "discovery": {
            "matching_object_names": sorted(
                name
                for name in object_names
                if isinstance(name, str) and DISCOVERY_PATTERN.search(name)
            ),
            "matching_config_sections": sorted(
                name for name in settings if DISCOVERY_PATTERN.search(name)
            ),
            "matching_registered_gcode_commands": sorted(
                name
                for name in gcode_help
                if isinstance(name, str) and DISCOVERY_PATTERN.search(name)
            ),
        },
        "mesh": {
            "active_profile": bed_mesh.get("profile_name"),
            "robust_profile": robust_profile_summary(status),
        },
        "macro_summaries": {
            name: macro_summary(settings, name) for name in SELECTED_MACROS
        },
        "effects": {
            "http_methods": ["GET"],
            "gcode_sent": False,
            "remote_files_read": False,
            "remote_files_written": False,
            "service_action": False,
            "heater_or_motion_action": False,
            "full_macro_source_exported": False,
        },
    }


def main():
    try:
        result = capture()
    except Exception as exc:
        result = {
            "schema": 1,
            "mission": MISSION,
            "status": "CAPTURE_KO",
            "error": "%s:%s" % (type(exc).__name__, exc),
            "effects": {
                "http_methods": ["GET"],
                "gcode_sent": False,
                "remote_files_read": False,
                "remote_files_written": False,
                "service_action": False,
                "heater_or_motion_action": False,
                "full_macro_source_exported": False,
            },
        }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print("CLEAN_MOTION_V1_READ_ONLY_%s" % result["status"])
    return 0 if result["status"] == "CAPTURE_OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
