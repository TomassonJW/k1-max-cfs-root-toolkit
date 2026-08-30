# Bibliothèque caméra et validation froide R3 V1

Cette tranche construit le capteur caméra minimal demandé après l'incident R5
et vérifie hors effet le candidat de départ R3.

Le pilote `camera_pilot.ps1` reste volontairement simple :

1. il résout l'adresse IPv4 de `k1max-root` avec `ssh -G`, sans ouvrir de
   session SSH ;
2. il effectue un seul `GET` sur le service caméra local ;
3. il exige une image `1280 × 720`, mesure une netteté minimale et découpe les
   zones buse, bac et plateau ;
4. il compare ces zones à une référence fournie, mais ne transforme jamais une
   ressemblance en verdict physique automatique ;
5. il écrit uniquement dans `inventory/raw`, qui reste privé et ignoré par
   Git.

La bibliothèque versionnée contient une seule référence acquise :
`SAFE_IDLE_PARK`, issue de l'image prise après l'annulation sûre de R5. Les
états `ROUGH_HOME_READY`, `BIN_PURGE_ACTIVE`, `BIN_RELEASED_CLEAN`,
`PRIME_OUTSIDE_BED` et `FIRST_LAYER_GOOD` restent explicitement absents.

`validate_r3_cold.py` vérifie que les deux pauses caméra bloquent réellement la
suite, que seules `PAUSE_BASE` et `RESUME_BASE` sont utilisées et qu'un timeout
coupe les chauffes sans fabriquer de confirmation caméra. Le parse Jinja réel
est séparé dans `validate_with_k1_jinja.ps1` : il envoie le candidat par stdin au
Python déjà présent sur la K1, ne crée aucun fichier distant et n'exécute aucun
G-code.

Cette tranche n'est pas un candidat de pose. Elle n'autorise ni chauffe,
mouvement, extrusion, homing, impression, commande CFS ou modification de la
K1.
