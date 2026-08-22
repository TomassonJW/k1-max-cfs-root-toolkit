[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Prepare', 'Mesh1', 'Mesh2', 'CommitMesh', 'BeginZ', 'StepZ', 'AdjustZ', 'ConfirmGap', 'Accept', 'Cancel', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',

    [string]$Gate,

    [ValidatePattern('^[0-9]{8}-[0-9]{6}-g4-k1-control-first-calibration-v1$')]
    [string]$CaptureId,

    [string]$EvidenceDirectory,

    [ValidateSet('2', '1', '0.5', '0.3', '0.2', '0.15', '0.1')]
    [string]$Height,

    [ValidateSet('-0.1', '-0.05', '-0.01', '-0.005', '0.005', '0.01', '0.05', '0.1')]
    [string]$Delta,

    [switch]$ConfirmPlateClear,
    [switch]$ConfirmNozzleClean,
    [switch]$ConfirmGapObserved,
    [switch]$ConfirmAccept,
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'PowerShell 7 ou plus recent est obligatoire.'
}

$RequiredGate = 'G4-K1-CONTROL-FIRST-CALIBRATION-V1'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\first-calibration-v1'
$ContractPath = Join-Path $PackageRoot 'first-calibration-contract.json'
$CompareScript = Join-Path $PackageRoot 'compare_meshes.py'

$ExpectedContractHash = 'e3931e6e7597668f6b741f8085a92c94a0bc48a6e8bedbe314ec098b90717870'
$ExpectedCompareHash = '2014d9127ca951d2e1cbc96ce41a4e3462c28cf1eb0b6ee5fc5924afae7b1578'
$ExpectedPrinterHash = '0d59dd656844c3198ee43a81056b06830dbe60779d558b71aaa8c28fa708d9ee'
$ExpectedRuntimeConfigHash = 'dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113'
$ExpectedRuntimeModuleHash = '696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede'
$ExpectedCalibrationPathHash = '825aadac8679e0d0e9be140cc5ba4e7656b2bff0d197d1683a73d2b5be4e364e'

$PrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$RuntimeConfig = '/usr/data/printer_data/config/k1-control-z-mesh.cfg'
$RuntimeModule = '/usr/share/klipper/klippy/extras/k1_control_store.py'
$CalibrationPathConfig = '/usr/data/printer_data/config/k1-control-calibration-path.cfg'
$RuntimeState = '/usr/data/k1-control-v1/state/k1-control-z-state.json'
$RemoteRoot = '/usr/data/k1-control-v1'
$KlipperSocket = '/tmp/klippy_uds'
$MeshProfile = 'k1_p001_t055_r001_n06x06'
$MeshToleranceMm = 0.025
$EmptyFileHash = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'

$SshArguments = @(
    '-o', 'BatchMode=yes',
    '-o', 'PasswordAuthentication=no',
    '-o', 'KbdInteractiveAuthentication=no',
    '-o', 'ConnectTimeout=8',
    'k1max-root'
)

function Assert-ReviewedLocalFiles {
    foreach ($item in @(
            @{ Path = $ContractPath; Expected = $ExpectedContractHash; Label = 'contrat' },
            @{ Path = $CompareScript; Expected = $ExpectedCompareHash; Label = 'comparateur' }
        )) {
        $hash = (Get-FileHash -LiteralPath $item.Path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hash -ne $item.Expected) {
            throw "Fichier local non revu ($($item.Label)) : $hash"
        }
    }
}

function Assert-ExactGate {
    if (-not $Execute -or $Gate -cne $RequiredGate) {
        throw "Action bloquee : -Execute et -Gate '$RequiredGate' sont obligatoires."
    }
}

function Assert-EvidenceDirectory {
    if (-not $CaptureId -or -not $EvidenceDirectory) {
        throw 'Cette action exige -CaptureId et -EvidenceDirectory.'
    }
    $resolved = (Resolve-Path -LiteralPath $EvidenceDirectory -ErrorAction Stop).Path
    $expected = Join-Path $WorkspaceRoot "inventory\raw\$CaptureId"
    if (-not $resolved.Equals($expected, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Dossier de preuve inattendu : $resolved"
    }
    & git check-ignore -q -- $resolved
    if ($LASTEXITCODE -ne 0) {
        throw 'Le dossier de preuve prive ne serait pas ignore par Git.'
    }
    return $resolved
}

function Save-Evidence {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Value
    )
    $root = Assert-EvidenceDirectory
    $path = Join-Path $root $Name
    if ($Value -is [string]) {
        $Value | Set-Content -LiteralPath $path -Encoding utf8
    }
    else {
        $Value | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $path -Encoding utf8
    }
}

function Assert-Checkpoint {
    param([Parameter(Mandatory = $true)][string]$Name)
    $root = Assert-EvidenceDirectory
    $path = Join-Path $root $Name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Checkpoint local absent : $Name"
    }
    return $path
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

function Get-RemoteHash {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (((Invoke-Remote "sha256sum '$Path'" | Select-Object -First 1) -split '\s+')[0]).ToLowerInvariant()
}

function Get-ExactRemoteLineCount {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Line
    )
    $program = '$0 == "' + $Line + '" {count++} END {print count+0}'
    return [int]((Invoke-Remote "awk '$program' '$Path'" | Select-Object -First 1).Trim())
}

