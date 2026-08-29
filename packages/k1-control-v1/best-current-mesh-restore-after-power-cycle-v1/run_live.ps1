[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Plan', 'Preflight', 'Restore')]
    [string]$Action,

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$CaptureId = ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-best-current-mesh-restore-after-power-cycle-v1'),

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$PrinterHost = 'k1max-root',
    [switch]$Execute,
    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-AFTER-POWER-CYCLE-V1'
$ExpectedProgramSha256 = 'cc9efc77fadf35a4e4590c84b49a6c70102f10c69294ad268bf796935e977b1e'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$RawRoot = Join-Path $WorkspaceRoot 'inventory\raw'
$SessionDirectory = Join-Path $RawRoot $CaptureId
$CapturePath = Join-Path $SessionDirectory 'best-current-mesh-restore-after-power-cycle.safe.jsonl'
$MetadataPath = Join-Path $SessionDirectory 'local-metadata.json'
$RemoteProgramPath = Join-Path $PSScriptRoot 'remote_gate.py'
$ActualProgramSha256 = (Get-FileHash -LiteralPath $RemoteProgramPath -Algorithm SHA256).Hash.ToLowerInvariant()

if ($ActualProgramSha256 -cne $ExpectedProgramSha256) {
    throw "Le programme distant ne correspond pas à la version revue : $ActualProgramSha256"
}
if ($Action -ceq 'Restore' -and (-not $Execute -or $Gate -cne $RequiredGate)) {
    throw "Remise du 11x11 bloquée : -Execute et -Gate '$RequiredGate' sont obligatoires."
}
if ($Action -in @('Plan', 'Preflight') -and ($Execute -or $Gate)) {
    throw 'Plan et Preflight sont sans drapeau de mutation.'
}
if ($Action -ceq 'Plan') {
    [ordered]@{
        status = 'BEST_CURRENT_MESH_RESTORE_AFTER_POWER_CYCLE_V1_PLAN_OK'
        mission = $RequiredGate
        remote_program_sha256 = $ActualProgramSha256
        accepted_prior_profiles = @('default', 'k1_p001_t055_r001_n06x06')
        target_profile = 'k1_p001_t055_r001_n11x11'
        exact_required_route = 'T1A'
        maximum_primary_attempts = 1
        rollback = 'exact_prior_profile_once_after_primary_uncertainty'
        printer_connection = $false
        remote_file_write = $false
        heater_or_motion_action = $false
        cfs_action = $false
        automatic_retry = $false
    } | ConvertTo-Json
    exit 0
}
if (-not (Test-Path -LiteralPath $RawRoot -PathType Container)) {
    throw 'Le dossier privé inventory/raw est introuvable.'
}
if (Test-Path -LiteralPath $SessionDirectory) {
    throw 'La capture existe déjà. Utilise un nouvel identifiant.'
}

New-Item -ItemType Directory -Path $SessionDirectory | Out-Null
$ResolvedRawRoot = (Resolve-Path -LiteralPath $RawRoot).Path
$ResolvedSession = (Resolve-Path -LiteralPath $SessionDirectory).Path
if (-not $ResolvedSession.StartsWith($ResolvedRawRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Le dossier de capture doit rester sous inventory/raw.'
}

$Metadata = [ordered]@{
    capture_id = $CaptureId
    mission = $RequiredGate
    action = $Action
    local_start = (Get-Date).ToString('o')
    ssh_alias = $PrinterHost
    remote_program_sha256 = $ActualProgramSha256
    remote_file_write = $false
    service_action = $false
    heater_or_motion_action = $false
    cfs_action = $false
    automatic_retry = $false
}
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

$RemoteProgram = (Get-Content -LiteralPath $RemoteProgramPath -Raw).Replace("`r`n", "`n")
$RemoteAction = $Action.ToLowerInvariant()
$RemoteCommand = "env PYTHONDONTWRITEBYTECODE=1 '/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' -B - '$RemoteAction'"

Write-Host "REMISE 11X11 APRÈS REDÉMARRAGE : action=$Action capture=$CaptureId"
Write-Host 'Aucun fichier distant, restart, chauffe, mouvement, homing, palpage, extrusion ou action CFS.'

$Output = $RemoteProgram | & ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ConnectTimeout=8' `
    -o 'ServerAliveInterval=10' `
    -o 'ServerAliveCountMax=3' `
    $PrinterHost `
    $RemoteCommand 2>&1
$SshExitCode = $LASTEXITCODE
$Output | Set-Content -LiteralPath $CapturePath -Encoding utf8
$Output | Write-Output

$Metadata.local_end = (Get-Date).ToString('o')
$Metadata.ssh_exit_code = $SshExitCode
$Metadata.capture_path = $CapturePath
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

Write-Host "BEST_CURRENT_MESH_RESTORE_AFTER_POWER_CYCLE_V1_CLOSED exit_code=$SshExitCode capture=$CapturePath"
exit $SshExitCode
