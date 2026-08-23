# CALIBRATION-UI-PRTOUCH-PRESETS-V1

Correctif statique séparé de l'interface K1 Control après preuve de la limite
réelle du chemin spiralé propriétaire `prtouch_v3` de cette K1.

- expose uniquement `6 x 6 + lagrange` ;
- bloque `3 x 3`, `4 x 4`, `5 x 5`, `9 x 9`, `11 x 11` et `15 x 15` ;
- explique dans la page la limite exacte de 36 points physiques ;
- ne lance ni chauffe, ni mouvement, ni calibration et ne redémarre aucun
  service.

Le serveur reste la garde finale : toute requête forgée vers une autre matrice
est refusée par l'adaptateur `k1_control_probe_count` avant toute chauffe.
