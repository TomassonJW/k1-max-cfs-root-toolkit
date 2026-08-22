[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-calibration-ui-prtouch-bed-mesh-v2',
    [switch]$Execute,
    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-BED-MESH-V2'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\calibration-ui-prtouch-bed-mesh-v2'
$ManifestPath = Join-Path $PackageRoot 'deployment-manifest.json'
$ContractPath = Join-Path $PackageRoot 'calibration-ui-prtouch-bed-mesh-v2-contract.json'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteCurrent = "$RemoteRoot/current"
$RemoteConfig = "$RemoteCurrent/config/moonraker.conf"
$RemoteComponents = "$RemoteCurrent/moonraker/moonraker/moonraker/components"
$RemoteComponent = "$RemoteComponents/k1_control_probe_count.py"
$RemotePrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$MoonrakerService = '/etc/init.d/S56k1_control_moonraker'
$RemoteBackup = "$RemoteRoot/backups/$CaptureId-calibration-ui-prtouch-bed-mesh-v2"
$RemoteStaging = "$RemoteRoot/tmp/$CaptureId-calibration-ui-prtouch-bed-mesh-v2"
$LocalCapture = Join-Path $WorkspaceRoot "inventory\raw\$CaptureId"
$MutationStarted = $false

function Assert-MutationGate {
    if (-not $Execute -or $Gate -cne $RequiredGate) {
        throw "Action bloquée : -Execute et -Gate '$RequiredGate' sont obligatoires."
    }
}

function Get-LocalSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Invoke-Remote {
    param([Parameter(Mandatory = $true)][string]$Command)
    $arguments = @(
        '-o', 'BatchMode=yes',
        '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no',
        '-o', 'ConnectTimeout=8',
        $PrinterHost,
        $Command
    )
    $output = & ssh.exe @arguments 2>&1
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
    $arguments = @(
        '-O',
        '-o', 'BatchMode=yes',
        '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no',
        '-o', 'ConnectTimeout=8',
        (Resolve-Path -LiteralPath $Source).Path,
        "$PrinterHost`:$Destination"
    )
    & scp.exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Transfert SCP KO : $Destination" }
}

function Get-RemoteSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    $line = Invoke-Remote "sha256sum '$Path'"
    return ((($line | Select-Object -First 1) -split '\s+')[0]).ToLowerInvariant()
}

function Assert-Package {
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ($manifest.contract_id -cne $RequiredGate -or $manifest.status -cne 'offline_review_candidate') {
        throw 'Manifeste PRTOUCH-BED-MESH-V2 inattendu.'
    }
    if ((Get-LocalSha256 $PSCommandPath) -cne [string]$manifest.deployer.sha256) {
        throw 'Empreinte du déployeur PRTOUCH-BED-MESH-V2 inattendue.'
    }
    if ((Get-LocalSha256 $ContractPath) -cne [string]$manifest.contract.sha256) {
        throw 'Empreinte du contrat PRTOUCH-BED-MESH-V2 inattendue.'
    }
    foreach ($file in $manifest.files) {
        $local = Join-Path $PackageRoot ([string]$file.source)
        if ((Get-LocalSha256 $local) -cne [string]$file.sha256) {
            throw "Empreinte locale inattendue : $($file.source)"
        }
    }
    return $manifest
}

function Get-ApiState {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/status'") -join "`n"
    $state = ($raw | ConvertFrom-Json).result
    if (-not $state) { throw 'API K1 Control sans état métier.' }
    return $state
}

function Get-PrinterStatus {
    $url = "http://127.0.0.1:7125/printer/objects/query?print_stats&extruder&heater_bed&bed_mesh&configfile&gcode_macro+KCTRL_STATE&k1_control_store&gcode_macro+KCTRL_CAL_PATH_STATE"
    $raw = (Invoke-Remote "curl '$url'") -join "`n"
    $status = ($raw | ConvertFrom-Json).result.status
    if (-not $status) { throw 'Réponse Moonraker sans état Klipper.' }
    return $status
}

