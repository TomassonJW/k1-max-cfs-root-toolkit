[CmdletBinding()]
param(
    [ValidateSet('Plan','Deploy','Validate','Rollback')]
    [string]$Action = 'Plan',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-stock-cutter-route-guard-hotfix-v1',
    [string]$EvidenceDirectory = '',
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 ou plus recent est obligatoire.' }

$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ManifestPath = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-cutter-route-guard-hotfix-v1\manifest.json'
$SnapshotDriver = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-cycle-activation-v1\remote_forward_purge_recovery.py'
$SshTarget = 'k1max-root'
$SshOptions = @('-o','BatchMode=yes','-o','PasswordAuthentication=no','-o','KbdInteractiveAuthentication=no','-o','ConnectTimeout=8')
$Service = '/etc/init.d/S56k1_control_moonraker'
$RunState = '/usr/data/k1-control-v1/state/stock-derived-cycle-state.json'
$RemoteBackup = "/usr/data/k1-control-v1/backups/$CaptureId/stock-cutter-route-guard-hotfix-v1"
$RemoteStaging = "/usr/data/k1-control-v1/staging/$CaptureId-stock-cutter-route-guard-hotfix-v1.py"
$MutationStarted = $false
if (-not $EvidenceDirectory) { $EvidenceDirectory = Join-Path $WorkspaceRoot "inventory\raw\$CaptureId" }

function Assert-InWorkspace {
    param([Parameter(Mandatory=$true)][string]$Path)
    $resolved = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
    if (-not $resolved.StartsWith($WorkspaceRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Chemin hors workspace : $resolved"
    }
    return $resolved
}

function Save-Evidence {
    param([Parameter(Mandatory=$true)][string]$Name, [Parameter(Mandatory=$true)]$Value)
    New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null
    $path = Join-Path (Assert-InWorkspace $EvidenceDirectory) $Name
    $Value | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $path -Encoding utf8NoBOM
}

function Invoke-Remote {
    param([Parameter(Mandatory=$true)][string]$Command)
    $output = & ssh.exe @SshOptions $SshTarget $Command 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Commande distante KO : $Command`n$($output -join "`n")" }
    return @($output)
}

function Invoke-RemoteStdin {
    param([Parameter(Mandatory=$true)][string]$Command, [Parameter(Mandatory=$true)][string]$InputText)
    $output = $InputText | & ssh.exe @SshOptions $SshTarget $Command 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Commande distante stdin KO : $Command`n$($output -join "`n")" }
    return @($output)
}

function Copy-ToRemote {
    param([Parameter(Mandatory=$true)][string]$Source, [Parameter(Mandatory=$true)][string]$Destination)
    $resolved = Assert-InWorkspace $Source
    $output = & scp.exe '-O' @SshOptions $resolved "${SshTarget}:$Destination" 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Transfert KO : $resolved -> $Destination`n$($output -join "`n")" }
}

function Get-RemoteHash {
    param([Parameter(Mandatory=$true)][string]$Path)
    return ((((Invoke-Remote "sha256sum '$Path'") | Select-Object -First 1) -split '\s+')[0]).ToLowerInvariant()
}

function Get-Status {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/stock-cycle/status'") -join "`n"
    $payload = $raw | ConvertFrom-Json
    if (-not $payload.result) { throw 'Etat stock-cycle absent.' }
    return $payload.result
}

function Get-Physical {
    $program = [IO.File]::ReadAllText($SnapshotDriver).Replace("`r`n","`n")
    $output = Invoke-RemoteStdin "/usr/share/klippy-env/bin/python -B - 'snapshot'" $program
    return (($output -join "`n") | ConvertFrom-Json)
}

function Wait-Service {
    for ($attempt=1; $attempt -le 60; $attempt++) {
        try { [void](Get-Status); return } catch { Start-Sleep -Seconds 1 }
    }
    throw 'K1 Control ne repond pas apres restart.'
}

function Assert-PhysicalUnchanged {
    param([Parameter(Mandatory=$true)]$Physical)
    if ($Physical.webhooks.state -cne 'ready' -or $Physical.print_state -cne 'standby' -or
        [double]$Physical.extruder.target -ne 0.0 -or [double]$Physical.heater_bed.target -ne 0.0 -or
        [string]$Physical.toolhead.homed_axes -ne '' -or
        $Physical.mesh_profile -cne 'k1_p001_t055_r001_n11x11' -or
        $Physical.sensors.head -ne $true -or $Physical.sensors.after_cutter -ne $true -or
        $Physical.direct_owner.active_route -cne 'T1A' -or $Physical.direct_owner.phase -cne 'loaded') {
        throw 'Etat physique T1A charge inattendu.'
    }
}

function Assert-Preflight {
    param([Parameter(Mandatory=$true)]$Manifest)
    if ((Get-RemoteHash ([string]$Manifest.component.destination)) -cne [string]$Manifest.component.before_sha256) {
        throw 'Composant distant de depart inattendu.'
    }
    $status = Get-Status
    $physical = Get-Physical
    if ($status.phase -cne 'preclean_unload_ready' -or
        $status.last_failure -cne 'cutter_access_reference_invalid' -or
        [int]$status.effect_dispatch_count -ne 0 -or $status.active_route -cne 'T1A' -or
        $status.filament_loaded -ne $true -or $status.run_state_present -ne $true -or
        [double]$status.selected.job.purge_mm -ne 140.0) {
        throw 'Etat du refus avant coupe inattendu.'
    }
    Assert-PhysicalUnchanged $physical
    Save-Evidence 'preflight-cycle-refusal.json' $status
    Save-Evidence 'preflight-physical.json' $physical
}

