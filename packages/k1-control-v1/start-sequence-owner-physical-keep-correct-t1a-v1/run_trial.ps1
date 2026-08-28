[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Preflight', 'Upload', 'Run')]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$CaptureId,

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$PrinterHost = 'k1max-root',

    [ValidateRange(300, 1200)]
    [int]$MaximumDurationSeconds = 900,

    [switch]$Execute,
    [string]$Gate,
    [switch]$HumanPresent,
    [switch]$PlateClear,
    [switch]$ManualNozzleCleanConfirmed,
    [switch]$ImmediateStopAvailable
)

$ErrorActionPreference = 'Stop'
$Mission = 'G4-K1-CONTROL-START-SEQUENCE-OWNER-PHYSICAL-KEEP-CORRECT-T1A-V1'
$ExpectedGcodeSha256 = 'eeaf9822a7016f89da45be83e4435f68c1d28441c469a9cde078c9645fcbf429'
$ExpectedGcodeBytes = 90552
$ExpectedTrialSha256 = '9ca8bfc7fdc2cd457346fc8a13a9f749d6c92fdd98306e35032c8c6617f12fbc'
$ExpectedInstallerSha256 = '6b2b7d3d82928d1f34e52adca877e33f0d6c9a6c8f5ccdca2a73f004e4625b3b'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$RawRoot = Join-Path $WorkspaceRoot 'inventory\raw'
$SessionDirectory = Join-Path $RawRoot $CaptureId
$GcodePath = Join-Path $RawRoot '20260828-goal3-start-owner-physical-keep-correct-t1a-v1\K1-START-OWNER-T1A-2LAYER.gcode'
$TrialPath = Join-Path $PSScriptRoot 'remote_trial.py'
$InstallerPath = Join-Path $PSScriptRoot 'remote_install.py'
$AnalyzerPath = Join-Path $PSScriptRoot 'analyze_capture.py'
$CapturePath = Join-Path $SessionDirectory 'keep-correct-t1a-physical.safe.jsonl'
$AnalysisPath = Join-Path $SessionDirectory 'keep-correct-t1a-physical.analysis.json'
$MetadataPath = Join-Path $SessionDirectory 'local-metadata.json'

function Get-LocalSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Invoke-RemoteProgram {
    param(
        [Parameter(Mandatory = $true)][string]$Program,
        [Parameter(Mandatory = $true)][string]$RemoteArguments,
        [Parameter(Mandatory = $true)][string]$OutputPath
    )
    $Normalized = $Program.Replace("`r`n", "`n")
    $Command = "env PYTHONDONTWRITEBYTECODE=1 '/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' -B - $RemoteArguments"
    $Normalized | & ssh.exe `
        -o 'BatchMode=yes' `
        -o 'PasswordAuthentication=no' `
        -o 'KbdInteractiveAuthentication=no' `
        -o 'ConnectTimeout=8' `
        -o 'ServerAliveInterval=10' `
        -o 'ServerAliveCountMax=35' `
        $PrinterHost `
        $Command 2>&1 | Tee-Object -FilePath $OutputPath | ForEach-Object { Write-Host $_ }
    return $LASTEXITCODE
}

if (-not $Execute -or $Gate -cne $Mission) {
    throw "Action refusée : utilise -Execute -Gate '$Mission'."
}
if (-not (Test-Path -LiteralPath $GcodePath -PathType Leaf)) {
    throw 'Le G-code privé vérifié est introuvable.'
}
if ((Get-Item -LiteralPath $GcodePath).Length -ne $ExpectedGcodeBytes -or (Get-LocalSha256 $GcodePath) -cne $ExpectedGcodeSha256) {
    throw 'Le G-code local ne correspond pas au fichier revu.'
}
if ((Get-LocalSha256 $TrialPath) -cne $ExpectedTrialSha256) {
    throw 'Le pilote distant ne correspond pas à la version revue.'
}
if ((Get-LocalSha256 $InstallerPath) -cne $ExpectedInstallerSha256) {
    throw "L'installateur distant ne correspond pas à la version revue."
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
    local_start = (Get-Date).ToString('o')
    gcode_sha256 = $ExpectedGcodeSha256
    gcode_bytes = $ExpectedGcodeBytes
    automatic_retry = $false
    human_present = [bool]$HumanPresent
    plate_clear = [bool]$PlateClear
    manual_nozzle_clean_confirmed = [bool]$ManualNozzleCleanConfirmed
    immediate_stop_available = [bool]$ImmediateStopAvailable
}
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

