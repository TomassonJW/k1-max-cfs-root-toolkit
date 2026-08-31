[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$Gate = '',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-integrated-production-cycle-v1',
    [string]$EvidenceDirectory = '',
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 ou plus recent est obligatoire.' }

$RequiredGate = 'G4-K1-CONTROL-INTEGRATED-PRODUCTION-CYCLE-V1'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\integrated-production-cycle-v1'
$ManifestPath = Join-Path $PackageRoot 'deployment-manifest.json'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteCurrent = "$RemoteRoot/current"
$PrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$MacroConfig = '/usr/data/printer_data/config/k1-control-integrated-production-cycle-v1.cfg'
$MoonrakerConfig = "$RemoteCurrent/config/moonraker.conf"
$RemoteComponents = "$RemoteCurrent/moonraker/moonraker/moonraker/components"
$RemoteUi = "$RemoteCurrent/www/mainsail/k1-control"
$RemoteCalibrationUi = "$RemoteUi/calibration"
$RemoteGcode = '/usr/data/printer_data/gcodes/K1-INTEGRATED-T1A-2LAYER.gcode'
$MoonrakerService = '/etc/init.d/S56k1_control_moonraker'
$RemoteBackup = "$RemoteRoot/backups/$CaptureId-integrated-production-cycle-v1"
$RemoteStaging = "$RemoteRoot/tmp/$CaptureId-integrated-production-cycle-v1"
$MutationStarted = $false

if (-not $EvidenceDirectory) {
    $EvidenceDirectory = Join-Path $WorkspaceRoot "inventory\raw\$CaptureId"
}

$SshArguments = @(
    '-o', 'BatchMode=yes',
    '-o', 'PasswordAuthentication=no',
    '-o', 'KbdInteractiveAuthentication=no',
    '-o', 'ConnectTimeout=8',
    $PrinterHost
)

function Assert-MutationGate {
    if (-not $Execute -or $Gate -cne $RequiredGate) {
        throw "Action bloquee : -Execute et -Gate '$RequiredGate' sont obligatoires."
    }
}

function Get-LocalHash {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Invoke-Remote {
    param([Parameter(Mandatory = $true)][string]$Command)
    $output = & ssh.exe @SshArguments $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Commande distante KO : $Command`n$($output -join "`n")"
    }
    return @($output)
}

function Invoke-RemoteStdin {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string]$InputText
    )
    $output = $InputText | & ssh.exe @SshArguments $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Programme distant KO : $Command`n$($output -join "`n")"
    }
    return @($output)
}

function Copy-ToRemote {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $arguments = @(
        '-O', '-o', 'BatchMode=yes', '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no', '-o', 'ConnectTimeout=8',
        (Resolve-Path -LiteralPath $Source).Path,
        "$PrinterHost`:$Destination"
    )
    & scp.exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Transfert SCP KO : $Destination" }
}

function Get-RemoteHash {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (((Invoke-Remote "sha256sum '$Path'" | Select-Object -First 1) -split '\s+')[0]).ToLowerInvariant()
}

function Save-Evidence {
    param([Parameter(Mandatory = $true)][string]$Name, [Parameter(Mandatory = $true)]$Value)
    New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null
    if ($Value -is [string]) {
        [IO.File]::WriteAllText((Join-Path $EvidenceDirectory $Name), $Value, (New-Object Text.UTF8Encoding($false)))
    }
    else {
        $Value | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $EvidenceDirectory $Name) -Encoding utf8NoBOM
    }
}

function Assert-Package {
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ($manifest.gate -cne $RequiredGate -or $manifest.status -cne 'offline_review_candidate') {
        throw 'Manifeste du cycle integre inattendu.'
    }
    foreach ($file in @($manifest.files) + @($manifest.support_files)) {
        $local = Join-Path $PackageRoot ([string]$file.source)
        if ((Get-LocalHash $local) -cne ([string]$file.sha256)) {
            throw "Empreinte locale inattendue : $($file.source)"
        }
    }
    if ((Get-LocalHash $PSCommandPath) -cne ([string]$manifest.deployer_sha256)) {
        throw 'Empreinte du deployeur inattendue.'
    }
    return $manifest
}

