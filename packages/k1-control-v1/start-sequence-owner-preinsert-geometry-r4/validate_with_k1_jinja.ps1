[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$config = Join-Path $PSScriptRoot 'k1-control-start-sequence-owner-preinsert-geometry-r4.cfg'
$validator = Join-Path $PSScriptRoot 'remote_jinja_validate.py'

$configText = [IO.File]::ReadAllText($config).Replace("`r`n", "`n")
$payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($configText))
$program = [IO.File]::ReadAllText($validator).Replace('__CONFIG_BASE64__', $payload).Replace("`r`n", "`n")

$output = $program | & ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ConnectTimeout=8' `
    k1max-root `
    '/usr/share/klippy-env/bin/python -B -' 2>&1

if ($LASTEXITCODE -ne 0) {
    throw "Parse Jinja R4 KO : $($output -join "`n")"
}
$joined = $output -join "`n"
if ($joined -notmatch '^REMOTE_R4_JINJA_PARSE_OK sections=20$') {
    throw "Marqueur Jinja R4 absent : $joined"
}

[pscustomobject]@{
    status = 'REMOTE_R4_JINJA_PARSE_OK'
    sections = 20
    remote_files_written = $false
    gcode_sent = $false
    heater_action = $false
    motion_action = $false
    extrusion_action = $false
    cfs_action = $false
    service_action = $false
} | ConvertTo-Json -Depth 4
