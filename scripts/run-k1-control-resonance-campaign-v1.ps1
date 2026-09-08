# Campagne de résonance complète sur la K1 : les deux axes, les deux courroies,
# puis l'analyse des cinq filtres hors ligne.
#
# Le script ne décide rien et n'applique rien. Il mesure, contrôle, rapatrie les
# données brutes dans le dépôt et rend un rapport lisible. L'écriture des
# valeurs retenues est une décision séparée, prise après lecture.
#
# Compter une vingtaine de minutes : quatre balayages d'environ quatre minutes,
# plus l'analyse, qui est lente sur le processeur de la machine.
[CmdletBinding()]
param(
    [string]$Target = 'k1max-root',
    [string]$Label = (Get-Date -Format 'yyyy-MM-dd') + '-resonance',
    [switch]$AnalyseOnly
)

$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repo 'experiments/2026-09-08-resonance-tete-modifiee'
$destination = Join-Path $repo ('experiments/' + $Label)
$distant = '/tmp/campagne-resonance'

# Affiche la sortie distante sans la renvoyer : une valeur de retour non
# affectee serait reaffichee par PowerShell, et le compte rendu paraitrait
# contenir deux campagnes la ou il n'y en a eu qu'une.
function Invoke-Remote {
    param([string]$Command, [switch]$Quiet)
    $sortie = Get-Remote $Command
    if (-not $Quiet) { $sortie | ForEach-Object { Write-Host $_ } }
}

function Get-Remote {
    param([string]$Command)
    $sortie = & ssh $Target $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        $sortie | ForEach-Object { Write-Host $_ }
        throw "commande distante en echec ($LASTEXITCODE) : $Command"
    }
    return $sortie
}

# Les scripts partent en base64, par morceaux : le pipeline texte de PowerShell
# re-encode les commentaires accentues et ajoute une marque d'ordre d'octets, et
# une ligne de commande distante trop longue fait fermer la connexion par la
# machine. En base64 tronconne il n'y a que de l'ASCII, et jamais de commande
# demesuree.
function Send-Script {
    param([string]$Nom, [string]$Cible)
    $chemin = Join-Path $source $Nom
    $octets = [System.IO.File]::ReadAllBytes($chemin)
    $b64 = [System.Convert]::ToBase64String($octets)
    $taille = 1500
    $premier = $true
    for ($i = 0; $i -lt $b64.Length; $i += $taille) {
        $morceau = $b64.Substring($i, [Math]::Min($taille, $b64.Length - $i))
        $redirection = if ($premier) { '>' } else { '>>' }
        & ssh $Target "printf '%s' '$morceau' $redirection $Cible.b64"
        if ($LASTEXITCODE -ne 0) { throw "envoi de $Nom en echec (morceau a l'octet $i)" }
        $premier = $false
    }
    & ssh $Target "base64 -d < $Cible.b64 > $Cible && rm -f $Cible.b64"
    if ($LASTEXITCODE -ne 0) { throw "decodage de $Nom en echec sur la machine" }

    # Un envoi tronque ou abime se voit ici, pas au milieu des balayages.
    $arrives = [int](& ssh $Target "wc -c < $Cible")
    if ($arrives -ne $octets.Length) {
        throw "$Nom est arrive abime : $($octets.Length) octets envoyes, $arrives arrives"
    }
    & ssh $Target "python3 -m py_compile $Cible"
    if ($LASTEXITCODE -ne 0) { throw "$Nom n'est pas lisible par la machine apres envoi" }
    Write-Host ("envoye : {0} ({1} octets)" -f $Nom, $octets.Length)
}

Write-Host "Cible                : $Target"
Write-Host "Donnees rapatriees   : $destination"

Send-Script -Nom 'prepare-analyseur.py' -Cible '/tmp/prepare-analyseur.py'
Send-Script -Nom 'campagne-resonance.py' -Cible '/tmp/campagne-resonance.py'
Send-Script -Nom 'analyse-campagne.py' -Cible '/tmp/analyse-campagne.py'

# L'analyseur non bride est pose avant la campagne : s'il refuse de se
# construire, autant le savoir avant vingt minutes de balayages.
Write-Host "`n--- preparation de l'analyseur"
Invoke-Remote "python3 /tmp/prepare-analyseur.py 2>&1 | grep -vE 'SyntaxWarning|if ret'"
Invoke-Remote "cp /tmp/analyse-campagne.py /tmp/sc/analyse-campagne.py" -Quiet

if (-not $AnalyseOnly) {
    Write-Host "`n--- campagne : quatre balayages, environ vingt minutes"
    Invoke-Remote "python3 -u /tmp/campagne-resonance.py $distant"
}

New-Item -ItemType Directory -Force -Path $destination | Out-Null
foreach ($nom in @('resonance-x.csv', 'resonance-y.csv', 'courroie-a.csv', 'courroie-b.csv', 'campagne.json')) {
    $contenu = & ssh $Target "cat $distant/$nom" 2>$null
    if ($LASTEXITCODE -eq 0 -and $contenu) {
        Set-Content -LiteralPath (Join-Path $destination $nom) -Value $contenu -Encoding UTF8
        Write-Host ("rapatrie : {0}" -f $nom)
    }
    else {
        Write-Warning "absent sur la machine : $nom"
    }
}

Write-Host "`n--- analyse des cinq filtres"
$rapport = Get-Remote "python3 /tmp/sc/analyse-campagne.py $distant 2>&1 | grep -vE 'SyntaxWarning|if ret'"
$rapport | ForEach-Object { Write-Host $_ }
$cheminRapport = Join-Path $destination 'rapport.txt'
Set-Content -LiteralPath $cheminRapport -Value $rapport -Encoding UTF8

Write-Host "`nRapport ecrit dans $cheminRapport"
Write-Host "Rien n'a ete applique : le choix des filtres et leur ecriture sont une etape separee."
