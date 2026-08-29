[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',

    [string]$Gate,

    [ValidatePattern('^[0-9]{8}-[0-9]{6}-g4-k1-control-start-sequence-owner-safety-r2$')]
    [string]$CaptureId,

    [string]$EvidenceDirectory,

    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'PowerShell 7 ou plus recent est obligatoire.'
}

$RequiredGate = 'G4-K1-CONTROL-START-SEQUENCE-OWNER-SAFETY-R2'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\start-sequence-owner-safety-r2'
$V1PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\start-sequence-owner-v1'
$LocalConfig = Join-Path $PackageRoot 'k1-control-start-sequence-owner-safety-r2.cfg'
$RemoteAdmin = Join-Path $V1PackageRoot 'remote_admin.py'
$RemoteJinja = Join-Path $V1PackageRoot 'remote_jinja_validate.py'

$ExpectedOldConfigHash = '25291e1534f0ba100d3171b983796089a24cd49fdfcef76817406d325e6d8e03'
$ExpectedNewConfigHash = '678582e808d74f6b720ef3d6b52dc2c443c7a0652a62c484319e2b22fba7b0bc'
$ExpectedRemoteAdminHash = 'e81b3810f675f9a3b8985ee6feedb04a8aea12a64e636ee56f7916c0d8943d52'
$ExpectedRemoteJinjaHash = 'b372d4d57602ad68cca801ee46c7b385e6ad3af5deb48f467c3a1625fd5cc0a4'
$ExpectedPrinterHash = 'a79c8c917d8eee2575939ade4907640c2b2cf7ff59283d28def895b020e127af'
$ExpectedBoxHash = 'e7a6b26df58a9fa8e49d3af6845f5a0937a790c8ef494b96ec72fd7392abc7a7'
$ExpectedGcodeMacroHash = '864fedde88fbb345c220ae5658f7b04779b3981bd78d68eda6fa63c59c79a04f'
$ExpectedRuntimeConfigHash = 'dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113'
$ExpectedCalibrationPathHash = '825aadac8679e0d0e9be140cc5ba4e7656b2bff0d197d1683a73d2b5be4e364e'
$ExpectedRuntimeModuleHash = '696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede'

$PrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$BoxConfig = '/usr/data/printer_data/config/box.cfg'
$GcodeMacroConfig = '/usr/data/printer_data/config/gcode_macro.cfg'
$RuntimeConfig = '/usr/data/printer_data/config/k1-control-z-mesh.cfg'
$CalibrationPathConfig = '/usr/data/printer_data/config/k1-control-calibration-path.cfg'
$RuntimeModule = '/usr/share/klipper/klippy/extras/k1_control_store.py'
$StartOwnerConfig = '/usr/data/printer_data/config/k1-control-start-sequence-owner-v1.cfg'
$RemoteRoot = '/usr/data/k1-control-v1'
$KlipperSocket = '/tmp/klippy_uds'
$MutationStarted = $false

$SshArguments = @(
    '-o', 'BatchMode=yes',
    '-o', 'PasswordAuthentication=no',
    '-o', 'KbdInteractiveAuthentication=no',
    '-o', 'ConnectTimeout=8',
    'k1max-root'
)

function Assert-ExactGate {
    if (-not $Execute -or $Gate -cne $RequiredGate) {
        throw "Action bloquee : -Execute et -Gate '$RequiredGate' sont obligatoires."
    }
}

function Assert-LocalPathInsideWorkspace {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
    if (-not $resolved.StartsWith(
            $WorkspaceRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase
        )) {
        throw "Chemin local hors workspace : $resolved"
    }
    return $resolved
}

function Assert-LocalPins {
    $pins = [ordered]@{
        $LocalConfig = $ExpectedNewConfigHash
        $RemoteAdmin = $ExpectedRemoteAdminHash
        $RemoteJinja = $ExpectedRemoteJinjaHash
    }
    foreach ($entry in $pins.GetEnumerator()) {
        $hash = (Get-FileHash -LiteralPath $entry.Key -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hash -ne $entry.Value) {
            throw "Fichier local non fige : $($entry.Key) hash=$hash attendu=$($entry.Value)"
        }
    }
}

function Invoke-Remote {
    param([Parameter(Mandatory = $true)][string]$Command)

    $output = & ssh.exe @SshArguments $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Commande distante KO ($LASTEXITCODE) : $Command`n$($output -join "`n")"
    }
    return @($output)
}

