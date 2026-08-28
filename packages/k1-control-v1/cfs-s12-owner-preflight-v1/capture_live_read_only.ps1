[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SessionDirectory,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SessionLabel,

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$PrinterHost = 'k1max-root'
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
    mission = 'G4-K1-CONTROL-CFS-S12-OWNER-PREFLIGHT-V1'
    mode = 'single_ssh_session_strict_read_only_s12_inventory'
    ssh_alias = $PrinterHost
    http_methods = @('GET')
    remote_sanitization = $true
    remote_writes = $false
    remote_binary_copied = $false
    remote_logs_read = $false
    gcode_requests = $false
    cfs_commands = $false
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
    "print_stats=state"
    "&extruder=temperature,target,can_extrude"
    "&heater_bed=temperature,target"
    "&toolhead=homed_axes"
    "&bed_mesh=profile_name"
    "&box"
    "&filament_switch_sensor+filament_sensor=filament_detected,enabled"
    "&filament_switch_sensor+filament_sensor_2=filament_detected,enabled"
    "&gcode_move=homing_origin"
    "&gcode_macro+KCTRL_STATE=ready,session_active,accepted_z_valid,accepted_z_offset,low_moves_armed"
    "&k1_control_store=ready,integrity,accepted_z_valid,accepted_z_offset,session_active,low_moves_armed"
)

FILE_PATHS = {
    "box_loader": "/usr/share/klipper/klippy/extras/box.py",
    "box_loader_bytecode": "/usr/share/klipper/klippy/extras/box.pyc",
    "box_wrapper": "/usr/share/klipper/klippy/extras/box_wrapper.cpython-38-mipsel-linux-gnu.so",
    "printer_config": "/usr/data/printer_data/config/printer.cfg",
    "box_config": "/usr/data/printer_data/config/box.cfg",
    "gcode_macro_config": "/usr/data/printer_data/config/gcode_macro.cfg",
}

CALLBACK_MARKERS = (
    "material_auto_refill",
    "filament_err_tighten_up_event",
    "filament_err_retry_process",
    "extrusion_all_materials",
    "check_material_refill",
    "power_loss_clean",
    "power_loss_restore",
    "print_end_err_retry_process",
    "empty_print_retry_process",
    "if_in_resume",
    "do_after_pause",
    "box_end",
    "update_Tnn_map",
    "macro_err_retry_process",
    "retrude_err_retry_process",
    "box_extrude_err_retry_process",
    "material_change_flush",
)

ARGUMENT_TOKENS = (
    "ACTION",
    "ADDR",
    "CMD",
    "COUNT",
    "DATA",
    "ENABLE",
    "INTERVAL",
    "LAST_TNN",
    "LEN",
    "MODE",
    "NUM",
    "PART",
    "PERCENT",
    "POSITION",
    "POWER_ON",
    "TEMP",
    "TIMEOUT",
    "TNN",
    "TRIGGER",
    "VELOCITY",
)

DANGER_MARKERS = (
    "BED_MESH_CLEAR",
    "FORCE_MOVE",
    "G28",
    "M104",
    "M109",
    "PAUSE",
    "RESUME",
    "SAVE_CONFIG",
    "SET_GCODE_OFFSET",
)

BOX_OPTION_KEYS = {
    "Tn_extrude",
    "Tn_extrude_percent",
    "Tn_extrude_temp",
    "Tn_extrude_velocity",
    "Tn_retrude",
    "Tn_retrude_velocity",
    "buffer_empty_len",
    "clean_left_pos_x",
    "clean_left_pos_y",
    "clean_left_pos_z",
    "clean_right_pos_x",
    "clean_right_pos_y",
    "clean_right_pos_z",
    "clean_velocity",
    "cut_pos_offset",
    "cut_pos_x",
    "cut_pos_y",
    "cut_velocity",
    "extrude_pos_x",
    "extrude_pos_y",
    "extrude_pos_z",
    "filament_sensor",
    "has_extrude_pos",
    "pre_cut_pos_x",
    "pre_cut_pos_y",
    "safe_pos_y",
    "switch_pin",
}


