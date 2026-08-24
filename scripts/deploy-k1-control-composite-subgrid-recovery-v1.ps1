[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-composite-mesh-subgrid-recovery-v1',
    [switch]$Execute,
    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-COMPOSITE-MESH-SUBGRID-RECOVERY-V1'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\composite-subgrid-v1'
$ManifestPath = Join-Path $PackageRoot 'recovery-deployment-manifest.json'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteComponents = "$RemoteRoot/current/moonraker/moonraker/moonraker/components"
$RemoteCore = "$RemoteComponents/k1_control_composite_subgrid_core.py"
$RemoteComponent = "$RemoteComponents/k1_control_composite_subgrid.py"
$RemoteState = "$RemoteRoot/state/k1-control-composite-subgrid.json"
$RemoteConfig = "$RemoteRoot/current/config/moonraker.conf"
$RemotePrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$MoonrakerService = '/etc/init.d/S56k1_control_moonraker'
$RemoteBackup = "$RemoteRoot/backups/$CaptureId-composite-subgrid-recovery-v1"
$RemoteStaging = "$RemoteRoot/tmp/$CaptureId-composite-subgrid-recovery-v1"
$RemoteMigration = "$RemoteStaging/migrate_composite_state.py"
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
        throw 'Manifeste de reprise composite inattendu.'
    }
    if ((Get-LocalSha256 $PSCommandPath) -cne [string]$manifest.deployer.sha256) {
        throw 'Empreinte du déployeur de reprise inattendue.'
    }
    foreach ($file in $manifest.files) {
        $local = Join-Path $PackageRoot ([string]$file.source)
        if ((Get-LocalSha256 $local) -cne [string]$file.sha256) {
            throw "Empreinte locale inattendue : $($file.source)"
        }
    }
    $migration = Join-Path $PackageRoot ([string]$manifest.state_migration.source)
    if ((Get-LocalSha256 $migration) -cne [string]$manifest.state_migration.sha256) {
        throw 'Empreinte locale de la migration d état inattendue.'
    }
    return $manifest
}

function Get-ServerInfo {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/server/info'") -join "`n"
    $info = ($raw | ConvertFrom-Json).result
    if (-not $info) { throw 'Moonraker sans server/info.' }
    return $info
}

function Get-CompositeState {
    try {
        $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/composite_subgrid/status'") -join "`n"
        $state = ($raw | ConvertFrom-Json).result
        if ($state) { return $state }
    }
    catch { }
    $persisted = (Invoke-Remote "cat '$RemoteState'") -join "`n"
    $state = $persisted | ConvertFrom-Json
    if (-not $state) { throw 'État composite persistant illisible.' }
    $state | Add-Member -NotePropertyName gate -NotePropertyValue 'G4-K1-CONTROL-COMPOSITE-MESH-SUBGRID-V1' -Force
    $state | Add-Member -NotePropertyName physical_contacts -NotePropertyValue 25 -Force
    $state | Add-Member -NotePropertyName backup_available -NotePropertyValue ([bool]$state.backup) -Force
    return $state
}

function Get-PrinterStatus {
    $url = "http://127.0.0.1:7125/printer/objects/query?print_stats&extruder&heater_bed&toolhead&bed_mesh&configfile&box&gcode_macro+KCTRL_STATE&k1_control_store&gcode_macro+KCTRL_CAL_PATH_STATE"
    $raw = (Invoke-Remote "curl '$url'") -join "`n"
    $status = ($raw | ConvertFrom-Json).result.status
    if (-not $status) { throw 'Réponse Moonraker sans état Klipper.' }
    return $status
}