function Invoke-RemoteTest {
    param([Parameter(Mandatory = $true)][string]$Command)

    & ssh.exe @SshArguments $Command *> $null
    return $LASTEXITCODE -eq 0
}

function Invoke-RemoteStdin {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string]$StandardInput
    )

    $output = $StandardInput | & ssh.exe @SshArguments $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Commande distante stdin KO ($LASTEXITCODE) : $Command`n$($output -join "`n")"
    }
    return @($output)
}

function Invoke-RemoteAdmin {
    param([Parameter(Mandatory = $true)][ValidateSet('generation', 'snapshot', 'restart', 'restore_mesh', 'selftest', 'reset')][string]$AdminAction)

    $program = [IO.File]::ReadAllText($RemoteAdmin).Replace("`r`n", "`n")
    $output = Invoke-RemoteStdin "/usr/share/klippy-env/bin/python -B - '$AdminAction'" $program
    if ($AdminAction -eq 'restart') { return $output }
    return (($output -join "`n") | ConvertFrom-Json)
}

function Save-Evidence {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Value
    )

    if (-not $EvidenceDirectory) { return }
    $resolved = Assert-LocalPathInsideWorkspace $EvidenceDirectory
    $path = Join-Path $resolved $Name
    if ($Value -is [string]) {
        $Value | Set-Content -LiteralPath $path -Encoding utf8
    }
    else {
        $Value | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $path -Encoding utf8
    }
}

function Get-RemoteHash {
    param([Parameter(Mandatory = $true)][string]$Path)

    return (((Invoke-Remote "sha256sum '$Path'" | Select-Object -First 1) -split '\s+')[0]).Trim()
}

function Assert-ExactRemoteJinjaSyntax {
    $configText = [IO.File]::ReadAllText($LocalConfig).Replace("`r`n", "`n")
    $configPayload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($configText))
    $program = [IO.File]::ReadAllText($RemoteJinja).Replace('__CONFIG_BASE64__', $configPayload).Replace("`r`n", "`n")
    $output = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $program
    $joined = $output -join "`n"
    if ($joined -notmatch '^REMOTE_START_OWNER_JINJA_PARSE_OK sections=13$') {
        throw "Validation Jinja exacte distante absente : $joined"
    }
    Save-Evidence 'preflight-jinja.txt' $joined
}

function Assert-ImmutableHashes {
    if ((Get-RemoteHash $PrinterConfig) -ne $ExpectedPrinterHash -or
        (Get-RemoteHash $BoxConfig) -ne $ExpectedBoxHash -or
        (Get-RemoteHash $GcodeMacroConfig) -ne $ExpectedGcodeMacroHash -or
        (Get-RemoteHash $RuntimeConfig) -ne $ExpectedRuntimeConfigHash -or
        (Get-RemoteHash $CalibrationPathConfig) -ne $ExpectedCalibrationPathHash -or
        (Get-RemoteHash $RuntimeModule) -ne $ExpectedRuntimeModuleHash) {
        throw 'Une configuration revue a derive.'
    }
}

function Get-RouteCount {
    param([Parameter(Mandatory = $true)]$Box)

    $count = 0
    foreach ($unitName in @('T1', 'T2', 'T3', 'T4')) {
        $unit = $Box.units.$unitName
        if ($unit -and [string]$unit.filament -match '^[ABCD]$') { $count++ }
    }
    return $count
}

