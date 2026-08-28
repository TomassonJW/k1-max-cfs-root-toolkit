[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',

    [string]$Gate,

    [ValidatePattern('^[0-9]{8}-[0-9]{6}-g4-k1-control-start-sequence-owner-v1$')]
    [string]$CaptureId,

    [string]$EvidenceDirectory,

    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'PowerShell 7 ou plus recent est obligatoire.'
}

$RequiredGate = 'G4-K1-CONTROL-START-SEQUENCE-OWNER-V1'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\start-sequence-owner-v1'
$LocalConfig = Join-Path $PackageRoot 'k1-control-start-sequence-owner-v1.cfg'
$RemoteAdmin = Join-Path $PackageRoot 'remote_admin.py'
$RemoteJinja = Join-Path $PackageRoot 'remote_jinja_validate.py'

$ExpectedConfigHash = '25291e1534f0ba100d3171b983796089a24cd49fdfcef76817406d325e6d8e03'
$ExpectedRemoteAdminHash = 'e81b3810f675f9a3b8985ee6feedb04a8aea12a64e636ee56f7916c0d8943d52'
$ExpectedRemoteJinjaHash = 'b372d4d57602ad68cca801ee46c7b385e6ad3af5deb48f467c3a1625fd5cc0a4'
$ExpectedPrinterHash = 'f88d6b52477592805384fca2b4d7abd00298deecd82227af2fa580085fe26fa2'
$ExpectedNextPrinterHash = 'a79c8c917d8eee2575939ade4907640c2b2cf7ff59283d28def895b020e127af'
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
        $LocalConfig = $ExpectedConfigHash
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
    param([Parameter(Mandatory = $true)][ValidateSet('objects', 'generation', 'snapshot', 'restart', 'restore_mesh', 'selftest', 'reset')][string]$AdminAction)

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

function Get-ExactRemoteLineCount {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Line
    )

    $program = '$0 == "' + $Line + '" {count++} END {print count+0}'
    return [int]((Invoke-Remote "awk '$program' '$Path'" | Select-Object -First 1).Trim())
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
    param(
        [Parameter(Mandatory = $true)]$Snapshot,
        [switch]$ExpectInstalled
    )

    if ($Snapshot.webhooks.state -ne 'ready' -or $Snapshot.print_state -ne 'standby') {
        throw 'Klipper non pret ou imprimante non standby.'
    }
    if ([double]$Snapshot.extruder.target -ne 0.0 -or [double]$Snapshot.heater_bed.target -ne 0.0) {
        throw 'Les cibles thermiques ne sont pas nulles.'
    }
    if ([string]$Snapshot.toolhead.homed_axes -ne '') { throw 'Les axes doivent etre liberes pour cette pose.' }
    if ($Snapshot.mesh_profile -ne 'k1_p001_t055_r001_n11x11') { throw 'Le meilleur mesh actuel n est pas actif.' }
    $runtime = $Snapshot.runtime
    if ([int]$runtime.ready -ne 1 -or [int]$runtime.accepted_z_valid -ne 1 -or
        [math]::Abs([double]$runtime.accepted_z_offset - (-0.04)) -gt 0.0005 -or
        [int]$runtime.session_active -ne 0 -or [int]$runtime.low_moves_armed -notin @(0, 1)) {
        throw 'Runtime Z/mesh different du contexte accepte.'
    }
    if ([int]$runtime.low_moves_armed -eq 1 -and [string]$runtime.armed_mesh_profile -ne 'k1_p001_t055_r001_n11x11') {
        throw 'Runtime arme sur un autre profil que le meilleur mesh courant.'
    }
    if ($Snapshot.store.integrity -ne 'ok') { throw 'Stockage Z accepte non integre.' }
    $box = $Snapshot.box
    if ($box.state -ne 'connect' -or [string]$box.t_command -ne '' -or
        $box.units.T1.state -ne 'connect' -or $box.units.T2.state -ne 'connect') {
        throw 'Etat CFS non stable.'
    }
    $routeCount = Get-RouteCount $box
    if ($routeCount -gt 1) { throw 'Plusieurs routes CFS engagees.' }
    if ($routeCount -eq 1 -and [string]$box.units.T1.filament -ne 'A') {
        throw 'La seule route acceptee par V1 est T1A.'
    }
    foreach ($required in @('mcu', 'virtual_sdcard', 'accurate_g28', 'kctrl_production_arm', 'kctrl_production_assert_armed')) {
        if (-not [bool]$Snapshot.object_requirements.$required) { throw "Objet Klipper requis absent : $required" }
    }
    if ($ExpectInstalled) {
        if (-not [bool]$Snapshot.object_requirements.start_owner_loaded -or -not [bool]$Snapshot.object_requirements.watchdog_loaded) {
            throw 'Start owner ou watchdog non charge.'
        }
        $owner = $Snapshot.start_owner
        if (-not $owner -or [int]$owner.manual_clean_token -ne 0 -or [int]$owner.watchdog_armed -ne 0 -or
            [double]$owner.manual_clean_deadline -ne 0.0 -or [double]$owner.watchdog_deadline -ne 0.0 -or
            $owner.phase -notin @('idle', 'watchdog_aborted')) {
            throw 'Etat initial du start owner non ferme.'
        }
    }
    else {
        if ([bool]$Snapshot.object_requirements.start_owner_loaded -or [bool]$Snapshot.object_requirements.watchdog_loaded) {
            throw 'Le start owner est deja charge avant pose.'
        }
    }
    $bounds = $Snapshot.bounds
    if ([double]$bounds.stepper_x.position_min -gt 15.0 -or [double]$bounds.stepper_x.position_max -lt 15.0 -or
        [double]$bounds.stepper_y.position_min -gt 20.0 -or [double]$bounds.stepper_y.position_max -lt 180.0 -or
        [double]$bounds.stepper_z.position_min -gt 0.3 -or [double]$bounds.stepper_z.position_max -lt 5.0) {
        throw 'La ligne de purge proposee sort des courses K1 observees.'
    }
}

