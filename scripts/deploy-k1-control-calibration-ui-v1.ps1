[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-calibration-ui-v1',
    [switch]$Execute,
    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-CALIBRATION-UI-V1'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\calibration-ui-v1'
$ManifestPath = Join-Path $PackageRoot 'deployment-manifest.json'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteCurrent = "$RemoteRoot/current"
$RemoteConfig = "$RemoteCurrent/config/moonraker.conf"
$RemoteComponents = "$RemoteCurrent/moonraker/moonraker/moonraker/components"
$RemoteUi = "$RemoteCurrent/www/mainsail/k1-control"
$MoonrakerService = '/etc/init.d/S56k1_control_moonraker'
$RemoteBackup = "$RemoteRoot/backups/$CaptureId-calibration-ui-v1"
$RemoteStaging = "$RemoteRoot/tmp/$CaptureId-calibration-ui-v1"
$LocalCapture = Join-Path $WorkspaceRoot "inventory\raw\$CaptureId"
$MutationStarted = $false

function Assert-MutationGate {
    if (-not $Execute -or $Gate -cne $RequiredGate) {
        throw "Action bloquee : -Execute et -Gate '$RequiredGate' sont obligatoires."
    }
}

function Get-LocalSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    $stream = [IO.File]::OpenRead((Resolve-Path -LiteralPath $Path).Path)
    try {
        $sha = [Security.Cryptography.SHA256]::Create()
        try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
        finally { $sha.Dispose() }
    }
    finally { $stream.Dispose() }
}

function Invoke-Remote {
    param([Parameter(Mandatory = $true)][string]$Command)
    $args = @(
        '-o', 'BatchMode=yes',
        '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no',
        '-o', 'ConnectTimeout=8',
        $PrinterHost,
        $Command
    )
    $output = & ssh.exe @args 2>&1
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
    $args = @(
        '-o', 'BatchMode=yes',
        '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no',
        '-o', 'ConnectTimeout=8',
        (Resolve-Path -LiteralPath $Source).Path,
        "$PrinterHost`:$Destination"
    )
    & scp.exe @args
    if ($LASTEXITCODE -ne 0) { throw "Transfert SCP KO : $Destination" }
}

function Get-RemoteSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    $line = Invoke-Remote "sha256sum '$Path'"
    return ((($line | Select-Object -First 1) -split '\s+')[0]).ToLowerInvariant()
}

function Assert-Package {
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ($manifest.contract_id -cne $RequiredGate -or $manifest.status -cne 'offline_review_candidate') {
        throw 'Manifeste CALIBRATION-UI-V1 inattendu.'
    }
    foreach ($file in $manifest.files) {
        $local = Join-Path $PackageRoot ([string]$file.source)
        if ((Get-LocalSha256 $local) -cne ([string]$file.sha256)) {
            throw "Empreinte locale inattendue : $($file.source)"
        }
    }
    return $manifest
}

function Get-PrinterStatus {
    $url = "http://127.0.0.1:7125/printer/objects/query?print_stats&extruder&heater_bed&gcode_macro%20KCTRL_STATE&gcode_macro%20KCTRL_CAL_PATH_STATE"
    $raw = (Invoke-Remote "curl -fsS '$url'") -join "`n"
    $payload = $raw | ConvertFrom-Json
    if (-not $payload.result.status) { throw 'Réponse Moonraker sans état Klipper.' }
    return $payload.result.status
}

