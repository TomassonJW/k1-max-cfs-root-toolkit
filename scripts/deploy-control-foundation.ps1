[CmdletBinding()]
param(
    [ValidateSet('Plan', 'InstallBootstrap', 'SetGatewayAccount', 'ActivateLan', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',

    [string]$Gate,

    [string]$Bundle,

    [ValidatePattern('^[0-9]{8}-[0-9]{6}-g4-control-foundation-v3$')]
    [string]$CaptureId,

    [string]$EvidenceDirectory,

    [ValidateSet('Bootstrap', 'BootstrapAuth', 'Lan')]
    [string]$Exposure = 'Bootstrap',

    [switch]$Execute,

    [switch]$AccountVerified,

    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{2,31}$')]
    [string]$GatewayUsername,

    [Security.SecureString]$GatewayPassword
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'PowerShell 7 ou plus recent est obligatoire pour ce deployeur.'
}

$RequiredGate = 'G4-K1-CONTROL-FOUNDATION-V3'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ManifestPath = Join-Path $WorkspaceRoot 'packages\k1-control-v1\foundation-manifest.json'
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$ResourceGates = $Manifest.resource_gates
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteRelease = '/usr/data/k1-control-v1/releases/K1-CONTROL-V1.0.0'
$RemoteCurrent = '/usr/data/k1-control-v1/current'
$MoonrakerService = '/etc/init.d/S56k1_control_moonraker'
$GatewayService = '/etc/init.d/S57k1_control_gateway'
$GatewayPasswordFile = '/usr/data/k1-control-v1/state/nginx.htpasswd'
$MutationStarted = $false
$RemoteRootWasProvenAbsent = $false

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

function Invoke-RemoteWithInput {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string]$InputText
    )

    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = 'ssh.exe'
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.StandardInputEncoding = [Text.UTF8Encoding]::new($false)
    foreach ($argument in $SshArguments) {
        [void]$startInfo.ArgumentList.Add($argument)
    }
    [void]$startInfo.ArgumentList.Add($Command)

    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    try {
        if (-not $process.Start()) { throw 'Demarrage SSH impossible.' }
        $standardOutput = $process.StandardOutput.ReadToEndAsync()
        $standardError = $process.StandardError.ReadToEndAsync()
        $process.StandardInput.Write($InputText)
        $process.StandardInput.Write("`n")
        $process.StandardInput.Close()
        $process.WaitForExit()
        $outputText = $standardOutput.GetAwaiter().GetResult()
        $errorText = $standardError.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0) {
            throw "Commande distante avec entree protegee KO ($($process.ExitCode)).`n$errorText"
        }
        return @($outputText -split '\r?\n' | Where-Object { $_ -ne '' })
    }
    finally {
        $process.Dispose()
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

function Assert-RemoteFilesEqual {
    param(
        [Parameter(Mandatory = $true)][string]$Expected,
        [Parameter(Mandatory = $true)][string]$Actual
    )

    $lines = Invoke-Remote "sha256sum '$Expected' '$Actual'"
    if ($lines.Count -ne 2) { throw 'Comparaison SHA-256 distante incomplete.' }
    $expectedHash = (($lines[0] -split '\s+')[0]).ToLowerInvariant()
    $actualHash = (($lines[1] -split '\s+')[0]).ToLowerInvariant()
    if ($expectedHash -ne $actualHash) {
        throw "Fichier installe different : $Actual"
    }
}

function Get-KlipperPreflight {
    $python = @'
from __future__ import print_function
import json
import socket

request = {
    "id": 4102,
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

function Get-MoonrakerAccessInfo {
    $python = @'
from __future__ import print_function
import json
from urllib.request import urlopen

response = urlopen("http://127.0.0.1:7125/access/info", timeout=5)
print(json.dumps(json.load(response), sort_keys=True))
'@
    $bytes = [Text.Encoding]::UTF8.GetBytes($python.Replace("`r`n", "`n"))
    $payload = [Convert]::ToBase64String($bytes)
    $line = Invoke-Remote "echo $payload | base64 -d | '$RemoteRelease/moonraker/moonraker-env/bin/python'"
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

function Test-GatewayCredential {
    param(
        [Parameter(Mandatory = $true)][string]$Username,
        [Parameter(Mandatory = $true)][string]$PlainPassword
    )

    $python = @'
from __future__ import print_function
import base64
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

credentials = json.load(sys.stdin)

def request_status(request):
    try:
        return urlopen(request, timeout=5).getcode()
    except HTTPError as exc:
        return exc.code

anonymous = request_status(Request("http://127.0.0.1:4409/"))
raw = (credentials["username"] + ":" + credentials["password"]).encode("utf-8")
authenticated_request = Request("http://127.0.0.1:4409/")
authenticated_request.add_header(
    "Authorization", "Basic " + base64.b64encode(raw).decode("ascii")
)
authenticated = request_status(authenticated_request)
print(json.dumps({
    "anonymous_status": anonymous,
    "authenticated_status": authenticated,
}, sort_keys=True))
'@
    $bytes = [Text.Encoding]::UTF8.GetBytes($python.Replace("`r`n", "`n"))
    $scriptPayload = [Convert]::ToBase64String($bytes)
    $inputPayload = @{ username = $Username; password = $PlainPassword } |
        ConvertTo-Json -Compress
    $line = Invoke-RemoteWithInput `
        "'$RemoteRelease/moonraker/moonraker-env/bin/python' -c 'import base64;exec(base64.b64decode(`"$scriptPayload`"))'" `
        $inputPayload
    return ($line -join "`n") | ConvertFrom-Json
}

function New-SshaPasswordRecord {
    param(
        [Parameter(Mandatory = $true)][string]$Username,
        [Parameter(Mandatory = $true)][string]$PlainPassword
    )

    if ($PlainPassword.Length -lt [int]$Manifest.network.password_minimum_characters) {
        throw "Le mot de passe doit contenir au moins $($Manifest.network.password_minimum_characters) caracteres."
    }
    if ($PlainPassword.Length -gt [int]$Manifest.network.password_maximum_characters -or
        $PlainPassword -cnotmatch '^[\x21-\x7E]+$') {
        throw "Le mot de passe doit utiliser 16 a $($Manifest.network.password_maximum_characters) caracteres ASCII imprimables sans espace."
    }
    $passwordBytes = [Text.Encoding]::UTF8.GetBytes($PlainPassword)
    $salt = New-Object byte[] 16
    $inputBytes = New-Object byte[] ($passwordBytes.Length + $salt.Length)
    try {
        [Security.Cryptography.RandomNumberGenerator]::Fill($salt)
        [Array]::Copy($passwordBytes, 0, $inputBytes, 0, $passwordBytes.Length)
        [Array]::Copy($salt, 0, $inputBytes, $passwordBytes.Length, $salt.Length)
        $sha1 = [Security.Cryptography.SHA1]::Create()
        try { $digest = $sha1.ComputeHash($inputBytes) }
        finally { $sha1.Dispose() }
        $stored = New-Object byte[] ($digest.Length + $salt.Length)
        [Array]::Copy($digest, 0, $stored, 0, $digest.Length)
        [Array]::Copy($salt, 0, $stored, $digest.Length, $salt.Length)
        return "${Username}:{SSHA}$([Convert]::ToBase64String($stored))"
    }
    finally {
        [Array]::Clear($passwordBytes, 0, $passwordBytes.Length)
        [Array]::Clear($inputBytes, 0, $inputBytes.Length)
    }
}

function Save-Evidence {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Value
    )

    if (-not $EvidenceDirectory) {
        return
    }
    $resolvedEvidence = Assert-LocalPathInsideWorkspace $EvidenceDirectory
    $path = Join-Path $resolvedEvidence $Name
    if ($Value -is [string]) {
        $Value | Set-Content -LiteralPath $path -Encoding utf8
    }
    else {
        $Value | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $path -Encoding utf8
    }
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

function Invoke-FoundationPreflight {
    $architecture = (Invoke-Remote 'uname -m' | Select-Object -First 1).Trim()
    if ($architecture -ne 'mips') { throw "Architecture inattendue : $architecture" }

    $board = (Invoke-Remote '/usr/bin/get_sn_mac.sh board' | Select-Object -First 1).Trim()
    if ($board -ne 'CR4CU220812S12') { throw "Carte inattendue : $board" }

    $structure = (Invoke-Remote '/usr/bin/get_sn_mac.sh structure_version' | Select-Object -First 1).Trim()
    if ($structure -ne '0') { throw "Structure inattendue : $structure" }

    $version = (Invoke-Remote "grep '^ota_version=' /etc/ota_info" | Select-Object -First 1).Trim()
    if ($version -ne 'ota_version=2.3.5.34') { throw "Firmware inattendu : $version" }

    if (-not (Invoke-RemoteTest "test -x /sbin/start-stop-daemon")) {
        throw 'start-stop-daemon absent.'
    }
    foreach ($tool in @('base64', 'tar', 'unzip', 'sha256sum', 'du', 'df', 'netstat')) {
        if (-not (Invoke-RemoteTest "command -v '$tool'")) {
            throw "Outil systeme absent : $tool"
        }
    }

    $klipper = Get-KlipperPreflight
    if ($klipper.print_state -ne 'standby' -or -not $klipper.filename_empty) {
        throw "Imprimante non disponible : etat=$($klipper.print_state)"
    }
    if ([double]$klipper.extruder_target -ne 0 -or [double]$klipper.bed_target -ne 0) {
        throw 'Une chauffe est demandee.'
    }
    if ($klipper.homed_axes) { throw "Axes encore homes : $($klipper.homed_axes)" }
    foreach ($name in @('T1', 'T2')) {
        $unit = $klipper.cfs.$name
        if (-not $unit.connected -or $unit.version -ne '1.1.3' -or $unit.slots -ne 4) {
            throw "CFS $name inattendu ou deconnecte."
        }
    }
    Assert-StockProcesses

    if (-not (Invoke-RemoteTest "test -S /dev/log")) { throw '/dev/log absent ou incorrect.' }
    if (-not (Invoke-RemoteTest "ps w | grep -q '[s]yslogd -n'")) { throw 'syslogd actif introuvable.' }
    $syslogHelp = Invoke-Remote 'syslogd --help 2>&1'
    $syslogText = $syslogHelp -join "`n"
    if ($syslogText -notmatch 'default 200KB' -or $syslogText -notmatch 'default 1') {
        throw 'Rotation BusyBox syslog inattendue.'
    }

    foreach ($path in @($RemoteRoot, $MoonrakerService, $GatewayService)) {
        if (Invoke-RemoteTest "test -e '$path'") { throw "Cible deja presente : $path" }
    }
    $script:RemoteRootWasProvenAbsent = $true

    $listeners = Invoke-Remote 'netstat -lnt'
    $listenerText = $listeners -join "`n"
    foreach ($port in @(80, 8080, 9999)) {
        if ($listenerText -notmatch ":$port\s") { throw "Port Creality absent : $port" }
    }
    if ($listenerText -match ':7125\s' -or $listenerText -match ':4409\s') {
        throw 'Un port de la fondation est deja utilise.'
    }

    $memory = Get-MemorySnapshot
    $disk = Invoke-Remote 'df -k /usr/data'
    $diskFields = (($disk | Select-Object -Last 1).Trim() -split '\s+')
    $minimumFreeKib = [int64]$ResourceGates.minimum_usr_data_free_before_install_mib * 1024
    if ($diskFields.Count -lt 4 -or [int64]$diskFields[3] -lt $minimumFreeKib) {
        throw "Moins de $($ResourceGates.minimum_usr_data_free_before_install_mib) Mio disponibles sous /usr/data."
    }
    Save-Evidence 'klipper-preflight.json' $klipper
    Save-Evidence 'memory-before.json' $memory
    Save-Evidence 'listeners-before.txt' $listenerText
    Save-Evidence 'disk-before.txt' ($disk -join "`n")
    return $memory
}

function Assert-Bundle {
    $resolvedBundle = Assert-LocalPathInsideWorkspace $Bundle
    if (-not (Test-Path -LiteralPath $resolvedBundle -PathType Container)) {
        throw 'Bundle local introuvable.'
    }
    $checksumPath = Join-Path $resolvedBundle 'checksums.sha256'
    foreach ($line in Get-Content -LiteralPath $checksumPath) {
        if ($line -notmatch '^([0-9a-f]{64})  (.+)$') { throw "Ligne SHA-256 invalide : $line" }
        $expected = $Matches[1]
        $relative = $Matches[2].Replace('/', [IO.Path]::DirectorySeparatorChar)
        $file = Join-Path $resolvedBundle $relative
        $resolvedFile = Assert-LocalPathInsideWorkspace $file
        $actual = (Get-FileHash -LiteralPath $resolvedFile -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $expected) { throw "SHA-256 local different : $relative" }
    }
    return $resolvedBundle
}

function New-TransportArchive {
    param([Parameter(Mandatory = $true)][string]$ResolvedBundle)

    $deployRoot = Join-Path $WorkspaceRoot ".codex-work\deploy\$CaptureId"
    New-Item -ItemType Directory -Path $deployRoot -Force | Out-Null
    $transport = Join-Path $deployRoot 'k1-control-foundation-v3.tar.gz'
    if (Test-Path -LiteralPath $transport) { Remove-Item -LiteralPath $transport -Force }
    & tar.exe -czf $transport -C $ResolvedBundle .
    if ($LASTEXITCODE -ne 0) { throw 'Creation de l archive de transport KO.' }
    return $transport
}

function Invoke-FoundationRollback {
    param([switch]$BestEffort)

    $rootRemovalGuard = if ($script:RemoteRootWasProvenAbsent) {
        'true'
    }
    else {
        "test `"`$(cat '$RemoteRoot/backups/$CaptureId/root.before' 2>/dev/null)`" = 'ABSENT'"
    }
    $commands = @(
        "test ! -x '$GatewayService' || '$GatewayService' stop",
        "test ! -x '$MoonrakerService' || '$MoonrakerService' stop",
        "rm -f '$GatewayService'",
        "rm -f '$MoonrakerService'",
        "rm -f '$RemoteCurrent'",
        "$rootRemovalGuard && rm -rf '$RemoteRoot'"
    )
    foreach ($command in $commands) {
        try { Invoke-Remote $command | Out-Null }
        catch {
            if (-not $BestEffort) { throw }
        }
    }
    try {
        Wait-RemoteCondition "test ! -e '$RemoteRoot' && test ! -e '$GatewayService' && test ! -e '$MoonrakerService' && test ! -e /var/run/k1-control-nginx.pid && test ! -e /var/run/k1-control-moonraker.pid && ! netstat -lnt | grep -q ':4409\|:7125'" 'restauration complete de l absence V3' 10 1
    }
    catch {
        if (-not $BestEffort) { throw }
    }
}

function Invoke-FoundationValidation {
    param(
        [hashtable]$MemoryBefore,
        [switch]$LanExpected,
        [switch]$AuthExpected
    )

    $listeners = (Invoke-Remote 'netstat -lnt') -join "`n"
    $gatewayListener = if ($LanExpected) { '0.0.0.0:4409' } else { '127.0.0.1:4409' }
    foreach ($required in @('127.0.0.1:7125', $gatewayListener, '0.0.0.0:80', '0.0.0.0:8080', '0.0.0.0:9999')) {
        if ($listeners -notmatch [regex]::Escape($required)) { throw "Ecoute absente : $required" }
    }
    if ($listeners -match '0.0.0.0:7125') {
        throw 'Moonraker est expose directement au LAN.'
    }
    if (-not $LanExpected -and $listeners -match '0.0.0.0:4409') {
        throw 'Fondation exposee au LAN avant creation du compte.'
    }

    $anonymousStatus = Get-GatewayAnonymousStatus
    $expectedAnonymousStatus = if ($AuthExpected) { 401 } else { 200 }
    if ($anonymousStatus -ne $expectedAnonymousStatus) {
        throw "Protection nginx inattendue : HTTP $anonymousStatus, attendu $expectedAnonymousStatus."
    }

    $accessInfo = Get-MoonrakerAccessInfo
    if (-not $accessInfo.result.trusted -or $accessInfo.result.login_required) {
        throw 'La relation de confiance nginx vers Moonraker est inattendue.'
    }

    Assert-StockProcesses
    foreach ($pidFile in @('/var/run/k1-control-moonraker.pid', '/var/run/k1-control-nginx.pid')) {
        if (-not (Invoke-RemoteTest "test -s '$pidFile' && kill -0 `$(cat '$pidFile')")) {
            throw "Nouveau service inactif : $pidFile"
        }
    }

    $memoryAfter = Get-MemorySnapshot
    $minimumAvailableKib = [int64]$ResourceGates.minimum_available_ram_after_start_mib * 1024
    if ($memoryAfter.MemAvailable -lt $minimumAvailableKib) {
        throw "RAM disponible sous $($ResourceGates.minimum_available_ram_after_start_mib) Mio."
    }
    if ($MemoryBefore) {
        $swapBefore = $MemoryBefore.SwapTotal - $MemoryBefore.SwapFree
        $swapAfter = $memoryAfter.SwapTotal - $memoryAfter.SwapFree
        $maximumSwapGrowthKib = [int64]$ResourceGates.maximum_swap_growth_mib * 1024
        if (($swapAfter - $swapBefore) -gt $maximumSwapGrowthKib) {
            throw "Hausse de swap superieure a $($ResourceGates.maximum_swap_growth_mib) Mio."
        }
    }

    $rssLine = Invoke-Remote "pid=`$(cat /var/run/k1-control-moonraker.pid); grep '^VmRSS:' /proc/`$pid/status"
    $rssText = $rssLine -join "`n"
    if ($rssText -notmatch 'VmRSS:\s+([0-9]+)') { throw 'RSS Moonraker illisible.' }
    $maximumMoonrakerKib = [int64]$ResourceGates.maximum_moonraker_idle_rss_mib * 1024
    if ([int64]$Matches[1] -gt $maximumMoonrakerKib) {
        throw "Moonraker depasse $($ResourceGates.maximum_moonraker_idle_rss_mib) Mio au repos."
    }

    $logSize = (Invoke-Remote "du -sk '$RemoteRoot/logs'" | Select-Object -First 1)
    if ($logSize -notmatch '^([0-9]+)') { throw 'Taille des logs illisible.' }
    $maximumLogsKib = [int64]$ResourceGates.maximum_logs_disk_mib * 1024
    if ([int64]$Matches[1] -gt $maximumLogsKib) {
        throw "Logs du projet au-dessus de $($ResourceGates.maximum_logs_disk_mib) Mio."
    }

    $releaseSize = (Invoke-Remote "du -sk '$RemoteRelease'" | Select-Object -First 1)
    if ($releaseSize -notmatch '^([0-9]+)') { throw 'Taille de la version illisible.' }
    $maximumReleaseKib = [int64]$ResourceGates.maximum_release_disk_mib * 1024
    if ([int64]$Matches[1] -gt $maximumReleaseKib) {
        throw "Version installee au-dessus de $($ResourceGates.maximum_release_disk_mib) Mio."
    }

    $klipper = Get-KlipperPreflight
    if ($klipper.print_state -ne 'standby' -or -not $klipper.cfs.T1.connected -or -not $klipper.cfs.T2.connected) {
        throw 'Klipper ou un CFS a change pendant la pose.'
    }

    Save-Evidence 'listeners-after.txt' $listeners
    Save-Evidence 'memory-after.json' $memoryAfter
    Save-Evidence 'klipper-after.json' $klipper
}

if ($Action -eq 'Plan') {
    [pscustomobject]@{
        status = 'PLAN_ONLY'
        gate = $RequiredGate
        package_version = $Manifest.package_version
        printer_mutation_authorized = $false
        actions = @('InstallBootstrap', 'SetGatewayAccount', 'ActivateLan', 'Validate', 'Rollback')
    } | ConvertTo-Json -Depth 4
    exit 0
}

Assert-ExactGate

if ($Action -eq 'InstallBootstrap') {
    if (-not $CaptureId -or -not $Bundle -or -not $EvidenceDirectory) {
        throw 'InstallBootstrap exige -CaptureId, -Bundle et -EvidenceDirectory.'
    }
    $resolvedEvidence = Assert-LocalPathInsideWorkspace $EvidenceDirectory
    $resolvedBundle = Assert-Bundle
    $memoryBefore = Invoke-FoundationPreflight
    $transport = New-TransportArchive $resolvedBundle
    $transportHash = (Get-FileHash -LiteralPath $transport -Algorithm SHA256).Hash.ToLowerInvariant()
    Save-Evidence 'transport.sha256.txt' "$transportHash  k1-control-foundation-v3.tar.gz"

    $remoteBackup = "$RemoteRoot/backups/$CaptureId"
    $remoteStaging = "$RemoteRoot/staging/$CaptureId"
    try {
        $MutationStarted = $true
        Invoke-Remote "mkdir -p '$remoteBackup' '$remoteStaging' && printf 'ABSENT\n' > '$remoteBackup/root.before'" | Out-Null
        foreach ($marker in @('moonraker-service', 'gateway-service', 'current-link')) {
            Invoke-Remote "printf 'ABSENT\n' > '$remoteBackup/$marker.before'" | Out-Null
        }

        # Dropbear 2019.78 has no SFTP server. OpenSSH 9+ defaults scp to SFTP,
        # so force the classic SCP protocol for this exact, pinned target.
        & scp.exe -O -q -o BatchMode=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no `
            $transport "k1max-root`:$remoteStaging/k1-control-foundation-v3.tar.gz"
        if ($LASTEXITCODE -ne 0) { throw 'Transfert SCP KO.' }

        $remoteHashLine = Invoke-Remote "sha256sum '$remoteStaging/k1-control-foundation-v3.tar.gz'"
        $remoteHash = (($remoteHashLine | Select-Object -First 1) -split '\s+')[0]
        if ($remoteHash -ne $transportHash) { throw 'SHA-256 transport local/distant different.' }

        Invoke-Remote "mkdir -p '$remoteStaging/unpacked'" | Out-Null
        Invoke-Remote "tar -xzf '$remoteStaging/k1-control-foundation-v3.tar.gz' -C '$remoteStaging/unpacked'" | Out-Null
        Invoke-Remote "cd '$remoteStaging/unpacked' && sha256sum -c checksums.sha256" | Out-Null

        Invoke-Remote "mkdir -p '$RemoteRelease' '$RemoteRelease/www/mainsail' '$RemoteRoot/state' '$RemoteRoot/logs' '$RemoteRoot/tmp'" | Out-Null
        Invoke-Remote "tar -xzf '$remoteStaging/unpacked/artifacts/moonraker-mips-bundle.tar.gz' -C '$RemoteRelease'" | Out-Null
        Invoke-Remote "tar -xzf '$remoteStaging/unpacked/artifacts/nginx-mips-bundle.tar.gz' -C '$RemoteRelease'" | Out-Null
        Invoke-Remote "unzip -q '$remoteStaging/unpacked/artifacts/mainsail.zip' -d '$RemoteRelease/www/mainsail'" | Out-Null
        Invoke-Remote "cp -R '$remoteStaging/unpacked/config' '$RemoteRelease/config'" | Out-Null
        Invoke-Remote "chmod 0711 '$RemoteRoot' '$RemoteRoot/releases' '$RemoteRelease'" | Out-Null
        Invoke-Remote "find '$RemoteRelease/www' -type d -exec chmod 0755 {} \;" | Out-Null
        Invoke-Remote "find '$RemoteRelease/www' -type f -exec chmod 0644 {} \;" | Out-Null
        Invoke-Remote "cp '$RemoteRelease/config/nginx-bootstrap.conf' '$RemoteRoot/state/nginx-active.conf'" | Out-Null
        Invoke-Remote "ln -s '$RemoteRelease' '$RemoteCurrent'" | Out-Null
        Invoke-Remote "cp '$remoteStaging/unpacked/services/S56k1_control_moonraker' '$MoonrakerService'" | Out-Null
        Invoke-Remote "cp '$remoteStaging/unpacked/services/S57k1_control_gateway' '$GatewayService'" | Out-Null
        Invoke-Remote "chmod 0755 '$MoonrakerService' '$GatewayService'" | Out-Null

        Assert-RemoteFilesEqual "$remoteStaging/unpacked/config/moonraker.conf" "$RemoteRelease/config/moonraker.conf"
        Assert-RemoteFilesEqual "$remoteStaging/unpacked/config/nginx-bootstrap.conf" "$RemoteRelease/config/nginx-bootstrap.conf"
        Assert-RemoteFilesEqual "$remoteStaging/unpacked/config/nginx-bootstrap-auth.conf" "$RemoteRelease/config/nginx-bootstrap-auth.conf"
        Assert-RemoteFilesEqual "$remoteStaging/unpacked/config/nginx.conf" "$RemoteRelease/config/nginx.conf"
        Assert-RemoteFilesEqual "$remoteStaging/unpacked/services/S56k1_control_moonraker" $MoonrakerService
        Assert-RemoteFilesEqual "$remoteStaging/unpacked/services/S57k1_control_gateway" $GatewayService
        Invoke-Remote "test -x '$RemoteRelease/moonraker/moonraker-env/bin/python'" | Out-Null
        Invoke-Remote "test -f '$RemoteRelease/moonraker/moonraker/moonraker/moonraker.py'" | Out-Null
        Invoke-Remote "'$RemoteRelease/nginx/sbin/nginx' -g 'error_log stderr;' -t -c '$RemoteRoot/state/nginx-active.conf' -p '$RemoteRelease/nginx/nginx'" | Out-Null

        Invoke-Remote "'$MoonrakerService' start" | Out-Null
        Wait-RemoteCondition "test -s /var/run/k1-control-moonraker.pid && kill -0 `$(cat /var/run/k1-control-moonraker.pid) && netstat -lnt | grep -q '127.0.0.1:7125'" 'demarrage Moonraker'
        Invoke-Remote "'$GatewayService' start" | Out-Null
        Wait-RemoteCondition "test -s /var/run/k1-control-nginx.pid && kill -0 `$(cat /var/run/k1-control-nginx.pid) && netstat -lnt | grep -q '127.0.0.1:4409'" 'demarrage Mainsail' 5 1
        Invoke-FoundationValidation $memoryBefore
        Write-Output "INSTALL_BOOTSTRAP_OK capture=$CaptureId"
    }
    catch {
        if ($MutationStarted) { Invoke-FoundationRollback -BestEffort }
        throw
    }
    exit 0
}

if ($Action -eq 'SetGatewayAccount') {
    if (-not $CaptureId -or -not $EvidenceDirectory -or -not $GatewayUsername -or -not $GatewayPassword) {
        throw 'SetGatewayAccount exige -CaptureId, -EvidenceDirectory, -GatewayUsername et un mot de passe securise.'
    }
    $resolvedEvidence = Assert-LocalPathInsideWorkspace $EvidenceDirectory
    $gatewayActiveConfig = "$RemoteRoot/state/nginx-active.conf"
    $gatewayPreviousConfig = "$RemoteRoot/state/nginx-active.conf.previous"
    $gatewayNextConfig = "$RemoteRoot/state/nginx-active.conf.next"
    $passwordNext = "$GatewayPasswordFile.next"
    $secretPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($GatewayPassword)
    $plainPassword = $null
    try {
        $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPointer)
        $record = New-SshaPasswordRecord $GatewayUsername $plainPassword
        Assert-RemoteFilesEqual "$RemoteRelease/config/nginx-bootstrap.conf" $gatewayActiveConfig
        if (Invoke-RemoteTest "test -e '$GatewayPasswordFile'") {
            throw 'Un compte nginx existe deja : remplacement refuse.'
        }

        $MutationStarted = $true
        Invoke-RemoteWithInput `
            "umask 077; cat > '$passwordNext' && chmod 0600 '$passwordNext' && mv '$passwordNext' '$GatewayPasswordFile'" `
            $record | Out-Null
        if (-not (Invoke-RemoteTest "test -s '$GatewayPasswordFile' && test `$(wc -l < '$GatewayPasswordFile') -eq 1 && grep -Eq '^[A-Za-z0-9][A-Za-z0-9._-]{2,31}:\{SSHA\}[A-Za-z0-9+/=]+$' '$GatewayPasswordFile'")) {
            throw 'Fichier de compte nginx invalide.'
        }

        Invoke-Remote "cp '$gatewayActiveConfig' '$gatewayPreviousConfig'" | Out-Null
        Invoke-Remote "cp '$RemoteRelease/config/nginx-bootstrap-auth.conf' '$gatewayNextConfig'" | Out-Null
        Assert-RemoteFilesEqual "$RemoteRelease/config/nginx-bootstrap-auth.conf" $gatewayNextConfig
        Invoke-Remote "'$RemoteRelease/nginx/sbin/nginx' -g 'error_log stderr;' -t -c '$gatewayNextConfig' -p '$RemoteRelease/nginx/nginx'" | Out-Null
        Invoke-Remote "mv '$gatewayNextConfig' '$gatewayActiveConfig'" | Out-Null
        Invoke-Remote "'$GatewayService' reload" | Out-Null
        Wait-RemoteCondition "netstat -lnt | grep -q '127.0.0.1:4409'" 'activation du compte nginx en boucle locale' 5 1

        $credentialCheck = Test-GatewayCredential $GatewayUsername $plainPassword
        if ($credentialCheck.anonymous_status -ne 401 -or $credentialCheck.authenticated_status -ne 200) {
            throw 'Verification du compte nginx KO.'
        }
        Invoke-FoundationValidation -AuthExpected
        Save-Evidence 'gateway-authentication.txt' 'scheme=SSHA; anonymous_http=401; authenticated_http=200; exposure=loopback'
        Invoke-Remote "rm -f '$gatewayPreviousConfig'" | Out-Null
        Write-Output "SET_GATEWAY_ACCOUNT_OK username=$GatewayUsername"
    }
    catch {
        if ($MutationStarted) { Invoke-FoundationRollback -BestEffort }
        throw
    }
    finally {
        if ($secretPointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPointer)
        }
        $plainPassword = $null
    }
    exit 0
}

