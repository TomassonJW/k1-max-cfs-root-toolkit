# BEST-CURRENT-MESH-RESTORE-AFTER-POWER-CYCLE-V1

Statut : **candidat hors imprimante, figé et testé ; aucune connexion ni action
K1 encore exécutée par ce paquet**.

Ce successeur remplace uniquement l'ancienne gate de remise du mesh dans le cas
prouvé après extinction : route logique volatile perdue et profil actif revenu
à `default`. Il ne modifie pas l'ancienne mission close ni ses preuves.

Il accepte comme état initial seulement `default` ou le profil quotidien
`6 × 6`. Il exige ensuite une route unique `T1A`, les deux CFS connectés, aucune
commande CFS active, la machine froide et immobile, les axes libérés, le Z
accepté `−0,04 mm`, le propriétaire de démarrage R2 au repos et les empreintes
exactes revues.

L'unique effet autorisé est :

`BED_MESH_PROFILE LOAD=k1_p001_t055_r001_n11x11`

La commande n'est jamais retentée. Si sa réponse ou la relecture est ambiguë,
le programme recharge une seule fois le profil exact observé avant l'essai. Il
n'envoie aucune commande de chauffe, mouvement, homing, palpage, extrusion,
filament, service ou fichier distant.

## Utilisation

Le plan reste entièrement local :

```powershell
.\packages\k1-control-v1\best-current-mesh-restore-after-power-cycle-v1\run_live.ps1 -Action Plan
```

Le préflight est en lecture seule et ne prend pas de drapeau de mutation. La
remise réelle exige l'autorisation exacte du contrat figé.