function Get-KlipperSnapshot {
    $python = @'
from __future__ import print_function
import json
import socket

objects = {
    "print_stats": ["state", "filename"],
    "extruder": ["target", "temperature"],
    "heater_bed": ["target", "temperature"],
    "toolhead": ["homed_axes", "position"],
    "gcode_move": ["homing_origin"],
    "bed_mesh": None,
    "box": None,
    "gcode_macro KCTRL_STATE": None,
    "k1_control_store": None,
    "gcode_macro KCTRL_CAL_PATH_STATE": None,
}
request = {"id": 5401, "method": "objects/query", "params": {"objects": objects}}
client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.settimeout(8)
client.connect("/tmp/klippy_uds")
client.sendall((json.dumps(request) + "\x03").encode("utf-8"))
data = b""
while b"\x03" not in data:
    chunk = client.recv(262144)
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
    $line = Invoke-Remote "echo '$payload' | base64 -d | /usr/share/klippy-env/bin/python"
    return (($line -join "`n") | ConvertFrom-Json)
}

function Wait-KlipperSnapshot {
    param([int]$Attempts = 90)
    $lastError = 'socket non encore disponible'
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $snapshot = Get-KlipperSnapshot
            if ($snapshot.print_stats) { return $snapshot }
        }
        catch { $lastError = $_.Exception.Message }
        if ($attempt -lt $Attempts) { Start-Sleep -Seconds 1 }
    }
    throw "Klipper non stabilise apres $Attempts tentatives : $lastError"
}

function Wait-MeshCommitRestart {
    param([int]$Attempts = 120)
    $lastState = 'restart non encore observe'
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $snapshot = Get-KlipperSnapshot
            $profiles = @($snapshot.bed_mesh.profiles.PSObject.Properties.Name)
            if ($snapshot.print_stats.state -eq 'standby' -and -not $snapshot.toolhead.homed_axes -and
                $profiles -contains $MeshProfile) {
                return $snapshot
            }
            $lastState = "state=$($snapshot.print_stats.state) homed=$($snapshot.toolhead.homed_axes) profile_present=$($profiles -contains $MeshProfile)"
        }
        catch { $lastState = $_.Exception.Message }
        if ($attempt -lt $Attempts) { Start-Sleep -Seconds 1 }
    }
    throw "Restart du commit mesh non stabilise apres $Attempts tentatives : $lastState"
}

function Wait-RollbackRestart {
    param([int]$Attempts = 120)
    $lastState = 'restart non encore observe'
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $snapshot = Get-KlipperSnapshot
            $profiles = @($snapshot.bed_mesh.profiles.PSObject.Properties.Name)
            $runtime = $snapshot.'gcode_macro KCTRL_STATE'
            $path = $snapshot.'gcode_macro KCTRL_CAL_PATH_STATE'
            if ($snapshot.print_stats.state -eq 'standby' -and -not $snapshot.toolhead.homed_axes -and
                $profiles -notcontains $MeshProfile -and $runtime.ready -eq 1 -and
                $runtime.accepted_z_valid -eq 0 -and $path.phase -eq 'idle') {
                return $snapshot
            }
            $lastState = "state=$($snapshot.print_stats.state) homed=$($snapshot.toolhead.homed_axes) profile_present=$($profiles -contains $MeshProfile) runtime_ready=$($runtime.ready) path=$($path.phase)"
        }
        catch { $lastState = $_.Exception.Message }
        if ($attempt -lt $Attempts) { Start-Sleep -Seconds 1 }
    }
    throw "Restart du rollback non stabilise apres $Attempts tentatives : $lastState"
}

function Test-ReviewedGcode {
    param([Parameter(Mandatory = $true)][string]$Script)
    $fixed = @(
        'KCTRL_CALIBRATION_PREHEAT BED_TEMP=55 NOZZLE_TEMP=140 SOAK_SECONDS=200',
        'NOZZLE_CLEAR HOT_MIN_TEMP=140 HOT_MAX_TEMP=180 BED_MAX_TEMP=55',
        'KCTRL_CALIBRATION_HOME',
        'KCTRL_MESH_CALIBRATE X_COUNT=6 Y_COUNT=6 ALGORITHM=lagrange',
        'KCTRL_MESH_COMMIT PLATE=1 TEMP_BAND=55 PROBE_REV=1 X_COUNT=6 Y_COUNT=6',
        'KCTRL_CAL_PATH_LOAD_MESH PLATE=1 TEMP_BAND=55 PROBE_REV=1 X_COUNT=6 Y_COUNT=6 BED_TEMP=55 NOZZLE_TEMP=140',
        'KCTRL_CAL_PATH_START_Z SEED=0.0 PLATE=1 TEMP_BAND=55 PROBE_REV=1 NOZZLE_ID=1 CONFIG_ID=1',
        'KCTRL_CAL_PATH_BEGIN CLEAR_PLATE=1 CLEAN_NOZZLE=1',
        'KCTRL_CAL_PATH_CONFIRM_GAP CONFIRMED=1',
        'KCTRL_CAL_PATH_PARK',
        'KCTRL_CAL_PATH_CANCEL_Z',
        'TURN_OFF_HEATERS',
        'RESTART'
    )
    if ($Script -in $fixed) { return $true }
    if ($Script -match '^KCTRL_CAL_PATH_MOVE HEIGHT=(2|1|0\.5|0\.3|0\.2|0\.15|0\.1)$') { return $true }
    if ($Script -match '^KCTRL_CAL_PATH_ADJUST DELTA=(-0\.1|-0\.05|-0\.01|-0\.005|0\.005|0\.01|0\.05|0\.1)$') { return $true }
    if ($Script -match '^KCTRL_CAL_PATH_COMMIT_Z ACCEPTED_AT=[1-9][0-9]{9}$') { return $true }
    return $false
}

