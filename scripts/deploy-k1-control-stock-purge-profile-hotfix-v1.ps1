[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-stock-purge-profile-hotfix-v1',
    [string]$EvidenceDirectory = '',
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 ou plus recent est obligatoire.' }

$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-purge-profile-hotfix-v1'
$ManifestPath = Join-Path $PackageRoot 'manifest.json'
$RemoteAdmin = Join-Path $WorkspaceRoot 'packages\k1-control-v1\start-sequence-owner-v1\remote_admin.py'
$RestoreZ = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-cycle-activation-v1\remote_restore_accepted_z.py'
$PhysicalSnapshot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-cycle-activation-v1\remote_forward_purge_recovery.py'
$FinalizeDriver = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-cycle-activation-v1\remote_err8_load_tail_recovery.py'
$SshTarget = 'k1max-root'
$SshOptions = @('-o','BatchMode=yes','-o','PasswordAuthentication=no','-o','KbdInteractiveAuthentication=no','-o','ConnectTimeout=8')
$MoonrakerService = '/etc/init.d/S56k1_control_moonraker'
$KlipperService = '/etc/init.d/S55klipper_service'
$RunState = '/usr/data/k1-control-v1/state/stock-derived-cycle-state.json'
$SelectionState = '/usr/data/k1-control-v1/state/stock-derived-selection.json'
$BestMesh = 'k1_p001_t055_r001_n11x11'
$MutationStarted = $false

if (-not $EvidenceDirectory) {
    $EvidenceDirectory = Join-Path $WorkspaceRoot "inventory\raw\$CaptureId"
}
$RemoteBackup = "/usr/data/k1-control-v1/backups/$CaptureId/stock-purge-profile-hotfix-v1"
$RemoteStaging = "/usr/data/k1-control-v1/staging/$CaptureId-stock-purge-profile-hotfix-v1"

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
    $line = Invoke-Remote "sha256sum '$Path'" | Select-Object -First 1
    return (($line -split '\s+')[0]).ToLowerInvariant()
}

function Get-CycleStatus {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/stock-cycle/status'") -join "`n"
    $payload = $raw | ConvertFrom-Json
    if (-not $payload.result) { throw 'Etat du cycle absent.' }
    return $payload.result
}

function Get-PhysicalSnapshot {
    $program = [IO.File]::ReadAllText($PhysicalSnapshot).Replace("`r`n", "`n")
    $output = Invoke-RemoteStdin "/usr/share/klippy-env/bin/python -B - 'snapshot'" $program
    return (($output -join "`n") | ConvertFrom-Json)
}

function Invoke-Admin {
    param([Parameter(Mandatory=$true)][ValidateSet('generation','snapshot','restore_mesh')][string]$Name)
    $program = [IO.File]::ReadAllText($RemoteAdmin).Replace("`r`n", "`n")
    $output = Invoke-RemoteStdin "/usr/share/klippy-env/bin/python -B - '$Name'" $program
    return (($output -join "`n") | ConvertFrom-Json)
}

