[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SessionDirectory,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SessionLabel
)

$ErrorActionPreference = 'Stop'

$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$rawRoot = Join-Path $workspaceRoot 'inventory\raw'

if (-not (Test-Path -LiteralPath $rawRoot -PathType Container)) {
    throw 'Le dossier prive inventory/raw est introuvable.'
}

if (-not (Test-Path -LiteralPath $SessionDirectory -PathType Container)) {
    New-Item -ItemType Directory -Path $SessionDirectory -Force | Out-Null
}

$resolvedRawRoot = (Resolve-Path -LiteralPath $rawRoot).Path
$resolvedSession = (Resolve-Path -LiteralPath $SessionDirectory).Path
if (-not $resolvedSession.StartsWith($resolvedRawRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Le dossier de session doit rester sous inventory/raw.'
}

$capturePath = Join-Path $resolvedSession "$SessionLabel.safe.json"
$metadataPath = Join-Path $resolvedSession "$SessionLabel.local-metadata.json"
if (Test-Path -LiteralPath $capturePath) {
    throw 'La capture existe deja. Utilise un nouvel identifiant de session.'
}

$metadata = [ordered]@{
    session_label = $SessionLabel
    local_start = (Get-Date).ToString('o')
    mode = 'goal_p4_k1_strict_read_only_qualification_v1'
    ssh_alias = 'k1max-root'
    http_methods = @('GET')
    remote_writes = $false
    remote_file_reads = 'hashes_and_moonraker_section_names_only'
    gcode_requests = $false
    guard_run_called = $false
    service_actions = $false
    physical_actions = $false
}
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8

$remotePython = @'
from __future__ import print_function

import hashlib
import json
import os
import re
import time
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:7125"
TIMEOUT_S = 5.0
QUERY_PATH = (
    "/printer/objects/query?"
    "print_stats=state,filename"
    "&extruder=temperature,target,can_extrude"
    "&heater_bed=temperature,target"
    "&toolhead=homed_axes,position"
    "&bed_mesh=profile_name,probed_matrix,mesh_matrix,profiles"
    "&box=state,t_command,T1,T2,T3,T4"
    "&filament_switch_sensor+filament_sensor=filament_detected,enabled"
    "&filament_switch_sensor+filament_sensor_2=filament_detected,enabled"
    "&gcode_move=homing_origin"
    "&gcode_macro+KCTRL_STATE=ready,session_active,accepted_z_valid,accepted_z_offset,low_moves_armed"
    "&k1_control_store=ready,integrity,accepted_z_valid,accepted_z_offset,session_active,low_moves_armed"
    "&gcode_macro+KCTRL_CAL_PATH_STATE=phase,motion_armed,commit_ready"
)

HASH_PATHS = (
    "/usr/data/printer_data/config/printer.cfg",
    "/usr/data/printer_data/config/box.cfg",
    "/usr/data/printer_data/config/gcode_macro.cfg",
    "/usr/data/printer_data/config/k1-control-z-mesh.cfg",
    "/usr/data/printer_data/config/k1-control-calibration-path.cfg",
    "/usr/data/k1-control-v1/current/config/moonraker.conf",
    "/usr/data/k1-control-v1/current/moonraker/moonraker/moonraker/components/k1_control.py",
    "/usr/data/k1-control-v1/current/moonraker/moonraker/moonraker/components/k1_control_calibration_core.py",
    "/usr/data/k1-control-v1/current/moonraker/moonraker/moonraker/components/k1_control_probe_count.py",
    "/usr/data/k1-control-v1/current/www/mainsail/k1-control/index.html",
    "/usr/data/k1-control-v1/current/www/mainsail/k1-control/app.js",
    "/usr/data/k1-control-v1/current/www/mainsail/k1-control/styles.css",
)


def fetch_json(path):
    started = time.monotonic()
    request = Request(BASE_URL + path, method="GET")
    with urlopen(request, timeout=TIMEOUT_S) as response:
        body = response.read()
        status_code = response.getcode()
    elapsed_ms = round((time.monotonic() - started) * 1000.0, 3)
    if status_code != 200:
        raise RuntimeError("http_status_%s" % status_code)
    return json.loads(body.decode("utf-8")), elapsed_ms


def value_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


def schema_of(value):
    if isinstance(value, dict):
        return {
            "type": "object",
            "properties": {key: schema_of(value[key]) for key in sorted(value)},
        }
    if isinstance(value, list):
        return {
            "type": "array",
            "item_types": sorted(set(value_type(item) for item in value)),
        }
    return {"type": value_type(value)}


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


def hashes():
    return {path: hash_file(path) for path in HASH_PATHS}


def moonraker_sections():
    path = "/usr/data/k1-control-v1/current/config/moonraker.conf"
    if not os.path.isfile(path):
        return []
    names = []
    with open(path, "r", encoding="utf-8", errors="strict") as stream:
        for line in stream:
            match = re.match(r"^\s*\[([^\]]+)\]\s*$", line)
            if match:
                names.append(match.group(1))
    return names


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


def safe_projection(payload):
    result = child(payload, "result")
    status = child(result, "status")
    print_stats = child(status, "print_stats")
    box = child(status, "box")
    extruder = child(status, "extruder")
    heater_bed = child(status, "heater_bed")
    toolhead = child(status, "toolhead")
    bed_mesh = child(status, "bed_mesh")
    gcode_move = child(status, "gcode_move")
    runtime = child(status, "gcode_macro KCTRL_STATE")
    store = child(status, "k1_control_store")
    path_state = child(status, "gcode_macro KCTRL_CAL_PATH_STATE")
    sensor_1 = child(status, "filament_switch_sensor filament_sensor")
    sensor_2 = child(status, "filament_switch_sensor filament_sensor_2")
    safe_box = {
        "state": box.get("state"),
        "t_command": box.get("t_command"),
    }
    for unit_name in ("T1", "T2", "T3", "T4"):
        unit = child(box, unit_name)
        safe_box[unit_name] = {
            "state": unit.get("state"),
            "filament": unit.get("filament"),
        }
    profiles = bed_mesh.get("profiles")
    if not isinstance(profiles, dict):
        profiles = {}
    profile_summaries = {}
    for profile_name in sorted(profiles):
        profile = profiles.get(profile_name)
        points = profile.get("points") if isinstance(profile, dict) else None
        profile_summaries[profile_name] = matrix_summary(points)
    return {
        "eventtime": result.get("eventtime"),
        "print_stats": {
            "state": print_stats.get("state"),
            "filename_present": bool(print_stats.get("filename")),
        },
        "extruder": {
            "temperature": extruder.get("temperature"),
            "target": extruder.get("target"),
            "can_extrude": extruder.get("can_extrude"),
        },
        "heater_bed": {
            "temperature": heater_bed.get("temperature"),
            "target": heater_bed.get("target"),
        },
        "toolhead": {
            "homed_axes": toolhead.get("homed_axes"),
            "position": toolhead.get("position"),
        },
        "bed_mesh": {
            "profile_name": bed_mesh.get("profile_name"),
            "probed_matrix": matrix_summary(bed_mesh.get("probed_matrix")),
            "mesh_matrix": matrix_summary(bed_mesh.get("mesh_matrix")),
            "profiles": profile_summaries,
        },
        "box": safe_box,
        "sensors": {
            "filament_sensor": {
                "enabled": sensor_1.get("enabled"),
                "filament_detected": sensor_1.get("filament_detected"),
            },
            "filament_sensor_2": {
                "enabled": sensor_2.get("enabled"),
                "filament_detected": sensor_2.get("filament_detected"),
            },
        },
        "gcode_move": {"homing_origin": gcode_move.get("homing_origin")},
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
        "store": {
            key: store.get(key)
            for key in (
                "ready",
                "integrity",
                "accepted_z_valid",
                "accepted_z_offset",
                "session_active",
                "low_moves_armed",
            )
        },
        "calibration_path": {
            key: path_state.get(key)
            for key in ("phase", "motion_armed", "commit_ready")
        },
    }


hashes_before = hashes()
server_info_1, server_ms_1 = fetch_json("/server/info")
objects, objects_ms = fetch_json("/printer/objects/list")
state_1, query_ms_1 = fetch_json(QUERY_PATH)
time.sleep(2.0)
state_2, query_ms_2 = fetch_json(QUERY_PATH)
server_info_2, server_ms_2 = fetch_json("/server/info")
hashes_after = hashes()

server_1 = child(server_info_1, "result")
server_2 = child(server_info_2, "result")
object_names = child(objects, "result").get("objects", [])
required_objects = (
    "print_stats",
    "extruder",
    "heater_bed",
    "toolhead",
    "bed_mesh",
    "box",
    "filament_switch_sensor filament_sensor",
    "filament_switch_sensor filament_sensor_2",
    "gcode_move",
    "gcode_macro KCTRL_STATE",
    "k1_control_store",
    "gcode_macro KCTRL_CAL_PATH_STATE",
)

output = {
    "schema": 1,
    "mission": "GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1",
    "authority": "strict_read_only",
    "capture_mode": "remote_sanitization_before_local_processing",
    "identity_values_exported": False,
    "http_methods": ["GET"],
    "query_timeout_s": TIMEOUT_S,
    "query_interval_s": 2.0,
    "server": {
        "first": {
            "klippy_state": server_1.get("klippy_state"),
            "failed_components": server_1.get("failed_components"),
            "warnings": server_1.get("warnings"),
        },
        "second": {
            "klippy_state": server_2.get("klippy_state"),
            "failed_components": server_2.get("failed_components"),
            "warnings": server_2.get("warnings"),
        },
    },
    "required_objects_present": {
        name: name in object_names for name in required_objects
    },
    "response_schema": schema_of(state_1),
    "response_schema_stable": schema_of(state_1) == schema_of(state_2),
    "snapshots": [safe_projection(state_1), safe_projection(state_2)],
    "timings_ms": {
        "server_info": [server_ms_1, server_ms_2],
        "objects_list": [objects_ms],
        "objects_query": [query_ms_1, query_ms_2],
    },
    "hashes_before": hashes_before,
    "hashes_after": hashes_after,
    "moonraker_sections": moonraker_sections(),
    "effects": {
        "remote_files_written": False,
        "gcode_sent": False,
        "guard_called": False,
        "service_action": False,
        "physical_action": False,
    },
}
print(json.dumps(output, sort_keys=True, separators=(",", ":")))
print("K1_READ_ONLY_QUALIFICATION_CAPTURE_V1_OK")
'@

$remoteProgram = $remotePython.Replace("`r`n", "`n")
$remoteCommand = "'/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python'"

Write-Host "QUALIFICATION K1 STRICTEMENT EN LECTURE SEULE : $SessionLabel"
Write-Host 'GET locaux uniquement ; aucune identite exportee, aucun G-code, fichier, service ou effet physique.'

$remoteProgram | & ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ServerAliveInterval=10' `
    -o 'ServerAliveCountMax=3' `
    k1max-root `
    $remoteCommand | Set-Content -LiteralPath $capturePath -Encoding utf8

$sshExitCode = $LASTEXITCODE
$metadata.local_end = (Get-Date).ToString('o')
$metadata.ssh_exit_code = $sshExitCode
$metadata.capture_path = $capturePath
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8

Write-Host "K1_READ_ONLY_QUALIFICATION_CLOSED exit_code=$sshExitCode capture=$capturePath"
exit $sshExitCode
