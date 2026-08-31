[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$Gate = '',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-integrated-production-cycle-hotfix-r2',
    [string]$EvidenceDirectory = '',
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 ou plus recent est obligatoire.' }

$RequiredGate = 'G4-K1-CONTROL-INTEGRATED-PRODUCTION-CYCLE-HOTFIX-R2'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\integrated-production-cycle-v1'
$ManifestPath = Join-Path $PackageRoot 'hotfix-r2-manifest.json'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteCurrent = "$RemoteRoot/current"
$PrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$MoonrakerConfig = "$RemoteCurrent/config/moonraker.conf"
$RemoteComponents = "$RemoteCurrent/moonraker/moonraker/moonraker/components"
$RemoteComponent = "$RemoteComponents/k1_control_cycle.py"
$MoonrakerService = '/etc/init.d/S56k1_control_moonraker'
$RemoteBackup = "$RemoteRoot/backups/$CaptureId-integrated-cycle-hotfix-r2"
$RemoteStaging = "$RemoteRoot/tmp/$CaptureId-integrated-cycle-hotfix-r2"
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
        throw 'Manifeste du correctif R2 inattendu.'
    }
    foreach ($file in $manifest.files) {
        $source = Join-Path $PackageRoot ([string]$file.source)
        if ((Get-LocalHash $source) -cne ([string]$file.source_sha256)) {
            throw "Empreinte locale inattendue : $($file.source)"
        }
    }
    if ((Get-LocalHash $PSCommandPath) -cne ([string]$manifest.deployer_sha256)) {
        throw 'Empreinte du deployeur R2 inattendue.'
    }
    return $manifest
}

function Get-CycleStatus {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/cycle/status'") -join "`n"
    $payload = $raw | ConvertFrom-Json
    if (-not $payload.result) { throw 'Etat du cycle integre absent.' }
    return $payload.result
}

function Get-PrinterStatus {
    $url = 'http://127.0.0.1:7125/printer/objects/query?webhooks=state&print_stats=state,filename&extruder=temperature,target&heater_bed=temperature,target&toolhead=homed_axes,position&gcode_move=homing_origin&bed_mesh=profile_name&box&filament_switch_sensor+filament_sensor=filament_detected&filament_switch_sensor+filament_sensor_2=filament_detected&gcode_macro+KCTRL_STATE&gcode_macro+KCTRL_CYCLE_STATE'
    $raw = (Invoke-Remote "curl '$url'") -join "`n"
    $payload = $raw | ConvertFrom-Json
    if (-not $payload.result.status) { throw 'Etat Klipper absent.' }
    return $payload.result.status
}

function Assert-SafeState {
    param([Parameter(Mandatory = $true)]$Status, [switch]$RequireIdle)
    if ($Status.webhooks.state -cne 'ready' -or $Status.print_stats.state -cne 'standby' -or $Status.print_stats.filename) {
        throw 'La K1 n est pas au repos.'
    }
    if ([double]$Status.extruder.target -ne 0 -or [double]$Status.heater_bed.target -ne 0) {
        throw 'Une chauffe est demandee.'
    }
    if ($Status.box.state -cne 'connect' -or $Status.box.t_command -cne '' -or
        $Status.box.T1.state -cne 'connect' -or $Status.box.T2.state -cne 'connect') {
        throw 'Les deux CFS ne sont pas stables.'
    }
    if ($Status.box.T1.filament -notin @('None','none','') -or $Status.box.T2.filament -notin @('None','none','')) {
        throw 'Une route CFS a ete engagee malgre le refus de commande.'
    }
    if ($Status.bed_mesh.profile_name -cne 'k1_p001_t055_r001_n11x11') { throw 'Le mesh 11x11 actif est absent.' }
    if ([int]$Status.'gcode_macro KCTRL_STATE'.accepted_z_valid -ne 1 -or
        [math]::Abs([double]$Status.'gcode_macro KCTRL_STATE'.accepted_z_offset + 0.04) -gt 0.0005) {
        throw 'Le Z accepte -0,04 mm est absent.'
    }
    $phase = [string]$Status.'gcode_macro KCTRL_CYCLE_STATE'.phase
    if ($RequireIdle -and $phase -cne 'idle') { throw 'Le cycle integre n est pas revenu au repos.' }
    if (-not $RequireIdle -and $phase -cne 'failed_safe') { throw 'Le preflight attend le refus sur failed_safe.' }
}

