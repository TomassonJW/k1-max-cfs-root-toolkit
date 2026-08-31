[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback', 'RestoreAcceptedZ')]
    [string]$Action = 'Plan',

    [string]$Gate,

    [ValidatePattern('^[0-9]{8}-[0-9]{6}-g4-k1-control-stock-derived-cycle-activation-v1$')]
    [string]$CaptureId,

    [string]$EvidenceDirectory,

    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'PowerShell 7 ou plus recent est obligatoire.'
}

$RequiredGate = 'G4-K1-CONTROL-STOCK-DERIVED-CYCLE-ACTIVATION-IDLE-V1'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-cycle-activation-v1'
$ManifestPath = Join-Path $PackageRoot 'deployment-manifest.json'
$RemoteAdmin = Join-Path $WorkspaceRoot 'packages\k1-control-v1\start-sequence-owner-v1\remote_admin.py'
$RemoteSourceValidator = Join-Path $PackageRoot 'remote_source_validate.py'
$RemoteActiveValidator = Join-Path $PackageRoot 'remote_validate_active_idle.py'
$RemoteProspective = Join-Path $PackageRoot 'remote_prospective_hash.py'
$RemoteAcceptedZRestorer = Join-Path $PackageRoot 'remote_restore_accepted_z.py'
$RemoteDisabledValidator = Join-Path $WorkspaceRoot (
    'packages\k1-control-v1\stock-derived-handoff-moonraker-install-disabled-v1\remote_validate_disabled.py'
)
$OldMoonrakerSection = Join-Path $WorkspaceRoot (
    'packages\k1-control-v1\stock-derived-handoff-moonraker-install-disabled-v1\moonraker-section.conf'
)
$NewMoonrakerSection = Join-Path $PackageRoot 'moonraker-section.conf'

$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteCurrent = "$RemoteRoot/current"
$PrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$MoonrakerConfig = "$RemoteCurrent/config/moonraker.conf"
$MoonrakerComponent = "$RemoteCurrent/moonraker/moonraker/moonraker/components/k1_control_stock_cycle.py"
$MoonrakerService = '/etc/init.d/S56k1_control_moonraker'
$KlipperService = '/etc/init.d/S55klipper_service'
$RunStatePath = "$RemoteRoot/state/stock-derived-cycle-state.json"
$SelectionStatePath = "$RemoteRoot/state/stock-derived-selection.json"
$SshTarget = 'k1max-root'
$SshOptions = @(
    '-o', 'BatchMode=yes',
    '-o', 'PasswordAuthentication=no',
    '-o', 'KbdInteractiveAuthentication=no',
    '-o', 'ConnectTimeout=8'
)
$MutationStarted = $false
$PreflightRoute = $null

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

function Get-LocalSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Resolve-Source {
    param([Parameter(Mandatory = $true)]$Entry)
    return Assert-LocalPathInsideWorkspace (Join-Path $WorkspaceRoot ([string]$Entry.source))
}

function Assert-Package {
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ($manifest.gate -cne $RequiredGate -or
        [string]$manifest.status -notin @(
            'offline_review_candidate_not_installed',
            'installed_validated_active_idle_no_physical_trial'
        ) -or
        $manifest.files.Count -ne 8) {
        throw 'Manifeste d activation invalide.'
    }
    foreach ($entry in @($manifest.files) + @($manifest.support_files) + @($manifest.preparation_evidence)) {
        $local = Resolve-Source $entry
        if ((Get-LocalSha256 $local) -cne [string]$entry.sha256) {
            throw "Fichier local non fige : $($entry.source)"
        }
    }
    $deployer = Resolve-Source $manifest.deployer
    if ((Get-LocalSha256 $deployer) -cne [string]$manifest.deployer.sha256) {
        throw 'Deployer local non fige.'
    }
    foreach ($config in @(
        'k1-control-cfs-direct-owner-active-v1.cfg',
        'k1-control-stock-cycle-active-v1.cfg',
        'k1-control-stock-geometry-handoff-active-v1.cfg',
        'moonraker-section.conf'
    )) {
        $text = [IO.File]::ReadAllText((Join-Path $PackageRoot $config)).Replace("`r`n", "`n")
        if ($text -notmatch '(?m)^enabled:\s*true\s*$' -or $text -match '(?m)^enabled:\s*false\s*$') {
            throw "Configuration non active : $config"
        }
    }
    return $manifest
}

