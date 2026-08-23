[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'CaptureLevel', 'Validate')]
    [string]$Action = 'Plan',

    [ValidateSet('supported')]
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
$BedMeshPackage = Join-Path $WorkspaceRoot 'packages\k1-control-v1\calibration-ui-prtouch-bed-mesh-v2'
$BedMeshManifestPath = Join-Path $BedMeshPackage 'deployment-manifest.json'
$PresetPackage = Join-Path $WorkspaceRoot 'packages\k1-control-v1\calibration-ui-prtouch-presets-v1'
$PresetManifestPath = Join-Path $PresetPackage 'deployment-manifest.json'
$CampaignContractPath = Join-Path $WorkspaceRoot 'packages\k1-control-v1\calibration-ui-campaign-v1\calibration-ui-campaign-contract.json'
$ExpectedUiManifestHash = 'e43de6a5f34e35b0f375c22d0dcceaa09cc9eec063d8bfbe4b0869baae139149'
$ExpectedRetryManifestHash = '37bdc87ff20d283e862505b70678afe4790845a517d1a191a8fc4565b570cbc8'
$ExpectedBedMeshManifestHash = '3357113e8b7da06fceeb6c2053197e6f9410fec58abc85e851c2984e196d7dec'
$ExpectedPresetManifestHash = '332b4edc8047e38c9abf5af00df572abb089d5dbc7e352af876e78da41bc1dc3'
$ExpectedCampaignContractHash = 'd566fb9735fa2a3ca9f26c73dc0b848dd67ed69c9042719def6ca742afd29b13'
$RemoteUi = '/usr/data/k1-control-v1/current/www/mainsail/k1-control'
$RemoteState = '/usr/data/k1-control-v1/state/k1-control-calibration-workflow.json'
$MeshProfiles = @('k1_p001_t055_r001_n06x06')

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
    if ((Get-LocalSha256 $BedMeshManifestPath) -cne $ExpectedBedMeshManifestHash) {
        throw 'Manifeste adaptateur bed_mesh V2 différent de la version revue.'
    }
    if ((Get-LocalSha256 $PresetManifestPath) -cne $ExpectedPresetManifestHash) {
        throw 'Manifeste des choix prtouch différent de la version revue.'
    }
    $manifest = Get-Content -LiteralPath $UiManifestPath -Raw | ConvertFrom-Json
    $retryManifest = Get-Content -LiteralPath $RetryManifestPath -Raw | ConvertFrom-Json
    $bedMeshManifest = Get-Content -LiteralPath $BedMeshManifestPath -Raw | ConvertFrom-Json
    $presetManifest = Get-Content -LiteralPath $PresetManifestPath -Raw | ConvertFrom-Json
    $contract = Get-Content -LiteralPath $CampaignContractPath -Raw | ConvertFrom-Json
    if ($manifest.contract_id -cne 'G4-K1-CONTROL-CALIBRATION-UI-MATRIX-V1' -or
        $retryManifest.contract_id -cne 'G4-K1-CONTROL-CALIBRATION-UI-RETRY-SAFETY-V1' -or
        $bedMeshManifest.contract_id -cne 'G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-BED-MESH-V2' -or
        $presetManifest.contract_id -cne 'G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-PRESETS-V1' -or
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
    foreach ($file in $bedMeshManifest.files) {
        $local = Join-Path $BedMeshPackage ([string]$file.source)
        if ((Get-LocalSha256 $local) -cne ([string]$file.sha256)) {
            throw "Payload adaptateur bed_mesh V2 local non revu : $($file.source)"
        }
    }
    foreach ($file in $presetManifest.files) {
        $local = Join-Path $PresetPackage ([string]$file.source)
        if ((Get-LocalSha256 $local) -cne ([string]$file.sha256)) {
            throw "Payload des choix prtouch local non revu : $($file.source)"
        }
    }
    return @{
        Manifest = $manifest
        RetryManifest = $retryManifest
        BedMeshManifest = $bedMeshManifest
        PresetManifest = $presetManifest
        Contract = $contract
    }
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
        [Parameter(Mandatory = $true)]$RetryManifest,
        [Parameter(Mandatory = $true)]$BedMeshManifest,
        [Parameter(Mandatory = $true)]$PresetManifest
    )
    $bedMeshDestinations = @(
        @($BedMeshManifest.files) + @($BedMeshManifest.unchanged.files) |
            ForEach-Object { [string]$_.destination }
    )
    $presetDestinations = @($PresetManifest.files | ForEach-Object { [string]$_.destination })
    $supersededDestinations = @($bedMeshDestinations + $presetDestinations)
    foreach ($file in $Manifest.files) {
        if ([string]$file.destination -ceq [string]$RetryManifest.file.destination -or
            $presetDestinations -ccontains [string]$file.destination) { continue }
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne ([string]$file.sha256)) {
            throw "Payload UI distant inattendu : $($file.destination)"
        }
    }
    if ($presetDestinations -notcontains [string]$RetryManifest.file.destination -and
        (Get-RemoteSha256 ([string]$RetryManifest.file.destination)) -cne ([string]$RetryManifest.file.sha256)) {
        throw 'Correctif distant de sécurité de reprise inattendu.'
    }
    foreach ($file in $Manifest.unchanged.files) {
        if ($supersededDestinations -ccontains [string]$file.destination) { continue }
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne ([string]$file.sha256)) {
            throw "Payload UI hors write-set inattendu : $($file.destination)"
        }
    }
    foreach ($file in $RetryManifest.unchanged.files) {
        if ($supersededDestinations -ccontains [string]$file.destination) { continue }
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne ([string]$file.sha256)) {
            throw "Payload hors write-set RETRY-SAFETY inattendu : $($file.destination)"
        }
    }
    foreach ($file in @($BedMeshManifest.files) + @($BedMeshManifest.unchanged.files)) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne ([string]$file.sha256)) {
            throw "Payload adaptateur bed_mesh V2 distant inattendu : $($file.destination)"
        }
    }
    foreach ($file in $PresetManifest.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne ([string]$file.sha256)) {
            throw "Payload des choix prtouch distant inattendu : $($file.destination)"
        }
    }
    $serverInfoRaw = (Invoke-Remote "curl 'http://127.0.0.1:7125/server/info'") -join "`n"
    $serverInfo = ($serverInfoRaw | ConvertFrom-Json).result
    if (-not $serverInfo -or @($serverInfo.components) -notcontains 'k1_control_probe_count' -or
        @($serverInfo.failed_components) -contains 'k1_control_probe_count') {
        throw "L'adaptateur bed_mesh V2 n'est pas chargé proprement : $(@($serverInfo.warnings) -join ' | ')"
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
    if ($qualification.method -cne 'single_firmware_bounded_mesh') {
        throw 'La méthode de calibration normale n est pas celle revue.'
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
        measurements_per_level = 1
        total_measurements = 1
        automatic_rerun = $false
        printer_contact = $false
    } | ConvertTo-Json -Depth 8
    exit 0
}

