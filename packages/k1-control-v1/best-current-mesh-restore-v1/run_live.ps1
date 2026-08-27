[CmdletBinding()]
param(
    [ValidateSet('Preflight', 'Restore')]
    [string]$Action = 'Preflight',

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$CaptureId = ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-best-current-mesh-restore-v1'),

    [string]$PrinterHost = 'k1max-root',
    [switch]$Execute,
    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-V1'
$ExpectedProgramSha256 = '7372a3751a1af928c2f8594df3308ad6e529971f1a43b72342adcbda9bfe2900'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$RawRoot = Join-Path $WorkspaceRoot 'inventory\raw'
$SessionDirectory = Join-Path $RawRoot $CaptureId
$CapturePath = Join-Path $SessionDirectory 'best-current-mesh-restore.safe.jsonl'
$MetadataPath = Join-Path $SessionDirectory 'local-metadata.json'
$RemoteProgramPath = Join-Path $PSScriptRoot 'remote_gate.py'

if ($Action -ceq 'Restore' -and (-not $Execute -or $Gate -cne $RequiredGate)) {
    throw "Remise au meilleur profil bloquée : -Execute et -Gate '$RequiredGate' sont obligatoires."
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
$ActualProgramSha256 = (Get-FileHash -LiteralPath $RemoteProgramPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualProgramSha256 -cne $ExpectedProgramSha256) {
    throw "Le programme distant ne correspond pas à la version revue : $ActualProgramSha256"
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
    remote_program_sha256 = $ActualProgramSha256
    remote_file_write = $false
    service_action = $false
    heater_or_motion_action = $false
    identity_values_exported = $false
}
$Metadata | ConvertTo-Json | Set-Content -LiteralPath $MetadataPath -Encoding utf8

$RemoteProgram = (Get-Content -LiteralPath $RemoteProgramPath -Raw).Replace("`r`n", "`n")
$RemoteAction = $Action.ToLowerInvariant()
$RemoteCommand = "'/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' - '$RemoteAction'"

Write-Host "REMISE AU MEILLEUR PROFIL ACTUEL : action=$Action capture=$CaptureId"
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

Write-Host "BEST_CURRENT_MESH_RESTORE_V1_CLOSED exit_code=$SshExitCode capture=$CapturePath"
exit $SshExitCode
