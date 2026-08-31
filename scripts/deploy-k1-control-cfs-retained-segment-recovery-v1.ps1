[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Deploy', 'Reload', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$CaptureId,
    [string]$EvidenceDirectory,
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 ou plus recent est obligatoire.' }

$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RecoveryDriver = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-cycle-activation-v1\remote_forward_purge_recovery.py'
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
        before = 'df121ba1fa8dfc494aa65afc235ae6404d5c9e7124ef8fc90e3346512239c3af'
        after = 'e68df4ab9d62d64f5b9bcf5a09acdd8a79730b555c2b37d347455e52226e8541'
    },
    [ordered]@{
        name = 'direct_adapter'
        local = Join-Path $WorkspaceRoot 'packages\k1-control-v1\cfs-direct-owner-install-disabled-v1\k1_control_cfs_direct_owner.py'
        remote = '/usr/share/klipper/klippy/extras/k1_control_cfs_direct_owner.py'
        before = '47cc69a495afc269d5e54df7224d88d9b9ada430fc511a4107f42935138029d2'
        after = 'f392b8435dbe025789a1ce98f840aa1e1193aa549372872f216334a7f5cddc86'
    }
)

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
    if (-not $EvidenceDirectory) { return }
    $root = Assert-InWorkspace $EvidenceDirectory
    $path = Join-Path $root $Name
    if ($Value -is [string]) { $Value | Set-Content -LiteralPath $path -Encoding utf8 }
    else { $Value | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $path -Encoding utf8 }
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

function Get-Snapshot {
    $program = [IO.File]::ReadAllText($RecoveryDriver).Replace("`r`n","`n")
    $output = Invoke-RemoteStdin "/usr/share/klippy-env/bin/python -B - 'snapshot'" $program
    return (($output -join "`n") | ConvertFrom-Json)
}

function Invoke-Admin {
    param([Parameter(Mandatory=$true)][ValidateSet('generation','restart','restore_mesh')][string]$Name)
    $program = [IO.File]::ReadAllText($RemoteAdmin).Replace("`r`n","`n")
    $output = Invoke-RemoteStdin "/usr/share/klippy-env/bin/python -B - '$Name'" $program
    if ($Name -eq 'restart') { return @($output) }
    return (($output -join "`n") | ConvertFrom-Json)
}

function Assert-SafeSegmentState {
    param([Parameter(Mandatory=$true)]$Snapshot)
    if ($Snapshot.webhooks.state -cne 'ready' -or $Snapshot.print_state -cne 'standby' -or
        [double]$Snapshot.extruder.target -ne 0.0 -or [double]$Snapshot.heater_bed.target -ne 0.0 -or
        [string]$Snapshot.toolhead.homed_axes -ne '' -or [string]$Snapshot.mesh_profile -cne $BestMesh -or
        $Snapshot.box.logical_routes.Count -ne 0 -or [string]$Snapshot.box.t_command -ne '' -or
        [int]$Snapshot.box.auto_refill -ne 0 -or $Snapshot.sensors.head -ne $true -or
        $Snapshot.sensors.after_cutter -ne $false -or $Snapshot.direct_owner.enabled -ne $true -or
        $Snapshot.direct_owner.stock_commands_blocked -ne $true) {
        throw 'Etat segment retenu non conforme.'
    }
}

function Assert-Hashes {
    param([ValidateSet('before','after')][string]$Field)
    foreach ($file in $Files) {
        $actual = Get-RemoteHash $file.remote
        if ($actual -cne $file.$Field) { throw "Hash distant inattendu : $($file.name) $actual" }
    }
}

