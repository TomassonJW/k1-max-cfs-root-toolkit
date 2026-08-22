[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'CaptureLevel', 'Validate')]
    [string]$Action = 'Plan',

    [ValidateSet('standard', 'precise', 'expert', 'quick')]
    [string]$Level,

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
$RetryPackage = Join-Path $WorkspaceRoot 'packages\k1-control-v1\calibration-ui-retry-safety-v1'
$RetryManifestPath = Join-Path $RetryPackage 'deployment-manifest.json'
$CampaignContractPath = Join-Path $WorkspaceRoot 'packages\k1-control-v1\calibration-ui-campaign-v1\calibration-ui-campaign-contract.json'
$ExpectedUiManifestHash = '8970109289fb64645de22d6530c32c397738509ede0983a5e6362f1c4feae7db'
$ExpectedRetryManifestHash = '6c50d95bd542a59284a67291ade4a216ae53b125fc4cd5a0521bc726cf0c7c0f'
$ExpectedCampaignContractHash = '768d257c4b6c0f114edbdf7f8172920c1bf593646dc06e3bcf490b6fbfa457ae'
$RemoteUi = '/usr/data/k1-control-v1/current/www/mainsail/k1-control'
$RemoteState = '/usr/data/k1-control-v1/state/k1-control-calibration-workflow.json'
$MeshProfiles = @(
    'k1_p001_t055_r001_n06x06',
    'k1_p001_t055_r001_n09x09',
    'k1_p001_t055_r001_n11x11',
    'k1_p001_t055_r001_n15x15'
)

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
    if ((Get-LocalSha256 $RetryManifestPath) -cne $ExpectedRetryManifestHash) {
        throw 'Manifeste de sécurité de reprise différent de la version revue.'
    }
    $manifest = Get-Content -LiteralPath $UiManifestPath -Raw | ConvertFrom-Json
    $retryManifest = Get-Content -LiteralPath $RetryManifestPath -Raw | ConvertFrom-Json
    $contract = Get-Content -LiteralPath $CampaignContractPath -Raw | ConvertFrom-Json
    if ($manifest.contract_id -cne 'G4-K1-CONTROL-CALIBRATION-UI-MATRIX-V1' -or
        $retryManifest.contract_id -cne 'G4-K1-CONTROL-CALIBRATION-UI-RETRY-SAFETY-V1' -or
        $contract.contract_id -cne 'G4-K1-CONTROL-CALIBRATION-UI-CAMPAIGN-V1') {
        throw 'Identité du paquet UI ou de la campagne inattendue.'
    }
    foreach ($file in $manifest.files) {
        $local = Join-Path $UiPackage ([string]$file.source)
        if ((Get-LocalSha256 $local) -cne ([string]$file.sha256)) {
            throw "Payload UI local non revu : $($file.source)"
        }
    }
    $retrySource = Join-Path $RetryPackage ([string]$retryManifest.file.source)
    if ((Get-LocalSha256 $retrySource) -cne ([string]$retryManifest.file.sha256)) {
        throw 'Payload de sécurité de reprise local non revu.'
    }
    return @{ Manifest = $manifest; RetryManifest = $retryManifest; Contract = $contract }
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
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [Parameter(Mandatory = $true)]$RetryManifest
    )
    foreach ($file in $Manifest.files) {
        if ([string]$file.destination -ceq [string]$RetryManifest.file.destination) { continue }
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne ([string]$file.sha256)) {
            throw "Payload UI distant inattendu : $($file.destination)"
        }
    }
    if ((Get-RemoteSha256 ([string]$RetryManifest.file.destination)) -cne ([string]$RetryManifest.file.sha256)) {
        throw 'Correctif distant de sécurité de reprise inattendu.'
    }
    foreach ($file in $Manifest.unchanged.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne ([string]$file.sha256)) {
            throw "Payload UI hors write-set inattendu : $($file.destination)"
        }
    }
    foreach ($file in $RetryManifest.unchanged.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne ([string]$file.sha256)) {
            throw "Payload hors write-set RETRY-SAFETY inattendu : $($file.destination)"
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
    param(
        [Parameter(Mandatory = $true)]$Snapshot,
        [switch]$RequireCommittedPath
    )
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
    $closedPathPhases = @('idle', 'committed', 'cancelled')
    if ($closedPathPhases -notcontains [string]$path.phase -or
        [int]$path.motion_armed -ne 0 -or [int]$path.commit_ready -ne 0) {
        throw 'Chemin Z non fermé.'
    }
    if ($RequireCommittedPath -and $path.phase -cne 'committed') {
        throw 'Le parcours Z final ne se termine pas en phase committed.'
    }
    if ($Snapshot.bed_mesh.profiles.PSObject.Properties.Name -contains 'K1_TRANSIENT') {
        throw 'Un profil mesh transitoire est encore présent.'
    }
    Assert-Cfs $Snapshot
}

