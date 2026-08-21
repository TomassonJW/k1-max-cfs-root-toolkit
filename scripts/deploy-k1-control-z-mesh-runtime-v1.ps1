[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',

    [string]$Gate,

    [ValidatePattern('^[0-9]{8}-[0-9]{6}-g4-k1-control-z-mesh-runtime-v1$')]
    [string]$CaptureId,

    [string]$EvidenceDirectory,

    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'PowerShell 7 ou plus recent est obligatoire.'
}

$RequiredGate = 'G4-K1-CONTROL-Z-MESH-RUNTIME-V1'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\z-mesh-runtime-v1'
$LocalConfig = Join-Path $PackageRoot 'k1-control-z-mesh.cfg'
$LocalModule = Join-Path $PackageRoot 'k1_control_store.py'

$ExpectedPrinterHash = '272640237e20659cf01f3268ed4cb0282b098c3d613e94bf84a3b80caac3c3b0'
$ExpectedNextPrinterHash = 'fa8c25b0bc79f94bcdf1c1bca2c48c3d892ca42854cf277962580680d5767f05'
$ExpectedConfigHash = '1f202e94aaf3a28363a6a66727e27bf1a461b82436ccad0d8e00bb9b9e988fd9'
$ExpectedModuleHash = '385fc888b5fae7633de91a3c106b8e46656bd79936d40b4555e2a7da6dee9b93'

$PrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$RuntimeConfig = '/usr/data/printer_data/config/k1-control-z-mesh.cfg'
$RuntimeModule = '/usr/share/klipper/klippy/extras/k1_control_store.py'
$RuntimeState = '/usr/data/k1-control-v1/state/k1-control-z-state.json'
$RemoteRoot = '/usr/data/k1-control-v1'
$KlipperService = '/etc/init.d/S55klipper_service'
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

