[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$CaptureId = ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-clean-motion-v1-read-only'),
    [string]$PrinterHost = 'k1max-root'
)

$ErrorActionPreference = 'Stop'
$Mission = 'G4-K1-CONTROL-CLEAN-MOTION-V1-READ-ONLY-SOURCES'
$ExpectedRemoteProgramSha256 = '36b077e706cc2532f89cbb2389442d667738a9fbb0ef7a7b5b864bd3f8c58229'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$RawRoot = Join-Path $WorkspaceRoot 'inventory\raw'
$SessionDirectory = Join-Path $RawRoot $CaptureId
$CapturePath = Join-Path $SessionDirectory 'clean-motion-read-only.safe.jsonl'
$MetadataPath = Join-Path $SessionDirectory 'local-metadata.json'
$RemoteProgramPath = Join-Path $PSScriptRoot 'remote_geometry_read_only.py'

if (-not (Test-Path -LiteralPath $RawRoot -PathType Container)) {
    throw 'Le dossier privé inventory/raw est introuvable.'
}
if (Test-Path -LiteralPath $SessionDirectory) {
    throw 'La capture existe déjà. Utilise un nouvel identifiant.'
}
$ActualRemoteProgramSha256 = (Get-FileHash -LiteralPath $RemoteProgramPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualRemoteProgramSha256 -cne $ExpectedRemoteProgramSha256) {
    throw "Le collecteur distant ne correspond pas à la version revue : $ActualRemoteProgramSha256"
}

New-Item -ItemType Directory -Path $SessionDirectory | Out-Null
$ResolvedRawRoot = (Resolve-Path -LiteralPath $RawRoot).Path
$ResolvedSession = (Resolve-Path -LiteralPath $SessionDirectory).Path
if (-not $ResolvedSession.StartsWith($ResolvedRawRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Le dossier de capture doit rester sous inventory/raw.'
}

$RemoteProgram = (Get-Content -LiteralPath $RemoteProgramPath -Raw).Replace("`r`n", "`n")
$RemoteCommand = "'/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' -"
$Metadata = [ordered]@{
    capture_id = $CaptureId
    mission = $Mission
    local_start = (Get-Date).ToString('o')
    ssh_alias = $PrinterHost
    remote_program_sha256 = $ActualRemoteProgramSha256
    http_methods = @('GET')
    gcode_sent = $false
    remote_file_read = $false
    remote_file_write = $false
    service_action = $false
    heater_or_motion_action = $false
}
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

Write-Host "LECTURE SEULE SOURCES CLEAN-MOTION : capture=$CaptureId"
Write-Host 'GET Moonraker uniquement ; aucun code complet de macro exporté.'

$Output = $RemoteProgram | & ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ConnectTimeout=8' `
    -o 'ServerAliveInterval=10' `
    -o 'ServerAliveCountMax=3' `
    $PrinterHost `
    $RemoteCommand 2>&1
$SshExitCode = $LASTEXITCODE
$Output | Set-Content -LiteralPath $CapturePath -Encoding utf8
$Output | Write-Output

$Metadata.local_end = (Get-Date).ToString('o')
$Metadata.ssh_exit_code = $SshExitCode
$Metadata.capture_path = $CapturePath
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

Write-Host "CLEAN_MOTION_V1_READ_ONLY_CLOSED exit_code=$SshExitCode capture=$CapturePath"
exit $SshExitCode