function Assert-ConnectionGate {
    if (-not $Execute -or $Gate -cne $RequiredGate) {
        throw "Action bloquee : -Execute et -Gate '$RequiredGate' sont obligatoires."
    }
    if ($EvidenceDirectory) {
        if (-not (Test-Path -LiteralPath $EvidenceDirectory -PathType Container)) {
            New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null
        }
        [void](Assert-LocalPathInsideWorkspace $EvidenceDirectory)
    }
}

function Assert-MutationGate {
    Assert-ConnectionGate
    if (-not $CaptureId -or -not $EvidenceDirectory) {
        throw 'CaptureId et EvidenceDirectory sont obligatoires pour cette mutation.'
    }
}

function Save-Evidence {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Value
    )
    if (-not $EvidenceDirectory) { return }
    $root = Assert-LocalPathInsideWorkspace $EvidenceDirectory
    $path = Join-Path $root $Name
    if ($Value -is [string]) {
        $Value | Set-Content -LiteralPath $path -Encoding utf8
    }
    else {
        $Value | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $path -Encoding utf8
    }
}

function Invoke-Remote {
    param([Parameter(Mandatory = $true)][string]$Command)
    $output = & ssh.exe @SshOptions $SshTarget $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Commande distante KO ($LASTEXITCODE) : $Command`n$($output -join "`n")"
    }
    return @($output)
}

function Invoke-RemoteStdin {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string]$StandardInput
    )
    $output = $StandardInput | & ssh.exe @SshOptions $SshTarget $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Commande distante stdin KO ($LASTEXITCODE) : $Command`n$($output -join "`n")"
    }
    return @($output)
}

function Copy-ToRemote {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $resolved = Assert-LocalPathInsideWorkspace $Source
    $output = & scp.exe '-O' @SshOptions $resolved "${SshTarget}:$Destination" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Transfert distant KO : $resolved -> $Destination`n$($output -join "`n")"
    }
}

function Get-RemoteHash {
    param([Parameter(Mandatory = $true)][string]$Path)
    $line = Invoke-Remote "sha256sum '$Path'" | Select-Object -First 1
    return (($line -split '\s+')[0]).Trim().ToLowerInvariant()
}

function Invoke-Admin {
    param([Parameter(Mandatory = $true)][ValidateSet('generation', 'snapshot', 'restart', 'restore_mesh', 'objects')][string]$AdminAction)
    $program = [IO.File]::ReadAllText($RemoteAdmin).Replace("`r`n", "`n")
    $output = Invoke-RemoteStdin "/usr/share/klippy-env/bin/python -B - '$AdminAction'" $program
    if ($AdminAction -eq 'restart') { return @($output) }
    return (($output -join "`n") | ConvertFrom-Json)
}