function Invoke-KlipperScript {
    param(
        [Parameter(Mandatory = $true)][string]$Script,
        [switch]$NoResponse
    )
    if (-not (Test-ReviewedGcode $Script)) {
        throw "G-code hors liste revue : $Script"
    }
    $python = @'
from __future__ import print_function
import json
import socket
import sys
import time

script = sys.argv[1]
wait_response = sys.argv[2] == "1"
request = {"id": 5402, "method": "gcode/script", "params": {"script": script}}
client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.settimeout(1200)
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
    $response = (($line -join "`n") | ConvertFrom-Json)
    if ($response.error) {
        throw "Commande Klipper refusee : $($response.error | ConvertTo-Json -Compress)"
    }
    return $response
}

function Assert-CfsAndFoundation {
    param([Parameter(Mandatory = $true)]$Snapshot)
    foreach ($name in @('T1', 'T2')) {
        $unit = $Snapshot.box.$name
        if ($unit.state -ne 'connect' -or $unit.version -ne '1.1.3' -or @($unit.material_type).Count -ne 4) {
            throw "CFS $name inattendu ou deconnecte."
        }
    }
    $listeners = (Invoke-Remote 'netstat -lnt') -join "`n"
    foreach ($required in @('127.0.0.1:7125', '0.0.0.0:4409', '0.0.0.0:80', '0.0.0.0:8080', '0.0.0.0:9999')) {
        if ($listeners -notmatch [regex]::Escape($required)) { throw "Ecoute absente : $required" }
    }
    if ($listeners -match '0.0.0.0:7125') { throw 'Moonraker est expose directement au LAN.' }
    return $listeners
}

function Assert-InstalledHashes {
    if ((Get-RemoteHash $RuntimeConfig) -ne $ExpectedRuntimeConfigHash -or
        (Get-RemoteHash $RuntimeModule) -ne $ExpectedRuntimeModuleHash -or
        (Get-RemoteHash $CalibrationPathConfig) -ne $ExpectedCalibrationPathHash) {
        throw 'Runtime ou chemin de calibration different du lot installe et valide.'
    }
    if ((Get-ExactRemoteLineCount -Path $PrinterConfig -Line '[include k1-control-z-mesh.cfg]') -ne 1 -or
        (Get-ExactRemoteLineCount -Path $PrinterConfig -Line '[include k1-control-calibration-path.cfg]') -ne 1) {
        throw 'Inclusions K1 Control inattendues.'
    }
}

function Assert-Standby {
    param([Parameter(Mandatory = $true)]$Snapshot)
    if ($Snapshot.print_stats.state -ne 'standby' -or $Snapshot.print_stats.filename) {
        throw "Imprimante non disponible : $($Snapshot.print_stats.state)"
    }
}

function Assert-ThermalContext {
    param([Parameter(Mandatory = $true)]$Snapshot)
    if ([math]::Abs([double]$Snapshot.heater_bed.target - 55.0) -gt 0.1 -or
        [math]::Abs([double]$Snapshot.heater_bed.temperature - 55.0) -gt 2.0 -or
        [math]::Abs([double]$Snapshot.extruder.target - 140.0) -gt 0.1 -or
        [math]::Abs([double]$Snapshot.extruder.temperature - 140.0) -gt 5.0) {
        throw 'Contexte thermique hors des tolerances revues.'
    }
}

function Assert-EmptyRuntime {
    param([Parameter(Mandatory = $true)]$Snapshot)
    $runtime = $Snapshot.'gcode_macro KCTRL_STATE'
    $store = $Snapshot.k1_control_store
    if (-not $runtime -or [int]$runtime.ready -ne 1 -or [int]$runtime.accepted_z_valid -ne 0 -or
        [int]$runtime.session_active -ne 0 -or [int]$runtime.low_moves_armed -ne 0) {
        throw 'Runtime Z/mesh non vide ou non ferme.'
    }
    if (-not $store -or $store.integrity -ne 'empty' -or [int]$store.recovery_available -ne 0) {
        throw 'Stockage Z different de la base vide revue.'
    }
}

function Assert-IdlePath {
    param([Parameter(Mandatory = $true)]$Snapshot)
    $path = $Snapshot.'gcode_macro KCTRL_CAL_PATH_STATE'
    if (-not $path -or $path.phase -ne 'idle' -or [int]$path.ready -ne 0 -or
        [int]$path.mesh_ready -ne 0 -or [int]$path.motion_armed -ne 0 -or [int]$path.commit_ready -ne 0) {
        throw 'Chemin de calibration non ferme au depart.'
    }
}