function Assert-ImmutableDependencyHashes {
    if ((Get-RemoteHash $BoxConfig) -ne $ExpectedBoxHash -or
        (Get-RemoteHash $GcodeMacroConfig) -ne $ExpectedGcodeMacroHash -or
        (Get-RemoteHash $RuntimeConfig) -ne $ExpectedRuntimeConfigHash -or
        (Get-RemoteHash $CalibrationPathConfig) -ne $ExpectedCalibrationPathHash -or
        (Get-RemoteHash $RuntimeModule) -ne $ExpectedRuntimeModuleHash) {
        throw 'Une dependance K1 revue a derive.'
    }
}

function Get-ProspectivePrinterHash {
    $awkProgram = '{print; if ($0 == "[include k1-control-calibration-path.cfg]") {print "[include k1-control-start-sequence-owner-v1.cfg]"; count++}} END {if (count != 1) exit 42}'
    return ((Invoke-Remote "awk '$awkProgram' '$PrinterConfig' | sha256sum | cut -d ' ' -f 1" | Select-Object -First 1).Trim())
}

function Invoke-StartOwnerPreflight {
    Assert-LocalPins
    foreach ($tool in @('awk', 'base64', 'chmod', 'cp', 'cut', 'grep', 'mkdir', 'mv', 'rm', 'sha256sum', 'sync')) {
        if (-not (Invoke-RemoteTest "command -v '$tool'")) { throw "Outil distant absent : $tool" }
    }
    if (-not (Invoke-RemoteTest "test -S '$KlipperSocket'")) { throw 'Socket Klipper absent.' }
    foreach ($path in @($StartOwnerConfig, "$StartOwnerConfig.next", "$PrinterConfig.next", "$PrinterConfig.rollback-next", "$PrinterConfig.rollback-final")) {
        if (Invoke-RemoteTest "test -e '$path'") { throw "Cible ou transitoire deja present : $path" }
    }
    if ((Get-RemoteHash $PrinterConfig) -ne $ExpectedPrinterHash) { throw 'printer.cfg different de la base revue.' }
    Assert-ImmutableDependencyHashes
    if ((Get-ExactRemoteLineCount $PrinterConfig '[include k1-control-z-mesh.cfg]') -ne 1 -or
        (Get-ExactRemoteLineCount $PrinterConfig '[include k1-control-calibration-path.cfg]') -ne 1 -or
        (Get-ExactRemoteLineCount $PrinterConfig '[include k1-control-start-sequence-owner-v1.cfg]') -ne 0) {
        throw 'Graphe d include inattendu avant pose.'
    }
    Assert-ExactRemoteJinjaSyntax
    $snapshot = Invoke-RemoteAdmin 'snapshot'
    Assert-SafeSnapshot $snapshot
    $prospective = Get-ProspectivePrinterHash
    Save-Evidence 'preflight-safe.json' $snapshot
    Save-Evidence 'preflight-prospective-printer-sha256.txt' $prospective
    Save-Evidence 'preflight-hashes.txt' "printer_cfg=$ExpectedPrinterHash`nprospective_printer_cfg=$prospective`nstart_owner_cfg=$ExpectedConfigHash"
    return [pscustomobject]@{
        status = 'PREFLIGHT_START_SEQUENCE_OWNER_V1_OK'
        prospective_printer_sha256 = $prospective
        route_count = Get-RouteCount $snapshot.box
        physical_trial_precondition_T1A = ([string]$snapshot.box.units.T1.filament -eq 'A')
        accepted_z_offset_mm = [double]$snapshot.runtime.accepted_z_offset
        active_mesh = $snapshot.mesh_profile
        prime_line_inside_live_bounds = $true
        remote_write = $false
        service_action = $false
        heat = $false
        motion = $false
        extrusion = $false
    }
}