function Assert-PrinterIdle {
    $status = Get-PrinterStatus
    if ($status.print_stats.state -cne 'standby' -or $status.print_stats.filename) {
        throw "Imprimante non disponible : $($status.print_stats.state)"
    }
    if ([double]$status.extruder.target -ne 0 -or [double]$status.heater_bed.target -ne 0) {
        throw 'Une chauffe est déjà demandée.'
    }
    $runtime = $status.'gcode_macro KCTRL_STATE'
    if ([int]$runtime.ready -ne 1 -or [int]$runtime.session_active -ne 0 -or [int]$runtime.low_moves_armed -ne 0) {
        throw "Le runtime K1 Control n'est pas vide et fermé."
    }
    $path = $status.'gcode_macro KCTRL_CAL_PATH_STATE'
    if ([string]$path.phase -cne 'idle' -or [int]$path.motion_armed -ne 0) {
        throw "Le chemin Z n'est pas fermé."
    }
    return $status
}

function Assert-BasePreflight {
    param([Parameter(Mandatory = $true)]$Manifest)
    [void](Invoke-Remote "test -x '$MoonrakerService' && test -S /tmp/klippy_uds && test -f '$RemoteConfig'")
    $baseline = Get-RemoteSha256 $RemoteConfig
    if ($baseline -cne ([string]$Manifest.baseline.moonraker_conf_sha256)) {
        throw "Base moonraker.conf inattendue : $baseline"
    }
    $newPaths = @(
        "$RemoteComponents/k1_control.py",
        "$RemoteComponents/k1_control_calibration_core.py",
        "$RemoteUi/index.html",
        "$RemoteUi/app.js",
        "$RemoteUi/styles.css"
    )
    foreach ($path in $newPaths) {
        [void](Invoke-Remote "test ! -e '$path'")
    }
    [void](Invoke-Remote "test ! -e '$RemoteRoot/state/k1-control-calibration-workflow.json'")
    [void](Assert-PrinterIdle)
}

function Wait-Moonraker {
    param([int]$Attempts = 60)
    $last = 'aucune réponse'
    for ($index = 1; $index -le $Attempts; $index++) {
        try {
            [void](Invoke-Remote "curl -fsS 'http://127.0.0.1:7125/server/info'")
            return
        }
        catch { $last = $_.Exception.Message }
        Start-Sleep -Seconds 1
    }
    throw "Moonraker non stabilisé : $last"
}

function Invoke-ExactRollback {
    [void](Invoke-Remote "test -f '$RemoteBackup/moonraker.conf.before'")
    $backupHash = Get-RemoteSha256 "$RemoteBackup/moonraker.conf.before"
    $manifest = Assert-Package
    if ($backupHash -cne ([string]$manifest.baseline.moonraker_conf_sha256)) {
        throw 'Le backup moonraker.conf ne correspond pas à la base revue.'
    }
    [void](Invoke-Remote "cp '$RemoteBackup/moonraker.conf.before' '$RemoteConfig.rollback-next' && mv '$RemoteConfig.rollback-next' '$RemoteConfig'")
    [void](Invoke-Remote "rm -f '$RemoteComponents/k1_control.py' '$RemoteComponents/k1_control_calibration_core.py' '$RemoteComponents/__pycache__/k1_control.cpython-38.pyc' '$RemoteComponents/__pycache__/k1_control_calibration_core.cpython-38.pyc'")
    [void](Invoke-Remote "rm -f '$RemoteUi/index.html' '$RemoteUi/app.js' '$RemoteUi/styles.css' && rmdir '$RemoteUi' 2>/dev/null || true")
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    if ((Get-RemoteSha256 $RemoteConfig) -cne $backupHash) {
        throw 'Rollback moonraker.conf incomplet.'
    }
    [void](Assert-PrinterIdle)
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "PLAN_CALIBRATION_UI_V1_OK gate=$RequiredGate"
    Write-Output 'Effet: backup exact, 2 composants Python, 3 fichiers UI, moonraker.conf, restart Moonraker seulement.'
    Write-Output 'Aucun chauffage, homing, mouvement, mesh, Z, extrusion, impression ou action CFS.'
    exit 0
}

