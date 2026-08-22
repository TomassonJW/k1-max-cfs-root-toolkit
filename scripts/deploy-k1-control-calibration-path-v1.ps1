[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',

    [string]$Gate,

    [ValidatePattern('^[0-9]{8}-[0-9]{6}-g4-k1-control-calibration-path-v1$')]
    [string]$CaptureId,

    [string]$EvidenceDirectory,

    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'PowerShell 7 ou plus recent est obligatoire.'
}

$RequiredGate = 'G4-K1-CONTROL-CALIBRATION-PATH-V1'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\calibration-path-v1'
$LocalConfig = Join-Path $PackageRoot 'k1-control-calibration-path.cfg'

$ExpectedPrinterHash = 'a484e8d802d0ba1a1331ea2060ecc339bd2d1a607e3a0f9bbcca976c66709c6a'
$ExpectedNextPrinterHash = '0d59dd656844c3198ee43a81056b06830dbe60779d558b71aaa8c28fa708d9ee'
$ExpectedConfigHash = '825aadac8679e0d0e9be140cc5ba4e7656b2bff0d197d1683a73d2b5be4e364e'
$ExpectedRuntimeConfigHash = 'dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113'
$ExpectedRuntimeModuleHash = '696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede'

$PrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$CalibrationConfig = '/usr/data/printer_data/config/k1-control-calibration-path.cfg'
$RuntimeConfig = '/usr/data/printer_data/config/k1-control-z-mesh.cfg'
$RuntimeModule = '/usr/share/klipper/klippy/extras/k1_control_store.py'
$RuntimeState = '/usr/data/k1-control-v1/state/k1-control-z-state.json'
$RemoteRoot = '/usr/data/k1-control-v1'
$KlipperSocket = '/tmp/klippy_uds'
$MutationStarted = $false

$SshArguments = @(
    '-o', 'BatchMode=yes',
    '-o', 'PasswordAuthentication=no',
    '-o', 'KbdInteractiveAuthentication=no',
    '-o', 'ConnectTimeout=8',
    'k1max-root'
)

function Assert-ExactGate {
    if (-not $Execute -or $Gate -cne $RequiredGate) {
        throw "Action bloquee : -Execute et -Gate '$RequiredGate' sont obligatoires."
    }
}

function Assert-LocalPathInsideWorkspace {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
    if (-not $resolved.StartsWith(
            $WorkspaceRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase
        )) {
        throw "Chemin local hors workspace : $resolved"
    }
    return $resolved
}

function Assert-ReviewedLocalFile {
    $hash = (Get-FileHash -LiteralPath $LocalConfig -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $ExpectedConfigHash) {
        throw "Configuration locale non revue : $hash"
    }
}

function Invoke-Remote {
    param([Parameter(Mandatory = $true)][string]$Command)

    $output = & ssh.exe @SshArguments $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Commande distante KO ($LASTEXITCODE) : $Command`n$($output -join "`n")"
    }
    return @($output)
}

function Invoke-RemoteStdin {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string]$StandardInput
    )

    $output = $StandardInput | & ssh.exe @SshArguments $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Commande distante avec stdin KO ($LASTEXITCODE) : $Command`n$($output -join "`n")"
    }
    return @($output)
}

function Invoke-RemoteTest {
    param([Parameter(Mandatory = $true)][string]$Command)

    & ssh.exe @SshArguments $Command *> $null
    return $LASTEXITCODE -eq 0
}

function Get-ExactRemoteLineCount {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Line
    )

    $program = '$0 == "' + $Line + '" {count++} END {print count+0}'
    return [int]((Invoke-Remote "awk '$program' '$Path'" | Select-Object -First 1).Trim())
}

function Save-Evidence {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Value
    )

    if (-not $EvidenceDirectory) { return }
    $resolved = Assert-LocalPathInsideWorkspace $EvidenceDirectory
    $path = Join-Path $resolved $Name
    if ($Value -is [string]) {
        $Value | Set-Content -LiteralPath $path -Encoding utf8
    }
    else {
        $Value | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $path -Encoding utf8
    }
}

