# CFS Minimal Owner Protocol V1

Statut : **gate close en KO borné ; aucune trame appelable ; aucun transport**.

Ce paquet répond à une question étroite : les captures privées existantes
suffisent-elles à construire sans invention le protocole d'un propriétaire
filament minimal séparé ? La réponse est non.

La carte nettoyée relie les requêtes et réponses retenues aux empreintes et aux
lignes exactes des captures privées. Elle montre deux adresses interrogées,
mais une seule route d'action : `T1A`, adresse 1, slot A. Le journal ne contient
pas de trame d'effet pour le second CFS, les slots B/C/D, le retrait, la coupe
isolée ou la purge isolée. Il ne prouve pas non plus comment exclure puis rendre
la main au propriétaire constructeur.

## Contenu

- `contract.json` : verdict KO, liste appelable vide et règles de blocage ;
- `evidence-map.json` : carte nettoyée des preuves privées, sans identifiant
  matériel ;
- `verify_private_evidence.py` : vérification statique locale des empreintes,
  lignes et absences annoncées ;
- `emulator.py` : automate hors ligne, sans réseau, série, SSH, G-code ou
  chargement du module MIPS ;
- `scenarios.json` : 25 scénarios déterministes couvrant doublon, perte,
  réponse tardive, reconnexion, révision de route et deux CFS ;
- `FUTURE-EVIDENCE-PLAN.md` : preuves exactes encore requises ;
- `RESULT.md` : clôture opérationnelle.

## Exécution locale

Depuis la racine du dépôt :

```powershell
python packages\k1-control-v1\cfs-minimal-owner-protocol-v1\verify_private_evidence.py
python packages\k1-control-v1\cfs-minimal-owner-protocol-v1\emulator.py
```

La première commande ne fait que lire et hacher les captures déjà présentes.
Elle n'importe jamais le `.so`. La seconde ne lit aucune capture privée et ne
possède aucun transport.

Un résultat vert signifie seulement que le **refus est cohérent et
reproductible**. Il ne qualifie aucune commande CFS.
