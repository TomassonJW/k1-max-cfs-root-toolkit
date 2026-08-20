# ADR-003 — Surcharger `START_PRINT` par un point d'entrée Z sécurisé

Date : 2026-08-20

Statut : **rejeté le 2026-08-20 ; jamais déployé ; remplacé par ADR-004**

> Cette décision est conservée comme historique. Son paquet fixe ne doit jamais
> être déployé. Voir `ADR-004-pilotage-parametrable-et-calibration-persistante.md`.

## Contexte

Le profil Orca actuel envoie `G28`, puis `T0`, avant `START_PRINT`. Le stock
refait ensuite une référence, nettoie la buse près du plateau, refait une
référence précise, contrôle un mesh avec génération et sauvegarde automatiques,
charge le CFS et purge. Le `+0,27 mm` du post-traitement arrive seulement après
le retour de `START_PRINT`.

Les corrections faites en direct appellent `Z_OFFSET_APPLY_PROBE`. Après la fin
du G-code, une commande externe applique l'inverse de la correction et prépare
de nouveau zéro. Modifier seulement `END_PRINT` ne peut donc pas supprimer ce
producteur externe.

## Options

- ajout tardif après le stock : refusé, car la purge antérieure reste exposée ;
- modification directe de `gcode_macro.cfg` : refusée, car elle dégrade la
  comparaison et le rollback ;
- remplacement simultané du nettoyage, mesh, CFS et interface : refusé, car il
  mélange plusieurs classes de changement ;
- include original chargé après le stock : retenu.

## Décision historique, désormais refusée

La version capturée de Klipper lit les doublons avec
`RawConfigParser(strict=False)`. Le paquet remplace donc uniquement le corps de
`START_PRINT` par un include tardif, sans toucher au fichier constructeur.

Il conserve le nom public et le post-traitement Orca, exige un nettoyage manuel
confirmé une fois, établit la référence finale, charge le mesh `default`,
applique `+0,27 mm`, puis ouvre une garde avant CFS et purge. La fin capture la
correction observée avant l'effacement externe, sans la réappliquer
automatiquement.

Les homings et mesures sont les descentes contrôlées nécessaires à la référence.
La garde interdit les descentes de production et toute extrusion avant que
référence finale, mesh et correction soient prêts.

## Conséquences

- confirmation humaine de propreté avant chaque départ ;
- arrêt si le mesh `default` manque ;
- outils initiaux bornés à `T0`–`T7` ;
- nettoyage automatique, mesh adaptatif, températures CFS et UI restent séparés ;
- autre correction que `+0,27 mm` soumise à un futur diff et une future gate ;
- la capture de fin évite la perte silencieuse, mais son acceptation reste
  volontaire et manuelle.

Ces conséquences ne sont plus acceptables comme base de production : valeur Z
fixe, mesh unique et absence d'interface/état persistant. ADR-004 remplace ce
lot par un système paramétrable conçu et testé comme un tout.
