[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$PackageRoot = $PSScriptRoot
$ProgramPath = Join-Path $PackageRoot 'remote_baseline_probe.py'
$Program = [IO.File]::ReadAllText($ProgramPath).Replace("`r`n", "`n")
$Options = @(
    '-o', 'BatchMode=yes',
    '-o', 'PasswordAuthentication=no',
    '-o', 'KbdInteractiveAuthentication=no',
    '-o', 'ConnectTimeout=8'
)
$Output = $Program | & ssh.exe @Options 'k1max-root' '/usr/share/klippy-env/bin/python -B -' 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Sonde K1 en lecture seule KO :`n$($Output -join "`n")"
}
$Marker = $Output | Select-Object -Last 1
if ($Marker -cne 'REMOTE_STOCK_DERIVED_HANDOFF_MOONRAKER_BASELINE_READ_ONLY_OK') {
    throw "Marqueur de sonde absent : $Marker"
}
Write-Output ($Output | Select-Object -First 1)
Write-Output $Marker