function Assert-ExactCampaignConfig {
    param(
        [Parameter(Mandatory = $true)]$ApiState,
        [Parameter(Mandatory = $true)]$Expected
    )
    $config = $ApiState.config
    if (-not $config -or [int]$config.plate_id -ne 1 -or $config.plate_label -cne 'PEI_TEXTURED_A' -or
        [int]$config.bed_temp_c -ne 55 -or [int]$config.nozzle_temp_c -ne 140 -or
        [int]$config.soak_seconds -ne 200 -or [int]$config.x_count -ne [int]$Expected.matrix[0] -or
        [int]$config.y_count -ne [int]$Expected.matrix[1] -or $config.algorithm -cne [string]$Expected.interpolation -or
        [math]::Abs([double]$config.seed_offset_mm - (-0.04)) -gt 0.000001 -or
        [bool]$config.replace_existing -ne [bool]$Expected.replace_existing) {
        throw 'Paramètres de campagne différents du contrat revu.'
    }
}

function Assert-ExpectedProfiles {
    param(
        [Parameter(Mandatory = $true)]$Snapshot,
        [Parameter(Mandatory = $true)][string[]]$ExpectedProfiles,
        [string[]]$AbsentProfiles = @()
    )
    $names = @($Snapshot.bed_mesh.profiles.PSObject.Properties.Name)
    foreach ($profile in $ExpectedProfiles) {
        if ($names -notcontains $profile) { throw "Profil qualifié absent : $profile" }
    }
    foreach ($profile in $AbsentProfiles) {
        if ($names -contains $profile) { throw "Profil supérieur déjà présent avant campagne : $profile" }
    }
    if ($names -contains 'K1_TRANSIENT') { throw 'Profil transitoire encore présent.' }
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
        common_settings = $reviewed.Contract.common_operator_settings
        sequence = $reviewed.Contract.physical_sequence
        measurements_per_level = 6
        total_measurements = 24
        automatic_rerun = $false
        printer_contact = $false
    } | ConvertTo-Json -Depth 8
    exit 0
}

[void](Assert-EvidenceDirectory)
Assert-InstalledUi $reviewed.Manifest $reviewed.RetryManifest
$api = Get-ApiState
$snapshot = Get-PrinterSnapshot

if ($Action -eq 'Preflight') {
    $freshIdle = $api.phase -ceq 'idle' -and -not [bool]$api.busy -and
        -not [bool]$api.backup_available
    $cancelledBeforeFirstMesh = $api.phase -ceq 'cancelled' -and
        -not [bool]$api.busy -and [int]$api.mesh_index -eq 0 -and
        [bool]$api.backup_available
    $exactRollback = $api.phase -ceq 'rolled_back' -and
        -not [bool]$api.busy -and [bool]$api.backup_available -and
        $api.rollback -and [string]$api.rollback.printer_cfg_sha256
    if (-not $freshIdle -and -not $cancelledBeforeFirstMesh -and -not $exactRollback) {
        throw "État UI initial inattendu : $($api.phase)"
    }
    Assert-SafeAcceptedMachine $snapshot -RequireCommittedPath
    Assert-ExpectedProfiles $snapshot @($MeshProfiles[0]) @($MeshProfiles[1..3])
    Save-Evidence 'preflight-api.json' $api
    Save-Evidence 'preflight-printer.json' $snapshot
    Write-Output "PREFLIGHT_CALIBRATION_UI_CAMPAIGN_V1_OK capture=$CaptureId"
    exit 0
}

