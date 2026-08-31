[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Plan', 'Preflight', 'Activate', 'PrepareClear', 'Load', 'Unload', 'Deactivate', 'Validate')]
    [string]$Action,

    [ValidatePattern('^[0-9]{8}-[0-9]{6}-g4-k1-control-cfs-direct-owner-physical-load-unload-v1$')]
    [string]$CaptureId,

    [string]$Gate,
    [switch]$Execute,
    [string]$PrinterHost = 'k1max-root'
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'PowerShell 7 ou plus recent est obligatoire.'
}

$Mission = 'G4-K1-CONTROL-CFS-DIRECT-OWNER-PHYSICAL-LOAD-UNLOAD-V1'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$ManifestPath = Join-Path $PSScriptRoot 'deployment-manifest.json'
$RemotePhasePath = Join-Path $PSScriptRoot 'remote_phase.py'
$ActiveConfigPath = Join-Path $PSScriptRoot 'k1-control-cfs-direct-owner-active-physical-v1.cfg'
$DisabledConfigPath = Join-Path $WorkspaceRoot 'packages\k1-control-v1\cfs-direct-owner-install-disabled-v1\k1-control-cfs-direct-owner-disabled-v1.cfg'
$RemoteAdminPath = Join-Path $WorkspaceRoot 'packages\k1-control-v1\start-sequence-owner-v1\remote_admin.py'
$RemoteConfig = '/usr/data/printer_data/config/k1-control-cfs-direct-owner-disabled-v1.cfg'
$RemoteComponent = '/usr/share/klipper/klippy/extras/k1_control_cfs_direct_owner.py'
$RemoteRoot = '/usr/data/k1-control-v1'
$SshOptions = @(
    '-o', 'BatchMode=yes',
    '-o', 'PasswordAuthentication=no',
    '-o', 'KbdInteractiveAuthentication=no',
    '-o', 'ConnectTimeout=8',
    '-o', 'ServerAliveInterval=10',
    '-o', 'ServerAliveCountMax=35'
)

function Get-LocalSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-InWorkspace {
    param([Parameter(Mandatory = $true)][string]$Path)
    $resolved = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
    if (-not $resolved.StartsWith(
            $WorkspaceRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase
        )) {
        throw "Chemin hors workspace : $resolved"
    }
    return $resolved
}

function Assert-Package {
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ($manifest.mission -cne $Mission -or
        $manifest.status -cne 'closed_ko_before_filament_effect') {
        throw 'Manifeste de gate physique invalide.'
    }
    foreach ($item in $manifest.local_files) {
        $path = Join-Path $WorkspaceRoot ([string]$item.path).Replace('/', '\')
        [void](Assert-InWorkspace $path)
        if ((Get-LocalSha256 $path) -cne [string]$item.sha256) {
            throw "Fichier local non fige : $($item.path)"
        }
    }
    return $manifest
}

function Assert-Authority {
    if (-not $Execute -or $Gate -cne $Mission) {
        throw "Action refusee : -Execute et -Gate '$Mission' sont obligatoires."
    }
    if (-not $CaptureId) {
        throw 'CaptureId obligatoire pour toute connexion K1.'
    }
}

function Get-EvidenceDirectory {
    $rawRoot = (Resolve-Path (Join-Path $WorkspaceRoot 'inventory\raw')).Path
    $directory = Join-Path $rawRoot $CaptureId
    if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
        New-Item -ItemType Directory -Path $directory -ErrorAction Stop | Out-Null
    }
    $resolved = (Resolve-Path -LiteralPath $directory).Path
    if (-not $resolved.StartsWith(
            $rawRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase
        )) {
        throw 'Capture hors inventory/raw.'
    }
    return $resolved
}

function Save-Json {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Value
    )
    $directory = Get-EvidenceDirectory
    $path = Join-Path $directory $Name
    if (Test-Path -LiteralPath $path) {
        throw "Preuve deja presente : $Name"
    }
    $Value | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $path -Encoding utf8
}