function Get-KlipperSnapshot {
    param([switch]$IncludeCalibrationPath)

    $python = @'
from __future__ import print_function
import json
import socket
import sys

objects = {
    "print_stats": ["state", "filename"],
    "extruder": ["target", "temperature"],
    "heater_bed": ["target", "temperature"],
    "toolhead": ["homed_axes", "position"],
    "gcode_move": ["homing_origin"],
    "bed_mesh": ["profile_name"],
    "box": None,
    "gcode_macro KCTRL_STATE": None,
    "k1_control_store": None,
}
if sys.argv[1] == "1":
    objects["gcode_macro KCTRL_CAL_PATH_STATE"] = None
request = {"id": 5201, "method": "objects/query", "params": {"objects": objects}}
client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.settimeout(5)
client.connect("/tmp/klippy_uds")
client.sendall((json.dumps(request) + "\x03").encode("utf-8"))
data = b""
while b"\x03" not in data:
    chunk = client.recv(65536)
    if not chunk:
        raise RuntimeError("Klipper closed the socket")
    data += chunk
client.close()
message = json.loads(data.split(b"\x03", 1)[0].decode("utf-8"))
if message.get("error"):
    raise RuntimeError(message["error"])
print(json.dumps(message.get("result", {}).get("status", {}), sort_keys=True))
'@
    $payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($python.Replace("`r`n", "`n")))
    $include = if ($IncludeCalibrationPath) { '1' } else { '0' }
    $line = Invoke-Remote "echo '$payload' | base64 -d | /usr/share/klippy-env/bin/python - '$include'"
    return (($line -join "`n") | ConvertFrom-Json)
}

function Get-KlipperObjectNames {
    $python = @'
from __future__ import print_function
import json
import socket

request = {"id": 5202, "method": "objects/list", "params": {}}
client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.settimeout(5)
client.connect("/tmp/klippy_uds")
client.sendall((json.dumps(request) + "\x03").encode("utf-8"))
data = b""
while b"\x03" not in data:
    chunk = client.recv(65536)
    if not chunk:
        raise RuntimeError("Klipper closed the socket")
    data += chunk
client.close()
message = json.loads(data.split(b"\x03", 1)[0].decode("utf-8"))
if message.get("error"):
    raise RuntimeError(message["error"])
print(json.dumps(message.get("result", {}).get("objects", []), sort_keys=True))
'@
    $payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($python.Replace("`r`n", "`n")))
    $line = Invoke-Remote "echo '$payload' | base64 -d | /usr/share/klippy-env/bin/python"
    return @(($line -join "`n") | ConvertFrom-Json)
}

function Invoke-KlipperScript {
    param(
        [Parameter(Mandatory = $true)][string]$Script,
        [switch]$NoResponse
    )

    if ($Script -notin @('RESTART', 'KCTRL_CAL_PATH_ASSERT_ARMED')) {
        throw "Script Klipper hors liste revue : $Script"
    }
    $python = @'
from __future__ import print_function
import json
import socket
import sys
import time

script = sys.argv[1]
wait_response = sys.argv[2] == "1"
request = {"id": 5203, "method": "gcode/script", "params": {"script": script}}
client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.settimeout(5)
client.connect("/tmp/klippy_uds")
client.sendall((json.dumps(request) + "\x03").encode("utf-8"))
if not wait_response:
    time.sleep(0.2)
    client.close()
    print(json.dumps({"sent": script}))
    raise SystemExit(0)
data = b""
while b"\x03" not in data:
    chunk = client.recv(65536)
    if not chunk:
        break
    data += chunk
client.close()
if not data:
    print(json.dumps({"closed_without_response": True}))
else:
    print(json.dumps(json.loads(data.split(b"\x03", 1)[0].decode("utf-8")), sort_keys=True))
'@
    $payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($python.Replace("`r`n", "`n")))
    $wait = if ($NoResponse) { '0' } else { '1' }
    $line = Invoke-Remote "echo '$payload' | base64 -d | /usr/share/klippy-env/bin/python - '$Script' '$wait'"
    return (($line -join "`n") | ConvertFrom-Json)
}

function Wait-KlipperReady {
    param(
        [int]$Attempts = 30,
        [switch]$IncludeCalibrationPath
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $snapshot = Get-KlipperSnapshot -IncludeCalibrationPath:$IncludeCalibrationPath
            if ($snapshot.print_stats) { return $snapshot }
        }
        catch {
            if ($attempt -eq $Attempts) { throw }
        }
        if ($attempt -lt $Attempts) { Start-Sleep -Seconds 1 }
    }
    throw 'Klipper ne repond pas apres le redemarrage.'
}

