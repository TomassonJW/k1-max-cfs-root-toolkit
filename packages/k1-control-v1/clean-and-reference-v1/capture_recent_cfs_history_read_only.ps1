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
# Lecture bornee du journal (document 81 : le 15 septembre 2026, un tail -n sur
# klippy.log a fait planter Klipper) : fenetre en octets depuis la fin, 32 Mo
# au repos et 3 Mo si une impression tourne, basse priorite, lignes coupees a
# 300 caracteres avant le tail -n. tests/test_lectures_journal_bornees_v1.py.
KLOG=/usr/data/printer_data/logs/klippy.log
KSTATE=$(curl 'http://127.0.0.1:7125/printer/objects/query?print_stats=state' 2>/dev/null | sed -n 's/.*"state": *"\([a-z]*\)".*/\1/p' || true)
case "$KSTATE" in printing|paused) KWIN=3 ;; *) KWIN=32 ;; esac
KSIZE=$(wc -c < "$KLOG" 2>/dev/null || echo 0)
KSKIP=$((KSIZE / 1048576 - KWIN)); [ "$KSKIP" -lt 0 ] && KSKIP=0
echo "fenetre=${KWIN}Mo etat=${KSTATE:-inconnu} skip=${KSKIP}"
nice -n 19 dd if="$KLOG" bs=1048576 skip="$KSKIP" 2>/dev/null \
  | cut -c1-300 \
  | grep -a -E -i 'BOX_(QUIT|EXTRUDE|START|CHANGE|REFILL)|RETRUDE_PROCESS|EXTRUDE_PROCESS|cmd_T |last_cmd:|last_tnn|tnn_map|material_auto_refill|BOX_MODIFY_TN|T[1-4][A-D]' \
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