if ($Action -eq 'ActivateLan') {
    if (-not $CaptureId -or -not $EvidenceDirectory -or -not $AccountVerified) {
        throw 'ActivateLan exige -CaptureId, -EvidenceDirectory et -AccountVerified apres la connexion humaine.'
    }
    $resolvedEvidence = Assert-LocalPathInsideWorkspace $EvidenceDirectory
    $gatewayActiveConfig = "$RemoteRoot/state/nginx-active.conf"
    $gatewayPreviousConfig = "$RemoteRoot/state/nginx-active.conf.previous"
    $gatewayNextConfig = "$RemoteRoot/state/nginx-active.conf.next"
    try {
        if (-not (Invoke-RemoteTest "test -s '$GatewayPasswordFile' && test `$(wc -l < '$GatewayPasswordFile') -eq 1 && grep -Eq '^[A-Za-z0-9][A-Za-z0-9._-]{2,31}:\{SSHA\}[A-Za-z0-9+/=]+$' '$GatewayPasswordFile'")) {
            throw 'Compte nginx absent ou invalide : activation LAN refusee.'
        }
        Assert-RemoteFilesEqual "$RemoteRelease/config/nginx-bootstrap-auth.conf" $gatewayActiveConfig
        if ((Get-GatewayAnonymousStatus) -ne 401) {
            throw 'La protection nginx locale ne refuse pas les connexions anonymes.'
        }

        Invoke-Remote "cp '$gatewayActiveConfig' '$gatewayPreviousConfig'" | Out-Null
        Invoke-Remote "cp '$RemoteRelease/config/nginx.conf' '$gatewayNextConfig'" | Out-Null
        Assert-RemoteFilesEqual "$RemoteRelease/config/nginx.conf" $gatewayNextConfig
        Invoke-Remote "'$RemoteRelease/nginx/sbin/nginx' -g 'error_log stderr;' -t -c '$gatewayNextConfig' -p '$RemoteRelease/nginx/nginx'" | Out-Null
        Invoke-Remote "mv '$gatewayNextConfig' '$gatewayActiveConfig'" | Out-Null
        Invoke-Remote "'$GatewayService' reload" | Out-Null
        Wait-RemoteCondition "netstat -lnt | grep -q '0.0.0.0:4409'" 'ouverture Mainsail authentifie au LAN' 5 1
        Invoke-FoundationValidation -LanExpected -AuthExpected
        Invoke-Remote "rm -f '$gatewayPreviousConfig'" | Out-Null
    }
    catch {
        $activationError = $_
        try {
            if (Invoke-RemoteTest "test -f '$gatewayPreviousConfig'") {
                Invoke-Remote "mv '$gatewayPreviousConfig' '$gatewayActiveConfig'" | Out-Null
                Invoke-Remote "'$GatewayService' reload" | Out-Null
            }
        }
        catch { }
        try { Invoke-Remote "rm -f '$gatewayNextConfig'" | Out-Null }
        catch { }
        Invoke-FoundationRollback -BestEffort
        throw $activationError
    }
    Write-Output 'ACTIVATE_LAN_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    Invoke-FoundationValidation `
        -LanExpected:($Exposure -eq 'Lan') `
        -AuthExpected:($Exposure -ne 'Bootstrap')
    Write-Output 'VALIDATE_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    if (-not $CaptureId) { throw 'Rollback exige -CaptureId.' }
    Invoke-FoundationRollback
    Write-Output "ROLLBACK_OK capture=$CaptureId"
    exit 0
}
