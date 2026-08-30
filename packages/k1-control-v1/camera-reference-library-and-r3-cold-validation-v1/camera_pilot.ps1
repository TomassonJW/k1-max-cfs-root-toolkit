[CmdletBinding(DefaultParameterSetName = 'Live')]
param(
    [Parameter(Mandatory = $true)]
    [string]$SessionDirectory,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SessionLabel,

    [Parameter(ParameterSetName = 'Local', Mandatory = $true)]
    [string]$SnapshotPath,

    [string]$ReferencePath,

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$PrinterHost = 'k1max-root'
)

$ErrorActionPreference = 'Stop'

function Get-GrayValue {
    param([System.Drawing.Color]$Color)
    return (0.299 * $Color.R) + (0.587 * $Color.G) + (0.114 * $Color.B)
}

function Get-RegionMetrics {
    param(
        [System.Drawing.Bitmap]$Bitmap,
        [System.Drawing.Rectangle]$Region,
        [int]$Step
    )

    $sum = 0.0
    $sumSquared = 0.0
    $count = 0
    $gradientSum = 0.0
    $gradientCount = 0

    for ($y = $Region.Top; $y -lt $Region.Bottom; $y += $Step) {
        $previous = $null
        for ($x = $Region.Left; $x -lt $Region.Right; $x += $Step) {
            $gray = Get-GrayValue -Color $Bitmap.GetPixel($x, $y)
            $sum += $gray
            $sumSquared += $gray * $gray
            $count += 1
            if ($null -ne $previous) {
                $gradientSum += [Math]::Abs($gray - $previous)
                $gradientCount += 1
            }
            $previous = $gray
        }
    }

    if ($count -eq 0 -or $gradientCount -eq 0) {
        throw 'La zone image ne contient aucun echantillon exploitable.'
    }
    $mean = $sum / $count
    $variance = [Math]::Max(0.0, ($sumSquared / $count) - ($mean * $mean))
    return [ordered]@{
        sampled_pixels = $count
        mean_luminance = [Math]::Round($mean, 6)
        luminance_stddev = [Math]::Round([Math]::Sqrt($variance), 6)
        sampled_gradient = [Math]::Round($gradientSum / $gradientCount, 6)
    }
}

function Get-NormalizedMeanAbsoluteDifference {
    param(
        [System.Drawing.Bitmap]$Current,
        [System.Drawing.Bitmap]$Reference,
        [System.Drawing.Rectangle]$Region,
        [int]$Step
    )

    $differenceSum = 0.0
    $count = 0
    for ($y = $Region.Top; $y -lt $Region.Bottom; $y += $Step) {
        for ($x = $Region.Left; $x -lt $Region.Right; $x += $Step) {
            $currentGray = Get-GrayValue -Color $Current.GetPixel($x, $y)
            $referenceGray = Get-GrayValue -Color $Reference.GetPixel($x, $y)
            $differenceSum += [Math]::Abs($currentGray - $referenceGray)
            $count += 1
        }
    }
    if ($count -eq 0) {
        throw 'La comparaison image ne contient aucun echantillon.'
    }
    return [Math]::Round(($differenceSum / $count) / 255.0, 6)
}

function Save-RegionImage {
    param(
        [System.Drawing.Bitmap]$Bitmap,
        [System.Drawing.Rectangle]$Region,
        [string]$Path
    )

    $crop = New-Object System.Drawing.Bitmap($Region.Width, $Region.Height)
    try {
        $graphics = [System.Drawing.Graphics]::FromImage($crop)
        try {
            $destination = New-Object System.Drawing.Rectangle(0, 0, $Region.Width, $Region.Height)
            $graphics.DrawImage($Bitmap, $destination, $Region, [System.Drawing.GraphicsUnit]::Pixel)
        }
        finally {
            $graphics.Dispose()
        }
        $crop.Save($Path, [System.Drawing.Imaging.ImageFormat]::Jpeg)
    }
    finally {
        $crop.Dispose()
    }
}