function Assert-SafeSnapshot {
    param([Parameter(Mandatory = $true)]$Snapshot)

    if ($Snapshot.webhooks.state -ne 'ready' -or $Snapshot.print_state -ne 'standby') {
        throw 'Klipper non pret ou imprimante non standby.'
    }
    if ([double]$Snapshot.extruder.target -ne 0.0 -or [double]$Snapshot.heater_bed.target -ne 0.0) {
        throw 'Les cibles thermiques ne sont pas nulles.'
    }
    if ([string]$Snapshot.toolhead.homed_axes -ne '') { throw 'Les axes doivent etre liberes.' }
    if ($Snapshot.mesh_profile -ne 'k1_p001_t055_r001_n11x11') { throw 'Le mesh 11 x 11 n est pas actif.' }
    if ([int]$Snapshot.runtime.ready -ne 1 -or [int]$Snapshot.runtime.accepted_z_valid -ne 1 -or
        [math]::Abs([double]$Snapshot.runtime.accepted_z_offset - (-0.04)) -gt 0.0005 -or
        [int]$Snapshot.runtime.session_active -ne 0 -or [int]$Snapshot.runtime.low_moves_armed -ne 0) {
        throw 'Runtime Z/mesh different de l etat final attendu.'
    }
    if ($Snapshot.store.integrity -ne 'ok') { throw 'Stockage Z accepte non integre.' }
    if ($Snapshot.box.state -ne 'connect' -or [string]$Snapshot.box.t_command -ne '' -or
        $Snapshot.box.units.T1.state -ne 'connect' -or $Snapshot.box.units.T2.state -ne 'connect') {
        throw 'Etat CFS non stable.'
    }
    $routeCount = Get-RouteCount $Snapshot.box
    if ($routeCount -gt 1 -or ($routeCount -eq 1 -and [string]$Snapshot.box.units.T1.filament -ne 'A')) {
        throw 'La route CFS est multiple ou differente de T1A.'
    }
    if (-not [bool]$Snapshot.object_requirements.start_owner_loaded -or
        -not [bool]$Snapshot.object_requirements.watchdog_loaded) {
        throw 'Le proprietaire ou son surveillant n est pas charge.'
    }
    $owner = $Snapshot.start_owner
    if (-not $owner -or [int]$owner.manual_clean_token -ne 0 -or [int]$owner.watchdog_armed -ne 0 -or
        [double]$owner.manual_clean_deadline -ne 0.0 -or [double]$owner.watchdog_deadline -ne 0.0 -or
        $owner.phase -notin @('idle', 'watchdog_aborted')) {
        throw 'Etat du proprietaire non ferme.'
    }
    if ([double]$Snapshot.bounds.stepper_x.position_min -gt 0.1 -or
        [double]$Snapshot.bounds.stepper_x.position_max -lt 0.4 -or
        [double]$Snapshot.bounds.stepper_y.position_min -gt 10.0 -or
        [double]$Snapshot.bounds.stepper_y.position_max -lt 180.0 -or
        [double]$Snapshot.bounds.stepper_z.position_min -gt 0.3 -or
        [double]$Snapshot.bounds.stepper_z.position_max -lt 5.0) {
        throw 'La purge R2 sort des courses observees.'
    }
}

function Wait-RestartCompleted {
    param([Parameter(Mandatory = $true)]$PreviousGeneration, [int]$Attempts = 60)

    $transitionObserved = $false
    $lastError = 'transition non observee'
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $generation = Invoke-RemoteAdmin 'generation'
            if ([string]$generation.socket_inode -ne [string]$PreviousGeneration.socket_inode -or
                [string]$generation.socket_mtime_ns -ne [string]$PreviousGeneration.socket_mtime_ns) {
                $transitionObserved = $true
            }
            $snapshot = Invoke-RemoteAdmin 'snapshot'
            if ($transitionObserved -and $snapshot.webhooks.state -eq 'ready' -and $snapshot.print_state -eq 'standby') {
                return $snapshot
            }
            $lastError = "transition=$transitionObserved state=$($snapshot.webhooks.state)"
        }
        catch {
            $transitionObserved = $true
            $lastError = $_.Exception.Message
        }
        if ($attempt -lt $Attempts) { Start-Sleep -Seconds 1 }
    }
    throw "Restart Klipper non confirme : $lastError"
}

function Invoke-RestartAndRestoreMesh {
    $generation = Invoke-RemoteAdmin 'generation'
    Invoke-RemoteAdmin 'restart' | Out-Null
    Wait-RestartCompleted -PreviousGeneration $generation | Out-Null
    Invoke-RemoteAdmin 'restore_mesh' | Out-Null
    for ($attempt = 1; $attempt -le 10; $attempt++) {
        $snapshot = Invoke-RemoteAdmin 'snapshot'
        if ($snapshot.mesh_profile -eq 'k1_p001_t055_r001_n11x11') { return $snapshot }
        if ($attempt -lt 10) { Start-Sleep -Seconds 1 }
    }
    throw 'Le mesh 11 x 11 n est pas revenu apres sa commande unique.'
}

