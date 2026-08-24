[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Run', 'Recover', 'Validate', 'Cancel')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-composite-mesh-v1-run',
    [switch]$Execute,
    [string]$Gate = '',
    [int]$TimeoutSeconds = 3600
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-COMPOSITE-MESH-V1'
$RecoveryGate = 'G4-K1-CONTROL-COMPOSITE-MESH-RECOVERY-V1'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\composite-mesh-v1'
$ManifestPath = Join-Path $PackageRoot 'deployment-manifest.json'
$ArtifactValidator = Join-Path $WorkspaceRoot 'scripts\validate-k1-control-composite-mesh-artifacts.py'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteComponents = "$RemoteRoot/current/moonraker/moonraker/moonraker/components"
$RemotePrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$RemoteZState = "$RemoteRoot/state/k1-control-z-state.json"
$LocalCapture = Join-Path $WorkspaceRoot "inventory\raw\$CaptureId"

function Assert-MutationGate {
    param([string]$ExpectedGate = $RequiredGate)
    if (-not $Execute -or $Gate -cne $ExpectedGate) {
        throw "Action bloquée : -Execute et -Gate '$ExpectedGate' sont obligatoires."
    }
}

function Get-LocalSha256 {
    param([string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Invoke-Remote {
    param([string]$Command)
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

function Copy-FromRemote {
    param([string]$Source, [string]$Destination)
    $arguments = @(
        '-O', '-o', 'BatchMode=yes', '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no', '-o', 'ConnectTimeout=8',
        "$PrinterHost`:$Source", $Destination
    )
    & scp.exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Copie distante KO : $Source" }
}

function Get-RemoteSha256 {
    param([string]$Path)
    $line = Invoke-Remote "sha256sum '$Path'"
    return ((($line | Select-Object -First 1) -split '\s+')[0]).ToLowerInvariant()
}

function Assert-Package {
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ($manifest.contract_id -cne $RequiredGate -or $manifest.status -cne 'deployment_candidate') { throw 'Manifeste COMPOSITE-MESH-V1 inattendu.' }
    foreach ($pin in @(
        @{ Path = $PSCommandPath; Hash = [string]$manifest.runner.sha256 },
        @{ Path = $ArtifactValidator; Hash = [string]$manifest.artifact_validator.sha256 },
        @{ Path = (Join-Path $PackageRoot ([string]$manifest.contract.path)); Hash = [string]$manifest.contract.sha256 }
    )) {
        if ((Get-LocalSha256 $pin.Path) -cne $pin.Hash) { throw "Empreinte locale inattendue : $($pin.Path)" }
    }
    foreach ($file in $manifest.files) {
        if ((Get-LocalSha256 (Join-Path $PackageRoot ([string]$file.source))) -cne [string]$file.sha256) { throw "Payload local inattendu : $($file.source)" }
    }
    return $manifest
}

function Get-ServerInfo {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/server/info'") -join "`n"
    return ($raw | ConvertFrom-Json).result
}

function Get-CompositeState {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/composite_mesh/status'") -join "`n"
    $state = ($raw | ConvertFrom-Json).result
    if (-not $state) { throw 'API composite complète sans état.' }
    return $state
}

function Get-SubgridState {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/composite_subgrid/status'") -join "`n"
    $state = ($raw | ConvertFrom-Json).result
    if (-not $state) { throw 'API de sous-grille sans état.' }
    return $state
}

function Get-PrinterStatus {
    $url = "http://127.0.0.1:7125/printer/objects/query?print_stats&extruder&heater_bed&toolhead&bed_mesh&configfile&box&gcode_macro+KCTRL_STATE&k1_control_store&gcode_macro+KCTRL_CAL_PATH_STATE"
    $raw = (Invoke-Remote "curl '$url'") -join "`n"
    $status = ($raw | ConvertFrom-Json).result.status
    if (-not $status) { throw 'Réponse Moonraker sans état Klipper.' }
    return $status
}

function Assert-Installed {
    $manifest = Assert-Package
    foreach ($file in $manifest.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne [string]$file.sha256) { throw "Payload distant inattendu : $($file.destination)" }
    }
    $info = Get-ServerInfo
    if (@($info.components) -notcontains 'k1_control_composite_mesh' -or @($info.failed_components).Count -ne 0 -or @($info.warnings).Count -ne 0) { throw 'Composant composite complet absent ou échoué.' }
    return $manifest
}

function Assert-SubgridQualified {
    $state = Get-SubgridState
    if ([string]$state.phase -cne 'qualified' -or [bool]$state.busy -or [int]$state.physical_contacts -ne 25) { throw 'SUBGRID-V1 n est pas qualifiée.' }
}

function Assert-SafePrinter {
    param([Parameter(Mandatory = $true)]$Status, [bool]$ExpectTarget)
    if ($Status.print_stats.state -cne 'standby' -or $Status.print_stats.filename) { throw 'Imprimante non disponible.' }
    if ([double]$Status.extruder.target -ne 0 -or [double]$Status.heater_bed.target -ne 0) { throw 'Les chauffes ne sont pas coupées.' }
    if ([string]$Status.toolhead.homed_axes) { throw 'Les axes sont encore référencés.' }
    $runtime = $Status.'gcode_macro KCTRL_STATE'
    $store = $Status.k1_control_store
    $path = $Status.'gcode_macro KCTRL_CAL_PATH_STATE'
    if ([int]$runtime.ready -ne 1 -or [int]$runtime.accepted_z_valid -ne 1 -or [double]$runtime.accepted_z_offset -ne -0.04 -or
        [int]$runtime.session_active -ne 0 -or [int]$runtime.low_moves_armed -ne 0 -or -not $store -or $store.integrity -cne 'ok') { throw 'Runtime ou stockage Z non sûr.' }
    if (@('idle','committed','cancelled') -notcontains [string]$path.phase -or [int]$path.motion_armed -ne 0 -or [int]$path.commit_ready -ne 0) { throw 'Chemin Z non fermé.' }
    $profiles = @($Status.bed_mesh.profiles.PSObject.Properties.Name)
    if ($profiles -notcontains 'k1_p001_t055_r001_n06x06' -or [string]$Status.bed_mesh.profile_name -cne 'k1_p001_t055_r001_n06x06') { throw 'Le profil robuste 6x6 n est pas actif.' }
    if (($profiles -contains 'k1_p001_t055_r001_n11x11') -ne $ExpectTarget) { throw 'Présence du profil 11x11 inattendue.' }
    if (@($profiles | Where-Object { $_ -like 'K1_COMPOSITE_CAPTURE_*' -or $_ -eq 'K1_TRANSIENT' }).Count -ne 0) { throw 'Un profil temporaire subsiste.' }
    foreach ($unit in @('T1','T2')) {
        if ([string]$Status.box.$unit.state -cne 'connect') { throw "CFS $unit non connecté." }
    }
}

function Assert-ReadyForStart {
    $manifest = Assert-Installed
    Assert-SubgridQualified
    $state = Get-CompositeState
    if ([string]$state.phase -cne 'idle' -or [bool]$state.busy -or [int]$state.completed_passes -ne 0 -or [bool]$state.backup_available) { throw 'État composite non neuf.' }
    $status = Get-PrinterStatus
    Assert-SafePrinter $status $false
    if ((Get-RemoteSha256 $RemotePrinterConfig) -cne [string]$manifest.baseline.printer_cfg_sha256) { throw 'printer.cfg de base inattendu.' }
    return @{ State=$state; Printer=$status }
}

function Save-Evidence {
    param([string]$Name, $Value)
    New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null
    $Value | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath (Join-Path $LocalCapture $Name) -Encoding UTF8
}

function Invoke-Start {
    $url = "http://127.0.0.1:7125/machine/k1_control/composite_mesh/start?gate=$RequiredGate&plate_clear=true"
    $raw = (Invoke-Remote "curl -X POST '$url'") -join "`n"
    $response = $raw | ConvertFrom-Json
    if (-not $response.result) { throw "Démarrage composite refusé : $raw" }
    return $response.result
}

function Invoke-Cancel {
    $raw = (Invoke-Remote "curl -X POST 'http://127.0.0.1:7125/machine/k1_control/composite_mesh/cancel'") -join "`n"
    $response = $raw | ConvertFrom-Json
    if (-not $response.result) { throw "Annulation composite refusée : $raw" }
    return $response.result
}

function Invoke-Recover {
    $url = "http://127.0.0.1:7125/machine/k1_control/composite_mesh/recover?gate=$RecoveryGate"
    $raw = (Invoke-Remote "curl -X POST '$url'") -join "`n"
    $response = $raw | ConvertFrom-Json
    if (-not $response.result) { throw "Reprise composite refusée : $raw" }
    return $response.result
}

function Wait-TerminalState {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $lastPhase = ''
    $lastHeartbeat = [DateTime]::MinValue
    while ([DateTime]::UtcNow -lt $deadline) {
        $state = Get-CompositeState
        $phase = [string]$state.phase
        if ($phase -ne $lastPhase -or ([DateTime]::UtcNow - $lastHeartbeat).TotalSeconds -ge 15) {
                Write-Host "COMPOSITE_MESH_PROGRESS phase=$phase pass=$($state.completed_passes)/4 contacts=$($state.physical_contacts)/144 busy=$($state.busy)"
            $lastPhase = $phase
            $lastHeartbeat = [DateTime]::UtcNow
        }
        if (-not [bool]$state.busy -and @('qualified','failed','cancelled','interrupted') -contains $phase) { return $state }
        Start-Sleep -Seconds 5
    }
    [void](Invoke-Cancel)
    throw "Timeout composite après $TimeoutSeconds secondes ; annulation demandée."
}

function Assert-Qualified {
    $manifest = Assert-Installed
    $state = Get-CompositeState
    if ([string]$state.phase -cne 'qualified' -or [bool]$state.busy -or [int]$state.completed_passes -ne 4 -or
        [int]$state.physical_contacts -ne 144 -or -not [bool]$state.backup_available -or -not $state.qualification.accepted -or
        [int]$state.qualification.physical_contacts -ne 144 -or [int]$state.qualification.unique_physical_points -ne 121 -or
        [double]$state.qualification.overlap_mm.maximum_spread -gt 0.05 -or
        [string]$state.qualification.mesh_params.algo -cne 'bicubic') { throw 'Campagne composite non qualifiée.' }
    $matrix = @($state.candidate_matrix)
    if ($matrix.Count -ne 11) { throw 'Matrice finale sans onze lignes.' }
    foreach ($row in $matrix) { if (@($row).Count -ne 11) { throw 'Matrice finale sans onze colonnes.' } }
    $names = @($state.passes | ForEach-Object { $_.name }) -join ','
    if ($names -cne 'north_west,north_east,south_west,south_east') { throw 'Ordre des quatre passages inattendu.' }
    $status = Get-PrinterStatus
    Assert-SafePrinter $status $true
    $target = $status.bed_mesh.profiles.'k1_p001_t055_r001_n11x11'
    if (-not $target -or @($target.points).Count -ne 11) { throw 'Profil 11x11 persistant absent ou incomplet.' }
    if ((Get-RemoteSha256 $RemotePrinterConfig) -cne [string]$state.candidate_printer_cfg_sha256) { throw 'Hash printer.cfg différent de la qualification.' }
    $backupRoot = "$RemoteRoot/backups/composite-mesh-v1/$($state.campaign_id)"
    if ((Get-RemoteSha256 "$backupRoot/printer.cfg.before") -cne [string]$manifest.baseline.printer_cfg_sha256) { throw 'Backup printer.cfg de campagne inattendu.' }
    if ((Get-RemoteSha256 "$backupRoot/k1-control-z-state.json.before") -cne (Get-RemoteSha256 $RemoteZState)) { throw 'État Z modifié pendant la campagne.' }
    Save-Evidence 'composite-mesh-state.json' $state
    Save-Evidence 'final-printer-status.json' $status
    $backupLocal = Join-Path $LocalCapture 'printer.cfg.before'
    $currentLocal = Join-Path $LocalCapture 'printer.cfg.composite'
    Copy-FromRemote "$backupRoot/printer.cfg.before" $backupLocal
    Copy-FromRemote $RemotePrinterConfig $currentLocal
    if (-not (Get-Command python.exe -ErrorAction SilentlyContinue)) { throw 'python.exe local est requis pour la validation exacte.' }
    $validation = & python.exe $ArtifactValidator $backupLocal $currentLocal (Join-Path $LocalCapture 'composite-mesh-state.json') 2>&1
    if ($LASTEXITCODE -ne 0 -or ($validation -join "`n") -notmatch 'VALIDATE_COMPOSITE_MESH_ARTIFACTS_OK') { throw "Validation exacte des artefacts KO : $($validation -join "`n")" }
    $validation | Set-Content -LiteralPath (Join-Path $LocalCapture 'artifact-validation.json') -Encoding UTF8
    return @{ State=$state; Printer=$status }
}

if ($Action -eq 'Plan') {
    Write-Output "PLAN_RUN_COMPOSITE_MESH_V1_OK gate=$RequiredGate"
    Write-Output 'Run: PEI_TEXTURED_A, 55/140 C, 200 s, un nettoyage, un homing, quatre quadrants 6x6 carrés.'
    Write-Output 'Sortie: 144 contacts, 121 positions uniques, profil 11x11 bicubique persistant, chauffes zéro, profil robuste actif.'
    exit 0
}
if ($Action -eq 'Preflight') { [void](Assert-ReadyForStart); Write-Output 'PREFLIGHT_RUN_COMPOSITE_MESH_V1_OK'; exit 0 }
if ($Action -eq 'Validate') { [void](Assert-Qualified); Write-Output "VALIDATE_RUN_COMPOSITE_MESH_V1_OK capture=$CaptureId"; exit 0 }
if ($Action -eq 'Recover') {
    Assert-MutationGate $RecoveryGate
    $manifest = Assert-Installed
    $state = Get-CompositeState
    if ([string]$state.phase -cne 'failed' -or [bool]$state.busy -or
        [int]$state.completed_passes -ne 4 -or [int]$state.physical_contacts -ne 144 -or
        -not [bool]$state.backup_available -or [bool]$state.config_written) {
        throw 'Capture complète non récupérable.'
    }
    $status = Get-PrinterStatus
    Assert-SafePrinter $status $false
    if ((Get-RemoteSha256 $RemotePrinterConfig) -cne [string]$manifest.baseline.printer_cfg_sha256) {
        throw 'printer.cfg ne correspond plus à la capture physique.'
    }
    New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null
    Save-Evidence 'recovery-start-state.json' (Invoke-Recover)
    $terminal = Wait-TerminalState
    Save-Evidence 'recovery-terminal-state.json' $terminal
    if ([string]$terminal.phase -cne 'qualified') {
        throw "Reprise composite KO : phase=$($terminal.phase) erreur=$($terminal.last_error)"
    }
    [void](Assert-Qualified)
    Write-Output "RECOVER_COMPOSITE_MESH_V1_OK capture=$CaptureId"
    exit 0
}
if ($Action -eq 'Cancel') {
    Assert-MutationGate
    $state = Invoke-Cancel
    if ([bool]$state.busy) { $state = Wait-TerminalState }
    if (@('cancelled','interrupted') -notcontains [string]$state.phase) { throw "Annulation non close : phase=$($state.phase)" }
    $manifest = Assert-Installed
    $status = Get-PrinterStatus
    Assert-SafePrinter $status $false
    if ((Get-RemoteSha256 $RemotePrinterConfig) -cne [string]$manifest.baseline.printer_cfg_sha256) { throw 'Rollback de campagne incomplet.' }
    Write-Output "CANCEL_COMPOSITE_MESH_V1_OK phase=$($state.phase)"
    exit 0
}

Assert-MutationGate
[void](Assert-ReadyForStart)
New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null
$started = Invoke-Start
Save-Evidence 'start-state.json' $started
$terminal = Wait-TerminalState
Save-Evidence 'terminal-state.json' $terminal
if ([string]$terminal.phase -cne 'qualified') { throw "Campagne composite KO : phase=$($terminal.phase) erreur=$($terminal.last_error)" }
[void](Assert-Qualified)
Write-Output "RUN_COMPOSITE_MESH_V1_OK capture=$CaptureId"
