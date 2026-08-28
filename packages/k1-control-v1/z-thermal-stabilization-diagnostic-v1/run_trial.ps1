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

    [ValidateRange(600, 1200)]
    [int]$MaximumDurationSeconds = 1200,

    [switch]$Execute,
    [string]$Gate,
    [switch]$HumanPresent,
    [switch]$PlateClear,
    [switch]$ManualNozzleCleanConfirmed,
    [switch]$ImmediateStopAvailable
)

$ErrorActionPreference = 'Stop'
$Mission = 'G4-K1-CONTROL-Z-THERMAL-STABILIZATION-DIAGNOSTIC-V1'
$ExpectedGcodeSha256 = '657db94f006a92b5f4b68ee3afd4674f56963208f90c145892cc1205a2582ce1'
$ExpectedGcodeBytes = 90735
$ExpectedBaseTrialSha256 = '5f461db624acaa8682ec20bcd3eed001da39688f1e19a880d8096685c350a68f'
$ExpectedBaseInstallerSha256 = 'ff84e23462dc642d916bc7d83cfca0eea53414253b7ad940c1cb46be56a5ffa0'
$ExpectedDerivedTrialSha256 = '73cf0aca9b757140a3064677cc3cd2cbebdcb0efc55488657f353403214021a1'
$ExpectedDerivedInstallerSha256 = 'bf7d7e0d67b5598645c927dfbe7c2e17989877c4b4fc4a1ba51b8c840d9453a7'
$OldMission = 'G4-K1-CONTROL-START-SEQUENCE-OWNER-PHYSICAL-KEEP-CORRECT-T1A-V1'
$OldGcodeName = 'K1-START-OWNER-T1A-2LAYER.gcode'
$GcodeName = 'K1-Z-THERMAL-SOAK-200S-T1A-2LAYER.gcode'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$RawRoot = Join-Path $WorkspaceRoot 'inventory\raw'
$SessionDirectory = Join-Path $RawRoot $CaptureId
$GcodePath = Join-Path $RawRoot '20260829-goal3-z-thermal-stabilization-diagnostic-v1\K1-Z-THERMAL-SOAK-200S-T1A-2LAYER.gcode'
$BasePackage = Join-Path $WorkspaceRoot 'packages\k1-control-v1\start-sequence-owner-physical-keep-correct-t1a-v1'
$BaseTrialPath = Join-Path $BasePackage 'remote_trial.py'
$BaseInstallerPath = Join-Path $BasePackage 'remote_install.py'
$AnalyzerPath = Join-Path $PSScriptRoot 'analyze_capture.py'
$CapturePath = Join-Path $SessionDirectory 'z-thermal-stabilization.safe.jsonl'
$AnalysisPath = Join-Path $SessionDirectory 'z-thermal-stabilization.analysis.json'
$MetadataPath = Join-Path $SessionDirectory 'local-metadata.json'

function Get-LocalSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-TextSha256 {
    param([Parameter(Mandatory = $true)][string]$Text)
    $Hasher = [Security.Cryptography.SHA256]::Create()
    try {
        $Bytes = [Text.Encoding]::UTF8.GetBytes($Text)
        return -join ($Hasher.ComputeHash($Bytes) | ForEach-Object { $_.ToString('x2') })
    }
    finally {
        $Hasher.Dispose()
    }
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
    throw 'Le G-code privé du diagnostic est introuvable.'
}
if ((Get-Item -LiteralPath $GcodePath).Length -ne $ExpectedGcodeBytes -or (Get-LocalSha256 $GcodePath) -cne $ExpectedGcodeSha256) {
    throw 'Le G-code privé ne correspond pas au candidat revu.'
}
if ((Get-LocalSha256 $BaseTrialPath) -cne $ExpectedBaseTrialSha256) {
    throw 'Le pilote distant de base a dérivé.'
}
if ((Get-LocalSha256 $BaseInstallerPath) -cne $ExpectedBaseInstallerSha256) {
    throw "L'installateur distant de base a dérivé."
}

$TrialProgram = Get-Content -LiteralPath $BaseTrialPath -Raw
$TrialProgram = $TrialProgram.Replace($OldMission, $Mission)
$TrialProgram = $TrialProgram.Replace($OldGcodeName, $GcodeName)
$TrialProgram = $TrialProgram.Replace('KEEP_CORRECT_T1A_PHYSICAL_', 'Z_THERMAL_STABILIZATION_DIAGNOSTIC_')
$InstallerProgram = Get-Content -LiteralPath $BaseInstallerPath -Raw
$InstallerProgram = $InstallerProgram.Replace($OldGcodeName, $GcodeName)
$InstallerProgram = $InstallerProgram.Replace('eeaf9822a7016f89da45be83e4435f68c1d28441c469a9cde078c9645fcbf429', ('0' * 64))
if ((Get-TextSha256 $TrialProgram) -cne $ExpectedDerivedTrialSha256) {
    throw 'Le pilote distant dérivé ne correspond pas à la version revue.'
}
if ((Get-TextSha256 $InstallerProgram) -cne $ExpectedDerivedInstallerSha256) {
    throw "L'installateur distant dérivé ne correspond pas à la version revue."
}
if (Test-Path -LiteralPath $SessionDirectory) {
    throw 'La capture existe déjà. Utilise un nouvel identifiant.'
}
New-Item -ItemType Directory -Path $SessionDirectory | Out-Null

$Metadata = [ordered]@{
    capture_id = $CaptureId
    mission = $Mission
    action = $Action
    local_start = (Get-Date).ToString('o')
    gcode_sha256 = $ExpectedGcodeSha256
    gcode_bytes = $ExpectedGcodeBytes
    soak_seconds = 200
    automatic_retry = $false
    human_present = [bool]$HumanPresent
    plate_clear = [bool]$PlateClear
    manual_nozzle_clean_confirmed = [bool]$ManualNozzleCleanConfirmed
    immediate_stop_available = [bool]$ImmediateStopAvailable
}
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

$ExitCode = 1
if ($Action -eq 'Preflight') {
    $ExitCode = Invoke-RemoteProgram -Program $TrialProgram -RemoteArguments 'preflight none' -OutputPath $CapturePath
}
elseif ($Action -eq 'Upload') {
    $PreflightPath = Join-Path $SessionDirectory 'preflight.safe.jsonl'
    $PreflightExit = Invoke-RemoteProgram -Program $TrialProgram -RemoteArguments 'preflight none' -OutputPath $PreflightPath
    if ($PreflightExit -ne 0) {
        throw "Préflight refusé avant transfert : code $PreflightExit."
    }
    $StageName = ".k1-control-stage-$CaptureId.gcode"
    $RemoteStage = "$PrinterHost`:/usr/data/printer_data/gcodes/$StageName"
    & scp.exe -O `
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
    $Python = (Get-Command python.exe -ErrorAction Stop).Source
    $AnalysisOutput = & $Python $AnalyzerPath $CapturePath 2>&1
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
    Write-Host "Z_THERMAL_STABILIZATION_DIAGNOSTIC_CLOSED_KO action=$Action exit_code=$ExitCode capture=$CapturePath"
    exit $ExitCode
}
Write-Host "Z_THERMAL_STABILIZATION_DIAGNOSTIC_OK action=$Action capture=$CapturePath"
exit 0
