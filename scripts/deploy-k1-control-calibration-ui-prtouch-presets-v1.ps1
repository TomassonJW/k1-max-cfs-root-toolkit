[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-calibration-ui-prtouch-presets-v1',
    [switch]$Execute,
    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-PRESETS-V1'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\calibration-ui-prtouch-presets-v1'
$ManifestPath = Join-Path $PackageRoot 'deployment-manifest.json'
$ContractPath = Join-Path $PackageRoot 'calibration-ui-prtouch-presets-contract.json'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteApp = "$RemoteRoot/current/www/mainsail/k1-control/app.js"
$RemoteIndex = "$RemoteRoot/current/www/mainsail/k1-control/index.html"
$RemoteBackup = "$RemoteRoot/backups/$CaptureId-calibration-ui-prtouch-presets-v1"
$RemoteStaging = "$RemoteRoot/tmp/$CaptureId-calibration-ui-prtouch-presets-v1"
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
        throw 'Identité du paquet PRTOUCH-PRESETS-V1 inattendue.'
    }
    if ((Get-LocalSha256 $PSCommandPath) -cne [string]$manifest.deployer.sha256) {
        throw 'Empreinte du déployeur PRTOUCH-PRESETS-V1 inattendue.'
    }
    if ((Get-LocalSha256 $ContractPath) -cne [string]$manifest.contract.sha256) {
        throw 'Empreinte du contrat PRTOUCH-PRESETS-V1 inattendue.'
    }
    foreach ($file in $manifest.files) {
        $source = Join-Path $PackageRoot ([string]$file.source)
        if ((Get-LocalSha256 $source) -cne [string]$file.sha256) {
            throw "Empreinte locale inattendue : $($file.source)"
        }
    }
    if (@($manifest.files).Count -ne 2 -or
        [string]$manifest.files[0].source -cne 'index.html' -or
        [string]$manifest.files[1].source -cne 'app.js') {
        throw 'Write-set statique inattendu.'
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
    $url = "http://127.0.0.1:7125/printer/objects/query?print_stats&extruder&heater_bed&bed_mesh&gcode_macro+KCTRL_STATE&k1_control_store&gcode_macro+KCTRL_CAL_PATH_STATE"
    $raw = (Invoke-Remote "curl '$url'") -join "`n"
    $status = ($raw | ConvertFrom-Json).result.status
    if (-not $status) { throw 'Réponse Moonraker sans état Klipper.' }
    return $status
}

function Assert-SafeState {
    $api = Get-ApiState
    if ([bool]$api.busy -or @('idle', 'accepted', 'cancelled', 'restored', 'rolled_back') -notcontains [string]$api.phase) {
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
    return @{ Api = $api; Printer = $status }
}

function Assert-RemoteFiles {
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [Parameter(Mandatory = $true)][string]$ExpectedIndexHash,
        [Parameter(Mandatory = $true)][string]$ExpectedAppHash
    )
    if ((Get-RemoteSha256 $RemoteIndex) -cne $ExpectedIndexHash) {
        throw 'Empreinte distante index.html inattendue.'
    }
    if ((Get-RemoteSha256 $RemoteApp) -cne $ExpectedAppHash) {
        throw 'Empreinte distante app.js inattendue.'
    }
    foreach ($file in $Manifest.unchanged.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne [string]$file.sha256) {
            throw "Fichier hors write-set modifié : $($file.destination)"
        }
    }
}

function Remove-RemoteStaging {
    [void](Invoke-Remote "rm -f '$RemoteStaging/index.html' '$RemoteStaging/app.js' && rmdir '$RemoteStaging' 2>/dev/null || true")
}

function Invoke-ExactRollback {
    $manifest = Assert-Package
    $indexBackup = "$RemoteBackup/index.html.before"
    $appBackup = "$RemoteBackup/app.js.before"
    [void](Invoke-Remote "test -f '$indexBackup' && test -f '$appBackup'")
    if ((Get-RemoteSha256 $indexBackup) -cne [string]$manifest.baseline.index_html_sha256 -or
        (Get-RemoteSha256 $appBackup) -cne [string]$manifest.baseline.app_js_sha256) {
        throw 'Backup statique inattendu.'
    }
    [void](Invoke-Remote "cp '$indexBackup' '$RemoteIndex.rollback-next' && cp '$appBackup' '$RemoteApp.rollback-next' && chmod 0644 '$RemoteIndex.rollback-next' '$RemoteApp.rollback-next' && mv '$RemoteIndex.rollback-next' '$RemoteIndex' && mv '$RemoteApp.rollback-next' '$RemoteApp'")
    Remove-RemoteStaging
    Assert-RemoteFiles $manifest ([string]$manifest.baseline.index_html_sha256) ([string]$manifest.baseline.app_js_sha256)
    [void](Assert-SafeState)
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "PLAN_CALIBRATION_UI_PRTOUCH_PRESETS_V1_OK gate=$RequiredGate"
    Write-Output 'Effet: backup exact et remplacement atomique de index.html et app.js; aucun restart.'
    Write-Output 'Le choix 4x4 incompatible disparaît; 3, 5, 6, 9, 11 et 15 restent disponibles.'
    Write-Output 'Aucun chauffage, homing, mouvement, mesh, Z, extrusion, impression ou action CFS.'
    exit 0
}