function Assert-IdleSnapshot {
    param(
        [Parameter(Mandatory = $true)]$Snapshot,
        [switch]$RequireUnhomed
    )

    if ($Snapshot.print_stats.state -ne 'standby' -or $Snapshot.print_stats.filename) {
        throw "Imprimante non disponible : $($Snapshot.print_stats.state)"
    }
    if ([double]$Snapshot.extruder.target -ne 0 -or [double]$Snapshot.heater_bed.target -ne 0) {
        throw 'Une chauffe est demandee.'
    }
    if ($RequireUnhomed -and $Snapshot.toolhead.homed_axes) {
        throw "Axes encore homes : $($Snapshot.toolhead.homed_axes)"
    }
    foreach ($name in @('T1', 'T2')) {
        $unit = $Snapshot.box.$name
        if ($unit.state -ne 'connect' -or $unit.version -ne '1.1.3' -or @($unit.material_type).Count -ne 4) {
            throw "CFS $name inattendu ou deconnecte."
        }
    }
}

function Wait-IdleSnapshot {
    param(
        [int]$Attempts = 60,
        [switch]$IncludeCalibrationPath,
        [switch]$RequireUnhomed
    )

    $lastError = 'etat non encore observe'
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $snapshot = Get-KlipperSnapshot -IncludeCalibrationPath:$IncludeCalibrationPath
            Assert-IdleSnapshot $snapshot -RequireUnhomed:$RequireUnhomed
            return $snapshot
        }
        catch {
            $lastError = $_.Exception.Message
        }
        if ($attempt -lt $Attempts) { Start-Sleep -Seconds 1 }
    }
    throw "Etat imprimante/CFS non stabilise apres $Attempts tentatives : $lastError"
}

function Assert-Foundation {
    $listeners = (Invoke-Remote 'netstat -lnt') -join "`n"
    foreach ($required in @('127.0.0.1:7125', '0.0.0.0:4409', '0.0.0.0:80', '0.0.0.0:8080', '0.0.0.0:9999')) {
        if ($listeners -notmatch [regex]::Escape($required)) {
            throw "Ecoute absente : $required"
        }
    }
    if ($listeners -match '0.0.0.0:7125') {
        throw 'Moonraker est expose directement au LAN.'
    }
    foreach ($process in @('[k]lippy/klippy.py', '[k]lipper_mcu', '[m]aster-server', '[a]pp-server', '[d]isplay-server', '[w]eb-server', '[M]onitor')) {
        if (-not (Invoke-RemoteTest "ps w | grep -q '$process'")) {
            throw "Processus Creality absent : $process"
        }
    }
    return $listeners
}

function Assert-ExactRemoteJinjaSyntax {
    $python = @'
from __future__ import print_function
import base64
import re
import jinja2

text = base64.b64decode("__CONFIG_PAYLOAD__").decode("utf-8")
environment = jinja2.Environment(
    block_start_string="{%",
    block_end_string="%}",
    variable_start_string="{",
    variable_end_string="}",
)
bodies = re.findall(r"^gcode:\n((?:^  .*\n?)*)", text, flags=re.MULTILINE)
if len(bodies) < 10:
    raise RuntimeError("calibration path macro count is incomplete")
for body in bodies:
    environment.parse(body)
print("REMOTE_JINJA_PARSE_OK macros=%d" % len(bodies))
'@
    $configText = [IO.File]::ReadAllText($LocalConfig).Replace("`r`n", "`n")
    $configPayload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($configText))
    $program = $python.Replace('__CONFIG_PAYLOAD__', $configPayload).Replace("`r`n", "`n")
    $output = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -' $program
    if (($output -join "`n") -notmatch '^REMOTE_JINJA_PARSE_OK macros=') {
        throw 'Validation Jinja exacte distante absente.'
    }
    Save-Evidence 'preflight-jinja.txt' ($output -join "`n")
}

function Assert-RuntimeBaseline {
    param([Parameter(Mandatory = $true)]$Snapshot)

    $runtime = $Snapshot.'gcode_macro KCTRL_STATE'
    $store = $Snapshot.k1_control_store
    if (-not $runtime -or [int]$runtime.ready -ne 1 -or [int]$runtime.accepted_z_valid -ne 0 -or [int]$runtime.low_moves_armed -ne 0) {
        throw 'Runtime Z/mesh non pret ou production deja armee.'
    }
    if (-not $store -or $store.integrity -ne 'empty' -or [int]$store.recovery_available -ne 0) {
        throw 'Etat atomique Z/mesh different de la base vide revue.'
    }
}