function Get-PrinterStatus {
    $url = "http://127.0.0.1:7125/printer/objects/query?webhooks=state,state_message&print_stats=state,filename&extruder=temperature,target&heater_bed=temperature,target&toolhead=homed_axes,position&gcode_move=homing_origin&bed_mesh=profile_name&box&filament_switch_sensor+filament_sensor=enabled,filament_detected&filament_switch_sensor+filament_sensor_2=enabled,filament_detected&gcode_macro+KCTRL_STATE&gcode_macro+KCTRL_START_OWNER_STATE&gcode_macro+KCTRL_CYCLE_STATE"
    $raw = (Invoke-Remote "curl '$url'") -join "`n"
    $payload = $raw | ConvertFrom-Json
    if (-not $payload.result.status) { throw 'Etat Klipper absent.' }
    return $payload.result.status
}

function Get-SafeProjection {
    param([Parameter(Mandatory = $true)]$Status)
    $box = $Status.box
    return [ordered]@{
        webhooks_state = $Status.webhooks.state
        print_state = $Status.print_stats.state
        print_filename = $Status.print_stats.filename
        nozzle_target_c = [double]$Status.extruder.target
        bed_target_c = [double]$Status.heater_bed.target
        homed_axes = $Status.toolhead.homed_axes
        position = @($Status.toolhead.position)
        homing_origin = @($Status.gcode_move.homing_origin)
        mesh_profile = $Status.bed_mesh.profile_name
        cfs_state = $box.state
        cfs_command = $box.t_command
        connected_units = @('T1','T2' | Where-Object { $box.$_.state -eq 'connect' })
        routes = @('T1','T2' | ForEach-Object { if ($box.$_.filament -in @('A','B','C','D')) { "$_$($box.$_.filament)" } })
        head_sensor = [bool]$Status.'filament_switch_sensor filament_sensor'.filament_detected
        after_cutter_sensor = [bool]$Status.'filament_switch_sensor filament_sensor_2'.filament_detected
        accepted_z_valid = [int]$Status.'gcode_macro KCTRL_STATE'.accepted_z_valid
        accepted_z_offset = [double]$Status.'gcode_macro KCTRL_STATE'.accepted_z_offset
        start_owner_phase = $Status.'gcode_macro KCTRL_START_OWNER_STATE'.phase
        cycle_phase = if ($Status.'gcode_macro KCTRL_CYCLE_STATE') { $Status.'gcode_macro KCTRL_CYCLE_STATE'.phase } else { 'absent' }
        identity_values_exported = $false
    }
}

function Assert-SafeState {
    param([Parameter(Mandatory = $true)]$Status, [switch]$AfterDeploy)
    if ($Status.webhooks.state -cne 'ready' -or $Status.print_stats.state -cne 'standby' -or $Status.print_stats.filename) {
        throw "K1 non disponible : $($Status.print_stats.state)"
    }
    if ([double]$Status.extruder.target -ne 0 -or [double]$Status.heater_bed.target -ne 0) {
        throw 'Une chauffe est demandee.'
    }
    if ($Status.box.state -cne 'connect' -or $Status.box.t_command -cne '' -or
        $Status.box.T1.state -cne 'connect' -or $Status.box.T2.state -cne 'connect') {
        throw 'Les deux CFS ne sont pas stables.'
    }
    if ($Status.bed_mesh.profile_name -cne 'k1_p001_t055_r001_n11x11') { throw 'Le 11x11 actif est absent.' }
    if ([int]$Status.'gcode_macro KCTRL_STATE'.accepted_z_valid -ne 1 -or
        [math]::Abs([double]$Status.'gcode_macro KCTRL_STATE'.accepted_z_offset + 0.04) -gt 0.0005) {
        throw 'Le Z accepte -0,04 mm est absent.'
    }
    if ($Status.'gcode_macro KCTRL_START_OWNER_STATE'.phase -cne 'idle') { throw 'R4 n est pas au repos.' }
    if ($AfterDeploy -and $Status.'gcode_macro KCTRL_CYCLE_STATE'.phase -cne 'idle') { throw 'Le cycle integre n est pas au repos.' }
}

function Assert-RemotePython {
    $sources = [ordered]@{
        'moonraker.components.k1_control_cycle_core' = 'cycle.py'
        'moonraker.components.k1_control_cycle_job_contract' = 'job_contract.py'
        'moonraker.components.k1_control_cycle_orchestrator' = 'orchestrator.py'
        'moonraker.components.k1_control_cycle' = 'moonraker_component.py'
    }
    $payload = [ordered]@{}
    foreach ($item in $sources.GetEnumerator()) {
        $payload[$item.Key] = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $PackageRoot $item.Value)))
    }
    $json = ($payload | ConvertTo-Json -Compress)
    $program = @"
