[CmdletBinding()]
param(
    [ValidateSet('Snapshot', 'Inspect', 'Run')]
    [string]$Action = 'Snapshot',
    [string]$PrinterHost = 'k1max-root',
    [string]$EvidenceDirectory = 'inventory\raw\20260831-cutter-recovery-v1',
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$DriverPath = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-cycle-activation-v1\remote_forward_purge_recovery.py'

if ($Action -in @('Inspect', 'Run') -and -not $Execute) {
    throw "$Action exige -Execute."
}

$resolvedEvidence = [IO.Path]::GetFullPath((Join-Path $WorkspaceRoot $EvidenceDirectory))
$resolvedWorkspace = [IO.Path]::GetFullPath($WorkspaceRoot)
if (-not $resolvedEvidence.StartsWith($resolvedWorkspace + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'EvidenceDirectory hors workspace.'
}
New-Item -ItemType Directory -Path $resolvedEvidence -Force | Out-Null

$program = [IO.File]::ReadAllText($DriverPath).Replace("`r`n", "`n")
$remoteAction = $Action.ToLowerInvariant()
$arguments = @(
    '-o', 'BatchMode=yes',
    '-o', 'PasswordAuthentication=no',
    '-o', 'KbdInteractiveAuthentication=no',
    '-o', 'ConnectTimeout=8',
    $PrinterHost,
    "/usr/share/klippy-env/bin/python -B - '$remoteAction'"
)
$output = $program | & ssh.exe @arguments 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Recuperation $Action KO : $($output -join "`n")"
}
$document = (($output -join "`n") | ConvertFrom-Json)
$document | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath (Join-Path $resolvedEvidence ("forward-purge-$remoteAction.json")) -Encoding UTF8
$document | ConvertTo-Json -Depth 40