function Invoke-FreshPreflight {
    Assert-ReviewedLocalFiles
    if (-not (Get-Command python.exe -ErrorAction SilentlyContinue)) {
        throw 'Python local absent pour la qualification des deux meshes.'
    }
    $architecture = (Invoke-Remote 'uname -m' | Select-Object -First 1).Trim()
    $board = (Invoke-Remote '/usr/bin/get_sn_mac.sh board' | Select-Object -First 1).Trim()
    $structure = (Invoke-Remote '/usr/bin/get_sn_mac.sh structure_version' | Select-Object -First 1).Trim()
    $version = (Invoke-Remote "grep '^ota_version=' /etc/ota_info" | Select-Object -First 1).Trim()
    if ($architecture -ne 'mips' -or $board -ne 'CR4CU220812S12' -or $structure -ne '0' -or $version -ne 'ota_version=2.3.5.34') {
        throw 'Identite machine ou firmware inattendue.'
    }
    Assert-InstalledHashes
    if ((Get-RemoteHash $PrinterConfig) -ne $ExpectedPrinterHash) {
        throw 'printer.cfg ne correspond pas a la base revue avant calibration.'
    }
    if (-not (Invoke-RemoteTest "test -S '$KlipperSocket'")) { throw 'Socket Klipper absent.' }
    foreach ($tool in @('awk', 'base64', 'cp', 'cut', 'grep', 'mkdir', 'mv', 'netstat', 'ps', 'rm', 'sha256sum', 'sync')) {
        if (-not (Invoke-RemoteTest "command -v '$tool'")) { throw "Outil distant absent : $tool" }
    }
    foreach ($path in @("$PrinterConfig.first-calibration-rollback", "$PrinterConfig.first-calibration-final")) {
        if (Invoke-RemoteTest "test -e '$path'") { throw "Transitoire de calibration deja present : $path" }
    }
    foreach ($path in @($RuntimeState, "$RuntimeState.previous", "$RuntimeState.tmp")) {
        if (Invoke-RemoteTest "test -e '$path'") { throw "Etat Z inattendu avant premiere calibration : $path" }
    }
    if ((Get-ExactRemoteLineCount -Path $PrinterConfig -Line "[bed_mesh $MeshProfile]") -ne 0) {
        throw 'Le profil mesh cible existe deja dans printer.cfg.'
    }
    $snapshot = Get-KlipperSnapshot
    Assert-Standby $snapshot
    if ([double]$snapshot.extruder.target -ne 0 -or [double]$snapshot.heater_bed.target -ne 0) {
        throw 'Une chauffe est deja demandee.'
    }
    if ($snapshot.toolhead.homed_axes) { throw "Axes deja homes : $($snapshot.toolhead.homed_axes)" }
    Assert-EmptyRuntime $snapshot
    Assert-IdlePath $snapshot
    if ($snapshot.bed_mesh.profiles.PSObject.Properties.Name -contains $MeshProfile) {
        throw 'Le profil mesh cible existe deja en memoire.'
    }
    $listeners = Assert-CfsAndFoundation $snapshot
    Save-Evidence 'preflight.json' $snapshot
    Save-Evidence 'preflight-listeners.txt' $listeners
    return $snapshot
}

function Get-RemoteBackupRoot {
    if (-not $CaptureId) { throw 'CaptureId absent.' }
    return "$RemoteRoot/backups/$CaptureId/first-calibration-v1"
}

function Assert-RemoteBackup {
    $backup = Get-RemoteBackupRoot
    foreach ($command in @(
            "test -f '$backup/printer.cfg.before'",
            "test -f '$backup/checksums.sha256'",
            "test -f '$backup/state-baseline-absent'",
            "cd '$backup' && sha256sum -c checksums.sha256"
        )) {
        Invoke-Remote $command | Out-Null
    }
    if ((Get-RemoteHash "$backup/printer.cfg.before") -ne $ExpectedPrinterHash) {
        throw 'Backup printer.cfg inattendu.'
    }
    if ((Get-RemoteHash "$backup/state-baseline-absent") -ne $EmptyFileHash) {
        throw 'Marqueur de base Z absente inattendu.'
    }
    return $backup
}

