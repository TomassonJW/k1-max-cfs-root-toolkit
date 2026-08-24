[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-calibration-ui-navigation-v1',
    [switch]$Execute,
    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-CALIBRATION-UI-NAVIGATION-V1-R2'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\calibration-ui-navigation-v1'
$ManifestPath = Join-Path $PackageRoot 'deployment-manifest.json'
$ContractPath = Join-Path $PackageRoot 'calibration-ui-navigation-contract.json'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteApp = "$RemoteRoot/current/www/mainsail/k1-control/app.js"
$RemoteAlias = "$RemoteRoot/current/www/mainsail/access-k1-control"
$RemoteTheme = '/usr/data/printer_data/config/.theme'
$RemoteNavi = "$RemoteTheme/navi.json"
$RemoteBackup = "$RemoteRoot/backups/$CaptureId-calibration-ui-navigation-v1"
$RemoteStaging = "$RemoteRoot/tmp/$CaptureId-calibration-ui-navigation-v1"
$LocalCapture = Join-Path $WorkspaceRoot "inventory\raw\$CaptureId"
$MutationStarted = $false

function Assert-MutationGate {
    if (-not $Execute -or $Gate -cne $RequiredGate) {
        throw "Action bloquee : -Execute et -Gate '$RequiredGate' sont obligatoires."
    }
}

function Get-LocalSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Invoke-Remote {
    param([Parameter(Mandatory = $true)][string]$Command)
    $arguments = @(
        '-o', 'BatchMode=yes',
        '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no',
        '-o', 'ConnectTimeout=8',
        $PrinterHost,
        $Command
    )
    $output = & ssh.exe @arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Commande distante KO : $Command`n$($output -join "`n")"
    }
    return @($output)
}

function Copy-ToRemote {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $arguments = @(
        '-O',
        '-o', 'BatchMode=yes',
        '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no',
        '-o', 'ConnectTimeout=8',
        (Resolve-Path -LiteralPath $Source).Path,
        "$PrinterHost`:$Destination"
    )
    & scp.exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Transfert SCP KO : $Destination" }
}

function Get-RemoteSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    $line = Invoke-Remote "sha256sum '$Path'"
    return ((($line | Select-Object -First 1) -split '\s+')[0]).ToLowerInvariant()
}

function Assert-Package {
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    $contract = Get-Content -LiteralPath $ContractPath -Raw | ConvertFrom-Json
    if ($manifest.contract_id -cne $RequiredGate -or $contract.contract_id -cne $RequiredGate) {
        throw 'Identité du paquet CALIBRATION-UI-NAVIGATION-V1 inattendue.'
    }
    if ((Get-LocalSha256 $PSCommandPath) -cne [string]$manifest.deployer.sha256) {
        throw 'Empreinte du déployeur CALIBRATION-UI-NAVIGATION-V1 inattendue.'
    }
    if ((Get-LocalSha256 $ContractPath) -cne [string]$manifest.contract.sha256) {
        throw 'Empreinte du contrat CALIBRATION-UI-NAVIGATION-V1 inattendue.'
    }
    foreach ($file in $manifest.files) {
        $source = Join-Path $PackageRoot ([string]$file.source)
        if ((Get-LocalSha256 $source) -cne [string]$file.sha256) {
            throw "Empreinte locale inattendue : $($file.source)"
        }
    }
    if (@($manifest.files).Count -ne 2 -or
        [string]$manifest.files[0].source -cne 'app.js' -or
        [string]$manifest.files[0].destination -cne $RemoteApp -or
        [string]$manifest.files[1].source -cne 'navi.json' -or
        [string]$manifest.files[1].destination -cne $RemoteNavi) {
        throw 'Write-set UX inattendu.'
    }
    if ([string]$manifest.static_alias.destination -cne $RemoteAlias -or
        [string]$manifest.static_alias.target -cne 'k1-control' -or
        [bool]$manifest.static_alias.service_worker_vendor_file_changed) {
        throw 'Alias statique UX inattendu.'
    }
    return $manifest
}

function Get-ApiState {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/machine/k1_control/status'") -join "`n"
    $state = ($raw | ConvertFrom-Json).result
    if (-not $state) { throw 'API K1 Control sans état métier.' }
    return $state
}

