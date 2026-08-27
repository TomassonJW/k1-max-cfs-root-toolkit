[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$CaptureId = ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-clean-motion-manual-geometry'),

    [ValidateRange(60, 1800)]
    [int]$DurationSeconds = 900,

    [ValidateRange(0.2, 2.0)]
    [double]$IntervalSeconds = 0.5,

    [string]$PrinterHost = 'k1max-root',
    [switch]$OperatorPresent,
    [switch]$PlateClear
)

$ErrorActionPreference = 'Stop'
$Mission = 'G4-K1-CONTROL-CLEAN-MOTION-V1-MANUAL-GEOMETRY-CAPTURE'
$ExpectedProgramSha256 = '9d56fc37a839dac3feb6b36289f6648fd782370bf957bf707637c5209f8590eb'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$RawRoot = Join-Path $WorkspaceRoot 'inventory\raw'
$SessionDirectory = Join-Path $RawRoot $CaptureId
$CapturePath = Join-Path $SessionDirectory 'clean-motion-manual-geometry.safe.jsonl'
$MetadataPath = Join-Path $SessionDirectory 'local-metadata.json'
$RemoteProgramPath = Join-Path $PSScriptRoot 'remote_manual_geometry_capture.py'

if (-not $OperatorPresent -or -not $PlateClear) {
    throw 'Capture bloquée : -OperatorPresent et -PlateClear sont obligatoires.'
}
if (-not (Test-Path -LiteralPath $RawRoot -PathType Container)) {
    throw 'Le dossier privé inventory/raw est introuvable.'
}
if (Test-Path -LiteralPath $SessionDirectory) {
    throw 'La capture existe déjà. Utilise un nouvel identifiant.'
}
$ActualProgramSha256 = (Get-FileHash -LiteralPath $RemoteProgramPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualProgramSha256 -cne $ExpectedProgramSha256) {
    throw "Le collecteur ne correspond pas à la version revue : $ActualProgramSha256"
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
    local_start = (Get-Date).ToString('o')
    ssh_alias = $PrinterHost
    duration_seconds = $DurationSeconds
    interval_seconds = $IntervalSeconds
    remote_program_sha256 = $ActualProgramSha256
    operator_present = $true
    plate_clear = $true
    operator_manual_motion = $true
    codex_motion = $false
    http_methods = @('GET')
    gcode_sent = $false
    remote_file_read = $false
    remote_file_write = $false
    service_action = $false
    heating = $false
    extrusion = $false
    cfs_action = $false
}
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

$RemoteProgram = (Get-Content -LiteralPath $RemoteProgramPath -Raw).Replace("`r`n", "`n")
$DurationArgument = $DurationSeconds.ToString([Globalization.CultureInfo]::InvariantCulture)
$IntervalArgument = $IntervalSeconds.ToString([Globalization.CultureInfo]::InvariantCulture)
$RemoteCommand = "'/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' - '$DurationArgument' '$IntervalArgument'"
$Utf8NoBom = New-Object Text.UTF8Encoding($false)
$Writer = New-Object IO.StreamWriter($CapturePath, $false, $Utf8NoBom)
$SshExitCode = -1

Write-Host "CAPTURE MANUELLE GÉOMÉTRIE : capture=$CaptureId durée=${DurationSeconds}s intervalle=${IntervalSeconds}s"
Write-Host 'Codex observe uniquement. Les mouvements sont effectués manuellement par Thomas.'

try {
    $RemoteProgram | & ssh.exe `
        -o 'BatchMode=yes' `
        -o 'PasswordAuthentication=no' `
        -o 'KbdInteractiveAuthentication=no' `
        -o 'ConnectTimeout=8' `
        -o 'ServerAliveInterval=10' `
        -o 'ServerAliveCountMax=5' `
        $PrinterHost `
        $RemoteCommand 2>&1 | ForEach-Object {
            $Line = [string]$_
            $Writer.WriteLine($Line)
            $Writer.Flush()
            if ($Line.Contains('"record":"control"')) {
                Write-Output $Line
            }
        }
    $SshExitCode = $LASTEXITCODE
}
finally {
    $Writer.Dispose()
}

$Metadata.local_end = (Get-Date).ToString('o')
$Metadata.ssh_exit_code = $SshExitCode
$Metadata.capture_path = $CapturePath
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

Write-Host "CLEAN_MOTION_MANUAL_GEOMETRY_CAPTURE_CLOSED exit_code=$SshExitCode capture=$CapturePath"
exit $SshExitCode