function New-RemoteBackup {
    $backup = Get-RemoteBackupRoot
    Invoke-Remote "test ! -e '$backup' && mkdir -p '$backup'" | Out-Null
    Invoke-Remote "cp '$PrinterConfig' '$backup/printer.cfg.before'" | Out-Null
    $hash = Get-RemoteHash "$backup/printer.cfg.before"
    if ($hash -ne $ExpectedPrinterHash) { throw 'Backup printer.cfg different de la base revue.' }
    Invoke-Remote "test ! -e '$RuntimeState' && test ! -e '$RuntimeState.previous' && test ! -e '$RuntimeState.tmp' && : > '$backup/state-baseline-absent'" | Out-Null
    $checksum = "$hash  printer.cfg.before`n$EmptyFileHash  state-baseline-absent"
    $payload = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$checksum`n"))
    Invoke-Remote "echo '$payload' | base64 -d > '$backup/checksums.sha256'" | Out-Null
    Invoke-Remote "cd '$backup' && sha256sum -c checksums.sha256" | Out-Null
    Save-Evidence 'remote-backup-sha256.txt' $checksum
    return $backup
}

function Assert-PreparedSnapshot {
    param([Parameter(Mandatory = $true)]$Snapshot)
    Assert-Standby $Snapshot
    Assert-ThermalContext $Snapshot
    if ($Snapshot.toolhead.homed_axes -ne 'xyz') { throw 'Les axes XYZ ne sont pas homes.' }
    Assert-EmptyRuntime $Snapshot
    Assert-CfsAndFoundation $Snapshot | Out-Null
}

function Assert-TransientMesh {
    param([Parameter(Mandatory = $true)]$Snapshot)
    Assert-PreparedSnapshot $Snapshot
    if ($Snapshot.bed_mesh.profile_name -ne 'K1_TRANSIENT') { throw 'Le mesh transitoire attendu n est pas actif.' }
    $matrix = @($Snapshot.bed_mesh.probed_matrix)
    if ($matrix.Count -ne 6) { throw 'Le mesh mesure ne contient pas 6 lignes.' }
    foreach ($row in $matrix) {
        if (@($row).Count -ne 6) { throw 'Le mesh mesure ne contient pas 6 colonnes.' }
    }
    $meshMin = @($Snapshot.bed_mesh.mesh_min)
    $meshMax = @($Snapshot.bed_mesh.mesh_max)
    if ($meshMin.Count -ne 2 -or $meshMax.Count -ne 2 -or
        [double]$meshMin[0] -ne 5.0 -or [double]$meshMin[1] -ne 5.0 -or
        [double]$meshMax[0] -ne 295.0 -or [double]$meshMax[1] -ne 295.0) {
        throw 'La zone du mesh mesure differe de 5-295 mm.'
    }
}

function Invoke-TurnOffHeatersBestEffort {
    try { Invoke-KlipperScript 'TURN_OFF_HEATERS' | Out-Null } catch { Write-Warning $_ }
}

function Assert-QualifiedEvidence {
    $path = Assert-Checkpoint 'mesh-qualification.json'
    $qualification = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
    if (-not $qualification.accepted -or [double]$qualification.tolerance_mm -ne $MeshToleranceMm -or
        [int]$qualification.compared_points -ne 36 -or [double]$qualification.maximum_delta_mm -gt $MeshToleranceMm) {
        throw 'La qualification locale des deux meshes n est pas acceptee.'
    }
    return $qualification
}

function Assert-AcceptedState {
    param([Parameter(Mandatory = $true)]$Snapshot)
    Assert-Standby $Snapshot
    $runtime = $Snapshot.'gcode_macro KCTRL_STATE'
    $store = $Snapshot.k1_control_store
    $path = $Snapshot.'gcode_macro KCTRL_CAL_PATH_STATE'
    if ([int]$runtime.ready -ne 1 -or [int]$runtime.accepted_z_valid -ne 1 -or [int]$runtime.session_active -ne 0 -or
        [int]$runtime.plate_id -ne 1 -or [int]$runtime.temperature_band_c -ne 55 -or [int]$runtime.probe_revision -ne 1 -or
        [int]$runtime.nozzle_id -ne 1 -or [int]$runtime.config_id -ne 1 -or [int]$runtime.low_moves_armed -ne 0) {
        throw 'Etat Z accepte incomplet ou contexte inattendu.'
    }
    if ($store.integrity -ne 'ok' -or [int]$store.record[1] -ne 1 -or [int]$store.recovery_available -ne 0) {
        throw 'Stockage Z accepte invalide.'
    }
    if ($path.phase -ne 'committed' -or [int]$path.motion_armed -ne 0 -or [int]$path.commit_ready -ne 0) {
        throw 'Chemin Z non ferme apres acceptation.'
    }
    if ($Snapshot.bed_mesh.profiles.PSObject.Properties.Name -notcontains $MeshProfile) {
        throw 'Profil mesh qualifie absent apres acceptation.'
    }
}

if ($Action -eq 'Plan') {
    Assert-ReviewedLocalFiles
    [pscustomobject]@{
        status = 'PLAN_ONLY'
        gate = $RequiredGate
        printer_mutation_authorized = $false
        plate = 'PEI_TEXTURED_A (id=1)'
        temperatures_c = @{ bed = 55; nozzle = 140; cleaning_max = 180 }
        soak_seconds = 200
        mesh = 'two 6x6 Lagrange measurements over 5-295 mm'
        tolerance_mm = $MeshToleranceMm
        automatic_rerun = $false
        z_ladder_mm = @(5, 2, 1, 0.5, 0.3, 0.2, 0.15, 0.1)
        rollback = 'restore exact printer.cfg and empty Z store; preserve installed runtime and calibration path'
        calibration_started = $false
    } | ConvertTo-Json -Depth 6
    exit 0
}

Assert-ReviewedLocalFiles
Assert-ExactGate
[void](Assert-EvidenceDirectory)

if ($Action -eq 'Preflight') {
    Invoke-FreshPreflight | Out-Null
    Write-Output 'PREFLIGHT_FIRST_CALIBRATION_V1_OK'
    exit 0
}

if ($Action -eq 'Prepare') {
    if (-not $ConfirmPlateClear) { throw 'Prepare exige -ConfirmPlateClear.' }
    Invoke-FreshPreflight | Out-Null
    [void](New-RemoteBackup)
    try {
        Invoke-KlipperScript 'KCTRL_CALIBRATION_PREHEAT BED_TEMP=55 NOZZLE_TEMP=140 SOAK_SECONDS=200' | Out-Null
        Invoke-KlipperScript 'NOZZLE_CLEAR HOT_MIN_TEMP=140 HOT_MAX_TEMP=180 BED_MAX_TEMP=55' | Out-Null
        Invoke-KlipperScript 'KCTRL_CALIBRATION_HOME' | Out-Null
        $snapshot = Get-KlipperSnapshot
        Assert-PreparedSnapshot $snapshot
        Save-Evidence 'prepare.json' $snapshot
        Write-Output "PREPARE_FIRST_CALIBRATION_V1_OK capture=$CaptureId"
    }
    catch {
        Invoke-TurnOffHeatersBestEffort
        throw
    }
    exit 0
}

if ($Action -eq 'Mesh1') {
    [void](Assert-Checkpoint 'prepare.json')
    [void](Assert-RemoteBackup)
    try {
        $before = Get-KlipperSnapshot
        Assert-PreparedSnapshot $before
        Invoke-KlipperScript 'KCTRL_MESH_CALIBRATE X_COUNT=6 Y_COUNT=6 ALGORITHM=lagrange' | Out-Null
        $snapshot = Get-KlipperSnapshot
        Assert-TransientMesh $snapshot
        Save-Evidence 'mesh-1.json' $snapshot
        Write-Output "MESH1_FIRST_CALIBRATION_V1_OK capture=$CaptureId"
    }
    catch {
        Invoke-TurnOffHeatersBestEffort
        throw
    }
    exit 0
}

if ($Action -eq 'Mesh2') {
    $mesh1 = Assert-Checkpoint 'mesh-1.json'
    [void](Assert-RemoteBackup)
    try {
        $before = Get-KlipperSnapshot
        Assert-TransientMesh $before
        Invoke-KlipperScript 'KCTRL_MESH_CALIBRATE X_COUNT=6 Y_COUNT=6 ALGORITHM=lagrange' | Out-Null
        $snapshot = Get-KlipperSnapshot
        Assert-TransientMesh $snapshot
        Save-Evidence 'mesh-2.json' $snapshot
        $mesh2 = Assert-Checkpoint 'mesh-2.json'
        $comparison = & python.exe $CompareScript $mesh1 $mesh2 --tolerance-mm $MeshToleranceMm 2>&1
        $comparisonCode = $LASTEXITCODE
        if ($comparisonCode -notin @(0, 2)) { throw "Comparateur mesh KO ($comparisonCode) : $comparison" }
        Save-Evidence 'mesh-qualification.json' ($comparison -join "`n")
        if ($comparisonCode -eq 2) {
            Invoke-TurnOffHeatersBestEffort
            throw 'MESH2_FIRST_CALIBRATION_V1_KO : ecart superieur a 0,025 mm ; aucun rerun automatique.'
        }
        [void](Assert-QualifiedEvidence)
        Write-Output "MESH2_FIRST_CALIBRATION_V1_OK capture=$CaptureId"
    }
    catch {
        Invoke-TurnOffHeatersBestEffort
        throw
    }
    exit 0
}