function Get-PrinterStatus {
    $url = "http://127.0.0.1:7125/printer/objects/query?print_stats&extruder&heater_bed&bed_mesh&configfile&box&gcode_macro+KCTRL_STATE&k1_control_store&gcode_macro+KCTRL_CAL_PATH_STATE"
    $raw = (Invoke-Remote "curl '$url'") -join "`n"
    $status = ($raw | ConvertFrom-Json).result.status
    if (-not $status) { throw 'Réponse Moonraker sans état Klipper.' }
    return $status
}

function Get-ServerInfo {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/server/info'") -join "`n"
    $info = ($raw | ConvertFrom-Json).result
    if (-not $info) { throw 'Moonraker sans server/info.' }
    return $info
}

function Assert-ServerInfo {
    $info = Get-ServerInfo
    if (-not [bool]$info.klippy_connected -or [string]$info.klippy_state -cne 'ready' -or
        @($info.components) -notcontains 'k1_control' -or
        @($info.components) -notcontains 'k1_control_probe_count' -or
        @($info.failed_components).Count -ne 0 -or @($info.warnings).Count -ne 0) {
        throw "Moonraker non sain : state=$($info.klippy_state) failed=$(@($info.failed_components) -join ',') warnings=$(@($info.warnings) -join ' | ')"
    }
    return $info
}

function Assert-SafeState {
    [void](Assert-ServerInfo)
    $api = Get-ApiState
    if ([bool]$api.busy -or @('idle', 'accepted', 'cancelled', 'failed', 'mesh_rejected', 'restored', 'rolled_back') -notcontains [string]$api.phase) {
        throw "Campagne UI non fermée : phase=$($api.phase) busy=$($api.busy)"
    }
    $status = Get-PrinterStatus
    if ($status.print_stats.state -cne 'standby' -or $status.print_stats.filename) {
        throw "Imprimante non disponible : $($status.print_stats.state)"
    }
    if ([double]$status.extruder.target -ne 0 -or [double]$status.heater_bed.target -ne 0) {
        throw 'Les chauffes ne sont pas coupées.'
    }
    $runtime = $status.'gcode_macro KCTRL_STATE'
    $store = $status.k1_control_store
    $path = $status.'gcode_macro KCTRL_CAL_PATH_STATE'
    if ([int]$runtime.ready -ne 1 -or [int]$runtime.accepted_z_valid -ne 1 -or
        [int]$runtime.session_active -ne 0 -or [int]$runtime.low_moves_armed -ne 0 -or
        -not $store -or $store.integrity -cne 'ok') {
        throw 'Runtime ou stockage Z non sûr.'
    }
    if (@('idle', 'committed', 'cancelled') -notcontains [string]$path.phase -or
        [int]$path.motion_armed -ne 0 -or [int]$path.commit_ready -ne 0) {
        throw 'Chemin Z non fermé.'
    }
    if ($status.bed_mesh.profiles.PSObject.Properties.Name -contains 'K1_TRANSIENT') {
        throw 'Profil mesh transitoire encore présent.'
    }
    if ($status.bed_mesh.profiles.PSObject.Properties.Name -notcontains 'k1_p001_t055_r001_n06x06') {
        throw 'Profil robuste absent.'
    }
    $count = @($status.configfile.settings.bed_mesh.probe_count)
    if ($count.Count -ne 2 -or [int]$count[0] -ne 6 -or [int]$count[1] -ne 6 -or
        [string]$status.configfile.settings.bed_mesh.algorithm -cne 'lagrange') {
        throw 'Configuration bed_mesh chargée autre que 6x6 Lagrange.'
    }
    foreach ($name in @('T1', 'T2')) {
        $unit = $status.box.$name
        if ($unit.state -cne 'connect' -or $unit.version -cne '1.1.3' -or @($unit.material_type).Count -ne 4) {
            throw "CFS $name inattendu ou déconnecté."
        }
    }
    return @{ Api = $api; Printer = $status }
}

function Assert-UnchangedFiles {
    param([Parameter(Mandatory = $true)]$Manifest)
    foreach ($file in $Manifest.unchanged.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne [string]$file.sha256) {
            throw "Fichier hors write-set modifié : $($file.destination)"
        }
    }
}

function Get-RemoteNaviPresence {
    return ((Invoke-Remote "if test -e '$RemoteNavi'; then echo present; else echo absent; fi" | Select-Object -First 1).Trim())
}