import base64, json, sys, types
sys.path.insert(0, '$RemoteCurrent/moonraker/moonraker')
import moonraker.common
payload = json.loads('''$json''')
for name, encoded in payload.items():
    module = types.ModuleType(name)
    module.__file__ = name.rsplit('.', 1)[-1] + '.py'
    module.__package__ = 'moonraker.components'
    sys.modules[name] = module
    exec(compile(base64.b64decode(encoded), module.__file__, 'exec'), module.__dict__)
print('REMOTE_INTEGRATED_CYCLE_IMPORT_OK')
"@
    $output = Invoke-RemoteStdin "'$RemoteCurrent/moonraker/moonraker-env/bin/python' -B -" $program
    if (($output | Select-Object -Last 1) -cne 'REMOTE_INTEGRATED_CYCLE_IMPORT_OK') {
        throw "Import Python distant invalide : $($output -join "`n")"
    }
}

function Assert-RemoteJinja {
    $config = [IO.File]::ReadAllText((Join-Path $PackageRoot 'k1-control-integrated-production-cycle-v1.cfg')).Replace("`r`n", "`n")
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($config))
    $program = [IO.File]::ReadAllText((Join-Path $PackageRoot 'remote_jinja_validate.py')).Replace('__CONFIG_BASE64__', $encoded).Replace("`r`n", "`n")
    $output = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $program
    if (($output -join "`n") -notmatch 'REMOTE_INTEGRATED_CYCLE_JINJA_PARSE_OK sections=20') {
        throw "Parse Jinja distant invalide : $($output -join "`n")"
    }
}

function Assert-Base {
    param([Parameter(Mandatory = $true)]$Manifest)
    if ((Get-RemoteHash $PrinterConfig) -cne ([string]$Manifest.baseline.printer_cfg_sha256) -or
        (Get-RemoteHash $MoonrakerConfig) -cne ([string]$Manifest.baseline.moonraker_conf_sha256) -or
        (Get-RemoteHash '/usr/data/printer_data/config/k1-control-start-sequence-owner-v1.cfg') -cne ([string]$Manifest.baseline.start_owner_r4_sha256)) {
        throw 'Une configuration de base a derive.'
    }
    foreach ($ui in $Manifest.baseline.ui.PSObject.Properties) {
        if ((Get-RemoteHash "$RemoteUi/$($ui.Name)") -cne ([string]$ui.Value)) { throw "UI de base derivee : $($ui.Name)" }
    }
    [void](Invoke-Remote "test ! -e '$MacroConfig' && test ! -e '$RemoteComponents/k1_control_cycle.py' && test ! -e '$RemoteGcode'")
    [void](Invoke-Remote "test ! -e '$RemoteCalibrationUi' && ! grep -q '^\[include k1-control-integrated-production-cycle-v1.cfg\]$' '$PrinterConfig' && ! grep -q '^\[k1_control_cycle\]$' '$MoonrakerConfig'")
    $status = Get-PrinterStatus
    Assert-SafeState $status
    Save-Evidence 'preflight-safe-state.json' (Get-SafeProjection $status)
    Assert-RemotePython
    Assert-RemoteJinja
}

function Wait-Moonraker {
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        try { [void](Invoke-Remote "curl 'http://127.0.0.1:7125/server/info'"); return }
        catch { Start-Sleep -Seconds 1 }
    }
    throw 'Moonraker ne repond pas apres restart.'
}

function Wait-Klipper {
    param([Parameter(Mandatory = $true)]$BeforeGeneration)
    Start-Sleep -Seconds 2
    $readyReads = 0
    for ($attempt = 1; $attempt -le 90; $attempt++) {
        try {
            $generation = ((Invoke-Admin 'generation') -join "`n") | ConvertFrom-Json
            $changed = ([long]$generation.socket_inode -ne [long]$BeforeGeneration.socket_inode) -or
                ([long]$generation.socket_mtime_ns -ne [long]$BeforeGeneration.socket_mtime_ns)
            if ($changed) {
                $snapshot = ((Invoke-Admin 'snapshot') -join "`n") | ConvertFrom-Json
                if ($snapshot.webhooks.state -eq 'ready' -and $snapshot.print_state) {
                    $readyReads++
                    if ($readyReads -ge 2) { return $snapshot }
                }
                else { $readyReads = 0 }
            }
        }
        catch { $readyReads = 0 }
        Start-Sleep -Seconds 1
    }
    throw 'Klipper ne repond pas apres RESTART.'
}

