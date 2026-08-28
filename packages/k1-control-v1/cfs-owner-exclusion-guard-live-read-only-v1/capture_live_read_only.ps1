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

$capturePath = Join-Path $resolvedSession "$SessionLabel.safe.jsonl"
$metadataPath = Join-Path $resolvedSession "$SessionLabel.local-metadata.json"
if (Test-Path -LiteralPath $capturePath) {
    throw 'La capture existe deja. Utilise un nouvel identifiant de session.'
}

$metadata = [ordered]@{
    session_label = $SessionLabel
    local_start = (Get-Date).ToString('o')
    mission = 'G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-LIVE-READ-ONLY-V1'
    mode = 'single_ssh_two_get_remote_sanitization'
    ssh_alias = $PrinterHost
    http_methods = @('GET')
    remote_sanitization = $true
    identity_values_exported = $false
    guard_imported_or_called = $false
    gcode_requests = $false
    remote_writes = $false
    service_actions = $false
    physical_actions = $false
}
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8

$remotePython = @'
from __future__ import print_function

import hashlib
import json
import os
import time
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:7125"
TIMEOUT_S = 5.0
QUERY_PATH = (
    "/printer/objects/query?"
    "print_stats=state"
    "&extruder=target"
    "&heater_bed=target"
    "&toolhead=homed_axes"
    "&bed_mesh=profile_name"
    "&box"
    "&gcode_move=homing_origin"
    "&k1_control_store=ready,integrity,accepted_z_valid,accepted_z_offset,session_active,low_moves_armed"
)
CONFIG_PATHS = (
    "/usr/data/printer_data/config/printer.cfg",
    "/usr/data/printer_data/config/box.cfg",
    "/usr/data/printer_data/config/gcode_macro.cfg",
)
UNITS = ("T1", "T2", "T3", "T4")
SLOTS = ("A", "B", "C", "D")


def child(value, key):
    result = value.get(key) if isinstance(value, dict) else None
    return result if isinstance(result, dict) else {}


def canonical_hash(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def hash_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def config_hashes():
    return {path: hash_file(path) if os.path.isfile(path) else None for path in CONFIG_PATHS}


def fetch_state():
    request = Request(BASE_URL + QUERY_PATH, method="GET")
    with urlopen(request, timeout=TIMEOUT_S) as response:
        if response.getcode() != 200:
            raise RuntimeError("http_status_%s" % response.getcode())
        return json.loads(response.read().decode("utf-8"))


def safe_snapshot(payload, sample_seq):
    result = child(payload, "result")
    status = child(result, "status")
    print_stats = child(status, "print_stats")
    extruder = child(status, "extruder")
    heater_bed = child(status, "heater_bed")
    toolhead = child(status, "toolhead")
    bed_mesh = child(status, "bed_mesh")
    box = child(status, "box")
    gcode_move = child(status, "gcode_move")
    store = child(status, "k1_control_store")

    units = {}
    connected = []
    engaged = []
    for unit_name in UNITS:
        unit = child(box, unit_name)
        state = unit.get("state")
        filament = unit.get("filament")
        units[unit_name] = {"state": state, "filament": filament}
        if state == "connect":
            connected.append(unit_name)
            if filament in SLOTS:
                engaged.append(unit_name + filament)

    raw_command = box.get("t_command")
    command_text = raw_command if isinstance(raw_command, str) else ""
    active_command = "" if not command_text else "present:" + hashlib.sha256(
        command_text.encode("utf-8")
    ).hexdigest()
    mapping_material = {
        "box_state": box.get("state"),
        "units": units,
        "same_material_sha256": canonical_hash(box.get("same_material")),
    }
    accepted_z_material = {
        key: store.get(key)
        for key in ("ready", "integrity", "accepted_z_valid", "accepted_z_offset")
    }
    homing_origin = gcode_move.get("homing_origin")
    effective_z = homing_origin[2] if isinstance(homing_origin, list) and len(homing_origin) >= 3 else None

    return {
        "schema": 1,
        "sample_seq": sample_seq,
        "mapping_revision": "mapping:" + canonical_hash(mapping_material),
        "connection_epoch": None,
        "printer_state": print_stats.get("state"),
        "connected_units": connected,
        "active_command": active_command,
        "stock_auto_refill": box.get("auto_refill"),
        "stock_cfs_print_enable": box.get("enable"),
        "engaged_routes": engaged,
        "protected": {
            "mesh_profile": bed_mesh.get("profile_name"),
            "accepted_z_revision": "accepted-z:" + canonical_hash(accepted_z_material),
            "effective_z_offset_mm": effective_z,
            "homed_axes": toolhead.get("homed_axes"),
            "nozzle_target_c": extruder.get("target"),
            "bed_target_c": heater_bed.get("target"),
        },
    }


hashes_before = config_hashes()
first = safe_snapshot(fetch_state(), 1)
time.sleep(2.0)
second = safe_snapshot(fetch_state(), 2)
hashes_after = config_hashes()

output = {
    "schema": 1,
    "mission": "G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-LIVE-READ-ONLY-V1",
    "authority": "strict_read_only",
    "capture_mode": "single_ssh_two_get_remote_sanitization",
    "identity_values_exported": False,
    "identity_fields_stripped": ["sn", "uuid"],
    "http_methods": ["GET"],
    "query_count": 2,
    "query_timeout_s": TIMEOUT_S,
    "connection_epoch_observable": False,
    "connection_epoch_source": "unavailable_no_notification_epoch",
    "snapshots": [first, second],
    "configuration_hashes_before": hashes_before,
    "configuration_hashes_after": hashes_after,
    "effects": {
        "remote_files_written": False,
        "gcode_sent": False,
        "heater_action": False,
        "motion_action": False,
        "cfs_action": False,
        "service_action": False,
        "guard_imported_or_called": False,
    },
}
print(json.dumps(output, sort_keys=True, separators=(",", ":")))
print("CFS_OWNER_EXCLUSION_GUARD_LIVE_READ_ONLY_V1_CAPTURE_OK")
'@

$remoteProgram = $remotePython.Replace("`r`n", "`n")
$remoteCommand = "env PYTHONDONTWRITEBYTECODE=1 '/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' -B -"

Write-Host "LECTURE SEULE GARDE EXCLUSION CFS : $SessionLabel"
Write-Host 'Deux GET locaux, nettoyage sur la K1, aucune commande ni effet.'

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

Write-Host "CFS_OWNER_EXCLUSION_GUARD_LIVE_READ_ONLY_V1_CLOSED exit_code=$sshExitCode capture=$capturePath"
exit $sshExitCode