function Assert-SafeState {
    $api = Get-ApiState
    if ([bool]$api.busy -or @('idle', 'accepted', 'cancelled', 'failed', 'rolled_back') -notcontains [string]$api.phase) {
        throw "Campagne UI non fermée : phase=$($api.phase) busy=$($api.busy)"
    }
    if ($api.phase -ceq 'failed' -and ([int]$api.mesh_index -ne 0 -or -not [bool]$api.backup_available)) {
        throw 'La reprise V2 exige le XS3002 borné à zéro mesh avec backup.'
    }
    $status = Get-PrinterStatus
    if ($status.print_stats.state -cne 'standby' -or $status.print_stats.filename) {
        throw "Imprimante non disponible : $($status.print_stats.state)"
    }
    if ([double]$status.extruder.target -ne 0 -or [double]$status.heater_bed.target -ne 0) {
        throw 'Les chauffes ne sont pas coupées.'
    }
    $runtime = $status.'gcode_macro KCTRL_STATE'
    $store = $status.k1_control_store
    $path = $status.'gcode_macro KCTRL_CAL_PATH_STATE'
    if ([int]$runtime.ready -ne 1 -or [int]$runtime.accepted_z_valid -ne 1 -or
        [int]$runtime.session_active -ne 0 -or [int]$runtime.low_moves_armed -ne 0 -or
        -not $store -or $store.integrity -cne 'ok') {
        throw 'Runtime ou stockage Z non sûr.'
    }
    if (@('idle', 'committed', 'cancelled') -notcontains [string]$path.phase -or
        [int]$path.motion_armed -ne 0 -or [int]$path.commit_ready -ne 0) {
        throw 'Chemin Z non fermé.'
    }
    $profiles = @($status.bed_mesh.profiles.PSObject.Properties.Name)
    if ($profiles -notcontains 'k1_p001_t055_r001_n06x06' -or $profiles -contains 'K1_TRANSIENT') {
        throw 'Profil 6x6 absent ou profil transitoire présent.'
    }
    foreach ($name in @('k1_p001_t055_r001_n09x09', 'k1_p001_t055_r001_n11x11', 'k1_p001_t055_r001_n15x15')) {
        if ($profiles -contains $name) { throw "Profil inattendu avant correction : $name" }
    }
    $count = @($status.configfile.settings.bed_mesh.probe_count)
    if ($count.Count -ne 2 -or [int]$count[0] -ne 6 -or [int]$count[1] -ne 6) {
        throw "probe_count chargé inattendu : $($count -join ',')"
    }
    if ([string]$status.configfile.settings.bed_mesh.algorithm -cne 'lagrange') {
        throw "Algorithme bed_mesh chargé inattendu : $($status.configfile.settings.bed_mesh.algorithm)"
    }
    return @{ Api = $api; Printer = $status }
}

