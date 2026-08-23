[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-composite-mesh-subgrid-v1',
    [switch]$Execute,
    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-COMPOSITE-MESH-SUBGRID-V1'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\composite-subgrid-v1'
$ManifestPath = Join-Path $PackageRoot 'deployment-manifest.json'
$ContractPath = Join-Path $PackageRoot 'composite-subgrid-contract.json'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteCurrent = "$RemoteRoot/current"
$RemoteConfig = "$RemoteCurrent/config/moonraker.conf"
$RemoteComponents = "$RemoteCurrent/moonraker/moonraker/moonraker/components"
$RemoteCore = "$RemoteComponents/k1_control_composite_subgrid_core.py"
$RemoteComponent = "$RemoteComponents/k1_control_composite_subgrid.py"
$RemoteState = "$RemoteRoot/state/k1-control-composite-subgrid.json"
$RemotePrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$MoonrakerService = '/etc/init.d/S56k1_control_moonraker'
$RemoteBackup = "$RemoteRoot/backups/$CaptureId-composite-subgrid-v1"
$RemoteStaging = "$RemoteRoot/tmp/$CaptureId-composite-subgrid-v1"
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
        throw 'Manifeste COMPOSITE-SUBGRID-V1 inattendu.'
    }
    if ((Get-LocalSha256 $PSCommandPath) -cne [string]$manifest.deployer.sha256) {
        throw 'Empreinte du déployeur COMPOSITE-SUBGRID-V1 inattendue.'
    }
    if ((Get-LocalSha256 $ContractPath) -cne [string]$manifest.contract.sha256) {
        throw 'Empreinte du contrat COMPOSITE-SUBGRID-V1 inattendue.'
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

function Get-CompositeState {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/composite_subgrid/status'") -join "`n"
    $state = ($raw | ConvertFrom-Json).result
    if (-not $state) { throw 'API composite sans état métier.' }
    return $state
}

function Get-PrinterStatus {
    $url = "http://127.0.0.1:7125/printer/objects/query?print_stats&extruder&heater_bed&toolhead&bed_mesh&configfile&box&gcode_macro+KCTRL_STATE&k1_control_store&gcode_macro+KCTRL_CAL_PATH_STATE"
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
    if ($profiles -notcontains 'k1_p001_t055_r001_n06x06' -or
        $profiles -contains 'K1_TRANSIENT' -or
        $profiles -contains 'K1_COMPOSITE_ODD_ODD_05X05') {
        throw 'Profils bed_mesh non sûrs avant la gate composite.'
    }
    $count = @($status.configfile.settings.bed_mesh.probe_count)
    if ($count.Count -ne 2 -or [int]$count[0] -ne 6 -or [int]$count[1] -ne 6 -or
        [string]$status.configfile.settings.bed_mesh.algorithm -cne 'lagrange') {
        throw 'Configuration bed_mesh chargée différente de 6x6 Lagrange.'
    }
    foreach ($unit in @('T1', 'T2')) {
        if ([string]$status.box.$unit.state -cne 'connect') {
            throw "CFS $unit non connecté."
        }
    }
    return $status
}

function Assert-RemotePythonCompatibility {
    $core = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $PackageRoot 'k1_control_composite_subgrid_core.py')))
    $component = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $PackageRoot 'k1_control_composite_subgrid.py')))
    $python = "$RemoteCurrent/moonraker/moonraker-env/bin/python"
    $program = @"