[void](Assert-EvidenceDirectory)
Assert-InstalledUi $reviewed.Manifest $reviewed.RetryManifest $reviewed.BedMeshManifest $reviewed.PresetManifest
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
    # Un rollback redémarre Klipper : le store Z accepté reste persistant, tandis
    # que le petit automate de mouvement revient normalement en phase idle.
    Assert-SafeAcceptedMachine $snapshot
    Assert-ExpectedProfiles $snapshot $MeshProfiles
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
    $expectedPhase = 'accepted'
    if ($api.phase -cne $expectedPhase -or [bool]$api.busy -or [int]$api.mesh_index -ne 1 -or
        -not [bool]$api.backup_available) {
        throw "Niveau $Level incomplet : phase=$($api.phase) mesh=$($api.mesh_index)"
    }
    if ([int64]$api.accepted_at -le 0) {
        throw 'Le parcours ne contient pas une acceptation Z finale.'
    }
    Assert-ExactCampaignConfig $api $expected
    Assert-Qualification $api
    $privateState = Get-PrivateCampaignState
    if (@($privateState.meshes).Count -ne 1 -or $privateState.phase -cne $expectedPhase) {
        throw "État privé incomplet pour le niveau $Level."
    }
    Assert-SafeAcceptedMachine $snapshot -RequireCommittedPath
    Assert-ExpectedProfiles $snapshot @([string]$expected.expected_profile)
    Save-Evidence "level-$Level-api.json" $api
    Save-Evidence "level-$Level-private.json" $privateState
    Save-Evidence "level-$Level-printer.json" $snapshot
    Write-Output "CAPTURE_CALIBRATION_UI_LEVEL_OK level=$Level capture=$CaptureId"
    exit 0
}

if ($api.phase -cne 'accepted' -or [bool]$api.busy -or [int]$api.mesh_index -ne 1 -or
    -not [bool]$api.backup_available -or [int64]$api.accepted_at -le 0) {
    throw "Campagne UI finale non acceptée : phase=$($api.phase) mesh=$($api.mesh_index)"
}
$supported = @($reviewed.Contract.physical_sequence | Where-Object { $_.name -ceq 'supported' })[0]
Assert-ExactCampaignConfig $api $supported
Assert-Qualification $api
$privateState = Get-PrivateCampaignState
if (@($privateState.meshes).Count -ne 1 -or $privateState.phase -cne 'accepted') {
    throw 'État privé différent de la mesure acceptée.'
}
Assert-SafeAcceptedMachine $snapshot -RequireCommittedPath
Assert-ExpectedProfiles $snapshot $MeshProfiles
$evidenceRoot = Assert-EvidenceDirectory
foreach ($name in @('supported')) {
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
