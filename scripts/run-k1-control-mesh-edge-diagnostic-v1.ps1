[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Preflight', 'RecoverRobust', 'Deploy', 'Upload', 'PrepareSource', 'PrepareCorrected', 'CheckPrepared', 'PrintSource', 'PrintCorrected', 'WaitComplete', 'Rollback', 'FinalValidate')]
    [string]$Action = 'Plan',
    [string]$PrinterHost = 'k1max-root',
    [string]$CaptureId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-mesh-edge-diagnostic-v1',
    [string]$ArtifactsDirectory = '.codex-work\mesh-edge-diagnostic-v1',
    [ValidateSet('source', 'corrected')]
    [string]$Variant = 'source',
    [switch]$Execute,
    [string]$Gate = '',
    [switch]$HumanPresent,
    [switch]$PlateClear,
    [switch]$FilamentRouteConfirmed,
    [switch]$PurgeFlowConfirmed
)

$ErrorActionPreference = 'Stop'
$RequiredGate = 'MESH-EDGE-DIAGNOSTIC-V1'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$PackageRoot = Join-Path $WorkspaceRoot 'packages\k1-control-v1\mesh-edge-diagnostic-v1'
$Builder = Join-Path $PackageRoot 'build_candidate_config.py'
$ArtifactsRoot = if ([IO.Path]::IsPathRooted($ArtifactsDirectory)) { $ArtifactsDirectory } else { Join-Path $WorkspaceRoot $ArtifactsDirectory }
$ManifestPath = Join-Path $ArtifactsRoot 'diagnostic-manifest.json'
$RemoteRoot = '/usr/data/k1-control-v1'
$RemotePrinterConfig = '/usr/data/printer_data/config/printer.cfg'
$RemoteGcodeRoot = '/usr/data/printer_data/gcodes'
$RemoteBackup = "$RemoteRoot/backups/$CaptureId-mesh-edge-diagnostic-v1"
$RemoteStaging = "$RemoteRoot/tmp/$CaptureId-mesh-edge-diagnostic-v1"
$LocalCapture = Join-Path $WorkspaceRoot "inventory\raw\$CaptureId"
$SessionPath = Join-Path $LocalCapture 'mesh-edge-session.json'
$AllowedBaseline = 'f88d6b52477592805384fca2b4d7abd00298deecd82227af2fa580085fe26fa2'
$RobustProfile = 'k1_p001_t055_r001_n06x06'
$SourceProfile = 'k1_p001_t055_r001_n11x11'
$DerivedProfile = 'k1_p001_t055_r001_n11x11_tuned_v001'

function Assert-MutationGate {
    if (-not $Execute -or $Gate -cne $RequiredGate) {
        throw "Action bloquée : -Execute et -Gate '$RequiredGate' sont obligatoires."
    }
}

function Assert-PhysicalFacts {
    param([switch]$RequireFilamentFlow)
    if (-not $HumanPresent -or -not $PlateClear) {
        throw 'La présence humaine et le plateau libre doivent être confirmés pour cette action.'
    }
    if ($RequireFilamentFlow -and (-not $FilamentRouteConfirmed -or -not $PurgeFlowConfirmed)) {
        throw "Le motif reste bloqué : route filament et purge réellement visible doivent être confirmées sans supposer T0."
    }
}

function Get-LocalSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    $resolved = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
    $stream = [IO.File]::OpenRead($resolved)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return (($algorithm.ComputeHash($stream) | ForEach-Object { $_.ToString('x2') }) -join '')
    } finally {
        $algorithm.Dispose()
        $stream.Dispose()
    }
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
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $arguments = @(
        '-O', '-o', 'BatchMode=yes', '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no', '-o', 'ConnectTimeout=8',
        (Resolve-Path -LiteralPath $Source).Path, "$PrinterHost`:$Destination"
    )
    & scp.exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Transfert SCP KO : $Destination" }
}

function Copy-FromRemote {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $arguments = @(
        '-O', '-o', 'BatchMode=yes', '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no', '-o', 'ConnectTimeout=8',
        "$PrinterHost`:$Source", $Destination
    )
    & scp.exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Copie SCP locale KO : $Source" }
}

function Get-RemoteSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    $line = Invoke-Remote "sha256sum '$Path'"
    return ((($line | Select-Object -First 1) -split '\s+')[0]).ToLowerInvariant()
}