function Get-SafeProjection {
    param([Parameter(Mandatory = $true)]$Status)
    return [ordered]@{
        webhooks_state = $Status.webhooks.state
        print_state = $Status.print_stats.state
        nozzle_temperature_c = [double]$Status.extruder.temperature
        nozzle_target_c = [double]$Status.extruder.target
        bed_temperature_c = [double]$Status.heater_bed.temperature
        bed_target_c = [double]$Status.heater_bed.target
        homed_axes = $Status.toolhead.homed_axes
        position = @($Status.toolhead.position)
        homing_origin = @($Status.gcode_move.homing_origin)
        mesh_profile = $Status.bed_mesh.profile_name
        cfs_command = $Status.box.t_command
        routes = @('T1','T2' | ForEach-Object { if ($Status.box.$_.filament -in @('A','B','C','D')) { "$_$($Status.box.$_.filament)" } })
        head_sensor = [bool]$Status.'filament_switch_sensor filament_sensor'.filament_detected
        after_cutter_sensor = [bool]$Status.'filament_switch_sensor filament_sensor_2'.filament_detected
        accepted_z_offset = [double]$Status.'gcode_macro KCTRL_STATE'.accepted_z_offset
        cycle_phase = $Status.'gcode_macro KCTRL_CYCLE_STATE'.phase
        identity_values_exported = $false
    }
}

