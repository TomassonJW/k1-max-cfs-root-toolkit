[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Validate')]
    [string]$Action = 'Plan',

    [ValidatePattern('^[0-9]{8}-[0-9]{6}-g4-k1-control-calibration-ui-campaign-v1$')]
    [string]$CaptureId,

    [string]$EvidenceDirectory,

    [string]$PrinterHost = 'k1max-root'
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'PowerShell 7 ou plus récent est obligatoire.'
}

$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$UiPackage = Join-Path $WorkspaceRoot 'packages\k1-control-v1\calibration-ui-matrix-v1'
$UiManifestPath = Join-Path $UiPackage 'deployment-manifest.json'
$CampaignContractPath = Join-Path $WorkspaceRoot 'packages\k1-control-v1\calibration-ui-campaign-v1\calibration-ui-campaign-contract.json'
$ExpectedUiManifestHash = '8970109289fb64645de22d6530c32c397738509ede0983a5e6362f1c4feae7db'
$ExpectedCampaignContractHash = '9fe0a251925b62d7d7a7c59724d1d752d43b4213a5bb7289fe9105242cde5713'
$RemoteUi = '/usr/data/k1-control-v1/current/www/mainsail/k1-control'
$RemoteState = '/usr/data/k1-control-v1/state/k1-control-calibration-workflow.json'
$MeshProfile = 'k1_p001_t055_r001_n06x06'

$SshArguments = @(
    '-o', 'BatchMode=yes',
    '-o', 'PasswordAuthentication=no',
    '-o', 'KbdInteractiveAuthentication=no',
    '-o', 'ConnectTimeout=8',
    $PrinterHost
)

function Get-LocalSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Invoke-Remote {
    param([Parameter(Mandatory = $true)][string]$Command)
    $output = & ssh.exe @SshArguments $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Commande distante en lecture seule KO : $Command`n$($output -join "`n")"
    }
    return @($output)
}

function Get-RemoteSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    $line = Invoke-Remote "sha256sum '$Path'"
    return ((($line | Select-Object -First 1) -split '\s+')[0]).ToLowerInvariant()
}

function Assert-ReviewedLocalFiles {
    if ((Get-LocalSha256 $UiManifestPath) -cne $ExpectedUiManifestHash) {
        throw 'Manifeste UI local différent de la version revue.'
    }
    if ((Get-LocalSha256 $CampaignContractPath) -cne $ExpectedCampaignContractHash) {
        throw 'Contrat de campagne local différent de la version revue.'
    }
    $manifest = Get-Content -LiteralPath $UiManifestPath -Raw | ConvertFrom-Json
    $contract = Get-Content -LiteralPath $CampaignContractPath -Raw | ConvertFrom-Json
    if ($manifest.contract_id -cne 'G4-K1-CONTROL-CALIBRATION-UI-MATRIX-V1' -or
        $contract.contract_id -cne 'G4-K1-CONTROL-CALIBRATION-UI-CAMPAIGN-V1') {
        throw 'Identité du paquet UI ou de la campagne inattendue.'
    }
    foreach ($file in $manifest.files) {
        $local = Join-Path $UiPackage ([string]$file.source)
        if ((Get-LocalSha256 $local) -cne ([string]$file.sha256)) {
            throw "Payload UI local non revu : $($file.source)"
        }
    }
    return @{ Manifest = $manifest; Contract = $contract }
}

function Assert-EvidenceDirectory {
    if (-not $CaptureId -or -not $EvidenceDirectory) {
        throw 'Preflight et Validate exigent -CaptureId et -EvidenceDirectory.'
    }
    $resolved = (Resolve-Path -LiteralPath $EvidenceDirectory -ErrorAction Stop).Path
    $expected = Join-Path $WorkspaceRoot "inventory\raw\$CaptureId"
    if (-not $resolved.Equals($expected, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Dossier de preuve inattendu : $resolved"
    }
    & git check-ignore -q -- $resolved
    if ($LASTEXITCODE -ne 0) {
        throw 'Le dossier de preuve privé ne serait pas ignoré par Git.'
    }
    return $resolved
}

function Save-Evidence {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Value
    )
    $root = Assert-EvidenceDirectory
    $path = Join-Path $root $Name
    if ($Value -is [string]) {
        $Value | Set-Content -LiteralPath $path -Encoding utf8
    }
    else {
        $Value | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $path -Encoding utf8
    }
}