function Get-Manifest {
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        throw "Manifeste privé absent : $ManifestPath"
    }
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ($manifest.gate -cne $RequiredGate -or [int]$manifest.schema -ne 1) {
        throw 'Manifeste diagnostic inattendu.'
    }
    foreach ($property in $manifest.files.PSObject.Properties) {
        $entry = $property.Value
        $path = Join-Path $ArtifactsRoot ([string]$entry.name)
        if ((Get-LocalSha256 $path) -cne [string]$entry.sha256) {
            throw "Empreinte locale inattendue : $($entry.name)"
        }
    }
    if ([string]$manifest.pattern.geometry_sha256 -cne '1259e040b34a95bac80ad6ac8862a3bfa8457618484df17036a39cfafcedd0e5') {
        throw "La géométrie diagnostic n'a pas l'empreinte revue."
    }
    if ([string]$manifest.pattern.estimated_filament_g -ne '0.558') {
        throw 'Le budget matière diagnostic a changé.'
    }
    return $manifest
}

function Get-ServerInfo {
    $raw = (Invoke-Remote "curl 'http://127.0.0.1:7125/server/info'") -join "`n"
    $info = ($raw | ConvertFrom-Json).result
    if (-not $info) { throw 'Moonraker sans server/info.' }
    return $info
}

function Get-PrinterStatus {
    $url = 'http://127.0.0.1:7125/printer/objects/query?print_stats&extruder&heater_bed&toolhead&bed_mesh&box&gcode_move&gcode_macro+KCTRL_STATE&k1_control_store&gcode_macro+KCTRL_CAL_PATH_STATE'
    $raw = (Invoke-Remote "curl '$url'") -join "`n"
    $status = ($raw | ConvertFrom-Json).result.status
    if (-not $status) { throw 'Réponse Moonraker sans état Klipper.' }
    return $status
}

function Wait-KlippyReady {
    param([int]$TimeoutSeconds = 120)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        Start-Sleep -Seconds 2
        try {
            $info = Get-ServerInfo
            if ([string]$info.klippy_state -ceq 'ready') { return $info }
        } catch {
            $lastError = $_.Exception.Message
        }
    } while ((Get-Date) -lt $deadline)
    throw "Klipper non prêt après $TimeoutSeconds s. Dernière erreur : $lastError"
}

function Test-ReviewedGcode {
    param([Parameter(Mandatory = $true)][string]$Script)
    return $Script -in @(
        'RESTART',
        "BED_MESH_PROFILE LOAD=$RobustProfile",
        'TURN_OFF_HEATERS',
        'M84',
        'CANCEL_PRINT'
    )
}

function Send-Gcode {
    param(
        [Parameter(Mandatory = $true)][string]$Script,
        [switch]$NoResponse
    )
    if (-not (Test-ReviewedGcode $Script)) { throw "G-code hors liste revue : $Script" }
    $python = @'
from __future__ import print_function
import json
import socket
import sys
import time

script = sys.argv[1]
wait_response = sys.argv[2] == "1"
request = {"id": 5501, "method": "gcode/script", "params": {"script": script}}
client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.settimeout(1200)
client.connect("/tmp/klippy_uds")
client.sendall((json.dumps(request) + "\x03").encode("utf-8"))
if not wait_response:
    time.sleep(0.2)
    client.close()
    print(json.dumps({"sent": script}))
    raise SystemExit(0)
data = b""
while b"\x03" not in data:
    chunk = client.recv(65536)
    if not chunk:
        break
    data += chunk
client.close()
if not data:
    print(json.dumps({"closed_without_response": True}))
else:
    print(json.dumps(json.loads(data.split(b"\x03", 1)[0].decode("utf-8")), sort_keys=True))
'@
    $payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($python.Replace("`r`n", "`n")))
    $wait = if ($NoResponse) { '0' } else { '1' }
    $line = Invoke-Remote "echo '$payload' | base64 -d | /usr/share/klippy-env/bin/python - '$Script' '$wait'"
    $response = (($line -join "`n") | ConvertFrom-Json)
    if ($response.error) {
        throw "Commande Klipper refusée : $($response.error | ConvertTo-Json -Compress)"
    }
    return $response
}