def child(mapping, key):
    value = mapping.get(key) if isinstance(mapping, dict) else None
    return value if isinstance(value, dict) else {}


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


def hash_file(path):
    if not os.path.isfile(path):
        return {"exists": False, "size_bytes": None, "sha256": None}
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return {"exists": True, "size_bytes": size, "sha256": digest.hexdigest()}


def file_inventory():
    return {role: dict({"path": path}, **hash_file(path)) for role, path in FILE_PATHS.items()}


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


def known_identity(value):
    text = str(value).strip().lower()
    return text not in ("", "-1", "none", "unknown", "null")


def bool_vector(values, predicate):
    if not isinstance(values, list):
        return []
    return [bool(predicate(item)) for item in values]


def safe_t_command(value):
    text = value if isinstance(value, str) else ""
    commands = sorted(set(re.findall(r"\b(?:BOX_[A-Z0-9_]+|T[1-4][A-D]|T(?:1[0-5]|[0-9]))\b", text)))
    argument_names = sorted(set(re.findall(r"\b([A-Z][A-Z0-9_]*)\s*=", text)))
    return {
        "present": bool(text.strip()),
        "commands": commands,
        "argument_names": argument_names,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None,
    }


def safe_same_material(value):
    if not isinstance(value, list):
        return []
    groups = []
    for raw_group in value:
        slots = []
        if isinstance(raw_group, (list, tuple)):
            for item in raw_group:
                candidates = item if isinstance(item, (list, tuple)) else (item,)
                for candidate in candidates:
                    text = str(candidate)
                    if re.match(r"^T[1-4][A-D]$", text):
                        slots.append(text)
        slots = sorted(set(slots))
        if slots:
            groups.append(slots)
    return sorted(groups)


def safe_unit(unit):
    unit = unit if isinstance(unit, dict) else {}
    return {
        "state": unit.get("state"),
        "filament": unit.get("filament"),
        "temperature": unit.get("temperature"),
        "dry_and_humidity": unit.get("dry_and_humidity"),
        "filament_detected": unit.get("filament_detected"),
        "measuring_wheel": unit.get("measuring_wheel"),
        "version": unit.get("version"),
        "mode": unit.get("mode"),
        "rfid_known_by_slot": bool_vector(unit.get("vender"), known_identity),
        "material_type_known_by_slot": bool_vector(unit.get("material_type"), known_identity),
        "color_known_by_slot": bool_vector(unit.get("color_value"), known_identity),
        "remaining_length_known_by_slot": bool_vector(unit.get("remain_len"), known_identity),
        "identity_fields_stripped": [key for key in ("sn", "uuid") if key in unit],
        "safe_source_fields": sorted(key for key in unit if key not in ("sn", "uuid")),
    }


def safe_box(box):
    box = box if isinstance(box, dict) else {}
    same_material = box.get("same_material")
    canonical = json.dumps(same_material, sort_keys=True, separators=(",", ":"))
    result = {
        "state": box.get("state"),
        "filament": box.get("filament"),
        "auto_refill": box.get("auto_refill"),
        "enable": box.get("enable"),
        "filament_useup": box.get("filament_useup"),
        "cut_pos": box.get("cut_pos"),
        "t_command": safe_t_command(box.get("t_command")),
        "same_material_groups": safe_same_material(same_material),
        "same_material_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "safe_source_fields": sorted(key for key in box if key not in ("sn", "uuid")),
    }
    for unit_name in ("T1", "T2", "T3", "T4"):
        result[unit_name] = safe_unit(box.get(unit_name))
    return result


