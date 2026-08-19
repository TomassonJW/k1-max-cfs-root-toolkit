[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SessionDirectory,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SessionLabel,

    [ValidateRange(0, 86400)]
    [int]$DurationSeconds = 0
)

$ErrorActionPreference = 'Stop'

$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
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

$capturePath = Join-Path $resolvedSession "$SessionLabel.raw.txt"
$metadataPath = Join-Path $resolvedSession "$SessionLabel.local-metadata.json"
if (Test-Path -LiteralPath $capturePath) {
    throw 'La capture existe deja. Utilise un nouvel identifiant de session.'
}

$metadata = [ordered]@{
    session_label = $SessionLabel
    local_start = (Get-Date).ToString('o')
    duration_seconds = $DurationSeconds
    mode = 'read_only_passive'
    ssh_alias = 'k1max-root'
}
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8

$remoteScript = @'
set -eu

echo '=== PASSIVE_TRACE_PREFLIGHT_BEGIN ==='
date
uptime
sha256sum /usr/data/printer_data/config/printer.cfg /usr/data/printer_data/config/gcode_macro.cfg /usr/data/printer_data/config/box.cfg 2>/dev/null
grep -n 'z_offset' /usr/data/printer_data/config/printer.cfg 2>/dev/null | tail -n 12
stat -c 'log=%n size=%s modified=%Y' /usr/data/printer_data/logs/klippy.log 2>/dev/null
df -h /usr/data 2>/dev/null
echo '=== PASSIVE_TRACE_STREAM_BEGIN ==='

/usr/share/klippy-env/bin/python - <<'PY'
from __future__ import print_function

import datetime
import json
import os
import select
import socket
import sys
import time

LOG_PATH = "/usr/data/printer_data/logs/klippy.log"
KLIPPY_SOCKET = "/tmp/klippy_uds"
SAMPLE_SECONDS = 2.0
DURATION_SECONDS = __DURATION_SECONDS__

OBJECTS = {
    "print_stats": None,
    "extruder": ["temperature", "target", "power", "can_extrude", "pressure_advance", "smooth_time"],
    "heater_bed": ["temperature", "target", "power"],
    "toolhead": ["homed_axes", "position", "print_time", "estimated_print_time", "stalls"],
    "gcode_move": ["homing_origin", "position", "gcode_position", "speed_factor", "extrude_factor"],
}


def timestamp():
    return datetime.datetime.now().isoformat()


def emit(kind, payload):
    if not isinstance(payload, str):
        payload = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    print("{}|{}|{}".format(kind, timestamp(), payload))
    sys.stdout.flush()


def open_subscription():
    request = {
        "id": 1,
        "method": "objects/subscribe",
        "params": {"objects": OBJECTS, "response_template": {"stream": "status"}},
    }
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(5)
    client.connect(KLIPPY_SOCKET)
    client.sendall((json.dumps(request) + "\x03").encode("utf-8"))
    return client


def read_initial_message(client):
    buffer = b""
    while b"\x03" not in buffer:
        chunk = client.recv(65536)
        if not chunk:
            raise RuntimeError("Klipper closed the subscription during setup")
        buffer += chunk
    frame, remainder = buffer.split(b"\x03", 1)
    return json.loads(frame.decode("utf-8")), bytearray(remainder)


def merge_status(current, update):
    for object_name, fields in update.items():
        if object_name not in current or not isinstance(fields, dict):
            current[object_name] = fields
        else:
            current[object_name].update(fields)


def critical_signature(status):
    print_stats = status.get("print_stats", {})
    extruder = status.get("extruder", {})
    heater_bed = status.get("heater_bed", {})
    toolhead = status.get("toolhead", {})
    gcode_move = status.get("gcode_move", {})
    info = print_stats.get("info", {}) or {}
    return (
        print_stats.get("state"),
        print_stats.get("filename"),
        info.get("current_layer"),
        info.get("total_layer"),
        extruder.get("target"),
        extruder.get("pressure_advance"),
        heater_bed.get("target"),
        toolhead.get("homed_axes"),
        tuple(gcode_move.get("homing_origin", [])),
    )