function Assert-SafePrinter {
    param([Parameter(Mandatory = $true)]$Manifest)
    $status = Get-PrinterStatus
    if ($status.print_stats.state -cne 'standby' -or $status.print_stats.filename) {
        throw "Imprimante non disponible : $($status.print_stats.state)"
    }
    if ([double]$status.extruder.target -ne 0 -or [double]$status.heater_bed.target -ne 0) {
        throw 'Les chauffes ne sont pas coupées.'
    }
    if ([string]$status.toolhead.homed_axes) { throw 'Les axes sont encore référencés.' }
    if ([string]$status.bed_mesh.profile_name -cne 'k1_p001_t055_r001_n06x06') {
        throw 'Le profil robuste 6x6 est inactif.'
    }
    $runtime = $status.'gcode_macro KCTRL_STATE'
    $store = $status.k1_control_store
    $path = $status.'gcode_macro KCTRL_CAL_PATH_STATE'
    if ([int]$runtime.ready -ne 1 -or [int]$runtime.accepted_z_valid -ne 1 -or
        [double]$runtime.accepted_z_offset -ne -0.04 -or [int]$runtime.session_active -ne 0 -or
        [int]$runtime.low_moves_armed -ne 0 -or -not $store -or $store.integrity -cne 'ok') {
        throw 'Runtime ou stockage Z non sûr.'
    }
    if (@('idle', 'committed', 'cancelled') -notcontains [string]$path.phase -or
        [int]$path.motion_armed -ne 0 -or [int]$path.commit_ready -ne 0) {
        throw 'Chemin Z non fermé.'
    }
    foreach ($unit in @('T1', 'T2')) {
        if ([string]$status.box.$unit.state -cne 'connect') { throw "CFS $unit non connecté." }
    }
    if ((Get-RemoteSha256 $RemotePrinterConfig) -cne [string]$Manifest.baseline.printer_cfg_sha256) {
        throw 'printer.cfg a changé.'
    }
    return $status
}

function Assert-CapturedState {
    $state = Get-CompositeState
    if ([bool]$state.busy -or @('failed', 'qualified') -notcontains [string]$state.phase -or
        [int]$state.physical_contacts -ne 25 -or -not [bool]$state.backup_available) {
        throw "État de capture inattendu : phase=$($state.phase) busy=$($state.busy)"
    }
    $matrix = @($state.matrix)
    if ($matrix.Count -ne 5) { throw 'La matrice capturée doit avoir cinq lignes.' }
    foreach ($row in $matrix) {
        if (@($row).Count -ne 5) { throw 'La matrice capturée doit avoir cinq colonnes.' }
    }
    if ((@($state.context.x_indices) -join ',') -cne '1,3,5,7,9' -or
        (@($state.context.y_indices) -join ',') -cne '1,3,5,7,9' -or
        [int]$state.context.klipper_restart_count -ne 0) {
        throw 'Contexte de capture inattendu.'
    }
    return $state
}

function Wait-Moonraker {
    param([int]$Attempts = 60)
    $last = 'aucune réponse'
    for ($index = 1; $index -le $Attempts; $index++) {
        try {
            $info = Get-ServerInfo
            if (@($info.components) -contains 'k1_control_composite_subgrid' -and
                @($info.failed_components).Count -eq 0 -and @($info.warnings).Count -eq 0) {
                return
            }
            $last = "failed=$(@($info.failed_components) -join ',') warnings=$(@($info.warnings) -join ',')"
        }
        catch { $last = $_.Exception.Message }
        Start-Sleep -Seconds 1
    }
    throw "Moonraker non stabilisé : $last"
}

function Assert-PreviousRevision {
    param([Parameter(Mandatory = $true)]$Manifest)
    if ((Get-RemoteSha256 $RemoteCore) -cne [string]$Manifest.baseline.core_sha256 -or
        (Get-RemoteSha256 $RemoteComponent) -cne [string]$Manifest.baseline.component_sha256) {
        throw 'Révision composite précédente inattendue.'
    }
    if ((Get-RemoteSha256 $RemoteConfig) -cne [string]$Manifest.baseline.moonraker_conf_sha256) {
        throw 'moonraker.conf inattendu.'
    }
    [void](Assert-CapturedState)
    [void](Assert-SafePrinter $Manifest)
}

