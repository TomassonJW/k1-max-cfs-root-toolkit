[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-calibration-ui-matrix-v1',
    [switch]$Execute,
    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-CALIBRATION-UI-MATRIX-V1'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\calibration-ui-matrix-v1'
$BaseUiRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\calibration-ui-v1'
$ManifestPath = Join-Path $PackageRoot 'deployment-manifest.json'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteCurrent = "$RemoteRoot/current"
$RemoteConfig = "$RemoteCurrent/config/moonraker.conf"
$RemoteComponents = "$RemoteCurrent/moonraker/moonraker/moonraker/components"
$RemoteUi = "$RemoteCurrent/www/mainsail/k1-control"
$MoonrakerService = '/etc/init.d/S56k1_control_moonraker'
$RemoteBackup = "$RemoteRoot/backups/$CaptureId-calibration-ui-matrix-v1"
$RemoteStaging = "$RemoteRoot/tmp/$CaptureId-calibration-ui-matrix-v1"
$LocalCapture = Join-Path $WorkspaceRoot "inventory\raw\$CaptureId"
$MutationStarted = $false

function Assert-MutationGate {
    if (-not $Execute -or $Gate -cne $RequiredGate) {
        throw "Action bloquee : -Execute et -Gate '$RequiredGate' sont obligatoires."
    }
}

function Get-LocalSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    $stream = [IO.File]::OpenRead((Resolve-Path -LiteralPath $Path).Path)
    try {
        $sha = [Security.Cryptography.SHA256]::Create()
        try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
        finally { $sha.Dispose() }
    }
    finally { $stream.Dispose() }
}

function Invoke-Remote {
    param([Parameter(Mandatory = $true)][string]$Command)
    $args = @(
        '-o', 'BatchMode=yes',
        '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no',
        '-o', 'ConnectTimeout=8',
        $PrinterHost,
        $Command
    )
    $output = & ssh.exe @args 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Commande distante KO : $Command`n$($output -join "`n")"
    }
    return @($output)
}

function Copy-ToRemote {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $args = @(
        '-O',
        '-o', 'BatchMode=yes',
        '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no',
        '-o', 'ConnectTimeout=8',
        (Resolve-Path -LiteralPath $Source).Path,
        "$PrinterHost`:$Destination"
    )
    & scp.exe @args
    if ($LASTEXITCODE -ne 0) { throw "Transfert SCP KO : $Destination" }
}

function Get-RemoteSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    $line = Invoke-Remote "sha256sum '$Path'"
    return ((($line | Select-Object -First 1) -split '\s+')[0]).ToLowerInvariant()
}

function Assert-Package {
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ($manifest.contract_id -cne $RequiredGate -or
        $manifest.status -cne 'corrected_after_exact_prtouch_runtime_limit_proof') {
        throw 'Manifeste CALIBRATION-UI-MATRIX-V1 inattendu.'
    }
    if ([string]$manifest.deployer.path -cne 'scripts/deploy-k1-control-calibration-ui-matrix-v1.ps1' -or
        (Get-LocalSha256 $PSCommandPath) -cne ([string]$manifest.deployer.sha256)) {
        throw 'Empreinte du déployeur CALIBRATION-UI-MATRIX-V1 inattendue.'
    }
    foreach ($file in $manifest.files) {
        $local = Join-Path $PackageRoot ([string]$file.source)
        if ((Get-LocalSha256 $local) -cne ([string]$file.sha256)) {
            throw "Empreinte locale inattendue : $($file.source)"
        }
    }
    if ((Get-LocalSha256 (Join-Path $BaseUiRoot 'k1_control.py')) -cne ([string]$manifest.unchanged.k1_control_sha256)) {
        throw 'Le composant Moonraker inchangé ne correspond pas à la base revue.'
    }
    return $manifest
}

function Get-PrinterStatus {
    $url = "http://127.0.0.1:7125/printer/objects/query?print_stats&extruder&heater_bed&bed_mesh&configfile&box&gcode_macro+KCTRL_STATE&k1_control_store&gcode_macro+KCTRL_CAL_PATH_STATE"
    $raw = (Invoke-Remote "curl '$url'") -join "`n"
    $payload = $raw | ConvertFrom-Json
    if (-not $payload.result.status) { throw 'Réponse Moonraker sans état Klipper.' }
    return $payload.result.status
}

