[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-composite-mesh-v1',
    [switch]$Execute,
    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-COMPOSITE-MESH-V1'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\composite-mesh-v1'
$ManifestPath = Join-Path $PackageRoot 'deployment-manifest.json'
$ContractPath = Join-Path $PackageRoot 'composite-mesh-contract.json'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteCurrent = "$RemoteRoot/current"
$RemoteConfig = "$RemoteCurrent/config/moonraker.conf"
$RemoteComponents = "$RemoteCurrent/moonraker/moonraker/moonraker/components"
$RemoteState = "$RemoteRoot/state/k1-control-composite-mesh.json"
$RemoteSubgridState = "$RemoteRoot/state/k1-control-composite-subgrid.json"
$RemotePrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$RemoteCore = "$RemoteComponents/k1_control_composite_mesh_core.py"
$RemoteComponent = "$RemoteComponents/k1_control_composite_mesh.py"
$RemoteCompose = "$RemoteComponents/k1_control_composite_mesh_compose.py"
$RemoteRender = "$RemoteComponents/k1_control_composite_mesh_render.py"
$RemoteSubgridCore = "$RemoteComponents/k1_control_composite_subgrid_core.py"
$RemoteSubgridComponent = "$RemoteComponents/k1_control_composite_subgrid.py"
$MoonrakerService = '/etc/init.d/S56k1_control_moonraker'
$RemoteBackup = "$RemoteRoot/backups/$CaptureId-composite-mesh-v1"
$RemoteStaging = "$RemoteRoot/tmp/$CaptureId-composite-mesh-v1"
$LocalCapture = Join-Path $WorkspaceRoot "inventory\raw\$CaptureId"
$MutationStarted = $false

function Assert-MutationGate {
    if (-not $Execute -or $Gate -cne $RequiredGate) {
        throw "Action bloquée : -Execute et -Gate '$RequiredGate' sont obligatoires."
    }
}

function Get-LocalSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Invoke-Remote {
    param([Parameter(Mandatory = $true)][string]$Command)
    $arguments = @(
        '-o', 'BatchMode=yes', '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no', '-o', 'ConnectTimeout=8',
        $PrinterHost, $Command
    )
    $output = & ssh.exe @arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Commande distante KO : $Command`n$($output -join "`n")"
    }
    return @($output)
}

function Copy-ToRemote {
    param([string]$Source, [string]$Destination)
    $arguments = @(
        '-O', '-o', 'BatchMode=yes', '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no', '-o', 'ConnectTimeout=8',
        (Resolve-Path -LiteralPath $Source).Path, "$PrinterHost`:$Destination"
    )
    & scp.exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Transfert SCP KO : $Destination" }
}

function Get-RemoteSha256 {
    param([string]$Path)
    $line = Invoke-Remote "sha256sum '$Path'"
    return ((($line | Select-Object -First 1) -split '\s+')[0]).ToLowerInvariant()
}

function Assert-Package {
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ($manifest.contract_id -cne $RequiredGate -or $manifest.status -cne 'deployment_candidate') {
        throw 'Manifeste COMPOSITE-MESH-V1 inattendu.'
    }
    foreach ($pin in @(
        @{ Path = $PSCommandPath; Hash = [string]$manifest.deployer.sha256 },
        @{ Path = $ContractPath; Hash = [string]$manifest.contract.sha256 }
    )) {
        if ((Get-LocalSha256 $pin.Path) -cne $pin.Hash) { throw "Empreinte locale inattendue : $($pin.Path)" }
    }
    foreach ($file in $manifest.files) {
        $local = Join-Path $PackageRoot ([string]$file.source)
        if ((Get-LocalSha256 $local) -cne [string]$file.sha256) {
            throw "Empreinte locale inattendue : $($file.source)"
        }
    }
    return $manifest
}

function Get-ServerInfo {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/server/info'") -join "`n"
    $info = ($raw | ConvertFrom-Json).result
    if (-not $info) { throw 'Moonraker sans server/info.' }
    return $info
}

function Get-SubgridState {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/composite_subgrid/status'") -join "`n"
    $state = ($raw | ConvertFrom-Json).result
    if (-not $state) { throw 'API de sous-grille sans état.' }
    return $state
}

function Get-CompositeState {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/composite_mesh/status'") -join "`n"
    $state = ($raw | ConvertFrom-Json).result
    if (-not $state) { throw 'API composite complète sans état.' }
    return $state
}

function Get-PrinterStatus {
    $url = "http://127.0.0.1:7125/printer/objects/query?print_stats&extruder&heater_bed&toolhead&bed_mesh&configfile&box&gcode_macro+KCTRL_STATE&k1_control_store&gcode_macro+KCTRL_CAL_PATH_STATE"
    $raw = (Invoke-Remote "curl '$url'") -join "`n"
    $status = ($raw | ConvertFrom-Json).result.status
    if (-not $status) { throw 'Réponse Moonraker sans état Klipper.' }
    return $status
}