function Assert-InstalledState {
    param([Parameter(Mandatory = $true)][string]$ExpectedConfigHash)

    Assert-ImmutableHashes
    if ((Get-RemoteHash $StartOwnerConfig) -ne $ExpectedConfigHash) {
        throw 'Empreinte distante du proprietaire inattendue.'
    }
    $snapshot = Invoke-RemoteAdmin 'snapshot'
    Assert-SafeSnapshot $snapshot
    return $snapshot
}

function Invoke-Preflight {
    Assert-LocalPins
    foreach ($tool in @('base64', 'chmod', 'cp', 'cut', 'mkdir', 'mv', 'rm', 'sha256sum', 'sync')) {
        if (-not (Invoke-RemoteTest "command -v '$tool'")) { throw "Outil distant absent : $tool" }
    }
    if (-not (Invoke-RemoteTest "test -S '$KlipperSocket'")) { throw 'Socket Klipper absent.' }
    foreach ($path in @("$StartOwnerConfig.next", "$StartOwnerConfig.rollback-next")) {
        if (Invoke-RemoteTest "test -e '$path'") { throw "Transitoire distant present : $path" }
    }
    Assert-ImmutableHashes
    if ((Get-RemoteHash $StartOwnerConfig) -ne $ExpectedOldConfigHash) {
        throw 'La version V1 exacte n est pas installee avant R2.'
    }
    Assert-ExactRemoteJinjaSyntax
    $snapshot = Invoke-RemoteAdmin 'snapshot'
    Assert-SafeSnapshot $snapshot
    $routeCount = Get-RouteCount $snapshot.box
    Save-Evidence 'preflight-safe.json' $snapshot
    Save-Evidence 'preflight-hashes.txt' "printer_cfg=$ExpectedPrinterHash`nold_start_owner=$ExpectedOldConfigHash`nnew_start_owner=$ExpectedNewConfigHash"
    return [pscustomobject]@{
        status = 'PREFLIGHT_START_SEQUENCE_OWNER_SAFETY_R2_OK'
        old_config_sha256 = $ExpectedOldConfigHash
        new_config_sha256 = $ExpectedNewConfigHash
        route = $(if ($routeCount -eq 1) { 'T1A' } else { 'NONE' })
        route_count = $routeCount
        active_mesh = $snapshot.mesh_profile
        accepted_z_offset_mm = [double]$snapshot.runtime.accepted_z_offset
        remote_write = $false
        service_action = $false
        heat = $false
        motion = $false
        extrusion = $false
    }
}

function Invoke-ColdValidation {
    Assert-LocalPins
    $before = Assert-InstalledState $ExpectedNewConfigHash
    Invoke-RemoteAdmin 'selftest' | Out-Null
    Start-Sleep -Seconds 3
    $aborted = Invoke-RemoteAdmin 'snapshot'
    if ($aborted.start_owner.phase -ne 'watchdog_aborted' -or [int]$aborted.start_owner.watchdog_armed -ne 0) {
        throw 'Le self-test froid du surveillant ne s est pas ferme.'
    }
    Invoke-RemoteAdmin 'reset' | Out-Null
    $final = Assert-InstalledState $ExpectedNewConfigHash
    foreach ($field in @('position', 'homed_axes')) {
        if (($before.toolhead.$field | ConvertTo-Json -Compress) -ne ($final.toolhead.$field | ConvertTo-Json -Compress)) {
            throw "Etat physique change pendant le self-test : toolhead.$field"
        }
    }
    Save-Evidence 'validation-before.json' $before
    Save-Evidence 'validation-watchdog-aborted.json' $aborted
    Save-Evidence 'validation-final.json' $final
    return $final
}

function Invoke-Rollback {
    param([switch]$BestEffort)

    if (-not $CaptureId) { throw 'Rollback exige -CaptureId.' }
    $backup = "$RemoteRoot/backups/$CaptureId/start-sequence-owner-safety-r2"
    try {
        foreach ($command in @(
                "test -f '$backup/k1-control-start-sequence-owner-v1.cfg.before'",
                "test -f '$backup/checksums.sha256'",
                "cd '$backup' && sha256sum -c checksums.sha256",
                "cp '$backup/k1-control-start-sequence-owner-v1.cfg.before' '$StartOwnerConfig.rollback-next'",
                "test `"`$(sha256sum '$StartOwnerConfig.rollback-next' | cut -d ' ' -f 1)`" = '$ExpectedOldConfigHash'",
                "mv '$StartOwnerConfig.rollback-next' '$StartOwnerConfig'",
                "rm -f '$StartOwnerConfig.next'",
                'sync'
            )) {
            Invoke-Remote $command | Out-Null
        }
        Invoke-RestartAndRestoreMesh | Out-Null
        $snapshot = Assert-InstalledState $ExpectedOldConfigHash
        Save-Evidence 'rollback-final.json' $snapshot
    }
    catch { if (-not $BestEffort) { throw } }
}

