[CmdletBinding()]
param(
    [string]$CaptureId = '20260901-g4-k1-control-cfs-err8-load-tail-recovery-r3',
    [string]$EvidenceDirectory = 'inventory\raw\20260901-g4-k1-control-cfs-err8-load-tail-recovery-r3',
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 ou plus recent est obligatoire.' }
if (-not $Execute) { throw 'Cette pose exige -Execute.' }

$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$SnapshotDriver = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-cycle-activation-v1\remote_forward_purge_recovery.py'
$RemoteAdmin = Join-Path $WorkspaceRoot 'packages\k1-control-v1\start-sequence-owner-v1\remote_admin.py'
$RestoreZ = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-cycle-activation-v1\remote_restore_accepted_z.py'
$SshTarget = 'k1max-root'
$SshOptions = @('-o','BatchMode=yes','-o','PasswordAuthentication=no','-o','KbdInteractiveAuthentication=no','-o','ConnectTimeout=8')
$BestMesh = 'k1_p001_t055_r001_n11x11'
$MutationStarted = $false

$Files = @(
    [ordered]@{
        name = 'direct_core'
        local = Join-Path $WorkspaceRoot 'packages\k1-control-v1\cfs-direct-owner-offline-v1\owner.py'
        remote = '/usr/share/klipper/klippy/extras/k1_control_cfs_direct/owner.py'
        before = '93c3594512c1faca9030289f3d786bc513c9b6151270ecfc62f64a25f1d3aeeb'
        after = 'e9a0eca44cb2b87bd2a220c2c2ce13cc5dc9cd4870b519fc764a4d04070de031'
    },
    [ordered]@{
        name = 'direct_adapter'
        local = Join-Path $WorkspaceRoot 'packages\k1-control-v1\cfs-direct-owner-install-disabled-v1\k1_control_cfs_direct_owner.py'
        remote = '/usr/share/klipper/klippy/extras/k1_control_cfs_direct_owner.py'
        before = '3b3e9660ea40ebb559a360f39f0acc9b6ae83252502fcd92e7195cf804db14cd'
        after = '236d329a847ee02dd7b2ef259024b3485282db0e2a89668d35cc43553d784906'
    }
)

$ResolvedEvidence = [IO.Path]::GetFullPath((Join-Path $WorkspaceRoot $EvidenceDirectory))
if (-not $ResolvedEvidence.StartsWith($WorkspaceRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'EvidenceDirectory hors workspace.'
}
New-Item -ItemType Directory -Path $ResolvedEvidence -Force | Out-Null

function Save-Evidence {
    param([string]$Name, $Value)
    $path = Join-Path $ResolvedEvidence $Name
    if ($Value -is [string]) { $Value | Set-Content -LiteralPath $path -Encoding utf8 }
    else { $Value | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $path -Encoding utf8 }
}

function Invoke-Remote {
    param([string]$Command)
    $output = & ssh.exe @SshOptions $SshTarget $Command 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Commande distante KO : $Command`n$($output -join "`n")" }
    return @($output)
}

function Invoke-RemoteStdin {
    param([string]$Command, [string]$InputText)
    $output = $InputText | & ssh.exe @SshOptions $SshTarget $Command 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Commande distante stdin KO : $Command`n$($output -join "`n")" }
    return @($output)
}

function Copy-ToRemote {
    param([string]$Source, [string]$Destination)
    $resolved = (Resolve-Path -LiteralPath $Source -ErrorAction Stop).Path
    if (-not $resolved.StartsWith($WorkspaceRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Source hors workspace.'
    }
    $output = & scp.exe '-O' @SshOptions $resolved "${SshTarget}:$Destination" 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Transfert KO : $resolved -> $Destination`n$($output -join "`n")" }
}

function Get-RemoteHash {
    param([string]$Path)
    $line = Invoke-Remote "sha256sum '$Path'" | Select-Object -First 1
    return (($line -split '\s+')[0]).ToLowerInvariant()
}

