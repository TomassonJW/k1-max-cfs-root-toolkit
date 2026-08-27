[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-gateway-private-lan-no-auth-v1',
    [switch]$Execute,
    [string]$Gate = ''
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'G4-K1-CONTROL-GATEWAY-PRIVATE-LAN-NO-AUTH-V1'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\gateway-private-lan-no-auth-v1'
$ManifestPath = Join-Path $PackageRoot 'deployment-manifest.json'
$CandidatePath = Join-Path $PackageRoot 'nginx.conf'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteActive = "$RemoteRoot/state/nginx-active.conf"
$RemoteService = '/etc/init.d/S57k1_control_gateway'
$RemoteNginx = "$RemoteRoot/current/nginx/sbin/nginx"
$RemotePrefix = "$RemoteRoot/current/nginx/nginx"
$RemoteStaging = "$RemoteRoot/tmp/$CaptureId-gateway-no-auth"
$RemoteCandidate = "$RemoteStaging/nginx.conf"
$RemoteBackup = "$RemoteRoot/backups/$CaptureId-gateway-no-auth"
$RemoteBackupConfig = "$RemoteBackup/nginx-active.conf"
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
    if ([string]$manifest.contract_id -cne $RequiredGate) {
        throw 'Identité du paquet sans authentification inattendue.'
    }
    if ((Get-LocalSha256 $CandidatePath) -cne [string]$manifest.candidate.sha256) {
        throw 'Empreinte locale du candidat nginx inattendue.'
    }
    if ([string]$manifest.candidate.destination -cne $RemoteActive) {
        throw 'Destination nginx inattendue.'
    }
    return $manifest
}

function Get-ServerInfo {
    param([string]$BaseUrl = 'http://127.0.0.1:7125')
    $raw = (Invoke-Remote "curl '$BaseUrl/server/info'") -join "`n"
    $info = ($raw | ConvertFrom-Json).result
    if (-not $info) { throw "Réponse server/info absente sur $BaseUrl." }
    return $info
}

function Assert-ServerInfo {
    param([string]$BaseUrl = 'http://127.0.0.1:7125')
    $info = Get-ServerInfo -BaseUrl $BaseUrl
    if (-not [bool]$info.klippy_connected -or [string]$info.klippy_state -cne 'ready' -or
        @($info.failed_components).Count -ne 0 -or @($info.warnings).Count -ne 0) {
        throw "Moonraker non sain sur $BaseUrl : state=$($info.klippy_state)."
    }
    return $info
}

function Assert-SafePrinterState {
    [void](Assert-ServerInfo)
    $url = 'http://127.0.0.1:7125/printer/objects/query?print_stats=state,filename&extruder=target&heater_bed=target&toolhead=homed_axes&bed_mesh=profile_name'
    $raw = (Invoke-Remote "curl '$url'") -join "`n"
    $status = ($raw | ConvertFrom-Json).result.status
    if (-not $status) { throw 'État Klipper absent.' }
    if ([string]$status.print_stats.state -cne 'standby' -or [string]$status.print_stats.filename) {
        throw "Imprimante occupée : $($status.print_stats.state)."
    }
    if ([double]$status.extruder.target -ne 0 -or [double]$status.heater_bed.target -ne 0) {
        throw 'Les chauffes demandées ne sont pas à zéro.'
    }
    return $status
}

function Assert-Listeners {
    $listeners = (Invoke-Remote 'netstat -lnt') -join "`n"
    foreach ($required in @('127.0.0.1:7125', '0.0.0.0:4409')) {
        if ($listeners -notmatch [regex]::Escape($required)) {
            throw "Écoute absente : $required."
        }
    }
    if ($listeners -match '0.0.0.0:7125') {
        throw 'Moonraker est exposé directement au LAN.'
    }
}