function Restore-AcceptedZNoMove {
    param([Parameter(Mandatory = $true)][string]$EvidenceName)
    $program = [IO.File]::ReadAllText($RemoteAcceptedZRestorer).Replace("`r`n", "`n")
    $output = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $program
    if (($output | Select-Object -Last 1) -cne 'REMOTE_RESTORE_ACCEPTED_Z_NO_MOVE_OK') {
        throw "Restauration du Z accepte invalide : $($output -join "`n")"
    }
    Save-Evidence $EvidenceName (($output | Select-Object -First 1) | ConvertFrom-Json)
}

function Wait-KlipperTransition {
    param([Parameter(Mandatory = $true)]$BeforeGeneration)
    Start-Sleep -Seconds 2
    $readyReads = 0
    $fatalStateMessage = $null
    for ($attempt = 1; $attempt -le 90; $attempt++) {
        try {
            $generation = Invoke-Admin 'generation'
            $changed = ([long]$generation.socket_inode -ne [long]$BeforeGeneration.socket_inode) -or
                ([long]$generation.socket_mtime_ns -ne [long]$BeforeGeneration.socket_mtime_ns)
            if ($changed) {
                $snapshot = Invoke-Admin 'snapshot'
                if ([string]$snapshot.webhooks.state -cin @('error', 'shutdown')) {
                    $fatalStateMessage = [string]$snapshot.webhooks.state_message
                }
                if ($snapshot.webhooks.state -ceq 'ready' -and $snapshot.print_state) {
                    $readyReads++
                    if ($readyReads -ge 2) { return $snapshot }
                }
                else { $readyReads = 0 }
            }
        }
        catch { $readyReads = 0 }
        if ($fatalStateMessage) {
            throw "Klipper a refuse la configuration apres transition : $fatalStateMessage"
        }
        Start-Sleep -Seconds 1
    }
    throw 'Klipper ne presente pas une vraie transition prete dans le delai.'
}

function Wait-Moonraker {
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        try {
            [void](Invoke-Remote "curl 'http://127.0.0.1:7125/server/info'")
            return
        }
        catch { Start-Sleep -Seconds 1 }
    }
    throw 'Le Moonraker dedie ne repond pas apres restart.'
}

function Get-RouteSignature {
    param([Parameter(Mandatory = $true)]$Snapshot)
    $routes = @()
    if ([string]$Snapshot.box.units.T1.filament -notin @('', 'None', 'none')) {
        $routes += "T1$([string]$Snapshot.box.units.T1.filament)"
    }
    if ([string]$Snapshot.box.units.T2.filament -notin @('', 'None', 'none')) {
        $routes += "T2$([string]$Snapshot.box.units.T2.filament)"
    }
    if ($routes.Count -gt 1) { throw 'Plusieurs routes CFS engagees.' }
    return $(if ($routes.Count -eq 1) { $routes[0] } else { 'none' })
}

function Assert-SafeSnapshot {
    param(
        [Parameter(Mandatory = $true)]$Snapshot,
        [Parameter(Mandatory = $true)]$Manifest,
        [Parameter(Mandatory = $true)][int]$ExpectedAutoRefill,
        [string]$ExpectedRoute
    )
    $origin = @($Snapshot.homing_origin)
    if ($Snapshot.webhooks.state -cne 'ready' -or
        $Snapshot.print_state -cne 'standby' -or
        [double]$Snapshot.extruder.target -ne 0.0 -or
        [double]$Snapshot.heater_bed.target -ne 0.0 -or
        [string]$Snapshot.toolhead.homed_axes -ne '' -or
        [string]$Snapshot.mesh_profile -cne [string]$Manifest.baseline.best_current_mesh -or
        [int]$Snapshot.runtime.accepted_z_valid -ne 1 -or
        [Math]::Abs([double]$Snapshot.runtime.accepted_z_offset - [double]$Manifest.baseline.accepted_z_offset_mm) -gt 0.0005 -or
        $origin.Count -lt 3 -or
        [Math]::Abs([double]$origin[2] - [double]$Manifest.baseline.accepted_z_offset_mm) -gt 0.0005 -or
        $Snapshot.box.units.T1.state -cne 'connect' -or
        $Snapshot.box.units.T2.state -cne 'connect' -or
        [string]$Snapshot.box.t_command -ne '' -or
        [int]$Snapshot.box.auto_refill -ne $ExpectedAutoRefill -or
        [int]$Snapshot.box.enable -ne 1 -or
        $Snapshot.start_owner.phase -cne 'idle') {
        throw 'Etat K1 froid non conforme.'
    }
    $route = Get-RouteSignature $Snapshot
    if ($ExpectedRoute -and $route -cne $ExpectedRoute) {
        throw "La route CFS a change : $ExpectedRoute -> $route"
    }
    return $route
}

function Assert-RequiredBaseFiles {
    param([Parameter(Mandatory = $true)]$Manifest)
    foreach ($property in $Manifest.baseline.required_files.PSObject.Properties) {
        if ((Get-RemoteHash ([string]$property.Value.path)) -cne [string]$property.Value.sha256) {
            throw "Base distante revue derivee : $($property.Name)"
        }
    }
}

function Assert-ImmutableBase {
    param([Parameter(Mandatory = $true)]$Manifest)
    if ((Get-RemoteHash $PrinterConfig) -cne [string]$Manifest.baseline.printer_cfg_sha256 -or
        (Get-RemoteHash $MoonrakerConfig) -cne [string]$Manifest.baseline.moonraker_conf_sha256) {
        throw 'Une configuration distante revue a derive.'
    }
    Assert-RequiredBaseFiles $Manifest
}

function Assert-RemoteSources {
    $sources = @{
        '__STARTUP_B64__' = Join-Path $PackageRoot 'k1_control_cfs_startup_exclusion.py'
        '__RUNOUT_B64__' = Join-Path $PackageRoot 'k1_control_cfs_runout_owner.py'
        '__ACTIVE_CORE_B64__' = Join-Path $PackageRoot 'active_core.py'
        '__JOB_CONTRACT_B64__' = Join-Path $PackageRoot 'job_contract.py'
        '__MOONRAKER_B64__' = Join-Path $PackageRoot 'moonraker_component.py'
    }
    $program = [IO.File]::ReadAllText($RemoteSourceValidator)
    foreach ($item in $sources.GetEnumerator()) {
        $encoded = [Convert]::ToBase64String([IO.File]::ReadAllBytes($item.Value))
        $program = $program.Replace($item.Key, $encoded)
    }
    $program = $program.Replace("`r`n", "`n")
    $python = "$RemoteCurrent/moonraker/moonraker-env/bin/python"
    $output = Invoke-RemoteStdin "'$python' -B -" $program
    $marker = $output | Select-Object -Last 1
    if ($marker -cne 'REMOTE_STOCK_DERIVED_CYCLE_ACTIVATION_SOURCE_VALIDATE_OK') {
        throw "Validation distante des sources invalide : $($output -join "`n")"
    }
    Save-Evidence 'preflight-source-validate.txt' $marker
}

function Assert-ProspectiveHashes {
    param([Parameter(Mandatory = $true)]$Manifest)
    $old = [Convert]::ToBase64String([IO.File]::ReadAllBytes($OldMoonrakerSection))
    $new = [Convert]::ToBase64String([IO.File]::ReadAllBytes($NewMoonrakerSection))
    $program = [IO.File]::ReadAllText($RemoteProspective).
        Replace('__OLD_SECTION_B64__', $old).
        Replace('__NEW_SECTION_B64__', $new).
        Replace("`r`n", "`n")
    $output = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $program
    $value = (($output | Select-Object -Last 1) | ConvertFrom-Json)
    if ($value.printer_cfg_candidate_sha256 -cne [string]$Manifest.installed.printer_cfg_sha256 -or
        $value.moonraker_conf_candidate_sha256 -cne [string]$Manifest.installed.moonraker_conf_sha256) {
        throw 'Empreinte prospective distante differente du candidat.'
    }
    Save-Evidence 'preflight-prospective-hashes.json' $value
}

function Invoke-DisabledValidation {
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [string]$ExpectedRoute
    )
    $program = [IO.File]::ReadAllText($RemoteDisabledValidator).Replace("`r`n", "`n")
    $output = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $program
    if (($output | Select-Object -Last 1) -cne 'REMOTE_STOCK_DERIVED_HANDOFF_MOONRAKER_DISABLED_VALIDATE_OK') {
        throw "Validation desactivee invalide : $($output -join "`n")"
    }
    $snapshot = Invoke-Admin 'snapshot'
    [void](Assert-SafeSnapshot $snapshot $Manifest 1 $ExpectedRoute)
    Save-Evidence 'validate-disabled.json' (($output | Select-Object -First 1) | ConvertFrom-Json)
}

function Invoke-ActiveValidation {
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [string]$ExpectedRoute
    )
    if ((Get-RemoteHash $PrinterConfig) -cne [string]$Manifest.installed.printer_cfg_sha256 -or
        (Get-RemoteHash $MoonrakerConfig) -cne [string]$Manifest.installed.moonraker_conf_sha256) {
        throw 'Configurations actives non conformes.'
    }
    foreach ($file in $Manifest.files) {
        if ((Get-RemoteHash ([string]$file.destination)) -cne [string]$file.sha256) {
            throw "Payload actif non conforme : $($file.destination)"
        }
    }
    $program = [IO.File]::ReadAllText($RemoteActiveValidator).Replace("`r`n", "`n")
    $output = $null
    $marker = $null
    $lastValidationFailure = 'none'
    for ($attempt = 1; $attempt -le 70; $attempt++) {
        try {
            $output = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $program
            $marker = $output | Select-Object -Last 1
            if ($marker -ceq 'REMOTE_STOCK_DERIVED_CYCLE_ACTIVATION_IDLE_VALIDATE_OK') {
                break
            }
            $lastValidationFailure = $output -join "`n"
        }
        catch {
            $lastValidationFailure = $_.Exception.Message
        }
        if ($attempt -lt 70) { Start-Sleep -Seconds 1 }
    }
    if ($marker -cne 'REMOTE_STOCK_DERIVED_CYCLE_ACTIVATION_IDLE_VALIDATE_OK') {
        throw "Validation active au repos invalide apres attente CFS : $lastValidationFailure"
    }
    $snapshot = Invoke-Admin 'snapshot'
    [void](Assert-SafeSnapshot $snapshot $Manifest 0 $ExpectedRoute)
    Save-Evidence 'validate-active-idle.json' (($output | Select-Object -First 1) | ConvertFrom-Json)
    Save-Evidence 'validate-safe-state.json' $snapshot
}

function Assert-Preflight {
    param([Parameter(Mandatory = $true)]$Manifest)
    Assert-ImmutableBase $Manifest
    [void](Invoke-Remote "test -x '$KlipperService'")
    foreach ($file in $Manifest.files) {
        if ([string]$file.before -ceq 'absent') {
            [void](Invoke-Remote "test ! -e '$([string]$file.destination)'")
        }
        elseif ((Get-RemoteHash ([string]$file.destination)) -cne [string]$file.before_sha256) {
            throw "Fichier remplace derive : $($file.destination)"
        }
    }
    [void](Invoke-Remote "test ! -e '$RunStatePath' && test ! -e '$SelectionStatePath'")
    $snapshot = Invoke-Admin 'snapshot'
    $script:PreflightRoute = Assert-SafeSnapshot $snapshot $Manifest 1
    if ($script:PreflightRoute -cne 'none') {
        throw 'La pose active au repos exige aucune route engagee.'
    }
    Save-Evidence 'preflight-safe-state.json' $snapshot
    Invoke-DisabledValidation $Manifest $script:PreflightRoute
    Assert-RemoteSources
    Assert-ProspectiveHashes $Manifest
}

function Remove-RemoteRuntimeCaches {
    [void](Invoke-Remote "rm -f '/usr/share/klipper/klippy/extras/k1_control_cfs_startup_exclusion.pyc' '/usr/share/klipper/klippy/extras/k1_control_cfs_runout_owner.pyc'")
    foreach ($name in @(
        'k1_control_stock_cycle',
        'k1_control_stock_cycle_active_core',
        'k1_control_stock_job_contract'
    )) {
        [void](Invoke-Remote "rm -f '$RemoteCurrent/moonraker/moonraker/moonraker/components/$name.pyc' '$RemoteCurrent/moonraker/moonraker/moonraker/components/__pycache__/$name.'*.pyc")
    }
}

function Remove-NewPayload {
    param([Parameter(Mandatory = $true)]$Manifest)
    foreach ($file in $Manifest.files) {
        if ([string]$file.before -ceq 'absent') {
            [void](Invoke-Remote "rm -f '$([string]$file.destination)'")
        }
    }
    foreach ($name in @(
        'k1_control_cfs_startup_exclusion',
        'k1_control_cfs_runout_owner'
    )) {
        [void](Invoke-Remote "rm -f '/usr/share/klipper/klippy/extras/$name.pyc'")
        [void](Invoke-Remote "rm -f '/usr/share/klipper/klippy/extras/__pycache__/$name.'*.pyc")
    }
    foreach ($name in @(
        'k1_control_stock_cycle',
        'k1_control_stock_cycle_active_core',
        'k1_control_stock_job_contract'
    )) {
        [void](Invoke-Remote "rm -f '$RemoteCurrent/moonraker/moonraker/moonraker/components/$name.pyc'")
        [void](Invoke-Remote "rm -f '$RemoteCurrent/moonraker/moonraker/moonraker/components/__pycache__/$name.'*.pyc")
    }
    [void](Invoke-Remote "rm -f '$RunStatePath' '$SelectionStatePath' '$PrinterConfig.next' '$MoonrakerConfig.next'")
}

function Invoke-ExactRollback {
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [Parameter(Mandatory = $true)][string]$BackupDirectory,
        [string]$ExpectedRoute
    )
    [void](Invoke-Remote "test -f '$BackupDirectory/printer.cfg.before' && test -f '$BackupDirectory/moonraker.conf.before' && test -f '$BackupDirectory/k1_control_stock_cycle.py.before'")
    [void](Invoke-Remote "cp '$BackupDirectory/printer.cfg.before' '$PrinterConfig'")
    [void](Invoke-Remote "cp '$BackupDirectory/moonraker.conf.before' '$MoonrakerConfig'")
    [void](Invoke-Remote "cp '$BackupDirectory/k1_control_stock_cycle.py.before' '$MoonrakerComponent'")
    Remove-NewPayload $Manifest
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    $before = Invoke-Admin 'generation'
    [void](Invoke-Remote "'$KlipperService' restart")
    [void](Wait-KlipperTransition $before)
    [void](Invoke-Admin 'restore_mesh')
    Restore-AcceptedZNoMove 'rollback-restore-accepted-z.json'
    Assert-ImmutableBase $Manifest
    Invoke-DisabledValidation $Manifest $ExpectedRoute
    Save-Evidence 'rollback-safe-state.json' (Invoke-Admin 'snapshot')
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "PLAN_STOCK_DERIVED_CYCLE_ACTIVATION_V1_OK gate=$RequiredGate"
    Write-Output 'Pose: huit fichiers, remplacement exact de trois includes et de la section Moonraker, puis deux restarts bornes.'
    Write-Output 'Etat final attendu: proprietaires actifs mais idle, auto_refill stock a 0, aucun fichier de run ou selection.'
    Write-Output 'Effets physiques: aucune chauffe, mouvement, extrusion, trame CFS, palpation ou recalcul de mesh.'
    Write-Output 'Rollback: configurations et composant Moonraker exacts, nouveaux fichiers retires, politique stock retablie.'
    exit 0
}

Assert-ConnectionGate

if ($Action -eq 'Preflight') {
    Assert-Preflight $manifest
    Write-Output 'PREFLIGHT_STOCK_DERIVED_CYCLE_ACTIVATION_V1_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    $snapshot = Invoke-Admin 'snapshot'
    $route = Get-RouteSignature $snapshot
    Invoke-ActiveValidation $manifest $route
    Write-Output 'VALIDATE_STOCK_DERIVED_CYCLE_ACTIVATION_V1_OK'
    exit 0
}

Assert-MutationGate
$RemoteBackup = "$RemoteRoot/backups/$CaptureId/stock-derived-cycle-activation-v1"
$RemoteStaging = "$RemoteRoot/staging/$CaptureId-stock-derived-cycle-activation-v1"

if ($Action -eq 'RestoreAcceptedZ') {
    Assert-ImmutableBase $manifest
    Restore-AcceptedZNoMove 'recovery-restore-accepted-z.json'
    $snapshot = Invoke-Admin 'snapshot'
    [void](Assert-SafeSnapshot $snapshot $manifest 1 'none')
    Invoke-DisabledValidation $manifest 'none'
    Save-Evidence 'recovery-safe-state.json' $snapshot
    Write-Output "RESTORE_ACCEPTED_Z_NO_MOVE_V1_OK capture=$CaptureId"
    exit 0
}

if ($Action -eq 'Rollback') {
    $route = Get-RouteSignature (Invoke-Admin 'snapshot')
    Invoke-ExactRollback $manifest $RemoteBackup $route
    Write-Output "ROLLBACK_STOCK_DERIVED_CYCLE_ACTIVATION_V1_OK capture=$CaptureId"
    exit 0
}

Assert-Preflight $manifest

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup' '$RemoteStaging'")
    [void](Invoke-Remote "cp '$PrinterConfig' '$RemoteBackup/printer.cfg.before'")
    [void](Invoke-Remote "cp '$MoonrakerConfig' '$RemoteBackup/moonraker.conf.before'")
    [void](Invoke-Remote "cp '$MoonrakerComponent' '$RemoteBackup/k1_control_stock_cycle.py.before'")
    [void](Invoke-Remote "sha256sum '$PrinterConfig' '$MoonrakerConfig' '$MoonrakerComponent' > '$RemoteBackup/checksums.sha256'")
    $MutationStarted = $true

    foreach ($file in $manifest.files) {
        $local = Resolve-Source $file
        $staged = "$RemoteStaging/$([string]$file.stage_name)"
        Copy-ToRemote $local $staged
        if ((Get-RemoteHash $staged) -cne [string]$file.sha256) {
            throw "Transfert non conforme : $($file.source)"
        }
    }

    $oldSection = [Convert]::ToBase64String([IO.File]::ReadAllBytes($OldMoonrakerSection))
    $newSection = [Convert]::ToBase64String([IO.File]::ReadAllBytes($NewMoonrakerSection))
    $builder = @"
import base64
from hashlib import sha256
from pathlib import Path
p = Path('$PrinterConfig')
data = p.read_bytes()
assert sha256(data).hexdigest() == '$([string]$manifest.baseline.printer_cfg_sha256)'
replacements = (
    (b'[include k1-control-cfs-direct-owner-disabled-v1.cfg]', b'[include k1-control-cfs-direct-owner-active-v1.cfg]'),
    (b'[include k1-control-stock-derived-cycle-owner-disabled-v1.cfg]', b'[include k1-control-stock-cycle-active-v1.cfg]'),
    (b'[include k1-control-stock-geometry-handoff-disabled-v1.cfg]', b'[include k1-control-stock-geometry-handoff-active-v1.cfg]'),
)
candidate = data
for old, new in replacements:
    assert candidate.count(old) == 1 and candidate.count(new) == 0
    candidate = candidate.replace(old, new, 1)
assert sha256(candidate).hexdigest() == '$([string]$manifest.installed.printer_cfg_sha256)'
p.with_suffix('.cfg.next').write_bytes(candidate)
m = Path('$MoonrakerConfig')
moon = m.read_bytes()
assert sha256(moon).hexdigest() == '$([string]$manifest.baseline.moonraker_conf_sha256)'
old_section = base64.b64decode('$oldSection').strip()
new_section = base64.b64decode('$newSection').strip()
assert moon.count(old_section) == 1 and moon.count(new_section) == 0
moon_candidate = moon.replace(old_section, new_section, 1)
assert sha256(moon_candidate).hexdigest() == '$([string]$manifest.installed.moonraker_conf_sha256)'
m.with_suffix('.conf.next').write_bytes(moon_candidate)
print('REMOTE_STOCK_DERIVED_CYCLE_ACTIVATION_CONFIG_BUILD_OK')
"@
    $buildOutput = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $builder
    if (($buildOutput | Select-Object -Last 1) -cne 'REMOTE_STOCK_DERIVED_CYCLE_ACTIVATION_CONFIG_BUILD_OK') {
        throw 'Construction distante des configurations actives invalide.'
    }

    foreach ($file in $manifest.files) {
        $destination = [string]$file.destination
        $staged = [string]$file.stage_name
        [void](Invoke-Remote "cp '$RemoteStaging/$staged' '$destination.next' && chmod 0644 '$destination.next' && mv '$destination.next' '$destination'")
    }
    Remove-RemoteRuntimeCaches
    [void](Invoke-Remote "mv '$PrinterConfig.next' '$PrinterConfig'")
    [void](Invoke-Remote "mv '$MoonrakerConfig.next' '$MoonrakerConfig'")
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    $before = Invoke-Admin 'generation'
    [void](Invoke-Remote "'$KlipperService' restart")
    [void](Wait-KlipperTransition $before)
    [void](Invoke-Admin 'restore_mesh')
    Restore-AcceptedZNoMove 'deploy-restore-accepted-z.json'
    Invoke-ActiveValidation $manifest $PreflightRoute
    Save-Evidence 'deploy-result.json' ([ordered]@{
        capture_id = $CaptureId
        result = 'DEPLOY_STOCK_DERIVED_CYCLE_ACTIVATION_V1_OK'
        route_preserved = $PreflightRoute
        active_idle = $true
        run_state_created = $false
        selection_state_created = $false
        physical_action = $false
        heat = $false
        motion = $false
        extrusion = $false
        cfs_frame = $false
        probe = $false
        mesh_recalculation = $false
    })
    Write-Output "DEPLOY_STOCK_DERIVED_CYCLE_ACTIVATION_V1_OK capture=$CaptureId"
}
catch {
    $failure = $_
    try { Save-Evidence 'deploy-failure.txt' $failure.Exception.ToString() } catch {}
    if ($MutationStarted) {
        try { Invoke-ExactRollback $manifest $RemoteBackup $PreflightRoute }
        catch {
            throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)"
        }
    }
    throw $failure
}
