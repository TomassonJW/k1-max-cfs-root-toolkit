[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-LIVE-EFFECT-V1')]
    [string]$Gate,

    [Parameter(Mandatory = $true)]
    [switch]$Execute,

    [Parameter(Mandatory = $true)]
    [string]$SessionDirectory,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SessionLabel,

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$PrinterHost = 'k1max-root'
)

$ErrorActionPreference = 'Stop'
if (-not $Execute) {
    throw 'Le pilote reste inerte sans -Execute.'
}

$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$rawRoot = Join-Path $workspaceRoot 'inventory\raw'
if (-not (Test-Path -LiteralPath $rawRoot -PathType Container)) {
    throw 'Le dossier prive inventory/raw est introuvable.'
}
if (-not (Test-Path -LiteralPath $SessionDirectory -PathType Container)) {
    New-Item -ItemType Directory -Path $SessionDirectory -Force | Out-Null
}
$resolvedRawRoot = (Resolve-Path -LiteralPath $rawRoot).Path
$resolvedSession = (Resolve-Path -LiteralPath $SessionDirectory).Path
if (-not $resolvedSession.StartsWith($resolvedRawRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Le dossier de session doit rester sous inventory/raw.'
}

$capturePath = Join-Path $resolvedSession "$SessionLabel.safe.jsonl"
$metadataPath = Join-Path $resolvedSession "$SessionLabel.local-metadata.json"
if (Test-Path -LiteralPath $capturePath) {
    throw 'La capture existe deja. Utilise un nouvel identifiant de session.'
}

$observerPath = Join-Path $PSScriptRoot '..\cfs-owner-observability-live-read-only-v2\remote_observer.py'
$observerSource = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $observerPath)).Replace("`r`n", "`n")
$effectSource = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'remote_effect_gate.py')).Replace("`r`n", "`n")
$remoteProgram = $observerSource + "`n" + $effectSource
$remoteCommand = "env PYTHONDONTWRITEBYTECODE=1 K1_OBSERVER_LIBRARY=1 '/usr/data/k1-control-v1/current/moonraker/moonraker-env/bin/python' -B -"

$metadata = [ordered]@{
    session_label = $SessionLabel
    local_start = (Get-Date).ToString('o')
    mission = $Gate
    mode = 'single_ssh_continuous_observer_one_disable_one_restore'
    ssh_alias = $PrinterHost
    reviewed_commands = @('BOX_ENABLE_AUTO_REFILL ENABLE=0', 'BOX_ENABLE_AUTO_REFILL ENABLE=1')
    maximum_attempts_each = 1
    remote_files = $false
    service_actions = $false
    filament_actions = $false
    heater_actions = $false
    motion_actions = $false
}
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8

Write-Host "EXCLUSION PROPRIETAIRE STOCK : $SessionLabel"
Write-Host 'Une desactivation, preuve x2, une restauration exacte, preuve x2.'

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
$metadata.capture_path = $capturePath
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8

Write-Host "CFS_OWNER_EXCLUSION_GUARD_LIVE_EFFECT_V1_CLOSED exit_code=$sshExitCode capture=$capturePath"
exit $sshExitCode