function Assert-Installed {
    param([Parameter(Mandatory = $true)]$Manifest)
    foreach ($file in $Manifest.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne [string]$file.sha256) {
            throw "Empreinte distante inattendue : $($file.destination)"
        }
    }
    if ((Get-RemoteSha256 $RemoteConfig) -cne [string]$Manifest.baseline.moonraker_conf_sha256) {
        throw 'moonraker.conf a changé.'
    }
    $info = Get-ServerInfo
    if (@($info.failed_components).Count -ne 0 -or @($info.warnings).Count -ne 0) {
        throw 'Moonraker expose un échec ou un avertissement.'
    }
    [void](Assert-CapturedState)
    [void](Assert-SafePrinter $Manifest)
}

function Remove-RemoteStaging {
    [void](Invoke-Remote "rm -f '$RemoteStaging/k1_control_composite_subgrid_core.py' '$RemoteStaging/k1_control_composite_subgrid.py' '$RemoteMigration' && rmdir '$RemoteStaging' 2>/dev/null || true")
}

function Invoke-ExactRollback {
    $manifest = Assert-Package
    if ((Get-RemoteSha256 "$RemoteBackup/k1_control_composite_subgrid_core.py.before") -cne [string]$manifest.baseline.core_sha256 -or
        (Get-RemoteSha256 "$RemoteBackup/k1_control_composite_subgrid.py.before") -cne [string]$manifest.baseline.component_sha256) {
        throw 'Backup de reprise composite inattendu.'
    }
    if ((Get-RemoteSha256 "$RemoteBackup/migrate_composite_state.py") -cne [string]$manifest.state_migration.sha256) {
        throw 'Migration de rollback inattendue.'
    }
    [void](Invoke-Remote "cp '$RemoteBackup/k1_control_composite_subgrid_core.py.before' '$RemoteCore.rollback-next' && chmod 0644 '$RemoteCore.rollback-next' && mv '$RemoteCore.rollback-next' '$RemoteCore'")
    [void](Invoke-Remote "cp '$RemoteBackup/k1_control_composite_subgrid.py.before' '$RemoteComponent.rollback-next' && chmod 0644 '$RemoteComponent.rollback-next' && mv '$RemoteComponent.rollback-next' '$RemoteComponent'")
    $python = "$RemoteRoot/current/moonraker/moonraker-env/bin/python"
    [void](Invoke-Remote "'$python' '$RemoteBackup/migrate_composite_state.py' '$RemoteState'")
    [void](Invoke-Remote "rm -f '$RemoteComponents/__pycache__/k1_control_composite_subgrid_core.cpython-38.pyc' '$RemoteComponents/__pycache__/k1_control_composite_subgrid.cpython-38.pyc'")
    Remove-RemoteStaging
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    Assert-PreviousRevision $manifest
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "PLAN_COMPOSITE_SUBGRID_RECOVERY_V1_OK gate=$RequiredGate"
    Write-Output 'Remplace seulement les deux composants composites et redémarre uniquement Moonraker.'
    Write-Output 'Préserve la matrice 5x5 déjà mesurée; aucune chauffe, référence, mesure, mouvement ou écriture Z.'
    exit 0
}

if ($Action -eq 'Preflight') {
    Assert-PreviousRevision $manifest
    Write-Output 'PREFLIGHT_COMPOSITE_SUBGRID_RECOVERY_V1_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    Assert-Installed $manifest
    Write-Output 'VALIDATE_COMPOSITE_SUBGRID_RECOVERY_V1_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Assert-MutationGate
    Invoke-ExactRollback
    Write-Output "ROLLBACK_COMPOSITE_SUBGRID_RECOVERY_V1_OK capture=$CaptureId"
    exit 0
}

