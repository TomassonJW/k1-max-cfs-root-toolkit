[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-composite-mesh-recovery-v1',
    [switch]$Execute,
    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-COMPOSITE-MESH-RECOVERY-V1'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\composite-mesh-v1'
$ManifestPath = Join-Path $PackageRoot 'recovery-deployment-manifest.json'
$Validator = Join-Path $WorkspaceRoot 'scripts\validate-k1-control-composite-mesh-recovery.py'
$Runner = Join-Path $WorkspaceRoot 'scripts\run-k1-control-composite-mesh-v1.ps1'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteComponents = "$RemoteRoot/current/moonraker/moonraker/moonraker/components"
$RemoteCore = "$RemoteComponents/k1_control_composite_mesh_core.py"
$RemoteComponent = "$RemoteComponents/k1_control_composite_mesh.py"
$RemoteCompose = "$RemoteComponents/k1_control_composite_mesh_compose.py"
$RemoteState = "$RemoteRoot/state/k1-control-composite-mesh.json"
$RemoteConfig = "$RemoteRoot/current/config/moonraker.conf"
$RemotePrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$MoonrakerService = '/etc/init.d/S56k1_control_moonraker'
$RemoteBackup = "$RemoteRoot/backups/$CaptureId-composite-mesh-recovery-v1"
$RemoteStaging = "$RemoteRoot/tmp/$CaptureId-composite-mesh-recovery-v1"
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
        '-o', 'BatchMode=yes', '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no', '-o', 'ConnectTimeout=8',
        $PrinterHost, $Command
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
        '-O', '-o', 'BatchMode=yes', '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no', '-o', 'ConnectTimeout=8',
        (Resolve-Path -LiteralPath $Source).Path, "$PrinterHost`:$Destination"
    )
    & scp.exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Transfert SCP KO : $Destination" }
}