function Restore-AcceptedZ {
    $program = [IO.File]::ReadAllText($RestoreZ).Replace("`r`n", "`n")
    $output = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $program
    if (($output | Select-Object -Last 1) -cne 'REMOTE_RESTORE_ACCEPTED_Z_NO_MOVE_OK') {
        throw "Z accepte non restaure : $($output -join "`n")"
    }
    Save-Evidence 'restore-z-no-move.txt' ($output -join "`n")
}

function Wait-Moonraker {
    for ($attempt=1; $attempt -le 60; $attempt++) {
        try {
            [void](Invoke-Remote "curl 'http://127.0.0.1:7125/server/info'")
            [void](Get-CycleStatus)
            return
        } catch { Start-Sleep -Seconds 1 }
    }
    throw 'Moonraker K1 Control ne repond pas apres restart.'
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
    throw 'Klipper ne presente pas une vraie transition prete.'
}

function Assert-LocalPackage {
    param([Parameter(Mandatory=$true)]$Manifest)
    foreach ($file in $Manifest.files) {
        $local = Assert-InWorkspace (Join-Path $WorkspaceRoot ([string]$file.source))
        $hash = (Get-FileHash -LiteralPath $local -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hash -cne [string]$file.after_sha256) { throw "Payload local non fige : $($file.name) $hash" }
    }
}

function Assert-Hashes {
    param([Parameter(Mandatory=$true)]$Manifest, [ValidateSet('before_sha256','after_sha256')][string]$Field)
    foreach ($file in $Manifest.files) {
        $actual = Get-RemoteHash ([string]$file.destination)
        if ($actual -cne [string]$file.$Field) { throw "Empreinte distante inattendue : $($file.name) $actual" }
    }
}

function Assert-PreflightState {
    param([Parameter(Mandatory=$true)]$Cycle, [Parameter(Mandatory=$true)]$Physical)
    if ($Cycle.phase -cne 'blocked_uncertain' -or
        $Cycle.last_failure -cne 'effect_outcome_unknown_no_retry' -or
        [double]$Cycle.selected.job.purge_mm -ne 20.0 -or
        $Cycle.active_route -cne 'T1A' -or $Cycle.filament_loaded -ne $true -or
        [int]$Cycle.effect_dispatch_count -ne 1 -or $Cycle.run_state_present -ne $true) {
        throw 'Ancien cycle bloque inattendu.'
    }
    if ($Physical.webhooks.state -cne 'ready' -or $Physical.print_state -cne 'standby' -or
        [double]$Physical.extruder.target -ne 0.0 -or [double]$Physical.heater_bed.target -ne 0.0 -or
        [string]$Physical.toolhead.homed_axes -ne '' -or $Physical.mesh_profile -cne $BestMesh -or
        [int]$Physical.box.auto_refill -ne 0 -or [string]$Physical.box.t_command -ne '' -or
        @($Physical.box.logical_routes).Count -ne 0 -or $Physical.sensors.head -ne $true -or
        $Physical.sensors.after_cutter -ne $true -or $Physical.direct_owner.phase -cne 'loaded' -or
        $Physical.direct_owner.active_route -cne 'T1A') {
        throw 'Etat physique T1A charge non conforme.'
    }
}

function Assert-InstalledState {
    param([Parameter(Mandatory=$true)]$Manifest)
    Assert-Hashes $Manifest 'after_sha256'
    $cycle = Get-CycleStatus
    $physical = Get-PhysicalSnapshot
    $admin = Invoke-Admin 'snapshot'
    if ($cycle.phase -cne 'idle' -or $cycle.run_state_present -ne $false -or
        [int]$cycle.effect_dispatch_count -ne 0 -or [int]$cycle.mesh_recalculation_count -ne 0 -or
        [int]$cycle.post_filament_probe_count -ne 0) {
        throw 'Le nouveau cycle n est pas neutre.'
    }
    if ($physical.webhooks.state -cne 'ready' -or $physical.print_state -cne 'standby' -or
        [double]$physical.extruder.target -ne 0.0 -or [double]$physical.heater_bed.target -ne 0.0 -or
        [string]$physical.toolhead.homed_axes -ne '' -or $physical.mesh_profile -cne $BestMesh -or
        $physical.sensors.head -ne $true -or $physical.sensors.after_cutter -ne $true -or
        $physical.direct_owner.phase -cne 'loaded' -or $physical.direct_owner.active_route -cne 'T1A' -or
        [int]$physical.direct_owner.frames_sent_count -ne 3) {
        throw 'T1A n est pas realloue sans moteur apres le restart.'
    }
    if ([int]$admin.runtime.accepted_z_valid -ne 1 -or
        [Math]::Abs([double]$admin.runtime.accepted_z_offset + 0.04) -gt 0.0005 -or
        [Math]::Abs([double]$admin.homing_origin[2] + 0.04) -gt 0.0005) {
        throw 'Le Z accepte -0,04 mm n est pas applique sans mouvement.'
    }
    $stateProbe = (Invoke-Remote "if [ -e '$RunState' ] || [ -e '$SelectionState' ]; then echo present; else echo absent; fi" | Select-Object -Last 1)
    if ($stateProbe -cne 'absent') { throw 'Un ancien etat de cycle reste actif.' }
    Save-Evidence 'validate-cycle-idle.json' $cycle
    Save-Evidence 'validate-physical-t1a.json' $physical
    Save-Evidence 'validate-runtime.json' $admin
}

function Restart-And-Reassociate {
    [void](Invoke-Remote "'$MoonrakerService' start")
    Wait-Moonraker
    $before = Invoke-Admin 'generation'
    [void](Invoke-Remote "'$KlipperService' restart")
    Wait-KlipperTransition $before
    [void](Invoke-Admin 'restore_mesh')
    Restore-AcceptedZ
    $driver = [IO.File]::ReadAllText($FinalizeDriver).Replace("`r`n", "`n")
    $output = Invoke-RemoteStdin "/usr/share/klippy-env/bin/python -B - 'finalize'" $driver
    $result = (($output -join "`n") | ConvertFrom-Json)
    if ($result.status -cne 'COMPLETED_BUFFER_MIDDLE_T1A_LATCHED' -or
        [int]$result.serial_motor_frame_count -ne 0) {
        throw 'Reassociation T1A sans moteur non prouvee.'
    }
    Save-Evidence 'reassociate-t1a-no-motor.json' $result
}

function Restore-FromBackup {
    param([Parameter(Mandatory=$true)]$Manifest)
    try { [void](Invoke-Remote "'$MoonrakerService' stop") } catch {}
    foreach ($file in $Manifest.files) {
        $backup = "$RemoteBackup/$($file.name).before"
        if ((Get-RemoteHash $backup) -cne [string]$file.before_sha256) { throw "Backup invalide : $($file.name)" }
        [void](Invoke-Remote "cp '$backup' '$($file.destination).next'")
        [void](Invoke-Remote "chmod 0644 '$($file.destination).next'")
        [void](Invoke-Remote "mv '$($file.destination).next' '$($file.destination)'")
    }
    if ((Invoke-Remote "if [ -f '$RemoteBackup/run-state.before' ]; then echo present; else echo absent; fi" | Select-Object -Last 1) -ceq 'present') {
        [void](Invoke-Remote "cp '$RemoteBackup/run-state.before' '$RunState'")
    }
    if ((Invoke-Remote "if [ -f '$RemoteBackup/selection-state.before' ]; then echo present; else echo absent; fi" | Select-Object -Last 1) -ceq 'present') {
        [void](Invoke-Remote "cp '$RemoteBackup/selection-state.before' '$SelectionState'")
    }
    Restart-And-Reassociate
    Assert-Hashes $Manifest 'before_sha256'
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
Assert-LocalPackage $manifest

if ($Action -eq 'Plan') {
    Write-Output 'PLAN_STOCK_PURGE_PROFILE_HOTFIX_V1_OK'
    Write-Output 'Purge initiale 140 mm, transitions Orca jusqu a 400 mm, ancien run mis en quarantaine, aucun mouvement pendant la pose.'
    exit 0
}
if (-not $Execute) { throw 'Le parametre -Execute est obligatoire pour une action distante.' }

if ($Action -eq 'Validate') {
    Assert-InstalledState $manifest
    Write-Output "VALIDATE_STOCK_PURGE_PROFILE_HOTFIX_V1_OK capture=$CaptureId"
    exit 0
}
if ($Action -eq 'Rollback') {
    Restore-FromBackup $manifest
    Write-Output "ROLLBACK_STOCK_PURGE_PROFILE_HOTFIX_V1_OK capture=$CaptureId"
    exit 0
}

$cycleBefore = Get-CycleStatus
$physicalBefore = Get-PhysicalSnapshot
Assert-PreflightState $cycleBefore $physicalBefore
Assert-Hashes $manifest 'before_sha256'
New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null
Save-Evidence 'preflight-cycle-blocked.json' $cycleBefore
Save-Evidence 'preflight-physical-t1a.json' $physicalBefore

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup'")
    [void](Invoke-Remote "mkdir -p '$RemoteStaging'")
    foreach ($file in $manifest.files) {
        [void](Invoke-Remote "cp '$($file.destination)' '$RemoteBackup/$($file.name).before'")
        $staged = "$RemoteStaging/$($file.name).py"
        Copy-ToRemote (Join-Path $WorkspaceRoot ([string]$file.source)) $staged
        if ((Get-RemoteHash $staged) -cne [string]$file.after_sha256) { throw "Staging invalide : $($file.name)" }
        [void](Invoke-Remote "/usr/share/klippy-env/bin/python -B -m py_compile '$staged'")
    }
    [void](Invoke-Remote "cp '$RunState' '$RemoteBackup/run-state.before'")
    [void](Invoke-Remote "cp '$SelectionState' '$RemoteBackup/selection-state.before'")
    $MutationStarted = $true
    [void](Invoke-Remote "'$MoonrakerService' stop")
    [void](Invoke-Remote "mv '$RunState' '$RemoteBackup/run-state.quarantined'")
    [void](Invoke-Remote "mv '$SelectionState' '$RemoteBackup/selection-state.quarantined'")
    foreach ($file in $manifest.files) {
        $staged = "$RemoteStaging/$($file.name).py"
        [void](Invoke-Remote "cp '$staged' '$($file.destination).next'")
        [void](Invoke-Remote "chmod 0644 '$($file.destination).next'")
        [void](Invoke-Remote "mv '$($file.destination).next' '$($file.destination)'")
    }
    Restart-And-Reassociate
    Assert-InstalledState $manifest
    Save-Evidence 'deploy-result.json' ([ordered]@{
        result = 'DEPLOY_STOCK_PURGE_PROFILE_HOTFIX_V1_OK'
        capture_id = $CaptureId
        initial_purge_mm = 140.0
        orca_transition_limit_mm = 400.0
        stale_run_quarantined = $true
        route_reassociated = 'T1A'
        heat = $false; motion = $false; extrusion = $false; probe = $false; mesh_recalculation = $false
    })
    Write-Output "DEPLOY_STOCK_PURGE_PROFILE_HOTFIX_V1_OK capture=$CaptureId"
} catch {
    $failure = $_
    try { Save-Evidence 'deploy-failure.txt' $failure.Exception.ToString() } catch {}
    if ($MutationStarted) {
        try { Restore-FromBackup $manifest }
        catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
