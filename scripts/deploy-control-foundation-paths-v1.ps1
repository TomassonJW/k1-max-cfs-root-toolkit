[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',

    [string]$Gate,

    [ValidatePattern('^[0-9]{8}-[0-9]{6}-g4-control-foundation-v3-paths-v1$')]
    [string]$CaptureId,

    [string]$EvidenceDirectory,

    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'PowerShell 7 ou plus recent est obligatoire pour ce deployeur.'
}

$RequiredGate = 'G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$NextConfig = Join-Path $WorkspaceRoot 'packages\k1-control-v1\paths-v1\moonraker.conf'
$PreviousConfigSha256 = '7e9cc023da9addc62f492f6cddf6ab901dbc9e97821e8306b05cfbd1b6e576f7'
$NextConfigSha256 = (Get-FileHash -LiteralPath $NextConfig -Algorithm SHA256).Hash.ToLowerInvariant()
$ExpectedNextConfigSha256 = 'fef837a1acaa59af400ac63c244df78dec6e70a71e1707d61f242f56cb1c7fba'
if ($NextConfigSha256 -ne $ExpectedNextConfigSha256) {
    throw 'Le moonraker.conf local ne correspond pas au candidat PATHS-V1 revu.'
}

$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteRelease = '/usr/data/k1-control-v1/releases/K1-CONTROL-V1.0.0'
$RemoteConfig = "$RemoteRelease/config/moonraker.conf"
$RemoteState = "$RemoteRoot/state"
$MoonrakerConfigRoot = "$RemoteState/config"
$MoonrakerGcodeRoot = "$RemoteState/gcodes"
$CrealityConfigRoot = '/usr/data/printer_data/config'
$CrealityGcodeRoot = '/usr/data/printer_data/gcodes'
$MoonrakerService = '/etc/init.d/S56k1_control_moonraker'
$GatewayService = '/etc/init.d/S57k1_control_gateway'
$MoonrakerPidFile = '/var/run/k1-control-moonraker.pid'
$GatewayPidFile = '/var/run/k1-control-nginx.pid'
$RuntimeMutationStarted = $false

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
    $resolvedEvidence = Assert-LocalPathInsideWorkspace $EvidenceDirectory
    $path = Join-Path $resolvedEvidence $Name
    if ($Value -is [string]) {
        $Value | Set-Content -LiteralPath $path -Encoding utf8
    }
    else {
        $Value | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $path -Encoding utf8
    }
}

function Wait-RemoteCondition {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$Attempts = 10,
        [int]$DelaySeconds = 2
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        if (Invoke-RemoteTest $Command) { return }
        if ($attempt -lt $Attempts) { Start-Sleep -Seconds $DelaySeconds }
    }
    throw "Delai depasse : $Label"
}