function Invoke-CalibrationPathPreflight {
    Assert-ReviewedLocalFile
    $architecture = (Invoke-Remote 'uname -m' | Select-Object -First 1).Trim()
    $board = (Invoke-Remote '/usr/bin/get_sn_mac.sh board' | Select-Object -First 1).Trim()
    $structure = (Invoke-Remote '/usr/bin/get_sn_mac.sh structure_version' | Select-Object -First 1).Trim()
    $version = (Invoke-Remote "grep '^ota_version=' /etc/ota_info" | Select-Object -First 1).Trim()
    if ($architecture -ne 'mips' -or $board -ne 'CR4CU220812S12' -or $structure -ne '0' -or $version -ne 'ota_version=2.3.5.34') {
        throw 'Identite machine ou firmware inattendue.'
    }
    Assert-ExactRemoteJinjaSyntax
    foreach ($tool in @('awk', 'base64', 'chmod', 'cp', 'cut', 'grep', 'mkdir', 'mv', 'netstat', 'ps', 'rm', 'sha256sum', 'sync')) {
        if (-not (Invoke-RemoteTest "command -v '$tool'")) { throw "Outil distant absent : $tool" }
    }
    foreach ($path in @('/usr/data/printer_data/config', "$RemoteRoot/state")) {
        if (-not (Invoke-RemoteTest "test -d '$path'")) { throw "Dossier distant absent : $path" }
    }
    if (-not (Invoke-RemoteTest "test -S '$KlipperSocket'")) { throw 'Socket Klipper absent.' }
    foreach ($path in @($CalibrationConfig, "$CalibrationConfig.next", "$PrinterConfig.next", "$PrinterConfig.rollback-next", "$PrinterConfig.rollback-final")) {
        if (Invoke-RemoteTest "test -e '$path'") { throw "Cible ou transitoire deja present : $path" }
    }
    $printerHash = ((Invoke-Remote "sha256sum '$PrinterConfig'" | Select-Object -First 1) -split '\s+')[0]
    $runtimeConfigHash = ((Invoke-Remote "sha256sum '$RuntimeConfig'" | Select-Object -First 1) -split '\s+')[0]
    $runtimeModuleHash = ((Invoke-Remote "sha256sum '$RuntimeModule'" | Select-Object -First 1) -split '\s+')[0]
    if ($printerHash -ne $ExpectedPrinterHash -or $runtimeConfigHash -ne $ExpectedRuntimeConfigHash -or $runtimeModuleHash -ne $ExpectedRuntimeModuleHash) {
        throw 'Base printer.cfg ou runtime differente de la version revue.'
    }
    $runtimeIncludeCount = Get-ExactRemoteLineCount -Path $PrinterConfig -Line '[include k1-control-z-mesh.cfg]'
    $pathIncludeCount = Get-ExactRemoteLineCount -Path $PrinterConfig -Line '[include k1-control-calibration-path.cfg]'
    if ($runtimeIncludeCount -ne 1 -or $pathIncludeCount -ne 0) { throw 'Inclusions K1 Control inattendues avant pose.' }
    $objects = Get-KlipperObjectNames
    if ($objects -notcontains 'gcode_macro KCTRL_STATE' -or $objects -notcontains 'k1_control_store') {
        throw 'Runtime Z/mesh existant non charge.'
    }
    if ($objects -contains 'gcode_macro KCTRL_CAL_PATH_STATE') { throw 'Chemin de calibration deja charge.' }
    $snapshot = Get-KlipperSnapshot
    Assert-IdleSnapshot $snapshot
    Assert-RuntimeBaseline $snapshot
    $listeners = Assert-Foundation
    Save-Evidence 'preflight-klipper.json' $snapshot
    Save-Evidence 'preflight-listeners.txt' $listeners
    Save-Evidence 'preflight-hashes.txt' "printer_cfg=$printerHash`nruntime_config=$runtimeConfigHash`nruntime_module=$runtimeModuleHash`ncalibration_path=$ExpectedConfigHash"
    return $snapshot
}