function Assert-ReviewedLocalFiles {
    $configHash = (Get-FileHash -LiteralPath $LocalConfig -Algorithm SHA256).Hash.ToLowerInvariant()
    $moduleHash = (Get-FileHash -LiteralPath $LocalModule -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($configHash -ne $ExpectedConfigHash) {
        throw "Configuration locale non revue : $configHash"
    }
    if ($moduleHash -ne $ExpectedModuleHash) {
        throw "Module local non revu : $moduleHash"
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

function Invoke-RemoteTest {
    param([Parameter(Mandatory = $true)][string]$Command)

    & ssh.exe @SshArguments $Command *> $null
    return $LASTEXITCODE -eq 0
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
    param([switch]$IncludeRuntime)

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
}
if sys.argv[1] == "1":
    objects["gcode_macro K1_CONTROL_STATE"] = None
    objects["k1_control_store"] = None
request = {
    "id": 5101,
    "method": "objects/query",
    "params": {"objects": objects},
}
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
    $include = if ($IncludeRuntime) { '1' } else { '0' }
    $line = Invoke-Remote "echo '$payload' | base64 -d | /usr/share/klippy-env/bin/python - '$include'"
    return (($line -join "`n") | ConvertFrom-Json)
}

function Invoke-KlipperScript {
    param(
        [Parameter(Mandatory = $true)][string]$Script,
        [switch]$NoResponse
    )

    if ($Script -notin @('RESTART', 'K1_PRODUCTION_ASSERT_ARMED')) {
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
request = {"id": 5102, "method": "gcode/script", "params": {"script": script}}
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

function Get-KlipperObjectNames {
    $python = @'
from __future__ import print_function
import json
import socket

request = {"id": 5103, "method": "objects/list", "params": {}}
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
    $objects = ($line -join "`n") | ConvertFrom-Json
    return @($objects)
}

function Wait-KlipperReady {
    param(
        [int]$Attempts = 20,
        [int]$DelaySeconds = 1,
        [switch]$IncludeRuntime
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $snapshot = Get-KlipperSnapshot -IncludeRuntime:$IncludeRuntime
            if ($snapshot.print_stats) { return $snapshot }
        }
        catch {
            if ($attempt -eq $Attempts) { throw }
        }
        if ($attempt -lt $Attempts) { Start-Sleep -Seconds $DelaySeconds }
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

function Invoke-RuntimePreflight {
    Assert-ReviewedLocalFiles
    $architecture = (Invoke-Remote 'uname -m' | Select-Object -First 1).Trim()
    $board = (Invoke-Remote '/usr/bin/get_sn_mac.sh board' | Select-Object -First 1).Trim()
    $structure = (Invoke-Remote '/usr/bin/get_sn_mac.sh structure_version' | Select-Object -First 1).Trim()
    $version = (Invoke-Remote "grep '^ota_version=' /etc/ota_info" | Select-Object -First 1).Trim()
    if ($architecture -ne 'mips' -or $board -ne 'CR4CU220812S12' -or $structure -ne '0' -or $version -ne 'ota_version=2.3.5.34') {
        throw 'Identite machine ou firmware inattendue.'
    }
    foreach ($tool in @('awk', 'base64', 'chmod', 'cmp', 'cp', 'cut', 'find', 'grep', 'mkdir', 'mv', 'netstat', 'ps', 'rm', 'sha256sum', 'sync')) {
        if (-not (Invoke-RemoteTest "command -v '$tool'")) { throw "Outil distant absent : $tool" }
    }
    foreach ($path in @('/usr/data/printer_data/config', '/usr/share/klipper/klippy/extras', "$RemoteRoot/state")) {
        if (-not (Invoke-RemoteTest "test -d '$path'")) { throw "Dossier distant absent : $path" }
    }
    if (-not (Invoke-RemoteTest "test -x '$KlipperService' && test -S '$KlipperSocket'")) {
        throw 'Service ou socket Klipper absent.'
    }
    foreach ($path in @(
            $RuntimeConfig,
            "$RuntimeConfig.next",
            $RuntimeModule,
            "$RuntimeModule.next",
            $RuntimeState,
            "$RuntimeState.previous",
            "$RuntimeState.tmp",
            "$PrinterConfig.next",
            "$PrinterConfig.rollback-next"
        )) {
        if (Invoke-RemoteTest "test -e '$path'") { throw "Cible deja presente : $path" }
    }
    if (Invoke-RemoteTest "grep -q '^\[include k1-control-z-mesh.cfg\]$' '$PrinterConfig'") {
        throw 'Inclusion runtime deja presente.'
    }
    $printerHash = ((Invoke-Remote "sha256sum '$PrinterConfig'" | Select-Object -First 1) -split '\s+')[0]
    if ($printerHash -ne $ExpectedPrinterHash) {
        throw "printer.cfg distant non revu : $printerHash"
    }
    $snapshot = Get-KlipperSnapshot
    $objects = Get-KlipperObjectNames
    if ($objects -contains 'gcode_macro K1_CONTROL_STATE' -or $objects -contains 'k1_control_store') {
        throw 'Runtime K1 Control deja charge avant la pose.'
    }
    Assert-IdleSnapshot $snapshot
    $listeners = Assert-Foundation
    Save-Evidence 'preflight-klipper.json' $snapshot
    Save-Evidence 'preflight-listeners.txt' $listeners
    Save-Evidence 'preflight-hashes.txt' "printer_cfg=$printerHash`nruntime_config=$ExpectedConfigHash`nruntime_module=$ExpectedModuleHash"
    return $snapshot
}

function Assert-RuntimeInstalled {
    $printerHash = ((Invoke-Remote "sha256sum '$PrinterConfig'" | Select-Object -First 1) -split '\s+')[0]
    $configHash = ((Invoke-Remote "sha256sum '$RuntimeConfig'" | Select-Object -First 1) -split '\s+')[0]
    $moduleHash = ((Invoke-Remote "sha256sum '$RuntimeModule'" | Select-Object -First 1) -split '\s+')[0]
    if ($printerHash -ne $ExpectedNextPrinterHash -or $configHash -ne $ExpectedConfigHash -or $moduleHash -ne $ExpectedModuleHash) {
        throw 'Empreinte runtime installee inattendue.'
    }
    $includeCount = [int]((Invoke-Remote "grep -c '^\[include k1-control-z-mesh.cfg\]$' '$PrinterConfig'" | Select-Object -First 1).Trim())
    if ($includeCount -ne 1) { throw "Nombre d inclusions runtime inattendu : $includeCount" }
    $snapshot = $null
    for ($attempt = 1; $attempt -le 12; $attempt++) {
        $snapshot = Wait-KlipperReady -IncludeRuntime
        $runtime = $snapshot.'gcode_macro K1_CONTROL_STATE'
        if ($runtime -and [int]$runtime.ready -eq 1) { break }
        if ($attempt -lt 12) { Start-Sleep -Seconds 1 }
    }
    Assert-IdleSnapshot $snapshot -RequireUnhomed
    $runtime = $snapshot.'gcode_macro K1_CONTROL_STATE'
    $store = $snapshot.k1_control_store
    if (-not $runtime -or [int]$runtime.ready -ne 1 -or [int]$runtime.accepted_z_valid -ne 0 -or [int]$runtime.low_moves_armed -ne 0) {
        throw 'Etat initial K1 Control non ferme.'
    }
    if (-not $store -or $store.integrity -ne 'empty' -or [int]$store.recovery_available -ne 0) {
        throw 'Etat atomique initial inattendu.'
    }
    $listeners = Assert-Foundation
    Save-Evidence 'validation-klipper.json' $snapshot
    Save-Evidence 'validation-listeners.txt' $listeners
    Save-Evidence 'validation-hashes.txt' "printer_cfg=$printerHash`nruntime_config=$configHash`nruntime_module=$moduleHash"
    return $snapshot
}

function Assert-FailClosedWithoutMotion {
    $before = Get-KlipperSnapshot -IncludeRuntime
    $response = Invoke-KlipperScript 'K1_PRODUCTION_ASSERT_ARMED'
    if (-not $response.error) {
        throw 'La garde de production n a pas refuse le contexte vide.'
    }
    $after = Get-KlipperSnapshot -IncludeRuntime
    foreach ($path in @('extruder.target', 'heater_bed.target', 'toolhead.position', 'gcode_move.homing_origin')) {
        $segments = $path.Split('.')
        $left = $before
        $right = $after
        foreach ($segment in $segments) {
            $left = $left.$segment
            $right = $right.$segment
        }
        if (($left | ConvertTo-Json -Compress) -ne ($right | ConvertTo-Json -Compress)) {
            throw "Etat physique change pendant la garde : $path"
        }
    }
    Save-Evidence 'validation-fail-closed-response.json' $response
    Save-Evidence 'validation-no-motion-before.json' $before
    Save-Evidence 'validation-no-motion-after.json' $after
}

function Invoke-RuntimeRollback {
    param([switch]$BestEffort)

    if (-not $CaptureId) { throw 'Rollback exige -CaptureId.' }
    $remoteBackup = "$RemoteRoot/backups/$CaptureId/z-mesh-runtime-v1"
    $commands = @(
        "test -f '$remoteBackup/printer.cfg.before'",
        "test -f '$remoteBackup/checksums.sha256'",
        "cd '$remoteBackup' && sha256sum -c checksums.sha256",
        "mkdir -p '$remoteBackup/state-at-rollback'",
        "for f in '$RuntimeState' '$RuntimeState.previous' '$RuntimeState.tmp'; do test ! -e `"`$f`" || cp -p `"`$f`" '$remoteBackup/state-at-rollback/'; done",
        "find '$remoteBackup/state-at-rollback' -maxdepth 1 -type f -exec sha256sum {} \; > '$remoteBackup/state-at-rollback.sha256'",
        "cp '$remoteBackup/printer.cfg.before' '$PrinterConfig.rollback-next'",
        "test `"`$(sha256sum '$PrinterConfig.rollback-next' | cut -d ' ' -f 1)`" = '$ExpectedPrinterHash'",
        "mv '$PrinterConfig.rollback-next' '$PrinterConfig'",
        "rm -f '$RuntimeConfig' '$RuntimeConfig.next' '$RuntimeModule' '$RuntimeModule.next' '$RuntimeState' '$RuntimeState.previous' '$RuntimeState.tmp' '$PrinterConfig.next' '$PrinterConfig.rollback-next'",
        'sync'
    )
    foreach ($command in $commands) {
        try { Invoke-Remote $command | Out-Null }
        catch { if (-not $BestEffort) { throw } }
    }
    try {
        if (Invoke-RemoteTest "test -S '$KlipperSocket'") {
            Invoke-KlipperScript 'RESTART' -NoResponse | Out-Null
        }
        else {
            Invoke-Remote "'$KlipperService' restart" | Out-Null
        }
        $snapshot = $null
        for ($attempt = 1; $attempt -le 20; $attempt++) {
            $snapshot = Wait-KlipperReady
            $objects = Get-KlipperObjectNames
            if ($objects -notcontains 'gcode_macro K1_CONTROL_STATE' -and $objects -notcontains 'k1_control_store') { break }
            if ($attempt -lt 20) { Start-Sleep -Seconds 1 }
        }
        if ($objects -contains 'gcode_macro K1_CONTROL_STATE' -or $objects -contains 'k1_control_store') {
            throw 'Rollback charge encore le runtime K1 Control.'
        }
        Assert-IdleSnapshot $snapshot -RequireUnhomed
        $restoredHash = ((Invoke-Remote "sha256sum '$PrinterConfig'" | Select-Object -First 1) -split '\s+')[0]
        if ($restoredHash -ne $ExpectedPrinterHash) { throw 'Rollback printer.cfg incomplet.' }
        foreach ($path in @($RuntimeConfig, "$RuntimeConfig.next", $RuntimeModule, "$RuntimeModule.next", $RuntimeState, "$RuntimeState.previous", "$RuntimeState.tmp")) {
            if (Invoke-RemoteTest "test -e '$path'") { throw "Rollback incomplet : $path" }
        }
        Assert-Foundation | Out-Null
    }
    catch { if (-not $BestEffort) { throw } }
}

if ($Action -eq 'Plan') {
    Assert-ReviewedLocalFiles
    [pscustomobject]@{
        status = 'PLAN_ONLY'
        gate = $RequiredGate
        printer_mutation_authorized = $false
        current_printer_sha256 = $ExpectedPrinterHash
        next_printer_sha256 = $ExpectedNextPrinterHash
        config_sha256 = $ExpectedConfigHash
        module_sha256 = $ExpectedModuleHash
        remote_files_added = @($RuntimeConfig, $RuntimeModule)
        printer_cfg_change = '[include k1-control-z-mesh.cfg] after [include box.cfg]'
        restart = 'Klipper host RESTART only'
        validation = 'empty atomic state plus fail-closed no-motion guard'
        rollback = 'restore printer.cfg, archive state, remove two files, restart Klipper'
        orca_profile_changed = $false
    } | ConvertTo-Json -Depth 5
    exit 0
}

Assert-ExactGate
if ($EvidenceDirectory) { [void](Assert-LocalPathInsideWorkspace $EvidenceDirectory) }

if ($Action -eq 'Preflight') {
    Invoke-RuntimePreflight | ConvertTo-Json -Depth 8
    Write-Output 'PREFLIGHT_Z_MESH_RUNTIME_V1_OK'
    exit 0
}

if ($Action -eq 'Deploy') {
    if (-not $CaptureId -or -not $EvidenceDirectory) {
        throw 'Deploy exige -CaptureId et -EvidenceDirectory.'
    }
    Invoke-RuntimePreflight | Out-Null
    $remoteBackup = "$RemoteRoot/backups/$CaptureId/z-mesh-runtime-v1"
    $remoteStaging = "$RemoteRoot/staging/$CaptureId/z-mesh-runtime-v1"
    try {
        Invoke-Remote "test ! -e '$remoteBackup' && mkdir -p '$remoteBackup' '$remoteStaging'" | Out-Null
        & scp.exe -O -q -o BatchMode=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no `
            $LocalConfig "k1max-root`:$remoteStaging/k1-control-z-mesh.cfg"
        if ($LASTEXITCODE -ne 0) { throw 'Transfert de la configuration runtime KO.' }
        & scp.exe -O -q -o BatchMode=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no `
            $LocalModule "k1max-root`:$remoteStaging/k1_control_store.py"
        if ($LASTEXITCODE -ne 0) { throw 'Transfert du module runtime KO.' }
        Invoke-Remote "test `"`$(sha256sum '$remoteStaging/k1-control-z-mesh.cfg' | cut -d ' ' -f 1)`" = '$ExpectedConfigHash'" | Out-Null
        Invoke-Remote "test `"`$(sha256sum '$remoteStaging/k1_control_store.py' | cut -d ' ' -f 1)`" = '$ExpectedModuleHash'" | Out-Null

        Invoke-Remote "cp '$PrinterConfig' '$remoteBackup/printer.cfg.before'" | Out-Null
        $backupHash = ((Invoke-Remote "sha256sum '$remoteBackup/printer.cfg.before'" | Select-Object -First 1) -split '\s+')[0]
        if ($backupHash -ne $ExpectedPrinterHash) { throw 'Backup printer.cfg different.' }
        $checksumText = "$backupHash  printer.cfg.before"
        $checksumPayload = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$checksumText`n"))
        Invoke-Remote "echo '$checksumPayload' | base64 -d > '$remoteBackup/checksums.sha256'" | Out-Null
        Invoke-Remote "cd '$remoteBackup' && sha256sum -c checksums.sha256" | Out-Null
        Save-Evidence 'remote-backup-sha256.txt' $checksumText

        $awkProgram = '{print; if ($0 == "[include box.cfg]") {print "[include k1-control-z-mesh.cfg]"; count++}} END {if (count != 1) exit 42}'
        Invoke-Remote "awk '$awkProgram' '$PrinterConfig' > '$remoteStaging/printer.cfg.next'" | Out-Null
        Invoke-Remote "test `"`$(sha256sum '$remoteStaging/printer.cfg.next' | cut -d ' ' -f 1)`" = '$ExpectedNextPrinterHash'" | Out-Null

        $MutationStarted = $true
        Invoke-Remote "cp '$remoteStaging/k1_control_store.py' '$RuntimeModule.next' && chmod 600 '$RuntimeModule.next' && mv '$RuntimeModule.next' '$RuntimeModule'" | Out-Null
        Invoke-Remote "cp '$remoteStaging/k1-control-z-mesh.cfg' '$RuntimeConfig.next' && chmod 600 '$RuntimeConfig.next' && mv '$RuntimeConfig.next' '$RuntimeConfig'" | Out-Null
        Invoke-Remote "cp '$remoteStaging/printer.cfg.next' '$PrinterConfig.next' && test `"`$(sha256sum '$PrinterConfig.next' | cut -d ' ' -f 1)`" = '$ExpectedNextPrinterHash' && mv '$PrinterConfig.next' '$PrinterConfig' && sync" | Out-Null
        Invoke-KlipperScript 'RESTART' -NoResponse | Out-Null
        Assert-RuntimeInstalled | Out-Null
        Assert-FailClosedWithoutMotion
        Write-Output "DEPLOY_Z_MESH_RUNTIME_V1_OK capture=$CaptureId"
    }
    catch {
        $deploymentError = $_
        if ($MutationStarted) {
            try { Invoke-RuntimeRollback }
            catch { throw "Deploiement KO et rollback KO. Initial : $deploymentError`nRollback : $_" }
        }
        throw $deploymentError
    }
    exit 0
}

if ($Action -eq 'Validate') {
    Assert-RuntimeInstalled | Out-Null
    Write-Output 'VALIDATE_Z_MESH_RUNTIME_V1_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Invoke-RuntimeRollback
    Write-Output "ROLLBACK_Z_MESH_RUNTIME_V1_OK capture=$CaptureId"
    exit 0
}