function Get-RemoteAliasPresence {
    return ((Invoke-Remote "if test -e '$RemoteAlias' || test -L '$RemoteAlias'; then echo present; else echo absent; fi" | Select-Object -First 1).Trim())
}

function Assert-RemoteBaseline {
    param([Parameter(Mandatory = $true)]$Manifest)
    if ((Get-RemoteSha256 $RemoteApp) -cne [string]$Manifest.baseline.app_js_sha256) {
        throw 'Empreinte distante app.js différente de la base revue.'
    }
    if ((Get-RemoteSha256 $RemoteNavi) -cne [string]$Manifest.baseline.navi_json_sha256) {
        throw 'Empreinte distante navi.json différente de la base revue.'
    }
    if ((Get-RemoteAliasPresence) -cne 'absent') {
        throw 'Alias statique déjà présent hors de la base revue.'
    }
    [void](Invoke-Remote "test ! -e '$RemoteAlias.next' && test ! -L '$RemoteAlias.next'")
    Assert-UnchangedFiles $Manifest
}

function Assert-RemoteFinal {
    param([Parameter(Mandatory = $true)]$Manifest)
    if ((Get-RemoteSha256 $RemoteApp) -cne [string]$Manifest.files[0].sha256) {
        throw 'Empreinte distante app.js finale inattendue.'
    }
    if ((Get-RemoteSha256 $RemoteNavi) -cne [string]$Manifest.files[1].sha256) {
        throw 'Empreinte distante navi.json finale inattendue.'
    }
    [void](Invoke-Remote "test -L '$RemoteAlias' && test `"`$(readlink '$RemoteAlias')`" = 'k1-control'")
    if ((Get-RemoteSha256 "$RemoteAlias/index.html") -cne [string]$Manifest.unchanged.files[4].sha256 -or
        (Get-RemoteSha256 "$RemoteAlias/styles.css") -cne [string]$Manifest.unchanged.files[5].sha256 -or
        (Get-RemoteSha256 "$RemoteAlias/app.js") -cne [string]$Manifest.files[0].sha256) {
        throw 'Alias statique K1 Control inattendu.'
    }
    [void](Invoke-Remote "test `"`$(stat -c '%a' '$RemoteTheme')`" = '755' && test `"`$(stat -c '%a' '$RemoteApp')`" = '644' && test `"`$(stat -c '%a' '$RemoteNavi')`" = '644'")
    Assert-UnchangedFiles $Manifest
}

function Remove-RemoteStaging {
    [void](Invoke-Remote "rm -f '$RemoteStaging/app.js' '$RemoteStaging/navi.json' && rmdir '$RemoteStaging' 2>/dev/null || true")
}

function Invoke-ExactRollback {
    $manifest = Assert-Package
    $appBackup = "$RemoteBackup/app.js.before"
    $naviBackup = "$RemoteBackup/navi.json.before"
    [void](Invoke-Remote "test -f '$appBackup' && test -f '$naviBackup'")
    if ((Get-RemoteSha256 $appBackup) -cne [string]$manifest.baseline.app_js_sha256 -or
        (Get-RemoteSha256 $naviBackup) -cne [string]$manifest.baseline.navi_json_sha256) {
        throw 'Backup statique inattendu.'
    }
    [void](Invoke-Remote "cp '$appBackup' '$RemoteApp.rollback-next' && cp '$naviBackup' '$RemoteNavi.rollback-next' && chmod 0644 '$RemoteApp.rollback-next' '$RemoteNavi.rollback-next' && mv '$RemoteApp.rollback-next' '$RemoteApp' && mv '$RemoteNavi.rollback-next' '$RemoteNavi' && rm -f '$RemoteAlias' '$RemoteAlias.next'")
    Remove-RemoteStaging
    Assert-RemoteBaseline $manifest
    [void](Assert-SafeState)
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "PLAN_CALIBRATION_UI_NAVIGATION_V1_R2_OK gate=$RequiredGate"
    Write-Output 'Conserve app.js, remplace .theme/navi.json et crée un alias statique après backup exact.'
    Write-Output 'Contourne la route de navigation du service worker sans modifier le fichier constructeur.'
    Write-Output 'Corrige les textes starting_z, z_confirmed et accepted sans changer le contrôleur métier.'
    Write-Output 'Aucun chauffage, homing, mouvement, mesh, Z, extrusion, impression ou action CFS.'
    exit 0
}

