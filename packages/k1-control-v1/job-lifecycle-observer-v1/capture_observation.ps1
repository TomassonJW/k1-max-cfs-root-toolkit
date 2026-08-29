[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Observe')]
    [string]$Action = 'Plan',

    [Parameter(Mandatory = $true)]
    [ValidateSet('FULL_CYCLE', 'TOOL_CHANGE', 'RUNOUT_RECOVERY', 'PAUSE_RESUME', 'CANCEL', 'NORMAL_END', 'DISENGAGE')]
    [string]$Checkpoint,

    [ValidateRange(5, 900)]
    [int]$DurationSeconds = 300,

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$CaptureId = ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-job-lifecycle-observer-v1'),

    [string]$PrinterHost = 'k1max-root',

    [switch]$Execute,
    [string]$Gate,
    [switch]$HumanPresent,
    [switch]$ImmediateStopAvailable
)

$ErrorActionPreference = 'Stop'
$Mission = 'G4-K1-CONTROL-JOB-LIFECYCLE-OBSERVER-V1'
$ExpectedProgramSha256 = '0ad26d0ab3d53351373c0bbc2ce04860ff3941cca15ad749eac215297d2795dc'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$RawRoot = Join-Path $WorkspaceRoot 'inventory\raw'
$SessionDirectory = Join-Path $RawRoot $CaptureId
$CapturePath = Join-Path $SessionDirectory 'job-lifecycle.safe.jsonl'
$AnalysisPath = Join-Path $SessionDirectory 'job-lifecycle.analysis.txt'
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
if ($Action -eq 'Plan') {
    [ordered]@{
        status = 'JOB_LIFECYCLE_OBSERVER_PLAN_OK'
        mission = $Mission
        checkpoint = $Checkpoint
        observer_sha256 = $ExpectedProgramSha256
        installed_start_owner_sha256 = '678582e808d74f6b720ef3d6b52dc2c443c7a0652a62c484319e2b22fba7b0bc'
        printer_connection = $false
        gcode = $false
        job_action = $false
        cfs_action = $false
        remote_write = $false
        service_action = $false
    } | ConvertTo-Json
    exit 0
}
if (-not $Execute -or $Gate -cne $Mission -or -not $HumanPresent -or -not $ImmediateStopAvailable) {
    throw "Observation réelle refusée : -Execute, -Gate '$Mission', présence humaine et arrêt immédiat sont obligatoires."
}

New-Item -ItemType Directory -Path $SessionDirectory | Out-Null
$ResolvedRawRoot = (Resolve-Path -LiteralPath $RawRoot).Path
$ResolvedSession = (Resolve-Path -LiteralPath $SessionDirectory).Path
if (-not $ResolvedSession.StartsWith($ResolvedRawRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Le dossier de capture doit rester sous inventory/raw.'
}

$Metadata = [ordered]@{
    capture_id = $CaptureId
    mission = $Mission
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

Write-Host "OBSERVATION CYCLE : checkpoint=$Checkpoint durée=${DurationSeconds}s capture=$CaptureId"
Write-Host 'Lecture seule : aucun G-code, mouvement, chauffage, fichier distant ou service.'

$Output = $RemoteProgram | & ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ConnectTimeout=8' `
    -o 'ServerAliveInterval=10' `
    -o 'ServerAliveCountMax=95' `
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
    Write-Host "JOB_LIFECYCLE_OBSERVATION_CLOSED exit_code=1 capture=$CapturePath"
    exit 1
}
Write-Host "JOB_LIFECYCLE_OBSERVATION_CLOSED exit_code=0 capture=$CapturePath"
exit 0
