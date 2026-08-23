[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Run', 'Validate', 'Cancel')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-composite-mesh-subgrid-v1',
    [switch]$Execute,
    [string]$Gate = '',
    [int]$TimeoutSeconds = 1500
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-COMPOSITE-MESH-SUBGRID-V1'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\composite-subgrid-v1'
$ManifestPath = Join-Path $PackageRoot 'deployment-manifest.json'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteCurrent = "$RemoteRoot/current"
$RemoteConfig = "$RemoteCurrent/config/moonraker.conf"
$RemoteComponents = "$RemoteCurrent/moonraker/moonraker/moonraker/components"
$RemoteCore = "$RemoteComponents/k1_control_composite_subgrid_core.py"
$RemoteComponent = "$RemoteComponents/k1_control_composite_subgrid.py"
$RemotePrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$LocalCapture = Join-Path $WorkspaceRoot "inventory\raw\$CaptureId"

function Assert-MutationGate {
    if (-not $Execute -or $Gate -cne $RequiredGate) {
        throw "Action bloquée : -Execute et -Gate '$RequiredGate' sont obligatoires."
    }
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

function Get-RemoteSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    $line = Invoke-Remote "sha256sum '$Path'"
    return ((($line | Select-Object -First 1) -split '\s+')[0]).ToLowerInvariant()
}

function Get-CompositeState {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/composite_subgrid/status'") -join "`n"
    $state = ($raw | ConvertFrom-Json).result
    if (-not $state) { throw 'API composite sans état métier.' }
    return $state
}

function Get-UiState {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/status'") -join "`n"
    $state = ($raw | ConvertFrom-Json).result
    if (-not $state) { throw 'API K1 Control sans état métier.' }
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
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    foreach ($file in $manifest.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne [string]$file.sha256) {
            throw "Payload composite distant inattendu : $($file.destination)"
        }
    }
    foreach ($file in $manifest.unchanged.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne [string]$file.sha256) {
            throw "Fichier hors write-set inattendu : $($file.destination)"
        }
    }
    foreach ($module in $manifest.firmware_dependencies) {
        if ((Get-RemoteSha256 ([string]$module.path)) -cne [string]$module.sha256) {
            throw "Module firmware inattendu : $($module.path)"
        }
    }
    if ((Get-RemoteSha256 $RemotePrinterConfig) -cne [string]$manifest.baseline.printer_cfg_sha256) {
        throw 'printer.cfg ne correspond pas à la base revue.'
    }
    [void](Invoke-Remote "test -f '$RemoteCore' && test -f '$RemoteComponent' && test -f '$RemoteConfig'")
    return $manifest
}

function Assert-SafePrinter {
    param([Parameter(Mandatory = $true)]$Status)
    if ($Status.print_stats.state -cne 'standby' -or $Status.print_stats.filename) {
        throw "Imprimante non disponible : $($Status.print_stats.state)"
    }
    if ([double]$Status.extruder.target -ne 0 -or [double]$Status.heater_bed.target -ne 0) {
        throw 'Les chauffes ne sont pas coupées.'
    }
    $runtime = $Status.'gcode_macro KCTRL_STATE'
    $store = $Status.k1_control_store
    $path = $Status.'gcode_macro KCTRL_CAL_PATH_STATE'
    if ([int]$runtime.ready -ne 1 -or [int]$runtime.accepted_z_valid -ne 1 -or
        [int]$runtime.session_active -ne 0 -or [int]$runtime.low_moves_armed -ne 0 -or
        -not $store -or $store.integrity -cne 'ok') {
        throw 'Runtime ou stockage Z non sûr.'
    }
    if (@('idle', 'committed', 'cancelled') -notcontains [string]$path.phase -or
        [int]$path.motion_armed -ne 0 -or [int]$path.commit_ready -ne 0) {
        throw 'Chemin Z non fermé.'
    }
    $profiles = @($Status.bed_mesh.profiles.PSObject.Properties.Name)
    if ($profiles -notcontains 'k1_p001_t055_r001_n06x06' -or
        $profiles -contains 'K1_TRANSIENT' -or
        $profiles -contains 'K1_COMPOSITE_ODD_ODD_05X05') {
        throw 'Profils bed_mesh non sûrs.'
    }
    $count = @($Status.configfile.settings.bed_mesh.probe_count)
    if ($count.Count -ne 2 -or [int]$count[0] -ne 6 -or [int]$count[1] -ne 6 -or
        [string]$Status.configfile.settings.bed_mesh.algorithm -cne 'lagrange') {
        throw 'Configuration bed_mesh différente de 6x6 Lagrange.'
    }
    foreach ($unit in @('T1', 'T2')) {
        if ([string]$Status.box.$unit.state -cne 'connect') {
            throw "CFS $unit non connecté."
        }
    }
}

function Assert-ReadyForStart {
    [void](Assert-Installed)
    $ui = Get-UiState
    if ([bool]$ui.busy -or @('idle', 'accepted', 'cancelled', 'rolled_back') -notcontains [string]$ui.phase) {
        throw "Campagne UI non fermée : phase=$($ui.phase)"
    }
    $composite = Get-CompositeState
    if ([string]$composite.phase -cne 'idle' -or [bool]$composite.busy -or
        [bool]$composite.backup_available -or $composite.matrix) {
        throw "État composite non neuf : phase=$($composite.phase)"
    }
    $status = Get-PrinterStatus
    Assert-SafePrinter $status
    return @{ Ui = $ui; Composite = $composite; Printer = $status }
}

