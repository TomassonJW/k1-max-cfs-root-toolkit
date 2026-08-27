[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('CLEANING_PREP', 'KEEP_CORRECT', 'EMPTY_LOAD', 'WRONG_CHANGE', 'CROSS_CFS')]
    [string]$Checkpoint,

    [ValidateRange(5, 300)]
    [int]$DurationSeconds = 180,

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$CaptureId = ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-cfs-temp-owner-v1'),

    [string]$PrinterHost = 'k1max-root'
)

$ErrorActionPreference = 'Stop'
$ExpectedProgramSha256 = '7f818e5d144e3a9c6565ef80b72b36f127f4e9362c51b4b3fa5e825916f81aa6'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$RawRoot = Join-Path $WorkspaceRoot 'inventory\raw'
$SessionDirectory = Join-Path $RawRoot $CaptureId
$CapturePath = Join-Path $SessionDirectory 'cfs-temp-owner.safe.jsonl'
$AnalysisPath = Join-Path $SessionDirectory 'cfs-temp-owner.analysis.txt'
$MetadataPath = Join-Path $SessionDirectory 'local-metadata.json'
$RemoteProgramPath = Join-Path $PSScriptRoot 'observer.py'
$AnalyzerPath = Join-Path $PSScriptRoot 'analyze_observation.py'

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

if (-not (Test-Path -LiteralPath $RawRoot -PathType Container)) {
    throw 'Le dossier privé inventory/raw est introuvable.'
}
if (Test-Path -LiteralPath $SessionDirectory) {
    throw 'La capture existe déjà. Utilise un nouvel identifiant.'
}
$ActualProgramSha256 = Get-LocalSha256 -Path $RemoteProgramPath
if ($ActualProgramSha256 -cne $ExpectedProgramSha256) {
    throw "Le programme observateur ne correspond pas à la version revue : $ActualProgramSha256"
}

New-Item -ItemType Directory -Path $SessionDirectory | Out-Null
$ResolvedRawRoot = (Resolve-Path -LiteralPath $RawRoot).Path
$ResolvedSession = (Resolve-Path -LiteralPath $SessionDirectory).Path
if (-not $ResolvedSession.StartsWith($ResolvedRawRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Le dossier de capture doit rester sous inventory/raw.'
}

$Metadata = [ordered]@{
    capture_id = $CaptureId
    mission = 'G4-K1-CONTROL-CFS-TEMP-OWNER-V1'
    checkpoint = $Checkpoint
    duration_s = $DurationSeconds
    local_start = (Get-Date).ToString('o')
    ssh_alias = $PrinterHost
    remote_program_sha256 = $ActualProgramSha256
    gcode = $false
    remote_write = $false
    service_action = $false
    cfs_action_by_observer = $false
    physical_action_is_external_human_gate = $true
    identity_values_exported = $false
}
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

$RemoteProgram = (Get-Content -LiteralPath $RemoteProgramPath -Raw).Replace("`r`n", "`n")
$RemoteCommand = "'/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' - '$Checkpoint' '$DurationSeconds'"

Write-Host "OBSERVATION CFS : checkpoint=$Checkpoint durée=${DurationSeconds}s capture=$CaptureId"
Write-Host 'Lecture seule : aucun G-code, mouvement, chauffage, fichier distant ou service.'

$Output = $RemoteProgram | & ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ConnectTimeout=8' `
    -o 'ServerAliveInterval=10' `
    -o 'ServerAliveCountMax=35' `
    $PrinterHost `
    $RemoteCommand 2>&1
$SshExitCode = $LASTEXITCODE
$Output | Set-Content -LiteralPath $CapturePath -Encoding utf8
$Output | Write-Output

if ($SshExitCode -eq 0) {
    $AnalysisOutput = & python.exe $AnalyzerPath $CapturePath 2>&1
    $AnalysisExitCode = $LASTEXITCODE
    $AnalysisOutput | Set-Content -LiteralPath $AnalysisPath -Encoding utf8
    $AnalysisOutput | Write-Output
}
else {
    $AnalysisExitCode = 1
}

$Metadata.local_end = (Get-Date).ToString('o')
$Metadata.ssh_exit_code = $SshExitCode
$Metadata.capture_path = $CapturePath
$Metadata.analysis_path = $AnalysisPath
$Metadata.analysis_exit_code = $AnalysisExitCode
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

if ($SshExitCode -ne 0 -or $AnalysisExitCode -ne 0) {
    Write-Host "CFS_TEMP_OWNER_OBSERVATION_CLOSED exit_code=1 capture=$CapturePath"
    exit 1
}
Write-Host "CFS_TEMP_OWNER_OBSERVATION_CLOSED exit_code=0 capture=$CapturePath"
exit 0
