[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$CaptureId,

    [ValidateRange(30, 300)]
    [int]$DurationSeconds = 300,

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$PrinterHost = 'k1max-root',

    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
$ExpectedObserverSha256 = 'a5c4a75e99028ae7140d668a78934a931f2c1e8c26d1a9469e3fb8f4acaaaef0'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$RawRoot = Join-Path $WorkspaceRoot 'inventory\raw'
$SessionDirectory = Join-Path $RawRoot $CaptureId
$CapturePath = Join-Path $SessionDirectory 'start-sequence-t1a-route-v1.safe.jsonl'
$AnalysisPath = Join-Path $SessionDirectory 'start-sequence-t1a-route-v1.analysis.json'
$MetadataPath = Join-Path $SessionDirectory 'local-metadata.json'
$RemoteProgramPath = Join-Path $PSScriptRoot 'remote_observer.py'
$AnalyzerPath = Join-Path $PSScriptRoot 'analyze_capture.py'

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
$ActualObserverSha256 = Get-LocalSha256 -Path $RemoteProgramPath
if ($ActualObserverSha256 -cne $ExpectedObserverSha256) {
    throw "L'observateur ne correspond pas à la version revue : $ActualObserverSha256"
}

New-Item -ItemType Directory -Path $SessionDirectory | Out-Null
$ResolvedRawRoot = (Resolve-Path -LiteralPath $RawRoot).Path
$ResolvedSession = (Resolve-Path -LiteralPath $SessionDirectory).Path
if (-not $ResolvedSession.StartsWith($ResolvedRawRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Le dossier de capture doit rester sous inventory/raw.'
}

$Metadata = [ordered]@{
    capture_id = $CaptureId
    mission = 'G4-K1-CONTROL-START-SEQUENCE-T1A-ROUTE-V1'
    duration_s = $DurationSeconds
    local_start = (Get-Date).ToString('o')
    ssh_alias = $PrinterHost
    remote_program_sha256 = $ActualObserverSha256
    observer_gcode = $false
    observer_remote_write = $false
    observer_service_action = $false
    preflight_only = [bool]$PreflightOnly
    physical_action_owner = $(if ($PreflightOnly) { 'none' } else { 'human_operator_stock_ui' })
    physical_action = $(if ($PreflightOnly) { 'none' } else { 'load_T1A_once' })
    automatic_retry = $false
    identity_values_exported = $false
}
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

$RemoteProgram = (Get-Content -LiteralPath $RemoteProgramPath -Raw).Replace("`r`n", "`n")
$RemoteArgument = $(if ($PreflightOnly) { 'preflight' } else { [string]$DurationSeconds })
$RemoteCommand = "env PYTHONDONTWRITEBYTECODE=1 '/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' -B - '$RemoteArgument'"

if ($PreflightOnly) {
    Write-Host 'PREFLIGHT T1A EN LECTURE SEULE : aucune action humaine ni aucun effet.'
}
else {
    Write-Host 'NE TOUCHE PAS ENCORE AU CHARGEMENT.'
    Write-Host 'Après la ligne JSON kind=header, Thomas charge T1A UNE SEULE FOIS depuis l interface stock.'
    Write-Host 'L observateur ne produit aucun G-code et ne relance jamais le chargement.'
}

$Output = $RemoteProgram | & ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ConnectTimeout=8' `
    -o 'ServerAliveInterval=10' `
    -o 'ServerAliveCountMax=35' `
    $PrinterHost `
    $RemoteCommand 2>&1 | Tee-Object -FilePath $CapturePath
$SshExitCode = $LASTEXITCODE

if ($SshExitCode -eq 0 -and -not $PreflightOnly) {
    $AnalysisOutput = & python.exe $AnalyzerPath $CapturePath 2>&1
    $AnalysisExitCode = $LASTEXITCODE
    $AnalysisOutput | Set-Content -LiteralPath $AnalysisPath -Encoding utf8
    $AnalysisOutput | Write-Output
}
elseif ($SshExitCode -ne 0) {
    $AnalysisExitCode = 1
}
else {
    $AnalysisExitCode = 0
    $Output | Set-Content -LiteralPath $AnalysisPath -Encoding utf8
}

$Metadata.local_end = (Get-Date).ToString('o')
$Metadata.ssh_exit_code = $SshExitCode
$Metadata.analysis_exit_code = $AnalysisExitCode
$Metadata.capture_path = $CapturePath
$Metadata.analysis_path = $AnalysisPath
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

if ($SshExitCode -ne 0 -or $AnalysisExitCode -ne 0) {
    Write-Host "START_SEQUENCE_T1A_ROUTE_V1_CLOSED exit_code=$AnalysisExitCode capture=$CapturePath"
    exit $AnalysisExitCode
}
Write-Host "START_SEQUENCE_T1A_ROUTE_V1_CLOSED exit_code=0 capture=$CapturePath"
exit 0