function Resolve-PrinterIpv4 {
    param([string]$Alias)

    $sshConfig = @(& ssh.exe -G $Alias 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Impossible de lire la configuration SSH de $Alias."
    }
    $hostName = $null
    foreach ($line in $sshConfig) {
        if ($line -match '^hostname\s+(\S+)$') {
            $hostName = $Matches[1]
            break
        }
    }
    if ([string]::IsNullOrWhiteSpace($hostName)) {
        throw "La configuration SSH de $Alias ne contient pas de HostName."
    }
    $address = $null
    if (-not [Net.IPAddress]::TryParse($hostName, [ref]$address)) {
        $addresses = [Net.Dns]::GetHostAddresses($hostName)
        $address = $addresses | Where-Object { $_.AddressFamily -eq [Net.Sockets.AddressFamily]::InterNetwork } | Select-Object -First 1
    }
    if ($null -eq $address -or $address.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) {
        throw "L'adresse de $Alias ne se resout pas en IPv4."
    }
    return $address.ToString()
}

$packageRoot = $PSScriptRoot
$workspaceRoot = (Resolve-Path (Join-Path $packageRoot '..\..\..')).Path
$rawRoot = (Resolve-Path (Join-Path $workspaceRoot 'inventory\raw')).Path
$requestedSession = [IO.Path]::GetFullPath($SessionDirectory)
if (-not $requestedSession.StartsWith($rawRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Le dossier de session doit rester sous inventory/raw.'
}
if (-not (Test-Path -LiteralPath $requestedSession -PathType Container)) {
    New-Item -ItemType Directory -Path $requestedSession | Out-Null
}
$resolvedSession = (Resolve-Path -LiteralPath $requestedSession).Path

$libraryPath = Join-Path $packageRoot 'reference-library.json'
$library = Get-Content -LiteralPath $libraryPath -Raw | ConvertFrom-Json
$capturePath = Join-Path $resolvedSession "$SessionLabel.jpg"
$manifestPath = Join-Path $resolvedSession "$SessionLabel.analysis.json"
if (Test-Path -LiteralPath $manifestPath) {
    throw 'Cette analyse existe deja. Utilise un nouvel identifiant de session.'
}

$mode = $PSCmdlet.ParameterSetName
$resolvedIpv4 = $null
$imagePath = $null
if ($mode -eq 'Live') {
    if (Test-Path -LiteralPath $capturePath) {
        throw 'Cette capture existe deja. Utilise un nouvel identifiant de session.'
    }
    $resolvedIpv4 = Resolve-PrinterIpv4 -Alias $PrinterHost
    $snapshotUri = "http://${resolvedIpv4}:8080/?action=snapshot"
    Invoke-WebRequest -UseBasicParsing -Method Get -Uri $snapshotUri -TimeoutSec 10 -OutFile $capturePath
    $imagePath = $capturePath
}
else {
    $imagePath = (Resolve-Path -LiteralPath $SnapshotPath).Path
}

$referenceResolved = $null
if (-not [string]::IsNullOrWhiteSpace($ReferencePath)) {
    $referenceResolved = (Resolve-Path -LiteralPath $ReferencePath).Path
}

Add-Type -AssemblyName System.Drawing
$bitmap = New-Object System.Drawing.Bitmap($imagePath)
$referenceBitmap = $null
try {
    $expectedWidth = [int]$library.frame.width_px
    $expectedHeight = [int]$library.frame.height_px
    if ($bitmap.Width -ne $expectedWidth -or $bitmap.Height -ne $expectedHeight) {
        throw "Cadrage inattendu : $($bitmap.Width)x$($bitmap.Height), attendu ${expectedWidth}x${expectedHeight}."
    }
    if ($null -ne $referenceResolved) {
        $referenceBitmap = New-Object System.Drawing.Bitmap($referenceResolved)
        if ($referenceBitmap.Width -ne $expectedWidth -or $referenceBitmap.Height -ne $expectedHeight) {
            throw 'La reference ne respecte pas le cadrage canonique.'
        }
    }

    $step = [int]$library.frame.comparison_sample_step_px
    $minimumGradient = [double]$library.frame.minimum_sampled_gradient
    $matchThreshold = [double]$library.frame.candidate_match_max_normalized_mad
    $regions = [ordered]@{}
    $allSharp = $true
    $allCandidateMatches = $true

    foreach ($name in @('nozzle', 'bin', 'bed')) {
        $definition = $library.regions.$name
        $rectangle = New-Object System.Drawing.Rectangle(
            [int]$definition.left,
            [int]$definition.top,
            [int]$definition.width,
            [int]$definition.height
        )
        if ($rectangle.Left -lt 0 -or $rectangle.Top -lt 0 -or $rectangle.Right -gt $bitmap.Width -or $rectangle.Bottom -gt $bitmap.Height) {
            throw "La zone $name sort du cadre canonique."
        }
        $metrics = Get-RegionMetrics -Bitmap $bitmap -Region $rectangle -Step $step
        $sharpEnough = [double]$metrics.sampled_gradient -ge $minimumGradient
        if (-not $sharpEnough) {
            $allSharp = $false
        }
        $comparison = $null
        if ($null -ne $referenceBitmap) {
            $difference = Get-NormalizedMeanAbsoluteDifference -Current $bitmap -Reference $referenceBitmap -Region $rectangle -Step $step
            $candidateMatch = $difference -le $matchThreshold
            if (-not $candidateMatch) {
                $allCandidateMatches = $false
            }
            $comparison = [ordered]@{
                normalized_mean_absolute_difference = $difference
                candidate_match = $candidateMatch
            }
        }
        $cropPath = Join-Path $resolvedSession "$SessionLabel.$name.jpg"
        Save-RegionImage -Bitmap $bitmap -Region $rectangle -Path $cropPath
        $regions[$name] = [ordered]@{
            bounds = @($rectangle.Left, $rectangle.Top, $rectangle.Width, $rectangle.Height)
            metrics = $metrics
            sharp_enough = $sharpEnough
            comparison = $comparison
            private_crop_file = [IO.Path]::GetFileName($cropPath)
        }
    }

    $frameHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $imagePath).Hash.ToLowerInvariant()
    $referenceHash = $null
    if ($null -ne $referenceResolved) {
        $referenceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $referenceResolved).Hash.ToLowerInvariant()
    }
    $result = [ordered]@{
        schema = 1
        mission = 'G4-K1-CONTROL-CAMERA-REFERENCE-LIBRARY-AND-R3-COLD-VALIDATION-V1'
        session_label = $SessionLabel
        captured_at = (Get-Date).ToString('o')
        mode = $mode.ToLowerInvariant()
        ssh_alias = $PrinterHost
        address_resolved_to_ipv4 = ($null -ne $resolvedIpv4)
        resolved_address_exported = $false
        http_methods = @(if ($mode -eq 'Live') { 'GET' })
        frame = [ordered]@{
            width_px = $bitmap.Width
            height_px = $bitmap.Height
            sha256 = $frameHash
            cadrage_ok = $true
            sharpness_ok = $allSharp
        }
        reference = [ordered]@{
            provided = ($null -ne $referenceResolved)
            id = if ($null -ne $referenceResolved) { 'SAFE_IDLE_PARK' } else { $null }
            sha256 = $referenceHash
            all_regions_candidate_match = if ($null -ne $referenceResolved) { $allCandidateMatches } else { $null }
        }
        regions = $regions
        semantic_state_confirmed = $false
        visual_review_required = $true
        automatic_gate_command = $null
        effects = [ordered]@{
            gcode = $false
            heater_action = $false
            motion_action = $false
            extrusion_action = $false
            cfs_action = $false
            remote_file_write = $false
            service_action = $false
        }
    }
    $result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $manifestPath -Encoding utf8
    if (-not $allSharp) {
        throw "Image trop floue pour continuer. Analyse conservee dans $manifestPath"
    }
    Write-Host "CAMERA_PILOT_FRAME_OK semantic_confirmation=false analysis=$manifestPath"
}
finally {
    if ($null -ne $referenceBitmap) {
        $referenceBitmap.Dispose()
    }
    $bitmap.Dispose()
}
