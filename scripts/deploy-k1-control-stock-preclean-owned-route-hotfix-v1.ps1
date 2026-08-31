[CmdletBinding()]
param(
    [ValidateSet('Plan','Deploy','Validate','Rollback')]
    [string]$Action = 'Plan',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-stock-preclean-owned-route-hotfix-v1',
    [string]$EvidenceDirectory = '',
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 ou plus recent est obligatoire.' }

$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ManifestPath = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-preclean-owned-route-hotfix-v1\manifest.json'
$RemoteAdmin = Join-Path $WorkspaceRoot 'packages\k1-control-v1\start-sequence-owner-v1\remote_admin.py'
$RestoreZ = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-cycle-activation-v1\remote_restore_accepted_z.py'
$PhysicalDriver = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-cycle-activation-v1\remote_forward_purge_recovery.py'
$FinalizeDriver = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-cycle-activation-v1\remote_err8_load_tail_recovery.py'
$SshTarget = 'k1max-root'
$SshOptions = @('-o','BatchMode=yes','-o','PasswordAuthentication=no','-o','KbdInteractiveAuthentication=no','-o','ConnectTimeout=8')
$MoonrakerService = '/etc/init.d/S56k1_control_moonraker'
$KlipperService = '/etc/init.d/S55klipper_service'
$RunState = '/usr/data/k1-control-v1/state/stock-derived-cycle-state.json'
$RemoteBackup = "/usr/data/k1-control-v1/backups/$CaptureId/stock-preclean-owned-route-hotfix-v1"
$RemoteStaging = "/usr/data/k1-control-v1/staging/$CaptureId-stock-preclean-owned-route-hotfix-v1"
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
    if ($Value -is [string]) {
        [IO.File]::WriteAllText($path, $Value, (New-Object Text.UTF8Encoding($false)))
    } else {
        $Value | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $path -Encoding utf8NoBOM
    }
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

function Get-CycleStatus {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/stock-cycle/status'") -join "`n"
    $payload = $raw | ConvertFrom-Json
    if (-not $payload.result) { throw 'Etat stock-cycle absent.' }
    return $payload.result
}

function Get-Physical {
    $program = [IO.File]::ReadAllText($PhysicalDriver).Replace("`r`n","`n")
    $output = Invoke-RemoteStdin "/usr/share/klippy-env/bin/python -B - 'snapshot'" $program
    return (($output -join "`n") | ConvertFrom-Json)
}

function Invoke-Admin {
    param([Parameter(Mandatory=$true)][ValidateSet('generation','snapshot','restore_mesh')][string]$Name)
    $program = [IO.File]::ReadAllText($RemoteAdmin).Replace("`r`n","`n")
    $output = Invoke-RemoteStdin "/usr/share/klippy-env/bin/python -B - '$Name'" $program
    return (($output -join "`n") | ConvertFrom-Json)
}

function Wait-Moonraker {
    for ($attempt=1; $attempt -le 60; $attempt++) {
        try { [void](Get-CycleStatus); return } catch { Start-Sleep -Seconds 1 }
    }
    throw 'K1 Control ne repond pas apres restart.'
}

function Wait-KlipperTransition {
    param([Parameter(Mandatory=$true)]$Before)
    Start-Sleep -Seconds 2
    $readyReads = 0
    for ($attempt=1; $attempt -le 90; $attempt++) {
        try {
            $generation = Invoke-Admin 'generation'
            $changed = ([long]$generation.socket_inode -ne [long]$Before.socket_inode) -or
                ([long]$generation.socket_mtime_ns -ne [long]$Before.socket_mtime_ns)
            if ($changed) {
                $snapshot = Invoke-Admin 'snapshot'
                if ($snapshot.webhooks.state -ceq 'ready') {
                    $readyReads++
                    if ($readyReads -ge 2) { return }
                } else { $readyReads = 0 }
            }
        } catch { $readyReads = 0 }
        Start-Sleep -Seconds 1
    }
    throw 'Transition Klipper prete absente.'
}

function Restore-Z {
    $program = [IO.File]::ReadAllText($RestoreZ).Replace("`r`n","`n")
    $output = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $program
    if (($output | Select-Object -Last 1) -cne 'REMOTE_RESTORE_ACCEPTED_Z_NO_MOVE_OK') { throw 'Z accepte non restaure.' }
    Save-Evidence 'restore-z-no-move.txt' ($output -join "`n")
}

function Restart-KlipperAndReassociate {
    $before = Invoke-Admin 'generation'
    [void](Invoke-Remote "'$KlipperService' restart")
    Wait-KlipperTransition $before
    [void](Invoke-Admin 'restore_mesh')
    Restore-Z
    $driver = [IO.File]::ReadAllText($FinalizeDriver).Replace("`r`n","`n")
    $output = Invoke-RemoteStdin "/usr/share/klippy-env/bin/python -B - 'finalize'" $driver
    $result = (($output -join "`n") | ConvertFrom-Json)
    if ($result.status -cne 'COMPLETED_BUFFER_MIDDLE_T1A_LATCHED' -or [int]$result.serial_motor_frame_count -ne 0) {
        throw 'Reassociation T1A sans moteur non prouvee.'
    }
    Save-Evidence 'reassociate-t1a-no-motor.json' $result
}

function Assert-Hashes {
    param([Parameter(Mandatory=$true)]$Manifest, [ValidateSet('before_sha256','after_sha256')][string]$Field)
    foreach ($file in $Manifest.files) {
        if ((Get-RemoteHash ([string]$file.destination)) -cne [string]$file.$Field) {
            throw "Empreinte distante inattendue : $($file.name)"
        }
    }
}

function Assert-Preflight {
    param([Parameter(Mandatory=$true)]$Manifest)
    Assert-Hashes $Manifest 'before_sha256'
    $cycle = Get-CycleStatus
    $physical = Get-Physical
    if ($cycle.phase -cne 'blocked_uncertain' -or $cycle.last_failure -cne 'effect_outcome_unknown_no_retry' -or
        [int]$cycle.effect_dispatch_count -ne 1 -or $cycle.active_route -cne 'T1A' -or
        $cycle.filament_loaded -ne $true -or [double]$cycle.selected.job.purge_mm -ne 140.0) {
        throw 'Etat de la reconciliation refusee inattendu.'
    }
    if ($physical.webhooks.state -cne 'ready' -or $physical.print_state -cne 'standby' -or
        [double]$physical.extruder.target -ne 0.0 -or [double]$physical.heater_bed.target -ne 0.0 -or
        [string]$physical.toolhead.homed_axes -ne '' -or $physical.sensors.head -ne $true -or
        $physical.sensors.after_cutter -ne $true -or $physical.direct_owner.active_route -cne 'T1A' -or
        $physical.direct_owner.phase -cne 'failed_safe' -or $physical.direct_owner.failure_code -cne 'phase_invalid') {
        throw 'Etat physique apres refus phase_invalid inattendu.'
    }
    Save-Evidence 'preflight-cycle-blocked.json' $cycle
    Save-Evidence 'preflight-physical.json' $physical
}

function Assert-Installed {
    param([Parameter(Mandatory=$true)]$Manifest)
    Assert-Hashes $Manifest 'after_sha256'
    $cycle = Get-CycleStatus
    $physical = Get-Physical
    $admin = Invoke-Admin 'snapshot'
    if ($cycle.phase -cne 'idle' -or $cycle.run_state_present -ne $false -or
        [int]$cycle.effect_dispatch_count -ne 0 -or [double]$cycle.selected.job.purge_mm -ne 140.0) {
        throw 'Cycle non revenu au repos avec selection 140 mm.'
    }
    if ($physical.webhooks.state -cne 'ready' -or $physical.print_state -cne 'standby' -or
        [double]$physical.extruder.target -ne 0.0 -or [double]$physical.heater_bed.target -ne 0.0 -or
        [string]$physical.toolhead.homed_axes -ne '' -or $physical.mesh_profile -cne 'k1_p001_t055_r001_n11x11' -or
        $physical.sensors.head -ne $true -or $physical.sensors.after_cutter -ne $true -or
        $physical.direct_owner.active_route -cne 'T1A' -or $physical.direct_owner.phase -cne 'loaded' -or
        [int]$physical.direct_owner.frames_sent_count -ne 3) {
        throw 'Etat T1A final non conforme.'
    }
    if ([int]$admin.runtime.accepted_z_valid -ne 1 -or
        [Math]::Abs([double]$admin.runtime.accepted_z_offset + 0.04) -gt 0.0005 -or
        [Math]::Abs([double]$admin.homing_origin[2] + 0.04) -gt 0.0005) {
        throw 'Z accepte final non conforme.'
    }
    Save-Evidence 'validate-cycle-idle.json' $cycle
    Save-Evidence 'validate-physical-t1a.json' $physical
    Save-Evidence 'validate-runtime.json' $admin
}

function Restore-Backup {
    param([Parameter(Mandatory=$true)]$Manifest)
    try { [void](Invoke-Remote "'$MoonrakerService' stop") } catch {}
    foreach ($file in $Manifest.files) {
        $backup = "$RemoteBackup/$($file.name).before"
        if ((Get-RemoteHash $backup) -cne [string]$file.before_sha256) { throw "Backup invalide : $($file.name)" }
        [void](Invoke-Remote "cp '$backup' '$($file.destination).next'")
        [void](Invoke-Remote "chmod 0644 '$($file.destination).next'")
        [void](Invoke-Remote "mv '$($file.destination).next' '$($file.destination)'")
    }
    [void](Invoke-Remote "cp '$RemoteBackup/run-state.before' '$RunState'")
    [void](Invoke-Remote "'$MoonrakerService' start")
    Wait-Moonraker
    Restart-KlipperAndReassociate
    Assert-Hashes $Manifest 'before_sha256'
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
foreach ($file in $manifest.files) {
    $local = Assert-InWorkspace (Join-Path $WorkspaceRoot ([string]$file.source))
    $hash = (Get-FileHash -LiteralPath $local -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -cne [string]$file.after_sha256) { throw "Payload local non fige : $($file.name) $hash" }
}

if ($Action -eq 'Plan') {
    Write-Output 'PLAN_STOCK_PRECLEAN_OWNED_ROUTE_HOTFIX_V1_OK'
    Write-Output 'Deux composants, run incertain mis en quarantaine, selection preservee, T1A reassocie sans moteur apres restart.'
    exit 0
}
if (-not $Execute) { throw 'Le parametre -Execute est obligatoire.' }
if ($Action -eq 'Validate') {
    Assert-Installed $manifest
    Write-Output "VALIDATE_STOCK_PRECLEAN_OWNED_ROUTE_HOTFIX_V1_OK capture=$CaptureId"
    exit 0
}
if ($Action -eq 'Rollback') {
    Restore-Backup $manifest
    Write-Output "ROLLBACK_STOCK_PRECLEAN_OWNED_ROUTE_HOTFIX_V1_OK capture=$CaptureId"
    exit 0
}

Assert-Preflight $manifest
try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup' '$RemoteStaging'")
    foreach ($file in $manifest.files) {
        [void](Invoke-Remote "cp '$($file.destination)' '$RemoteBackup/$($file.name).before'")
        $staged = "$RemoteStaging/$($file.name).py"
        Copy-ToRemote (Join-Path $WorkspaceRoot ([string]$file.source)) $staged
        if ((Get-RemoteHash $staged) -cne [string]$file.after_sha256) { throw "Staging invalide : $($file.name)" }
        [void](Invoke-Remote "'/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' -B -m py_compile '$staged'")
    }
    [void](Invoke-Remote "cp '$RunState' '$RemoteBackup/run-state.before'")
    $MutationStarted = $true
    [void](Invoke-Remote "'$MoonrakerService' stop")
    [void](Invoke-Remote "mv '$RunState' '$RemoteBackup/run-state.quarantined'")
    foreach ($file in $manifest.files) {
        $staged = "$RemoteStaging/$($file.name).py"
        [void](Invoke-Remote "cp '$staged' '$($file.destination).next'")
        [void](Invoke-Remote "chmod 0644 '$($file.destination).next'")
        [void](Invoke-Remote "mv '$($file.destination).next' '$($file.destination)'")
    }
    [void](Invoke-Remote "'$MoonrakerService' start")
    Wait-Moonraker
    Restart-KlipperAndReassociate
    Assert-Installed $manifest
    Save-Evidence 'deploy-result.json' ([ordered]@{
        result = 'DEPLOY_STOCK_PRECLEAN_OWNED_ROUTE_HOTFIX_V1_OK'
        capture_id = $CaptureId
        selected_purge_mm = 140.0
        route_reassociated = 'T1A'
        heat = $false; motion = $false; filament = $false; cfs_motor_frame = $false; probe = $false
    })
    Write-Output "DEPLOY_STOCK_PRECLEAN_OWNED_ROUTE_HOTFIX_V1_OK capture=$CaptureId"
} catch {
    $failure = $_
    if ($MutationStarted) {
        try { Restore-Backup $manifest }
        catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