function Assert-PrinterIdle {
    $status = Get-PrinterStatus
    if ($status.print_stats.state -cne 'standby' -or $status.print_stats.filename) {
        throw "Imprimante non disponible : $($status.print_stats.state)"
    }
    if ([double]$status.extruder.target -ne 0 -or [double]$status.heater_bed.target -ne 0) {
        throw 'Une chauffe est déjà demandée.'
    }
    $runtime = $status.'gcode_macro KCTRL_STATE'
    if ([int]$runtime.ready -ne 1 -or [int]$runtime.accepted_z_valid -ne 1 -or
        [int]$runtime.session_active -ne 0 -or [int]$runtime.low_moves_armed -ne 0 -or
        -not $status.k1_control_store -or $status.k1_control_store.integrity -cne 'ok') {
        throw "Le runtime K1 Control n'est pas fermé."
    }
    $path = $status.'gcode_macro KCTRL_CAL_PATH_STATE'
    if (@('idle', 'committed', 'cancelled') -notcontains [string]$path.phase -or [int]$path.motion_armed -ne 0) {
        throw "Le chemin Z n'est pas fermé."
    }
    $profiles = @($status.bed_mesh.profiles.PSObject.Properties.Name)
    if ($profiles -notcontains 'k1_p001_t055_r001_n06x06' -or $profiles -contains 'K1_TRANSIENT') {
        throw 'Profil robuste absent ou profil transitoire présent.'
    }
    $count = @($status.configfile.settings.bed_mesh.probe_count)
    if ($count.Count -ne 2 -or [int]$count[0] -ne 6 -or [int]$count[1] -ne 6 -or
        [string]$status.configfile.settings.bed_mesh.algorithm -cne 'lagrange') {
        throw "La configuration bed_mesh chargée n'est pas 6x6 Lagrange."
    }
    foreach ($name in @('T1', 'T2')) {
        $unit = $status.box.$name
        if ($unit.state -cne 'connect' -or $unit.version -cne '1.1.3' -or @($unit.material_type).Count -ne 4) {
            throw "CFS $name inattendu ou déconnecté."
        }
    }
    return $status
}

function Get-CalibrationUiState {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/status'") -join "`n"
    $state = ($raw | ConvertFrom-Json).result
    if (-not $state) { throw 'API K1 Control sans état métier.' }
    return $state
}

function Assert-ClosedUiState {
    $state = Get-CalibrationUiState
    if ($state.busy -or @('idle', 'accepted', 'cancelled') -notcontains [string]$state.phase) {
        throw "La campagne UI n'est pas fermée : phase=$($state.phase) busy=$($state.busy)"
    }
    return $state
}