function Copy-FromRemote {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $arguments = @(
        '-O', '-o', 'BatchMode=yes', '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no', '-o', 'ConnectTimeout=8',
        "$PrinterHost`:$Source", $Destination
    )
    & scp.exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Copie SCP locale KO : $Source" }
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
    foreach ($pin in @(
        @{ Path = $PSCommandPath; Hash = [string]$manifest.deployer.sha256 },
        @{ Path = $Runner; Hash = [string]$manifest.runner.sha256 },
        @{ Path = $Validator; Hash = [string]$manifest.validator.sha256 },
        @{ Path = (Join-Path $PackageRoot ([string]$manifest.contract.path)); Hash = [string]$manifest.contract.sha256 }
    )) {
        if ((Get-LocalSha256 $pin.Path) -cne $pin.Hash) {
            throw "Empreinte locale inattendue : $($pin.Path)"
        }
    }
    foreach ($file in $manifest.files) {
        if ((Get-LocalSha256 (Join-Path $PackageRoot ([string]$file.source))) -cne [string]$file.sha256) {
            throw "Payload local inattendu : $($file.source)"
        }
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
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/composite_mesh/status'") -join "`n"
    $state = ($raw | ConvertFrom-Json).result
    if (-not $state) { throw 'API composite sans état.' }
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
    if ($status.print_stats.state -cne 'standby' -or $status.print_stats.filename) { throw 'Imprimante non disponible.' }
    if ([double]$status.extruder.target -ne 0 -or [double]$status.heater_bed.target -ne 0) { throw 'Les chauffes ne sont pas coupées.' }
    if ([string]$status.toolhead.homed_axes) { throw 'Les axes sont encore référencés.' }
    $runtime = $status.'gcode_macro KCTRL_STATE'
    $store = $status.k1_control_store
    $path = $status.'gcode_macro KCTRL_CAL_PATH_STATE'
    if ([int]$runtime.ready -ne 1 -or [int]$runtime.accepted_z_valid -ne 1 -or
        [double]$runtime.accepted_z_offset -ne -0.04 -or [int]$runtime.session_active -ne 0 -or
        [int]$runtime.low_moves_armed -ne 0 -or -not $store -or $store.integrity -cne 'ok') {
        throw 'Runtime ou stockage Z non sûr.'
    }
    if (@('idle','committed','cancelled') -notcontains [string]$path.phase -or
        [int]$path.motion_armed -ne 0 -or [int]$path.commit_ready -ne 0) { throw 'Chemin Z non fermé.' }
    $profiles = @($status.bed_mesh.profiles.PSObject.Properties.Name)
    if ($profiles -notcontains 'k1_p001_t055_r001_n06x06' -or
        $profiles -contains 'k1_p001_t055_r001_n11x11' -or
        @($profiles | Where-Object { $_ -like 'K1_COMPOSITE_CAPTURE_*' }).Count -ne 0 -or
        [string]$status.bed_mesh.profile_name -cne 'k1_p001_t055_r001_n06x06') {
        throw 'Profils bed_mesh non sûrs pour la reprise.'
    }
    foreach ($unit in @('T1','T2')) {
        if ([string]$status.box.$unit.state -cne 'connect') { throw "CFS $unit non connecté." }
    }
    if ((Get-RemoteSha256 $RemotePrinterConfig) -cne [string]$Manifest.baseline.printer_cfg_sha256) {
        throw 'printer.cfg diffère du backup physique.'
    }
    return $status
}

function Assert-RetainedState {
    param([Parameter(Mandatory = $true)]$Manifest)
    if ((Get-RemoteSha256 $RemoteState) -cne [string]$Manifest.baseline.state_sha256) {
        throw 'Empreinte de la capture 144 contacts inattendue.'
    }
    $state = Get-CompositeState
    if ([string]$state.phase -cne 'failed' -or [bool]$state.busy -or
        [string]$state.campaign_id -cne [string]$Manifest.baseline.campaign_id -or
        [int]$state.completed_passes -ne 4 -or [int]$state.physical_contacts -ne 144 -or
        -not [bool]$state.backup_available -or [bool]$state.config_written) {
        throw 'État de capture complète inattendu.'
    }
    if ((@($state.passes | ForEach-Object { $_.name }) -join ',') -cne 'north_west,north_east,south_west,south_east') {
        throw 'Ordre des quadrants conservés inattendu.'
    }
    New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null
    $localState = Join-Path $LocalCapture 'k1-control-composite-mesh.json'
    Copy-FromRemote $RemoteState $localState
    if ((Get-LocalSha256 $localState) -cne [string]$Manifest.baseline.state_sha256) {
        throw 'Copie locale de la capture altérée.'
    }
    $validation = & python.exe $Validator $localState 2>&1
    if ($LASTEXITCODE -ne 0 -or ($validation -join "`n") -notmatch 'VALIDATE_COMPOSITE_MESH_RECOVERY_OK') {
        throw "Validation de la reprise 144 contacts KO : $($validation -join "`n")"
    }
    $validation | Set-Content -LiteralPath (Join-Path $LocalCapture 'recovery-validation.json') -Encoding UTF8
    return $state
}

function Wait-Moonraker {
    param([int]$Attempts = 60)
    $last = 'aucune réponse'
    for ($index = 1; $index -le $Attempts; $index++) {
        try {
            $info = Get-ServerInfo
            if (@($info.components) -contains 'k1_control_composite_mesh' -and
                @($info.failed_components).Count -eq 0 -and @($info.warnings).Count -eq 0) { return }
            $last = "failed=$(@($info.failed_components) -join ',') warnings=$(@($info.warnings) -join ',')"
        }
        catch { $last = $_.Exception.Message }
        Start-Sleep -Seconds 1
    }
    throw "Moonraker non stabilisé : $last"
}

function Assert-RemoteCandidateParse {
    $sources = @{}
    foreach ($name in @('k1_control_composite_mesh_core.py', 'k1_control_composite_mesh.py', 'compose_mesh.py')) {
        $sources[$name] = [Convert]::ToBase64String(
            [IO.File]::ReadAllBytes((Join-Path $PackageRoot $name))
        )
    }
    $program = @"
import base64
sources = {}
"@
    $program += "`n"
    foreach ($name in $sources.Keys) {
        $program += "sources['$name'] = base64.b64decode('$($sources[$name])')`n"
    }
    $program += @"
for name, source in sources.items():
    compile(source, name, 'exec')
print('REMOTE_COMPOSITE_MESH_RECOVERY_PARSE_OK')
"@
    $python = "$RemoteRoot/current/moonraker/moonraker-env/bin/python"
    $arguments = @(
        '-o', 'BatchMode=yes', '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no', '-o', 'ConnectTimeout=8',
        $PrinterHost, "'$python' -"
    )
    $output = $program | & ssh.exe @arguments 2>&1
    if ($LASTEXITCODE -ne 0 -or ($output | Select-Object -Last 1) -cne 'REMOTE_COMPOSITE_MESH_RECOVERY_PARSE_OK') {
        throw "Parse distant de la reprise composite KO : $($output -join "`n")"
    }
}

function Assert-PreviousRevision {
    param([Parameter(Mandatory = $true)]$Manifest)
    foreach ($file in $Manifest.files) {
        $expected = [string]$file.previous_sha256
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne $expected) {
            throw "Révision précédente inattendue : $($file.destination)"
        }
    }
    if ((Get-RemoteSha256 $RemoteConfig) -cne [string]$Manifest.baseline.moonraker_conf_sha256) { throw 'moonraker.conf inattendu.' }
    [void](Assert-RetainedState $Manifest)
    [void](Assert-SafePrinter $Manifest)
    Assert-RemoteCandidateParse
}

function Assert-Installed {
    param([Parameter(Mandatory = $true)]$Manifest)
    foreach ($file in $Manifest.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne [string]$file.sha256) {
            throw "Payload de reprise inattendu : $($file.destination)"
        }
    }
    if ((Get-RemoteSha256 $RemoteConfig) -cne [string]$Manifest.baseline.moonraker_conf_sha256) { throw 'moonraker.conf a changé.' }
    $info = Get-ServerInfo
    if (@($info.failed_components).Count -ne 0 -or @($info.warnings).Count -ne 0) { throw 'Moonraker expose un échec ou un avertissement.' }
    [void](Assert-RetainedState $Manifest)
    [void](Assert-SafePrinter $Manifest)
}

function Remove-RemoteStaging {
    [void](Invoke-Remote "rm -f '$RemoteStaging/k1_control_composite_mesh_core.py' '$RemoteStaging/k1_control_composite_mesh.py' '$RemoteStaging/compose_mesh.py' && rmdir '$RemoteStaging' 2>/dev/null || true")
}

function Invoke-ExactRollback {
    $manifest = Assert-Package
    foreach ($file in $manifest.files) {
        $backupName = "$($file.source).before"
        if ((Get-RemoteSha256 "$RemoteBackup/$backupName") -cne [string]$file.previous_sha256) {
            throw "Backup de composant inattendu : $backupName"
        }
        $destination = [string]$file.destination
        [void](Invoke-Remote "cp '$RemoteBackup/$backupName' '$destination.rollback-next' && chmod 0644 '$destination.rollback-next' && mv '$destination.rollback-next' '$destination'")
    }
    if ((Get-RemoteSha256 "$RemoteBackup/k1-control-composite-mesh.json.before") -cne [string]$manifest.baseline.state_sha256) {
        throw 'Backup de l état 144 contacts inattendu.'
    }
    [void](Invoke-Remote "cp '$RemoteBackup/k1-control-composite-mesh.json.before' '$RemoteState.rollback-next' && chmod 0644 '$RemoteState.rollback-next' && mv '$RemoteState.rollback-next' '$RemoteState'")
    [void](Invoke-Remote "rm -f '$RemoteComponents/__pycache__/k1_control_composite_mesh_core.cpython-38.pyc' '$RemoteComponents/__pycache__/k1_control_composite_mesh.cpython-38.pyc' '$RemoteComponents/__pycache__/k1_control_composite_mesh_compose.cpython-38.pyc'")
    Remove-RemoteStaging
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    Assert-PreviousRevision $manifest
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "PLAN_COMPOSITE_MESH_RECOVERY_V1_OK gate=$RequiredGate"
    Write-Output 'Remplace trois modules Moonraker, préserve les 144 contacts exacts et redémarre uniquement Moonraker.'
    Write-Output 'Aucune chauffe, référence, mesure, mouvement ou écriture Z pendant la pose.'
    exit 0
}
if ($Action -eq 'Preflight') { Assert-PreviousRevision $manifest; Write-Output 'PREFLIGHT_COMPOSITE_MESH_RECOVERY_V1_OK'; exit 0 }
if ($Action -eq 'Validate') { Assert-Installed $manifest; Write-Output 'VALIDATE_COMPOSITE_MESH_RECOVERY_V1_OK'; exit 0 }
if ($Action -eq 'Rollback') { Assert-MutationGate; Invoke-ExactRollback; Write-Output "ROLLBACK_COMPOSITE_MESH_RECOVERY_V1_OK capture=$CaptureId"; exit 0 }

Assert-MutationGate
Assert-PreviousRevision $manifest
New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null
try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup' '$RemoteStaging'")
    foreach ($file in $manifest.files) {
        $destination = [string]$file.destination
        $backupName = "$($file.source).before"
        [void](Invoke-Remote "cp '$destination' '$RemoteBackup/$backupName'")
        if ((Get-RemoteSha256 "$RemoteBackup/$backupName") -cne [string]$file.previous_sha256) {
            throw "Backup exact non conforme : $backupName"
        }
        Copy-ToRemote (Join-Path $PackageRoot ([string]$file.source)) "$RemoteStaging/$($file.source)"
        if ((Get-RemoteSha256 "$RemoteStaging/$($file.source)") -cne [string]$file.sha256) {
            throw "Transfert non conforme : $($file.source)"
        }
    }
    [void](Invoke-Remote "cp '$RemoteState' '$RemoteBackup/k1-control-composite-mesh.json.before'")
    if ((Get-RemoteSha256 "$RemoteBackup/k1-control-composite-mesh.json.before") -cne [string]$manifest.baseline.state_sha256) {
        throw 'Backup exact de l état 144 contacts non conforme.'
    }
    $python = "$RemoteRoot/current/moonraker/moonraker-env/bin/python"
    [void](Invoke-Remote "'$python' -c `"compile(open('$RemoteStaging/k1_control_composite_mesh_core.py').read(), 'core.py', 'exec'); compile(open('$RemoteStaging/k1_control_composite_mesh.py').read(), 'component.py', 'exec'); compile(open('$RemoteStaging/compose_mesh.py').read(), 'compose.py', 'exec')`"")
    $MutationStarted = $true
    foreach ($file in $manifest.files) {
        $destination = [string]$file.destination
        [void](Invoke-Remote "cp '$RemoteStaging/$($file.source)' '$destination.next' && chmod 0644 '$destination.next' && mv '$destination.next' '$destination'")
    }
    [void](Invoke-Remote "rm -f '$RemoteComponents/__pycache__/k1_control_composite_mesh_core.cpython-38.pyc' '$RemoteComponents/__pycache__/k1_control_composite_mesh.cpython-38.pyc' '$RemoteComponents/__pycache__/k1_control_composite_mesh_compose.cpython-38.pyc'")
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    & $PSCommandPath -Action Validate -PrinterHost $PrinterHost -CaptureId $CaptureId
    Remove-RemoteStaging
    [pscustomobject]@{
        capture_id = $CaptureId
        result = 'DEPLOY_COMPOSITE_MESH_RECOVERY_V1_OK'
        moonraker_restart_only = $true
        physical_action = $false
        retained_contacts = 144
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LocalCapture 'deploy-result.json') -Encoding UTF8
    Write-Output "DEPLOY_COMPOSITE_MESH_RECOVERY_V1_OK capture=$CaptureId"
}
catch {
    $failure = $_
    if ($MutationStarted) {
        try { Invoke-ExactRollback }
        catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