function Assert-NoPhysicalChange {
    param(
        [Parameter(Mandatory = $true)]$Before,
        [Parameter(Mandatory = $true)]$After
    )

    foreach ($path in @('extruder.target', 'heater_bed.target', 'toolhead.position', 'gcode_move.homing_origin')) {
        $segments = $path.Split('.')
        $left = $Before
        $right = $After
        foreach ($segment in $segments) {
            $left = $left.$segment
            $right = $right.$segment
        }
        if (($left | ConvertTo-Json -Compress) -ne ($right | ConvertTo-Json -Compress)) {
            throw "Etat physique change pendant la garde : $path"
        }
    }
}

function Assert-CalibrationPathInstalled {
    $printerHash = ((Invoke-Remote "sha256sum '$PrinterConfig'" | Select-Object -First 1) -split '\s+')[0]
    $configHash = ((Invoke-Remote "sha256sum '$CalibrationConfig'" | Select-Object -First 1) -split '\s+')[0]
    $runtimeConfigHash = ((Invoke-Remote "sha256sum '$RuntimeConfig'" | Select-Object -First 1) -split '\s+')[0]
    $runtimeModuleHash = ((Invoke-Remote "sha256sum '$RuntimeModule'" | Select-Object -First 1) -split '\s+')[0]
    if ($printerHash -ne $ExpectedNextPrinterHash -or $configHash -ne $ExpectedConfigHash -or $runtimeConfigHash -ne $ExpectedRuntimeConfigHash -or $runtimeModuleHash -ne $ExpectedRuntimeModuleHash) {
        throw 'Empreinte du chemin de calibration installe inattendue.'
    }
    $runtimeIncludeCount = Get-ExactRemoteLineCount -Path $PrinterConfig -Line '[include k1-control-z-mesh.cfg]'
    $pathIncludeCount = Get-ExactRemoteLineCount -Path $PrinterConfig -Line '[include k1-control-calibration-path.cfg]'
    if ($runtimeIncludeCount -ne 1 -or $pathIncludeCount -ne 1) { throw 'Nombre d inclusions K1 Control inattendu apres pose.' }
    $objects = Get-KlipperObjectNames
    if ($objects -notcontains 'gcode_macro KCTRL_CAL_PATH_STATE') { throw 'Chemin de calibration non charge.' }
    $snapshot = Wait-IdleSnapshot -IncludeCalibrationPath -RequireUnhomed -Attempts 60
    Assert-RuntimeBaseline $snapshot
    $path = $snapshot.'gcode_macro KCTRL_CAL_PATH_STATE'
    if (-not $path -or [int]$path.ready -ne 0 -or $path.phase -ne 'idle' -or [int]$path.mesh_ready -ne 0 -or
        [int]$path.plate_id -ne 0 -or [int]$path.temperature_band_c -ne 0 -or [int]$path.probe_revision -ne 0 -or
        [int]$path.x_count -ne 0 -or [int]$path.y_count -ne 0 -or [int]$path.motion_armed -ne 0 -or
        [int]$path.commit_ready -ne 0) {
        throw 'Chemin de calibration non ferme apres chargement.'
    }
    $listeners = Assert-Foundation
    $before = Get-KlipperSnapshot -IncludeCalibrationPath
    $response = Invoke-KlipperScript 'KCTRL_CAL_PATH_ASSERT_ARMED'
    if (-not $response.error) { throw 'La garde du chemin de calibration n a pas refuse le contexte vide.' }
    $after = Get-KlipperSnapshot -IncludeCalibrationPath
    Assert-NoPhysicalChange -Before $before -After $after
    Save-Evidence 'validation-klipper.json' $snapshot
    Save-Evidence 'validation-listeners.txt' $listeners
    Save-Evidence 'validation-fail-closed-response.json' $response
    Save-Evidence 'validation-no-motion-before.json' $before
    Save-Evidence 'validation-no-motion-after.json' $after
    Save-Evidence 'validation-hashes.txt' "printer_cfg=$printerHash`nruntime_config=$runtimeConfigHash`nruntime_module=$runtimeModuleHash`ncalibration_path=$configHash"
    return $snapshot
}

