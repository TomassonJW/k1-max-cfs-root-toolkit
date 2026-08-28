# Préflight propriétaire CFS S12 V1

Cette gate relie la cartographie publique au matériel exact de cette K1 Max,
sans rien faire bouger.

Elle réalise une seule session SSH et seulement des lectures : état Moonraker,
aide des commandes déjà enregistrées, empreintes des fichiers, options utiles
de `box.cfg`, appels `BOX_*` visibles dans les configurations et chaînes sûres
du binaire CFS. Le binaire n'est ni copié ni exécuté en plus de son usage normal
par Klipper. Son contenu est seulement lu pour retrouver les noms déjà présents.

Les champs `sn` et `uuid` sont supprimés sur la K1 avant la sortie JSON. Aucun
journal n'est lu. Aucun G-code, chauffage, mouvement, effet CFS, fichier
distant ou redémarrage n'est permis.

Même si la carte est conforme, elle autorise seulement le prochain travail hors
imprimante. Chaque chargement, coupe, retrait, purge, fin de bobine ou reprise
restera une gate physique séparée avec Thomas devant la machine.

## Exécution revue

```powershell
& .\packages\k1-control-v1\cfs-s12-owner-preflight-v1\capture_live_read_only.ps1 `
  -SessionDirectory .\inventory\raw\<capture> `
  -SessionLabel <label>
```

La capture privée reste sous `inventory/raw`. `analyze_capture.py` produit
ensuite uniquement le résultat nettoyé et borné qui peut être versionné.
