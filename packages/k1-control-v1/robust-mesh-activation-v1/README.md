# G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1

Statut : **préflight live en lecture seule vert ; activation non autorisée**.

Cette gate lève le verrou placé entre le Goal 2 et le Goal 3. Elle distingue
deux profils déjà présents sur la K1 :

- `k1_p001_t055_r001_n06x06` : profil robuste quotidien qualifié ;
- `k1_p001_t055_r001_n11x11` : source physique composite, conservée mais non
  promue comme robuste à cause des défauts sévères observés aux bords.

Le préflight vérifie l'état au repos, les chauffes à zéro, les axes libérés, le
Z accepté, les deux CFS, les empreintes de configuration et les trois matrices
connues. L'activation envoie au plus une fois :

`BED_MESH_PROFILE LOAD=k1_p001_t055_r001_n06x06`

Elle relit immédiatement le profil actif et la matrice. Après toute ambiguïté
postérieure à l'envoi, elle tente une seule remise au profil précédent
`k1_p001_t055_r001_n11x11`, sans retenter le robuste.

Aucun fichier distant, restart, chauffage, mouvement, homing, palpage,
extrusion ou impression n'est possible dans ce paquet. La réussite de cette
gate ne commence pas automatiquement les tranches physiques du Goal 3.

La capture privée `20260827-robust-mesh-activation-v1-preflight` a obtenu
`PREFLIGHT_OK` sans envoyer de G-code. Voir `RESULT.md` et `evidence-map.json`.

## Lecture seule

```powershell
.\packages\k1-control-v1\robust-mesh-activation-v1\run_live.ps1 -Action Preflight
```

## Activation future après revue et GO exact

Autorisation attendue :

`GO G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1`

Commande correspondante :

```powershell
.\packages\k1-control-v1\robust-mesh-activation-v1\run_live.ps1 `
  -Action Activate `
  -Execute `
  -Gate G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1
```
