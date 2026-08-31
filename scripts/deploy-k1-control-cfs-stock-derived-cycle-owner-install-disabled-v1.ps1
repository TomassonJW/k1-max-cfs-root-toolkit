[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',

    [string]$Gate,

    [ValidatePattern('^[0-9]{8}-[0-9]{6}-g4-k1-control-cfs-stock-derived-cycle-owner-install-disabled-v1$')]
    [string]$CaptureId,

    [string]$EvidenceDirectory,

    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'PowerShell 7 ou plus recent est obligatoire.'
}

$RequiredGate = 'G4-K1-CONTROL-CFS-STOCK-DERIVED-CYCLE-OWNER-INSTALL-DISABLED-V1'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\cfs-stock-derived-cycle-owner-install-disabled-v1'
$ManifestPath = Join-Path $PackageRoot 'deployment-manifest.json'
$RemoteAdmin = Join-Path $WorkspaceRoot 'packages\k1-control-v1\start-sequence-owner-v1\remote_admin.py'
$RemoteSourceValidator = Join-Path $PackageRoot 'remote_source_validate.py'
$RemoteDisabledValidator = Join-Path $PackageRoot 'remote_validate_disabled.py'

$PrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$DirectConfig = '/usr/data/printer_data/config/k1-control-cfs-direct-owner-disabled-v1.cfg'
$DirectComponent = '/usr/share/klipper/klippy/extras/k1_control_cfs_direct_owner.py'
$IntegratedConfig = '/usr/data/printer_data/config/k1-control-integrated-production-cycle-v1.cfg'
$ComponentPath = '/usr/share/klipper/klippy/extras/k1_control_stock_cycle_owner.py'
$RemoteRoot = '/usr/data/k1-control-v1'
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