function Wait-StartOwnerSnapshot {
    param([switch]$ExpectInstalled, [int]$Attempts = 60)

    $lastError = 'snapshot not available'
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $snapshot = Invoke-RemoteAdmin 'snapshot'
            Assert-SafeSnapshot $snapshot -ExpectInstalled:$ExpectInstalled
            return $snapshot
        }
        catch { $lastError = $_.Exception.Message }
        if ($attempt -lt $Attempts) { Start-Sleep -Seconds 1 }
    }
    throw "Etat Klipper non stabilise : $lastError"
}

function Wait-KlipperAdminReady {
    param([int]$Attempts = 60)

    $lastError = 'snapshot not available'
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $snapshot = Invoke-RemoteAdmin 'snapshot'
            if ($snapshot.webhooks.state -eq 'ready' -and $snapshot.print_state -eq 'standby') {
                return $snapshot
            }
            $lastError = "state=$($snapshot.webhooks.state) print=$($snapshot.print_state)"
        }
        catch { $lastError = $_.Exception.Message }
        if ($attempt -lt $Attempts) { Start-Sleep -Seconds 1 }
    }
    throw "Socket Klipper non stabilise apres restart : $lastError"
}

function Wait-KlipperRestartCompleted {
    param(
        [Parameter(Mandatory = $true)]$PreviousGeneration,
        [int]$Attempts = 60
    )

    $transitionObserved = $false
    $lastError = 'restart transition not observed'
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
            $lastError = "transition=$transitionObserved state=$($snapshot.webhooks.state) print=$($snapshot.print_state)"
        }
        catch {
            $transitionObserved = $true
            $lastError = $_.Exception.Message
        }
        if ($attempt -lt $Attempts) { Start-Sleep -Seconds 1 }
    }
    throw "Restart Klipper non confirme : $lastError"
}

function Invoke-KlipperRestartAndWait {
    [void](Wait-KlipperAdminReady -Attempts 60)
    $generation = Invoke-RemoteAdmin 'generation'
    Invoke-RemoteAdmin 'restart' | Out-Null
    return Wait-KlipperRestartCompleted -PreviousGeneration $generation -Attempts 60
}

function Restore-BestCurrentMeshAfterRestart {
    Invoke-RemoteAdmin 'restore_mesh' | Out-Null
    $lastProfile = 'unknown'
    for ($attempt = 1; $attempt -le 10; $attempt++) {
        $snapshot = Invoke-RemoteAdmin 'snapshot'
        $lastProfile = [string]$snapshot.mesh_profile
        if ($lastProfile -eq 'k1_p001_t055_r001_n11x11') {
            return $snapshot
        }
        if ($attempt -lt 10) { Start-Sleep -Seconds 1 }
    }
    throw "Le meilleur mesh courant n est pas actif apres sa commande unique : $lastProfile"
}

function Assert-InstalledHashes {
    if ((Get-RemoteHash $PrinterConfig) -ne $ExpectedNextPrinterHash -or
        (Get-RemoteHash $StartOwnerConfig) -ne $ExpectedConfigHash) {
        throw 'Empreinte du start owner installe inattendue.'
    }
    Assert-ImmutableDependencyHashes
    if ((Get-ExactRemoteLineCount $PrinterConfig '[include k1-control-z-mesh.cfg]') -ne 1 -or
        (Get-ExactRemoteLineCount $PrinterConfig '[include k1-control-calibration-path.cfg]') -ne 1 -or
        (Get-ExactRemoteLineCount $PrinterConfig '[include k1-control-start-sequence-owner-v1.cfg]') -ne 1) {
        throw 'Graphe d include inattendu apres pose.'
    }
}

