# CALIBRATION-UI-PRTOUCH-BED-MESH-V2

Mise à jour bornée du composant `k1_control_probe_count` après la preuve réelle
XS3002 du 23 août 2026.

Le premier adaptateur commutait correctement `probe_count` avant la chauffe,
mais laissait l'algorithme persistant à `lagrange`. Klipper refuse donc de
démarrer en `9 x 9`, avant que l'argument dynamique `bicubic` de la campagne ne
puisse être exécuté.

La campagne suivante a établi une limite plus basse : le pilote propriétaire
`prtouch_v2_wrapper.py` plante exactement au point 37. V2 n'accepte donc plus
qu'un seul couple sûr : `6 x 6 + lagrange`.

Le backup de campagne précède toujours la mutation. Les deux valeurs sont
restaurées ensemble après coupure des chauffes ou après tout échec de démarrage.
Sur la configuration réelle de la K1, `lagrange` est implicite : la ligne
`algorithm` est absente de `printer.cfg`. La révision corrigée accepte cette
forme et restitue exactement l'absence initiale de la ligne. Toute demande
différente de `6 x 6` est refusée avant mouvement. La validation refuse
désormais aussi tout composant signalé dans `failed_components` par Moonraker.
La pose V2 remplace seulement le composant déjà installé, redémarre uniquement
le Moonraker dédié et ne lance aucune action physique.
