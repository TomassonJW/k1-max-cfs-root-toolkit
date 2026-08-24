# G4-K1-CONTROL-COMPOSITE-MESH-SUBGRID-V1

Date : 2026-08-23

Statut : **passé**. Paquet installé sous
`20260824-113026-g4-k1-control-composite-mesh-subgrid-v1`, 25 contacts capturés
sous `20260824-113434-g4-k1-control-composite-mesh-subgrid-v1-run`, reprise R2
posée sous `20260824-121607-g4-k1-control-composite-mesh-subgrid-recovery-v1-r2`
et validation indépendante verte.

La base `printer.cfg` épinglée est désormais l'état exact après cette campagne
quotidienne verte : `e1f6cd6dc92c9eea1e105f8c669f6d246753243535f09c7f9d92e2dfafebac14`.
Elle diffère du backup précédent uniquement par les six lignes de points du
profil robuste déjà validées. Le préflight refuse donc à la fois l'ancienne
base et toute dérive ultérieure non revue.

Le paquet dépend aussi explicitement de NAVIGATION-V1-R2 : le `app.js` corrigé,
le `navi.json` Mainsail et l'alias `access-k1-control -> k1-control` doivent être
présents exactement.
SUBGRID-V1 ne les remplace pas ; il vérifie seulement qu'ils restent inchangés.

## But

Qualifier la première hypothèse physique de l'ADR-013 sans ouvrir directement
une campagne `11 × 11`. Le seul mouvement autorisé par cette gate est une
sous-grille PRTouch décalée `5 × 5`, soit 25 contacts, aux positions :

- X : `34, 92, 150, 208, 266 mm` ;
- Y : `34, 92, 150, 208, 266 mm`.

La grille est la partition impaire/impaire du futur `11 × 11`. Elle est carrée,
reste onze contacts sous la limite prouvée de 36 et utilise le chemin dynamique
`MESH_MIN`, `MESH_MAX`, `PROBE_COUNT` du `bed_mesh.py` exact capturé.

## Ordre obligatoire

Cette gate ne doit être posée qu'après les quatre révisions quotidiennes :

1. PRTOUCH-BED-MESH-V2 corrigé ;
2. core MATRIX-V1 limité à `6 × 6 / un mesh` ;
3. RETRY-SAFETY-V1 corrigé ;
4. validation idempotente PRTOUCH-PRESETS-V1, sans écriture si les hashes de
   MATRIX + RETRY-SAFETY sont déjà les hashes finaux ;
5. campagne écran quotidienne verte — obtenue sous la capture
   `20260823-171803-g4-k1-control-calibration-ui-campaign-v1` avec
   `VALIDATE_CALIBRATION_UI_CAMPAIGN_V1_OK`.

Le delta UX NAVIGATION-V1-R2 est posé et rendu dans le vrai navigateur. Cette
dépendance d'interface ne modifie pas le protocole physique ci-dessous.

Le composant composite n'est pas visible dans l'interface quotidienne. Son API
exige l'identifiant exact de gate et `plate_clear=true`.

## Pose sans action physique

Write-set exact :

- `moonraker.conf`, remplacé par une copie complète revue qui ajoute seulement
  `[k1_control_composite_subgrid]` ;
- `k1_control_composite_subgrid_core.py` ;
- `k1_control_composite_subgrid.py` ;
- les caches Python correspondants, générés puis contrôlés.

La pose sauvegarde `moonraker.conf`, transfère par `scp -O`, compile les deux
sources avec le Python Moonraker `3.8.2`, redémarre seulement le Moonraker dédié
et exige `failed_components=[]`. Elle ne chauffe, ne home et ne déplace rien.

Commandes revues :

```powershell
.\scripts\deploy-k1-control-composite-subgrid-v1.ps1 -Action Preflight
.\scripts\deploy-k1-control-composite-subgrid-v1.ps1 -Action Deploy -Execute -Gate G4-K1-CONTROL-COMPOSITE-MESH-SUBGRID-V1
.\scripts\deploy-k1-control-composite-subgrid-v1.ps1 -Action Validate
```

Le rollback restaure le `moonraker.conf` exact, retire uniquement les deux
composants et leurs caches, puis redémarre le Moonraker dédié.

## Exécution physique bornée

Le pilote impose :

