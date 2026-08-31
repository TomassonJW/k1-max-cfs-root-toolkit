[CmdletBinding()]
param(
    [string]$Gate,
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-STOCK-DERIVED-CYCLE-ACTIVATION-IDLE-V1'
if (-not $Execute -or $Gate -cne $RequiredGate) {
    throw "Lecture bloquee : -Execute et -Gate '$RequiredGate' sont obligatoires."
}

$PackageRoot = $PSScriptRoot
$WorkspaceRoot = (Resolve-Path (Join-Path $PackageRoot '..\..\..')).Path
if (-not $PackageRoot.StartsWith(
        $WorkspaceRoot + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase
    )) {
    throw 'Package hors workspace.'
}

$ProgramPath = Join-Path $PackageRoot 'remote_prospective_hash.py'
$OldSectionPath = Join-Path $WorkspaceRoot (
    'packages\k1-control-v1\stock-derived-handoff-moonraker-install-disabled-v1\moonraker-section.conf'
)
$NewSectionPath = Join-Path $PackageRoot 'moonraker-section.conf'
foreach ($path in @($ProgramPath, $OldSectionPath, $NewSectionPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Fichier requis absent : $path"
    }
}

$old = [Convert]::ToBase64String([IO.File]::ReadAllBytes($OldSectionPath))
$new = [Convert]::ToBase64String([IO.File]::ReadAllBytes($NewSectionPath))
$program = [IO.File]::ReadAllText($ProgramPath).
    Replace('__OLD_SECTION_B64__', $old).
    Replace('__NEW_SECTION_B64__', $new).
    Replace("`r`n", "`n")

$sshOptions = @(
    '-o', 'BatchMode=yes',
    '-o', 'PasswordAuthentication=no',
    '-o', 'KbdInteractiveAuthentication=no',
    '-o', 'ConnectTimeout=8'
)
$output = $program | & ssh.exe @sshOptions 'k1max-root' '/usr/share/klippy-env/bin/python -B -' 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Capture distante KO : $($output -join "`n")"
}
$line = $output | Select-Object -Last 1
[void]($line | ConvertFrom-Json)
Write-Output $line
Write-Output 'CAPTURE_STOCK_DERIVED_CYCLE_ACTIVATION_BASELINE_READ_ONLY_OK'