def safe_projection(payload):
    result = child(payload, "result")
    status = child(result, "status")
    print_stats = child(status, "print_stats")
    extruder = child(status, "extruder")
    heater_bed = child(status, "heater_bed")
    toolhead = child(status, "toolhead")
    bed_mesh = child(status, "bed_mesh")
    sensor_1 = child(status, "filament_switch_sensor filament_sensor")
    sensor_2 = child(status, "filament_switch_sensor filament_sensor_2")
    gcode_move = child(status, "gcode_move")
    runtime = child(status, "gcode_macro KCTRL_STATE")
    store = child(status, "k1_control_store")
    return {
        "eventtime": result.get("eventtime"),
        "print_state": print_stats.get("state"),
        "extruder": {
            "temperature": extruder.get("temperature"),
            "target": extruder.get("target"),
            "can_extrude": extruder.get("can_extrude"),
        },
        "heater_bed": {
            "temperature": heater_bed.get("temperature"),
            "target": heater_bed.get("target"),
        },
        "homed_axes": toolhead.get("homed_axes"),
        "active_mesh": bed_mesh.get("profile_name"),
        "box": safe_box(status.get("box")),
        "filament_sensors": {
            "filament_sensor": {
                "enabled": sensor_1.get("enabled"),
                "filament_detected": sensor_1.get("filament_detected"),
            },
            "filament_sensor_2": {
                "enabled": sensor_2.get("enabled"),
                "filament_detected": sensor_2.get("filament_detected"),
            },
        },
        "homing_origin": gcode_move.get("homing_origin"),
        "runtime": {key: runtime.get(key) for key in (
            "ready", "session_active", "accepted_z_valid", "accepted_z_offset", "low_moves_armed"
        )},
        "store": {key: store.get(key) for key in (
            "ready", "integrity", "accepted_z_valid", "accepted_z_offset", "session_active", "low_moves_armed"
        )},
    }


def binary_inventory(path):
    if not os.path.isfile(path):
        return {
            "command_names": [],
            "callback_markers": {},
            "argument_tokens": {},
            "danger_markers": {},
            "embedded_paths": [],
        }
    with open(path, "rb") as stream:
        data = stream.read()
    strings = [match.group(0).decode("ascii", "ignore") for match in re.finditer(rb"[ -~]{4,}", data)]
    text = "\n".join(strings)
    command_names = sorted(set(re.findall(r"\bBOX_[A-Z0-9_]+\b", text)))
    embedded_paths = sorted(set(
        item for item in strings
        if re.match(r"^/(?:etc|mnt|root|tmp|usr)/[A-Za-z0-9._/-]+$", item)
    ))
    return {
        "command_names": command_names,
        "callback_markers": {marker: marker in text for marker in CALLBACK_MARKERS},
        "argument_tokens": {
            token: bool(re.search(r"(?:^|\W)%s(?:$|\W)" % re.escape(token), text))
            for token in ARGUMENT_TOKENS
        },
        "danger_markers": {marker: marker in text for marker in DANGER_MARKERS},
        "embedded_paths": embedded_paths[:100],
    }


def read_text(path):
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as stream:
        return stream.read()


def config_inventory():
    section_names = []
    include_names = []
    box_options = {}
    box_calls = []
    for role in ("printer_config", "box_config", "gcode_macro_config"):
        path = FILE_PATHS[role]
        current_section = ""
        for line_number, line in enumerate(read_text(path).splitlines(), 1):
            stripped = line.strip()
            section = re.match(r"^\[([^\]]+)\]$", stripped)
            if section:
                current_section = section.group(1)
                section_names.append({"file_role": role, "name": current_section})
                if current_section.lower().startswith("include "):
                    include_names.append(current_section[8:].strip())
                continue
            if not stripped or stripped.startswith("#"):
                continue
            if current_section.lower() == "box" and ":" in stripped:
                key, value = stripped.split(":", 1)
                key = key.strip()
                if key in BOX_OPTION_KEYS:
                    box_options[key] = value.strip()
            commands = sorted(set(re.findall(r"\bBOX_[A-Z0-9_]+\b", stripped)))
            if commands:
                argument_names = sorted(set(re.findall(r"\b([A-Z][A-Z0-9_]*)\s*=", stripped)))
                for command in commands:
                    box_calls.append({
                        "file_role": role,
                        "section": current_section,
                        "line": line_number,
                        "command": command,
                        "argument_names": argument_names,
                    })
    return {
        "section_names": section_names,
        "include_names": sorted(set(include_names)),
        "box_options": box_options,
        "box_calls": box_calls,
    }