function Assert-RemotePythonCompatibility {
    $componentSource = [Convert]::ToBase64String(
        [IO.File]::ReadAllBytes((Join-Path $BaseUiRoot 'k1_control.py'))
    )
    $coreSource = [Convert]::ToBase64String(
        [IO.File]::ReadAllBytes((Join-Path $PackageRoot 'k1_control_calibration_core.py'))
    )
    $pythonRoot = "$RemoteCurrent/moonraker/moonraker"
    $python = "$RemoteCurrent/moonraker/moonraker-env/bin/python"
    $program = @"
import base64
import sys
import types

sys.path.insert(0, '$pythonRoot')
import moonraker.common

core_name = 'moonraker.components.k1_control_calibration_core'
core = types.ModuleType(core_name)
core.__file__ = 'k1_control_calibration_core.py'
core.__package__ = 'moonraker.components'
sys.modules[core_name] = core
exec(compile(base64.b64decode('$coreSource'), core.__file__, 'exec'), core.__dict__)

component_name = 'moonraker.components.k1_control'
component = types.ModuleType(component_name)
component.__file__ = 'k1_control.py'
component.__package__ = 'moonraker.components'
sys.modules[component_name] = component
exec(compile(base64.b64decode('$componentSource'), component.__file__, 'exec'), component.__dict__)

def candidate(size, algorithm):
    return {
        'plate_id': 1, 'plate_label': 'PEI_TEXTURED_A',
        'bed_temp_c': 55, 'nozzle_temp_c': 140, 'soak_seconds': 200,
        'probe_revision': 1, 'nozzle_id': 1, 'config_id': 1,
        'x_count': size, 'y_count': size, 'algorithm': algorithm,
        'seed_offset_mm': -0.04,
    }

accepted = core.validate_config(candidate(6, 'lagrange'))
assert accepted['x_count'] == 6 and accepted['algorithm'] == 'lagrange'
for size in (3, 4, 5, 9, 11, 15):
    try:
        core.validate_config(candidate(size, 'lagrange'))
    except core.CalibrationError:
        pass
    else:
        raise AssertionError('%sx%s must fail closed' % (size, size))
try:
    core.validate_config(candidate(6, 'bicubic'))
except core.CalibrationError:
    pass
else:
    raise AssertionError('6x6 bicubic must fail closed')
print('REMOTE_CALIBRATION_UI_MATRIX_IMPORT_OK')
"@
    $args = @(
        '-o', 'BatchMode=yes',
        '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no',
        '-o', 'ConnectTimeout=8',
        $PrinterHost,
        "'$python' -"
    )
    $output = $program | & ssh.exe @args 2>&1
    if ($LASTEXITCODE -ne 0 -or ($output | Select-Object -Last 1) -cne 'REMOTE_CALIBRATION_UI_MATRIX_IMPORT_OK') {
        throw "Import Python distant CALIBRATION-UI-MATRIX-V1 KO : $($output -join "`n")"
    }
}

function Assert-InstalledBaseline {
    param([Parameter(Mandatory = $true)]$Manifest)
    [void](Invoke-Remote "test -x '$MoonrakerService' && test -S /tmp/klippy_uds && test -f '$RemoteConfig'")
    foreach ($file in $Manifest.baseline.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne ([string]$file.sha256)) {
            throw "Base UI V1 inattendue : $($file.destination)"
        }
    }
    foreach ($file in $Manifest.unchanged.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne ([string]$file.sha256)) {
            throw "Base UI V1 hors write-set inattendue : $($file.destination)"
        }
    }
    $uiMode = ((Invoke-Remote "stat -c '%a' '$RemoteUi'") | Select-Object -First 1).Trim()
    if ($uiMode -cne '755') { throw "Droits du dossier UI inattendus : $uiMode" }
    [void](Assert-ClosedUiState)
    [void](Assert-PrinterIdle)
    Assert-RemotePythonCompatibility
}

function Get-ServerInfo {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/server/info'") -join "`n"
    $info = ($raw | ConvertFrom-Json).result
    if (-not $info) { throw 'Moonraker sans server/info.' }
    return $info
}

function Assert-ServerInfo {
    $info = Get-ServerInfo
    if (-not [bool]$info.klippy_connected -or [string]$info.klippy_state -cne 'ready' -or
        @($info.components) -notcontains 'k1_control' -or
        @($info.components) -notcontains 'k1_control_probe_count' -or
        @($info.failed_components).Count -ne 0 -or @($info.warnings).Count -ne 0) {
        throw "Moonraker non sain : state=$($info.klippy_state) failed=$(@($info.failed_components) -join ',') warnings=$(@($info.warnings) -join ' | ')"
    }
    return $info
}

function Wait-Moonraker {
    param([int]$Attempts = 60)
    $last = 'aucune réponse'
    for ($index = 1; $index -le $Attempts; $index++) {
        try {
            [void](Assert-ServerInfo)
            return
        }
        catch { $last = $_.Exception.Message }
        Start-Sleep -Seconds 1
    }
    throw "Moonraker non stabilisé : $last"
}

function Remove-RemoteStaging {
    [void](Invoke-Remote "rm -f '$RemoteStaging/k1_control_calibration_core.py' '$RemoteStaging/www__index.html' '$RemoteStaging/www__app.js' && rmdir '$RemoteStaging' 2>/dev/null || true")
}

function Invoke-ExactRollback {
    $manifest = Assert-Package
    foreach ($file in $manifest.baseline.files) {
        $backupName = ([string]$file.destination).Split('/')[-1] + '.before'
        $backupPath = "$RemoteBackup/$backupName"
        [void](Invoke-Remote "test -f '$backupPath'")
        if ((Get-RemoteSha256 $backupPath) -cne ([string]$file.sha256)) {
            throw "Backup inattendu : $backupName"
        }
        $destination = [string]$file.destination
        [void](Invoke-Remote "cp '$backupPath' '$destination.rollback-next' && chmod 0644 '$destination.rollback-next' && mv '$destination.rollback-next' '$destination'")
    }
    [void](Invoke-Remote "rm -f '$RemoteComponents/__pycache__/k1_control_calibration_core.cpython-38.pyc'")
    Remove-RemoteStaging
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    foreach ($file in $manifest.baseline.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne ([string]$file.sha256)) {
            throw "Rollback incomplet : $($file.destination)"
        }
    }
    [void](Assert-ClosedUiState)
    [void](Assert-PrinterIdle)
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "PLAN_CALIBRATION_UI_MATRIX_V1_OK gate=$RequiredGate"
    Write-Output 'Effet: backup exact, remplacement du core et de deux fichiers UI, restart Moonraker seulement.'
    Write-Output 'Matrice: 6x6 Lagrange uniquement; 9x9/11x11/15x15 refusées avant chauffe; aucun mesh lancé.'
    Write-Output 'Aucun chauffage, homing, mouvement, Z, extrusion, impression ou action CFS.'
    exit 0
}