function Save-Evidence {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Value
    )
    New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null
    $path = Join-Path $LocalCapture $Name
    $Value | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $path -Encoding utf8
}

function Invoke-Start {
    $url = "http://127.0.0.1:7125/machine/k1_control/composite_subgrid/start?gate=$RequiredGate&plate_clear=true"
    $raw = (Invoke-Remote "curl -X POST '$url'") -join "`n"
    $response = $raw | ConvertFrom-Json
    if (-not $response.result) { throw "Démarrage composite refusé : $raw" }
    return $response.result
}

function Invoke-Cancel {
    $url = 'http://127.0.0.1:7125/machine/k1_control/composite_subgrid/cancel'
    $raw = (Invoke-Remote "curl -X POST '$url'") -join "`n"
    $response = $raw | ConvertFrom-Json
    if (-not $response.result) { throw "Annulation composite refusée : $raw" }
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
            Write-Output "COMPOSITE_SUBGRID_PROGRESS phase=$phase busy=$($state.busy)"
            $lastPhase = $phase
            $lastHeartbeat = [DateTime]::UtcNow
        }
        if (-not [bool]$state.busy -and @('qualified', 'failed', 'cancelled', 'interrupted') -contains $phase) {
            return $state
        }
        Start-Sleep -Seconds 5
    }
    [void](Invoke-Cancel)
    throw "Timeout composite après $TimeoutSeconds secondes ; annulation demandée."
}

function Assert-Qualified {
    $manifest = Assert-Installed
    $state = Get-CompositeState
    if ([string]$state.phase -cne 'qualified' -or [bool]$state.busy -or
        -not [bool]$state.backup_available -or [int]$state.physical_contacts -ne 25) {
        throw "Sous-grille non qualifiée : phase=$($state.phase) busy=$($state.busy)"
    }
    $matrix = @($state.matrix)
    if ($matrix.Count -ne 5) { throw 'Matrice composite sans cinq lignes.' }
    foreach ($row in $matrix) {
        if (@($row).Count -ne 5) { throw 'Matrice composite sans cinq colonnes.' }
        foreach ($value in @($row)) {
            if ([double]::IsNaN([double]$value) -or [double]::IsInfinity([double]$value)) {
                throw 'Matrice composite non finie.'
            }
        }
    }
    if ([int]$state.context.klipper_restart_count -ne 0 -or
        (@($state.context.x_indices) -join ',') -cne '1,3,5,7,9' -or
        (@($state.context.y_indices) -join ',') -cne '1,3,5,7,9') {
        throw 'Contexte physique de sous-grille inattendu.'
    }
    $status = Get-PrinterStatus
    Assert-SafePrinter $status
    if ([string]$status.bed_mesh.profile_name -cne 'k1_p001_t055_r001_n06x06') {
        throw "Le profil robuste 6x6 n'est pas actif après la gate."
    }
    if ([string]$status.toolhead.homed_axes) {
        throw "Le restart de nettoyage n'a pas libéré les axes."
    }
    if ((Get-RemoteSha256 $RemotePrinterConfig) -cne [string]$manifest.baseline.printer_cfg_sha256) {
        throw 'printer.cfg a changé pendant la sous-grille.'
    }
    Save-Evidence 'composite-subgrid-state.json' $state
    Save-Evidence 'final-printer-status.json' $status
    return @{ State = $state; Printer = $status }
}

if ($Action -eq 'Plan') {
    Write-Output "PLAN_RUN_COMPOSITE_SUBGRID_V1_OK gate=$RequiredGate"
    Write-Output 'Run: PEI_TEXTURED_A, 55/140 C, 200 s, nettoyage, homing, une sous-grille 5x5 décalée.'
    Write-Output 'Sortie: 25 contacts capturés, chauffes zéro, profil robuste 6x6 actif, aucun profil composite persisté.'
    exit 0
}

if ($Action -eq 'Preflight') {
    [void](Assert-ReadyForStart)
    Write-Output 'PREFLIGHT_RUN_COMPOSITE_SUBGRID_V1_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    [void](Assert-Qualified)
    Write-Output "VALIDATE_RUN_COMPOSITE_SUBGRID_V1_OK capture=$CaptureId"
    exit 0
}

if ($Action -eq 'Cancel') {
    Assert-MutationGate
    $state = Invoke-Cancel
    Write-Output "CANCEL_COMPOSITE_SUBGRID_V1_OK phase=$($state.phase)"
    exit 0
}

Assert-MutationGate
[void](Assert-ReadyForStart)
New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null
$started = Invoke-Start
Save-Evidence 'start-state.json' $started
$terminal = Wait-TerminalState
Save-Evidence 'terminal-state.json' $terminal
if ([string]$terminal.phase -cne 'qualified') {
    throw "Sous-grille composite KO : phase=$($terminal.phase) erreur=$($terminal.last_error)"
}
[void](Assert-Qualified)
Write-Output "RUN_COMPOSITE_SUBGRID_V1_OK capture=$CaptureId"