function Get-Snapshot {
    $program = [IO.File]::ReadAllText($SnapshotDriver).Replace("`r`n","`n")
    $output = Invoke-RemoteStdin "/usr/share/klippy-env/bin/python -B - 'snapshot'" $program
    return (($output -join "`n") | ConvertFrom-Json)
}

function Invoke-Admin {
    param([ValidateSet('generation','restore_mesh')][string]$Name)
    $program = [IO.File]::ReadAllText($RemoteAdmin).Replace("`r`n","`n")
    $output = Invoke-RemoteStdin "/usr/share/klippy-env/bin/python -B - '$Name'" $program
    return (($output -join "`n") | ConvertFrom-Json)
}

function Assert-CommonSafeState {
    param($Snapshot)
    if ($Snapshot.webhooks.state -cne 'ready' -or $Snapshot.print_state -cne 'standby' -or
        [double]$Snapshot.extruder.target -ne 0.0 -or [double]$Snapshot.heater_bed.target -ne 0.0 -or
        [string]$Snapshot.toolhead.homed_axes -ne '' -or [string]$Snapshot.mesh_profile -cne $BestMesh -or
        $Snapshot.box.logical_routes.Count -ne 0 -or [string]$Snapshot.box.t_command -ne '' -or
        [int]$Snapshot.box.auto_refill -ne 0 -or $Snapshot.sensors.head -ne $true -or
        $Snapshot.sensors.after_cutter -ne $true -or $Snapshot.direct_owner.enabled -ne $true -or
        $Snapshot.direct_owner.stock_commands_blocked -ne $true) {
        throw 'Etat physique EXTRUDE_ERR8 non conforme.'
    }
}

function Wait-ReadyTransition {
    param($Before)
    Start-Sleep -Seconds 2
    for ($attempt=1; $attempt -le 90; $attempt++) {
        try {
            $now = Invoke-Admin 'generation'
            $changed = ([long]$now.socket_inode -ne [long]$Before.socket_inode) -or ([long]$now.socket_mtime_ns -ne [long]$Before.socket_mtime_ns)
            if ($changed) {
                $snapshot = Get-Snapshot
                if ($snapshot.webhooks.state -ceq 'ready') { return $snapshot }
            }
        } catch {}
        Start-Sleep -Seconds 1
    }
    throw 'Transition Klipper prete absente.'
}

function Restart-Restore {
    $generation = Invoke-Admin 'generation'
    [void](Invoke-Remote "'/etc/init.d/S55klipper_service' restart")
    [void](Wait-ReadyTransition $generation)
    [void](Invoke-Admin 'restore_mesh')
    $program = [IO.File]::ReadAllText($RestoreZ).Replace("`r`n","`n")
    $output = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $program
    if (($output | Select-Object -Last 1) -cne 'REMOTE_RESTORE_ACCEPTED_Z_NO_MOVE_OK') { throw 'Z accepte non restaure.' }
    Save-Evidence 'restore-z-no-move.txt' ($output -join "`n")
}

function Assert-Hashes {
    param([ValidateSet('before','after')][string]$Field)
    foreach ($file in $Files) {
        $actual = Get-RemoteHash $file.remote
        if ($actual -cne $file.$Field) { throw "Hash distant inattendu : $($file.name) $actual" }
    }
}

function Restore-Backups {
    param([string]$RemoteBackup)
    foreach ($file in $Files) {
        $backup = "$RemoteBackup/$($file.name).before"
        if ((Get-RemoteHash $backup) -cne $file.before) { throw "Backup invalide : $($file.name)" }
        [void](Invoke-Remote "cp '$backup' '$($file.remote).next'")
        [void](Invoke-Remote "mv '$($file.remote).next' '$($file.remote)'")
    }
    [void](Invoke-Remote "rm -f /usr/share/klipper/klippy/extras/__pycache__/k1_control_cfs_direct_owner.*.pyc")
    [void](Invoke-Remote "rm -f /usr/share/klipper/klippy/extras/k1_control_cfs_direct/__pycache__/owner.*.pyc")
    Restart-Restore
    Assert-Hashes 'before'
    $rollback = Get-Snapshot
    Assert-CommonSafeState $rollback
    Save-Evidence 'rollback-safe-state.json' $rollback
}