function Wait-ReadyTransition {
    param([Parameter(Mandatory=$true)]$Before)
    Start-Sleep -Seconds 2
    for ($attempt=1; $attempt -le 90; $attempt++) {
        try {
            $generation = Invoke-Admin 'generation'
            $changed = ([long]$generation.socket_inode -ne [long]$Before.socket_inode) -or ([long]$generation.socket_mtime_ns -ne [long]$Before.socket_mtime_ns)
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

function Invoke-ExactRollback {
    param([Parameter(Mandatory=$true)][string]$RemoteBackup)
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
    $snapshot = Get-Snapshot
    Assert-SafeSegmentState $snapshot
    Save-Evidence 'rollback-safe-state.json' $snapshot
}

foreach ($file in $Files) {
    $local = Assert-InWorkspace $file.local
    $hash = (Get-FileHash -LiteralPath $local -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -cne $file.after) { throw "Payload local non fige : $($file.name) $hash" }
}

if ($Action -eq 'Plan') {
    Write-Output 'PLAN_CFS_RETAINED_SEGMENT_RECOVERY_V1_OK'
    Write-Output 'Deux fichiers remplaces avec backup exact; restart Klipper, remise du 11x11 et du Z -0.04, sans mouvement ni chauffe.'
    exit 0
}
if (-not $Execute -or -not $CaptureId -or -not $EvidenceDirectory) { throw 'Execute, CaptureId et EvidenceDirectory sont obligatoires.' }
if (-not (Test-Path -LiteralPath $EvidenceDirectory)) { New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null }
[void](Assert-InWorkspace $EvidenceDirectory)

$RemoteBackup = "/usr/data/k1-control-v1/backups/$CaptureId/cfs-retained-segment-recovery-v1"
$RemoteStaging = "/usr/data/k1-control-v1/staging/$CaptureId-cfs-retained-segment-recovery-v1"
if ($Action -eq 'Rollback') {
    Invoke-ExactRollback $RemoteBackup
    Write-Output "ROLLBACK_CFS_RETAINED_SEGMENT_RECOVERY_V1_OK capture=$CaptureId"
    exit 0
}

if ($Action -eq 'Reload') {
    $beforeReload = Get-Snapshot
    Assert-SafeSegmentState $beforeReload
    Assert-Hashes 'after'
    Save-Evidence 'reload-preflight-safe-state.json' $beforeReload
    try {
        Restart-Restore
        Assert-Hashes 'after'
        $afterReload = Get-Snapshot
        Assert-SafeSegmentState $afterReload
        if (-not $afterReload.direct_owner.PSObject.Properties['retained_head_segment']) {
            throw 'Le module Python corrige ne publie pas retained_head_segment.'
        }
        Save-Evidence 'reload-safe-state.json' $afterReload
        Write-Output "RELOAD_CFS_RETAINED_SEGMENT_RECOVERY_V1_OK capture=$CaptureId"
        exit 0
    } catch {
        $reloadFailure = $_
        try { Invoke-ExactRollback $RemoteBackup }
        catch { throw "Reload KO: $($reloadFailure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
        throw $reloadFailure
    }
}

$before = Get-Snapshot
Assert-SafeSegmentState $before
Assert-Hashes 'before'
Save-Evidence 'preflight-safe-state.json' $before

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup'")
    [void](Invoke-Remote "mkdir -p '$RemoteStaging'")
    foreach ($file in $Files) {
        [void](Invoke-Remote "cp '$($file.remote)' '$RemoteBackup/$($file.name).before'")
    }
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
    Assert-SafeSegmentState $after
    Save-Evidence 'deploy-safe-state.json' $after
    Save-Evidence 'deploy-result.json' ([ordered]@{
        result = 'DEPLOY_CFS_RETAINED_SEGMENT_RECOVERY_V1_OK'
        capture_id = $CaptureId
        files_replaced = 2
        klipper_restart = 1
        mesh_profile = $after.mesh_profile
        head_sensor = $after.sensors.head
        after_cutter_sensor = $after.sensors.after_cutter
        heat = $false; motion = $false; extrusion = $false; cfs_frame = $false; probe = $false
    })
    Write-Output "DEPLOY_CFS_RETAINED_SEGMENT_RECOVERY_V1_OK capture=$CaptureId"
} catch {
    $failure = $_
    try { Save-Evidence 'deploy-failure.txt' $failure.Exception.ToString() } catch {}
    if ($MutationStarted) {
        try { Invoke-ExactRollback $RemoteBackup } catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
