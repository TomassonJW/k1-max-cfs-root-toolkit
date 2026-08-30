[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SessionDirectory,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SessionLabel,

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$PrinterHost = 'k1max-root'
)

$ErrorActionPreference = 'Stop'

$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$rawRoot = (Resolve-Path (Join-Path $workspaceRoot 'inventory\raw')).Path
$requestedSession = [IO.Path]::GetFullPath($SessionDirectory)
if (-not $requestedSession.StartsWith($rawRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Le dossier de session doit rester sous inventory/raw.'
}
if (-not (Test-Path -LiteralPath $requestedSession -PathType Container)) {
    New-Item -ItemType Directory -Path $requestedSession | Out-Null
}
$resolvedSession = (Resolve-Path -LiteralPath $requestedSession).Path
$capturePath = Join-Path $resolvedSession "$SessionLabel.jinja.txt"
$metadataPath = Join-Path $resolvedSession "$SessionLabel.jinja.local-metadata.json"
if (Test-Path -LiteralPath $capturePath) {
    throw 'Cette validation existe deja. Utilise un nouvel identifiant de session.'
}

$candidatePath = Join-Path $PSScriptRoot '..\start-sequence-owner-camera-purge-r3\k1-control-start-sequence-owner-camera-purge-r3.cfg'
$templatePath = Join-Path $PSScriptRoot 'remote_jinja_validate.py'
$candidateBytes = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $candidatePath).Path)
$candidateBase64 = [Convert]::ToBase64String($candidateBytes)
$remoteProgram = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $templatePath).Path).Replace('__CONFIG_BASE64__', $candidateBase64)
$remoteProgram = $remoteProgram.Replace("`r`n", "`n")
$remoteCommand = "env PYTHONDONTWRITEBYTECODE=1 '/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' -B -"

$metadata = [ordered]@{
    schema = 1
    mission = 'G4-K1-CONTROL-CAMERA-REFERENCE-LIBRARY-AND-R3-COLD-VALIDATION-V1'
    session_label = $SessionLabel
    local_start = (Get-Date).ToString('o')
    ssh_alias = $PrinterHost
    remote_mode = 'stdin_jinja_parse_only'
    remote_files_written = $false
    gcode_sent = $false
    heater_action = $false
    motion_action = $false
    cfs_action = $false
    service_action = $false
}

$remoteProgram | & ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ConnectTimeout=8' `
    -o 'ServerAliveInterval=10' `
    -o 'ServerAliveCountMax=3' `
    $PrinterHost `
    $remoteCommand | Set-Content -LiteralPath $capturePath -Encoding utf8

$sshExitCode = $LASTEXITCODE
$metadata.local_end = (Get-Date).ToString('o')
$metadata.ssh_exit_code = $sshExitCode
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8

if ($sshExitCode -ne 0) {
    Write-Host "REMOTE_R3_JINJA_PARSE_KO exit_code=$sshExitCode capture=$capturePath"
    exit $sshExitCode
}
$output = Get-Content -LiteralPath $capturePath -Raw
if ($output -notmatch 'REMOTE_R3_JINJA_PARSE_OK sections=16') {
    Write-Host "REMOTE_R3_JINJA_PARSE_KO marker_missing capture=$capturePath"
    exit 2
}
Write-Host "REMOTE_R3_JINJA_PARSE_CLOSED_OK capture=$capturePath"
