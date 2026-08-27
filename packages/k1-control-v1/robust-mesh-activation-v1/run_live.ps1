[CmdletBinding()]
param(
    [ValidateSet('Preflight', 'Activate')]
    [string]$Action = 'Preflight',

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$CaptureId = ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-robust-mesh-activation-v1'),

    [string]$PrinterHost = 'k1max-root',
    [switch]$Execute,
    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1'
$ExpectedRemoteProgramSha256 = '988079f1fe5a93e6e306e569798e1d2084503a162b358e587d66a640c3349cd0'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$RawRoot = Join-Path $WorkspaceRoot 'inventory\raw'
$SessionDirectory = Join-Path $RawRoot $CaptureId
$CapturePath = Join-Path $SessionDirectory 'robust-mesh-activation.safe.jsonl'
$MetadataPath = Join-Path $SessionDirectory 'local-metadata.json'
$RemoteProgramPath = Join-Path $PSScriptRoot 'remote_gate.py'

if ($Action -ceq 'Activate' -and (-not $Execute -or $Gate -cne $RequiredGate)) {
    throw "Activation bloquée : -Execute et -Gate '$RequiredGate' sont obligatoires."
}
if ($Action -ceq 'Preflight' -and ($Execute -or $Gate)) {
    throw 'Le préflight de lecture seule ne prend aucun drapeau de mutation.'
}
if (-not (Test-Path -LiteralPath $RawRoot -PathType Container)) {
    throw 'Le dossier privé inventory/raw est introuvable.'
}
if (Test-Path -LiteralPath $SessionDirectory) {
    throw 'La capture existe déjà. Utilise un nouvel identifiant.'
}
$ActualRemoteProgramSha256 = (Get-FileHash -LiteralPath $RemoteProgramPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualRemoteProgramSha256 -cne $ExpectedRemoteProgramSha256) {
    throw "Le programme distant ne correspond pas à la version revue : $ActualRemoteProgramSha256"
}

New-Item -ItemType Directory -Path $SessionDirectory | Out-Null
$ResolvedRawRoot = (Resolve-Path -LiteralPath $RawRoot).Path
$ResolvedSession = (Resolve-Path -LiteralPath $SessionDirectory).Path
if (-not $ResolvedSession.StartsWith($ResolvedRawRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Le dossier de capture doit rester sous inventory/raw.'
}

$Metadata = [ordered]@{
    capture_id = $CaptureId
    mission = $RequiredGate
    action = $Action
    local_start = (Get-Date).ToString('o')
    ssh_alias = $PrinterHost
    remote_program_sha256 = $ActualRemoteProgramSha256
    remote_file_write = $false
    service_action = $false
    heater_or_motion_action = $false
}
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

$RemoteProgram = (Get-Content -LiteralPath $RemoteProgramPath -Raw).Replace("`r`n", "`n")
$RemoteAction = $Action.ToLowerInvariant()
$RemoteCommand = "'/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' - '$RemoteAction'"

Write-Host "GATE MESH ROBUSTE : action=$Action capture=$CaptureId"
Write-Host 'Aucun fichier distant, restart, chauffe, mouvement, homing, palpage ou impression.'

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

Write-Host "ROBUST_MESH_ACTIVATION_V1_CLOSED exit_code=$SshExitCode capture=$CapturePath"
exit $SshExitCode
