[CmdletBinding()]
param(
    [ValidateSet('PreflightD1', 'D1', 'PreflightD2', 'D2', 'PreflightD3', 'D3')]
    [string]$Action = 'PreflightD1',

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$CaptureId = ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-clean-motion-v1-checkpoint-d'),

    [string]$PrinterHost = 'k1max-root',
    [switch]$Execute,
    [string]$Gate = '',
    [string]$PreviousHumanVerdict = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-CLEAN-MOTION-V1'
$ExpectedProgramSha256 = '795560f66883cc4371ff4e2086e28d7430ce7bca476ae67dc1a689f8ae460be4'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$RawRoot = Join-Path $WorkspaceRoot 'inventory\raw'
$SessionDirectory = Join-Path $RawRoot $CaptureId
$CapturePath = Join-Path $SessionDirectory 'clean-motion-checkpoint-d.safe.jsonl'
$MetadataPath = Join-Path $SessionDirectory 'local-metadata.json'
$RemoteProgramPath = Join-Path $PSScriptRoot 'remote_checkpoint_d.py'
$IsEffect = $Action -in @('D1', 'D2', 'D3')
$RequiredPreviousHumanVerdict = switch ($Action) {
    'D2' { 'D1_OK' }
    'D3' { 'D2_OK' }
    default { '' }
}

if ($IsEffect -and (-not $Execute -or $Gate -cne $RequiredGate)) {
    throw "Checkpoint D bloqué : -Execute et -Gate '$RequiredGate' sont obligatoires."
}
if (-not $IsEffect -and ($Execute -or $Gate)) {
    throw 'Un préflight ne prend aucun drapeau de mouvement.'
}
if (-not $IsEffect -and $PreviousHumanVerdict) {
    throw 'Un préflight ne consomme aucun verdict humain.'
}
if ($IsEffect -and $RequiredPreviousHumanVerdict -and $PreviousHumanVerdict -cne $RequiredPreviousHumanVerdict) {
    throw "Checkpoint $Action bloqué : -PreviousHumanVerdict '$RequiredPreviousHumanVerdict' est obligatoire."
}
if (-not (Test-Path -LiteralPath $RawRoot -PathType Container)) {
    throw 'Le dossier privé inventory/raw est introuvable.'
}
if (Test-Path -LiteralPath $SessionDirectory) {
    throw 'La capture existe déjà. Utilise un nouvel identifiant.'
}
$ActualProgramSha256 = (Get-FileHash -LiteralPath $RemoteProgramPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualProgramSha256 -cne $ExpectedProgramSha256) {
    throw "Le programme distant ne correspond pas à la version revue : $ActualProgramSha256"
}

New-Item -ItemType Directory -Path $SessionDirectory | Out-Null
$ResolvedRawRoot = (Resolve-Path -LiteralPath $RawRoot).Path
$ResolvedSession = (Resolve-Path -LiteralPath $SessionDirectory).Path
if (-not $ResolvedSession.StartsWith($ResolvedRawRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Le dossier de capture doit rester sous inventory/raw.'
}

$CheckpointId = $Action.Substring($Action.Length - 2).ToLowerInvariant()
$Mode = if ($IsEffect) { 'run' } else { 'preflight' }
$Metadata = [ordered]@{
    capture_id = $CaptureId
    mission = $RequiredGate
    action = $Action
    checkpoint = $CheckpointId
    local_start = (Get-Date).ToString('o')
    ssh_alias = $PrinterHost
    remote_program_sha256 = $ActualProgramSha256
    remote_file_write = $false
    service_action = $false
    heating = $false
    extrusion = $false
    cfs_action = $false
    xy_motion_at_z50 = $IsEffect
    identity_values_exported = $false
}
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

$RemoteProgram = (Get-Content -LiteralPath $RemoteProgramPath -Raw).Replace("`r`n", "`n")
$RemoteCommand = "'/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' - '$Mode' '$CheckpointId'"

Write-Host "CLEAN-MOTION CHECKPOINT $($CheckpointId.ToUpperInvariant()) : action=$Action capture=$CaptureId"
Write-Host 'Déplacement XY borné à Z=50 mm. Aucune chauffe, extrusion, CFS, homing, mesure de mesh ou écriture.'

$Output = $RemoteProgram | & ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ConnectTimeout=8' `
    -o 'ServerAliveInterval=10' `
    -o 'ServerAliveCountMax=5' `
    $PrinterHost `
    $RemoteCommand 2>&1
$SshExitCode = $LASTEXITCODE
$Output | Set-Content -LiteralPath $CapturePath -Encoding utf8
$Output | Write-Output

$Metadata.local_end = (Get-Date).ToString('o')
$Metadata.ssh_exit_code = $SshExitCode
$Metadata.capture_path = $CapturePath
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

Write-Host "CLEAN_MOTION_V1_CHECKPOINT_D_CLOSED exit_code=$SshExitCode capture=$CapturePath"
exit $SshExitCode