if ($Action -eq 'CommitMesh') {
    [void](Assert-QualifiedEvidence)
    [void](Assert-RemoteBackup)
    $mesh2Path = Assert-Checkpoint 'mesh-2.json'
    $mesh2 = Get-Content -Raw -LiteralPath $mesh2Path | ConvertFrom-Json
    $snapshot = Get-KlipperSnapshot
    Assert-TransientMesh $snapshot
    if (($snapshot.bed_mesh.probed_matrix | ConvertTo-Json -Compress) -ne ($mesh2.bed_mesh.probed_matrix | ConvertTo-Json -Compress)) {
        throw 'Le mesh transitoire actif ne correspond plus au second mesh qualifie.'
    }
    Invoke-KlipperScript 'KCTRL_MESH_COMMIT PLATE=1 TEMP_BAND=55 PROBE_REV=1 X_COUNT=6 Y_COUNT=6' -NoResponse | Out-Null
    $after = Wait-MeshCommitRestart -Attempts 120
    Assert-Standby $after
    Assert-InstalledHashes
    Assert-EmptyRuntime $after
    if ($after.bed_mesh.profiles.PSObject.Properties.Name -notcontains $MeshProfile) {
        throw 'Profil mesh qualifie absent apres SAVE_CONFIG.'
    }
    Save-Evidence 'mesh-commit.json' $after
    Save-Evidence 'mesh-commit-printer-sha256.txt' (Get-RemoteHash $PrinterConfig)
    Write-Output "COMMIT_MESH_FIRST_CALIBRATION_V1_OK capture=$CaptureId"
    exit 0
}

