[CmdletBinding()]
param(
    [string]$PrinterHost = 'k1max-root',
    [string]$EvidenceDirectory = 'inventory\raw\20260901-g4-k1-control-cfs-err8-load-tail-recovery-v1',
    [ValidateSet('run','takeover','finalize')]
    [string]$Action = 'run',
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if (-not $Execute) { throw 'Cette récupération exige -Execute.' }
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$DriverPath = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-cycle-activation-v1\remote_err8_load_tail_recovery.py'
$resolvedEvidence = [IO.Path]::GetFullPath((Join-Path $WorkspaceRoot $EvidenceDirectory))
$resolvedWorkspace = [IO.Path]::GetFullPath($WorkspaceRoot)
if (-not $resolvedEvidence.StartsWith($resolvedWorkspace + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'EvidenceDirectory hors workspace.'
}
New-Item -ItemType Directory -Path $resolvedEvidence -Force | Out-Null
$program = [IO.File]::ReadAllText($DriverPath).Replace("`r`n", "`n")
$arguments = @(
    '-o','BatchMode=yes','-o','PasswordAuthentication=no',
    '-o','KbdInteractiveAuthentication=no','-o','ConnectTimeout=8',
    $PrinterHost,
    "/usr/share/klippy-env/bin/python -B - '$Action'"
)
$output = $program | & ssh.exe @arguments 2>&1
if ($LASTEXITCODE -ne 0) { throw "Récupération EXTRUDE_ERR8 KO : $($output -join "`n")" }
$document = (($output -join "`n") | ConvertFrom-Json)
$document | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath (Join-Path $resolvedEvidence "err8-load-tail-$Action.json") -Encoding utf8
$document | ConvertTo-Json -Depth 40
