# Résultat

Statut : `INSTALLED_VALIDATED_COLD_ZERO_LOGICAL_ROUTE_AFTER_RESTART`.

R4 choisit entre deux chemins. Une géométrie encore valide
garde `T1A` engagé et ne fait aucune mesure. Une géométrie perdue impose le
cycle frais qui sépare la référence de contact et l'insertion officielle. Dans
les deux cas, le bloc exécuté avec filament engagé contient zéro `G28`, zéro
`ACCURATE_G28` et zéro calibration de mesh. Le mesh et le Z sont réarmés sans
mesure avant toute purge ou trajectoire basse.

Le vérificateur dédié est vert. Le parse Jinja exact dans le Python déjà présent
sur la K1 est vert sur les `20` blocs, sans fichier distant, G-code, chauffe,
mouvement, extrusion, CFS ou service. Le déployeur remplace un seul fichier,
fait un backup exact, observe le vrai redémarrage Klipper, remet le `11 × 11`,
fait seulement un autotest froid du surveillant et restaure l'ancienne version
au premier écart.

R4 est posé sous la capture
`20260831-000831-g4-k1-control-start-sequence-owner-preinsert-geometry-r4`.
La première tentative de préflight s'est fermée sans effet sur une baseline
locale V1 trop ancienne ; la lecture a prouvé la R2 installée exacte, puis le
correctif `bccf344` a épinglé cette vraie source de rollback avant la pose.

Le backup R2, le remplacement unique, la transition réelle Klipper, la remise
du `11 × 11` et l'autotest froid sont verts. Le rollback n'a pas servi. Aucun
chauffage, mouvement, déplacement de filament, extrusion ou travail n'a été
commandé.

La lecture indépendante finale confirme `standby`, cibles zéro, axes libérés,
`11 × 11`, Z `−0,04`, propriétaire au repos et zéro avertissement. Après le
restart, les deux CFS sont connectés mais la route logique est vide. Aucun
mouvement de filament n'ayant été commandé, sa position physique n'est pas
prouvée par cette télémétrie. Elle devra être résolue avant la future géométrie
de contact.

La pose close n'autorise ni l'essai physique ni la production.

Vérifications finales : `28/28` tests ciblés verts sur R4, ADR-034, le
tombstone R3 et le registre Goal 3 ; suite complète `813` tests, soit `810`
verts et `3` ignorés connus ; `git diff --check` vert.
