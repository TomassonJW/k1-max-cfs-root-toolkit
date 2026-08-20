# Contrat Orca K1-CONTROL-V1

Statut : **candidat hors ligne, ne pas importer**.

Ces trois champs remplacent ensemble le départ, la fin et le changement de
filament. Aucun ne doit être copié seul dans Orca. Le profil actif de Thomas et
le post-traitement `+0,27 mm` ne sont pas modifiés par cette mission.

## Ce que le départ transmet

- version du contrat et mode `PRODUCTION` ;
- nom stable de la plaque et température du plateau ;
- premier outil et température initiale ;
- température de chaque outil réellement utilisé, jusqu'à T7 ;
- limites de la première couche pour choisir un mesh adaptatif ;
- sélection automatique des profils de nettoyage, mesh et purge.

`plate_name` doit devenir un identifiant stable sans espace, par exemple
`PEI_TEXTURED_A`. L'interface affiche ensuite un libellé agréable. Un nom vide,
libre ou inconnu bloque le travail au lieu de choisir un mesh au hasard.

## Ce que le changement transmet

Orca 2.4.2 fournit `previous_extruder`, `next_extruder`, `old_filament_temp`,
`new_filament_temp`, `flush_length` et `toolchange_z`. Le wrapper enregistre la
cible attendue, laisse le `Tn` stock piloter le CFS, puis vérifie et restaure la
cible. Cela couvre T0 à T7 et donc les deux CFS logiques. Une écriture CFS tardive
encore présente pendant la validation réelle rendra le test KO ; elle ne sera
pas masquée.

## Bascule future obligatoire

La pose sera atomique : macros côté machine, trois champs Orca, contrôle de
version et retrait de l'ancien post-traitement au même moment. Avant cette
bascule, les fichiers sont des fixtures de conception. Après rollback, les
quatre champs actifs et le script `+0,27 mm` doivent revenir exactement à leurs
empreintes de départ.
