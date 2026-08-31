[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'Deploy', 'Validate', 'Rollback')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$Gate = '',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-g4-k1-control-integrated-production-cycle-hotfix-r1',
    [string]$EvidenceDirectory = '',
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 ou plus recent est obligatoire.' }

$RequiredGate = 'G4-K1-CONTROL-INTEGRATED-PRODUCTION-CYCLE-HOTFIX-R1'
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\integrated-production-cycle-v1'
$ManifestPath = Join-Path $PackageRoot 'hotfix-r1-manifest.json'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemoteCurrent = "$RemoteRoot/current"
$RemoteComponents = "$RemoteCurrent/moonraker/moonraker/moonraker/components"
$RemoteComponent = "$RemoteComponents/k1_control_cycle.py"
$RemoteState = "$RemoteRoot/state/integrated-cycle-selected-job.json"
$RemoteGcodes = '/usr/data/printer_data/gcodes'
$MoonrakerService = '/etc/init.d/S56k1_control_moonraker'
$RemoteBackup = "$RemoteRoot/backups/$CaptureId-integrated-cycle-hotfix-r1"
$RemoteStaging = "$RemoteRoot/tmp/$CaptureId-integrated-cycle-hotfix-r1"
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
        throw 'Manifeste du correctif R1 inattendu.'
    }
    $source = Join-Path $PackageRoot ([string]$manifest.source)
    if ((Get-LocalHash $source) -cne ([string]$manifest.source_sha256)) {
        throw 'Empreinte locale du composant inattendue.'
    }
    if ((Get-LocalHash $PSCommandPath) -cne ([string]$manifest.deployer_sha256)) {
        throw 'Empreinte du deployeur du correctif inattendue.'
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
    $url = 'http://127.0.0.1:7125/printer/objects/query?webhooks=state&print_stats=state,filename&extruder=target&heater_bed=target&bed_mesh=profile_name&box&gcode_macro+KCTRL_STATE&gcode_macro+KCTRL_CYCLE_STATE'
    $raw = (Invoke-Remote "curl '$url'") -join "`n"
    $payload = $raw | ConvertFrom-Json
    if (-not $payload.result.status) { throw 'Etat Klipper absent.' }
    return $payload.result.status
}

