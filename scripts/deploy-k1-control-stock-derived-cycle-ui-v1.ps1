[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-stock-derived-cycle-ui-v1',
    [switch]$Execute,
    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-STOCK-DERIVED-CYCLE-UI-V1'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-cycle-ui-v1'
$ManifestPath = Join-Path $PackageRoot 'deployment-manifest.json'
$ContractPath = Join-Path $PackageRoot 'contract.json'
$ActivationDeployer = Join-Path $WorkspaceRoot 'scripts\deploy-k1-control-stock-derived-cycle-activation-v1.ps1'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteWeb = "$RemoteRoot/current/www/mainsail/k1-control"
$RemoteBackup = "$RemoteRoot/backups/$CaptureId-stock-derived-cycle-ui-v1"
$RemoteStaging = "$RemoteRoot/tmp/$CaptureId-stock-derived-cycle-ui-v1"
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

function Test-RemoteFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    & ssh.exe -o BatchMode=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o ConnectTimeout=8 $PrinterHost "test -f '$Path'"
    if ($LASTEXITCODE -eq 0) { return $true }
    if ($LASTEXITCODE -eq 1) { return $false }
    throw "Presence distante indeterminee : $Path"
}

function Assert-Package {
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    $contract = Get-Content -LiteralPath $ContractPath -Raw | ConvertFrom-Json
    if ($manifest.contract_id -cne $RequiredGate -or $contract.contract_id -cne $RequiredGate) {
        throw 'Identite du paquet UI inattendue.'
    }
    if ((Get-LocalSha256 $PSCommandPath) -cne [string]$manifest.deployer.sha256) {
        throw 'Empreinte du deployeur UI inattendue.'
    }
    if ((Get-LocalSha256 $ContractPath) -cne [string]$manifest.contract.sha256) {
        throw 'Empreinte du contrat UI inattendue.'
    }
    $expected = @('index.html', 'app.js', 'styles.css')
    if (@($manifest.files).Count -ne $expected.Count) { throw 'Write-set statique inattendu.' }
    for ($index = 0; $index -lt $expected.Count; $index += 1) {
        $file = $manifest.files[$index]
        if ([string]$file.source -cne $expected[$index]) { throw 'Ordre du write-set statique inattendu.' }
        if ((Get-LocalSha256 (Join-Path $PackageRoot ([string]$file.source))) -cne [string]$file.sha256) {
            throw "Empreinte locale inattendue : $($file.source)"
        }
    }
    return $manifest
}

function Assert-ActivationIdle {
    $activationCapture = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-stock-derived-cycle-activation-v1'
    & $ActivationDeployer -Action Validate -CaptureId $activationCapture -Execute -Gate 'G4-K1-CONTROL-STOCK-DERIVED-CYCLE-ACTIVATION-IDLE-V1'
    if ($LASTEXITCODE -ne 0) { throw 'Le proprietaire actif au repos n est pas valide.' }
}

function Assert-BaselineFiles {
    param([Parameter(Mandatory = $true)]$Manifest)
    foreach ($item in $Manifest.baseline.existing) {
        $path = [string]$item.destination
        if (-not (Test-RemoteFile $path) -or (Get-RemoteSha256 $path) -cne [string]$item.sha256) {
            throw "Fichier de base inattendu : $path"
        }
    }
    Assert-UnchangedCalibration $Manifest
}

function Assert-UnchangedCalibration {
    param([Parameter(Mandatory = $true)]$Manifest)
    foreach ($item in $Manifest.unchanged.calibration) {
        $path = [string]$item.destination
        if (-not (Test-RemoteFile $path) -or (Get-RemoteSha256 $path) -cne [string]$item.sha256) {
            throw "Calibration hors write-set modifiee : $path"
        }
    }
}

function Assert-CandidateFiles {
    param([Parameter(Mandatory = $true)]$Manifest)
    foreach ($item in $Manifest.files) {
        $path = "$RemoteWeb/$($item.source)"
        if (-not (Test-RemoteFile $path) -or (Get-RemoteSha256 $path) -cne [string]$item.sha256) {
            throw "Fichier UI candidat inattendu : $path"
        }
    }
    Assert-UnchangedCalibration $Manifest
}

function Remove-RemoteStaging {
    [void](Invoke-Remote "rm -f '$RemoteStaging/index.html' '$RemoteStaging/app.js' '$RemoteStaging/styles.css' && rmdir '$RemoteStaging' 2>/dev/null || true")
}

