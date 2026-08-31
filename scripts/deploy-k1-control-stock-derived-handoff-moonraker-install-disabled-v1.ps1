[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',

    [string]$Gate,

    [ValidatePattern('^[0-9]{8}-[0-9]{6}-g4-k1-control-stock-derived-handoff-moonraker-install-disabled-v1$')]
    [string]$CaptureId,

    [string]$EvidenceDirectory,

    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'PowerShell 7 ou plus recent est obligatoire.'
}

$RequiredGate = 'G4-K1-CONTROL-STOCK-DERIVED-HANDOFF-MOONRAKER-INSTALL-DISABLED-V1'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-handoff-moonraker-install-disabled-v1'
$ManifestPath = Join-Path $PackageRoot 'deployment-manifest.json'
$RemoteAdmin = Join-Path $WorkspaceRoot 'packages\k1-control-v1\start-sequence-owner-v1\remote_admin.py'
$RemoteSourceValidator = Join-Path $PackageRoot 'remote_source_validate.py'
$RemoteDisabledValidator = Join-Path $PackageRoot 'remote_validate_disabled.py'

$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteCurrent = "$RemoteRoot/current"
$PrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$MoonrakerConfig = "$RemoteCurrent/config/moonraker.conf"
$MoonrakerService = '/etc/init.d/S56k1_control_moonraker'
$StatePath = "$RemoteRoot/state/stock-derived-cycle-state.json"
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
        [string]$manifest.status -cne 'offline_review_candidate_not_installed' -or
        $manifest.files.Count -ne 6) {
        throw 'Manifeste de pose handoff/Moonraker invalide.'
    }
    foreach ($entry in @($manifest.files) + @($manifest.support_files) + @($manifest.preparation_evidence)) {
        $local = Resolve-Source $entry
        $actual = Get-LocalSha256 $local
        if ($actual -cne [string]$entry.sha256) {
            throw "Fichier local non fige : $($entry.source) hash=$actual"
        }
    }
    $deployer = Assert-LocalPathInsideWorkspace (Join-Path $WorkspaceRoot ([string]$manifest.deployer.source))
    $deployerHash = Get-LocalSha256 $deployer
    if ($deployerHash -cne [string]$manifest.deployer.sha256) {
        throw "Deployer local non fige : $deployerHash"
    }
    foreach ($configName in @(
        'packages\k1-control-v1\cfs-stock-derived-cycle-owner-install-disabled-v1\k1-control-stock-derived-cycle-owner-disabled-v1.cfg',
        'packages\k1-control-v1\stock-derived-handoff-moonraker-install-disabled-v1\k1-control-stock-geometry-handoff-disabled-v1.cfg'
    )) {
        $text = [IO.File]::ReadAllText((Join-Path $WorkspaceRoot $configName)).Replace("`r`n", "`n")
        if ($text -notmatch '(?m)^enabled:\s*false\s*$' -or $text -match '(?m)^enabled:\s*true\s*$') {
            throw "Configuration Klipper non immuablement desactivee : $configName"
        }
    }
    $section = [IO.File]::ReadAllText((Join-Path $PackageRoot 'moonraker-section.conf')).Replace("`r`n", "`n")
    if ($section -notmatch '(?m)^enabled:\s*false\s*$' -or $section -match '(?m)^enabled:\s*true\s*$') {
        throw 'Section Moonraker non immuablement desactivee.'
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

function Wait-KlipperTransition {
    param([Parameter(Mandatory = $true)]$BeforeGeneration)

    Start-Sleep -Seconds 2
    $readyReads = 0
    for ($attempt = 1; $attempt -le 90; $attempt++) {
        try {
            $generation = Invoke-Admin 'generation'
            $changed = ([long]$generation.socket_inode -ne [long]$BeforeGeneration.socket_inode) -or
                ([long]$generation.socket_mtime_ns -ne [long]$BeforeGeneration.socket_mtime_ns)
            if ($changed) {
                $snapshot = Invoke-Admin 'snapshot'
                if ($snapshot.webhooks.state -ceq 'ready' -and $snapshot.print_state) {
                    $readyReads++
                    if ($readyReads -ge 2) { return $snapshot }
                }
                else { $readyReads = 0 }
            }
        }
        catch { $readyReads = 0 }
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
        [string]$ExpectedRoute
    )

    if ($Snapshot.webhooks.state -cne 'ready' -or
        $Snapshot.print_state -cne 'standby' -or
        [double]$Snapshot.extruder.target -ne 0.0 -or
        [double]$Snapshot.heater_bed.target -ne 0.0 -or
        [string]$Snapshot.toolhead.homed_axes -ne '' -or
        [string]$Snapshot.mesh_profile -cne [string]$Manifest.baseline.best_current_mesh -or
        [int]$Snapshot.runtime.accepted_z_valid -ne 1 -or
        [Math]::Abs([double]$Snapshot.runtime.accepted_z_offset - [double]$Manifest.baseline.accepted_z_offset_mm) -gt 0.0005 -or
        $Snapshot.box.units.T1.state -cne 'connect' -or
        $Snapshot.box.units.T2.state -cne 'connect' -or
        [string]$Snapshot.box.t_command -ne '' -or
        [int]$Snapshot.box.auto_refill -ne 1 -or
        [int]$Snapshot.box.enable -ne 1 -or
        $Snapshot.start_owner.phase -cne 'idle') {
        throw 'Etat K1 froid ou proprietaires de base non conforme.'
    }
    $route = Get-RouteSignature $Snapshot
    if ($ExpectedRoute -and $route -cne $ExpectedRoute) {
        throw "La route CFS a change pendant la pose : $ExpectedRoute -> $route"
    }
    return $route
}

function Assert-RemoteSources {
    $geometry = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $PackageRoot 'k1_control_stock_geometry_handoff.py')))
    $core = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $WorkspaceRoot 'packages\k1-control-v1\cfs-stock-derived-orchestrator-offline-v1\orchestrator.py')))
    $moonraker = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $PackageRoot 'moonraker_component.py')))
    $program = [IO.File]::ReadAllText($RemoteSourceValidator).
        Replace('__GEOMETRY_B64__', $geometry).
        Replace('__CORE_B64__', $core).
        Replace('__MOONRAKER_B64__', $moonraker).
        Replace("`r`n", "`n")
    $python = "$RemoteCurrent/moonraker/moonraker-env/bin/python"
    $output = Invoke-RemoteStdin "'$python' -B -" $program
    $marker = $output | Select-Object -Last 1
    if ($marker -cne 'REMOTE_STOCK_DERIVED_HANDOFF_MOONRAKER_SOURCE_VALIDATE_OK') {
        throw "Validation Python K1 des sources invalide : $($output -join "`n")"
    }
    Save-Evidence 'preflight-source-validate.txt' $marker
}

function Assert-RequiredBaseFiles {
    param([Parameter(Mandatory = $true)]$Manifest)

    foreach ($property in $Manifest.baseline.required_files.PSObject.Properties) {
        $path = [string]$property.Value.path
        $expected = [string]$property.Value.sha256
        if ((Get-RemoteHash $path) -cne $expected) {
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

function Assert-Preflight {
    param([Parameter(Mandatory = $true)]$Manifest)

    Assert-ImmutableBase $Manifest
    foreach ($file in $Manifest.files) {
        [void](Invoke-Remote "test ! -e '$([string]$file.destination)'")
    }
    [void](Invoke-Remote "test ! -e '$StatePath'")
    [void](Invoke-Remote "test `$(grep -c '^\[include k1-control-stock-derived-cycle-owner-disabled-v1.cfg\]$' '$PrinterConfig') -eq 0")
    [void](Invoke-Remote "test `$(grep -c '^\[include k1-control-stock-geometry-handoff-disabled-v1.cfg\]$' '$PrinterConfig') -eq 0")
    [void](Invoke-Remote "test `$(grep -c '^\[k1_control_stock_cycle\]$' '$MoonrakerConfig') -eq 0")
    $snapshot = Invoke-Admin 'snapshot'
    $script:PreflightRoute = Assert-SafeSnapshot $snapshot $Manifest
    Save-Evidence 'preflight-safe-state.json' $snapshot
    Save-Evidence 'preflight-route.txt' $script:PreflightRoute
    Assert-RemoteSources
}