if ($Action -eq 'Preflight') {
    Assert-RemoteFiles $manifest ([string]$manifest.baseline.index_html_sha256) ([string]$manifest.baseline.app_js_sha256)
    [void](Assert-SafeState)
    Write-Output 'PREFLIGHT_CALIBRATION_UI_PRTOUCH_PRESETS_V1_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    Assert-RemoteFiles $manifest ([string]$manifest.files[0].sha256) ([string]$manifest.files[1].sha256)
    [void](Invoke-Remote "grep -q 'value=.15.' '$RemoteIndex' && ! grep -q 'value=.4.' '$RemoteIndex' && grep -q 'matrixField.value = .5.' '$RemoteApp'")
    [void](Assert-SafeState)
    Write-Output 'VALIDATE_CALIBRATION_UI_PRTOUCH_PRESETS_V1_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Assert-MutationGate
    Invoke-ExactRollback
    Write-Output "ROLLBACK_CALIBRATION_UI_PRTOUCH_PRESETS_V1_OK capture=$CaptureId"
    exit 0
}

Assert-MutationGate
Assert-RemoteFiles $manifest ([string]$manifest.baseline.index_html_sha256) ([string]$manifest.baseline.app_js_sha256)
[void](Assert-SafeState)
New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup'")
    [void](Invoke-Remote "cp '$RemoteIndex' '$RemoteBackup/index.html.before' && cp '$RemoteApp' '$RemoteBackup/app.js.before'")
    if ((Get-RemoteSha256 "$RemoteBackup/index.html.before") -cne [string]$manifest.baseline.index_html_sha256 -or
        (Get-RemoteSha256 "$RemoteBackup/app.js.before") -cne [string]$manifest.baseline.app_js_sha256) {
        throw 'Backup statique non conforme.'
    }
    $MutationStarted = $true
    [void](Invoke-Remote "mkdir -p '$RemoteStaging'")
    Copy-ToRemote (Join-Path $PackageRoot ([string]$manifest.files[0].source)) "$RemoteStaging/index.html"
    Copy-ToRemote (Join-Path $PackageRoot ([string]$manifest.files[1].source)) "$RemoteStaging/app.js"
    if ((Get-RemoteSha256 "$RemoteStaging/index.html") -cne [string]$manifest.files[0].sha256 -or
        (Get-RemoteSha256 "$RemoteStaging/app.js") -cne [string]$manifest.files[1].sha256) {
        throw 'Transfert statique non conforme.'
    }
    [void](Invoke-Remote "cp '$RemoteStaging/index.html' '$RemoteIndex.next' && cp '$RemoteStaging/app.js' '$RemoteApp.next' && chmod 0644 '$RemoteIndex.next' '$RemoteApp.next' && mv '$RemoteIndex.next' '$RemoteIndex' && mv '$RemoteApp.next' '$RemoteApp'")
    & $PSCommandPath -Action Validate -PrinterHost $PrinterHost -CaptureId $CaptureId
    Remove-RemoteStaging
    [pscustomobject]@{
        capture_id = $CaptureId
        gate = $RequiredGate
        action = 'Deploy'
        result = 'DEPLOY_CALIBRATION_UI_PRTOUCH_PRESETS_V1_OK'
        service_restart = $false
        calibration_action = $false
        printer_motion = $false
        heater_command = $false
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LocalCapture 'deploy-result.json') -Encoding UTF8
    Write-Output "DEPLOY_CALIBRATION_UI_PRTOUCH_PRESETS_V1_OK capture=$CaptureId"
}
catch {
    $failure = $_
    if ($MutationStarted) {
        try { Invoke-ExactRollback }
        catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
