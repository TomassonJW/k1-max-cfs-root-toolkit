# Résultat

Statut actuel : `CLOSED_CFS_AND_START_OK_WITH_HUMAN_Z_INTERVENTION`.

- fichier privé de deux couches reproduit et vérifié hors imprimante ;
- la lecture live a prouvé que `END_PRINT` appelait encore `BOX_END` et
  `BOX_END_PRINT` sous la capture privée
  `20260829-goal3-start-owner-safe-end-readonly-v1` ; cette version distante
  n'a jamais été lancée ;
- la fin corrigée coupe les chauffes, désarme le propriétaire, revient à
  `idle`, coupe les ventilateurs et libère les moteurs sans macro stock ;
- la capture privée
  `20260829-goal3-start-owner-physical-keep-correct-t1a-v1-run` est close avec
  l'automatisation verte, T1A conservé, le `11 × 11` actif, les cibles à zéro
  et les axes libérés ;
- verdict humain : `PURGE OK — 2 COUCHES OK À -0,19` ; le Z accepté `−0,04`
  n'est donc pas qualifié sans intervention ;
- la calibration utilisait une stabilisation plateau de `200 s`, absente du
  départ possédé. Cette différence thermique doit être isolée avant de décider
  une recalibration ;
- la fin minimale n'a ni parqué la tête ni présenté le plateau. Elle ne vaut
  pas qualification de la future séquence de fin de production ;
- T1A n'a volontairement été ni coupé, ni retiré, ni rembobiné conformément à
  la politique de conservation du bon filament ;
- aucune tentative automatique supplémentaire n'est permise.
