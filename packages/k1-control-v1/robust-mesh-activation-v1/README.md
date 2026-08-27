# G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1

Statut technique historique : **close OK ; commande exécutée et revérifiée**.
Statut produit actuel : **nomenclature et choix annulés par ADR-029 ; ne pas
rejouer**.

Le nom historique de cette gate est conservé pour la traçabilité. Il ne prouve
pas que le `6 × 6` est robuste. Tous les profils actuels ont des défauts de bord
et le `11 × 11` est le meilleur profil observé. La gate corrective
`G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-V1` l'a remis actif.

Cette gate lève le verrou placé entre le Goal 2 et le Goal 3. Elle distingue
deux profils déjà présents sur la K1 :

- `k1_p001_t055_r001_n06x06` : ancien profil quotidien, avec défauts de bord ;
- `k1_p001_t055_r001_n11x11` : meilleur profil observé, source physique
  immuable, avec défauts de bord.

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

Le GO exact a été consommé le 27 août 2026. Le préflight frais a obtenu
`PREFLIGHT_OK`, puis la capture
`20260827-robust-mesh-activation-v1-authorized-run` a obtenu `ACTIVATION_OK`
après une seule commande. Aucun rollback n'a été nécessaire. Deux lectures
indépendantes ont ensuite confirmé le robuste actif, les configurations
inchangées, les chauffes à zéro et la machine au repos. Voir `RESULT.md` et
`evidence-map.json`.

## Préflight historique

Cette commande attend le `11 × 11` comme état précédent. Elle est conservée
pour la traçabilité mais ne doit pas être rejouée après la clôture :

```powershell
.\packages\k1-control-v1\robust-mesh-activation-v1\run_live.ps1 -Action Preflight
```

## Commande exacte exécutée

Cette commande est conservée pour la traçabilité. Le GO est consommé et elle ne
doit pas être rejouée au titre de cette gate :

```powershell
.\packages\k1-control-v1\robust-mesh-activation-v1\run_live.ps1 `
  -Action Activate `
  -Execute `
  -Gate G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1
```