function Invoke-Admin {
    param([Parameter(Mandatory = $true)][ValidateSet('restart','restore_mesh','snapshot','generation')][string]$ActionName)
    $program = [IO.File]::ReadAllText((Join-Path $WorkspaceRoot 'packages\k1-control-v1\start-sequence-owner-v1\remote_admin.py')).Replace("`r`n", "`n")
    $output = $program | & ssh.exe @SshArguments "/usr/share/klippy-env/bin/python -B - '$ActionName'" 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Commande admin KO : $ActionName`n$($output -join "`n")" }
    return @($output)
}

function Invoke-Rollback {
    $manifest = Assert-Package
    [void](Invoke-Remote "test -f '$RemoteBackup/printer.cfg.before' && test -f '$RemoteBackup/moonraker.conf.before'")
    [void](Invoke-Remote "cp '$RemoteBackup/printer.cfg.before' '$PrinterConfig' && cp '$RemoteBackup/moonraker.conf.before' '$MoonrakerConfig'")
    foreach ($name in @('index.html','app.js','styles.css')) {
        [void](Invoke-Remote "cp '$RemoteBackup/$name.before' '$RemoteUi/$name'")
    }
    [void](Invoke-Remote "rm -f '$MacroConfig' '$RemoteGcode' '$RemoteComponents/k1_control_cycle.py' '$RemoteComponents/k1_control_cycle_core.py' '$RemoteComponents/k1_control_cycle_job_contract.py' '$RemoteComponents/k1_control_cycle_orchestrator.py'")
    [void](Invoke-Remote "rm -f '$RemoteComponents/__pycache__/k1_control_cycle'*.pyc '$RemoteRoot/state/integrated-cycle-selected-job.json'")
    [void](Invoke-Remote "rm -f '$RemoteCalibrationUi/index.html' '$RemoteCalibrationUi/app.js' '$RemoteCalibrationUi/styles.css' && rmdir '$RemoteCalibrationUi' 2>/dev/null || true")
    [void](Invoke-Remote "rm -f '$PrinterConfig.next' '$MoonrakerConfig.next'")
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    $beforeRestart = ((Invoke-Admin 'generation') -join "`n") | ConvertFrom-Json
    [void](Invoke-Admin 'restart')
    [void](Wait-Klipper -BeforeGeneration $beforeRestart)
    [void](Invoke-Admin 'restore_mesh')
    $final = Get-PrinterStatus
    Assert-SafeState $final
    if ((Get-RemoteHash $PrinterConfig) -cne ([string]$manifest.baseline.printer_cfg_sha256) -or
        (Get-RemoteHash $MoonrakerConfig) -cne ([string]$manifest.baseline.moonraker_conf_sha256)) {
        throw 'Rollback exact incomplet.'
    }
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "PLAN_INTEGRATED_PRODUCTION_CYCLE_V1_OK gate=$RequiredGate"
    Write-Output 'Pose: 1 overlay Klipper, 4 modules Moonraker, UI principale avec ancienne calibration conservee, 1 G-code de deux couches.'
    Write-Output 'Restart Moonraker et RESTART Klipper seulement; aucune chauffe, mouvement, extrusion ou action CFS pendant la pose.'
    exit 0
}

if ($Action -eq 'Preflight') {
    Assert-Base $manifest
    Write-Output 'PREFLIGHT_INTEGRATED_PRODUCTION_CYCLE_V1_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    foreach ($file in $manifest.files) {
        $destination = [string]$file.destination
        if ((Get-RemoteHash $destination) -cne ([string]$file.sha256)) { throw "Fichier distant non conforme : $destination" }
    }
    [void](Invoke-Remote "test `$(grep -c '^\[include k1-control-integrated-production-cycle-v1.cfg\]$' '$PrinterConfig') -eq 1 && test `$(grep -c '^\[k1_control_cycle\]$' '$MoonrakerConfig') -eq 1")
    foreach ($ui in $manifest.baseline.ui.PSObject.Properties) {
        if ((Get-RemoteHash "$RemoteCalibrationUi/$($ui.Name)") -cne ([string]$ui.Value)) { throw "Copie calibration non conforme : $($ui.Name)" }
    }
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/cycle/status'") -join "`n"
    $api = ($raw | ConvertFrom-Json).result
    if (-not $api -or $api.phase -cne 'idle' -or $api.authority_mode -cne 'offline' -or $api.effects_enabled) {
        throw 'API du cycle integre non conforme.'
    }
    $status = Get-PrinterStatus
    Assert-SafeState $status -AfterDeploy
    Save-Evidence 'validate-safe-state.json' (Get-SafeProjection $status)
    Save-Evidence 'validate-api.json' $api
    Write-Output 'VALIDATE_INTEGRATED_PRODUCTION_CYCLE_V1_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Assert-MutationGate
    Invoke-Rollback
    Write-Output "ROLLBACK_INTEGRATED_PRODUCTION_CYCLE_V1_OK capture=$CaptureId"
    exit 0
}