$TrialProgram = Get-Content -LiteralPath $TrialPath -Raw
$InstallerProgram = Get-Content -LiteralPath $InstallerPath -Raw
$ExitCode = 1
if ($Action -eq 'Preflight') {
    $ExitCode = Invoke-RemoteProgram -Program $TrialProgram -RemoteArguments "preflight none" -OutputPath $CapturePath
}
elseif ($Action -eq 'Upload') {
    $PreflightPath = Join-Path $SessionDirectory 'preflight.safe.jsonl'
    $PreflightExit = Invoke-RemoteProgram -Program $TrialProgram -RemoteArguments "preflight none" -OutputPath $PreflightPath
    if ($PreflightExit -ne 0) {
        throw "Préflight refusé avant transfert : code $PreflightExit."
    }
    $StageName = ".k1-control-stage-$CaptureId.gcode"
    $RemoteStage = "$PrinterHost`:/usr/data/printer_data/gcodes/$StageName"
    & scp.exe `
        -o 'BatchMode=yes' `
        -o 'PasswordAuthentication=no' `
        -o 'KbdInteractiveAuthentication=no' `
        -o 'ConnectTimeout=8' `
        $GcodePath `
        $RemoteStage 2>&1 | Tee-Object -FilePath (Join-Path $SessionDirectory 'scp.log')
    if ($LASTEXITCODE -ne 0) {
        throw "Le transfert borné a échoué : code $LASTEXITCODE."
    }
    $InstallPath = Join-Path $SessionDirectory 'install.safe.jsonl'
    $InstallExit = Invoke-RemoteProgram -Program $InstallerProgram -RemoteArguments "$StageName $ExpectedGcodeSha256" -OutputPath $InstallPath
    if ($InstallExit -ne 0) {
        throw "L'installation atomique a échoué : code $InstallExit."
    }
    $ExitCode = Invoke-RemoteProgram -Program $TrialProgram -RemoteArguments "preflight $ExpectedGcodeSha256" -OutputPath $CapturePath
}
else {
    if (-not $HumanPresent -or -not $PlateClear -or -not $ManualNozzleCleanConfirmed -or -not $ImmediateStopAvailable) {
        throw 'Run refusé : présence, plateau libre, nettoyage manuel et arrêt immédiat doivent être confirmés.'
    }
    $ExitCode = Invoke-RemoteProgram -Program $TrialProgram -RemoteArguments "execute $ExpectedGcodeSha256 $MaximumDurationSeconds" -OutputPath $CapturePath
    $AnalysisOutput = & python.exe $AnalyzerPath $CapturePath 2>&1
    $AnalysisExit = $LASTEXITCODE
    $AnalysisOutput | Set-Content -LiteralPath $AnalysisPath -Encoding utf8
    $AnalysisOutput | Write-Output
    if ($ExitCode -eq 0 -and $AnalysisExit -ne 0) {
        $ExitCode = $AnalysisExit
    }
}

$Metadata.local_end = (Get-Date).ToString('o')
$Metadata.exit_code = $ExitCode
$Metadata.capture_path = $CapturePath
$Metadata.analysis_path = $(if ($Action -eq 'Run') { $AnalysisPath } else { $null })
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8
if ($ExitCode -ne 0) {
    Write-Host "KEEP_CORRECT_T1A_PHYSICAL_CLOSED_KO action=$Action exit_code=$ExitCode capture=$CapturePath"
    exit $ExitCode
}
Write-Host "KEEP_CORRECT_T1A_PHYSICAL_OK action=$Action capture=$CapturePath"
exit 0