function Assert-ServerHealthy {
    $info = Get-ServerInfo
    if ([string]$info.klippy_state -cne 'ready') { throw "Klipper n'est pas prêt." }
    if (@($info.failed_components).Count -ne 0 -or @($info.warnings).Count -ne 0) {
        throw 'Moonraker signale un composant échoué ou un avertissement.'
    }
    return $info
}

function Assert-SafeBaseline {
    param(
        [switch]$AllowDerived,
        [switch]$AllowCompletedDiagnostic
    )
    [void](Assert-ServerHealthy)
    $status = Get-PrinterStatus
    $emptyStandby = [string]$status.print_stats.state -ceq 'standby' -and -not [string]$status.print_stats.filename
    $completedDiagnostic = $false
    if ($AllowCompletedDiagnostic) {
        $manifest = Get-Manifest
        $patternNames = @(
            [string]$manifest.files.source_pattern_gcode.name,
            [string]$manifest.files.corrected_pattern_gcode.name
        )
        $completedDiagnostic = [string]$status.print_stats.state -ceq 'complete' -and
            $patternNames -contains [string]$status.print_stats.filename
    }
    if (-not $emptyStandby -and -not $completedDiagnostic) {
        throw "La K1 n'est pas au repos."
    }
    if ([double]$status.extruder.target -ne 0 -or [double]$status.heater_bed.target -ne 0) {
        throw 'Les cibles de chauffe ne sont pas à zéro.'
    }
    if ([string]$status.toolhead.homed_axes) { throw 'Les axes sont encore référencés.' }
    $runtime = $status.'gcode_macro KCTRL_STATE'
    $store = $status.k1_control_store
    $path = $status.'gcode_macro KCTRL_CAL_PATH_STATE'
    if ([int]$runtime.ready -ne 1 -or [int]$runtime.accepted_z_valid -ne 1 -or
        [math]::Abs([double]$runtime.accepted_z_offset - (-0.04)) -gt 0.0005 -or
        [int]$runtime.session_active -ne 0 -or [int]$runtime.low_moves_armed -ne 0 -or
        -not $store -or [string]$store.integrity -cne 'ok') {
        throw 'Runtime ou stockage Z non sûr.'
    }
    if (@('idle', 'committed', 'cancelled') -notcontains [string]$path.phase -or
        [int]$path.motion_armed -ne 0 -or [int]$path.commit_ready -ne 0) {
        throw 'Chemin Z non fermé.'
    }
    $profiles = @($status.bed_mesh.profiles.PSObject.Properties.Name)
    if ($profiles -notcontains $RobustProfile -or $profiles -notcontains $SourceProfile) {
        throw 'Le robuste ou le composite source est absent.'
    }
    if (-not $AllowDerived -and $profiles -contains $DerivedProfile) {
        throw 'Le profil diagnostic existe déjà avant la pose.'
    }
    if ([string]$status.bed_mesh.profile_name -cne $RobustProfile) {
        throw "Le profil robuste n'est pas actif."
    }
    foreach ($unit in @('T1', 'T2')) {
        if ([string]$status.box.$unit.state -cne 'connect') { throw "CFS $unit non connecté." }
    }
    return $status
}

function Save-Session {
    param([Parameter(Mandatory = $true)]$Value)
    if (-not (Test-Path -LiteralPath $LocalCapture)) {
        [void](New-Item -ItemType Directory -Path $LocalCapture)
    }
    $Value | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $SessionPath -Encoding utf8
}

function Get-Session {
    if (-not (Test-Path -LiteralPath $SessionPath -PathType Leaf)) {
        throw "État local de session absent : $SessionPath"
    }
    return Get-Content -LiteralPath $SessionPath -Raw | ConvertFrom-Json
}