function Assert-RemotePythonCompatibility {
    $source = [Convert]::ToBase64String(
        [IO.File]::ReadAllBytes((Join-Path $PackageRoot 'k1_control_probe_count.py'))
    )
    $python = "$RemoteCurrent/moonraker/moonraker-env/bin/python"
    $program = @"
import base64
import sys
import types

name = 'moonraker.components.k1_control_probe_count'
module = types.ModuleType(name)
module.__file__ = 'k1_control_probe_count.py'
module.__package__ = 'moonraker.components'
sys.modules[name] = module
exec(compile(base64.b64decode('$source'), module.__file__, 'exec'), module.__dict__)
document = b'[bed_mesh]\nprobe_count: 6,6\nalgorithm: lagrange\n[printer]\nkinematics: corexy\n'
rewritten, previous = module.ProbeCountFile._rewrite(document, ((9, 9), 'bicubic'))
assert previous == ((6, 6), 'lagrange')
assert b'probe_count: 9,9' in rewritten
assert b'algorithm: bicubic' in rewritten
try:
    module.ProbeCountFile._rewrite(document, ((9, 9), 'lagrange'))
except module.ProbeCountError:
    pass
else:
    raise AssertionError('9x9 lagrange must fail closed')
print('REMOTE_PRTOUCH_BED_MESH_V2_IMPORT_OK')
"@
    $arguments = @(
        '-o', 'BatchMode=yes',
        '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no',
        '-o', 'ConnectTimeout=8',
        $PrinterHost,
        "'$python' -"
    )
    $output = $program | & ssh.exe @arguments 2>&1
    if ($LASTEXITCODE -ne 0 -or ($output | Select-Object -Last 1) -cne 'REMOTE_PRTOUCH_BED_MESH_V2_IMPORT_OK') {
        throw "Import Python distant PRTOUCH-BED-MESH-V2 KO : $($output -join "`n")"
    }
}

function Assert-Baseline {
    param([Parameter(Mandatory = $true)]$Manifest)
    [void](Invoke-Remote "test -x '$MoonrakerService' && test -S /tmp/klippy_uds && test -f '$RemoteConfig' && test -f '$RemoteComponent'")
    if ((Get-RemoteSha256 $RemoteConfig) -cne [string]$Manifest.baseline.moonraker_conf_sha256) {
        throw 'moonraker.conf de base inattendu.'
    }
    if ((Get-RemoteSha256 $RemotePrinterConfig) -cne [string]$Manifest.baseline.printer_cfg_sha256) {
        throw 'printer.cfg de base inattendu.'
    }
    if ((Get-RemoteSha256 $RemoteComponent) -cne [string]$Manifest.baseline.component_sha256) {
        throw 'Composant prtouch V1 de base inattendu.'
    }
    foreach ($file in $Manifest.unchanged.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne [string]$file.sha256) {
            throw "Fichier hors write-set inattendu : $($file.destination)"
        }
    }
    foreach ($module in $Manifest.firmware_dependencies) {
        if ((Get-RemoteSha256 ([string]$module.path)) -cne [string]$module.sha256) {
            throw "Module firmware inattendu : $($module.path)"
        }
    }
    [void](Assert-SafeState)
    Assert-RemotePythonCompatibility
}

function Get-ServerInfo {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/server/info'") -join "`n"
    $info = ($raw | ConvertFrom-Json).result
    if (-not $info) { throw 'Moonraker sans server/info.' }
    return $info
}

function Wait-Moonraker {
    param([int]$Attempts = 60)
    $last = 'aucune réponse'
    for ($index = 1; $index -le $Attempts; $index++) {
        try {
            $info = Get-ServerInfo
            if (@($info.components) -contains 'k1_control') { return }
        }
        catch { $last = $_.Exception.Message }
        Start-Sleep -Seconds 1
    }
    throw "Moonraker non stabilisé : $last"
}

function Assert-Installed {
    param([Parameter(Mandatory = $true)]$Manifest)
    foreach ($file in $Manifest.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne [string]$file.sha256) {
            throw "Empreinte distante inattendue : $($file.destination)"
        }
    }
    foreach ($file in $Manifest.unchanged.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne [string]$file.sha256) {
            throw "Fichier hors write-set modifié : $($file.destination)"
        }
    }
    if ((Get-RemoteSha256 $RemotePrinterConfig) -cne [string]$Manifest.baseline.printer_cfg_sha256) {
        throw 'La pose a modifié printer.cfg.'
    }
    $info = Get-ServerInfo
    if (@($info.components) -notcontains 'k1_control_probe_count') {
        throw 'Le composant k1_control_probe_count est absent des composants chargés.'
    }
    [void](Assert-SafeState)
}

function Remove-RemoteStaging {
    [void](Invoke-Remote "rm -f '$RemoteStaging/k1_control_probe_count.py' && rmdir '$RemoteStaging' 2>/dev/null || true")
}