function Assert-InstalledUi {
    param([Parameter(Mandatory = $true)]$Manifest)
    foreach ($file in $Manifest.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne ([string]$file.sha256)) {
            throw "Payload UI distant inattendu : $($file.destination)"
        }
    }
    foreach ($file in $Manifest.unchanged.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne ([string]$file.sha256)) {
            throw "Payload UI hors write-set inattendu : $($file.destination)"
        }
    }
    $mode = ((Invoke-Remote "stat -c '%a' '$RemoteUi'") | Select-Object -First 1).Trim()
    if ($mode -cne '755') {
        throw "Droits du dossier UI inattendus : $mode"
    }
}

function Get-ApiState {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/status'") -join "`n"
    $payload = $raw | ConvertFrom-Json
    if (-not $payload.result) {
        throw 'API K1 Control sans résultat métier.'
    }
    return $payload.result
}

function Get-PrivateCampaignState {
    $raw = (Invoke-Remote "cat '$RemoteState'") -join "`n"
    return ($raw | ConvertFrom-Json)
}

function Get-PrinterSnapshot {
    $url = "http://127.0.0.1:7125/printer/objects/query?print_stats&extruder&heater_bed&bed_mesh&box&gcode_macro+KCTRL_STATE&k1_control_store&gcode_macro+KCTRL_CAL_PATH_STATE"
    $raw = (Invoke-Remote "curl '$url'") -join "`n"
    $payload = $raw | ConvertFrom-Json
    if (-not $payload.result.status) {
        throw 'Réponse Moonraker sans état Klipper.'
    }
    return $payload.result.status
}

function Assert-Cfs {
    param([Parameter(Mandatory = $true)]$Snapshot)
    foreach ($name in @('T1', 'T2')) {
        $unit = $Snapshot.box.$name
        if (-not $unit -or $unit.state -cne 'connect' -or @($unit.material_type).Count -ne 4) {
            throw "CFS $name inattendu ou déconnecté."
        }
    }
}

function Assert-SafeAcceptedMachine {
    param([Parameter(Mandatory = $true)]$Snapshot)
    if ($Snapshot.print_stats.state -cne 'standby' -or $Snapshot.print_stats.filename) {
        throw "Imprimante non disponible : $($Snapshot.print_stats.state)"
    }
    if ([double]$Snapshot.extruder.target -ne 0 -or [double]$Snapshot.heater_bed.target -ne 0) {
        throw 'Les chauffes ne sont pas coupées.'
    }
    $runtime = $Snapshot.'gcode_macro KCTRL_STATE'
    $store = $Snapshot.k1_control_store
    $path = $Snapshot.'gcode_macro KCTRL_CAL_PATH_STATE'
    if ([int]$runtime.ready -ne 1 -or [int]$runtime.accepted_z_valid -ne 1 -or
        [int]$runtime.session_active -ne 0 -or [int]$runtime.low_moves_armed -ne 0 -or
        [int]$runtime.plate_id -ne 1 -or [int]$runtime.temperature_band_c -ne 55 -or
        [int]$runtime.probe_revision -ne 1 -or [int]$runtime.nozzle_id -ne 1 -or
        [int]$runtime.config_id -ne 1) {
        throw 'Runtime Z accepté incomplet ou contexte inattendu.'
    }
    if (-not $store -or $store.integrity -cne 'ok' -or [int]$store.record[1] -ne 1) {
        throw 'Stockage Z accepté invalide.'
    }
    if ($path.phase -cne 'committed' -or [int]$path.motion_armed -ne 0 -or
        [int]$path.commit_ready -ne 0) {
        throw 'Chemin Z non fermé après acceptation.'
    }
    if ($Snapshot.bed_mesh.profiles.PSObject.Properties.Name -notcontains $MeshProfile -or
        $Snapshot.bed_mesh.profiles.PSObject.Properties.Name -contains 'K1_TRANSIENT') {
        throw 'Profil mesh robuste absent ou transitoire encore présent.'
    }
    Assert-Cfs $Snapshot
}