function Invoke-Remote {
    param([Parameter(Mandatory = $true)][string]$Command)
    $output = & ssh.exe @SshOptions $PrinterHost $Command 2>&1
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
    $output = $StandardInput | & ssh.exe @SshOptions $PrinterHost $Command 2>&1
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
    $resolved = Assert-InWorkspace $Source
    $output = & scp.exe '-O' @SshOptions $resolved "${PrinterHost}:$Destination" 2>&1
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
    param([Parameter(Mandatory = $true)][ValidateSet('generation', 'snapshot', 'restart', 'restore_mesh')][string]$AdminAction)
    $program = [IO.File]::ReadAllText($RemoteAdminPath).Replace("`r`n", "`n")
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

function Invoke-Phase {
    param(
        [Parameter(Mandatory = $true)][string]$Phase,
        [Parameter(Mandatory = $true)][string]$EvidenceName
    )
    $program = [IO.File]::ReadAllText($RemotePhasePath).Replace("`r`n", "`n")
    $output = $program | & ssh.exe @SshOptions $PrinterHost "/usr/share/klippy-env/bin/python -B - '$Phase' '$CaptureId'" 2>&1
    $exitCode = $LASTEXITCODE
    $jsonLine = $output | Where-Object { $_ -match '^\{' } | Select-Object -First 1
    if (-not $jsonLine) {
        throw "Phase $Phase sans resultat JSON (code $exitCode).`n$($output -join "`n")"
    }
    $result = $jsonLine | ConvertFrom-Json
    Save-Json "$EvidenceName.json" $result
    if ($exitCode -ne 0 -or [string]$result.status -like 'CLOSED_KO*') {
        throw "Phase $Phase KO (code $exitCode) : $($result.reason)"
    }
    return $result
}

function Assert-RemoteBase {
    param([Parameter(Mandatory = $true)]$Manifest)
    foreach ($item in $Manifest.remote_baseline.PSObject.Properties) {
        if ((Get-RemoteHash ([string]$item.Value.path)) -cne [string]$item.Value.sha256) {
            throw "Base distante derivee : $($item.Name)"
        }
    }
}

function Set-RemoteConfig {
    param(
        [Parameter(Mandatory = $true)][string]$LocalPath,
        [Parameter(Mandatory = $true)][string]$ExpectedHash,
        [Parameter(Mandatory = $true)][string]$RemoteStaging
    )
    Copy-ToRemote $LocalPath $RemoteStaging
    if ((Get-RemoteHash $RemoteStaging) -cne $ExpectedHash) {
        throw 'Config transferee non conforme.'
    }
    [void](Invoke-Remote "cp '$RemoteStaging' '$RemoteConfig.next' && chmod 0644 '$RemoteConfig.next' && mv '$RemoteConfig.next' '$RemoteConfig'")
    if ((Get-RemoteHash $RemoteConfig) -cne $ExpectedHash) {
        throw 'Config distante remplacee non conforme.'
    }
}

function Restart-And-RestoreMesh {
    $before = Invoke-Admin 'generation'
    [void](Invoke-Admin 'restart')
    [void](Wait-KlipperTransition $before)
    [void](Invoke-Admin 'restore_mesh')
}

function Invoke-DeactivateInternal {
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [Parameter(Mandatory = $true)][bool]$RequireClear
    )
    $directory = Get-EvidenceDirectory
    $remoteStaging = "$RemoteRoot/staging/$CaptureId-cfs-direct-owner-physical/disabled.cfg"
    try { [void](Invoke-Phase 'shutdown' 'deactivate-shutdown') } catch {}
    [void](Invoke-Remote "mkdir -p '$RemoteStagingRoot'")
    Set-RemoteConfig $DisabledConfigPath ([string]$Manifest.disabled_config_sha256) $remoteStaging
    Restart-And-RestoreMesh
    $snapshotResult = Invoke-Phase 'snapshot' 'deactivate-snapshot'
    if ([int]$snapshotResult.snapshot.box.auto_refill -eq 0) {
        [void](Invoke-Phase 'restore_auto_refill' 'deactivate-auto-refill-restored')
    }
    [void](Invoke-Phase 'preflight' 'deactivate-disabled-preflight')
    if ($RequireClear) {
        [void](Invoke-Phase 'final_validate' 'deactivate-final-validate')
    }
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "CLOSED_KO_CFS_DIRECT_OWNER_PHYSICAL_LOAD_UNLOAD_V1 gate=$Mission"
    Write-Output 'Ne jamais rejouer V1 : le retrait sans cutter et le chargement sans purge ne respectent pas le cycle produit.'
    Write-Output 'Aucun effet filament V1 n a eu lieu ; le proprietaire distant est revenu desactive.'
    exit 0
}

throw 'V1 close KO et rendue non executable : cutter avant retrait, puis purge bac et 3 a 4 allers-retours apres chargement sont obligatoires.'

Assert-Authority
[void](Get-EvidenceDirectory)
$remoteBackup = "$RemoteRoot/backups/$CaptureId/cfs-direct-owner-physical-load-unload-v1"
$remoteStagingRoot = "$RemoteRoot/staging/$CaptureId-cfs-direct-owner-physical"

if ($Action -eq 'Preflight') {
    Assert-RemoteBase $manifest
    [void](Invoke-Phase 'preflight' 'preflight-fresh')
    Write-Output "PREFLIGHT_CFS_DIRECT_OWNER_PHYSICAL_LOAD_UNLOAD_V1_OK capture=$CaptureId"
    exit 0
}

if ($Action -eq 'Activate') {
    $mutationStarted = $false
    try {
        Assert-RemoteBase $manifest
        [void](Invoke-Phase 'preflight' 'activate-preflight-disabled')
        [void](Invoke-Remote "mkdir -p '$remoteBackup' '$remoteStagingRoot'")
        [void](Invoke-Remote "cp '$RemoteConfig' '$remoteBackup/disabled.cfg.before'")
        if ((Get-RemoteHash "$remoteBackup/disabled.cfg.before") -cne [string]$manifest.disabled_config_sha256) {
            throw 'Backup de la configuration desactivee non exact.'
        }
        $mutationStarted = $true
        [void](Invoke-Phase 'disable_auto_refill' 'activate-auto-refill-disabled')
        Set-RemoteConfig $ActiveConfigPath ([string]$manifest.active_config_sha256) "$remoteStagingRoot/active.cfg"
        Restart-And-RestoreMesh
        [void](Invoke-Phase 'active_preflight' 'activate-active-preflight')
        Write-Output "ACTIVATE_CFS_DIRECT_OWNER_PHYSICAL_LOAD_UNLOAD_V1_OK capture=$CaptureId"
    }
    catch {
        $failure = $_
        if ($mutationStarted) {
            try { Invoke-DeactivateInternal $manifest $false }
            catch { throw "Activation KO: $($failure.Exception.Message) ; retour desactive KO: $($_.Exception.Message)" }
        }
        throw $failure
    }
    exit 0
}

if ($Action -in @('PrepareClear', 'Load', 'Unload')) {
    $phase = $Action.ToLowerInvariant()
    if ($Action -eq 'PrepareClear') { $phase = 'prepare_clear' }
    $activeConfirmed = $false
    try {
        if ((Get-RemoteHash $RemoteConfig) -cne [string]$manifest.active_config_sha256) {
            throw 'Le proprietaire actif exact n est pas installe.'
        }
        $activeConfirmed = $true
        [void](Invoke-Phase $phase $phase)
        Write-Output "$($Action.ToUpperInvariant())_CFS_DIRECT_OWNER_PHYSICAL_LOAD_UNLOAD_V1_OK capture=$CaptureId"
    }
    catch {
        $failure = $_
        if ($activeConfirmed) {
            try { Invoke-DeactivateInternal $manifest $false }
            catch { throw "Phase $Action KO: $($failure.Exception.Message) ; retour desactive KO: $($_.Exception.Message)" }
        }
        throw $failure
    }
    exit 0
}

if ($Action -eq 'Deactivate') {
    Invoke-DeactivateInternal $manifest $true
    Write-Output "DEACTIVATE_CFS_DIRECT_OWNER_PHYSICAL_LOAD_UNLOAD_V1_OK capture=$CaptureId"
    exit 0
}

if ($Action -eq 'Validate') {
    Assert-RemoteBase $manifest
    [void](Invoke-Phase 'final_validate' 'validate-final')
    Write-Output "VALIDATE_CFS_DIRECT_OWNER_PHYSICAL_LOAD_UNLOAD_V1_OK capture=$CaptureId"
    exit 0
}
