# CALIBRATION-UI-PRTOUCH-PRESETS-V1

Correctif statique séparé de l'interface K1 Control pour ne présenter que des
matrices réellement exécutables par le chemin spiralé propriétaire
`prtouch_v3` de cette K1.

- retire le choix pair `4 x 4` ;
- conserve les choix impairs personnalisés `3 x 3` et `5 x 5` ;
- conserve les niveaux produit `6 x 6`, `9 x 9`, `11 x 11` et `15 x 15` ;
- remplace le repli JavaScript `4 x 4` par `5 x 5` quand l'utilisateur choisit
  bicubique depuis `3 x 3` ;
- ne lance ni chauffe, ni mouvement, ni calibration et ne redémarre aucun
  service.

Le serveur reste la garde finale : une requête forgée vers une matrice paire
est refusée par l'adaptateur `k1_control_probe_count` avant toute chauffe.