Assert-MutationGate
Assert-Base $manifest
New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup' '$RemoteStaging'")
    [void](Invoke-Remote "cp '$PrinterConfig' '$RemoteBackup/printer.cfg.before' && cp '$MoonrakerConfig' '$RemoteBackup/moonraker.conf.before'")
    foreach ($name in @('index.html','app.js','styles.css')) {
        [void](Invoke-Remote "cp '$RemoteUi/$name' '$RemoteBackup/$name.before'")
    }
    $MutationStarted = $true
    foreach ($file in $manifest.files) {
        $staged = ([string]$file.source).Replace('/', '__')
        Copy-ToRemote (Join-Path $PackageRoot ([string]$file.source)) "$RemoteStaging/$staged"
        if ((Get-RemoteHash "$RemoteStaging/$staged") -cne ([string]$file.sha256)) { throw "Transfert non conforme : $($file.source)" }
    }
    foreach ($file in $manifest.support_files) {
        $staged = ([string]$file.source).Replace('/', '__')
        Copy-ToRemote (Join-Path $PackageRoot ([string]$file.source)) "$RemoteStaging/$staged"
        if ((Get-RemoteHash "$RemoteStaging/$staged") -cne ([string]$file.sha256)) { throw "Transfert support non conforme : $($file.source)" }
    }
    $builder = @"
from pathlib import Path
p = Path('$PrinterConfig')
text = p.read_text()
needle = '[include k1-control-start-sequence-owner-v1.cfg]\n'
assert text.count(needle) == 1
p.with_suffix('.cfg.next').write_text(text.replace(needle, needle + '[include k1-control-integrated-production-cycle-v1.cfg]\n', 1))
m = Path('$MoonrakerConfig')
moon = m.read_text()
assert '[k1_control_cycle]' not in moon
section = Path('$RemoteStaging/moonraker-section.conf').read_text()
m.with_suffix('.conf.next').write_text(moon.rstrip() + '\n\n' + section.strip() + '\n')
"@
    [void](Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $builder)
    [void](Invoke-Remote "mkdir -p '$RemoteCalibrationUi'")
    foreach ($name in @('index.html','app.js','styles.css')) {
        [void](Invoke-Remote "cp '$RemoteUi/$name' '$RemoteCalibrationUi/$name'")
    }
    foreach ($file in $manifest.files) {
        $destination = [string]$file.destination
        $staged = ([string]$file.source).Replace('/', '__')
        [void](Invoke-Remote "cp '$RemoteStaging/$staged' '$destination.next' && chmod 0644 '$destination.next' && mv '$destination.next' '$destination'")
    }
    [void](Invoke-Remote "mv '$PrinterConfig.next' '$PrinterConfig' && mv '$MoonrakerConfig.next' '$MoonrakerConfig'")
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    $beforeRestart = ((Invoke-Admin 'generation') -join "`n") | ConvertFrom-Json
    [void](Invoke-Admin 'restart')
    [void](Wait-Klipper -BeforeGeneration $beforeRestart)
    [void](Invoke-Admin 'restore_mesh')
    & $PSCommandPath -Action Validate -PrinterHost $PrinterHost -CaptureId $CaptureId -EvidenceDirectory $EvidenceDirectory
    Save-Evidence 'deploy-result.json' ([ordered]@{
        capture_id = $CaptureId
        result = 'DEPLOY_INTEGRATED_PRODUCTION_CYCLE_V1_OK'
        physical_action = $false
        heater_command = $false
        cfs_command = $false
        authority_mode = 'offline'
    })
    Write-Output "DEPLOY_INTEGRATED_PRODUCTION_CYCLE_V1_OK capture=$CaptureId"
}
catch {
    $failure = $_
    try { Save-Evidence 'deploy-failure.txt' $failure.Exception.ToString() } catch {}
    if ($MutationStarted) {
        try { Invoke-Rollback }
        catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
