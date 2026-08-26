[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SessionDirectory,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SessionLabel
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
    mode = 'strict_read_only_cfs_audit'
    ssh_alias = 'k1max-root'
    remote_writes = $false
    gcode_requests = $false
}
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8

$remoteScript = @'
set -eu

echo '=== CFS_READ_ONLY_AUDIT_BEGIN ==='
date
uptime

echo '=== BASELINE_HASHES_BEGIN ==='
sha256sum \
  /usr/data/printer_data/config/printer.cfg \
  /usr/data/printer_data/config/box.cfg \
  /usr/data/printer_data/config/gcode_macro.cfg \
  /usr/data/printer_data/config/k1-control-z-mesh.cfg \
  /usr/data/printer_data/config/k1-control-calibration-path.cfg 2>/dev/null
echo '=== BASELINE_HASHES_END ==='

echo '=== SERVER_INFO_BEGIN ==='
curl http://127.0.0.1:7125/server/info
echo
echo '=== SERVER_INFO_END ==='

echo '=== OBJECT_LIST_BEGIN ==='
curl http://127.0.0.1:7125/printer/objects/list
echo
echo '=== OBJECT_LIST_END ==='

echo '=== OBJECT_QUERY_BEGIN ==='
curl 'http://127.0.0.1:7125/printer/objects/query?print_stats=state,filename&extruder=temperature,target,can_extrude&heater_bed=temperature,target&toolhead=homed_axes&bed_mesh=profile_name&box&filament_switch_sensor+filament_sensor=filament_detected,enabled&filament_switch_sensor+filament_sensor_2=filament_detected,enabled&gcode_move=homing_origin&gcode_macro+KCTRL_STATE&k1_control_store&gcode_macro+KCTRL_CAL_PATH_STATE'
echo
echo '=== OBJECT_QUERY_END ==='

echo '=== BOX_CONFIG_BEGIN ==='
cat /usr/data/printer_data/config/box.cfg
echo '=== BOX_CONFIG_END ==='

echo '=== SENSOR_CONFIG_BEGIN ==='
awk '
  /^\[filament_switch_sensor filament_sensor\]$/ {show=1}
  /^\[filament_switch_sensor filament_sensor_2\]$/ {show=1}
  /^\[/ && $0 !~ /^\[filament_switch_sensor filament_sensor(_2)?\]$/ && show {show=0}
  show {print}
' /usr/data/printer_data/config/printer.cfg
echo '=== SENSOR_CONFIG_END ==='

echo '=== PERSISTED_TN_DATA_BEGIN ==='
stat /usr/data/creality/userdata/box/tn_data.json
sha256sum /usr/data/creality/userdata/box/tn_data.json
cat /usr/data/creality/userdata/box/tn_data.json
echo
echo '=== PERSISTED_TN_DATA_END ==='

echo '=== PERSISTED_BOX_INFO_BEGIN ==='
sha256sum \
  /usr/data/creality/userdata/box/material_box_config.json \
  /usr/data/creality/userdata/box/material_box_info.json \
  /usr/data/creality/userdata/box/material_modify_info.json 2>/dev/null
cat /usr/data/creality/userdata/box/material_box_config.json
cat /usr/data/creality/userdata/box/material_box_info.json
cat /usr/data/creality/userdata/box/material_modify_info.json
echo '=== PERSISTED_BOX_INFO_END ==='

echo '=== BOX_RELATED_FILES_BEGIN ==='
find /usr/data/creality/userdata/box -maxdepth 2 -type f -print 2>/dev/null
echo '=== BOX_RELATED_FILES_END ==='

echo '=== RELEVANT_LOG_HISTORY_BEGIN ==='
tail -n 160000 /usr/data/printer_data/logs/klippy.log 2>/dev/null \
  | grep -E -i 'BOX_|box_wrapper|filament_switch|filament_sensor|t_command|T[1-4][A-D]|retrude|refill|cut_pos|material' \
  | grep -E -v 'GET_BOX_STATE|webhooks: method:objects/query|_handle_query after complete.wait' \
  | tail -n 5000 || true
echo '=== RELEVANT_LOG_HISTORY_END ==='

echo '=== MAPPING_LOG_HISTORY_BEGIN ==='
grep -E -i 'cmd_T |last_cmd:|last_tnn|tnn_map|filament_err|material_auto_refill|extrude_process_stage|BOX_MODIFY_TN|filament_sensor_2 pause' \
  /usr/data/printer_data/logs/klippy.log 2>/dev/null \
  | grep -E -v 'GET_BOX_STATE|webhooks: method:objects/query|_handle_query after complete.wait' \
  | tail -n 4000 || true
echo '=== MAPPING_LOG_HISTORY_END ==='

echo '=== FINAL_OBJECT_QUERY_BEGIN ==='
curl 'http://127.0.0.1:7125/printer/objects/query?print_stats=state,filename&extruder=temperature,target,can_extrude&heater_bed=temperature,target&toolhead=homed_axes&bed_mesh=profile_name&box&filament_switch_sensor+filament_sensor=filament_detected,enabled&filament_switch_sensor+filament_sensor_2=filament_detected,enabled&gcode_move=homing_origin&gcode_macro+KCTRL_STATE&k1_control_store&gcode_macro+KCTRL_CAL_PATH_STATE'
echo
echo '=== FINAL_OBJECT_QUERY_END ==='

echo '=== FINAL_HASHES_BEGIN ==='
sha256sum \
  /usr/data/printer_data/config/printer.cfg \
  /usr/data/printer_data/config/box.cfg \
  /usr/data/printer_data/config/gcode_macro.cfg \
  /usr/data/printer_data/config/k1-control-z-mesh.cfg \
  /usr/data/printer_data/config/k1-control-calibration-path.cfg 2>/dev/null
echo '=== FINAL_HASHES_END ==='
echo 'CFS_READ_ONLY_AUDIT_OK'
'@

$remoteBytes = [Text.Encoding]::UTF8.GetBytes($remoteScript.Replace("`r`n", "`n"))
$remoteBase64 = [Convert]::ToBase64String($remoteBytes)
$remoteCommand = "echo $remoteBase64 | base64 -d | sh"

Write-Host "AUDIT CFS LECTURE SEULE : $SessionLabel"
Write-Host 'Aucun G-code, chauffage, mouvement, service ou fichier distant ne sera modifie.'
Write-Host ''

& ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ServerAliveInterval=10' `
    -o 'ServerAliveCountMax=3' `
    k1max-root `
    $remoteCommand | Tee-Object -LiteralPath $capturePath

$sshExitCode = $LASTEXITCODE
$metadata.local_end = (Get-Date).ToString('o')
$metadata.ssh_exit_code = $sshExitCode
$metadata.capture_path = $capturePath
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8

Write-Host ''
Write-Host "CFS_READ_ONLY_AUDIT_CLOSED exit_code=$sshExitCode capture=$capturePath"
exit $sshExitCode