function Invoke-CalibrationPathRollback {
    param([switch]$BestEffort)

    if (-not $CaptureId) { throw 'Rollback exige -CaptureId.' }
    $remoteBackup = "$RemoteRoot/backups/$CaptureId/calibration-path-v1"
    foreach ($command in @(
            "test -f '$remoteBackup/printer.cfg.before'",
            "test -f '$remoteBackup/checksums.sha256'",
            "cd '$remoteBackup' && sha256sum -c checksums.sha256",
            "cp '$remoteBackup/printer.cfg.before' '$PrinterConfig.rollback-next'",
            "test `"`$(sha256sum '$PrinterConfig.rollback-next' | cut -d ' ' -f 1)`" = '$ExpectedPrinterHash'",
            "mv '$PrinterConfig.rollback-next' '$PrinterConfig'",
            "rm -f '$CalibrationConfig' '$CalibrationConfig.next' '$PrinterConfig.next' '$PrinterConfig.rollback-final'",
            'sync'
        )) {
        try { Invoke-Remote $command | Out-Null }
        catch { if (-not $BestEffort) { throw } }
    }
    try {
        Invoke-KlipperScript 'RESTART' -NoResponse | Out-Null
        $unloaded = $false
        for ($attempt = 1; $attempt -le 60; $attempt++) {
            $snapshot = Wait-KlipperReady
            $objects = Get-KlipperObjectNames
            if ($objects -notcontains 'gcode_macro KCTRL_CAL_PATH_STATE') {
                $unloaded = $true
                break
            }
            if ($attempt -lt 60) { Start-Sleep -Seconds 1 }
        }
        if (-not $unloaded) { throw 'Rollback charge encore le chemin de calibration.' }
        $snapshot = Wait-IdleSnapshot -RequireUnhomed -Attempts 60
        Assert-RuntimeBaseline $snapshot
        Assert-Foundation | Out-Null
        Start-Sleep -Seconds 5
        $snapshot = Wait-IdleSnapshot -RequireUnhomed -Attempts 10
        Assert-RuntimeBaseline $snapshot

        Invoke-Remote "cp '$remoteBackup/printer.cfg.before' '$PrinterConfig.rollback-final'" | Out-Null
        $finalHash = ((Invoke-Remote "sha256sum '$PrinterConfig.rollback-final'" | Select-Object -First 1) -split '\s+')[0]
        if ($finalHash -ne $ExpectedPrinterHash) { throw 'Copie finale du backup rollback differente.' }
        Invoke-Remote "mv '$PrinterConfig.rollback-final' '$PrinterConfig'" | Out-Null
        Invoke-Remote 'sync' | Out-Null
        Start-Sleep -Seconds 3
        $restoredHash = ((Invoke-Remote "sha256sum '$PrinterConfig'" | Select-Object -First 1) -split '\s+')[0]
        if ($restoredHash -ne $ExpectedPrinterHash) { throw 'Rollback printer.cfg incomplet.' }
        foreach ($path in @($CalibrationConfig, "$CalibrationConfig.next", "$PrinterConfig.next", "$PrinterConfig.rollback-next", "$PrinterConfig.rollback-final")) {
            if (Invoke-RemoteTest "test -e '$path'") { throw "Rollback incomplet : $path" }
        }
    }
    catch { if (-not $BestEffort) { throw } }
}

if ($Action -eq 'Plan') {
    Assert-ReviewedLocalFile
    [pscustomobject]@{
        status = 'PLAN_ONLY'
        gate = $RequiredGate
        printer_mutation_authorized = $false
        current_printer_sha256 = $ExpectedPrinterHash
        next_printer_sha256 = $ExpectedNextPrinterHash
        calibration_path_sha256 = $ExpectedConfigHash
        existing_runtime_config_sha256 = $ExpectedRuntimeConfigHash
        existing_runtime_module_sha256 = $ExpectedRuntimeModuleHash
        remote_file_added = $CalibrationConfig
        printer_cfg_change = '[include k1-control-calibration-path.cfg] after [include k1-control-z-mesh.cfg]'
        restart = 'Klipper host RESTART only'
        deployment_movement = $false
        deployment_heating = $false
        validation = 'idle fail-closed path plus no physical state change'
        rollback = 'restore exact printer.cfg, remove one file, restart Klipper, wait CFS and quiet window, restore exact backup again'
        calibration_started = $false
    } | ConvertTo-Json -Depth 5
    exit 0
}