if ($Action -eq 'BeginZ') {
    if (-not $ConfirmPlateClear -or -not $ConfirmNozzleClean) {
        throw 'BeginZ exige -ConfirmPlateClear et -ConfirmNozzleClean.'
    }
    [void](Assert-Checkpoint 'mesh-commit.json')
    [void](Assert-QualifiedEvidence)
    [void](Assert-RemoteBackup)
    $snapshot = Get-KlipperSnapshot
    Assert-Standby $snapshot
    Assert-EmptyRuntime $snapshot
    if ($snapshot.bed_mesh.profiles.PSObject.Properties.Name -notcontains $MeshProfile) {
        throw 'Profil qualifie absent avant la session Z.'
    }
    try {
        Invoke-KlipperScript 'KCTRL_CALIBRATION_PREHEAT BED_TEMP=55 NOZZLE_TEMP=140 SOAK_SECONDS=200' | Out-Null
        Invoke-KlipperScript 'KCTRL_CALIBRATION_HOME' | Out-Null
        Invoke-KlipperScript 'KCTRL_CAL_PATH_LOAD_MESH PLATE=1 TEMP_BAND=55 PROBE_REV=1 X_COUNT=6 Y_COUNT=6 BED_TEMP=55 NOZZLE_TEMP=140' | Out-Null
        Invoke-KlipperScript 'KCTRL_CAL_PATH_START_Z SEED=0.0 PLATE=1 TEMP_BAND=55 PROBE_REV=1 NOZZLE_ID=1 CONFIG_ID=1' | Out-Null
        Invoke-KlipperScript 'KCTRL_CAL_PATH_BEGIN CLEAR_PLATE=1 CLEAN_NOZZLE=1' | Out-Null
        $after = Get-KlipperSnapshot
        $path = $after.'gcode_macro KCTRL_CAL_PATH_STATE'
        $runtime = $after.'gcode_macro KCTRL_STATE'
        Assert-ThermalContext $after
        if ($path.phase -ne 'testing' -or [int]$path.motion_armed -ne 1 -or [double]$path.current_height_mm -ne 5.0 -or [int]$runtime.session_active -ne 1) {
            throw 'Session Z bornee non armee a 5 mm.'
        }
        Save-Evidence 'z-begin.json' $after
        Write-Output "BEGIN_Z_FIRST_CALIBRATION_V1_OK capture=$CaptureId"
    }
    catch {
        Invoke-TurnOffHeatersBestEffort
        throw
    }
    exit 0
}

if ($Action -eq 'StepZ') {
    if (-not $Height) { throw 'StepZ exige -Height.' }
    [void](Assert-Checkpoint 'z-begin.json')
    [void](Assert-RemoteBackup)
    Invoke-KlipperScript "KCTRL_CAL_PATH_MOVE HEIGHT=$Height" | Out-Null
    $snapshot = Get-KlipperSnapshot
    $path = $snapshot.'gcode_macro KCTRL_CAL_PATH_STATE'
    if ($path.phase -ne 'testing' -or [int]$path.motion_armed -ne 1 -or [double]$path.current_height_mm -ne [double]$Height) {
        throw "Checkpoint Z inattendu apres la hauteur $Height."
    }
    Save-Evidence ("z-step-{0}.json" -f $Height.Replace('.', '_')) $snapshot
    Write-Output "STEP_Z_FIRST_CALIBRATION_V1_OK height=$Height capture=$CaptureId"
    exit 0
}

if ($Action -eq 'AdjustZ') {
    if (-not $Delta) { throw 'AdjustZ exige -Delta.' }
    [void](Assert-Checkpoint 'z-step-0_1.json')
    [void](Assert-RemoteBackup)
    Invoke-KlipperScript "KCTRL_CAL_PATH_ADJUST DELTA=$Delta" | Out-Null
    $snapshot = Get-KlipperSnapshot
    $path = $snapshot.'gcode_macro KCTRL_CAL_PATH_STATE'
    if ($path.phase -ne 'testing' -or [int]$path.motion_armed -ne 1 -or [double]$path.current_height_mm -ne 0.1) {
        throw 'Ajustement Z sorti du chemin borne.'
    }
    $stamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    Save-Evidence "z-adjust-$stamp.json" $snapshot
    Write-Output "ADJUST_Z_FIRST_CALIBRATION_V1_OK delta=$Delta capture=$CaptureId"
    exit 0
}

if ($Action -eq 'ConfirmGap') {
    if (-not $ConfirmGapObserved) { throw 'ConfirmGap exige -ConfirmGapObserved.' }
    [void](Assert-Checkpoint 'z-step-0_1.json')
    [void](Assert-RemoteBackup)
    Invoke-KlipperScript 'KCTRL_CAL_PATH_CONFIRM_GAP CONFIRMED=1' | Out-Null
    Invoke-KlipperScript 'KCTRL_CAL_PATH_PARK' | Out-Null
    $snapshot = Get-KlipperSnapshot
    $path = $snapshot.'gcode_macro KCTRL_CAL_PATH_STATE'
    if ($path.phase -ne 'parked_confirmed' -or [int]$path.motion_armed -ne 0 -or [int]$path.commit_ready -ne 1) {
        throw 'Confirmation du jeu ou remontée de securite incomplete.'
    }
    Save-Evidence 'z-gap-confirmed-and-parked.json' $snapshot
    Write-Output "CONFIRM_GAP_FIRST_CALIBRATION_V1_OK capture=$CaptureId"
    exit 0
}

if ($Action -eq 'Accept') {
    if (-not $ConfirmAccept) { throw 'Accept exige -ConfirmAccept.' }
    [void](Assert-Checkpoint 'z-gap-confirmed-and-parked.json')
    [void](Assert-RemoteBackup)
    $acceptedAt = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    Invoke-KlipperScript "KCTRL_CAL_PATH_COMMIT_Z ACCEPTED_AT=$acceptedAt" | Out-Null
    Invoke-KlipperScript 'TURN_OFF_HEATERS' | Out-Null
    $snapshot = Get-KlipperSnapshot
    Assert-AcceptedState $snapshot
    if ([double]$snapshot.extruder.target -ne 0 -or [double]$snapshot.heater_bed.target -ne 0) {
        throw 'Les chauffes ne sont pas coupees apres acceptation.'
    }
    Save-Evidence 'accepted.json' $snapshot
    Save-Evidence 'accepted-printer-sha256.txt' (Get-RemoteHash $PrinterConfig)
    Write-Output "ACCEPT_FIRST_CALIBRATION_V1_OK accepted_at=$acceptedAt capture=$CaptureId"
    exit 0
}

