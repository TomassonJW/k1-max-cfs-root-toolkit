[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Plan', 'Preflight', 'Observe')]
    [string]$Action,

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$CaptureId = ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-wrong-change-t1a-to-t2c-v1'),

    [ValidateRange(180, 600)]
    [int]$DurationSeconds = 420,

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$PrinterHost = 'k1max-root',

    [switch]$Execute,
    [string]$Gate,
    [switch]$HumanPresent,
    [switch]$ImmediateStopAvailable,
    [switch]$HumanConfirmedT2CIdentity
)

$ErrorActionPreference = 'Stop'
$Mission = 'G4-K1-CONTROL-WRONG-CHANGE-T1A-TO-T2C-V1'
$ExpectedObserverSha256 = '3c91e8e77395cdab37443180d762bc78d76d55911049578584c110c3aba6738b'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$RawRoot = Join-Path $WorkspaceRoot 'inventory\raw'
$SessionDirectory = Join-Path $RawRoot $CaptureId
$CapturePath = Join-Path $SessionDirectory 'wrong-change-t1a-to-t2c.safe.jsonl'
$AnalysisPath = Join-Path $SessionDirectory 'wrong-change-t1a-to-t2c.analysis.json'
$MetadataPath = Join-Path $SessionDirectory 'local-metadata.json'
$ObserverPath = Join-Path $PSScriptRoot 'remote_observer.py'
$AnalyzerPath = Join-Path $PSScriptRoot 'analyze_capture.py'

function Get-LocalSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

if ($Action -eq 'Observe' -and (-not $Execute -or $Gate -cne $Mission)) {
    throw "Observation physique refusée : utilise -Execute -Gate '$Mission'."
}
if ($Action -in @('Plan', 'Preflight') -and ($Execute -or $Gate)) {
    throw 'Plan et Preflight sont sans drapeau de mutation.'
}
if ((Get-LocalSha256 $ObserverPath) -cne $ExpectedObserverSha256) {
    throw "L'observateur ne correspond pas à la version revue."
}
if ($Action -eq 'Plan') {
    [ordered]@{
        status = 'WRONG_CHANGE_T1A_TO_T2C_PLAN_OK'
        mission = $Mission
        observer_sha256 = $ExpectedObserverSha256
        installed_start_owner_sha256 = '678582e808d74f6b720ef3d6b52dc2c443c7a0652a62c484319e2b22fba7b0bc'
        starting_route = 'T1A'
        target_route = 'T2C'
        printer_connection = $false
        observer_gcode = $false
        observer_cfs_action = $false
        observer_remote_write = $false
        exact_gate_required_for = 'Observe_only'
        automatic_retry = $false
    } | ConvertTo-Json
    exit 0
}
if ($Action -eq 'Observe' -and (-not $HumanPresent -or -not $ImmediateStopAvailable -or -not $HumanConfirmedT2CIdentity)) {
    throw 'Observation réelle refusée : présence, arrêt immédiat et identité T2C doivent être confirmés.'
}
if (Test-Path -LiteralPath $SessionDirectory) {
    throw 'La capture existe déjà. Utilise un nouvel identifiant.'
}
New-Item -ItemType Directory -Path $SessionDirectory | Out-Null
$ResolvedRawRoot = (Resolve-Path -LiteralPath $RawRoot).Path
$ResolvedSession = (Resolve-Path -LiteralPath $SessionDirectory).Path
if (-not $ResolvedSession.StartsWith($ResolvedRawRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'La capture doit rester sous inventory/raw.'
}

$Metadata = [ordered]@{
    capture_id = $CaptureId
    mission = $Mission
    action = $Action
    duration_s = $(if ($Action -eq 'Observe') { $DurationSeconds } else { 0 })
    local_start = (Get-Date).ToString('o')
    observer_sha256 = $ExpectedObserverSha256
    automatic_retry = $false
    observer_gcode = $false
    observer_cfs_action = $false
    observer_remote_write = $false
    human_present = [bool]$HumanPresent
    immediate_stop_available = [bool]$ImmediateStopAvailable
    human_confirmed_t2c_identity = [bool]$HumanConfirmedT2CIdentity
}
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

$Program = (Get-Content -LiteralPath $ObserverPath -Raw).Replace("`r`n", "`n")
$RemoteArguments = $(if ($Action -eq 'Preflight') { 'preflight' } else { "observe $DurationSeconds" })
$RemoteCommand = "env PYTHONDONTWRITEBYTECODE=1 '/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' -B - $RemoteArguments"
if ($Action -eq 'Observe') {
    Write-Host 'NE DECLENCHE PAS ENCORE LE CHANGEMENT.'
    Write-Host 'Après la ligne kind=header, change T1A vers T2C UNE SEULE FOIS depuis l interface stock.'
    Write-Host 'L observateur ne commande rien et ne relance jamais l action.'
}
else {
    Write-Host 'PREFLIGHT STRICTEMENT EN LECTURE SEULE.'
}

$Program | & ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ConnectTimeout=8' `
    -o 'ServerAliveInterval=10' `
    -o 'ServerAliveCountMax=65' `
    $PrinterHost `
    $RemoteCommand 2>&1 | Tee-Object -FilePath $CapturePath | ForEach-Object { Write-Host $_ }
$SshExitCode = $LASTEXITCODE
$AnalysisExitCode = 0
if ($SshExitCode -eq 0 -and $Action -eq 'Observe') {
    $AnalysisOutput = & python.exe $AnalyzerPath $CapturePath 2>&1
    $AnalysisExitCode = $LASTEXITCODE
    $AnalysisOutput | Set-Content -LiteralPath $AnalysisPath -Encoding utf8
    $AnalysisOutput | Write-Output
}
elseif ($SshExitCode -ne 0) {
    $AnalysisExitCode = 1
}

$Metadata.local_end = (Get-Date).ToString('o')
$Metadata.ssh_exit_code = $SshExitCode
$Metadata.analysis_exit_code = $AnalysisExitCode
$Metadata.capture_path = $CapturePath
$Metadata.analysis_path = $(if ($Action -eq 'Observe') { $AnalysisPath } else { $null })
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8
if ($SshExitCode -ne 0 -or $AnalysisExitCode -ne 0) {
    Write-Host "WRONG_CHANGE_T1A_TO_T2C_CLOSED_KO action=$Action capture=$CapturePath"
    exit 1
}
Write-Host "WRONG_CHANGE_T1A_TO_T2C_OK action=$Action capture=$CapturePath"
exit 0
