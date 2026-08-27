[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SessionDirectory,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SessionLabel
)

$ErrorActionPreference = 'Stop'
$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$rawRoot = Join-Path $workspaceRoot 'inventory\raw'
if (-not (Test-Path -LiteralPath $rawRoot -PathType Container)) {
    throw 'Le dossier prive inventory/raw est introuvable.'
}
if (-not (Test-Path -LiteralPath $SessionDirectory -PathType Container)) {
    New-Item -ItemType Directory -Path $SessionDirectory -Force | Out-Null
}
$resolvedRawRoot = (Resolve-Path -LiteralPath $rawRoot).Path
$resolvedSession = (Resolve-Path -LiteralPath $SessionDirectory).Path
if (-not $resolvedSession.StartsWith($resolvedRawRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Le dossier de session doit rester sous inventory/raw.'
}

$capturePath = Join-Path $resolvedSession "$SessionLabel.private.txt"
if (Test-Path -LiteralPath $capturePath) {
    throw 'La capture existe deja. Utilise un nouvel identifiant.'
}

$remoteScript = @'
set -eu
BOX_ROOT=/usr/data/creality/userdata/box
echo '=== FILE_LIST_BEGIN ==='
find "$BOX_ROOT" -maxdepth 2 -type f -print 2>/dev/null | sort
echo '=== FILE_LIST_END ==='
for name in material_box_config.json material_box_info.json material_modify_info.json material_database.json material_option.json tn_data.json; do
  path="$BOX_ROOT/$name"
  marker=$(echo "$name" | tr '.-' '__' | tr '[:lower:]' '[:upper:]')
  echo "=== ${marker}_BEGIN ==="
  if [ -f "$path" ]; then
    sha256sum "$path"
    cat "$path"
    echo
  else
    echo 'ABSENT'
  fi
  echo "=== ${marker}_END ==="
done
echo 'MATERIAL_DATABASE_READ_ONLY_OK'
'@

$remoteBytes = [Text.Encoding]::UTF8.GetBytes($remoteScript.Replace("`r`n", "`n"))
$remoteBase64 = [Convert]::ToBase64String($remoteBytes)
$remoteCommand = "echo $remoteBase64 | base64 -d | sh"

& ssh.exe `
    -o 'BatchMode=yes' `
    -o 'PasswordAuthentication=no' `
    -o 'KbdInteractiveAuthentication=no' `
    -o 'ServerAliveInterval=10' `
    -o 'ServerAliveCountMax=3' `
    k1max-root `
    $remoteCommand | Set-Content -LiteralPath $capturePath -Encoding utf8

$sshExitCode = $LASTEXITCODE
Write-Host "MATERIAL_DATABASE_READ_ONLY_CLOSED exit_code=$sshExitCode capture=$capturePath"
exit $sshExitCode