if ($Action -eq 'Cancel') {
    [void](Assert-RemoteBackup)
    $snapshot = Get-KlipperSnapshot
    $path = $snapshot.'gcode_macro KCTRL_CAL_PATH_STATE'
    $runtime = $snapshot.'gcode_macro KCTRL_STATE'
    if ([int]$path.motion_armed -eq 1) { Invoke-KlipperScript 'KCTRL_CAL_PATH_PARK' | Out-Null }
    if ([int]$runtime.session_active -eq 1) { Invoke-KlipperScript 'KCTRL_CAL_PATH_CANCEL_Z' | Out-Null }
    Invoke-KlipperScript 'TURN_OFF_HEATERS' | Out-Null
    $after = Get-KlipperSnapshot
    if ([int]$after.'gcode_macro KCTRL_STATE'.accepted_z_valid -ne 0 -or [int]$after.'gcode_macro KCTRL_STATE'.session_active -ne 0 -or
        [int]$after.'gcode_macro KCTRL_CAL_PATH_STATE'.motion_armed -ne 0) {
        throw 'Annulation Z incomplete.'
    }
    Save-Evidence 'cancelled.json' $after
    Write-Output "CANCEL_FIRST_CALIBRATION_V1_OK capture=$CaptureId"
    exit 0
}

if ($Action -eq 'Validate') {
    [void](Assert-Checkpoint 'accepted.json')
    [void](Assert-RemoteBackup)
    Assert-InstalledHashes
    $snapshot = Get-KlipperSnapshot
    Assert-AcceptedState $snapshot
    if ([double]$snapshot.extruder.target -ne 0 -or [double]$snapshot.heater_bed.target -ne 0) {
        throw 'Une chauffe reste demandee pendant la validation.'
    }
    if ((Get-ExactRemoteLineCount -Path $PrinterConfig -Line "[bed_mesh $MeshProfile]") -ne 1) {
        throw 'Section persistante du mesh qualifie absente ou dupliquee.'
    }
    $listeners = Assert-CfsAndFoundation $snapshot
    Save-Evidence 'validation.json' $snapshot
    Save-Evidence 'validation-listeners.txt' $listeners
    Save-Evidence 'validation-printer-sha256.txt' (Get-RemoteHash $PrinterConfig)
    Write-Output 'VALIDATE_FIRST_CALIBRATION_V1_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    $backup = Assert-RemoteBackup
    $snapshot = Get-KlipperSnapshot
    $path = $snapshot.'gcode_macro KCTRL_CAL_PATH_STATE'
    $runtime = $snapshot.'gcode_macro KCTRL_STATE'
    if ([int]$path.motion_armed -eq 1) { Invoke-KlipperScript 'KCTRL_CAL_PATH_PARK' | Out-Null }
    if ([int]$runtime.session_active -eq 1) { Invoke-KlipperScript 'KCTRL_CAL_PATH_CANCEL_Z' | Out-Null }
    Invoke-KlipperScript 'TURN_OFF_HEATERS' | Out-Null
    Invoke-Remote "cp '$backup/printer.cfg.before' '$PrinterConfig.first-calibration-rollback'" | Out-Null
    if ((Get-RemoteHash "$PrinterConfig.first-calibration-rollback") -ne $ExpectedPrinterHash) {
        throw 'Copie de rollback printer.cfg differente du backup.'
    }
    Invoke-Remote "mv '$PrinterConfig.first-calibration-rollback' '$PrinterConfig'" | Out-Null
    Invoke-Remote "rm -f '$RuntimeState' '$RuntimeState.previous' '$RuntimeState.tmp'" | Out-Null
    Invoke-Remote 'sync' | Out-Null
    Invoke-KlipperScript 'RESTART' -NoResponse | Out-Null
    $after = Wait-RollbackRestart -Attempts 120
    Assert-Standby $after
    Assert-InstalledHashes
    Assert-EmptyRuntime $after
    Assert-IdlePath $after
    if ($after.toolhead.homed_axes) { throw 'Les axes restent homes apres rollback.' }
    if ([double]$after.extruder.target -ne 0 -or [double]$after.heater_bed.target -ne 0) {
        throw 'Une chauffe reste demandee apres rollback.'
    }
    if ($after.bed_mesh.profiles.PSObject.Properties.Name -contains $MeshProfile) {
        throw 'Le profil mesh qualifie subsiste apres rollback.'
    }
    Start-Sleep -Seconds 5
    Invoke-Remote "cp '$backup/printer.cfg.before' '$PrinterConfig.first-calibration-final'" | Out-Null
    if ((Get-RemoteHash "$PrinterConfig.first-calibration-final") -ne $ExpectedPrinterHash) {
        throw 'Restauration finale printer.cfg differente du backup.'
    }
    Invoke-Remote "mv '$PrinterConfig.first-calibration-final' '$PrinterConfig'" | Out-Null
    Invoke-Remote 'sync' | Out-Null
    Start-Sleep -Seconds 3
    if ((Get-RemoteHash $PrinterConfig) -ne $ExpectedPrinterHash) { throw 'Rollback printer.cfg incomplet.' }
    Save-Evidence 'rollback.json' $after
    Write-Output "ROLLBACK_FIRST_CALIBRATION_V1_OK capture=$CaptureId"
    exit 0
}