function Assert-RemoteCandidates {
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
    $json = $payload | ConvertTo-Json -Compress
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
print('REMOTE_INTEGRATED_CYCLE_HOTFIX_R2_IMPORT_OK')
"@
    $output = Invoke-RemoteStdin "'$RemoteCurrent/moonraker/moonraker-env/bin/python' -B -" $program
    if (($output | Select-Object -Last 1) -cne 'REMOTE_INTEGRATED_CYCLE_HOTFIX_R2_IMPORT_OK') {
        throw "Import Python distant invalide : $($output -join "`n")"
    }
    $config = [IO.File]::ReadAllText((Join-Path $PackageRoot 'k1-control-integrated-production-cycle-v1.cfg')).Replace("`r`n", "`n")
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($config))
    $jinja = [IO.File]::ReadAllText((Join-Path $PackageRoot 'remote_jinja_validate.py')).Replace('__CONFIG_BASE64__', $encoded).Replace("`r`n", "`n")
    $parsed = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $jinja
    if (($parsed -join "`n") -notmatch 'REMOTE_INTEGRATED_CYCLE_JINJA_PARSE_OK sections=20') {
        throw "Parse Jinja distant invalide : $($parsed -join "`n")"
    }
}

function Wait-Moonraker {
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        try {
            [void](Invoke-Remote "curl 'http://127.0.0.1:7125/server/info'")
            [void](Get-CycleStatus)
            return
        }
        catch { Start-Sleep -Seconds 1 }
    }
    throw 'Moonraker ne repond pas apres restart.'
}

function Invoke-Admin {
    param([Parameter(Mandatory = $true)][ValidateSet('restart','restore_mesh','snapshot','generation')][string]$ActionName)
    $program = [IO.File]::ReadAllText((Join-Path $WorkspaceRoot 'packages\k1-control-v1\start-sequence-owner-v1\remote_admin.py')).Replace("`r`n", "`n")
    $output = $program | & ssh.exe @SshArguments "/usr/share/klippy-env/bin/python -B - '$ActionName'" 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Commande admin KO : $ActionName`n$($output -join "`n")" }
    return @($output)
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

function Restart-And-RestoreMesh {
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    $beforeRestart = ((Invoke-Admin 'generation') -join "`n") | ConvertFrom-Json
    [void](Invoke-Admin 'restart')
    [void](Wait-Klipper -BeforeGeneration $beforeRestart)
    [void](Invoke-Admin 'restore_mesh')
}

function Assert-Preflight {
    param([Parameter(Mandatory = $true)]$Manifest)
    if ((Get-RemoteHash $PrinterConfig) -cne ([string]$Manifest.stable.printer_cfg_sha256) -or
        (Get-RemoteHash $MoonrakerConfig) -cne ([string]$Manifest.stable.moonraker_conf_sha256) -or
        (Get-RemoteHash $RemoteComponent) -cne ([string]$Manifest.stable.component_sha256)) {
        throw 'Une base stable a derive.'
    }
    foreach ($file in $Manifest.files) {
        if ((Get-RemoteHash ([string]$file.destination)) -cne ([string]$file.installed_sha256)) {
            throw "Fichier distant de depart inattendu : $($file.destination)"
        }
    }
    $cycle = Get-CycleStatus
    if ($cycle.phase -cne 'failed_safe' -or $cycle.failure_code -cne 'operator_abort' -or $cycle.busy -or
        @($cycle.effect_ids).Count -ne 0 -or [int]$cycle.load_count -ne 0 -or [int]$cycle.unload_count -ne 0 -or [int]$cycle.purge_count -ne 0 -or
        $cycle.job.filename -cne ([string]$Manifest.selection_fixture)) {
        throw 'La preuve du refus avant tout effet est incomplete.'
    }
    $printer = Get-PrinterStatus
    Assert-SafeState $printer
    Assert-RemoteCandidates
    Save-Evidence 'preflight-cycle-failed-safe.json' $cycle
    Save-Evidence 'preflight-safe-state.json' (Get-SafeProjection $printer)
}

function Assert-Installed {
    param([Parameter(Mandatory = $true)]$Manifest)
    foreach ($file in $Manifest.files) {
        if ((Get-RemoteHash ([string]$file.destination)) -cne ([string]$file.source_sha256)) {
            throw "Correctif R2 distant absent : $($file.destination)"
        }
    }
    if ((Get-RemoteHash $PrinterConfig) -cne ([string]$Manifest.stable.printer_cfg_sha256) -or
        (Get-RemoteHash $MoonrakerConfig) -cne ([string]$Manifest.stable.moonraker_conf_sha256) -or
        (Get-RemoteHash $RemoteComponent) -cne ([string]$Manifest.stable.component_sha256)) {
        throw 'Une base stable a change pendant le correctif.'
    }
    $cycle = Get-CycleStatus
    if ($cycle.phase -cne 'idle' -or $cycle.busy -or $cycle.job.filename -cne ([string]$Manifest.selection_fixture)) {
        throw 'Le cycle corrige n est pas revenu au repos avec le G-code selectionne.'
    }
    $printer = Get-PrinterStatus
    Assert-SafeState $printer -RequireIdle
    Save-Evidence 'validate-cycle-idle.json' $cycle
    Save-Evidence 'validate-safe-state.json' (Get-SafeProjection $printer)
}

function Invoke-Rollback {
    param([Parameter(Mandatory = $true)]$Manifest)
    foreach ($file in $Manifest.files) {
        $name = [IO.Path]::GetFileName([string]$file.destination)
        [void](Invoke-Remote "test -f '$RemoteBackup/$name.before'")
        [void](Invoke-Remote "cp '$RemoteBackup/$name.before' '$($file.destination).next' && chmod 0644 '$($file.destination).next' && mv '$($file.destination).next' '$($file.destination)'")
    }
    [void](Invoke-Remote "rm -f '$RemoteComponents/__pycache__/k1_control_cycle_orchestrator'*.pyc")
    Restart-And-RestoreMesh
    foreach ($file in $Manifest.files) {
        if ((Get-RemoteHash ([string]$file.destination)) -cne ([string]$file.installed_sha256)) {
            throw "Rollback exact incomplet : $($file.destination)"
        }
    }
    $printer = Get-PrinterStatus
    Assert-SafeState $printer -RequireIdle
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "PLAN_INTEGRATED_PRODUCTION_CYCLE_HOTFIX_R2_OK gate=$RequiredGate"
    Write-Output 'Pose: macro Klipper et pilote Moonraker seulement; sauvegardes exactes, deux restarts et restauration unique du 11x11.'
    Write-Output 'Aucune chauffe, mouvement, extrusion, action CFS ou retry physique.'
    exit 0
}

if ($Action -eq 'Preflight') {
    Assert-Preflight $manifest
    Write-Output 'PREFLIGHT_INTEGRATED_PRODUCTION_CYCLE_HOTFIX_R2_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    Assert-Installed $manifest
    Write-Output 'VALIDATE_INTEGRATED_PRODUCTION_CYCLE_HOTFIX_R2_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Assert-MutationGate
    Invoke-Rollback $manifest
    Write-Output "ROLLBACK_INTEGRATED_PRODUCTION_CYCLE_HOTFIX_R2_OK capture=$CaptureId"
    exit 0
}

Assert-MutationGate
Assert-Preflight $manifest
New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup' '$RemoteStaging'")
    foreach ($file in $manifest.files) {
        $name = [IO.Path]::GetFileName([string]$file.destination)
        [void](Invoke-Remote "cp '$($file.destination)' '$RemoteBackup/$name.before'")
    }
    $MutationStarted = $true
    foreach ($file in $manifest.files) {
        $name = [IO.Path]::GetFileName([string]$file.destination)
        $source = Join-Path $PackageRoot ([string]$file.source)
        Copy-ToRemote $source "$RemoteStaging/$name"
        if ((Get-RemoteHash "$RemoteStaging/$name") -cne ([string]$file.source_sha256)) {
            throw "Transfert R2 non conforme : $($file.source)"
        }
        [void](Invoke-Remote "cp '$RemoteStaging/$name' '$($file.destination).next' && chmod 0644 '$($file.destination).next' && mv '$($file.destination).next' '$($file.destination)'")
    }
    [void](Invoke-Remote "rm -f '$RemoteComponents/__pycache__/k1_control_cycle_orchestrator'*.pyc")
    Restart-And-RestoreMesh
    Assert-Installed $manifest
    Save-Evidence 'deploy-result.json' ([ordered]@{
        capture_id = $CaptureId
        result = 'DEPLOY_INTEGRATED_PRODUCTION_CYCLE_HOTFIX_R2_OK'
        physical_action = $false
        heater_command = $false
        cfs_command = $false
        restored_mesh = 'k1_p001_t055_r001_n11x11'
        selected_job = [string]$manifest.selection_fixture
    })
    Write-Output "DEPLOY_INTEGRATED_PRODUCTION_CYCLE_HOTFIX_R2_OK capture=$CaptureId"
}
catch {
    $failure = $_
    try { Save-Evidence 'deploy-failure.txt' $failure.Exception.ToString() } catch {}
    if ($MutationStarted) {
        try { Invoke-Rollback $manifest }
        catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