function Assert-NoPhysicalChange {
    param(
        [Parameter(Mandatory = $true)]$Before,
        [Parameter(Mandatory = $true)]$After
    )

    foreach ($field in @('toolhead.position', 'toolhead.homed_axes', 'homing_origin', 'mesh_profile', 'runtime.accepted_z_offset')) {
        $left = $Before
        $right = $After
        foreach ($segment in $field.Split('.')) {
            $left = $left.$segment
            $right = $right.$segment
        }
        if (($left | ConvertTo-Json -Compress) -ne ($right | ConvertTo-Json -Compress)) {
            throw "Etat physique change pendant la validation : $field"
        }
    }
    if ([double]$After.extruder.target -ne 0.0 -or [double]$After.heater_bed.target -ne 0.0) {
        throw 'Le self-test n a pas conserve les cibles thermiques a zero.'
    }
}

function Invoke-InstalledValidation {
    Assert-LocalPins
    Assert-InstalledHashes
    $before = Wait-StartOwnerSnapshot -ExpectInstalled
    if ($before.start_owner.phase -ne 'idle') { throw 'Le self-test exige un owner idle.' }
    Invoke-RemoteAdmin 'selftest' | Out-Null
    Start-Sleep -Seconds 3
    $aborted = Wait-StartOwnerSnapshot -ExpectInstalled -Attempts 10
    if ($aborted.start_owner.phase -ne 'watchdog_aborted' -or [int]$aborted.start_owner.watchdog_armed -ne 0) {
        throw 'Le watchdog froid ne s est pas ferme par lui-meme.'
    }
    Assert-NoPhysicalChange $before $aborted
    Invoke-RemoteAdmin 'reset' | Out-Null
    $final = Wait-StartOwnerSnapshot -ExpectInstalled -Attempts 10
    if ($final.start_owner.phase -ne 'idle') { throw 'Le reset du self-test n a pas rendu idle.' }
    Assert-NoPhysicalChange $before $final
    Assert-InstalledHashes
    Save-Evidence 'validation-before.json' $before
    Save-Evidence 'validation-watchdog-aborted.json' $aborted
    Save-Evidence 'validation-final.json' $final
    return $final
}

function Invoke-StartOwnerRollback {
    param([switch]$BestEffort)

    if (-not $CaptureId) { throw 'Rollback exige -CaptureId.' }
    $backup = "$RemoteRoot/backups/$CaptureId/start-sequence-owner-v1"
    foreach ($command in @(
            "test -f '$backup/printer.cfg.before'",
            "test -f '$backup/checksums.sha256'",
            "cd '$backup' && sha256sum -c checksums.sha256",
            "cp '$backup/printer.cfg.before' '$PrinterConfig.rollback-next'",
            "test `"`$(sha256sum '$PrinterConfig.rollback-next' | cut -d ' ' -f 1)`" = '$ExpectedPrinterHash'",
            "mv '$PrinterConfig.rollback-next' '$PrinterConfig'",
            "rm -f '$StartOwnerConfig' '$StartOwnerConfig.next' '$PrinterConfig.next' '$PrinterConfig.rollback-final'",
            'sync'
        )) {
        try { Invoke-Remote $command | Out-Null }
        catch { if (-not $BestEffort) { throw } }
    }
    try {
        Invoke-KlipperRestartAndWait | Out-Null
        Restore-BestCurrentMeshAfterRestart | Out-Null
        $snapshot = Wait-StartOwnerSnapshot -Attempts 60
        if ((Get-RemoteHash $PrinterConfig) -ne $ExpectedPrinterHash) { throw 'Rollback printer.cfg incomplet.' }
        Assert-ImmutableDependencyHashes
        if (Invoke-RemoteTest "test -e '$StartOwnerConfig'") { throw 'Le fichier start owner existe encore apres rollback.' }
        Save-Evidence 'rollback-final.json' $snapshot
    }
    catch { if (-not $BestEffort) { throw } }
}

if ($Action -eq 'Plan') {
    Assert-LocalPins
    [pscustomobject]@{
        status = 'PLAN_ONLY'
        gate = $RequiredGate
        current_printer_sha256 = $ExpectedPrinterHash
        next_printer_sha256 = $ExpectedNextPrinterHash
        config_sha256 = $ExpectedConfigHash
        remote_file_added = $StartOwnerConfig
        printer_cfg_change = '[include k1-control-start-sequence-owner-v1.cfg] after calibration path include'
        restart = 'Klipper host RESTART only'
        installed_validation = 'cold watchdog self-test then reset; no heat, motion or extrusion'
        rollback = 'restore exact printer.cfg, remove one additive file, restart and revalidate safe baseline'
        physical_trial_started = $false
    } | ConvertTo-Json -Depth 6
    exit 0
}