function Assert-SafePrinter {
    param([Parameter(Mandatory = $true)]$Manifest)
    $status = Get-PrinterStatus
    if ($status.print_stats.state -cne 'standby' -or $status.print_stats.filename) { throw 'Imprimante non disponible.' }
    if ([double]$status.extruder.target -ne 0 -or [double]$status.heater_bed.target -ne 0) { throw 'Les chauffes ne sont pas coupées.' }
    if ([string]$status.toolhead.homed_axes) { throw 'Les axes sont encore référencés.' }
    $runtime = $status.'gcode_macro KCTRL_STATE'
    $store = $status.k1_control_store
    $path = $status.'gcode_macro KCTRL_CAL_PATH_STATE'
    if ([int]$runtime.ready -ne 1 -or [int]$runtime.accepted_z_valid -ne 1 -or
        [double]$runtime.accepted_z_offset -ne -0.04 -or [int]$runtime.session_active -ne 0 -or
        [int]$runtime.low_moves_armed -ne 0 -or -not $store -or $store.integrity -cne 'ok') {
        throw 'Runtime ou stockage Z non sûr.'
    }
    if (@('idle', 'committed', 'cancelled') -notcontains [string]$path.phase -or
        [int]$path.motion_armed -ne 0 -or [int]$path.commit_ready -ne 0) { throw 'Chemin Z non fermé.' }
    $profiles = @($status.bed_mesh.profiles.PSObject.Properties.Name)
    if ($profiles -notcontains 'k1_p001_t055_r001_n06x06' -or
        $profiles -contains 'k1_p001_t055_r001_n11x11' -or
        @($profiles | Where-Object { $_ -like 'K1_COMPOSITE_CAPTURE_*' -or $_ -eq 'K1_TRANSIENT' }).Count -ne 0 -or
        [string]$status.bed_mesh.profile_name -cne 'k1_p001_t055_r001_n06x06') {
        throw 'Profils bed_mesh non sûrs avant la campagne complète.'
    }
    $count = @($status.configfile.settings.bed_mesh.probe_count)
    if ($count.Count -ne 2 -or [int]$count[0] -ne 6 -or [int]$count[1] -ne 6 -or
        [string]$status.configfile.settings.bed_mesh.algorithm -cne 'lagrange') { throw 'Configuration bed_mesh inattendue.' }
    foreach ($unit in @('T1', 'T2')) {
        if ([string]$status.box.$unit.state -cne 'connect') { throw "CFS $unit non connecté." }
    }
    if ((Get-RemoteSha256 $RemotePrinterConfig) -cne [string]$Manifest.baseline.printer_cfg_sha256) { throw 'printer.cfg de base inattendu.' }
    return $status
}

function Assert-SubgridQualified {
    $state = Get-SubgridState
    if ([string]$state.phase -cne 'qualified' -or [bool]$state.busy -or
        [int]$state.physical_contacts -ne 25 -or -not [bool]$state.backup_available -or
        (@($state.context.x_indices) -join ',') -cne '1,3,5,7,9' -or
        (@($state.context.y_indices) -join ',') -cne '1,3,5,7,9') {
        throw 'SUBGRID-V1 physique n est pas qualifiée.'
    }
}

function Assert-RemoteCandidateParse {
    $sources = @{}
    foreach ($name in @('compose_mesh.py', 'render_profile.py', 'k1_control_composite_mesh_core.py', 'k1_control_composite_mesh.py')) {
        $sources[$name] = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $PackageRoot $name)))
    }
    $program = @"
import base64
import configparser
import sys
sys.path.insert(0, '/usr/share/klipper/klippy')
import configfile
sources = {}
"@
    $program += "`n"
    foreach ($name in $sources.Keys) {
        $program += "sources['$name'] = base64.b64decode('$($sources[$name])')`n"
    }
    $program += @"
for name, source in sources.items():
    compile(source, name, 'exec')
