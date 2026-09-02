<#
.SYNOPSIS
    Pose l'éditeur de maillage sur l'imprimante et le fait démarrer au boot.

.DESCRIPTION
    L'éditeur était installé à la main et relancé à la main : chaque coupure de
    courant le laissait mort, sans rien pour le dire. Ce script pose les quatre
    fichiers du paquet et le service init.d qui le rallume au démarrage, puis
    prouve que la page répond.

    Aucune écriture machine n'est faite ici : le serveur posé ne fait que servir
    la page et passer la main à KCTRL_MESH_APPLY, qui reste l'unique écrivain.

.PARAMETER Action
    Status   lit l'état posé, sans rien écrire.
    Deploy   copie les fichiers, installe le service, redémarre, vérifie.
    Rollback arrête le service et retire le fichier init.d, en laissant le
             paquet en place : l'éditeur redevient lançable à la main.
#>
[CmdletBinding()]
param(
    [ValidateSet('Status', 'Deploy', 'Rollback')]
    [string]$Action = 'Status'
)

$ErrorActionPreference = 'Stop'

$SshHost = 'k1max-root'
$Package = Join-Path $PSScriptRoot '..\packages\k1-control-v1\mesh-editor-live-v1'
$RemoteRoot = '/usr/data/k1-control-mesh-editor'
$ServiceName = 'S58k1_control_mesh_editor'
$RemoteService = "/etc/init.d/$ServiceName"

function Invoke-Printer {
    param([Parameter(Mandatory = $true)][string]$Command)

    # Pas de 2>&1 : sous PowerShell 5.1 la sortie d'erreur d'un exe natif
    # deviendrait une erreur terminante, et un simple avertissement du service
    # ferait echouer la pose.
    $output = & ssh.exe '-o' 'BatchMode=yes' '-o' 'ConnectTimeout=10' $SshHost $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Commande refusée par l'imprimante ($LASTEXITCODE) : $Command"
    }
    return $output
}

function Copy-ToPrinter {
    param(
        [Parameter(Mandatory = $true)][string]$Local,
        [Parameter(Mandatory = $true)][string]$Remote
    )

    # -O : le dropbear de la machine n'a pas de sftp-server, seul l'ancien
    # protocole scp passe.
    & scp.exe '-O' '-o' 'BatchMode=yes' $Local "${SshHost}:$Remote" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Copie refusée : $Local" }
}

# La page ne prouve rien par son code HTTP : un module JavaScript cassé laisse
# le serveur répondre 200 sur une page qui ne démarre jamais. On vérifie donc
# la syntaxe avant de poser, et l'API après.
function Test-EditorSyntax {
    $app = Join-Path $Package 'www\app.mjs'
    $node = Get-Command 'node.exe' -ErrorAction SilentlyContinue
    if (-not $node) {
        Write-Warning 'node introuvable : syntaxe de app.mjs non vérifiée avant la pose.'
        return
    }
    & $node.Source '--check' $app
    if ($LASTEXITCODE -ne 0) { throw "app.mjs ne compile pas : pose annulée." }
}

function Get-RemoteStatus {
    $probe = "[ -f $RemoteService ] && echo service:pose || echo service:absent; " +
        "$RemoteService status 2>/dev/null || true; " +
        'wget -q -O- http://127.0.0.1:7130/api/state > /dev/null && echo page:ok || echo page:ko'
    return Invoke-Printer -Command $probe
}

switch ($Action) {
    'Status' {
        Get-RemoteStatus
    }

    'Deploy' {
        Test-EditorSyntax

        Invoke-Printer -Command "mkdir -p $RemoteRoot/www" | Out-Null
        Copy-ToPrinter -Local (Join-Path $Package 'server.py') -Remote "$RemoteRoot/server.py"
        foreach ($asset in @('index.html', 'app.mjs', 'styles.css')) {
            Copy-ToPrinter -Local (Join-Path $Package "www\$asset") -Remote "$RemoteRoot/www/$asset"
        }
        Copy-ToPrinter -Local (Join-Path $Package "init.d\$ServiceName") -Remote $RemoteService
        Invoke-Printer -Command "chmod 755 $RemoteService" | Out-Null
        Invoke-Printer -Command "$RemoteService restart" | Out-Null

        Start-Sleep -Seconds 2
        Get-RemoteStatus
    }

    'Rollback' {
        Invoke-Printer -Command "$RemoteService stop || true" | Out-Null
        Invoke-Printer -Command "rm -f $RemoteService" | Out-Null
        Get-RemoteStatus
    }
}
