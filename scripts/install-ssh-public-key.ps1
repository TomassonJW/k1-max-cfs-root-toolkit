[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Target,

    [Parameter(Mandatory = $true)]
    [string]$KnownHostsPath,

    [Parameter(Mandatory = $true)]
    [string]$PublicKeyPath,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]{8}-[0-9]{6}$')]
    [string]$BackupId,

    [Parameter(Mandatory = $true)]
    [string]$EvidencePath,

    [Parameter(Mandatory = $true)]
    [string]$ResultPath
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $KnownHostsPath -PathType Leaf)) {
    throw "Fichier known_hosts introuvable."
}

if (-not (Test-Path -LiteralPath $PublicKeyPath -PathType Leaf)) {
    throw "Cle publique introuvable."
}

$publicKey = (Get-Content -LiteralPath $PublicKeyPath -Raw).Trim()
if ($publicKey -notmatch '^(ssh-ed25519|ecdsa-sha2-nistp256) [A-Za-z0-9+/]+={0,3} [A-Za-z0-9._@-]+$') {
    throw "La cle publique dediee n'a pas le format attendu."
}

if ($publicKey.Contains("'")) {
    throw "La cle publique contient un caractere refuse."
}

$evidenceDirectory = Split-Path -Parent $EvidencePath
$resultDirectory = Split-Path -Parent $ResultPath
New-Item -ItemType Directory -Path $evidenceDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $resultDirectory -Force | Out-Null

$remoteScript = @"
set -eu

auth_dir='/root/.ssh'
auth_file='/root/.ssh/authorized_keys'
backup_file='/root/.ssh/authorized_keys.codex-backup-$BackupId'
public_key='$publicKey'

if [ -e "`$backup_file" ]; then
    echo 'G4_SSH_KEY_KO reason=backup_already_exists'
    exit 41
fi

if [ -d "`$auth_dir" ]; then
    dir_before='present'
elif [ -e "`$auth_dir" ]; then
    echo 'G4_SSH_KEY_KO reason=ssh_path_not_directory'
    exit 42
else
    dir_before='absent'
fi

if [ -e "`$auth_file" ]; then
    if [ ! -f "`$auth_file" ] || [ -L "`$auth_file" ]; then
        echo 'G4_SSH_KEY_KO reason=authorized_keys_not_regular_file'
        exit 43
    fi
    file_before='present'
    before_sha256=`$(sha256sum "`$auth_file" | awk '{print `$1}')
    cp -p "`$auth_file" "`$backup_file"
    backup_sha256=`$(sha256sum "`$backup_file" | awk '{print `$1}')
    if [ "`$before_sha256" != "`$backup_sha256" ]; then
        echo 'G4_SSH_KEY_KO reason=backup_checksum_mismatch'
        exit 44
    fi
else
    file_before='absent'
    before_sha256='ABSENT'
    backup_sha256='ABSENT'
fi

umask 077
mkdir -p "`$auth_dir"
chmod 700 "`$auth_dir"

tmp_file="`$auth_dir/.authorized_keys.codex-`$`$"
trap 'rm -f "`$tmp_file"' EXIT HUP INT TERM

if [ "`$file_before" = 'present' ]; then
    cat "`$auth_file" > "`$tmp_file"
else
    : > "`$tmp_file"
fi

if grep -Fqx "`$public_key" "`$tmp_file"; then
    key_action='already_present'
else
    printf '%s\n' "`$public_key" >> "`$tmp_file"
    key_action='added'
fi

chmod 600 "`$tmp_file"
mv "`$tmp_file" "`$auth_file"
trap - EXIT HUP INT TERM

key_count=`$(grep -Fxc "`$public_key" "`$auth_file" || true)
if [ "`$key_count" -ne 1 ]; then
    echo 'G4_SSH_KEY_KO reason=key_count_not_one'
    exit 45
fi

after_sha256=`$(sha256sum "`$auth_file" | awk '{print `$1}')

echo "G4_SSH_KEY_BACKUP_OK id=$BackupId dir_before=`$dir_before file_before=`$file_before before_sha256=`$before_sha256 backup_sha256=`$backup_sha256"
echo "G4_SSH_KEY_INSTALL_OK action=`$key_action after_sha256=`$after_sha256 key_count=`$key_count"
"@

Write-Host 'Une derniere authentification par mot de passe est necessaire.'
Write-Host 'La saisie reste invisible. Ne ferme pas cette fenetre avant le resultat.'
Write-Host ''

$remoteScriptBytes = [System.Text.Encoding]::UTF8.GetBytes($remoteScript.Replace("`r`n", "`n"))
$remoteScriptBase64 = [Convert]::ToBase64String($remoteScriptBytes)
$remoteCommand = "echo $remoteScriptBase64 | base64 -d | sh"

& ssh.exe `
    -tt `
    -o "UserKnownHostsFile=$KnownHostsPath" `
    -o 'StrictHostKeyChecking=yes' `
    -o 'PubkeyAuthentication=no' `
    $Target `
    $remoteCommand | Tee-Object -LiteralPath $EvidencePath

$sshExitCode = $LASTEXITCODE
if ($sshExitCode -eq 0) {
    Set-Content -LiteralPath $ResultPath -Value 'G4_SSH_KEY_INSTALL_SESSION_OK' -Encoding ascii
    Write-Host ''
    Write-Host 'G4_SSH_KEY_INSTALL_SESSION_OK'
}
else {
    Set-Content -LiteralPath $ResultPath -Value "G4_SSH_KEY_INSTALL_SESSION_KO exit_code=$sshExitCode" -Encoding ascii
    Write-Host ''
    Write-Host "G4_SSH_KEY_INSTALL_SESSION_KO exit_code=$sshExitCode"
}

Read-Host 'Appuie sur Entree pour fermer cette fenetre'
exit $sshExitCode
