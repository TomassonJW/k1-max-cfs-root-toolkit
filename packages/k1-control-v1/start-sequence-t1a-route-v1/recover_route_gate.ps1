[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$CaptureId,

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$PrinterHost = 'k1max-root',

    [switch]$Execute,

    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-START-SEQUENCE-T1A-ROUTE-V1'
$ExpectedProgramSha256 = 'da7b5d266f1e60a66c616c6ef1886b99d9165e9db96d7eea1d9a9a6c67377343'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$RawRoot = Join-Path $WorkspaceRoot 'inventory\raw'
$SessionDirectory = Join-Path $RawRoot $CaptureId
$CapturePath = Join-Path $SessionDirectory 'start-sequence-t1a-route-v1.recovery.safe.json'
$MetadataPath = Join-Path $SessionDirectory 'local-metadata.json'
$RemoteProgramPath = Join-Path $PSScriptRoot 'remote_recovery.py'

if (-not $Execute -or $Gate -cne $RequiredGate) {
    throw "Récupération bloquée : -Execute et -Gate '$RequiredGate' sont obligatoires."
}
if (-not (Test-Path -LiteralPath $RawRoot -PathType Container)) {
    throw 'Le dossier privé inventory/raw est introuvable.'
}
if (Test-Path -LiteralPath $SessionDirectory) {
    throw 'La capture existe déjà. Utilise un nouvel identifiant.'
}
$ActualProgramSha256 = (Get-FileHash -LiteralPath $RemoteProgramPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualProgramSha256 -cne $ExpectedProgramSha256) {
    throw "Le programme de récupération ne correspond pas à la version revue : $ActualProgramSha256"
}

New-Item -ItemType Directory -Path $SessionDirectory | Out-Null
$Metadata = [ordered]@{
    capture_id = $CaptureId
    mission = $RequiredGate
    action = 'recover_after_wrong_stock_button'
    local_start = (Get-Date).ToString('o')
    ssh_alias = $PrinterHost
    remote_program_sha256 = $ActualProgramSha256
    allowed_commands = @('BED_MESH_PROFILE LOAD=k1_p001_t055_r001_n11x11', 'M84')
    heater_action = $false
    motion_action = $false
    extrusion_action = $false
    cfs_action = $false
    remote_write = $false
    service_action = $false
    automatic_retry = $false
}
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

$RemoteProgram = (Get-Content -LiteralPath $RemoteProgramPath -Raw).Replace("`r`n", "`n")
$RemoteCommand = "env PYTHONDONTWRITEBYTECODE=1 '/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' -B -"
$Output = $RemoteProgram | & ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ConnectTimeout=8' `
    -o 'ServerAliveInterval=10' `
    -o 'ServerAliveCountMax=3' `
    $PrinterHost `
    $RemoteCommand 2>&1
$ExitCode = $LASTEXITCODE
$Output | Set-Content -LiteralPath $CapturePath -Encoding utf8
$Output | Write-Output
$Metadata.local_end = (Get-Date).ToString('o')
$Metadata.ssh_exit_code = $ExitCode
$Metadata.capture_path = $CapturePath
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8
Write-Host "START_SEQUENCE_T1A_ROUTE_V1_RECOVERY_CLOSED exit_code=$ExitCode capture=$CapturePath"
exit $ExitCode