if ($Action -eq 'CaptureLevel') {
    if (-not $Level) { throw 'CaptureLevel exige -Level.' }
    $expected = @($reviewed.Contract.physical_sequence | Where-Object { $_.name -ceq $Level })
    if ($expected.Count -ne 1) { throw "Niveau non revu : $Level" }
    $expected = $expected[0]
    $expectedPhase = if ($Level -ceq 'quick') { 'accepted' } else { 'cancelled' }
    if ($api.phase -cne $expectedPhase -or [bool]$api.busy -or [int]$api.mesh_index -ne 6 -or
        -not [bool]$api.backup_available) {
        throw "Niveau $Level incomplet : phase=$($api.phase) mesh=$($api.mesh_index)"
    }
    if ($Level -ceq 'quick' -and [int64]$api.accepted_at -le 0) {
        throw 'Le parcours rapide ne contient pas une acceptation Z finale.'
    }
    Assert-ExactCampaignConfig $api $expected
    Assert-Qualification $api
    $privateState = Get-PrivateCampaignState
    if (@($privateState.meshes).Count -ne 6 -or $privateState.phase -cne $expectedPhase) {
        throw "État privé incomplet pour le niveau $Level."
    }
    Assert-SafeAcceptedMachine $snapshot -RequireCommittedPath:($Level -ceq 'quick')
    Assert-ExpectedProfiles $snapshot @([string]$expected.expected_profile)
    Save-Evidence "level-$Level-api.json" $api
    Save-Evidence "level-$Level-private.json" $privateState
    Save-Evidence "level-$Level-printer.json" $snapshot
    Write-Output "CAPTURE_CALIBRATION_UI_LEVEL_OK level=$Level capture=$CaptureId"
    exit 0
}

if ($api.phase -cne 'accepted' -or [bool]$api.busy -or [int]$api.mesh_index -ne 6 -or
    -not [bool]$api.backup_available -or [int64]$api.accepted_at -le 0) {
    throw "Campagne UI finale non acceptée : phase=$($api.phase) mesh=$($api.mesh_index)"
}
$quick = @($reviewed.Contract.physical_sequence | Where-Object { $_.name -ceq 'quick' })[0]
Assert-ExactCampaignConfig $api $quick
Assert-Qualification $api
$privateState = Get-PrivateCampaignState
if (@($privateState.meshes).Count -ne 6 -or $privateState.phase -cne 'accepted') {
    throw 'État privé différent des six mesures acceptées.'
}
Assert-SafeAcceptedMachine $snapshot -RequireCommittedPath
Assert-ExpectedProfiles $snapshot $MeshProfiles
$evidenceRoot = Assert-EvidenceDirectory
foreach ($name in @('standard', 'precise', 'expert', 'quick')) {
    foreach ($suffix in @('api', 'private', 'printer')) {
        if (-not (Test-Path -LiteralPath (Join-Path $evidenceRoot "level-$name-$suffix.json"))) {
            throw "Capture de niveau manquante : $name/$suffix"
        }
    }
}
Save-Evidence 'validate-api.json' $api
Save-Evidence 'validate-private-campaign.json' $privateState
Save-Evidence 'validate-printer.json' $snapshot
Write-Output "VALIDATE_CALIBRATION_UI_CAMPAIGN_V1_OK capture=$CaptureId"