function Invoke-ExactRollback {
    $manifest = Assert-Package
    [void](Invoke-Remote "test -f '$RemoteBackup/k1_control_probe_count.py.before'")
    if ((Get-RemoteSha256 "$RemoteBackup/k1_control_probe_count.py.before") -cne [string]$manifest.baseline.component_sha256) {
        throw 'Backup du composant prtouch V1 inattendu.'
    }
    if ((Get-RemoteSha256 $RemotePrinterConfig) -cne [string]$manifest.baseline.printer_cfg_sha256) {
        throw 'Rollback refusé : probe_count temporaire encore présent ; restaurer la campagne active en premier.'
    }
    [void](Invoke-Remote "cp '$RemoteBackup/k1_control_probe_count.py.before' '$RemoteComponent.rollback-next' && chmod 0644 '$RemoteComponent.rollback-next' && mv '$RemoteComponent.rollback-next' '$RemoteComponent' && rm -f '$RemoteComponents/__pycache__/k1_control_probe_count.cpython-38.pyc'")
    Remove-RemoteStaging
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    if ((Get-RemoteSha256 $RemoteComponent) -cne [string]$manifest.baseline.component_sha256) {
        throw 'Rollback du composant prtouch V1 incomplet.'
    }
    foreach ($file in $manifest.unchanged.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne [string]$file.sha256) {
            throw "Rollback hors write-set inattendu : $($file.destination)"
        }
    }
    [void](Assert-SafeState)
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "PLAN_CALIBRATION_UI_PRTOUCH_BED_MESH_V2_OK gate=$RequiredGate"
    Write-Output 'Pose: remplacement du seul composant prtouch déjà installé, restart Moonraker seulement.'
    Write-Output 'Exécution future: couple probe_count+algorithm atomique avant chauffe, restart Klipper vérifié, restauration après chauffes.'
    Write-Output 'Aucun chauffage, homing, mouvement, mesh, Z, extrusion, impression ou action CFS pendant la pose.'
    exit 0
}

if ($Action -eq 'Preflight') {
    Assert-Baseline $manifest
    Write-Output 'PREFLIGHT_CALIBRATION_UI_PRTOUCH_BED_MESH_V2_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    Assert-Installed $manifest
    Write-Output 'VALIDATE_CALIBRATION_UI_PRTOUCH_BED_MESH_V2_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Assert-MutationGate
    Invoke-ExactRollback
    Write-Output "ROLLBACK_CALIBRATION_UI_PRTOUCH_BED_MESH_V2_OK capture=$CaptureId"
    exit 0
}

Assert-MutationGate
Assert-Baseline $manifest
New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup'")
    [void](Invoke-Remote "cp '$RemoteComponent' '$RemoteBackup/k1_control_probe_count.py.before'")
    if ((Get-RemoteSha256 "$RemoteBackup/k1_control_probe_count.py.before") -cne [string]$manifest.baseline.component_sha256) {
        throw 'Backup du composant prtouch V1 non conforme.'
    }
    $MutationStarted = $true
    [void](Invoke-Remote "mkdir -p '$RemoteStaging'")
    foreach ($file in $manifest.files) {
        $stagedName = ([string]$file.source).Replace('/', '__')
        Copy-ToRemote (Join-Path $PackageRoot ([string]$file.source)) "$RemoteStaging/$stagedName"
        if ((Get-RemoteSha256 "$RemoteStaging/$stagedName") -cne [string]$file.sha256) {
            throw "Transfert non conforme : $($file.source)"
        }
    }
    $python = "$RemoteCurrent/moonraker/moonraker-env/bin/python"
    [void](Invoke-Remote "'$python' -c `"compile(open('$RemoteStaging/k1_control_probe_count.py').read(), 'k1_control_probe_count.py', 'exec')`"")
    foreach ($file in $manifest.files) {
        $destination = [string]$file.destination
        $stagedName = ([string]$file.source).Replace('/', '__')
        [void](Invoke-Remote "cp '$RemoteStaging/$stagedName' '$destination.next' && chmod 0644 '$destination.next' && mv '$destination.next' '$destination'")
    }
    [void](Invoke-Remote "rm -f '$RemoteComponents/__pycache__/k1_control_probe_count.cpython-38.pyc'")
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    & $PSCommandPath -Action Validate -PrinterHost $PrinterHost -CaptureId $CaptureId
    Remove-RemoteStaging
    [pscustomobject]@{
        capture_id = $CaptureId
        gate = $RequiredGate
        result = 'DEPLOY_CALIBRATION_UI_PRTOUCH_BED_MESH_V2_OK'
        printer_cfg_changed_during_deployment = $false
        calibration_action = $false
        heater_command = $false
        printer_motion = $false
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LocalCapture 'deploy-result.json') -Encoding UTF8
    Write-Output "DEPLOY_CALIBRATION_UI_PRTOUCH_BED_MESH_V2_OK capture=$CaptureId"
}
catch {
    $failure = $_
    if ($MutationStarted) {
        try { Invoke-ExactRollback }
        catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
