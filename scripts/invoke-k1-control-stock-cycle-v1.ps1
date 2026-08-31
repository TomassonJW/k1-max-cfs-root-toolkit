[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Status', 'Files', 'PrepareT1A', 'Begin', 'CleanConfirm', 'CameraPass', 'CameraFail', 'ToolChange', 'Abort')]
    [string]$Action,
    [string]$PrinterHost = 'k1max-root',
    [string]$Filename = 'K1-INTEGRATED-T1A-2LAYER.gcode',
    [string]$EvidenceId = '',
    [string]$TargetRoute = '',
    [string]$EvidenceDirectory = '',
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$DriverPath = Join-Path $WorkspaceRoot 'packages\k1-control-v1\stock-derived-cycle-activation-v1\remote_control_action.py'
$EffectActions = @('Begin', 'CleanConfirm', 'CameraPass', 'CameraFail', 'ToolChange', 'Abort')

if ($Action -in $EffectActions -and -not $Execute) {
    throw "L'action $Action exige -Execute."
}

function Invoke-BoundedApi {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Payload
    )
    $json = $Payload | ConvertTo-Json -Depth 12 -Compress
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json))
    $program = [IO.File]::ReadAllText($DriverPath).Replace("`r`n", "`n")
    $arguments = @(
        '-o', 'BatchMode=yes',
        '-o', 'PasswordAuthentication=no',
        '-o', 'KbdInteractiveAuthentication=no',
        '-o', 'ConnectTimeout=8',
        $PrinterHost,
        "/usr/share/klippy-env/bin/python -B - '$Name' '$encoded'"
    )
    $output = $program | & ssh.exe @arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Action API $Name KO : $($output -join "`n")"
    }
    $document = (($output -join "`n") | ConvertFrom-Json)
    if ($document.error) {
        throw "Action API $Name refusee : $($document.error.message)"
    }
    return $document.result
}

$result = $null
switch ($Action) {
    'Status' { $result = Invoke-BoundedApi 'status' @{} }
    'Files' { $result = Invoke-BoundedApi 'files' @{} }
    'PrepareT1A' {
        $inventory = @(
            [ordered]@{
                route = 'T1A'
                available = $true
                material = [ordered]@{
                    reference_id = 'cfs-000001-0000000'
                    material_type = 'PLA'
                    color = '0000000'
                    diameter_mm = 1.75
                    thermal_recipe_id = 'pla-190'
                    user_approved = $true
                }
            }
        )
        [void](Invoke-BoundedApi 'inventory' @{inventory_json = (ConvertTo-Json -InputObject $inventory -Depth 12 -Compress)})
        $result = Invoke-BoundedApi 'select' @{filename = $Filename; initial_route = 'T1A'}
    }
    'Begin' {
        $result = Invoke-BoundedApi 'begin' @{
            operator_present = $true
            camera_available = $true
            machine_clear = $true
        }
    }
    'CleanConfirm' {
        $result = Invoke-BoundedApi 'clean-confirm' @{
            operator_confirmed = $true
            nozzle_visibly_clean = $true
            plate_clean = $true
            confirmation_fresh = $true
        }
    }
    'CameraPass' {
        if ([string]::IsNullOrWhiteSpace($EvidenceId)) { throw 'EvidenceId est obligatoire.' }
        $result = Invoke-BoundedApi 'camera-verdict' @{verdict = 'PASS'; evidence_id = $EvidenceId}
    }
    'CameraFail' {
        if ([string]::IsNullOrWhiteSpace($EvidenceId)) { throw 'EvidenceId est obligatoire.' }
        $result = Invoke-BoundedApi 'camera-verdict' @{verdict = 'FAIL'; evidence_id = $EvidenceId}
    }
    'ToolChange' {
        if ($TargetRoute -notmatch '^T[12][ABCD]$') { throw 'TargetRoute invalide.' }
        $result = Invoke-BoundedApi 'tool-change' @{target_route = $TargetRoute}
    }
    'Abort' { $result = Invoke-BoundedApi 'abort' @{} }
}

if (-not [string]::IsNullOrWhiteSpace($EvidenceDirectory)) {
    $root = [IO.Path]::GetFullPath((Join-Path $WorkspaceRoot $EvidenceDirectory))
    $workspace = [IO.Path]::GetFullPath($WorkspaceRoot)
    if (-not $root.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'EvidenceDirectory hors workspace.'
    }
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $result | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $root ("api-$($Action.ToLowerInvariant()).json")) -Encoding UTF8
}

$result | ConvertTo-Json -Depth 30
