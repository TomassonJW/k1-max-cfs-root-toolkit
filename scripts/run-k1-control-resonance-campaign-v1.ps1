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

function Invoke-Remote {
    param([string]$Command, [switch]$Quiet)
    $sortie = & ssh $Target $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        $sortie | ForEach-Object { Write-Host $_ }
        throw "commande distante en echec ($LASTEXITCODE) : $Command"
    }
    if (-not $Quiet) { $sortie | ForEach-Object { Write-Host $_ } }
    return $sortie
}

function Send-Script {
    param([string]$Nom, [string]$Cible)
    Get-Content -LiteralPath (Join-Path $source $Nom) -Raw -Encoding UTF8 |
        & ssh $Target "cat > $Cible"
    if ($LASTEXITCODE -ne 0) { throw "envoi de $Nom en echec" }
}

Write-Host "Cible                : $Target"
Write-Host "Donnees rapatriees   : $destination"

Send-Script -Nom 'prepare-analyseur.py' -Cible '/tmp/prepare-analyseur.py'
Send-Script -Nom 'campagne-resonance.py' -Cible '/tmp/campagne-resonance.py'
Send-Script -Nom 'analyse-campagne.py' -Cible '/tmp/analyse-campagne.py'

# L'analyseur non bride est pose avant la campagne : s'il refuse de se
# construire, autant le savoir avant vingt minutes de balayages.
Write-Host "`n--- preparation de l'analyseur"
Invoke-Remote 'python3 /tmp/prepare-analyseur.py 2>&1 | grep -vE "SyntaxWarning|if ret"'
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
$rapport = Invoke-Remote "python3 /tmp/sc/analyse-campagne.py $distant 2>&1 | grep -vE 'SyntaxWarning|if ret'"
$cheminRapport = Join-Path $destination 'rapport.txt'
Set-Content -LiteralPath $cheminRapport -Value $rapport -Encoding UTF8

Write-Host "`nRapport ecrit dans $cheminRapport"
Write-Host "Rien n'a ete applique : le choix des filtres et leur ecriture sont une etape separee."
