[CmdletBinding()]
param(
    [ValidateSet('PreflightE1', 'E1', 'PreflightE2', 'E2', 'PreflightE3', 'E3', 'PreflightE4', 'E4')]
    [string]$Action = 'PreflightE1',

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$CaptureId = ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-clean-motion-v1-brush-trial'),

    [string]$PrinterHost = 'k1max-root',
    [switch]$Execute,
    [string]$Gate = '',
    [string]$PreviousHumanVerdict = '',
    [switch]$OperatorPresent,
    [switch]$PlateClear,
    [switch]$BrushesVisible,
    [switch]$ImmediateStopAvailable
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-CLEAN-MOTION-V1'
$ExpectedProgramSha256 = '5942065e9020c15e108218594a5289e97220fa83f8a778d14e51dc353c69833b'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$RawRoot = Join-Path $WorkspaceRoot 'inventory\raw'
$SessionDirectory = Join-Path $RawRoot $CaptureId
$CapturePath = Join-Path $SessionDirectory 'clean-motion-brush-trial.safe.jsonl'
$MetadataPath = Join-Path $SessionDirectory 'local-metadata.json'
$RemoteProgramPath = Join-Path $PSScriptRoot 'remote_brush_trial.py'
$IsEffect = $Action -in @('E1', 'E2', 'E3', 'E4')
$RequiredPreviousHumanVerdict = switch ($Action) {
    'E1' { 'GEOMETRY_OK' }
    'E2' { 'CONTACT_COORDINATES_OK' }
    'E3' { 'E2_OK' }
    'E4' { 'SQUARE_CYCLE_COORDINATES_OK' }
    default { '' }
}

if ($IsEffect -and (-not $Execute -or $Gate -cne $RequiredGate)) {
    throw "Essai brosse bloqué : -Execute et -Gate '$RequiredGate' sont obligatoires."
}
if ($IsEffect -and (-not $OperatorPresent -or -not $PlateClear -or -not $BrushesVisible -or -not $ImmediateStopAvailable)) {
    throw 'Essai brosse bloqué : présence, plateau libre, brosses visibles et arrêt immédiat doivent être confirmés.'
}
if (-not $IsEffect -and ($Execute -or $Gate -or $OperatorPresent -or $PlateClear -or $BrushesVisible -or $ImmediateStopAvailable)) {
    throw 'Un préflight ne prend aucun drapeau de mouvement ou de présence.'
}
if (-not $IsEffect -and $PreviousHumanVerdict) {
    throw 'Un préflight ne consomme aucun verdict humain.'
}
if ($IsEffect -and $PreviousHumanVerdict -cne $RequiredPreviousHumanVerdict) {
    throw "Essai $Action bloqué : -PreviousHumanVerdict '$RequiredPreviousHumanVerdict' est obligatoire."
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

$TrialId = $Action.Substring($Action.Length - 2).ToLowerInvariant()
$Mode = if ($IsEffect) { 'run' } else { 'preflight' }
$Metadata = [ordered]@{
    capture_id = $CaptureId
    mission = $RequiredGate
    action = $Action
    trial = $TrialId
    local_start = (Get-Date).ToString('o')
    ssh_alias = $PrinterHost
    remote_program_sha256 = $ActualProgramSha256
    human_verdict_consumed = $PreviousHumanVerdict
    operator_present = [bool]$OperatorPresent
    plate_clear = [bool]$PlateClear
    brushes_visible = [bool]$BrushesVisible
    immediate_stop_available = [bool]$ImmediateStopAvailable
    remote_file_write = $false
    service_action = $false
    heating = $false
    extrusion = $false
    cfs_action = $false
    identity_values_exported = $false
}
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

$RemoteProgram = (Get-Content -LiteralPath $RemoteProgramPath -Raw).Replace("`r`n", "`n")
$RemoteCommand = "'/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' - '$Mode' '$TrialId'"

Write-Host "CLEAN-MOTION ESSAI $($TrialId.ToUpperInvariant()) : action=$Action capture=$CaptureId"
Write-Host 'Aucune chauffe, extrusion, action CFS, écriture distante, mesure de mesh ou relance automatique.'

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

Write-Host "CLEAN_MOTION_V1_BRUSH_TRIAL_CLOSED exit_code=$SshExitCode capture=$CapturePath"
exit $SshExitCode
