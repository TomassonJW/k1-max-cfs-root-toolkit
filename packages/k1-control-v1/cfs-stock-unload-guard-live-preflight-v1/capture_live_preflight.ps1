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

$capturePath = Join-Path $resolvedSession "$SessionLabel.private.txt"
$metadataPath = Join-Path $resolvedSession "$SessionLabel.local-metadata.json"
if (Test-Path -LiteralPath $capturePath) {
    throw 'La capture existe deja. Utilise un nouvel identifiant de session.'
}

$metadata = [ordered]@{
    session_label = $SessionLabel
    local_start = (Get-Date).ToString('o')
    mode = 'strict_read_only_stock_unload_guard_live_preflight'
    ssh_alias = 'k1max-root'
    remote_writes = $false
    gcode_requests = $false
    service_actions = $false
}
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8

$remoteScript = @'
set -eu

echo '=== LIVE_PREFLIGHT_BEGIN ==='
date
uptime

echo '=== HASHES_BEFORE_BEGIN ==='
sha256sum \
  /usr/data/printer_data/config/printer.cfg \
  /usr/data/printer_data/config/box.cfg \
  /usr/data/printer_data/config/gcode_macro.cfg
echo '=== HASHES_BEFORE_END ==='

echo '=== SERVER_INFO_BEGIN ==='
curl http://127.0.0.1:7125/server/info
echo
echo '=== SERVER_INFO_END ==='

echo '=== OBJECT_LIST_BEGIN ==='
curl http://127.0.0.1:7125/printer/objects/list
echo
echo '=== OBJECT_LIST_END ==='

echo '=== STATE_1_BEGIN ==='
curl 'http://127.0.0.1:7125/printer/objects/query?print_stats=state,filename&extruder=temperature,target,can_extrude&heater_bed=temperature,target&box&filament_switch_sensor+filament_sensor=filament_detected,enabled&filament_switch_sensor+filament_sensor_2=filament_detected,enabled'
echo
echo '=== STATE_1_END ==='

sleep 2

echo '=== STATE_2_BEGIN ==='
curl 'http://127.0.0.1:7125/printer/objects/query?print_stats=state,filename&extruder=temperature,target,can_extrude&heater_bed=temperature,target&box&filament_switch_sensor+filament_sensor=filament_detected,enabled&filament_switch_sensor+filament_sensor_2=filament_detected,enabled'
echo
echo '=== STATE_2_END ==='

echo '=== HASHES_AFTER_BEGIN ==='
sha256sum \
  /usr/data/printer_data/config/printer.cfg \
  /usr/data/printer_data/config/box.cfg \
  /usr/data/printer_data/config/gcode_macro.cfg
echo '=== HASHES_AFTER_END ==='
echo 'LIVE_PREFLIGHT_READ_ONLY_OK'
'@

$remoteBytes = [Text.Encoding]::UTF8.GetBytes($remoteScript.Replace("`r`n", "`n"))
$remoteBase64 = [Convert]::ToBase64String($remoteBytes)
$remoteCommand = "echo $remoteBase64 | base64 -d | sh"

Write-Host "PREFLIGHT LIVE CFS EN LECTURE SEULE : $SessionLabel"
Write-Host 'Aucun G-code, chauffage, mouvement, service ou fichier distant ne sera modifie.'

& ssh.exe `
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

Write-Host "LIVE_PREFLIGHT_CLOSED exit_code=$sshExitCode capture=$capturePath"
exit $sshExitCode
