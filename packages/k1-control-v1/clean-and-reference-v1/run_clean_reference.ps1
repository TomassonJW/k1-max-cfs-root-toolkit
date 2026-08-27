[CmdletBinding()]
param(
    [ValidateSet('Preflight', 'CleanCycle', 'Reference', 'Stop', 'Validate')]
    [string]$Action = 'Preflight',

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$MaterialId,

    [Parameter(Mandatory = $true)]
    [ValidateRange(160.0, 300.0)]
    [double]$CleaningTargetC,

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$CaptureId = ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-clean-and-reference-v1'),

    [string]$PrinterHost = 'k1max-root',
    [switch]$Execute,
    [string]$Gate = '',
    [string]$PreviousHumanVerdict = '',
    [switch]$OperatorPresent,
    [switch]$PlateClear,
    [switch]$BrushesVisible,
    [switch]$NozzleVisible,
    [switch]$ImmediateStopAvailable
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-CLEAN-AND-REFERENCE-V1'
$ExpectedProgramSha256 = '31e483f34bc0fc879326ae79a75ff28114bf29f4a0d084ad4b36666beffc0b4a'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$RawRoot = Join-Path $WorkspaceRoot 'inventory\raw'
$SessionDirectory = Join-Path $RawRoot $CaptureId
$CapturePath = Join-Path $SessionDirectory 'clean-and-reference.safe.jsonl'
$MetadataPath = Join-Path $SessionDirectory 'local-metadata.json'
$RemoteProgramPath = Join-Path $PSScriptRoot 'remote_clean_reference.py'
$IsEffect = $Action -in @('CleanCycle', 'Reference', 'Stop')
$RemoteAction = switch ($Action) {
    'Preflight' { 'preflight' }
    'CleanCycle' { 'clean-cycle' }
    'Reference' { 'reference' }
    'Stop' { 'stop' }
    'Validate' { 'validate' }
}
$RequiredPreviousHumanVerdict = switch ($Action) {
    'CleanCycle' { 'GEETECH_220_PRIMARY_BRUSH_V2_CONFIRMED' }
    'Reference' { 'FINAL_NOZZLE_CLEAN_OK' }
    'Stop' { 'THERMAL_STOP_REQUIRED' }
    default { '' }
}

function Get-LocalSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $algorithm.Dispose()
        $stream.Dispose()
    }
}

if ($MaterialId -in @('unknown', 'none', 'UNKNOWN', 'NONE')) {
    throw 'La matière précédente doit être explicite.'
}
if ($IsEffect -and (-not $Execute -or $Gate -cne $RequiredGate)) {
    throw "Action physique bloquée : -Execute et -Gate '$RequiredGate' sont obligatoires."
}
if ($IsEffect -and (-not $OperatorPresent -or -not $PlateClear -or -not $BrushesVisible -or -not $NozzleVisible -or -not $ImmediateStopAvailable)) {
    throw 'Action physique bloquée : présence, plateau libre, brosses et buse visibles, arrêt immédiat doivent être confirmés.'
}
if ($IsEffect -and $PreviousHumanVerdict -cne $RequiredPreviousHumanVerdict) {
    throw "Action $Action bloquée : verdict '$RequiredPreviousHumanVerdict' obligatoire."
}
if (-not $IsEffect -and ($Execute -or $Gate -or $PreviousHumanVerdict -or $OperatorPresent -or $PlateClear -or $BrushesVisible -or $NozzleVisible -or $ImmediateStopAvailable)) {
    throw 'Preflight et Validate sont strictement en lecture seule et ne prennent aucun drapeau physique.'
}
if (-not (Test-Path -LiteralPath $RawRoot -PathType Container)) {
    throw 'Le dossier privé inventory/raw est introuvable.'
}
if (Test-Path -LiteralPath $SessionDirectory) {
    throw 'La capture existe déjà. Utilise un nouvel identifiant.'
}

$ActualProgramSha256 = Get-LocalSha256 -Path $RemoteProgramPath
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
    remote_action = $RemoteAction
    material_id = $MaterialId
    cleaning_target_c = $CleaningTargetC
    local_start = (Get-Date).ToString('o')
    ssh_alias = $PrinterHost
    remote_program_sha256 = $ActualProgramSha256
    human_verdict_consumed = $PreviousHumanVerdict
    operator_present = [bool]$OperatorPresent
    plate_clear = [bool]$PlateClear
    brushes_visible = [bool]$BrushesVisible
    nozzle_visible = [bool]$NozzleVisible
    immediate_stop_available = [bool]$ImmediateStopAvailable
    remote_file_write = $false
    service_action = $false
    extrusion = $false
    cfs_action = $false
    identity_values_exported = $false
}
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

$TargetInvariant = $CleaningTargetC.ToString('0.0', [Globalization.CultureInfo]::InvariantCulture)
$RemoteProgram = (Get-Content -LiteralPath $RemoteProgramPath -Raw).Replace("`r`n", "`n")
$RemoteCommand = "'/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' - '$RemoteAction' '$MaterialId' '$TargetInvariant'"

Write-Host "CLEAN-AND-REFERENCE : action=$Action matière=$MaterialId cible=$TargetInvariant capture=$CaptureId"
Write-Host 'Aucune extrusion, action CFS, écriture distante, configuration ou relance automatique.'

$Output = $RemoteProgram | & ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ConnectTimeout=8' `
    -o 'ServerAliveInterval=10' `
    -o 'ServerAliveCountMax=20' `
    $PrinterHost `
    $RemoteCommand 2>&1
$SshExitCode = $LASTEXITCODE
$Output | Set-Content -LiteralPath $CapturePath -Encoding utf8
$Output | Write-Output

$Metadata.local_end = (Get-Date).ToString('o')
$Metadata.ssh_exit_code = $SshExitCode
$Metadata.capture_path = $CapturePath
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

Write-Host "CLEAN_AND_REFERENCE_V1_CLOSED exit_code=$SshExitCode capture=$CapturePath"
exit $SshExitCode
