[CmdletBinding()]
param(
    [ValidateSet('Preflight', 'Checkpoint', 'Validate')]
    [string]$Action = 'Preflight',

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$CaptureId = ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-clean-motion-v1-checkpoint-c'),

    [string]$PrinterHost = 'k1max-root',
    [switch]$Execute,
    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-CLEAN-MOTION-V1'
$ExpectedProgramSha256 = 'd7ff61f0b5280b1a2b73bd3ecb653ede181078b880164601713e54e5222653a7'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$RawRoot = Join-Path $WorkspaceRoot 'inventory\raw'
$SessionDirectory = Join-Path $RawRoot $CaptureId
$CapturePath = Join-Path $SessionDirectory 'clean-motion-checkpoint-c.safe.jsonl'
$MetadataPath = Join-Path $SessionDirectory 'local-metadata.json'
$RemoteProgramPath = Join-Path $PSScriptRoot 'remote_checkpoint_c.py'

if ($Action -ceq 'Checkpoint' -and (-not $Execute -or $Gate -cne $RequiredGate)) {
    throw "Checkpoint C bloqué : -Execute et -Gate '$RequiredGate' sont obligatoires."
}
if ($Action -cne 'Checkpoint' -and ($Execute -or $Gate)) {
    throw 'Le préflight et la validation ne prennent aucun drapeau de mouvement.'
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

$Metadata = [ordered]@{
    capture_id = $CaptureId
    mission = $RequiredGate
    action = $Action
    local_start = (Get-Date).ToString('o')
    ssh_alias = $PrinterHost
    remote_program_sha256 = $ActualProgramSha256
    remote_file_write = $false
    service_action = $false
    heating = $false
    extrusion = $false
    cfs_action = $false
    homing_and_motion = ($Action -ceq 'Checkpoint')
    identity_values_exported = $false
}
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

$RemoteProgram = (Get-Content -LiteralPath $RemoteProgramPath -Raw).Replace("`r`n", "`n")
$RemoteAction = switch ($Action) {
    'Checkpoint' { 'checkpoint' }
    'Validate' { 'validate' }
    default { 'preflight' }
}
$RemoteCommand = "'/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' - '$RemoteAction'"

Write-Host "CLEAN-MOTION CHECKPOINT C : action=$Action capture=$CaptureId"
Write-Host 'Checkpoint unique : référence stock, recharge 11x11, montée Z=50 mm. Aucune chauffe, extrusion, CFS, mesure de mesh ou écriture.'

$Output = $RemoteProgram | & ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ConnectTimeout=8' `
    -o 'ServerAliveInterval=10' `
    -o 'ServerAliveCountMax=10' `
    $PrinterHost `
    $RemoteCommand 2>&1
$SshExitCode = $LASTEXITCODE
$Output | Set-Content -LiteralPath $CapturePath -Encoding utf8
$Output | Write-Output

$Metadata.local_end = (Get-Date).ToString('o')
$Metadata.ssh_exit_code = $SshExitCode
$Metadata.capture_path = $CapturePath
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

Write-Host "CLEAN_MOTION_V1_CHECKPOINT_C_CLOSED exit_code=$SshExitCode capture=$CapturePath"
exit $SshExitCode
