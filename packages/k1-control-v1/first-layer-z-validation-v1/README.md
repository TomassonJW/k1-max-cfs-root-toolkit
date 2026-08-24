# FIRST-LAYER-Z-VALIDATION-V1

Ce paquet prépare un seul carré `260 × 260 × 0,20 mm` pour valider physiquement
le Z avec le profil robuste `6 × 6`.

Le fichier Orca source impose `z_offset = 0`, garde un post-traitement vide et
ne contient aucune commande Z absolue ou relative cachée. La copie ajoute
uniquement `KCTRL_PRODUCTION_ARM` après `START_PRINT`. Cette garde charge le
profil robuste et applique la valeur acceptée stockée, actuellement `−0,04 mm`.

Thomas reste devant la K1 pendant la couche et peut ajuster le Z depuis l'écran.
Codex capture parallèlement l'origine Z effective. Aucun passage composite ne
fait partie de cette gate.