function Invoke-Preflight {
    $manifest = Assert-Package
    $activeSha256 = Get-RemoteSha256 $RemoteActive
    if (@($manifest.allowed_before_sha256) -cnotcontains $activeSha256) {
        throw 'La configuration active ne correspond pas à la base sans authentification revue.'
    }
    [void](Assert-SafePrinterState)
    Assert-Listeners
    Write-Output 'PREFLIGHT_GATEWAY_PRIVATE_LAN_NO_AUTH_V1_OK'
}

function Invoke-Validate {
    $manifest = Assert-Package
    if ((Get-RemoteSha256 $RemoteActive) -cne [string]$manifest.candidate.sha256) {
        throw 'La configuration active sans authentification a une empreinte inattendue.'
    }
    [void](Assert-ServerInfo -BaseUrl 'http://127.0.0.1:4409')
    [void](Assert-SafePrinterState)
    Assert-Listeners
    Write-Output 'VALIDATE_GATEWAY_PRIVATE_LAN_NO_AUTH_V1_OK'
}

function Invoke-Rollback {
    Assert-MutationGate
    $backupCheck = (Invoke-Remote "test -f '$RemoteBackupConfig'; echo `$?") -join "`n"
    if ($backupCheck.Trim() -ne '0') {
        throw "Sauvegarde de rollback absente : $RemoteBackupConfig"
    }
    Invoke-Remote "cp '$RemoteBackupConfig' '$RemoteActive'" | Out-Null
    Invoke-Remote "'$RemoteService' reload" | Out-Null
    $manifest = Assert-Package
    if (@($manifest.allowed_before_sha256) -cnotcontains (Get-RemoteSha256 $RemoteActive)) {
        throw "Le rollback n'a pas restauré la configuration précédente exacte."
    }
    [void](Assert-SafePrinterState)
    Assert-Listeners
    Write-Output 'ROLLBACK_GATEWAY_PRIVATE_LAN_NO_AUTH_V1_OK'
}

switch ($Action) {
    'Plan' {
        [void](Assert-Package)
        Write-Output "PLAN_GATEWAY_PRIVATE_LAN_NO_AUTH_V1_OK gate=$RequiredGate"
    }
    'Preflight' {
        Invoke-Preflight
    }
    'Validate' {
        Invoke-Validate
    }
    'Rollback' {
        Invoke-Rollback
    }
    'Deploy' {
        Assert-MutationGate
        $manifest = Assert-Package
        Invoke-Preflight
        try {
            Invoke-Remote "mkdir -p '$RemoteStaging' '$RemoteBackup'" | Out-Null
            Copy-ToRemote -Source $CandidatePath -Destination $RemoteCandidate
            if ((Get-RemoteSha256 $RemoteCandidate) -cne [string]$manifest.candidate.sha256) {
                throw 'Empreinte distante du candidat nginx inattendue.'
            }
            Invoke-Remote "'$RemoteNginx' -g 'error_log stderr;' -t -c '$RemoteCandidate' -p '$RemotePrefix'" | Out-Null
            Invoke-Remote "cp '$RemoteActive' '$RemoteBackupConfig'" | Out-Null
            if (@($manifest.allowed_before_sha256) -cnotcontains (Get-RemoteSha256 $RemoteBackupConfig)) {
                throw 'Sauvegarde nginx inexacte.'
            }
            Invoke-Remote "cp '$RemoteCandidate' '$RemoteActive'" | Out-Null
            $MutationStarted = $true
            Invoke-Remote "'$RemoteService' reload" | Out-Null
            Invoke-Validate
            Invoke-Remote "rm -f '$RemoteCandidate'; rmdir '$RemoteStaging'" | Out-Null
            Write-Output "DEPLOY_GATEWAY_PRIVATE_LAN_NO_AUTH_V1_OK backup=$RemoteBackupConfig"
        }
        catch {
            $failure = $_
            if ($MutationStarted) {
                Invoke-Remote "cp '$RemoteBackupConfig' '$RemoteActive'" | Out-Null
                Invoke-Remote "'$RemoteService' reload" | Out-Null
            }
            throw $failure
        }
    }
}