function Invoke-Preflight {
    $manifest = Get-Manifest
    [void](Assert-SafeBaseline)
    $configHash = Get-RemoteSha256 $RemotePrinterConfig
    if ($configHash -cne $AllowedBaseline) {
        throw "Empreinte printer.cfg inattendue : $configHash"
    }
    if (-not (Test-Path -LiteralPath $LocalCapture)) {
        [void](New-Item -ItemType Directory -Path $LocalCapture)
    }
    $localBase = Join-Path $LocalCapture 'printer.cfg.preflight'
    Copy-FromRemote $RemotePrinterConfig $localBase
    if ((Get-LocalSha256 $localBase) -cne $configHash) { throw 'Copie locale printer.cfg incohérente.' }
    foreach ($entry in @($manifest.files.PSObject.Properties | Where-Object { $_.Name -like '*gcode' })) {
        $name = [string]$entry.Value.name
        $presence = (Invoke-Remote "if [ -e '$RemoteGcodeRoot/$name' ]; then echo present; else echo absent; fi") -join ''
        if ($presence -cne 'absent') { throw "Ancien G-code diagnostic encore présent : $name" }
    }
    Save-Session ([ordered]@{
        schema = 1
        gate = $RequiredGate
        capture_id = $CaptureId
        baseline_sha256 = $configHash
        remote_backup = $RemoteBackup
        remote_staging = $RemoteStaging
        deployed = $false
        uploaded = $false
        source_prepared = $false
        corrected_prepared = $false
        source_started = $false
        corrected_started = $false
    })
    Write-Output "PREFLIGHT_MESH_EDGE_DIAGNOSTIC_V1_OK capture=$CaptureId"
}

function Invoke-RecoverRobust {
    Assert-MutationGate
    [void](Assert-ServerHealthy)
    $status = Get-PrinterStatus
    if ([string]$status.print_stats.state -cne 'standby' -or [string]$status.print_stats.filename) {
        throw "La K1 n'est pas au repos."
    }
    if ([double]$status.extruder.target -ne 0 -or [double]$status.heater_bed.target -ne 0 -or
        [string]$status.toolhead.homed_axes -or [int]$status.'gcode_macro KCTRL_STATE'.low_moves_armed -ne 0) {
        throw 'La K1 ne permet pas une remise au robuste sans effet physique.'
    }
    $profiles = @($status.bed_mesh.profiles.PSObject.Properties.Name)
    if ($profiles -notcontains $RobustProfile -or $profiles -notcontains $SourceProfile -or $profiles -contains $DerivedProfile) {
        throw 'La liste des profils ne permet pas la remise au robuste.'
    }
    if ((Get-RemoteSha256 $RemotePrinterConfig) -cne $AllowedBaseline) {
        throw 'printer.cfg ne correspond pas à la base revue.'
    }
    [void](Send-Gcode "BED_MESH_PROFILE LOAD=$RobustProfile")
    [void](Assert-SafeBaseline)
    Write-Output 'RECOVER_ROBUST_MESH_EDGE_DIAGNOSTIC_V1_OK'
}

function Invoke-Deploy {
    Assert-MutationGate
    $manifest = Get-Manifest
    $session = Get-Session
    if ([string]$session.baseline_sha256 -cne $AllowedBaseline) { throw 'Session sans base revue.' }
    [void](Assert-SafeBaseline)
    $localBase = Join-Path $LocalCapture 'printer.cfg.preflight'
    if ((Get-LocalSha256 $localBase) -cne $AllowedBaseline) { throw 'Backup local inattendu.' }
    $profile = Join-Path $ArtifactsRoot ([string]$manifest.files.derived_klipper.name)
    $candidate = Join-Path $LocalCapture 'printer.cfg.candidate'
    & python $Builder $localBase $profile $candidate --expected-base-sha256 $AllowedBaseline
    if ($LASTEXITCODE -ne 0) { throw 'Construction locale de printer.cfg KO.' }
    $candidateHash = Get-LocalSha256 $candidate
    [void](Invoke-Remote "mkdir -p '$RemoteBackup' '$RemoteStaging'")
    [void](Invoke-Remote "cp '$RemotePrinterConfig' '$RemoteBackup/printer.cfg'")
    if ((Get-RemoteSha256 "$RemoteBackup/printer.cfg") -cne $AllowedBaseline) { throw 'Backup distant incohérent.' }
    Copy-ToRemote $candidate "$RemoteStaging/printer.cfg.candidate"
    if ((Get-RemoteSha256 "$RemoteStaging/printer.cfg.candidate") -cne $candidateHash) { throw 'Staging distant incohérent.' }
    $mutationStarted = $true
    try {
        [void](Invoke-Remote "cp '$RemoteStaging/printer.cfg.candidate' '$RemotePrinterConfig'")
        if ((Get-RemoteSha256 $RemotePrinterConfig) -cne $candidateHash) { throw 'Pose printer.cfg incohérente.' }
        [void](Send-Gcode 'RESTART' -NoResponse)
        [void](Wait-KlippyReady)
        $status = Get-PrinterStatus
        $profiles = @($status.bed_mesh.profiles.PSObject.Properties.Name)
        if ($profiles -notcontains $DerivedProfile) { throw 'Profil diagnostic absent après restart.' }
        [void](Send-Gcode "BED_MESH_PROFILE LOAD=$RobustProfile")
        $status = Get-PrinterStatus
        if ([string]$status.bed_mesh.profile_name -cne $RobustProfile) { throw 'Retour au robuste KO après pose.' }
    } catch {
        if ($mutationStarted) {
            [void](Invoke-Remote "cp '$RemoteBackup/printer.cfg' '$RemotePrinterConfig'")
            try { [void](Send-Gcode 'RESTART' -NoResponse) } catch {}
            try { [void](Wait-KlippyReady) } catch {}
        }
        throw
    }
    $session.deployed = $true
    $session | Add-Member -NotePropertyName candidate_sha256 -NotePropertyValue $candidateHash -Force
    Save-Session $session
    Write-Output "DEPLOY_MESH_EDGE_DIAGNOSTIC_V1_OK capture=$CaptureId"
}