function Invoke-DisabledValidation {
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [string]$ExpectedRoute
    )

    if ((Get-RemoteHash $PrinterConfig) -cne [string]$Manifest.installed.printer_cfg_sha256 -or
        (Get-RemoteHash $MoonrakerConfig) -cne [string]$Manifest.installed.moonraker_conf_sha256) {
        throw 'Configurations installees non conformes au candidat.'
    }
    Assert-RequiredBaseFiles $Manifest
    foreach ($file in $Manifest.files) {
        if ((Get-RemoteHash ([string]$file.destination)) -cne [string]$file.sha256) {
            throw "Payload distant non conforme : $($file.destination)"
        }
    }
    [void](Invoke-Remote "test `$(grep -c '^\[include k1-control-stock-derived-cycle-owner-disabled-v1.cfg\]$' '$PrinterConfig') -eq 1")
    [void](Invoke-Remote "test `$(grep -c '^\[include k1-control-stock-geometry-handoff-disabled-v1.cfg\]$' '$PrinterConfig') -eq 1")
    [void](Invoke-Remote "test `$(grep -c '^\[k1_control_stock_cycle\]$' '$MoonrakerConfig') -eq 1")
    $program = [IO.File]::ReadAllText($RemoteDisabledValidator).Replace("`r`n", "`n")
    $output = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $program
    if (($output | Select-Object -Last 1) -cne 'REMOTE_STOCK_DERIVED_HANDOFF_MOONRAKER_DISABLED_VALIDATE_OK') {
        throw "Validation desactivee distante invalide : $($output -join "`n")"
    }
    $state = ($output | Select-Object -First 1) | ConvertFrom-Json
    $snapshot = Invoke-Admin 'snapshot'
    [void](Assert-SafeSnapshot $snapshot $Manifest $ExpectedRoute)
    Save-Evidence 'validate-disabled.json' $state
    Save-Evidence 'validate-safe-state.json' $snapshot
    return $state
}

function Remove-RemotePayload {
    param([Parameter(Mandatory = $true)]$Manifest)

    foreach ($file in $Manifest.files) {
        [void](Invoke-Remote "rm -f '$([string]$file.destination)'")
    }
    [void](Invoke-Remote "rm -f '/usr/share/klipper/klippy/extras/__pycache__/k1_control_stock_cycle_owner.'*.pyc")
    [void](Invoke-Remote "rm -f '/usr/share/klipper/klippy/extras/__pycache__/k1_control_stock_geometry_handoff.'*.pyc")
    [void](Invoke-Remote "rm -f '$RemoteCurrent/moonraker/moonraker/moonraker/components/__pycache__/k1_control_stock_cycle.'*.pyc")
    [void](Invoke-Remote "rm -f '$RemoteCurrent/moonraker/moonraker/moonraker/components/__pycache__/k1_control_stock_cycle_core.'*.pyc")
    [void](Invoke-Remote "rm -f '$StatePath' '$PrinterConfig.next' '$MoonrakerConfig.next'")
}

function Invoke-ExactRollback {
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [Parameter(Mandatory = $true)][string]$BackupDirectory,
        [string]$ExpectedRoute
    )

    [void](Invoke-Remote "test -f '$BackupDirectory/printer.cfg.before' && test -f '$BackupDirectory/moonraker.conf.before'")
    [void](Invoke-Remote "cp '$BackupDirectory/printer.cfg.before' '$PrinterConfig'")
    [void](Invoke-Remote "cp '$BackupDirectory/moonraker.conf.before' '$MoonrakerConfig'")
    Remove-RemotePayload $Manifest
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    $before = Invoke-Admin 'generation'
    [void](Invoke-Admin 'restart')
    [void](Wait-KlipperTransition $before)
    [void](Invoke-Admin 'restore_mesh')
    if ((Get-RemoteHash $PrinterConfig) -cne [string]$Manifest.baseline.printer_cfg_sha256 -or
        (Get-RemoteHash $MoonrakerConfig) -cne [string]$Manifest.baseline.moonraker_conf_sha256) {
        throw 'Rollback exact des configurations incomplet.'
    }
    Assert-ImmutableBase $Manifest
    $objects = @(Invoke-Admin 'objects')
    foreach ($name in @('k1_control_stock_cycle_owner', 'k1_control_stock_geometry_handoff')) {
        if ($objects -contains $name) { throw "Objet encore charge apres rollback : $name" }
    }
    $snapshot = Invoke-Admin 'snapshot'
    [void](Assert-SafeSnapshot $snapshot $Manifest $ExpectedRoute)
    Save-Evidence 'rollback-safe-state.json' $snapshot
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "PLAN_STOCK_DERIVED_HANDOFF_MOONRAKER_INSTALL_DISABLED_V1_OK gate=$RequiredGate"
    Write-Output 'Pose: six fichiers, deux includes, une section Moonraker, restart Moonraker dedie et RESTART Klipper, puis remise du 11x11.'
    Write-Output 'Tous les proprietaires ajoutes restent immuablement enabled=false dans cette revision.'
    Write-Output 'Effets physiques: aucune chauffe, mouvement, extrusion, trame CFS, palpation ou recalcul de mesh.'
    Write-Output 'Rollback: printer.cfg et moonraker.conf exacts, six fichiers retires, deux restarts bornes et remise du meme mesh.'
    exit 0
}

Assert-ConnectionGate

if ($Action -eq 'Preflight') {
    Assert-Preflight $manifest
    Write-Output 'PREFLIGHT_STOCK_DERIVED_HANDOFF_MOONRAKER_INSTALL_DISABLED_V1_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    $snapshot = Invoke-Admin 'snapshot'
    $route = Assert-SafeSnapshot $snapshot $manifest
    [void](Invoke-DisabledValidation $manifest $route)
    Write-Output 'VALIDATE_STOCK_DERIVED_HANDOFF_MOONRAKER_INSTALL_DISABLED_V1_OK'
    exit 0
}

Assert-MutationGate
$RemoteBackup = "$RemoteRoot/backups/$CaptureId/stock-derived-handoff-moonraker-install-disabled-v1"
$RemoteStaging = "$RemoteRoot/staging/$CaptureId-stock-derived-handoff-moonraker-install-disabled-v1"

if ($Action -eq 'Rollback') {
    $snapshot = Invoke-Admin 'snapshot'
    $route = Get-RouteSignature $snapshot
    Invoke-ExactRollback $manifest $RemoteBackup $route
    Write-Output "ROLLBACK_STOCK_DERIVED_HANDOFF_MOONRAKER_INSTALL_DISABLED_V1_OK capture=$CaptureId"
    exit 0
}

Assert-Preflight $manifest

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup' '$RemoteStaging'")
    [void](Invoke-Remote "cp '$PrinterConfig' '$RemoteBackup/printer.cfg.before'")
    [void](Invoke-Remote "cp '$MoonrakerConfig' '$RemoteBackup/moonraker.conf.before'")
    [void](Invoke-Remote "sha256sum '$PrinterConfig' '$MoonrakerConfig' > '$RemoteBackup/checksums.sha256'")
    $MutationStarted = $true

    foreach ($file in $manifest.files) {
        $local = Resolve-Source $file
        Copy-ToRemote $local "$RemoteStaging/$([string]$file.stage_name)"
        if ((Get-RemoteHash "$RemoteStaging/$([string]$file.stage_name)") -cne [string]$file.sha256) {
            throw "Transfert non conforme : $($file.source)"
        }
    }
    Copy-ToRemote (Join-Path $PackageRoot 'moonraker-section.conf') "$RemoteStaging/moonraker-section.conf"

    $builder = @"
from hashlib import sha256
from pathlib import Path
p = Path('$PrinterConfig')
data = p.read_bytes()
assert sha256(data).hexdigest() == '$([string]$manifest.baseline.printer_cfg_sha256)'
needle = b'[include k1-control-cfs-direct-owner-disabled-v1.cfg]\n'
lines = (b'[include k1-control-stock-derived-cycle-owner-disabled-v1.cfg]\n'
         b'[include k1-control-stock-geometry-handoff-disabled-v1.cfg]\n')
assert data.count(needle) == 1 and all(line not in data for line in lines.splitlines(True))
candidate = data.replace(needle, needle + lines, 1)
assert sha256(candidate).hexdigest() == '$([string]$manifest.installed.printer_cfg_sha256)'
p.with_suffix('.cfg.next').write_bytes(candidate)
m = Path('$MoonrakerConfig')
moon = m.read_bytes()
assert sha256(moon).hexdigest() == '$([string]$manifest.baseline.moonraker_conf_sha256)'
section = Path('$RemoteStaging/moonraker-section.conf').read_bytes().strip() + b'\n'
assert b'[k1_control_stock_cycle]' not in moon
if not moon.endswith(b'\n'):
    moon += b'\n'
if not moon.endswith(b'\n\n'):
    moon += b'\n'
moon_candidate = moon + section
assert sha256(moon_candidate).hexdigest() == '$([string]$manifest.installed.moonraker_conf_sha256)'
m.with_suffix('.conf.next').write_bytes(moon_candidate)
print('REMOTE_STOCK_DERIVED_HANDOFF_MOONRAKER_CONFIG_BUILD_OK')
"@
    $buildOutput = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $builder
    if (($buildOutput | Select-Object -Last 1) -cne 'REMOTE_STOCK_DERIVED_HANDOFF_MOONRAKER_CONFIG_BUILD_OK') {
        throw 'Construction distante des configurations invalide.'
    }

    foreach ($file in $manifest.files) {
        $destination = [string]$file.destination
        $staged = [string]$file.stage_name
        [void](Invoke-Remote "cp '$RemoteStaging/$staged' '$destination.next' && chmod 0644 '$destination.next' && mv '$destination.next' '$destination'")
    }
    [void](Invoke-Remote "mv '$PrinterConfig.next' '$PrinterConfig'")
    [void](Invoke-Remote "mv '$MoonrakerConfig.next' '$MoonrakerConfig'")
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    $before = Invoke-Admin 'generation'
    [void](Invoke-Admin 'restart')
    [void](Wait-KlipperTransition $before)
    [void](Invoke-Admin 'restore_mesh')
    $state = Invoke-DisabledValidation $manifest $PreflightRoute
    Save-Evidence 'deploy-result.json' ([ordered]@{
        capture_id = $CaptureId
        result = 'DEPLOY_STOCK_DERIVED_HANDOFF_MOONRAKER_INSTALL_DISABLED_V1_OK'
        klipper_owner_enabled = [bool]$state.klipper_owner.enabled
        geometry_handoff_enabled = [bool]$state.klipper_geometry.enabled
        moonraker_enabled = [bool]$state.moonraker.enabled
        effect_request_count = [int]$state.moonraker.effect_request_count
        route_preserved = $PreflightRoute
        physical_action = $false
        heat = $false
        motion = $false
        extrusion = $false
        cfs_frame = $false
        probe = $false
        mesh_recalculation = $false
    })
    Write-Output "DEPLOY_STOCK_DERIVED_HANDOFF_MOONRAKER_INSTALL_DISABLED_V1_OK capture=$CaptureId"
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