Assert-MutationGate
Assert-PreviousRevision $manifest
New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup' '$RemoteStaging'")
    [void](Invoke-Remote "cp '$RemoteCore' '$RemoteBackup/k1_control_composite_subgrid_core.py.before' && cp '$RemoteComponent' '$RemoteBackup/k1_control_composite_subgrid.py.before' && cp '$RemoteState' '$RemoteBackup/k1-control-composite-subgrid.json.before'")
    if ((Get-RemoteSha256 "$RemoteBackup/k1_control_composite_subgrid_core.py.before") -cne [string]$manifest.baseline.core_sha256 -or
        (Get-RemoteSha256 "$RemoteBackup/k1_control_composite_subgrid.py.before") -cne [string]$manifest.baseline.component_sha256) {
        throw 'Backup exact des composants non conforme.'
    }
    if ((Get-RemoteSha256 "$RemoteBackup/k1-control-composite-subgrid.json.before") -cne (Get-RemoteSha256 $RemoteState)) {
        throw 'Backup exact de l état composite non conforme.'
    }
    foreach ($file in $manifest.files) {
        Copy-ToRemote (Join-Path $PackageRoot ([string]$file.source)) "$RemoteStaging/$($file.source)"
        if ((Get-RemoteSha256 "$RemoteStaging/$($file.source)") -cne [string]$file.sha256) {
            throw "Transfert non conforme : $($file.source)"
        }
    }
    Copy-ToRemote (Join-Path $PackageRoot ([string]$manifest.state_migration.source)) $RemoteMigration
    if ((Get-RemoteSha256 $RemoteMigration) -cne [string]$manifest.state_migration.sha256) {
        throw 'Transfert non conforme : migration d état.'
    }
    [void](Invoke-Remote "cp '$RemoteMigration' '$RemoteBackup/migrate_composite_state.py'")
    if ((Get-RemoteSha256 "$RemoteBackup/migrate_composite_state.py") -cne [string]$manifest.state_migration.sha256) {
        throw 'Backup de la migration non conforme.'
    }
    $python = "$RemoteRoot/current/moonraker/moonraker-env/bin/python"
    [void](Invoke-Remote "'$python' -c `"compile(open('$RemoteStaging/k1_control_composite_subgrid_core.py').read(), 'core.py', 'exec'); compile(open('$RemoteStaging/k1_control_composite_subgrid.py').read(), 'component.py', 'exec'); compile(open('$RemoteMigration').read(), 'migration.py', 'exec')`"")
    $MutationStarted = $true
    [void](Invoke-Remote "'$python' '$RemoteMigration' '$RemoteState'")
    $migrated = Get-CompositeState
    if ([int]$migrated.version -ne 1 -or $migrated.PSObject.Properties.Name -contains 'schema') {
        throw 'Migration du marqueur d état non conforme.'
    }
    foreach ($file in $manifest.files) {
        $destination = [string]$file.destination
        [void](Invoke-Remote "cp '$RemoteStaging/$($file.source)' '$destination.next' && chmod 0644 '$destination.next' && mv '$destination.next' '$destination'")
    }
    [void](Invoke-Remote "rm -f '$RemoteComponents/__pycache__/k1_control_composite_subgrid_core.cpython-38.pyc' '$RemoteComponents/__pycache__/k1_control_composite_subgrid.cpython-38.pyc'")
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    & $PSCommandPath -Action Validate -PrinterHost $PrinterHost -CaptureId $CaptureId
    Remove-RemoteStaging
    [pscustomobject]@{
        capture_id = $CaptureId
        result = 'DEPLOY_COMPOSITE_SUBGRID_RECOVERY_V1_OK'
        moonraker_restart_only = $true
        physical_action = $false
        state_preserved = $true
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LocalCapture 'deploy-result.json') -Encoding UTF8
    Write-Output "DEPLOY_COMPOSITE_SUBGRID_RECOVERY_V1_OK capture=$CaptureId"
}
catch {
    $failure = $_
    if ($MutationStarted) {
        try { Invoke-ExactRollback }
        catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
