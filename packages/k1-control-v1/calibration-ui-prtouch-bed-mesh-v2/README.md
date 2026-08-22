# CALIBRATION-UI-PRTOUCH-BED-MESH-V2

Mise à jour bornée du composant `k1_control_probe_count` après la preuve réelle
XS3002 du 23 août 2026.

Le premier adaptateur commutait correctement `probe_count` avant la chauffe,
mais laissait l'algorithme persistant à `lagrange`. Klipper refuse donc de
démarrer en `9 x 9`, avant que l'argument dynamique `bicubic` de la campagne ne
puisse être exécuté.

V2 commute et vérifie atomiquement le couple :

- `6 x 6 + lagrange` pour le niveau rapide ;
- `9 x 9 + bicubic` pour le niveau standard ;
- `11 x 11 + bicubic` pour le niveau précis ;
- `15 x 15 + bicubic` pour le niveau expert.

Le backup de campagne précède toujours la mutation. Les deux valeurs sont
restaurées ensemble après coupure des chauffes ou après tout échec de démarrage.
Sur la configuration réelle de la K1, `lagrange` est implicite : la ligne
`algorithm` est absente de `printer.cfg`. La révision corrigée accepte cette
forme, ajoute `algorithm: bicubic` uniquement pendant les matrices supérieures à
6, puis restitue exactement l'absence initiale de la ligne. La validation refuse
désormais aussi tout composant signalé dans `failed_components` par Moonraker.
La pose V2 remplace seulement le composant déjà installé, redémarre uniquement
le Moonraker dédié et ne lance aucune action physique.