import base64
core = base64.b64decode('$core')
component = base64.b64decode('$component')
compile(core, 'k1_control_composite_subgrid_core.py', 'exec')
compile(component, 'k1_control_composite_subgrid.py', 'exec')
scope = {}
exec(compile(core, 'k1_control_composite_subgrid_core.py', 'exec'), scope)
assert scope['GATE_ID'] == 'G4-K1-CONTROL-COMPOSITE-MESH-SUBGRID-V1'
assert scope['MESH_COMMAND'].endswith('PROBE_COUNT=5,5 ALGORITHM=lagrange')
assert len(scope['validate_matrix']([[0.0] * 5 for _ in range(5)])) == 5
print('REMOTE_COMPOSITE_SUBGRID_IMPORT_OK')
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
    if ($LASTEXITCODE -ne 0 -or ($output | Select-Object -Last 1) -cne 'REMOTE_COMPOSITE_SUBGRID_IMPORT_OK') {
        throw "Import Python distant COMPOSITE-SUBGRID-V1 KO : $($output -join "`n")"
    }
}

function Assert-Baseline {
    param([Parameter(Mandatory = $true)]$Manifest)
    [void](Invoke-Remote "test -x '$MoonrakerService' && test -S /tmp/klippy_uds && test -f '$RemoteConfig' && test ! -e '$RemoteCore' && test ! -e '$RemoteComponent' && test ! -e '$RemoteState'")
    if ((Get-RemoteSha256 $RemoteConfig) -cne [string]$Manifest.baseline.moonraker_conf_sha256) {
        throw 'moonraker.conf de base inattendu.'
    }
    if ((Get-RemoteSha256 $RemotePrinterConfig) -cne [string]$Manifest.baseline.printer_cfg_sha256) {
        throw 'printer.cfg de base inattendu.'
    }
    foreach ($file in $Manifest.unchanged.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne [string]$file.sha256) {
            throw "Fichier requis inattendu : $($file.destination)"
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
            $loaded = @($info.components) -contains 'k1_control_composite_subgrid'
            $failed = @($info.failed_components) -contains 'k1_control_composite_subgrid'
            if (@($info.components) -contains 'k1_control' -and $loaded -and -not $failed) {
                return
            }
            $last = "components=$(@($info.components) -join ',') failed=$(@($info.failed_components) -join ',')"
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
    if (@($info.components) -notcontains 'k1_control_composite_subgrid' -or
        @($info.failed_components) -contains 'k1_control_composite_subgrid') {
        throw "Composant composite absent ou échoué : $(@($info.warnings) -join ' | ')"
    }
    $state = Get-CompositeState
    if ([string]$state.phase -cne 'idle' -or [bool]$state.busy -or
        [int]$state.physical_contacts -ne 25 -or [bool]$state.backup_available) {
        throw 'État initial du composant composite inattendu.'
    }
    [void](Assert-SafeState)
}

function Remove-RemoteStaging {
    [void](Invoke-Remote "rm -f '$RemoteStaging/moonraker.conf' '$RemoteStaging/k1_control_composite_subgrid_core.py' '$RemoteStaging/k1_control_composite_subgrid.py' && rmdir '$RemoteStaging' 2>/dev/null || true")
}

function Invoke-ExactRollback {
    $manifest = Assert-Package
    [void](Invoke-Remote "test -f '$RemoteBackup/moonraker.conf.before'")
    if ((Get-RemoteSha256 "$RemoteBackup/moonraker.conf.before") -cne [string]$manifest.baseline.moonraker_conf_sha256) {
        throw 'Backup moonraker.conf inattendu.'
    }
    [void](Invoke-Remote "cp '$RemoteBackup/moonraker.conf.before' '$RemoteConfig.rollback-next' && chmod 0600 '$RemoteConfig.rollback-next' && mv '$RemoteConfig.rollback-next' '$RemoteConfig'")
    [void](Invoke-Remote "rm -f '$RemoteCore' '$RemoteComponent' '$RemoteComponents/__pycache__/k1_control_composite_subgrid_core.cpython-38.pyc' '$RemoteComponents/__pycache__/k1_control_composite_subgrid.cpython-38.pyc'")
    Remove-RemoteStaging
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Start-Sleep -Seconds 3
    if ((Get-RemoteSha256 $RemoteConfig) -cne [string]$manifest.baseline.moonraker_conf_sha256) {
        throw 'Rollback moonraker.conf incomplet.'
    }
    [void](Invoke-Remote "test ! -e '$RemoteCore' && test ! -e '$RemoteComponent'")
    [void](Assert-SafeState)
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "PLAN_COMPOSITE_SUBGRID_V1_OK gate=$RequiredGate"
    Write-Output 'Pose: deux composants originaux et moonraker.conf exact; restart Moonraker seulement.'
    Write-Output 'Essai séparé: une grille décalée 5x5, 25 contacts, puis chauffes zéro et profil 6x6 restauré.'
    Write-Output 'Aucun chauffage, homing, mouvement, mesh, Z, extrusion, impression ou action CFS pendant la pose.'
    exit 0
}

if ($Action -eq 'Preflight') {
    Assert-Baseline $manifest
    Write-Output 'PREFLIGHT_COMPOSITE_SUBGRID_V1_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    Assert-Installed $manifest
    Write-Output 'VALIDATE_COMPOSITE_SUBGRID_V1_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Assert-MutationGate
    Invoke-ExactRollback
    Write-Output "ROLLBACK_COMPOSITE_SUBGRID_V1_OK capture=$CaptureId"
    exit 0
}

Assert-MutationGate
Assert-Baseline $manifest
New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup'")
    [void](Invoke-Remote "cp '$RemoteConfig' '$RemoteBackup/moonraker.conf.before'")
    if ((Get-RemoteSha256 "$RemoteBackup/moonraker.conf.before") -cne [string]$manifest.baseline.moonraker_conf_sha256) {
        throw 'Backup moonraker.conf non conforme.'
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
    [void](Invoke-Remote "'$python' -c `"compile(open('$RemoteStaging/k1_control_composite_subgrid_core.py').read(), 'k1_control_composite_subgrid_core.py', 'exec'); compile(open('$RemoteStaging/k1_control_composite_subgrid.py').read(), 'k1_control_composite_subgrid.py', 'exec')`"")
    foreach ($file in $manifest.files) {
        $destination = [string]$file.destination
        $stagedName = ([string]$file.source).Replace('/', '__')
        $mode = if ($destination -ceq $RemoteConfig) { '0600' } else { '0644' }
        [void](Invoke-Remote "cp '$RemoteStaging/$stagedName' '$destination.next' && chmod $mode '$destination.next' && mv '$destination.next' '$destination'")
    }
    [void](Invoke-Remote "rm -f '$RemoteComponents/__pycache__/k1_control_composite_subgrid_core.cpython-38.pyc' '$RemoteComponents/__pycache__/k1_control_composite_subgrid.cpython-38.pyc'")
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    & $PSCommandPath -Action Validate -PrinterHost $PrinterHost -CaptureId $CaptureId
    Remove-RemoteStaging
    [pscustomobject]@{
        capture_id = $CaptureId
        gate = $RequiredGate
        result = 'DEPLOY_COMPOSITE_SUBGRID_V1_OK'
        printer_cfg_changed_during_deployment = $false
        calibration_action = $false
        heater_command = $false
        printer_motion = $false
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LocalCapture 'deploy-result.json') -Encoding UTF8
    Write-Output "DEPLOY_COMPOSITE_SUBGRID_V1_OK capture=$CaptureId"
}
catch {
    $failure = $_
    if ($MutationStarted) {
        try { Invoke-ExactRollback }
        catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