function Invoke-ExactRollback {
    $manifest = Assert-Package
    [void](Invoke-Remote "test -f '$RemoteBackup/index.html.before' && test -f '$RemoteBackup/app.js.before' && test -f '$RemoteBackup/styles.css.before'")
    if ((Get-RemoteSha256 "$RemoteBackup/index.html.before") -cne [string]$manifest.baseline.existing[0].sha256 -or
        (Get-RemoteSha256 "$RemoteBackup/app.js.before") -cne [string]$manifest.baseline.existing[1].sha256 -or
        (Get-RemoteSha256 "$RemoteBackup/styles.css.before") -cne [string]$manifest.baseline.existing[2].sha256) {
        throw 'Backup statique inattendu.'
    }
    [void](Invoke-Remote "cp '$RemoteBackup/index.html.before' '$RemoteWeb/index.html.rollback-next' && cp '$RemoteBackup/app.js.before' '$RemoteWeb/app.js.rollback-next' && cp '$RemoteBackup/styles.css.before' '$RemoteWeb/styles.css.rollback-next' && chmod 0644 '$RemoteWeb/index.html.rollback-next' '$RemoteWeb/app.js.rollback-next' '$RemoteWeb/styles.css.rollback-next' && mv '$RemoteWeb/index.html.rollback-next' '$RemoteWeb/index.html' && mv '$RemoteWeb/app.js.rollback-next' '$RemoteWeb/app.js' && mv '$RemoteWeb/styles.css.rollback-next' '$RemoteWeb/styles.css'")
    Remove-RemoteStaging
    Assert-BaselineFiles $manifest
    Assert-ActivationIdle
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "PLAN_STOCK_DERIVED_CYCLE_UI_V1_OK gate=$RequiredGate"
    Write-Output 'Trois fichiers statiques racine seulement; sous-dossier calibration strictement inchange.'
    Write-Output 'Aucun restart, G-code, chauffage, mouvement, filament, CFS, palpage ou mesh.'
    Write-Output 'Le bouton PASS camera reste absent tant que les references physiques manquent.'
    exit 0
}

if ($Action -eq 'Preflight') {
    Assert-BaselineFiles $manifest
    Assert-ActivationIdle
    Write-Output 'PREFLIGHT_STOCK_DERIVED_CYCLE_UI_V1_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    Assert-CandidateFiles $manifest
    Assert-ActivationIdle
    Write-Output 'VALIDATE_STOCK_DERIVED_CYCLE_UI_V1_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Assert-MutationGate
    Invoke-ExactRollback
    Write-Output "ROLLBACK_STOCK_DERIVED_CYCLE_UI_V1_OK capture=$CaptureId"
    exit 0
}

Assert-MutationGate
$alreadyPresent = $true
foreach ($item in $manifest.files) {
    $path = "$RemoteWeb/$($item.source)"
    if (-not (Test-RemoteFile $path) -or (Get-RemoteSha256 $path) -cne [string]$item.sha256) {
        $alreadyPresent = $false
        break
    }
}
if ($alreadyPresent) {
    & $PSCommandPath -Action Validate -PrinterHost $PrinterHost -CaptureId $CaptureId
    Write-Output "DEPLOY_STOCK_DERIVED_CYCLE_UI_V1_OK capture=$CaptureId already_present=true remote_write=false"
    exit 0
}

Assert-BaselineFiles $manifest
Assert-ActivationIdle
New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup' '$RemoteStaging'")
    [void](Invoke-Remote "cp '$RemoteWeb/index.html' '$RemoteBackup/index.html.before' && cp '$RemoteWeb/app.js' '$RemoteBackup/app.js.before' && cp '$RemoteWeb/styles.css' '$RemoteBackup/styles.css.before'")
    if ((Get-RemoteSha256 "$RemoteBackup/index.html.before") -cne [string]$manifest.baseline.existing[0].sha256 -or
        (Get-RemoteSha256 "$RemoteBackup/app.js.before") -cne [string]$manifest.baseline.existing[1].sha256 -or
        (Get-RemoteSha256 "$RemoteBackup/styles.css.before") -cne [string]$manifest.baseline.existing[2].sha256) {
        throw 'Backup statique non conforme.'
    }
    $MutationStarted = $true
    foreach ($item in $manifest.files) {
        Copy-ToRemote (Join-Path $PackageRoot ([string]$item.source)) "$RemoteStaging/$($item.source)"
        if ((Get-RemoteSha256 "$RemoteStaging/$($item.source)") -cne [string]$item.sha256) {
            throw "Transfert statique non conforme : $($item.source)"
        }
    }
    foreach ($item in $manifest.files) {
        [void](Invoke-Remote "cp '$RemoteStaging/$($item.source)' '$RemoteWeb/$($item.source).next' && chmod 0644 '$RemoteWeb/$($item.source).next' && mv '$RemoteWeb/$($item.source).next' '$RemoteWeb/$($item.source)'")
    }
    & $PSCommandPath -Action Validate -PrinterHost $PrinterHost -CaptureId $CaptureId
    Remove-RemoteStaging
    [pscustomobject]@{
        capture_id = $CaptureId
        gate = $RequiredGate
        action = 'Deploy'
        result = 'DEPLOY_STOCK_DERIVED_CYCLE_UI_V1_OK'
        remote_write = $true
        service_restart = $false
        starts_cycle = $false
        heater_action = $false
        motion_action = $false
        filament_action = $false
        cfs_action = $false
        probe_action = $false
        mesh_recalculation = $false
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LocalCapture 'deploy-result.json') -Encoding UTF8
    Write-Output "DEPLOY_STOCK_DERIVED_CYCLE_UI_V1_OK capture=$CaptureId"
}
catch {
    $failure = $_
    if ($MutationStarted) {
        try { Invoke-ExactRollback }
        catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