function Invoke-Upload {
    Assert-MutationGate
    $manifest = Get-Manifest
    $session = Get-Session
    if (-not [bool]$session.deployed) { throw "Le profil diagnostic n'est pas posé." }
    [void](Assert-SafeBaseline -AllowDerived)
    foreach ($property in @($manifest.files.PSObject.Properties | Where-Object { $_.Name -like '*gcode' })) {
        $key = [string]$property.Name
        $entry = $property.Value
        $local = Join-Path $ArtifactsRoot ([string]$entry.name)
        $remote = "$RemoteGcodeRoot/$([string]$entry.name)"
        Copy-ToRemote $local $remote
        if ((Get-RemoteSha256 $remote) -cne [string]$entry.sha256) { throw "G-code distant incohérent : $key" }
    }
    $session.uploaded = $true
    Save-Session $session
    Write-Output "UPLOAD_MESH_EDGE_DIAGNOSTIC_V1_OK capture=$CaptureId"
}

function Wait-PrintFileComplete {
    param(
        [Parameter(Mandatory = $true)][string]$Filename,
        [int]$TimeoutSeconds = 120
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $seen = $false
    do {
        Start-Sleep -Milliseconds 500
        $status = Get-PrinterStatus
        if ([string]$status.print_stats.filename -ceq $Filename -or
            @('printing', 'paused') -contains [string]$status.print_stats.state) {
            $seen = $true
        }
        if ([string]$status.print_stats.state -ceq 'error' -or [string]$status.print_stats.state -ceq 'cancelled') {
            throw "Exécution G-code arrêtée : $($status.print_stats.state)"
        }
        if ($seen -and [string]$status.print_stats.state -ceq 'complete' -and
            [string]$status.print_stats.filename -ceq $Filename) {
            return $status
        }
        if ($seen -and [string]$status.print_stats.state -ceq 'standby' -and -not [string]$status.print_stats.filename) {
            return $status
        }
    } while ((Get-Date) -lt $deadline)
    throw "Timeout en attente de la fin de $Filename"
}

function Invoke-PrepareVariant {
    param([Parameter(Mandatory = $true)][ValidateSet('source', 'corrected')][string]$Which)
    Assert-MutationGate
    Assert-PhysicalFacts
    $manifest = Get-Manifest
    $session = Get-Session
    if (-not [bool]$session.uploaded) { throw 'Les G-code ne sont pas validés sur la K1.' }
    [void](Assert-SafeBaseline -AllowDerived)
    $entry = if ($Which -ceq 'source') { $manifest.files.source_prepare_gcode } else { $manifest.files.corrected_prepare_gcode }
    [void](Invoke-Remote "curl -X POST 'http://127.0.0.1:7125/printer/print/start?filename=$([string]$entry.name)'")
    [void](Wait-PrintFileComplete -Filename ([string]$entry.name) -TimeoutSeconds 180)
    if ($Which -ceq 'source') { $session.source_prepared = $true } else { $session.corrected_prepared = $true }
    Save-Session $session
    $script:Variant = $Which
    Invoke-CheckPrepared
    Write-Output "PREPARE_REMOTE_MESH_EDGE_DIAGNOSTIC_V1_OK variant=$Which capture=$CaptureId"
}

function Invoke-CheckPrepared {
    $manifest = Get-Manifest
    $status = Get-PrinterStatus
    $prepareEntry = if ($Variant -ceq 'source') { $manifest.files.source_prepare_gcode } else { $manifest.files.corrected_prepare_gcode }
    $closedPrepare = [string]$status.print_stats.state -ceq 'complete' -and
        [string]$status.print_stats.filename -ceq [string]$prepareEntry.name
    $emptyStandby = [string]$status.print_stats.state -ceq 'standby' -and -not [string]$status.print_stats.filename
    if (-not $closedPrepare -and -not $emptyStandby) {
        throw "Le fichier de préparation n'est pas terminé."
    }
    $expected = if ($Variant -ceq 'source') { $SourceProfile } else { $DerivedProfile }
    $runtime = $status.'gcode_macro KCTRL_STATE'
    if ([string]$status.bed_mesh.profile_name -cne $expected -or
        [string]$runtime.armed_mesh_profile -cne $expected -or [int]$runtime.low_moves_armed -ne 1) {
        throw 'Le profil effectif ou la garde de mouvements bas est incorrect.'
    }
    if ([math]::Abs([double]$status.gcode_move.homing_origin[2] - (-0.04)) -gt 0.0005) {
        throw "Le Z effectif n'est pas -0,04 mm à la pause."
    }
    if ([string]$status.toolhead.homed_axes -notmatch 'x' -or [string]$status.toolhead.homed_axes -notmatch 'y' -or [string]$status.toolhead.homed_axes -notmatch 'z') {
        throw 'Les axes XYZ ne sont pas tous référencés.'
    }
    if ([double]$status.extruder.target -ne 0 -or [double]$status.heater_bed.target -ne 0) {
        throw 'La préparation a lancé une chauffe inattendue.'
    }
    Write-Output "CHECK_PREPARED_MESH_EDGE_DIAGNOSTIC_V1_OK variant=$Variant profile=$expected z=-0.04"
}

function Invoke-RecoverPrepared {
    Assert-MutationGate
    Assert-PhysicalFacts
    $session = Get-Session
    if (-not [bool]$session.uploaded) { throw 'Les G-code ne sont pas validés sur la K1.' }
    Invoke-CheckPrepared
    if ($Variant -ceq 'source') { $session.source_prepared = $true } else { $session.corrected_prepared = $true }
    Save-Session $session
    Write-Output "RECOVER_PREPARED_MESH_EDGE_DIAGNOSTIC_V1_OK variant=$Variant capture=$CaptureId"
}

function Invoke-PrintPattern {
    param([Parameter(Mandatory = $true)][ValidateSet('source', 'corrected')][string]$Which)
    Assert-MutationGate
    Assert-PhysicalFacts -RequireFilamentFlow
    $manifest = Get-Manifest
    $session = Get-Session
    if ($Which -ceq 'source' -and -not [bool]$session.source_prepared) { throw "La source n'est pas préparée." }
    if ($Which -ceq 'corrected' -and -not [bool]$session.corrected_prepared) { throw "La correction n'est pas préparée." }
    $script:Variant = $Which
    Invoke-CheckPrepared
    $entry = if ($Which -ceq 'source') { $manifest.files.source_pattern_gcode } else { $manifest.files.corrected_pattern_gcode }
    [void](Invoke-Remote "curl -X POST 'http://127.0.0.1:7125/printer/print/start?filename=$([string]$entry.name)'")
    if ($Which -ceq 'source') { $session.source_started = $true } else { $session.corrected_started = $true }
    Save-Session $session
    Write-Output "PRINT_MESH_EDGE_DIAGNOSTIC_V1_OK variant=$Which capture=$CaptureId"
}

function Invoke-WaitComplete {
    $deadline = (Get-Date).AddMinutes(20)
    $manifest = Get-Manifest
    $entry = if ($Variant -ceq 'source') { $manifest.files.source_pattern_gcode } else { $manifest.files.corrected_pattern_gcode }
    [void](Wait-PrintFileComplete -Filename ([string]$entry.name) -TimeoutSeconds 1200)
    [void](Assert-SafeBaseline -AllowDerived -AllowCompletedDiagnostic)
    Write-Output "WAIT_COMPLETE_MESH_EDGE_DIAGNOSTIC_V1_OK variant=$Variant"
}

function Invoke-Rollback {
    Assert-MutationGate
    $manifest = Get-Manifest
    $session = Get-Session
    $status = Get-PrinterStatus
    if (@('printing', 'paused') -contains [string]$status.print_stats.state) {
        [void](Send-Gcode 'CANCEL_PRINT')
        Start-Sleep -Seconds 3
    }
    try { [void](Send-Gcode 'TURN_OFF_HEATERS') } catch {}
    try { [void](Send-Gcode 'M84') } catch {}
    if ((Get-RemoteSha256 "$RemoteBackup/printer.cfg") -cne [string]$session.baseline_sha256) {
        throw 'Backup distant absent ou incohérent.'
    }
    [void](Invoke-Remote "cp '$RemoteBackup/printer.cfg' '$RemotePrinterConfig'")
    if ((Get-RemoteSha256 $RemotePrinterConfig) -cne [string]$session.baseline_sha256) {
        throw 'Restauration printer.cfg incohérente.'
    }
    [void](Send-Gcode 'RESTART' -NoResponse)
    [void](Wait-KlippyReady)
    [void](Send-Gcode "BED_MESH_PROFILE LOAD=$RobustProfile")
    try { [void](Send-Gcode 'M84') } catch {}
    foreach ($property in @($manifest.files.PSObject.Properties | Where-Object { $_.Name -like '*gcode' })) {
        $name = [string]$property.Value.name
        [void](Invoke-Remote "rm -f '$RemoteGcodeRoot/$name'")
    }
    $session.deployed = $false
    $session.uploaded = $false
    $session | Add-Member -NotePropertyName rolled_back -NotePropertyValue $true -Force
    Save-Session $session
    Write-Output "ROLLBACK_MESH_EDGE_DIAGNOSTIC_V1_OK capture=$CaptureId"
}

function Invoke-FinalValidate {
    $manifest = Get-Manifest
    [void](Assert-SafeBaseline)
    if ((Get-RemoteSha256 $RemotePrinterConfig) -cne $AllowedBaseline) {
        throw "printer.cfg final n'est pas la base exacte."
    }
    foreach ($property in @($manifest.files.PSObject.Properties | Where-Object { $_.Name -like '*gcode' })) {
        $name = [string]$property.Value.name
        $presence = (Invoke-Remote "if [ -e '$RemoteGcodeRoot/$name' ]; then echo present; else echo absent; fi") -join ''
        if ($presence -cne 'absent') { throw "G-code final encore présent : $name" }
    }
    Write-Output "VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK capture=$CaptureId"
}

switch ($Action) {
    'Plan' {
        $manifest = Get-Manifest
        Write-Output "gate=$RequiredGate"
        Write-Output "capture=$CaptureId"
        Write-Output "source_prepare=$($manifest.files.source_prepare_gcode.name)"
        Write-Output "source_pattern=$($manifest.files.source_pattern_gcode.name)"
        Write-Output "corrected_prepare=$($manifest.files.corrected_prepare_gcode.name)"
        Write-Output "corrected_pattern=$($manifest.files.corrected_pattern_gcode.name)"
        Write-Output "profile=$DerivedProfile"
        Write-Output "target=X34,Y266 farther=+0.010mm"
        Write-Output "estimated_filament_g_per_variant=$($manifest.pattern.estimated_filament_g)"
        Write-Output 'physical_tool=unresolved_until_fresh_cfs_confirmation'
        Write-Output 'pattern_requires=-FilamentRouteConfirmed -PurgeFlowConfirmed'
        Write-Output 'PLAN_MESH_EDGE_DIAGNOSTIC_V1_OK'
    }
    'Preflight' { Invoke-Preflight }
    'RecoverRobust' { Invoke-RecoverRobust }
    'Deploy' { Invoke-Deploy }
    'Upload' { Invoke-Upload }
    'PrepareSource' { Invoke-PrepareVariant 'source' }
    'PrepareCorrected' { Invoke-PrepareVariant 'corrected' }
    'CheckPrepared' { Invoke-RecoverPrepared }
    'PrintSource' { Invoke-PrintPattern 'source' }
    'PrintCorrected' { Invoke-PrintPattern 'corrected' }
    'WaitComplete' { Invoke-WaitComplete }
    'Rollback' { Invoke-Rollback }
    'FinalValidate' { Invoke-FinalValidate }
}