files_before = file_inventory()
server_info, server_ms = fetch_json("/server/info")
objects, objects_ms = fetch_json("/printer/objects/list")
gcode_help, help_ms = fetch_json("/printer/gcode/help")
state_1_raw, state_1_ms = fetch_json(QUERY_PATH)
state_1 = safe_projection(state_1_raw)
binary = binary_inventory(FILE_PATHS["box_wrapper"])
configs = config_inventory()
time.sleep(1.0)
state_2_raw, state_2_ms = fetch_json(QUERY_PATH)
state_2 = safe_projection(state_2_raw)
files_after = file_inventory()

server = child(server_info, "result")
object_names = child(objects, "result").get("objects", [])
help_result = child(gcode_help, "result")
registered_commands = {}
for command in sorted(help_result):
    if command.startswith("BOX_") or re.match(r"^T(?:[1-4][A-D]|1[0-5]|[0-9])$", command):
        description = help_result.get(command)
        registered_commands[command] = str(description)[:240] if description is not None else ""

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
)

output = {
    "schema": 1,
    "mission": "G4-K1-CONTROL-CFS-S12-OWNER-PREFLIGHT-V1",
    "authority": "strict_read_only",
    "capture_mode": "single_ssh_session_remote_sanitization",
    "identity_values_exported": False,
    "identity_fields_stripped": ["sn", "uuid"],
    "http_methods": ["GET"],
    "query_timeout_s": TIMEOUT_S,
    "server": {
        "klippy_state": server.get("klippy_state"),
        "failed_components": server.get("failed_components"),
        "warnings": server.get("warnings"),
    },
    "required_objects_present": {name: name in object_names for name in required_objects},
    "registered_commands": registered_commands,
    "binary_inventory": binary,
    "config_inventory": configs,
    "snapshots": [state_1, state_2],
    "safe_response_schema": schema_of(state_1),
    "safe_response_schema_stable": schema_of(state_1) == schema_of(state_2),
    "files_before": files_before,
    "files_after": files_after,
    "timings_ms": {
        "server_info": server_ms,
        "objects_list": objects_ms,
        "gcode_help": help_ms,
        "objects_query": [state_1_ms, state_2_ms],
    },
    "effects": {
        "remote_files_written": False,
        "remote_binary_copied": False,
        "logs_read": False,
        "gcode_sent": False,
        "cfs_command_sent": False,
        "service_action": False,
        "physical_action": False,
    },
}
print(json.dumps(output, sort_keys=True, separators=(",", ":")))
print("CFS_S12_OWNER_PREFLIGHT_V1_CAPTURE_OK")
'@

$remoteProgram = $remotePython.Replace("`r`n", "`n")
$remoteCommand = "env PYTHONDONTWRITEBYTECODE=1 '/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' -B -"

Write-Host "PREFLIGHT CFS S12 STRICTEMENT EN LECTURE SEULE : $SessionLabel"
Write-Host 'Une session SSH, GET locaux et lectures de fichiers seulement ; aucune identite CFS exportee.'

$remoteProgram | & ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ConnectTimeout=8' `
    -o 'ServerAliveInterval=10' `
    -o 'ServerAliveCountMax=3' `
    $PrinterHost `
    $remoteCommand | Set-Content -LiteralPath $capturePath -Encoding utf8

$sshExitCode = $LASTEXITCODE
$metadata.local_end = (Get-Date).ToString('o')
$metadata.ssh_exit_code = $sshExitCode
$metadata.capture_path = $capturePath
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8

Write-Host "CFS_S12_OWNER_PREFLIGHT_V1_CLOSED exit_code=$sshExitCode capture=$capturePath"
exit $sshExitCode