- plaque `PEI_TEXTURED_A` ;
- plateau `55 °C` ;
- buse `140 °C` ;
- stabilisation `200 s` ;
- nettoyage stock plafonné à `180 °C` ;
- un seul homing ;
- `BED_MESH_CALIBRATE PROFILE=K1_COMPOSITE_ODD_ODD_05X05 MESH_MIN=34,34 MESH_MAX=266,266 PROBE_COUNT=5,5 ALGORITHM=lagrange`.

Il refuse une impression active, une chauffe existante, un Z non accepté, un
chemin Z armé, un profil temporaire ou l'absence de l'un des deux CFS. Un backup
exact de `printer.cfg` et de l'état Z précède toute chauffe.

La matrice doit contenir exactement 25 valeurs finies. Elle est conservée dans
l'état privé avec son identifiant de session et les indices `1,3,5,7,9`.
Aucun profil composite n'est persisté.

Après la capture, le composant :

1. coupe les chauffes ;
2. recharge le profil robuste `6 × 6` ;
3. retire le profil temporaire ;
4. redémarre Klipper seulement à ce moment pour éliminer les changements de
   session en attente ;
5. recharge le profil robuste ;
6. attend de façon bornée le runtime et les deux CFS ;
7. remet explicitement le propriétaire thermique à `none`.

Commande revue :

```powershell
.\scripts\run-k1-control-composite-subgrid-v1.ps1 -Action Run -Execute -Gate G4-K1-CONTROL-COMPOSITE-MESH-SUBGRID-V1
```

Le pilote publie un heartbeat toutes les quinze secondes. Après `1500 s`, il
demande une annulation et rend un timeout, jamais un succès silencieux.

## OK

- 25 contacts, matrice `5 × 5` finie ;
- aucune erreur PRTouch, Klipper ou MCU ;
- aucun contact 26 ni rerun ;
- `printer.cfg` identique ;
- Z accepté et stockage `ok` identiques ;
- profil temporaire absent ;
- profil robuste `6 × 6` actif ;
- chauffes à zéro ;
- axes libérés par le restart final ;
- deux CFS reconnectés ;
- état composite `qualified`, preuves privées capturées.

## KO

Tout écart ci-dessus, un mouvement inattendu, un profil partiel, un changement
de configuration ou l'impossibilité de restaurer l'état sûr ferme la gate. Il
n'autorise ni une deuxième sous-grille ni la campagne `11 × 11`.

## Résultat réel et reprise R2

Thomas a confirmé le plateau libre et la plaque `PEI_TEXTURED_A`. Le pilote a
chauffé à `55/140 °C`, stabilisé `200 s`, nettoyé, référencé puis obtenu les 25
contacts attendus. La matrice `5 × 5` finie et son contexte exact ont été
enregistrés avant le nettoyage final.

Le premier restart de nettoyage a toutefois rencontré la fenêtre transitoire
où Klipper répond aux lectures mais refuse encore une commande avec `Printer is
not ready`. La restauration automatique a rencontré la même fenêtre. Les
chauffes étaient déjà coupées ; la vérification indépendante a confirmé
`standby`, axes non référencés, Z et stockage intacts, puis le profil robuste a
été rechargé sans mouvement via le socket Klipper revu.

Le premier déploiement du delta de reprise a ensuite révélé un second défaut :
le composant écrivait `schema: 1`, mais `AtomicJsonStore` exige `version: 1` au
redémarrage. Le fichier courant et son backup avaient la même empreinte et le
JSON contenait toujours la matrice complète. R2 ajoute :

- une migration atomique limitée au marqueur `schema` → `version` ;
- un retry borné des commandes après restart ;
- une reprise explicite d'un état `failed` contenant une capture complète ;
- un rollback qui restaure l'ancienne révision dans un format chargeable.

R2 a obtenu son préflight, sa pose, puis deux validations. La reprise logique a
qualifié les 25 valeurs existantes sans nouveau contact. Le validateur final a
obtenu `VALIDATE_RUN_COMPOSITE_SUBGRID_V1_OK`. L'état final est sûr et le profil
temporaire est absent.

## Validation hors imprimante

- 19 tests ciblés verts ;
- grammaire Python 3.8 vérifiée ;
- parse PowerShell des deux pilotes vert ;
- hashes du contrat, du déployeur, du pilote et des payloads épinglés ;
- suite complète : 237 tests, 3 ignorés connus ;
- trois tests de chaîne prouvent les transitions exactes BED-MESH-V2 → MATRIX
  → RETRY-SAFETY → PRESETS → COMPOSITE et le caractère sans écriture de
  PRESETS dans l'état final attendu.