render = {}
exec(compile(sources['render_profile.py'], 'render_profile.py', 'exec'), render)
matrix = [[float(y * 11 + x) / 1000.0 for x in range(11)] for y in range(11)]
source = open('/usr/data/printer_data/config/printer.cfg', 'rb').read()
candidate = render['append_profile'](source, matrix).decode('utf-8')
reader = object.__new__(configfile.PrinterConfig)
regular, autosave = configfile.PrinterConfig._find_autosave_data(reader, candidate)
parser = configparser.RawConfigParser(strict=False, inline_comment_prefixes=(';', '#'))
parser.read_string(autosave)
section = 'bed_mesh k1_p001_t055_r001_n11x11'
assert parser.has_section('bed_mesh k1_p001_t055_r001_n06x06')
assert parser.has_section(section)
assert parser.getint(section, 'x_count') == 11
assert parser.getint(section, 'y_count') == 11
assert parser.get(section, 'algo') == 'bicubic'
rows = [line for line in parser.get(section, 'points').strip().split('\n') if line.strip()]
assert len(rows) == 11 and all(len(row.split(',')) == 11 for row in rows)
print('REMOTE_COMPOSITE_MESH_PARSE_OK')
"@
    $python = "$RemoteCurrent/moonraker/moonraker-env/bin/python"
    $arguments = @('-o','BatchMode=yes','-o','PasswordAuthentication=no','-o','KbdInteractiveAuthentication=no','-o','ConnectTimeout=8',$PrinterHost,"'$python' -")
    $output = $program | & ssh.exe @arguments 2>&1
    if ($LASTEXITCODE -ne 0 -or ($output | Select-Object -Last 1) -cne 'REMOTE_COMPOSITE_MESH_PARSE_OK') {
        throw "Parse distant du candidat composite KO : $($output -join "`n")"
    }
}

function Assert-Baseline {
    param([Parameter(Mandatory = $true)]$Manifest)
    [void](Invoke-Remote "test -f '$RemoteConfig' && test -f '$RemoteSubgridCore' && test -f '$RemoteSubgridComponent' && test ! -e '$RemoteCore' && test ! -e '$RemoteComponent' && test ! -e '$RemoteCompose' && test ! -e '$RemoteRender' && test ! -e '$RemoteState'")
    if ((Get-RemoteSha256 $RemoteConfig) -cne [string]$Manifest.baseline.moonraker_conf_sha256) { throw 'moonraker.conf de base inattendu.' }
    if ((Get-RemoteSha256 $RemoteSubgridCore) -cne [string]$Manifest.baseline.subgrid_core_sha256 -or
        (Get-RemoteSha256 $RemoteSubgridComponent) -cne [string]$Manifest.baseline.subgrid_component_sha256) { throw 'Révision SUBGRID-V1 inattendue.' }
    foreach ($module in $Manifest.firmware_dependencies) {
        if ((Get-RemoteSha256 ([string]$module.path)) -cne [string]$module.sha256) { throw "Module firmware inattendu : $($module.path)" }
    }
    [void](Assert-SafePrinter $Manifest)
    Assert-SubgridQualified
    Assert-RemoteCandidateParse
}

function Wait-Moonraker {
    param([bool]$ExpectComposite = $true, [int]$Attempts = 60)
    $last = 'aucune réponse'
    for ($index = 1; $index -le $Attempts; $index++) {
        try {
            $info = Get-ServerInfo
            $present = @($info.components) -contains 'k1_control_composite_mesh'
            if (($present -eq $ExpectComposite) -and @($info.failed_components).Count -eq 0 -and @($info.warnings).Count -eq 0) { return }
            $last = "components=$(@($info.components) -join ',') failed=$(@($info.failed_components) -join ',') warnings=$(@($info.warnings) -join ',')"
        }
        catch { $last = $_.Exception.Message }
        Start-Sleep -Seconds 1
    }
    throw "Moonraker non stabilisé : $last"
}

function Assert-Installed {
    param([Parameter(Mandatory = $true)]$Manifest)
    foreach ($file in $Manifest.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne [string]$file.sha256) { throw "Empreinte distante inattendue : $($file.destination)" }
    }
    $info = Get-ServerInfo
    if (@($info.components) -notcontains 'k1_control_composite_mesh' -or @($info.failed_components).Count -ne 0 -or @($info.warnings).Count -ne 0) { throw 'Composant composite complet absent ou échoué.' }
    $state = Get-CompositeState
    if ([string]$state.phase -cne 'idle' -or [bool]$state.busy -or [int]$state.completed_passes -ne 0 -or [bool]$state.backup_available) { throw 'État initial du composant complet inattendu.' }
    Assert-SubgridQualified
    [void](Assert-SafePrinter $Manifest)
}

function Remove-RemoteStaging {
    [void](Invoke-Remote "rm -f '$RemoteStaging/moonraker.conf' '$RemoteStaging/k1_control_composite_mesh_core.py' '$RemoteStaging/k1_control_composite_mesh.py' '$RemoteStaging/compose_mesh.py' '$RemoteStaging/render_profile.py' && rmdir '$RemoteStaging' 2>/dev/null || true")
}

function Invoke-ExactRollback {
    $manifest = Assert-Package
    if ((Get-RemoteSha256 "$RemoteBackup/moonraker.conf.before") -cne [string]$manifest.baseline.moonraker_conf_sha256) { throw 'Backup moonraker.conf inattendu.' }
    [void](Invoke-Remote "cp '$RemoteBackup/moonraker.conf.before' '$RemoteConfig.rollback-next' && chmod 0600 '$RemoteConfig.rollback-next' && mv '$RemoteConfig.rollback-next' '$RemoteConfig'")
    [void](Invoke-Remote "rm -f '$RemoteCore' '$RemoteComponent' '$RemoteCompose' '$RemoteRender' '$RemoteState' '$RemoteComponents/__pycache__/k1_control_composite_mesh_core.cpython-38.pyc' '$RemoteComponents/__pycache__/k1_control_composite_mesh.cpython-38.pyc' '$RemoteComponents/__pycache__/k1_control_composite_mesh_compose.cpython-38.pyc' '$RemoteComponents/__pycache__/k1_control_composite_mesh_render.cpython-38.pyc'")
    Remove-RemoteStaging
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker -ExpectComposite $false
    Assert-Baseline $manifest
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "PLAN_COMPOSITE_MESH_V1_OK gate=$RequiredGate"
    Write-Output 'Pose: quatre modules originaux et moonraker.conf exact; restart Moonraker seulement.'
    Write-Output 'Aucune chauffe, référence, mesure, persistance de profil ou écriture Z pendant la pose.'
    exit 0
}
if ($Action -eq 'Preflight') { Assert-Baseline $manifest; Write-Output 'PREFLIGHT_COMPOSITE_MESH_V1_OK'; exit 0 }
if ($Action -eq 'Validate') { Assert-Installed $manifest; Write-Output 'VALIDATE_COMPOSITE_MESH_V1_OK'; exit 0 }
if ($Action -eq 'Rollback') { Assert-MutationGate; Invoke-ExactRollback; Write-Output "ROLLBACK_COMPOSITE_MESH_V1_OK capture=$CaptureId"; exit 0 }

Assert-MutationGate
Assert-Baseline $manifest
New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null
try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup' '$RemoteStaging'")
    [void](Invoke-Remote "cp '$RemoteConfig' '$RemoteBackup/moonraker.conf.before'")
    if ((Get-RemoteSha256 "$RemoteBackup/moonraker.conf.before") -cne [string]$manifest.baseline.moonraker_conf_sha256) { throw 'Backup moonraker.conf non conforme.' }
    foreach ($file in $manifest.files) {
        Copy-ToRemote (Join-Path $PackageRoot ([string]$file.source)) "$RemoteStaging/$($file.source)"
        if ((Get-RemoteSha256 "$RemoteStaging/$($file.source)") -cne [string]$file.sha256) { throw "Transfert non conforme : $($file.source)" }
    }
    $python = "$RemoteCurrent/moonraker/moonraker-env/bin/python"
    [void](Invoke-Remote "'$python' -c `"compile(open('$RemoteStaging/k1_control_composite_mesh_core.py').read(), 'core.py', 'exec'); compile(open('$RemoteStaging/k1_control_composite_mesh.py').read(), 'component.py', 'exec'); compile(open('$RemoteStaging/compose_mesh.py').read(), 'compose.py', 'exec'); compile(open('$RemoteStaging/render_profile.py').read(), 'render.py', 'exec')`"")
    $MutationStarted = $true
    foreach ($file in $manifest.files) {
        $destination = [string]$file.destination
        $mode = if ($destination -ceq $RemoteConfig) { '0600' } else { '0644' }
        [void](Invoke-Remote "cp '$RemoteStaging/$($file.source)' '$destination.next' && chmod $mode '$destination.next' && mv '$destination.next' '$destination'")
    }
    [void](Invoke-Remote "rm -f '$RemoteComponents/__pycache__/k1_control_composite_mesh_core.cpython-38.pyc' '$RemoteComponents/__pycache__/k1_control_composite_mesh.cpython-38.pyc' '$RemoteComponents/__pycache__/k1_control_composite_mesh_compose.cpython-38.pyc' '$RemoteComponents/__pycache__/k1_control_composite_mesh_render.cpython-38.pyc'")
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    & $PSCommandPath -Action Validate -PrinterHost $PrinterHost -CaptureId $CaptureId
    Remove-RemoteStaging
    [pscustomobject]@{ capture_id=$CaptureId; result='DEPLOY_COMPOSITE_MESH_V1_OK'; moonraker_restart_only=$true; physical_action=$false } |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LocalCapture 'deploy-result.json') -Encoding UTF8
    Write-Output "DEPLOY_COMPOSITE_MESH_V1_OK capture=$CaptureId"
}
catch {
    $failure = $_
    if ($MutationStarted) {
        try { Invoke-ExactRollback } catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