Assert-ExactGate
if ($EvidenceDirectory) { [void](Assert-LocalPathInsideWorkspace $EvidenceDirectory) }

if ($Action -eq 'Preflight') {
    Invoke-CalibrationPathPreflight | ConvertTo-Json -Depth 8
    Write-Output 'PREFLIGHT_CALIBRATION_PATH_V1_OK'
    exit 0
}

if ($Action -eq 'Deploy') {
    if (-not $CaptureId -or -not $EvidenceDirectory) { throw 'Deploy exige -CaptureId et -EvidenceDirectory.' }
    Invoke-CalibrationPathPreflight | Out-Null
    $remoteBackup = "$RemoteRoot/backups/$CaptureId/calibration-path-v1"
    $remoteStaging = "$RemoteRoot/staging/$CaptureId/calibration-path-v1"
    try {
        Invoke-Remote "test ! -e '$remoteBackup' && mkdir -p '$remoteBackup' '$remoteStaging'" | Out-Null
        & scp.exe -O -q -o BatchMode=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no `
            $LocalConfig "k1max-root`:$remoteStaging/k1-control-calibration-path.cfg"
        if ($LASTEXITCODE -ne 0) { throw 'Transfert de la configuration calibration-path KO.' }
        Invoke-Remote "test `"`$(sha256sum '$remoteStaging/k1-control-calibration-path.cfg' | cut -d ' ' -f 1)`" = '$ExpectedConfigHash'" | Out-Null

        Invoke-Remote "cp '$PrinterConfig' '$remoteBackup/printer.cfg.before'" | Out-Null
        $backupHash = ((Invoke-Remote "sha256sum '$remoteBackup/printer.cfg.before'" | Select-Object -First 1) -split '\s+')[0]
        if ($backupHash -ne $ExpectedPrinterHash) { throw 'Backup printer.cfg different.' }
        $checksumText = "$backupHash  printer.cfg.before"
        $checksumPayload = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$checksumText`n"))
        Invoke-Remote "echo '$checksumPayload' | base64 -d > '$remoteBackup/checksums.sha256'" | Out-Null
        Invoke-Remote "cd '$remoteBackup' && sha256sum -c checksums.sha256" | Out-Null
        Save-Evidence 'remote-backup-sha256.txt' $checksumText

        $awkProgram = '{print; if ($0 == "[include k1-control-z-mesh.cfg]") {print "[include k1-control-calibration-path.cfg]"; count++}} END {if (count != 1) exit 42}'
        Invoke-Remote "awk '$awkProgram' '$PrinterConfig' > '$remoteStaging/printer.cfg.next'" | Out-Null
        Invoke-Remote "test `"`$(sha256sum '$remoteStaging/printer.cfg.next' | cut -d ' ' -f 1)`" = '$ExpectedNextPrinterHash'" | Out-Null

        $MutationStarted = $true
        Invoke-Remote "cp '$remoteStaging/k1-control-calibration-path.cfg' '$CalibrationConfig.next' && chmod 600 '$CalibrationConfig.next' && mv '$CalibrationConfig.next' '$CalibrationConfig'" | Out-Null
        Invoke-Remote "cp '$remoteStaging/printer.cfg.next' '$PrinterConfig.next' && test `"`$(sha256sum '$PrinterConfig.next' | cut -d ' ' -f 1)`" = '$ExpectedNextPrinterHash' && mv '$PrinterConfig.next' '$PrinterConfig' && sync" | Out-Null
        Invoke-KlipperScript 'RESTART' -NoResponse | Out-Null
        Assert-CalibrationPathInstalled | Out-Null
        Write-Output "DEPLOY_CALIBRATION_PATH_V1_OK capture=$CaptureId"
    }
    catch {
        $deploymentError = $_
        if ($MutationStarted) {
            try { Invoke-CalibrationPathRollback }
            catch { throw "Deploiement KO et rollback KO. Initial : $deploymentError`nRollback : $_" }
        }
        throw $deploymentError
    }
    exit 0
}

if ($Action -eq 'Validate') {
    Assert-ReviewedLocalFile
    Assert-CalibrationPathInstalled | Out-Null
    Write-Output 'VALIDATE_CALIBRATION_PATH_V1_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Invoke-CalibrationPathRollback
    Write-Output "ROLLBACK_CALIBRATION_PATH_V1_OK capture=$CaptureId"
    exit 0
}
