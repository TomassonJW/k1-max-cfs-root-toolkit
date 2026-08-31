[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-stock-derived-cycle-selected-route-recovery-v1',
    [switch]$Execute,
    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-STOCK-DERIVED-CYCLE-SELECTED-ROUTE-RECOVERY-V1'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-cycle-activation-v1'
$ManifestPath = Join-Path $PackageRoot 'deployment-manifest.json'
$ComponentPath = Join-Path $PackageRoot 'moonraker_component.py'
$RemoteValidatorPath = Join-Path $PackageRoot 'remote_validate_active_idle.py'
$ActivationDeployer = Join-Path $WorkspaceRoot 'scripts\deploy-k1-control-stock-derived-cycle-activation-v1.ps1'
$RemoteComponent = '/usr/data/k1-control-v1/current/moonraker/moonraker/moonraker/components/k1_control_stock_cycle.py'
$RemoteService = '/etc/init.d/S56k1_control_moonraker'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteBackup = "$RemoteRoot/backups/$CaptureId/stock-derived-cycle-selected-route-recovery-v1"
$RemoteStaging = "$RemoteRoot/staging/$CaptureId-stock-derived-cycle-selected-route-recovery-v1.py"
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

function Invoke-RemoteStdin {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string]$StandardInput
    )
    $arguments = @(
        '-o', 'BatchMode=yes',
        '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no',
        '-o', 'ConnectTimeout=8',
        $PrinterHost,
        $Command
    )
    $output = $StandardInput | & ssh.exe @arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Commande distante stdin KO : $Command`n$($output -join "`n")"
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

function Get-StockStatus {
    $output = Invoke-Remote "/usr/bin/curl 'http://127.0.0.1:7125/machine/k1_control/stock-cycle/status'"
    $payload = (($output -join "`n") | ConvertFrom-Json)
    if ($null -eq $payload.result) { throw 'Reponse stock-cycle invalide.' }
    return $payload.result
}

function Wait-Moonraker {
    $lastFailure = 'none'
    for ($attempt = 1; $attempt -le 60; $attempt += 1) {
        try { return Get-StockStatus }
        catch { $lastFailure = $_.Exception.Message }
        if ($attempt -lt 60) { Start-Sleep -Seconds 1 }
    }
    throw "Moonraker indisponible apres restart : $lastFailure"
}

