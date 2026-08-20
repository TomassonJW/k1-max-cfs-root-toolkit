[CmdletBinding()]
param(
    [string]$FixtureRoot = "inventory/raw/g3-production/20260820-0815-cfs-temp-preflight"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Assert-True {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )

    if (-not $Condition) {
        throw "ASSERTION_KO: $Message"
    }
}

function Get-MacroBlock {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $escaped = [Regex]::Escape($Name)
    $match = [Regex]::Match(
        $Text,
        "(?ms)^\[gcode_macro $escaped\]\r?\n.*?(?=^\[|\z)"
    )
    Assert-True $match.Success "macro $Name absent"
    return $match.Value
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$fixturePath = (Resolve-Path (Join-Path $repoRoot $FixtureRoot)).Path
$patchPath = Join-Path $repoRoot "overrides/cfs-temperature-contract/active-config.patch"
$overlayPath = Join-Path $repoRoot "overrides/cfs-temperature-contract/cfs-temperature-contract.cfg"
$workRoot = Join-Path $repoRoot ".codex-work/cfs-temperature-contract-test"
$configRoot = Join-Path $workRoot "config"

$expectedHashes = @{
    "printer.private.cfg" = "272640237E20659CF01F3268ED4CB0282B098C3D613E94BF84A3B80CAAC3C3B0"
    "gcode_macro.private.cfg" = "864FEDDE88FBB345C220AE5658F7B04779B3981BD78D68EDA6FA63C59C79A04F"
    "box.private.cfg" = "E7A6B26DF58A9FA8E49D3AF6845F5A0937A790C8EF494B96EC72FD7392ABC7A7"
}

foreach ($entry in $expectedHashes.GetEnumerator()) {
    $source = Join-Path $fixturePath $entry.Key
    Assert-True (Test-Path -LiteralPath $source -PathType Leaf) "fixture absente: $($entry.Key)"
    $actualHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    Assert-True ($actualHash -eq $entry.Value) "empreinte inattendue: $($entry.Key)"
}

if (Test-Path -LiteralPath $workRoot) {
    $resolvedWork = (Resolve-Path -LiteralPath $workRoot).Path
    Assert-True ($resolvedWork.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) "dossier de test hors dépôt"
    Remove-Item -LiteralPath $resolvedWork -Recurse -Force
}

try {
    New-Item -ItemType Directory -Path $configRoot -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $fixturePath "printer.private.cfg") -Destination (Join-Path $configRoot "printer.cfg")
    Copy-Item -LiteralPath (Join-Path $fixturePath "gcode_macro.private.cfg") -Destination (Join-Path $configRoot "gcode_macro.cfg")
    Copy-Item -LiteralPath (Join-Path $fixturePath "box.private.cfg") -Destination (Join-Path $configRoot "box.cfg")
    Copy-Item -LiteralPath $overlayPath -Destination (Join-Path $configRoot "cfs_temperature_contract.cfg")

    Push-Location $repoRoot
    try {
        & git apply --check --unidiff-zero --whitespace=error-all --directory=.codex-work/cfs-temperature-contract-test $patchPath
        Assert-True ($LASTEXITCODE -eq 0) "le patch ne s'applique pas aux fichiers exacts"
        & git apply --unidiff-zero --whitespace=error-all --directory=.codex-work/cfs-temperature-contract-test $patchPath
        Assert-True ($LASTEXITCODE -eq 0) "échec d'application du patch"
    }
    finally {
        Pop-Location
    }

    $printer = Get-Content -LiteralPath (Join-Path $configRoot "printer.cfg") -Raw
    $box = Get-Content -LiteralPath (Join-Path $configRoot "box.cfg") -Raw
    $macros = Get-Content -LiteralPath (Join-Path $configRoot "gcode_macro.cfg") -Raw
    $overlay = Get-Content -LiteralPath (Join-Path $configRoot "cfs_temperature_contract.cfg") -Raw

    Assert-True ([Regex]::Matches($printer, "\[include cfs_temperature_contract\.cfg\]").Count -eq 1) "inclusion du contrat incorrecte"
    Assert-True ([Regex]::Matches($box, "(?m)^Tn_extrude_temp:\s*195\b").Count -eq 1) "température CFS 195 absente ou multiple"
    Assert-True (-not [Regex]::IsMatch($box, "(?m)^Tn_extrude_temp:\s*220\b")) "ancienne température CFS 220 encore active"

    $start = Get-MacroBlock $macros "START_PRINT"
    Assert-True ($start.IndexOf("CFS_TEMP_CONTRACT_START", [StringComparison]::Ordinal) -ge 0) "contrat absent du démarrage"
    Assert-True ($start.IndexOf("CFS_TEMP_CONTRACT_START", [StringComparison]::Ordinal) -lt $start.IndexOf("BOX_START_PRINT", [StringComparison]::Ordinal)) "le contrat doit précéder le premier appel CFS"

    $pause = Get-MacroBlock $macros "PAUSE"
    $pauseHook = [Regex]::Match($pause, "(?m)^\s+CFS_TEMP_CONTRACT_PAUSE\s*$")
    $pauseBase = [Regex]::Match($pause, "(?m)^\s+PAUSE_BASE\s*$")
    Assert-True ($pauseHook.Success -and $pauseBase.Success -and $pauseHook.Index -lt $pauseBase.Index) "la cible doit être mémorisée avant la pause"

    $resume = Get-MacroBlock $macros "RESUME"
    $resumeHook = [Regex]::Match($resume, "(?m)^\s+CFS_TEMP_CONTRACT_ARM_GUARD\s*$")
    $resumeBase = [Regex]::Match($resume, "(?m)^\s+RESUME_BASE .*$")
    Assert-True ($resumeHook.Success -and $resumeBase.Success -and $resumeHook.Index -lt $resumeBase.Index) "la garde doit être armée avant la reprise"

    $endPrint = Get-MacroBlock $macros "END_PRINT_NO_M84"
    Assert-True ($endPrint.Contains("CFS_TEMP_CONTRACT_CLEAR")) "nettoyage du contrat absent en fin de travail"

    foreach ($required in @(
        "CFS_MATERIAL=GEEETECH_PLA is required",
        "only accepts FIRST=190 and NORMAL=195",
        "printer.box.auto_refill",
        "printer.box.filament_useup",
        "UPDATE_DELAYED_GCODE ID=CFS_TEMP_CONTRACT_GUARD DURATION=0.25",
        "M104 S{desired}"
    )) {
        Assert-True ($overlay.Contains($required)) "protection absente: $required"
    }

    Write-Output "CFS_TEMP_CONTRACT_TEST_OK"
    Write-Output "FIXTURE_HASHES_OK"
    Write-Output "PATCH_APPLY_OK"
    Write-Output "FAIL_CLOSED_CONTRACT_OK"
    Write-Output "REFILL_GUARD_ORDER_OK"
}
finally {
    if (Test-Path -LiteralPath $workRoot) {
        $resolvedWork = (Resolve-Path -LiteralPath $workRoot).Path
        if ($resolvedWork.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedWork -Recurse -Force
        }
    }
}