if ($Action -eq 'Plan') {
    Assert-LocalPins
    [pscustomobject]@{
        status = 'PLAN_ONLY'
        gate = $RequiredGate
        remote_file_replaced = $StartOwnerConfig
        old_config_sha256 = $ExpectedOldConfigHash
        new_config_sha256 = $ExpectedNewConfigHash
        printer_cfg_unchanged = $true
        restart = 'Klipper host RESTART only, with real socket transition'
        post_restart = 'load k1_p001_t055_r001_n11x11 once and read it back'
        rollback = 'restore exact V1 file, restart, restore mesh, validate safe state'
        physical_trial_started = $false
    } | ConvertTo-Json -Depth 6
    exit 0
}

Assert-ExactGate
if ($EvidenceDirectory) { [void](Assert-LocalPathInsideWorkspace $EvidenceDirectory) }

if ($Action -eq 'Preflight') {
    Invoke-Preflight | ConvertTo-Json -Depth 8
    exit 0
}

if ($Action -eq 'Deploy') {
    if (-not $CaptureId -or -not $EvidenceDirectory) { throw 'Deploy exige -CaptureId et -EvidenceDirectory.' }
    Invoke-Preflight | Out-Null
    $backup = "$RemoteRoot/backups/$CaptureId/start-sequence-owner-safety-r2"
    $staging = "$RemoteRoot/staging/$CaptureId/start-sequence-owner-safety-r2"
    try {
        Invoke-Remote "test ! -e '$backup' && mkdir -p '$backup' '$staging'" | Out-Null
        & scp.exe -O -q -o BatchMode=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no `
            $LocalConfig "k1max-root`:$staging/k1-control-start-sequence-owner-safety-r2.cfg"
        if ($LASTEXITCODE -ne 0) { throw 'Transfert du candidat R2 KO.' }
        if ((Get-RemoteHash "$staging/k1-control-start-sequence-owner-safety-r2.cfg") -ne $ExpectedNewConfigHash) {
            throw 'Candidat R2 distant different.'
        }
        Invoke-Remote "cp '$StartOwnerConfig' '$backup/k1-control-start-sequence-owner-v1.cfg.before'" | Out-Null
        if ((Get-RemoteHash "$backup/k1-control-start-sequence-owner-v1.cfg.before") -ne $ExpectedOldConfigHash) {
            throw 'Backup V1 different.'
        }
        $checksum = "$ExpectedOldConfigHash  k1-control-start-sequence-owner-v1.cfg.before"
        $payload = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$checksum`n"))
        Invoke-Remote "echo '$payload' | base64 -d > '$backup/checksums.sha256'" | Out-Null
        Invoke-Remote "cd '$backup' && sha256sum -c checksums.sha256" | Out-Null
        Save-Evidence 'remote-backup-sha256.txt' $checksum
        $MutationStarted = $true
        Invoke-Remote "cp '$staging/k1-control-start-sequence-owner-safety-r2.cfg' '$StartOwnerConfig.next' && chmod 600 '$StartOwnerConfig.next' && mv '$StartOwnerConfig.next' '$StartOwnerConfig' && sync" | Out-Null
        Invoke-RestartAndRestoreMesh | Out-Null
        Invoke-ColdValidation | Out-Null
        Write-Output "DEPLOY_START_SEQUENCE_OWNER_SAFETY_R2_OK capture=$CaptureId"
    }
    catch {
        $deploymentError = $_
        if ($MutationStarted) {
            try { Invoke-Rollback }
            catch { throw "Deploiement KO et rollback KO. Initial : $deploymentError`nRollback : $_" }
        }
        throw $deploymentError
    }
    exit 0
}

if ($Action -eq 'Validate') {
    Invoke-ColdValidation | Out-Null
    Write-Output 'VALIDATE_START_SEQUENCE_OWNER_SAFETY_R2_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Invoke-Rollback
    Write-Output "ROLLBACK_START_SEQUENCE_OWNER_SAFETY_R2_OK capture=$CaptureId"
    exit 0
}