function Invoke-IdleValidator {
    $program = [IO.File]::ReadAllText($RemoteValidatorPath).Replace("`r`n", "`n")
    $output = Invoke-RemoteStdin '/usr/share/klippy-env/bin/python -B -' $program
    if (($output | Select-Object -Last 1) -cne 'REMOTE_STOCK_DERIVED_CYCLE_ACTIVATION_IDLE_VALIDATE_OK') {
        throw "Validation active idle KO : $($output -join "`n")"
    }
    return @($output)
}

function Assert-Package {
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    $patch = $manifest.recovery_patch
    if ($patch.gate -cne $RequiredGate -or [string]$patch.destination -cne $RemoteComponent) {
        throw 'Contrat de correctif inattendu.'
    }
    if ((Get-LocalSha256 $ComponentPath) -cne [string]$patch.after_sha256) {
        throw 'Composant local non fige.'
    }
    if ((Get-LocalSha256 $PSCommandPath) -cne [string]$patch.deployer_sha256) {
        throw 'Deployeur du correctif non fige.'
    }
    return $manifest
}

function Assert-IdleStatus {
    param(
        [Parameter(Mandatory = $true)]$Status,
        [Parameter(Mandatory = $true)][bool]$ExpectRecoveryField
    )
    if (
        $Status.enabled -ne $true -or
        [string]$Status.phase -cne 'idle' -or
        $null -ne $Status.active_route -or
        [int]$Status.effect_dispatch_count -ne 0 -or
        $Status.run_state_present -ne $false
    ) {
        throw 'Le proprietaire stock-derived n est pas au repos strict.'
    }
    $hasField = $Status.PSObject.Properties.Name -contains 'cutter_access_reference'
    if ($hasField -ne $ExpectRecoveryField) {
        throw 'Marqueur de version du correctif inattendu.'
    }
}

function Invoke-ExactRollback {
    param([Parameter(Mandatory = $true)]$Manifest)
    $patch = $Manifest.recovery_patch
    [void](Invoke-Remote "test -f '$RemoteBackup/k1_control_stock_cycle.py.before'")
    if ((Get-RemoteSha256 "$RemoteBackup/k1_control_stock_cycle.py.before") -cne [string]$patch.before_sha256) {
        throw 'Backup du composant inattendu.'
    }
    [void](Invoke-Remote "cp '$RemoteBackup/k1_control_stock_cycle.py.before' '$RemoteComponent.rollback-next' && chmod 0644 '$RemoteComponent.rollback-next' && mv '$RemoteComponent.rollback-next' '$RemoteComponent'")
    [void](Invoke-Remote "rm -f '$RemoteStaging'")
    [void](Invoke-Remote "'$RemoteService' restart")
    $status = Wait-Moonraker
    Assert-IdleStatus $status $false
    [void](Invoke-IdleValidator)
}

$manifest = Assert-Package
$patch = $manifest.recovery_patch

if ($Action -eq 'Plan') {
    Write-Output "PLAN_STOCK_DERIVED_CYCLE_SELECTED_ROUTE_RECOVERY_V1_OK gate=$RequiredGate"
    Write-Output 'Un composant Moonraker remplace, backup exact, restart Moonraker dedie seulement.'
    Write-Output 'Aucun G-code, chauffe, mouvement, filament, trame CFS, palpage ou mesh.'
    exit 0
}

if ($Action -eq 'Preflight') {
    if ((Get-RemoteSha256 $RemoteComponent) -cne [string]$patch.before_sha256) {
        throw 'Composant distant de base inattendu.'
    }
    $status = Get-StockStatus
    Assert-IdleStatus $status $false
    [void](Invoke-IdleValidator)
    Write-Output 'PREFLIGHT_STOCK_DERIVED_CYCLE_SELECTED_ROUTE_RECOVERY_V1_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    if ((Get-RemoteSha256 $RemoteComponent) -cne [string]$patch.after_sha256) {
        throw 'Composant distant corrige inattendu.'
    }
    $status = Get-StockStatus
    Assert-IdleStatus $status $true
    [void](Invoke-IdleValidator)
    & $ActivationDeployer -Action Validate -CaptureId ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-stock-derived-cycle-activation-v1') -Execute -Gate 'G4-K1-CONTROL-STOCK-DERIVED-CYCLE-ACTIVATION-IDLE-V1'
    if ($LASTEXITCODE -ne 0) { throw 'Validation complete du propriétaire actif KO.' }
    Write-Output 'VALIDATE_STOCK_DERIVED_CYCLE_SELECTED_ROUTE_RECOVERY_V1_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Assert-MutationGate
    Invoke-ExactRollback $manifest
    Write-Output "ROLLBACK_STOCK_DERIVED_CYCLE_SELECTED_ROUTE_RECOVERY_V1_OK capture=$CaptureId"
    exit 0
}

Assert-MutationGate
if ((Get-RemoteSha256 $RemoteComponent) -ceq [string]$patch.after_sha256) {
    & $PSCommandPath -Action Validate -PrinterHost $PrinterHost -CaptureId $CaptureId
    Write-Output "DEPLOY_STOCK_DERIVED_CYCLE_SELECTED_ROUTE_RECOVERY_V1_OK capture=$CaptureId already_present=true"
    exit 0
}

& $PSCommandPath -Action Preflight -PrinterHost $PrinterHost -CaptureId $CaptureId
New-Item -ItemType Directory -Path $LocalCapture -Force | Out-Null

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup' '$(Split-Path -Parent $RemoteStaging)'")
    [void](Invoke-Remote "cp '$RemoteComponent' '$RemoteBackup/k1_control_stock_cycle.py.before'")
    if ((Get-RemoteSha256 "$RemoteBackup/k1_control_stock_cycle.py.before") -cne [string]$patch.before_sha256) {
        throw 'Backup du composant non conforme.'
    }
    $MutationStarted = $true
    Copy-ToRemote $ComponentPath $RemoteStaging
    if ((Get-RemoteSha256 $RemoteStaging) -cne [string]$patch.after_sha256) {
        throw 'Transfert du composant non conforme.'
    }
    [void](Invoke-Remote "cp '$RemoteStaging' '$RemoteComponent.next' && chmod 0644 '$RemoteComponent.next' && mv '$RemoteComponent.next' '$RemoteComponent'")
    [void](Invoke-Remote "rm -f '$RemoteStaging'")
    [void](Invoke-Remote "'$RemoteService' restart")
    [void](Wait-Moonraker)
    & $PSCommandPath -Action Validate -PrinterHost $PrinterHost -CaptureId $CaptureId
    if ($LASTEXITCODE -ne 0) { throw 'Validation du correctif KO.' }
    [pscustomobject]@{
        capture_id = $CaptureId
        gate = $RequiredGate
        result = 'DEPLOY_STOCK_DERIVED_CYCLE_SELECTED_ROUTE_RECOVERY_V1_OK'
        component_before_sha256 = [string]$patch.before_sha256
        component_after_sha256 = [string]$patch.after_sha256
        dedicated_moonraker_restart = 1
        klipper_restart = 0
        starts_cycle = $false
        heat = $false
        motion = $false
        filament = $false
        cfs_frame = $false
        probe = $false
        mesh_recalculation = $false
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LocalCapture 'deploy-result.json') -Encoding UTF8
    Write-Output "DEPLOY_STOCK_DERIVED_CYCLE_SELECTED_ROUTE_RECOVERY_V1_OK capture=$CaptureId"
}
catch {
    $failure = $_
    if ($MutationStarted) {
        try { Invoke-ExactRollback $manifest }
        catch { throw "Pose KO: $($failure.Exception.Message) ; rollback KO: $($_.Exception.Message)" }
    }
    throw $failure
}