function Assert-SafeState {
    param([Parameter(Mandatory = $true)]$Status)
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
    if ($Status.bed_mesh.profile_name -cne 'k1_p001_t055_r001_n11x11') { throw 'Le mesh 11x11 actif est absent.' }
    if ([int]$Status.'gcode_macro KCTRL_STATE'.accepted_z_valid -ne 1 -or
        [math]::Abs([double]$Status.'gcode_macro KCTRL_STATE'.accepted_z_offset + 0.04) -gt 0.0005) {
        throw 'Le Z accepte -0,04 mm est absent.'
    }
    if ($Status.'gcode_macro KCTRL_CYCLE_STATE'.phase -cne 'idle') { throw 'Le cycle integre n est pas au repos.' }
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
print('REMOTE_INTEGRATED_CYCLE_HOTFIX_R1_IMPORT_OK')
"@
    $output = Invoke-RemoteStdin "'$RemoteCurrent/moonraker/moonraker-env/bin/python' -B -" $program
    if (($output | Select-Object -Last 1) -cne 'REMOTE_INTEGRATED_CYCLE_HOTFIX_R1_IMPORT_OK') {
        throw "Import Python distant invalide : $($output -join "`n")"
    }
}

function Wait-Moonraker {
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        try {
            [void](Invoke-Remote "curl 'http://127.0.0.1:7125/server/info'")
            $status = Get-CycleStatus
            if ($status.phase -eq 'idle') { return $status }
        }
        catch {}
        Start-Sleep -Seconds 1
    }
    throw 'Moonraker et le cycle integre ne repondent pas apres restart.'
}

function Select-QualificationFile {
    param([Parameter(Mandatory = $true)][string]$Filename)
    $payload = @{ filename = $Filename } | ConvertTo-Json -Compress
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($payload))
    $program = @"
import base64, json, urllib.request
body = base64.b64decode('$encoded')
request = urllib.request.Request(
    'http://127.0.0.1:7125/machine/k1_control/cycle/select',
    data=body,
    headers={'Content-Type': 'application/json'},
    method='POST')
with urllib.request.urlopen(request, timeout=15) as response:
    print(response.read().decode('utf-8'))
"@
    $raw = (Invoke-RemoteStdin "'$RemoteCurrent/moonraker/moonraker-env/bin/python' -B -" $program) -join "`n"
    $response = $raw | ConvertFrom-Json
    if (-not $response.result -or $response.result.job.filename -cne $Filename) {
        throw 'La selection du G-code de qualification a echoue.'
    }
    return $response.result
}

function Assert-Preflight {
    param([Parameter(Mandatory = $true)]$Manifest)
    if ((Get-RemoteHash $RemoteComponent) -cne ([string]$Manifest.installed_sha256)) {
        throw 'Le composant distant de depart a derive.'
    }
    [void](Invoke-Remote "test -f '$RemoteGcodes/$($Manifest.selection_fixture)'")
    $cycle = Get-CycleStatus
    if ($cycle.phase -cne 'idle' -or $cycle.job) { throw 'Le cycle doit etre vide et au repos avant le correctif.' }
    $printer = Get-PrinterStatus
    Assert-SafeState $printer
    Assert-RemotePython
    Save-Evidence 'preflight-cycle.json' $cycle
    Save-Evidence 'preflight-safe-state.json' $printer
}

function Invoke-Rollback {
    param([Parameter(Mandatory = $true)]$Manifest)
    [void](Invoke-Remote "test -f '$RemoteBackup/k1_control_cycle.py.before'")
    [void](Invoke-Remote "cp '$RemoteBackup/k1_control_cycle.py.before' '$RemoteComponent.next' && chmod 0644 '$RemoteComponent.next' && mv '$RemoteComponent.next' '$RemoteComponent'")
    [void](Invoke-Remote "rm -f '$RemoteComponents/__pycache__/k1_control_cycle'*.pyc '$RemoteState'")
    [void](Invoke-Remote "'$MoonrakerService' restart")
    [void](Wait-Moonraker)
    if ((Get-RemoteHash $RemoteComponent) -cne ([string]$Manifest.installed_sha256)) {
        throw 'Rollback exact du composant incomplet.'
    }
    $printer = Get-PrinterStatus
    Assert-SafeState $printer
}

$manifest = Assert-Package

if ($Action -eq 'Plan') {
    Write-Output "PLAN_INTEGRATED_PRODUCTION_CYCLE_HOTFIX_R1_OK gate=$RequiredGate"
    Write-Output 'Pose: un composant Moonraker seulement, sauvegarde exacte et restart du Moonraker dedie.'
    Write-Output 'Validation: selection du G-code explicite; aucune chauffe, mouvement, extrusion ou action CFS.'
    exit 0
}

if ($Action -eq 'Preflight') {
    Assert-Preflight $manifest
    Write-Output 'PREFLIGHT_INTEGRATED_PRODUCTION_CYCLE_HOTFIX_R1_OK'
    exit 0
}

if ($Action -eq 'Validate') {
    if ((Get-RemoteHash $RemoteComponent) -cne ([string]$manifest.source_sha256)) {
        throw 'Le composant corrige distant est absent.'
    }
    $cycle = Get-CycleStatus
    if ($cycle.phase -cne 'idle' -or $cycle.job.filename -cne ([string]$manifest.selection_fixture)) {
        throw 'Le fichier de qualification n est pas selectionne.'
    }
    $printer = Get-PrinterStatus
    Assert-SafeState $printer
    Save-Evidence 'validate-cycle.json' $cycle
    Save-Evidence 'validate-safe-state.json' $printer
    Write-Output 'VALIDATE_INTEGRATED_PRODUCTION_CYCLE_HOTFIX_R1_OK'
    exit 0
}

if ($Action -eq 'Rollback') {
    Assert-MutationGate
    Invoke-Rollback $manifest
    Write-Output "ROLLBACK_INTEGRATED_PRODUCTION_CYCLE_HOTFIX_R1_OK capture=$CaptureId"
    exit 0
}

Assert-MutationGate
Assert-Preflight $manifest
New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null

try {
    [void](Invoke-Remote "mkdir -p '$RemoteBackup' '$RemoteStaging'")
    [void](Invoke-Remote "cp '$RemoteComponent' '$RemoteBackup/k1_control_cycle.py.before'")
    $MutationStarted = $true
    $source = Join-Path $PackageRoot ([string]$manifest.source)
    Copy-ToRemote $source "$RemoteStaging/k1_control_cycle.py"
    if ((Get-RemoteHash "$RemoteStaging/k1_control_cycle.py") -cne ([string]$manifest.source_sha256)) {
        throw 'Transfert du composant corrige non conforme.'
    }
    [void](Invoke-Remote "cp '$RemoteStaging/k1_control_cycle.py' '$RemoteComponent.next' && chmod 0644 '$RemoteComponent.next' && mv '$RemoteComponent.next' '$RemoteComponent'")
    [void](Invoke-Remote "rm -f '$RemoteComponents/__pycache__/k1_control_cycle'*.pyc")
    [void](Invoke-Remote "'$MoonrakerService' restart")
    [void](Wait-Moonraker)
    $selected = Select-QualificationFile ([string]$manifest.selection_fixture)
    Save-Evidence 'selected-job.json' $selected
    & $PSCommandPath -Action Validate -PrinterHost $PrinterHost -CaptureId $CaptureId -EvidenceDirectory $EvidenceDirectory
    Save-Evidence 'deploy-result.json' ([ordered]@{
        capture_id = $CaptureId
        result = 'DEPLOY_INTEGRATED_PRODUCTION_CYCLE_HOTFIX_R1_OK'
        physical_action = $false
        heater_command = $false
        cfs_command = $false
        selected_job = [string]$manifest.selection_fixture
    })
    Write-Output "DEPLOY_INTEGRATED_PRODUCTION_CYCLE_HOTFIX_R1_OK capture=$CaptureId"
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