if ($Action -eq 'Preflight') {
    Assert-InstalledBaseline $manifest
    Write-Output 'PREFLIGHT_CALIBRATION_UI_MATRIX_V1_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    foreach ($file in $manifest.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne ([string]$file.sha256)) {
            throw "Empreinte distante inattendue : $($file.destination)"
        }
    }
    foreach ($file in $manifest.unchanged.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne ([string]$file.sha256)) {
            throw "Fichier hors write-set modifié : $($file.destination)"
        }
    }
    [void](Assert-ServerInfo)
    [void](Assert-ClosedUiState)
    [void](Assert-PrinterIdle)
    Write-Output 'VALIDATE_CALIBRATION_UI_MATRIX_V1_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Assert-MutationGate
    Invoke-ExactRollback
    Write-Output "ROLLBACK_CALIBRATION_UI_MATRIX_V1_OK capture=$CaptureId"
    exit 0
}

Assert-MutationGate
Assert-InstalledBaseline $manifest
New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup'")
    foreach ($file in $manifest.baseline.files) {
        $backupName = ([string]$file.destination).Split('/')[-1] + '.before'
        [void](Invoke-Remote "cp '$($file.destination)' '$RemoteBackup/$backupName'")
        if ((Get-RemoteSha256 "$RemoteBackup/$backupName") -cne ([string]$file.sha256)) {
            throw "Backup non conforme : $backupName"
        }
    }
    $MutationStarted = $true
    [void](Invoke-Remote "mkdir -p '$RemoteStaging'")
    foreach ($file in $manifest.files) {
        $stagedName = ([string]$file.source).Replace('/', '__')
        Copy-ToRemote (Join-Path $PackageRoot ([string]$file.source)) "$RemoteStaging/$stagedName"
        if ((Get-RemoteSha256 "$RemoteStaging/$stagedName") -cne ([string]$file.sha256)) {
            throw "Transfert non conforme : $($file.source)"
        }
    }
    $python = "$RemoteCurrent/moonraker/moonraker-env/bin/python"
    [void](Invoke-Remote "'$python' -c `"compile(open('$RemoteStaging/k1_control_calibration_core.py').read(), 'k1_control_calibration_core.py', 'exec')`"")
    foreach ($file in $manifest.files) {
        $destination = [string]$file.destination
        $stagedName = ([string]$file.source).Replace('/', '__')
        [void](Invoke-Remote "cp '$RemoteStaging/$stagedName' '$destination.next' && chmod 0644 '$destination.next' && mv '$destination.next' '$destination'")
    }
    [void](Invoke-Remote "rm -f '$RemoteComponents/__pycache__/k1_control_calibration_core.cpython-38.pyc'")
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    & $PSCommandPath -Action Validate -PrinterHost $PrinterHost -CaptureId $CaptureId
    Remove-RemoteStaging
    [pscustomobject]@{
        capture_id = $CaptureId
        gate = $RequiredGate
        action = 'Deploy'
        result = 'DEPLOY_CALIBRATION_UI_MATRIX_V1_OK'
        calibration_action = $false
        printer_motion = $false
        heater_command = $false
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LocalCapture 'deploy-result.json') -Encoding UTF8
    Write-Output "DEPLOY_CALIBRATION_UI_MATRIX_V1_OK capture=$CaptureId"
}
catch {
    $failure = $_
    if ($MutationStarted) {
        try { Invoke-ExactRollback }
        catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
