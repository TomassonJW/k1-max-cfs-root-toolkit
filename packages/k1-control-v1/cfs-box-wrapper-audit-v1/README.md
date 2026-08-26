# CFS Box Wrapper Audit V1

Statut : audit hors imprimante clos ; adaptateur fermé ; production fermée.

Ce paquet vérifie sans charger le module propriétaire :

- l'empreinte et l'en-tête ELF du `box_wrapper` exact ;
- la présence des commandes et des chemins thermiques/géométriques visibles ;
- l'ordre des preuves de l'incident du 26 août ;
- le verdict séparé de chaque primitive envisagée.

Le résultat sûr n'est pas une primitive autorisée. `BOX_EXTRUDE_MATERIAL` est
refusée parce que le passage observé lui attribue la sélection `220 °C` et le
positionnement interne. `BOX_EXTRUDER_EXTRUDE` et `BOX_MATERIAL_FLUSH` restent
non qualifiées : le script les appelait à la suite et ne fournit pas de
frontière d'état complète pour chacune.

`adapter-contract.json` fixe l'ordre futur et les six états à surveiller. Il
ne contient volontairement aucune primitive appelable et son statut interdit
pose et essai physique. La position froide observée est conservée comme
candidate, pas comme autorisation de mouvement.

## Exécution sur les fixtures nettoyées

```powershell
python packages/k1-control-v1/cfs-box-wrapper-audit-v1/analyze_evidence.py `
  packages/k1-control-v1/cfs-box-wrapper-audit-v1/contract.json `
  packages/k1-control-v1/cfs-box-wrapper-audit-v1/fixtures/box-wrapper.strings.redacted.txt `
  packages/k1-control-v1/cfs-box-wrapper-audit-v1/fixtures/incident.redacted.txt
```

Le code retour `1` représente le refus attendu. Le code `2` représente une
preuve incomplète ou incohérente. L'outil ne se connecte jamais à la K1.

Le binaire et les journaux bruts restent dans `inventory/raw/`, ignoré par Git.
Ils ne doivent jamais être publiés.