def open_log_at_end():
    handle = open(LOG_PATH, "r")
    handle.seek(0, os.SEEK_END)
    stat = os.fstat(handle.fileno())
    emit("META", {"event": "log_open", "inode": stat.st_ino, "offset": handle.tell()})
    return handle, stat.st_ino


start = time.time()
client = open_subscription()
initial_message, socket_buffer = read_initial_message(client)
current_state = initial_message.get("result", {}).get("status", {})
last_eventtime = initial_message.get("result", {}).get("eventtime")
last_signature = critical_signature(current_state)
last_emit = time.time()
emit("STATE", {"eventtime": last_eventtime, "status": current_state})
client.setblocking(False)
log_handle, log_inode = open_log_at_end()
emit("META", {"event": "monitor_ready", "duration_seconds": DURATION_SECONDS})

try:
    while True:
        now = time.time()
        if DURATION_SECONDS and now - start >= DURATION_SECONDS:
            emit("META", {"event": "duration_reached"})
            break

        readable, _, _ = select.select([client], [], [], 0)
        if readable:
            chunk = client.recv(65536)
            if not chunk:
                emit("ERROR", {"event": "subscription_closed"})
                break
            socket_buffer.extend(chunk)

        while b"\x03" in socket_buffer:
            frame, remainder = socket_buffer.split(b"\x03", 1)
            socket_buffer = bytearray(remainder)
            if not frame:
                continue
            message = json.loads(bytes(frame).decode("utf-8"))
            params = message.get("params", {})
            update = params.get("status", {})
            if update:
                merge_status(current_state, update)
                last_eventtime = params.get("eventtime", last_eventtime)
                signature = critical_signature(current_state)
                if signature != last_signature or now - last_emit >= SAMPLE_SECONDS:
                    emit("STATE", {"eventtime": last_eventtime, "status": current_state})
                    last_emit = now
                    last_signature = signature

        while True:
            line = log_handle.readline()
            if not line:
                break
            emit("LOG", line.rstrip("\r\n"))

        try:
            current = os.stat(LOG_PATH)
            if current.st_ino != log_inode or current.st_size < log_handle.tell():
                log_handle.close()
                log_handle, log_inode = open_log_at_end()
                emit("META", {"event": "log_reopened"})
        except Exception as exc:
            emit("ERROR", {"event": "log_stat_failed", "message": str(exc)})

        time.sleep(0.2)
except KeyboardInterrupt:
    emit("META", {"event": "operator_stop"})
finally:
    log_handle.close()
    client.close()
    emit("META", {"event": "monitor_closed"})
PY
'@

$remoteScript = $remoteScript.Replace('__DURATION_SECONDS__', $DurationSeconds.ToString([Globalization.CultureInfo]::InvariantCulture))
$remoteBytes = [Text.Encoding]::UTF8.GetBytes($remoteScript.Replace("`r`n", "`n"))
$remoteBase64 = [Convert]::ToBase64String($remoteBytes)
$remoteCommand = "echo $remoteBase64 | base64 -d | sh"

Write-Host "CAPTURE PASSIVE : $SessionLabel"
Write-Host 'Aucune commande de mouvement, chauffe, impression ou configuration ne sera envoyee.'
if ($DurationSeconds -eq 0) {
    Write-Host 'Laisse cette fenetre ouverte pendant le travail. Ctrl+C arrete uniquement la capture locale.'
}
Write-Host ''

& ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ServerAliveInterval=15' `
    -o 'ServerAliveCountMax=20' `
    k1max-root `
    $remoteCommand | Tee-Object -LiteralPath $capturePath

$sshExitCode = $LASTEXITCODE
Write-Host ''
Write-Host "PASSIVE_TRACE_CLOSED exit_code=$sshExitCode capture=$capturePath"
exit $sshExitCode
