[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Gate,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]{8}-[0-9]{6}-g4-control-foundation-v3$')]
    [string]$CaptureId,

    [Parameter(Mandatory = $true)]
    [string]$EvidenceDirectory,

    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{2,31}$')]
    [string]$Username,

    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'PowerShell 7 ou plus recent est obligatoire pour cette saisie securisee.'
}
$requiredGate = 'G4-K1-CONTROL-FOUNDATION-V3'
if (-not $Execute -or $Gate -cne $requiredGate) {
    throw "Action bloquee : -Execute et -Gate '$requiredGate' sont obligatoires."
}

if (-not $Username) {
    $Username = Read-Host 'Nom du compte Mainsail (3 a 32 caracteres)'
}
if ($Username -cnotmatch '^[A-Za-z0-9][A-Za-z0-9._-]{2,31}$') {
    throw 'Nom de compte invalide.'
}

$password = Read-Host 'Mot de passe (16 a 128 caracteres ASCII, sans espace)' -AsSecureString
$confirmation = Read-Host 'Confirme le mot de passe' -AsSecureString

function Convert-SecureStringForComparison {
    param([Parameter(Mandatory = $true)][Security.SecureString]$Value)

    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
}

$plainPassword = Convert-SecureStringForComparison $password
$plainConfirmation = Convert-SecureStringForComparison $confirmation
try {
    if ($plainPassword.Length -lt 16 -or $plainPassword.Length -gt 128 -or
        $plainPassword -cnotmatch '^[\x21-\x7E]+$') {
        throw 'Le mot de passe doit contenir 16 a 128 caracteres ASCII imprimables sans espace.'
    }
    if (-not [string]::Equals($plainPassword, $plainConfirmation, [StringComparison]::Ordinal)) {
        throw 'Les deux mots de passe sont differents.'
    }
}
finally {
    $plainPassword = $null
    $plainConfirmation = $null
}

$deployer = Join-Path $PSScriptRoot 'deploy-control-foundation.ps1'
& $deployer `
    -Action SetGatewayAccount `
    -Gate $Gate `
    -CaptureId $CaptureId `
    -EvidenceDirectory $EvidenceDirectory `
    -GatewayUsername $Username `
    -GatewayPassword $password `
    -Execute