function Assert-Package {
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ($manifest.gate -cne $RequiredGate -or
        [string]$manifest.status -cne 'offline_review_candidate_not_installed' -or
        $manifest.files.Count -ne 2) {
        throw 'Manifeste de pose stock-derived invalide.'
    }
    foreach ($file in @($manifest.files) + @($manifest.support_files) + @($manifest.preparation_evidence)) {
        $local = Join-Path $PackageRoot ([string]$file.source)
        [void](Assert-LocalPathInsideWorkspace $local)
        $actual = Get-LocalSha256 $local
        if ($actual -cne [string]$file.sha256) {
            throw "Fichier local non fige : $($file.source) hash=$actual"
        }
    }
    $deployer = Join-Path $WorkspaceRoot ([string]$manifest.deployer.source)
    [void](Assert-LocalPathInsideWorkspace $deployer)
    $deployerHash = Get-LocalSha256 $deployer
    if ($deployerHash -cne [string]$manifest.deployer.sha256) {
        throw "Deployer local non fige : $deployerHash"
    }
    $config = Join-Path $PackageRoot 'k1-control-stock-derived-cycle-owner-disabled-v1.cfg'
    $text = [IO.File]::ReadAllText($config).Replace("`r`n", "`n")
    if ($text -notmatch '(?m)^enabled:\s*false\s*$' -or
        $text -match '(?m)^enabled:\s*true\s*$' -or
        $text -match 'SET_GCODE_VARIABLE') {
        throw 'La configuration candidate ne reste pas immuablement desactivee.'
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
        $Value | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $path -Encoding utf8
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

function Assert-RemoteSource {
    $source = Join-Path $PackageRoot 'k1_control_stock_cycle_owner.py'
    $encoded = [Convert]::ToBase64String([IO.File]::ReadAllBytes($source))
    $program = [IO.File]::ReadAllText($RemoteSourceValidator).Replace('__SOURCE_B64__', $encoded).Replace("`r`n", "`n")
    $output = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $program
    $marker = $output | Select-Object -Last 1
    if ($marker -cne 'REMOTE_STOCK_DERIVED_CYCLE_SOURCE_VALIDATE_OK') {
        throw "Validation Python K1 du composant invalide : $($output -join "`n")"
    }
    Save-Evidence 'preflight-source-validate.txt' $marker
}

function Assert-ImmutableBase {
    param([Parameter(Mandatory = $true)]$Manifest)

    if ((Get-RemoteHash $PrinterConfig) -cne [string]$Manifest.baseline.printer_cfg_sha256 -or
        (Get-RemoteHash $DirectConfig) -cne [string]$Manifest.baseline.direct_owner_config_sha256 -or
        (Get-RemoteHash $DirectComponent) -cne [string]$Manifest.baseline.direct_owner_component_sha256 -or
        (Get-RemoteHash $IntegratedConfig) -cne [string]$Manifest.baseline.integrated_cycle_neutralized_sha256) {
        throw 'Une base distante revue a derive.'
    }
}

function Assert-Preflight {
    param([Parameter(Mandatory = $true)]$Manifest)

    Assert-ImmutableBase $Manifest
    foreach ($file in $Manifest.files) {
        [void](Invoke-Remote "test ! -e '$([string]$file.destination)'")
    }
    [void](Invoke-Remote "test `$(grep -c '^\[include k1-control-stock-derived-cycle-owner-disabled-v1.cfg\]$' '$PrinterConfig') -eq 0")
    $snapshot = Invoke-Admin 'snapshot'
    $script:PreflightRoute = Assert-SafeSnapshot $snapshot $Manifest
    Save-Evidence 'preflight-safe-state.json' $snapshot
    Save-Evidence 'preflight-route.txt' $script:PreflightRoute
    Assert-RemoteSource
}

function Invoke-DisabledValidation {
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [string]$ExpectedRoute
    )

    if ((Get-RemoteHash $PrinterConfig) -cne [string]$Manifest.printer_cfg.installed_sha256) {
        throw 'printer.cfg installe ne correspond pas au candidat.'
    }
    foreach ($file in $Manifest.files) {
        if ((Get-RemoteHash ([string]$file.destination)) -cne [string]$file.sha256) {
            throw "Payload distant non conforme : $($file.destination)"
        }
    }
    [void](Invoke-Remote "test `$(grep -c '^\[include k1-control-stock-derived-cycle-owner-disabled-v1.cfg\]$' '$PrinterConfig') -eq 1")
    $program = [IO.File]::ReadAllText($RemoteDisabledValidator).Replace("`r`n", "`n")
    $output = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $program
    if (($output | Select-Object -Last 1) -cne 'REMOTE_STOCK_DERIVED_CYCLE_DISABLED_VALIDATE_OK') {
        throw "Validation desactivee distante invalide : $($output -join "`n")"
    }
    $owner = ($output | Select-Object -First 1) | ConvertFrom-Json
    $snapshot = Invoke-Admin 'snapshot'
    [void](Assert-SafeSnapshot $snapshot $Manifest $ExpectedRoute)
    Save-Evidence 'validate-owner-disabled.json' $owner
    Save-Evidence 'validate-safe-state.json' $snapshot
    return $owner
}

function Remove-RemotePayload {
    param([Parameter(Mandatory = $true)]$Manifest)

    foreach ($file in $Manifest.files) {
        $path = [string]$file.destination
        [void](Invoke-Remote "rm -f '$path'")
    }
    [void](Invoke-Remote "rm -f '/usr/share/klipper/klippy/extras/__pycache__/k1_control_stock_cycle_owner.'*.pyc")
}

function Invoke-ExactRollback {
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [Parameter(Mandatory = $true)][string]$BackupDirectory,
        [string]$ExpectedRoute
    )

    [void](Invoke-Remote "test -f '$BackupDirectory/printer.cfg.before'")
    [void](Invoke-Remote "cp '$BackupDirectory/printer.cfg.before' '$PrinterConfig'")
    Remove-RemotePayload $Manifest
    $before = Invoke-Admin 'generation'
    [void](Invoke-Admin 'restart')
    [void](Wait-KlipperTransition $before)
    [void](Invoke-Admin 'restore_mesh')
    if ((Get-RemoteHash $PrinterConfig) -cne [string]$Manifest.printer_cfg.rollback_sha256) {
        throw 'Rollback printer.cfg non exact.'
    }
    Assert-ImmutableBase $Manifest
    $objects = @(Invoke-Admin 'objects')
    if ($objects -contains 'k1_control_stock_cycle_owner') {
        throw 'Objet stock-derived encore charge apres rollback.'
    }
    $snapshot = Invoke-Admin 'snapshot'
    [void](Assert-SafeSnapshot $snapshot $Manifest $ExpectedRoute)
    Save-Evidence 'rollback-safe-state.json' $snapshot
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "PLAN_CFS_STOCK_DERIVED_CYCLE_OWNER_INSTALL_DISABLED_V1_OK gate=$RequiredGate"
    Write-Output 'Pose: deux fichiers, un include, un RESTART Klipper, remise du 11x11; enabled=false.'
    Write-Output 'Effets pendant la pose: aucune chauffe, mouvement, extrusion, trame CFS ou commande stock.'
    Write-Output 'Rollback: printer.cfg exact, deux fichiers retires, RESTART Klipper et remise du meme mesh.'
    exit 0
}

Assert-ConnectionGate

if ($Action -eq 'Preflight') {
    Assert-Preflight $manifest
    Write-Output 'PREFLIGHT_CFS_STOCK_DERIVED_CYCLE_OWNER_INSTALL_DISABLED_V1_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    $snapshot = Invoke-Admin 'snapshot'
    $route = Assert-SafeSnapshot $snapshot $manifest
    [void](Invoke-DisabledValidation $manifest $route)
    Write-Output 'VALIDATE_CFS_STOCK_DERIVED_CYCLE_OWNER_INSTALL_DISABLED_V1_OK'
    exit 0
}

Assert-MutationGate
$RemoteBackup = "$RemoteRoot/backups/$CaptureId/stock-derived-cycle-install-disabled-v1"
$RemoteStaging = "$RemoteRoot/staging/$CaptureId-stock-derived-cycle-install-disabled-v1"

if ($Action -eq 'Rollback') {
    $snapshot = Invoke-Admin 'snapshot'
    $route = Get-RouteSignature $snapshot
    Invoke-ExactRollback $manifest $RemoteBackup $route
    Write-Output "ROLLBACK_CFS_STOCK_DERIVED_CYCLE_OWNER_INSTALL_DISABLED_V1_OK capture=$CaptureId"
    exit 0
}

Assert-Preflight $manifest

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup' '$RemoteStaging'")
    [void](Invoke-Remote "cp '$PrinterConfig' '$RemoteBackup/printer.cfg.before'")
    [void](Invoke-Remote "sha256sum '$PrinterConfig' '$DirectConfig' '$DirectComponent' '$IntegratedConfig' > '$RemoteBackup/checksums.sha256'")
    $MutationStarted = $true

    foreach ($file in $manifest.files) {
        $local = Join-Path $PackageRoot ([string]$file.source)
        $staged = ([string]$file.source).Replace('/', '__')
        Copy-ToRemote $local "$RemoteStaging/$staged"
        if ((Get-RemoteHash "$RemoteStaging/$staged") -cne [string]$file.sha256) {
            throw "Transfert non conforme : $($file.source)"
        }
    }

    $builder = @"
from hashlib import sha256
from pathlib import Path
p = Path('$PrinterConfig')
data = p.read_bytes()
assert sha256(data).hexdigest() == '$([string]$manifest.baseline.printer_cfg_sha256)'
needle = b'$([string]$manifest.printer_cfg.insert_after)\n'
line = b'$([string]$manifest.printer_cfg.add_line)\n'
assert data.count(needle) == 1
assert line not in data
candidate = data.replace(needle, needle + line, 1)
assert sha256(candidate).hexdigest() == '$([string]$manifest.printer_cfg.installed_sha256)'
p.with_suffix('.cfg.next').write_bytes(candidate)
print('REMOTE_STOCK_DERIVED_CYCLE_CONFIG_BUILD_OK')
"@
    $buildOutput = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $builder
    if (($buildOutput | Select-Object -Last 1) -cne 'REMOTE_STOCK_DERIVED_CYCLE_CONFIG_BUILD_OK') {
        throw 'Construction distante de printer.cfg invalide.'
    }

    foreach ($file in $manifest.files) {
        $destination = [string]$file.destination
        $staged = ([string]$file.source).Replace('/', '__')
        [void](Invoke-Remote "cp '$RemoteStaging/$staged' '$destination.next' && chmod 0644 '$destination.next' && mv '$destination.next' '$destination'")
    }
    [void](Invoke-Remote "mv '$PrinterConfig.next' '$PrinterConfig'")
    $before = Invoke-Admin 'generation'
    [void](Invoke-Admin 'restart')
    [void](Wait-KlipperTransition $before)
    [void](Invoke-Admin 'restore_mesh')
    $owner = Invoke-DisabledValidation $manifest $PreflightRoute
    Save-Evidence 'deploy-result.json' ([ordered]@{
        capture_id = $CaptureId
        result = 'DEPLOY_CFS_STOCK_DERIVED_CYCLE_OWNER_INSTALL_DISABLED_V1_OK'
        enabled = [bool]$owner.enabled
        effect_count = [int]$owner.effect_count
        command_count = [int]$owner.command_count
        route_preserved = $PreflightRoute
        physical_action = $false
        heater_command = $false
        cfs_frame = $false
    })
    Write-Output "DEPLOY_CFS_STOCK_DERIVED_CYCLE_OWNER_INSTALL_DISABLED_V1_OK capture=$CaptureId"
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