function Assert-ExactCampaignConfig {
    param([Parameter(Mandatory = $true)]$ApiState)
    $config = $ApiState.config
    if (-not $config -or [int]$config.plate_id -ne 1 -or $config.plate_label -cne 'PEI_TEXTURED_A' -or
        [int]$config.bed_temp_c -ne 55 -or [int]$config.nozzle_temp_c -ne 140 -or
        [int]$config.soak_seconds -ne 200 -or [int]$config.x_count -ne 6 -or
        [int]$config.y_count -ne 6 -or $config.algorithm -cne 'lagrange' -or
        [math]::Abs([double]$config.seed_offset_mm - (-0.04)) -gt 0.000001 -or
        -not [bool]$config.replace_existing) {
        throw 'Paramètres de campagne différents du contrat revu.'
    }
}

function Assert-Qualification {
    param([Parameter(Mandatory = $true)]$ApiState)
    $qualification = $ApiState.qualification
    if (-not $qualification -or -not [bool]$qualification.accepted) {
        throw 'Qualification mesh absente ou refusée.'
    }
    if ([double]$qualification.observed_mm.mean_absolute -gt 0.020 -or
        [double]$qualification.observed_mm.rms -gt 0.025 -or
        [double]$qualification.observed_mm.maximum -gt 0.060) {
        throw 'Une métrique mesh dépasse sa limite revue.'
    }
}

$reviewed = Assert-ReviewedLocalFiles
if ($Action -eq 'Plan') {
    [pscustomobject]@{
        status = 'PLAN_CALIBRATION_UI_CAMPAIGN_V1_OK'
        gate = 'G4-K1-CONTROL-CALIBRATION-UI-CAMPAIGN-V1'
        control = 'browser_only_by_operator'
        settings = $reviewed.Contract.operator_settings
        measurements = 6
        automatic_rerun = $false
        printer_contact = $false
    } | ConvertTo-Json -Depth 8
    exit 0
}

[void](Assert-EvidenceDirectory)
Assert-InstalledUi $reviewed.Manifest
$api = Get-ApiState
$snapshot = Get-PrinterSnapshot

if ($Action -eq 'Preflight') {
    if ($api.phase -cne 'idle' -or [bool]$api.busy -or [bool]$api.backup_available) {
        throw "État UI initial inattendu : $($api.phase)"
    }
    Assert-SafeAcceptedMachine $snapshot
    Save-Evidence 'preflight-api.json' $api
    Save-Evidence 'preflight-printer.json' $snapshot
    Write-Output "PREFLIGHT_CALIBRATION_UI_CAMPAIGN_V1_OK capture=$CaptureId"
    exit 0
}

if ($api.phase -cne 'accepted' -or [bool]$api.busy -or [int]$api.mesh_index -ne 6 -or
    -not [bool]$api.backup_available -or [int64]$api.accepted_at -le 0) {
    throw "Campagne UI non acceptée ou incomplète : phase=$($api.phase) mesh=$($api.mesh_index)"
}
Assert-ExactCampaignConfig $api
Assert-Qualification $api
$privateState = Get-PrivateCampaignState
if (@($privateState.meshes).Count -ne 6 -or $privateState.phase -cne 'accepted') {
    throw 'État privé différent des six mesures acceptées.'
}
Assert-SafeAcceptedMachine $snapshot
Save-Evidence 'validate-api.json' $api
Save-Evidence 'validate-private-campaign.json' $privateState
Save-Evidence 'validate-printer.json' $snapshot
Write-Output "VALIDATE_CALIBRATION_UI_CAMPAIGN_V1_OK capture=$CaptureId"
