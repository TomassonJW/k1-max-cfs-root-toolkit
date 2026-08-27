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
if (Test-Path -LiteralPath $capturePath) {
    throw 'La capture existe deja. Utilise un nouvel identifiant.'
}

$remoteScript = @'
set -eu
echo '=== HASHES_BEFORE_BEGIN ==='
sha256sum /usr/data/printer_data/config/printer.cfg /usr/data/printer_data/config/box.cfg /usr/data/printer_data/config/gcode_macro.cfg
echo '=== HASHES_BEFORE_END ==='
echo '=== CURRENT_STATE_BEGIN ==='
curl 'http://127.0.0.1:7125/printer/objects/query?print_stats=state&extruder=target&heater_bed=target&box&filament_switch_sensor+filament_sensor=filament_detected,enabled'
echo
echo '=== CURRENT_STATE_END ==='
echo '=== CFS_HISTORY_BEGIN ==='
grep -E -i 'BOX_(QUIT|EXTRUDE|START|CHANGE|REFILL)|RETRUDE_PROCESS|EXTRUDE_PROCESS|cmd_T |last_cmd:|last_tnn|tnn_map|material_auto_refill|BOX_MODIFY_TN|T[1-4][A-D]' /usr/data/printer_data/logs/klippy.log 2>/dev/null \
  | grep -E -v 'GET_BOX_STATE|webhooks: method:objects/query|_handle_query after complete.wait' \
  | tail -n 12000 || true
echo '=== CFS_HISTORY_END ==='
echo '=== HASHES_AFTER_BEGIN ==='
sha256sum /usr/data/printer_data/config/printer.cfg /usr/data/printer_data/config/box.cfg /usr/data/printer_data/config/gcode_macro.cfg
echo '=== HASHES_AFTER_END ==='
echo 'CFS_HISTORY_READ_ONLY_OK'
'@

$remoteBytes = [Text.Encoding]::UTF8.GetBytes($remoteScript.Replace("`r`n", "`n"))
$remoteBase64 = [Convert]::ToBase64String($remoteBytes)
$remoteCommand = "echo $remoteBase64 | base64 -d | sh"

& ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ServerAliveInterval=10' `
    -o 'ServerAliveCountMax=3' `
    k1max-root `
    $remoteCommand | Set-Content -LiteralPath $capturePath -Encoding utf8

$sshExitCode = $LASTEXITCODE
Write-Host "CFS_HISTORY_READ_ONLY_CLOSED exit_code=$sshExitCode capture=$capturePath"
exit $sshExitCode
