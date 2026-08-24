# G4-K1-CONTROL-COMPOSITE-FIRST-LAYER-COMPARISON-V1

Date : 2026-08-24

Statut : **paire préparée hors imprimante ; passage robuste en attente**

## Question unique

Le profil composite `k1_p001_t055_r001_n11x11` améliore-t-il de façon visible
la régularité d'une vraie première couche par rapport au profil robuste
`k1_p001_t055_r001_n06x06` ?

Sans gain clair, le profil robuste reste le défaut et le mode Précision reste
caché dans K1 Control.

## Entrée retenue

La comparaison réutilise le carré privé déjà qualifié pendant G3 :

- empreinte source :
  `50b54577a4b8a76a0bb5fb2b48e915d1dc6ea9e5bb87aa1f32404c559a54f856` ;
- une seule couche `200 × 200 × 0,20 mm` ;
- PLA Geeetech, outil `T0` ;
- plateau `55 °C`, buse `190 °C` ;
- environ `9,91 g` et `18 min 44 s` par passage ;
- même plaque `PEI_TEXTURED_A`.

Le fichier a déjà été imprimé physiquement. Son démarrage Orca historique et
son `SET_GCODE_OFFSET Z=0.27` restent inchangés et identiques entre les deux
passages. Cette gate ne prétend donc pas valider le Z de production.

## Isolation de la variable

`prepare_gcodes.py` refuse toute autre empreinte, toute source multi-couche,
toute séquence de départ différente et toute commande Bed Mesh préexistante.
Les deux sorties ont le même nombre d'octets à la longueur du nom près et ne
diffèrent sémantiquement que par une ligne ajoutée juste après `START_PRINT` :

1. `BED_MESH_PROFILE LOAD="k1_p001_t055_r001_n06x06"` ;
2. `BED_MESH_PROFILE LOAD="k1_p001_t055_r001_n11x11"`.

La capture privée préparée est
`20260824-161503-g4-k1-control-composite-first-layer-comparison-v1`.
Empreintes :

- robuste : `ffeb317c713c4a6390e5133b65fd930b2da46682256dd53fd0b48f4f372c95db` ;
- composite : `39360643c1b14b3d578b9318ea2d3eb8f946a2d5de6a82428f189af7052afbe2`.

## Déroulé borné

1. Préflight frais : standby, chauffes à zéro, filament présent, deux CFS,
   profils exacts et configuration persistante conforme.
2. Charger le passage robuste, observer que le profil `6 × 6` est actif pendant
   la couche, attendre la fin, photographier et repérer la pièce.
3. Retirer la pièce sans changer de plaque ni de face ; nettoyer de la même
   façon que pour le second passage.
4. Charger le passage composite, observer le profil `11 × 11`, attendre la fin,
   photographier et repérer la pièce.
5. Recharger le profil robuste, couper les cibles si nécessaire et vérifier
   l'état final.

Le deuxième passage ne démarre jamais automatiquement derrière le premier : la
pièce imprimée doit être retirée physiquement.

## Verdict

Le mode Précision ne peut être exposé que si les photos et le constat humain
montrent une amélioration utile sur les zones où le `6 × 6` présente un défaut.
Un résultat équivalent, ambigu ou moins bon ferme l'exposition UI, sans invalider
le profil composite comme outil de diagnostic.

Cette gate ne valide ni Orca, ni `START_PRINT`, ni le retrait du `+0,27 mm`, ni
la propriété des températures CFS, ni l'autonomie production.