function Get-KlipperSnapshot {
    $python = @'
from __future__ import print_function
import json
import socket

request = {
    "id": 4301,
    "method": "objects/query",
    "params": {"objects": {
        "print_stats": ["state", "filename"],
        "extruder": ["target"],
        "heater_bed": ["target"],
        "toolhead": ["homed_axes"],
        "box": None,
    }},
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
status = message.get("result", {}).get("status", {})
box = status.get("box", {})
result = {
    "print_state": status.get("print_stats", {}).get("state"),
    "filename_empty": not bool(status.get("print_stats", {}).get("filename")),
    "extruder_target": status.get("extruder", {}).get("target"),
    "bed_target": status.get("heater_bed", {}).get("target"),
    "homed_axes": status.get("toolhead", {}).get("homed_axes"),
    "cfs": {},
}
for name in ("T1", "T2"):
    record = box.get(name, {})
    result["cfs"][name] = {
        "connected": record.get("state") == "connect",
        "version": record.get("version"),
        "slots": len(record.get("material_type", [])),
    }
print(json.dumps(result, sort_keys=True))
'@
    $bytes = [Text.Encoding]::UTF8.GetBytes($python.Replace("`r`n", "`n"))
    $payload = [Convert]::ToBase64String($bytes)
    $line = Invoke-Remote "echo $payload | base64 -d | /usr/share/klippy-env/bin/python"
    return ($line -join "`n") | ConvertFrom-Json
}

function Get-MoonrakerJson {
    param([Parameter(Mandatory = $true)][string]$Path)

    $python = @'
from __future__ import print_function
import json
import sys
from urllib.request import urlopen

path = sys.argv[1]
response = urlopen("http://127.0.0.1:7125" + path, timeout=5)
print(json.dumps(json.load(response), sort_keys=True))
'@
    $bytes = [Text.Encoding]::UTF8.GetBytes($python.Replace("`r`n", "`n"))
    $payload = [Convert]::ToBase64String($bytes)
    $line = Invoke-Remote "'$RemoteRelease/moonraker/moonraker-env/bin/python' -c 'import base64;exec(base64.b64decode(`"$payload`"))' '$Path'"
    return ($line -join "`n") | ConvertFrom-Json
}

function Get-GatewayAnonymousStatus {
    $python = @'
from __future__ import print_function
from urllib.error import HTTPError
from urllib.request import urlopen

try:
    response = urlopen("http://127.0.0.1:4409/", timeout=5)
    print(response.getcode())
except HTTPError as exc:
    print(exc.code)
'@
    $bytes = [Text.Encoding]::UTF8.GetBytes($python.Replace("`r`n", "`n"))
    $payload = [Convert]::ToBase64String($bytes)
    $line = Invoke-Remote "echo $payload | base64 -d | '$RemoteRelease/moonraker/moonraker-env/bin/python'"
    return [int](($line | Select-Object -First 1).Trim())
}

function Get-MemorySnapshot {
    $lines = Invoke-Remote "grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo"
    $values = @{}
    foreach ($line in $lines) {
        if ($line -match '^([^:]+):\s+([0-9]+)') {
            $values[$Matches[1]] = [int64]$Matches[2]
        }
    }
    return $values
}

function Assert-StockProcesses {
    foreach ($process in @(
            '[k]lippy/klippy.py',
            '[k]lipper_mcu',
            '[m]aster-server',
            '[a]pp-server',
            '[d]isplay-server',
            '[w]eb-server',
            '[M]onitor'
        )) {
        if (-not (Invoke-RemoteTest "ps w | grep -q '$process'")) {
            throw "Processus Creality absent : $process"
        }
    }
}

function Assert-PrinterIdle {
    param([switch]$AllowHomedAxes)

    $klipper = Get-KlipperSnapshot
    if ($klipper.print_state -ne 'standby' -or -not $klipper.filename_empty) {
        throw "Imprimante non disponible : etat=$($klipper.print_state)"
    }
    if ([double]$klipper.extruder_target -ne 0 -or [double]$klipper.bed_target -ne 0) {
        throw 'Une chauffe est demandee.'
    }
    if ($klipper.homed_axes -and -not $AllowHomedAxes) {
        throw "Axes encore homes : $($klipper.homed_axes)"
    }
    foreach ($name in @('T1', 'T2')) {
        $unit = $klipper.cfs.$name
        if (-not $unit.connected -or $unit.version -ne '1.1.3' -or $unit.slots -ne 4) {
            throw "CFS $name inattendu ou deconnecte."
        }
    }
    Assert-StockProcesses
    return $klipper
}

function Assert-FoundationListeners {
    $listeners = (Invoke-Remote 'netstat -lnt') -join "`n"
    foreach ($required in @(
            '127.0.0.1:7125',
            '0.0.0.0:4409',
            '0.0.0.0:80',
            '0.0.0.0:8080',
            '0.0.0.0:9999'
        )) {
        if ($listeners -notmatch [regex]::Escape($required)) {
            throw "Ecoute absente : $required"
        }
    }
    if ($listeners -match '0.0.0.0:7125') {
        throw 'Moonraker est expose directement au LAN.'
    }
    if ((Get-GatewayAnonymousStatus) -ne 401) {
        throw 'La protection nginx ne refuse plus les connexions anonymes.'
    }
    return $listeners
}

function Invoke-PathsPreflight {
    $architecture = (Invoke-Remote 'uname -m' | Select-Object -First 1).Trim()
    if ($architecture -ne 'mips') { throw "Architecture inattendue : $architecture" }
    $board = (Invoke-Remote '/usr/bin/get_sn_mac.sh board' | Select-Object -First 1).Trim()
    if ($board -ne 'CR4CU220812S12') { throw "Carte inattendue : $board" }
    $structure = (Invoke-Remote '/usr/bin/get_sn_mac.sh structure_version' | Select-Object -First 1).Trim()
    if ($structure -ne '0') { throw "Structure inattendue : $structure" }
    $version = (Invoke-Remote "grep '^ota_version=' /etc/ota_info" | Select-Object -First 1).Trim()
    if ($version -ne 'ota_version=2.3.5.34') { throw "Firmware inattendu : $version" }

    foreach ($tool in @('sha256sum', 'tar', 'find', 'rmdir', 'ln', 'cut', 'netstat', 'base64')) {
        if (-not (Invoke-RemoteTest "command -v '$tool'")) {
            throw "Outil systeme absent : $tool"
        }
    }

    foreach ($path in @($MoonrakerService, $GatewayService, $RemoteConfig)) {
        if (-not (Invoke-RemoteTest "test -e '$path'")) { throw "Fondation V3 absente : $path" }
    }
    if (-not (Invoke-RemoteTest "test -s '$MoonrakerPidFile' && kill -0 `$(cat '$MoonrakerPidFile')")) {
        throw 'Moonraker dedie inactif.'
    }
    if (-not (Invoke-RemoteTest "test -s '$GatewayPidFile' && kill -0 `$(cat '$GatewayPidFile')")) {
        throw 'Passerelle nginx dediee inactive.'
    }
    foreach ($root in @($CrealityConfigRoot, $CrealityGcodeRoot)) {
        if (-not (Invoke-RemoteTest "test -d '$root' && test ! -L '$root'")) {
            throw "Racine Creality inattendue : $root"
        }
    }
    if (-not (Invoke-RemoteTest "test -f '$CrealityConfigRoot/printer.cfg'")) {
        throw 'printer.cfg actif absent.'
    }
    foreach ($root in @($MoonrakerConfigRoot, $MoonrakerGcodeRoot)) {
        if (-not (Invoke-RemoteTest "test -d '$root' && test ! -L '$root' && test -z `"`$(find '$root' -mindepth 1 -maxdepth 1 -print -quit)`"")) {
            throw "Racine Moonraker non vide ou deja modifiee : $root"
        }
    }
    $remoteConfigHash = ((Invoke-Remote "sha256sum '$RemoteConfig'" | Select-Object -First 1) -split '\s+')[0]
    if ($remoteConfigHash -ne $PreviousConfigSha256) {
        throw "moonraker.conf distant inattendu : $remoteConfigHash"
    }

    $klipper = Assert-PrinterIdle
    $listeners = Assert-FoundationListeners
    $roots = Get-MoonrakerJson '/server/files/roots'
    $configRoot = @($roots.result | Where-Object { $_.name -eq 'config' })
    $gcodeRoot = @($roots.result | Where-Object { $_.name -eq 'gcodes' })
    if ($configRoot.Count -ne 1 -or $configRoot[0].permissions -ne 'rw') {
        throw 'Permission config initiale inattendue.'
    }
    if ($gcodeRoot.Count -ne 1 -or $gcodeRoot[0].permissions -ne 'rw') {
        throw 'Permission gcodes initiale inattendue.'
    }
    $serverInfo = Get-MoonrakerJson '/server/info'
    $warnings = @($serverInfo.result.warnings)
    foreach ($pattern in @(
            'Klipper configuration file not located',
            'GCode path received from Klipper does not match'
        )) {
        if (@($warnings | Where-Object { $_ -match $pattern }).Count -ne 1) {
            throw "Avertissement initial absent ou duplique : $pattern"
        }
    }
    $memory = Get-MemorySnapshot
    $gatewayPid = (Invoke-Remote "cat '$GatewayPidFile'" | Select-Object -First 1).Trim()
    Save-Evidence 'preflight-klipper.json' $klipper
    Save-Evidence 'preflight-listeners.txt' $listeners
    Save-Evidence 'preflight-memory.json' $memory
    Save-Evidence 'preflight-paths.txt' "config=directory-empty; gcodes=directory-empty; remote_config_sha256=$remoteConfigHash"
    Save-Evidence 'preflight-roots.json' $roots
    Save-Evidence 'preflight-server-info.json' $serverInfo
    return [pscustomobject]@{
        GatewayPid = $gatewayPid
        Memory = $memory
    }
}

function Assert-PathCorrection {
    param(
        [string]$ExpectedGatewayPid,
        [switch]$AllowHomedAxes
    )

    if (-not (Invoke-RemoteTest "test -L '$MoonrakerConfigRoot' && test `"`$(readlink '$MoonrakerConfigRoot')`" = '$CrealityConfigRoot'")) {
        throw 'Lien config absent ou inattendu.'
    }
    if (-not (Invoke-RemoteTest "test -L '$MoonrakerGcodeRoot' && test `"`$(readlink '$MoonrakerGcodeRoot')`" = '$CrealityGcodeRoot'")) {
        throw 'Lien gcodes absent ou inattendu.'
    }
    $remoteConfigHash = ((Invoke-Remote "sha256sum '$RemoteConfig'" | Select-Object -First 1) -split '\s+')[0]
    if ($remoteConfigHash -ne $NextConfigSha256) {
        throw "moonraker.conf PATHS-V1 absent : $remoteConfigHash"
    }

    Wait-RemoteCondition "test -s '$MoonrakerPidFile' && kill -0 `$(cat '$MoonrakerPidFile') && netstat -lnt | grep -q '127.0.0.1:7125'" 'redemarrage du Moonraker dedie'
    $roots = Get-MoonrakerJson '/server/files/roots'
    $configRoot = @($roots.result | Where-Object { $_.name -eq 'config' })
    $gcodeRoot = @($roots.result | Where-Object { $_.name -eq 'gcodes' })
    if ($configRoot.Count -ne 1 -or $configRoot[0].permissions -ne 'r') {
        throw 'La racine config API n est pas strictement en lecture seule.'
    }
    if ($gcodeRoot.Count -ne 1 -or $gcodeRoot[0].permissions -ne 'rw') {
        throw 'Le pouvoir restant sur gcodes n est pas expose comme attendu.'
    }

    $serverInfo = $null
    for ($attempt = 1; $attempt -le 10; $attempt++) {
        $serverInfo = Get-MoonrakerJson '/server/info'
        $warnings = @($serverInfo.result.warnings)
        $pathWarnings = @($warnings | Where-Object {
                $_ -match 'Klipper configuration file not located' -or
                $_ -match 'GCode path received from Klipper does not match'
            })
        if ($pathWarnings.Count -eq 0) { break }
        if ($attempt -lt 10) { Start-Sleep -Seconds 2 }
    }
    if ($pathWarnings.Count -ne 0) {
        throw 'Les avertissements de chemins Moonraker sont encore presents.'
    }

    $klipper = Assert-PrinterIdle -AllowHomedAxes:$AllowHomedAxes
    $listeners = Assert-FoundationListeners
    if ($ExpectedGatewayPid) {
        $gatewayPid = (Invoke-Remote "cat '$GatewayPidFile'" | Select-Object -First 1).Trim()
        if ($gatewayPid -ne $ExpectedGatewayPid) {
            throw 'La passerelle nginx a ete redemarree hors perimetre.'
        }
    }
    $memory = Get-MemorySnapshot
    if ($memory.MemAvailable -lt (64 * 1024)) {
        throw 'RAM disponible sous 64 Mio.'
    }

    Save-Evidence 'validation-roots.json' $roots
    Save-Evidence 'validation-server-info.json' $serverInfo
    Save-Evidence 'validation-klipper.json' $klipper
    Save-Evidence 'validation-listeners.txt' $listeners
    Save-Evidence 'validation-memory.json' $memory
    Save-Evidence 'gcode-api-risk.txt' 'gcodes permissions=rw; upload/delete/start remain possible for an authenticated Mainsail user; no such endpoint was called during validation'
}

function Assert-RollbackState {
    foreach ($root in @($MoonrakerConfigRoot, $MoonrakerGcodeRoot)) {
        if (-not (Invoke-RemoteTest "test -d '$root' && test ! -L '$root' && test -z `"`$(find '$root' -mindepth 1 -maxdepth 1 -print -quit)`"")) {
            throw "Rollback de racine incomplet : $root"
        }
    }
    $remoteConfigHash = ((Invoke-Remote "sha256sum '$RemoteConfig'" | Select-Object -First 1) -split '\s+')[0]
    if ($remoteConfigHash -ne $PreviousConfigSha256) {
        throw 'Rollback de moonraker.conf incomplet.'
    }
    Wait-RemoteCondition "test -s '$MoonrakerPidFile' && kill -0 `$(cat '$MoonrakerPidFile') && netstat -lnt | grep -q '127.0.0.1:7125'" 'retour du Moonraker V3 initial'
    Assert-PrinterIdle | Out-Null
    Assert-FoundationListeners | Out-Null
}

function Invoke-PathsRollback {
    param([switch]$BestEffort)

    if (-not $CaptureId) { throw 'Rollback exige -CaptureId.' }
    $remoteBackup = "$RemoteRoot/backups/$CaptureId/paths-v1"
    $commands = @(
        "test -f '$remoteBackup/moonraker.conf.before'",
        "test -f '$remoteBackup/empty-roots.before.tar'",
        "test -f '$remoteBackup/checksums.sha256'",
        "cd '$remoteBackup' && sha256sum -c checksums.sha256",
        "active_hash=`$(sha256sum '$RemoteConfig' | cut -d ' ' -f 1); test `"`$active_hash`" = '$PreviousConfigSha256' || test `"`$active_hash`" = '$NextConfigSha256'",
        "test ! -L '$MoonrakerConfigRoot' || test `"`$(readlink '$MoonrakerConfigRoot')`" = '$CrealityConfigRoot'",
        "test ! -L '$MoonrakerGcodeRoot' || test `"`$(readlink '$MoonrakerGcodeRoot')`" = '$CrealityGcodeRoot'",
        "test ! -s '$MoonrakerPidFile' || '$MoonrakerService' stop",
        "test ! -L '$MoonrakerConfigRoot' || rm -f '$MoonrakerConfigRoot'",
        "test ! -L '$MoonrakerGcodeRoot' || rm -f '$MoonrakerGcodeRoot'",
        "tar -xpf '$remoteBackup/empty-roots.before.tar' -C '$RemoteState'",
        "cp '$remoteBackup/moonraker.conf.before' '$RemoteConfig.rollback-next'",
        "test `"`$(sha256sum '$RemoteConfig.rollback-next' | cut -d ' ' -f 1)`" = '$PreviousConfigSha256'",
        "mv '$RemoteConfig.rollback-next' '$RemoteConfig'",
        "'$MoonrakerService' start"
    )
    foreach ($command in $commands) {
        try { Invoke-Remote $command | Out-Null }
        catch {
            if (-not $BestEffort) { throw }
        }
    }
    try { Assert-RollbackState }
    catch {
        if (-not $BestEffort) { throw }
    }
}

if ($Action -eq 'Plan') {
    [pscustomobject]@{
        status = 'PLAN_ONLY'
        gate = $RequiredGate
        printer_mutation_authorized = $false
        previous_config_sha256 = $PreviousConfigSha256
        next_config_sha256 = $NextConfigSha256
        config_target = $CrealityConfigRoot
        gcodes_target = $CrealityGcodeRoot
        config_api_permissions = 'r'
        gcodes_api_permissions = 'rw'
        service_restart = $MoonrakerService
        actions = @('Preflight', 'Deploy', 'Validate', 'Rollback')
    } | ConvertTo-Json -Depth 4
    exit 0
}

Assert-ExactGate
if ($EvidenceDirectory) {
    [void](Assert-LocalPathInsideWorkspace $EvidenceDirectory)
}

if ($Action -eq 'Preflight') {
    Invoke-PathsPreflight | ConvertTo-Json -Depth 5
    Write-Output 'PREFLIGHT_OK'
    exit 0
}

if ($Action -eq 'Deploy') {
    if (-not $CaptureId -or -not $EvidenceDirectory) {
        throw 'Deploy exige -CaptureId et -EvidenceDirectory.'
    }
    $preflight = Invoke-PathsPreflight
    $remoteBackup = "$RemoteRoot/backups/$CaptureId/paths-v1"
    $remoteStaging = "$RemoteRoot/staging/$CaptureId"
    try {
        Invoke-Remote "test ! -e '$remoteBackup' && mkdir -p '$remoteBackup' '$remoteStaging'" | Out-Null
        & scp.exe -O -q -o BatchMode=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no `
            $NextConfig "k1max-root`:$remoteStaging/moonraker.conf.paths-v1"
        if ($LASTEXITCODE -ne 0) { throw 'Transfert SCP du moonraker.conf PATHS-V1 KO.' }
        $stagedHash = ((Invoke-Remote "sha256sum '$remoteStaging/moonraker.conf.paths-v1'" | Select-Object -First 1) -split '\s+')[0]
        if ($stagedHash -ne $NextConfigSha256) { throw 'SHA-256 du fichier transfere different.' }

        Invoke-Remote "cp '$RemoteConfig' '$remoteBackup/moonraker.conf.before'" | Out-Null
        Invoke-Remote "tar -cpf '$remoteBackup/empty-roots.before.tar' -C '$RemoteState' config gcodes" | Out-Null
        $backupConfigHash = ((Invoke-Remote "sha256sum '$remoteBackup/moonraker.conf.before'" | Select-Object -First 1) -split '\s+')[0]
        if ($backupConfigHash -ne $PreviousConfigSha256) { throw 'Backup moonraker.conf different.' }
        $backupTarHash = ((Invoke-Remote "sha256sum '$remoteBackup/empty-roots.before.tar'" | Select-Object -First 1) -split '\s+')[0]
        $backupChecksums = "$backupConfigHash  moonraker.conf.before`n$backupTarHash  empty-roots.before.tar"
        $checksumBytes = [Text.Encoding]::ASCII.GetBytes("$backupChecksums`n")
        $checksumPayload = [Convert]::ToBase64String($checksumBytes)
        Invoke-Remote "echo '$checksumPayload' | base64 -d > '$remoteBackup/checksums.sha256'" | Out-Null
        Invoke-Remote "cd '$remoteBackup' && sha256sum -c checksums.sha256" | Out-Null
        Save-Evidence 'remote-backup-sha256.txt' $backupChecksums

        $RuntimeMutationStarted = $true
        Invoke-Remote "'$MoonrakerService' stop" | Out-Null
        Wait-RemoteCondition "test ! -e '$MoonrakerPidFile' && ! netstat -lnt | grep -q '127.0.0.1:7125'" 'arret du Moonraker dedie' 10 1
        Invoke-Remote "rmdir '$MoonrakerConfigRoot'" | Out-Null
        Invoke-Remote "rmdir '$MoonrakerGcodeRoot'" | Out-Null
        Invoke-Remote "ln -s '$CrealityConfigRoot' '$MoonrakerConfigRoot'" | Out-Null
        Invoke-Remote "ln -s '$CrealityGcodeRoot' '$MoonrakerGcodeRoot'" | Out-Null
        Invoke-Remote "cp '$remoteStaging/moonraker.conf.paths-v1' '$RemoteConfig.paths-next'" | Out-Null
        Invoke-Remote "test `"`$(sha256sum '$RemoteConfig.paths-next' | cut -d ' ' -f 1)`" = '$NextConfigSha256'" | Out-Null
        Invoke-Remote "mv '$RemoteConfig.paths-next' '$RemoteConfig'" | Out-Null
        Invoke-Remote "'$MoonrakerService' start" | Out-Null
        Assert-PathCorrection -ExpectedGatewayPid $preflight.GatewayPid
        Write-Output "DEPLOY_PATHS_V1_OK capture=$CaptureId"
    }
    catch {
        $deploymentError = $_
        if ($RuntimeMutationStarted) {
            try { Invoke-PathsRollback }
            catch {
                throw "Deploiement KO et rollback KO. Erreur initiale : $deploymentError`nErreur rollback : $_"
            }
        }
        throw $deploymentError
    }
    exit 0
}

if ($Action -eq 'Validate') {
    Assert-PathCorrection -AllowHomedAxes
    Write-Output 'VALIDATE_PATHS_V1_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Invoke-PathsRollback
    Write-Output "ROLLBACK_PATHS_V1_OK capture=$CaptureId"
    exit 0
}