Assert-ExactGate
if ($EvidenceDirectory) { [void](Assert-LocalPathInsideWorkspace $EvidenceDirectory) }

if ($Action -eq 'Preflight') {
    Invoke-StartOwnerPreflight | ConvertTo-Json -Depth 8
    exit 0
}

if ($Action -eq 'Deploy') {
    if (-not $CaptureId -or -not $EvidenceDirectory) { throw 'Deploy exige -CaptureId et -EvidenceDirectory.' }
    $preflight = Invoke-StartOwnerPreflight
    if ($preflight.prospective_printer_sha256 -ne $ExpectedNextPrinterHash) {
        throw 'Le hash prospectif ne correspond pas au paquet fige.'
    }
    $backup = "$RemoteRoot/backups/$CaptureId/start-sequence-owner-v1"
    $staging = "$RemoteRoot/staging/$CaptureId/start-sequence-owner-v1"
    try {
        Invoke-Remote "test ! -e '$backup' && mkdir -p '$backup' '$staging'" | Out-Null
        & scp.exe -O -q -o BatchMode=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no `
            $LocalConfig "k1max-root`:$staging/k1-control-start-sequence-owner-v1.cfg"
        if ($LASTEXITCODE -ne 0) { throw 'Transfert du start owner KO.' }
        if ((Get-RemoteHash "$staging/k1-control-start-sequence-owner-v1.cfg") -ne $ExpectedConfigHash) {
            throw 'Configuration staging differente.'
        }
        Invoke-Remote "cp '$PrinterConfig' '$backup/printer.cfg.before'" | Out-Null
        if ((Get-RemoteHash "$backup/printer.cfg.before") -ne $ExpectedPrinterHash) { throw 'Backup printer.cfg different.' }
        $checksum = "$ExpectedPrinterHash  printer.cfg.before"
        $payload = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$checksum`n"))
        Invoke-Remote "echo '$payload' | base64 -d > '$backup/checksums.sha256'" | Out-Null
        Invoke-Remote "cd '$backup' && sha256sum -c checksums.sha256" | Out-Null
        Save-Evidence 'remote-backup-sha256.txt' $checksum
        $awkProgram = '{print; if ($0 == "[include k1-control-calibration-path.cfg]") {print "[include k1-control-start-sequence-owner-v1.cfg]"; count++}} END {if (count != 1) exit 42}'
        Invoke-Remote "awk '$awkProgram' '$PrinterConfig' > '$staging/printer.cfg.next'" | Out-Null
        if ((Get-RemoteHash "$staging/printer.cfg.next") -ne $ExpectedNextPrinterHash) { throw 'printer.cfg staging different.' }
        $MutationStarted = $true
        Invoke-Remote "cp '$staging/k1-control-start-sequence-owner-v1.cfg' '$StartOwnerConfig.next' && chmod 600 '$StartOwnerConfig.next' && mv '$StartOwnerConfig.next' '$StartOwnerConfig'" | Out-Null
        Invoke-Remote "cp '$staging/printer.cfg.next' '$PrinterConfig.next' && mv '$PrinterConfig.next' '$PrinterConfig' && sync" | Out-Null
        Invoke-KlipperRestartAndWait | Out-Null
        Restore-BestCurrentMeshAfterRestart | Out-Null
        Invoke-InstalledValidation | Out-Null
        Write-Output "DEPLOY_START_SEQUENCE_OWNER_V1_OK capture=$CaptureId"
    }
    catch {
        $deploymentError = $_
        if ($MutationStarted) {
            try { Invoke-StartOwnerRollback }
            catch { throw "Deploiement KO et rollback KO. Initial : $deploymentError`nRollback : $_" }
        }
        throw $deploymentError
    }
    exit 0
}

if ($Action -eq 'Validate') {
    Invoke-InstalledValidation | Out-Null
    Write-Output 'VALIDATE_START_SEQUENCE_OWNER_V1_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Invoke-StartOwnerRollback
    Write-Output "ROLLBACK_START_SEQUENCE_OWNER_V1_OK capture=$CaptureId"
    exit 0
}