if ($Action -eq 'Preflight') {
    Assert-RemoteBaseline $manifest
    [void](Assert-SafeState)
    Write-Output 'PREFLIGHT_CALIBRATION_UI_NAVIGATION_V1_R2_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    Assert-RemoteFinal $manifest
    [void](Assert-SafeState)
    Write-Output 'VALIDATE_CALIBRATION_UI_NAVIGATION_V1_R2_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Assert-MutationGate
    Invoke-ExactRollback
    Write-Output "ROLLBACK_CALIBRATION_UI_NAVIGATION_V1_R2_OK capture=$CaptureId"
    exit 0
}

Assert-MutationGate
if ((Get-RemoteSha256 $RemoteApp) -ceq [string]$manifest.files[0].sha256 -and
    (Get-RemoteNaviPresence) -ceq 'present' -and
    (Get-RemoteSha256 $RemoteNavi) -ceq [string]$manifest.files[1].sha256 -and
    (Get-RemoteAliasPresence) -ceq 'present') {
    & $PSCommandPath -Action Validate -PrinterHost $PrinterHost -CaptureId $CaptureId
    New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null
    [pscustomobject]@{
        capture_id = $CaptureId
        gate = $RequiredGate
        action = 'Deploy'
        result = 'DEPLOY_CALIBRATION_UI_NAVIGATION_V1_R2_OK'
        already_present = $true
        remote_write = $false
        service_restart = $false
        calibration_action = $false
        printer_motion = $false
        heater_command = $false
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LocalCapture 'deploy-result.json') -Encoding UTF8
    Write-Output "DEPLOY_CALIBRATION_UI_NAVIGATION_V1_R2_OK capture=$CaptureId already_present=true remote_write=false"
    exit 0
}

Assert-RemoteBaseline $manifest
[void](Assert-SafeState)
New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup'")
    [void](Invoke-Remote "cp '$RemoteApp' '$RemoteBackup/app.js.before' && cp '$RemoteNavi' '$RemoteBackup/navi.json.before'")
    if ((Get-RemoteSha256 "$RemoteBackup/app.js.before") -cne [string]$manifest.baseline.app_js_sha256 -or
        (Get-RemoteSha256 "$RemoteBackup/navi.json.before") -cne [string]$manifest.baseline.navi_json_sha256) {
        throw 'Backup statique non conforme.'
    }
    $MutationStarted = $true
    [void](Invoke-Remote "mkdir -p '$RemoteStaging'")
    Copy-ToRemote (Join-Path $PackageRoot ([string]$manifest.files[0].source)) "$RemoteStaging/app.js"
    Copy-ToRemote (Join-Path $PackageRoot ([string]$manifest.files[1].source)) "$RemoteStaging/navi.json"
    if ((Get-RemoteSha256 "$RemoteStaging/app.js") -cne [string]$manifest.files[0].sha256 -or
        (Get-RemoteSha256 "$RemoteStaging/navi.json") -cne [string]$manifest.files[1].sha256) {
        throw 'Transfert statique non conforme.'
    }
    [void](Invoke-Remote "cp '$RemoteStaging/app.js' '$RemoteApp.next' && mkdir -p '$RemoteTheme' && cp '$RemoteStaging/navi.json' '$RemoteNavi.next' && ln -s 'k1-control' '$RemoteAlias.next' && chmod 0755 '$RemoteTheme' && chmod 0644 '$RemoteApp.next' '$RemoteNavi.next' && mv '$RemoteApp.next' '$RemoteApp' && mv '$RemoteNavi.next' '$RemoteNavi' && mv '$RemoteAlias.next' '$RemoteAlias'")
    & $PSCommandPath -Action Validate -PrinterHost $PrinterHost -CaptureId $CaptureId
    Remove-RemoteStaging
    [pscustomobject]@{
        capture_id = $CaptureId
        gate = $RequiredGate
        action = 'Deploy'
        result = 'DEPLOY_CALIBRATION_UI_NAVIGATION_V1_R2_OK'
        service_restart = $false
        calibration_action = $false
        printer_motion = $false
        heater_command = $false
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LocalCapture 'deploy-result.json') -Encoding UTF8
    Write-Output "DEPLOY_CALIBRATION_UI_NAVIGATION_V1_R2_OK capture=$CaptureId"
}
catch {
    $failure = $_
    if ($MutationStarted) {
        try { Invoke-ExactRollback }
        catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