function Assert-Installed {
    param([Parameter(Mandatory=$true)]$Manifest)
    if ((Get-RemoteHash ([string]$Manifest.component.destination)) -cne [string]$Manifest.component.after_sha256) {
        throw 'Composant corrige absent.'
    }
    $status = Get-Status
    $physical = Get-Physical
    if ($status.phase -cne 'idle' -or $status.run_state_present -ne $false -or
        [int]$status.effect_dispatch_count -ne 0 -or [double]$status.selected.job.purge_mm -ne 140.0) {
        throw 'Cycle non revenu au repos avec la selection conservee.'
    }
    Assert-PhysicalUnchanged $physical
    Save-Evidence 'validate-cycle-idle-selected.json' $status
    Save-Evidence 'validate-physical.json' $physical
}

function Restore-Backup {
    param([Parameter(Mandatory=$true)]$Manifest)
    try { [void](Invoke-Remote "'$Service' stop") } catch {}
    $backup = "$RemoteBackup/k1_control_stock_cycle.py.before"
    if ((Get-RemoteHash $backup) -cne [string]$Manifest.component.before_sha256) { throw 'Backup composant invalide.' }
    [void](Invoke-Remote "cp '$backup' '$($Manifest.component.destination).next'")
    [void](Invoke-Remote "chmod 0644 '$($Manifest.component.destination).next'")
    [void](Invoke-Remote "mv '$($Manifest.component.destination).next' '$($Manifest.component.destination)'")
    [void](Invoke-Remote "cp '$RemoteBackup/run-state.before' '$RunState'")
    [void](Invoke-Remote "'$Service' start")
    Wait-Service
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$localComponent = Assert-InWorkspace (Join-Path $WorkspaceRoot ([string]$manifest.component.source))
$localHash = (Get-FileHash -LiteralPath $localComponent -Algorithm SHA256).Hash.ToLowerInvariant()
if ($localHash -cne [string]$manifest.component.after_sha256) { throw "Composant local non fige : $localHash" }

if ($Action -eq 'Plan') {
    Write-Output 'PLAN_STOCK_CUTTER_ROUTE_GUARD_HOTFIX_V1_OK'
    Write-Output 'Route directe exigee inchangee pendant la reference X/Y; restart K1 Control uniquement; aucun effet physique.'
    exit 0
}
if (-not $Execute) { throw 'Le parametre -Execute est obligatoire.' }
if ($Action -eq 'Validate') {
    Assert-Installed $manifest
    Write-Output "VALIDATE_STOCK_CUTTER_ROUTE_GUARD_HOTFIX_V1_OK capture=$CaptureId"
    exit 0
}
if ($Action -eq 'Rollback') {
    Restore-Backup $manifest
    Write-Output "ROLLBACK_STOCK_CUTTER_ROUTE_GUARD_HOTFIX_V1_OK capture=$CaptureId"
    exit 0
}

Assert-Preflight $manifest
try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup'")
    [void](Invoke-Remote "mkdir -p '$(Split-Path -Parent $RemoteStaging)'")
    [void](Invoke-Remote "cp '$($manifest.component.destination)' '$RemoteBackup/k1_control_stock_cycle.py.before'")
    [void](Invoke-Remote "cp '$RunState' '$RemoteBackup/run-state.before'")
    Copy-ToRemote $localComponent $RemoteStaging
    if ((Get-RemoteHash $RemoteStaging) -cne [string]$manifest.component.after_sha256) { throw 'Staging invalide.' }
    [void](Invoke-Remote "'/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' -B -m py_compile '$RemoteStaging'")
    $MutationStarted = $true
    [void](Invoke-Remote "'$Service' stop")
    [void](Invoke-Remote "mv '$RunState' '$RemoteBackup/run-state.quarantined'")
    [void](Invoke-Remote "cp '$RemoteStaging' '$($manifest.component.destination).next'")
    [void](Invoke-Remote "chmod 0644 '$($manifest.component.destination).next'")
    [void](Invoke-Remote "mv '$($manifest.component.destination).next' '$($manifest.component.destination)'")
    [void](Invoke-Remote "'$Service' start")
    Wait-Service
    Assert-Installed $manifest
    Save-Evidence 'deploy-result.json' ([ordered]@{
        result = 'DEPLOY_STOCK_CUTTER_ROUTE_GUARD_HOTFIX_V1_OK'
        capture_id = $CaptureId
        dedicated_moonraker_restart = 1
        klipper_restart = 0
        heat = $false; motion = $false; filament = $false; cfs_frame = $false; probe = $false
    })
    Write-Output "DEPLOY_STOCK_CUTTER_ROUTE_GUARD_HOTFIX_V1_OK capture=$CaptureId"
} catch {
    $failure = $_
    if ($MutationStarted) {
        try { Restore-Backup $manifest }
        catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