if ($Action -eq 'Preflight') {
    Assert-BasePreflight $manifest
    Write-Output 'PREFLIGHT_CALIBRATION_UI_V1_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    foreach ($file in $manifest.files) {
        if ((Get-RemoteSha256 ([string]$file.destination)) -cne ([string]$file.sha256)) {
            throw "Empreinte distante inattendue : $($file.destination)"
        }
    }
    $raw = (Invoke-Remote "curl -fsS 'http://127.0.0.1:7125/machine/k1_control/status'") -join "`n"
    $state = ($raw | ConvertFrom-Json).result
    if (-not $state -or $state.busy -or $state.phase -cne 'idle' -or $state.backup_available) {
        throw 'Le composant K1 Control ne démarre pas dans son état vide.'
    }
    [void](Invoke-Remote "test -f '$RemoteUi/index.html' && grep -q 'Interface réelle' '$RemoteUi/index.html'")
    [void](Assert-PrinterIdle)
    Write-Output 'VALIDATE_CALIBRATION_UI_V1_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Assert-MutationGate
    Invoke-ExactRollback
    Write-Output "ROLLBACK_CALIBRATION_UI_V1_OK capture=$CaptureId"
    exit 0
}

Assert-MutationGate
Assert-BasePreflight $manifest
New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup' && cp '$RemoteConfig' '$RemoteBackup/moonraker.conf.before'")
    if ((Get-RemoteSha256 "$RemoteBackup/moonraker.conf.before") -cne ([string]$manifest.baseline.moonraker_conf_sha256)) {
        throw 'Backup moonraker.conf différent de la base revue.'
    }
    $MutationStarted = $true
    [void](Invoke-Remote "mkdir -p '$RemoteStaging'")
    foreach ($file in $manifest.files) {
        $stagedName = ([string]$file.source).Replace('/', '__')
        Copy-ToRemote (Join-Path $PackageRoot ([string]$file.source)) "$RemoteStaging/$stagedName"
        if ((Get-RemoteSha256 "$RemoteStaging/$stagedName") -cne ([string]$file.sha256)) {
            throw "Transfert non conforme : $($file.source)"
        }
    }
    $python = "$RemoteCurrent/moonraker/moonraker-env/bin/python"
    $compileCommand = "'$python' -c `"compile(open('$RemoteStaging/k1_control.py').read(), 'k1_control.py', 'exec'); compile(open('$RemoteStaging/k1_control_calibration_core.py').read(), 'k1_control_calibration_core.py', 'exec')`""
    [void](Invoke-Remote $compileCommand)
    [void](Invoke-Remote "mkdir -p '$RemoteUi'")
    foreach ($file in $manifest.files) {
        $destination = [string]$file.destination
        $stagedName = ([string]$file.source).Replace('/', '__')
        [void](Invoke-Remote "cp '$RemoteStaging/$stagedName' '$destination.next' && chmod 0644 '$destination.next' && mv '$destination.next' '$destination'")
    }
    [void](Invoke-Remote "'$MoonrakerService' restart")
    Wait-Moonraker
    & $PSCommandPath -Action Validate -PrinterHost $PrinterHost -CaptureId $CaptureId
    [void](Invoke-Remote "rm -f '$RemoteStaging/moonraker.conf' '$RemoteStaging/k1_control.py' '$RemoteStaging/k1_control_calibration_core.py' '$RemoteStaging/www__index.html' '$RemoteStaging/www__app.js' '$RemoteStaging/www__styles.css' && rmdir '$RemoteStaging' 2>/dev/null || true")
    [pscustomobject]@{
        capture_id = $CaptureId
        gate = $RequiredGate
        action = 'Deploy'
        result = 'DEPLOY_CALIBRATION_UI_V1_OK'
        printer_motion = $false
        heater_command = $false
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LocalCapture 'deploy-result.json') -Encoding UTF8
    Write-Output "DEPLOY_CALIBRATION_UI_V1_OK capture=$CaptureId"
}
catch {
    $failure = $_
    if ($MutationStarted) {
        try { Invoke-ExactRollback }
        catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
