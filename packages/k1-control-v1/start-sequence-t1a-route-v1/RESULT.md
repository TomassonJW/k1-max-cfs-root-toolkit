# Résultat courant

Statut : **tentative KO opérateur ; `T1A` établi ; récupération verte**.

La gate est limitée à la restauration et à la relecture d'une route unique
`T1A`. Elle réutilise l'action stock déjà observée sans créer de transport CFS
propriétaire. Le chargement reste une action humaine unique et visible.

La capture privée
`20260828-goal3-start-sequence-t1a-route-v1-preflight` confirme `standby`, les
deux CFS connectés, aucune route, les chauffes à zéro, le `11 × 11`, le Z
`−0,04 mm`, le propriétaire `idle` et les six empreintes exactes. Aucun effet
n'a eu lieu.

Pendant la capture réelle, Thomas a d'abord lancé par erreur la vérification
stock du filament. Elle a référencé XYZ, demandé `200 °C` et remplacé le mesh
actif par `default`. Le chargement `T1A` lancé ensuite a demandé `220 °C`, puis
établi exactement une route `T1A` avec débit visible normal. Aucun second
chargement n'a été demandé.

La récupération bornée a rechargé une fois le `11 × 11` et libéré les axes.
Deux relectures identiques confirment `T1A`, commande vide, chauffes zéro, Z
`−0,04 mm`, configurations exactes et propriétaire `idle`. La gate de route
reste honnêtement KO à cause du mauvais bouton, mais son état final sûr permet
de préparer le premier départ court sans rejouer le chargement.
