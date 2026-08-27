# Résultat

Statut : **RESTORE_OK ; `11 × 11` actif ; gate close**.

Le préflight nettoyé
`20260827-best-current-mesh-restore-v1-preflight-clean` a confirmé le `6 × 6`
actif, la K1 au repos et froide, les deux profils exacts et les configurations
inchangées. Il n'a exporté que l'état et le filament des deux CFS.

La capture `20260827-best-current-mesh-restore-v1-run` a ensuite envoyé une
seule fois :

`BED_MESH_PROFILE LOAD=k1_p001_t055_r001_n11x11`

Sa relecture immédiate a obtenu `RESTORE_OK`. Aucun rollback, fichier distant,
restart, chauffe, mouvement, homing, palpage ou impression n'a eu lieu. Deux
lectures indépendantes ont enfin confirmé le `11 × 11` actif, sa matrice exacte,
les configurations inchangées, les axes libérés, les cibles zéro et le Z
accepté `−0,04 mm`.

Cette clôture ne qualifie aucun profil comme robuste. Tous les profils actuels
restent affectés par les bords ; le `11 × 11` est seulement le meilleur profil
observé et la source immuable de futures corrections point par point.