foreach ($file in $Files) {
    $localHash = (Get-FileHash -LiteralPath $file.local -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($localHash -cne $file.after) { throw "Payload local non fige : $($file.name) $localHash" }
}

$before = Get-Snapshot
Assert-CommonSafeState $before
if ($before.direct_owner.phase -cne 'failed_safe' -or $before.direct_owner.failure_code -cne 'buffer_not_middle_after_load' -or
    [int]$before.direct_owner.frames_sent_count -ne 9 -or $before.direct_owner.retained_head_segment -ne $true) {
    throw 'Etat sûr après prise locale absent.'
}
Assert-Hashes 'before'
Save-Evidence 'preflight-safe-state.json' $before

$RemoteBackup = "/usr/data/k1-control-v1/backups/$CaptureId/cfs-err8-load-tail-recovery-v1"
$RemoteStaging = "/usr/data/k1-control-v1/staging/$CaptureId-cfs-err8-load-tail-recovery-v1"
try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup'")
    [void](Invoke-Remote "mkdir -p '$RemoteStaging'")
    foreach ($file in $Files) { [void](Invoke-Remote "cp '$($file.remote)' '$RemoteBackup/$($file.name).before'") }
    $MutationStarted = $true
    foreach ($file in $Files) {
        $staged = "$RemoteStaging/$($file.name).py"
        Copy-ToRemote $file.local $staged
        if ((Get-RemoteHash $staged) -cne $file.after) { throw "Staging invalide : $($file.name)" }
        [void](Invoke-Remote "/usr/share/klippy-env/bin/python -B -m py_compile '$staged'")
    }
    foreach ($file in $Files) {
        $staged = "$RemoteStaging/$($file.name).py"
        [void](Invoke-Remote "cp '$staged' '$($file.remote).next'")
        [void](Invoke-Remote "chmod 0644 '$($file.remote).next'")
        [void](Invoke-Remote "mv '$($file.remote).next' '$($file.remote)'")
    }
    [void](Invoke-Remote "rm -f /usr/share/klipper/klippy/extras/__pycache__/k1_control_cfs_direct_owner.*.pyc")
    [void](Invoke-Remote "rm -f /usr/share/klipper/klippy/extras/k1_control_cfs_direct/__pycache__/owner.*.pyc")
    Restart-Restore
    Assert-Hashes 'after'
    $after = Get-Snapshot
    Assert-CommonSafeState $after
    if ($after.direct_owner.phase -cne 'idle' -or -not $after.direct_owner.PSObject.Properties['load_tail_recovery_count']) {
        throw 'Nouvelle reprise non chargee apres restart.'
    }
    Save-Evidence 'deploy-safe-state.json' $after
    Save-Evidence 'deploy-result.json' ([ordered]@{
        result = 'DEPLOY_CFS_ERR8_LOAD_TAIL_RECOVERY_V1_OK'
        capture_id = $CaptureId
        files_replaced = 2
        sensors = 'head_true_after_cutter_true'
        allowed_tail_stages = @(4,6)
        forbidden_stage5 = $true
        heat = $false; motion = $false; extrusion = $false; cfs_frame = $false; probe = $false
    })
    Write-Output "DEPLOY_CFS_ERR8_LOAD_TAIL_RECOVERY_V1_OK capture=$CaptureId"
} catch {
    $failure = $_
    try { Save-Evidence 'deploy-failure.txt' $failure.Exception.ToString() } catch {}
    if ($MutationStarted) {
        try { Restore-Backups $RemoteBackup }
        catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
