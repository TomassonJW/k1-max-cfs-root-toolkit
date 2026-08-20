# 09 — Paquet G4 de sécurité Z au démarrage

Date : 2026-08-20

Identifiant : `G4-ZSAFE-START-V1`

Statut : **préparé et simulé hors imprimante ; G4 non passée ; aucun déploiement**

## Résultat visé

Le paquet rend impossible la sélection CFS, la purge et une trajectoire basse de
production tant que les quatre conditions suivantes ne sont pas vraies :

1. Thomas a nettoyé la buse et confirmé cette action pour un seul départ ;
2. la référence Z finale a réussi ;
3. le mesh stock `default` est explicitement chargé ;
4. la correction absolue revue `+0,27 mm` est réellement active.

Les homings et mesures PR Touch restent des descentes contrôlées nécessaires à
la création de la référence. Ce premier paquet interdit les autres descentes et
toute extrusion avant l'ouverture de la garde.

## Ordre actuel confirmé

| Ordre | Propriétaire actuel | Action | Effet Z ou risque |
|---:|---|---|---|
| 1 | profil Orca | `G28` | première référence avant le macro public |
| 2 | profil Orca | `T0` | le CFS peut agir avant la séquence Z finale |
| 3 | `START_PRINT` stock | `BOX_START_PRINT` | état CFS |
| 4 | `CX_ROUGH_G28` | chauffe de référence puis `G28` | nouvelle référence XYZ/PR Touch |
| 5 | `CX_NOZZLE_CLEAR` | `NOZZLE_CLEAR` | nettoyage avec mouvements proches du plateau |
| 6 | `ACCURATE_G28` | `ACCURATE_HOME_Z` | autre référence Z, frontière interne partiellement opaque |
| 7 | `CX_PRINT_LEVELING_CALIBRATION` | `CHECK_BED_MESH AUTO_G29=1` | quatre contrôles aléatoires ; génération et `CXSAVE_CONFIG` possibles |
| 8 | `BOX_START_PRINT_EXTRUDE_MATERIAL` | chargement/flush CFS | extrusion avant la correction Orca |
| 9 | `CX_PRINT_DRAW_ONE_LINE` | descente `Z0.1`, puis ligne stock | purge basse avant la correction Orca |
| 10 | post-traitement Orca | `SET_GCODE_OFFSET Z=0.27` | correction absolue enfin active |
| 11 | G-code Orca | modèle | impression |
| 12 | `END_PRINT` stock | fin, parking, chauffe coupée, `M84` | ne contient pas l'effacement Z mesuré |
| 13 | service/interface Creality | inverse du `homing_origin`, puis `Z_OFFSET_APPLY_PROBE` | prépare `0.000` après la fin du G-code |

Le dernier producteur est confirmé dans les traces P3 et PETG : la requête
arrive par `webhooks gcode/script` après l'état `complete`. Elle n'est pas émise
par le fichier G-code ni par le corps lisible de `END_PRINT`.

## Qui applique et qui efface le Z

- PR Touch établit la référence Z pendant `G28` et applique son
  `self_z_offset` ;
- le post-traitement Orca fixe ensuite le `homing_origin.z` à `+0,27 mm` ;
- chaque clic Z de l'interface envoie `SET_GCODE_OFFSET Z_ADJUST=...`, puis
  `Z_OFFSET_APPLY_PROBE` ;
- cette commande calcule `nouvelle_valeur_capteur = z_offset_capteur -
  homing_origin.z` et prépare sa persistance ;
- après la fin, l'interface envoie l'inverse exact du `homing_origin.z`, puis
  rappelle `Z_OFFSET_APPLY_PROBE`, ce qui prépare zéro.

Le paquet ne tente pas de modifier cette interface dans un lot Z. Il capture la
valeur finale dans son propre fichier avant d'appeler la fin stock. La valeur
capturée est un **candidat**, jamais une calibration acceptée automatiquement.

## Ordre cible

1. nettoyage manuel de la buse ;
2. `ZSAFE_CONFIRM_NOZZLE_CLEAN`, valable une fois ;
3. `START_PRINT` sans `G28` ni `T0` préalable dans Orca ;
4. remise à zéro de l'état de garde ;
5. référence grossière stock par `CX_ROUGH_G28` ;
6. référence finale stock par `ACCURATE_G28` ;
7. chargement explicite de `BED_MESH_PROFILE LOAD=default` ;
8. application et lecture de contrôle de `SET_GCODE_OFFSET Z=0.27 MOVE=0` ;
9. ouverture de la garde Z ;
10. initialisation CFS, sélection de l'outil initial, chargement et flush CFS ;
11. réapplication absolue de `+0,27 mm`, puis nouvelle lecture de contrôle ;
12. ligne de purge stock ;
13. retour du macro, puis réapplication idempotente par le post-traitement Orca ;
14. impression ;
15. capture du candidat Z final par `ZSAFE_END_PRINT` ;
16. `END_PRINT` stock, puis comportement externe Creality inchangé.

## Intervention unique et fichiers

La seule classe de comportement modifiée est la propriété du démarrage Z et de
sa garde avant purge.

| Source versionnée | Destination future | Rôle |
|---|---|---|
| `overrides/g4-zsafe-start/zsafe_g4.cfg` | `/usr/data/printer_data/config/zsafe_g4.cfg` | overlay original |
| une ligne d'include revue | `/usr/data/printer_data/config/printer.cfg` | charger l'overlay après `box.cfg` |
| `orca-machine-start.gcode` | champ Orca `machine_start_gcode` | retirer `G28` et `T0` antérieurs |
| `orca-machine-end.gcode` | champ Orca `machine_end_gcode` | capturer le candidat avant la fin stock |

Diff attendu dans `printer.cfg` :

```diff
 [include sensorless.cfg]
 [include gcode_macro.cfg]
 [include printer_params.cfg]
 [include box.cfg]
+[include zsafe_g4.cfg]
```

`gcode_macro.cfg`, `printer_params.cfg`, `box.cfg` et les modules Python stock ne
sont ni remplacés ni modifiés.

## Empreintes de référence

Les copies lues le 2026-08-20 donnent :

| Fichier | SHA-256 observé |
|---|---|
| `/usr/data/printer_data/config/printer.cfg` | `272640237e20659cf01f3268ed4cb0282b098c3d613e94bf84a3b80caac3c3b0` |
| `/usr/data/printer_data/config/gcode_macro.cfg` | `864fedde88fbb345c220ae5658f7b04779b3981bd78d68eda6fa63c59c79a04f` |
| paquet `zsafe_g4.cfg` | `2a32c4533f1cc04239e52c6c7067575c4ebcb3bd6a1299f56c014b887e93d03a` |
| snippet Orca de départ | `435fd5497fb7552a20eb50bcbf39757c52efebd4788c49203e746222783c854d` |
| snippet Orca de fin | `a6609d2525a6cea7049600862acb0ffaca9583e133c81506610d8219d12e0535` |

Ces valeurs sont des références historiques, pas une permission d'écraser un
fichier différent. Avant un futur déploiement, les fichiers seront recopiés en
lecture seule, hachés et comparés. Toute dérive impose l'arrêt et une nouvelle
revue du diff.

## Préflight du futur déploiement

Conditions cumulatives :

- GO explicite portant exactement `G4-ZSAFE-START-V1` ;
- imprimante au repos, aucun travail en attente ;
- plaque, buse et zone de mouvement inspectées par Thomas ;
- alias SSH `k1max-root` sans demande de mot de passe ;
- `printer.cfg`, export Orca actif et post-traitement actuel sauvegardés dans un
  dossier privé ignoré ;
- SHA-256 locaux et distants identiques pour chaque sauvegarde ;
- diff réel limité à l'overlay, à une ligne d'include et aux deux champs Orca ;
- aucun fichier brut ou secret ajouté à Git.

## Sauvegarde et installation futures

Cette séquence est préparée, mais ne doit pas être exécutée avant le GO G4 :

1. créer un identifiant privé `YYYYMMDD-HHMM-g4-zsafe-start-v1` ;
2. copier depuis l'imprimante `printer.cfg`, `gcode_macro.cfg`, `box.cfg` et le
   futur éventuel `zsafe_g4_variables.cfg` vers ce dossier local ;
3. exporter le profil Orca actif et copier le script de post-traitement actuel ;
4. calculer les SHA-256 locaux et distants et les enregistrer dans le dossier
   privé ;
5. préparer localement `printer.cfg.candidate` avec la seule ligne d'include ;
6. vérifier le diff et l'unicité de `[include zsafe_g4.cfg]` ;
7. déposer l'overlay et le candidat sous des noms temporaires dans
   `/usr/data/printer_data/config/` ;
8. vérifier leurs SHA-256 à distance ;
9. créer les sauvegardes distantes portant l'identifiant de session ;
10. installer d'abord l'overlay, puis le `printer.cfg` candidat ;
11. demander un seul redémarrage Klipper contrôlé ;
12. vérifier l'état `ready`, la présence des macros `ZSAFE_*`, l'absence d'erreur
    de configuration et le hash des fichiers installés ;
13. importer les deux champs Orca seulement après ce contrôle ;
14. ne lancer aucune impression avant le test sans extrusion ci-dessous.

Chaque copie, renommage, écriture et redémarrage de cette liste est une mutation
future couverte uniquement par le GO nommé.

## Test futur à grande hauteur, sans extrusion

Thomas nettoie la buse, garde la main sur l'arrêt physique et confirme une zone
libre. La séquence future est :

```gcode
ZSAFE_CONFIRM_NOZZLE_CLEAN
START_PRINT EXTRUDER_TEMP=180 BED_TEMP=0 INITIAL_TOOL=0 Z_CORRECTION=0.27 VALIDATE_ONLY=1
```

Ce chemin exécute les homings stock nécessaires, charge le mesh, applique la
correction et monte à `Z30`. Il n'envoie aucun `Tn`, aucune commande d'extrusion
et aucun `BOX_START_PRINT_EXTRUDE_MATERIAL`.

### OK

- aucune extrusion ;
- aucun déplacement de production à `Z<30` hors mesures PR Touch contrôlées ;
- arrêt à `Z30` ;
- axes `xyz` référencés ;
- profil de mesh actif `default` ;
- `homing_origin.z = 0.27` dans la tolérance du paquet ;
- message `low moves armed` puis message de validation haute ;
- aucune génération de mesh, aucun `CXSAVE_CONFIG`, aucune persistance PR Touch ;
- aucune erreur Klipper ou CFS.

### KO et arrêt

- buse proche du plateau hors mesure attendue ;
- extrusion, outil CFS sélectionné ou purge ;
- mesh absent ou différent ;
- correction différente de `0.27` ;
- macro inconnue, erreur de rendu Jinja, redémarrage inattendu ;
- bruit, contact, mouvement imprévu ou besoin de correction manuelle.

Un KO interdit la petite première couche. Il déclenche le rollback ou une
analyse locale selon que l'état installé est sûr ou non.

## Validation physique suivante, encore humaine

Après le test haut OK seulement, Thomas pourra autoriser séparément dans la même
gate nommée une petite première couche surveillée :

- nettoyage manuel puis confirmation ;
- même plaque et même mesh `default` ;
- `+0,27 mm` uniquement ;
- arrêt physique immédiat au moindre contact ou comportement inattendu ;
- contrôle des logs : garde ouverte avant `T0`, flush et ligne stock ;
- à la fin, présence de `zsafe_correction_candidate` avant la remise à zéro
  externe.

Le PLA/PETG, une autre valeur Z et la persistance acceptée ne sont pas validés
par ce premier essai.

## Rollback complet

Le rollback futur est borné :

1. ne lancer aucun nouveau travail ;
2. remettre les champs Orca sauvegardés, dont l'ancien départ avec `G28`, `T0`
   et `START_PRINT`, ainsi que l'ancien `END_PRINT` ;
3. restaurer le `printer.cfg` sauvegardé et vérifier son SHA-256 ;
4. redémarrer Klipper une seule fois ;
5. vérifier l'état `ready` et que `START_PRINT` correspond de nouveau au stock ;
6. vérifier l'absence de l'include `zsafe_g4.cfg` dans la configuration active ;
7. seulement après cette preuve, conserver les fichiers ZSAFE hors chemin actif
   ou les retirer dans le périmètre autorisé ;
8. garder les sauvegardes et traces privées avec leurs hashes.

Le fichier de variables ne modifie pas le comportement sans l'include. Il est
conservé pour l'analyse tant que Thomas n'autorise pas sa suppression.

## Manuel et automatique

| Étape | Responsable |
|---|---|
| nettoyage de buse et confirmation | Thomas |
| vérification référence/mesh/correction et garde | macros ZSAFE |
| sélection initiale, flush et ligne de purge après garde | stock CFS appelé par ZSAFE |
| surveillance du premier mouvement physique | Thomas |
| capture du candidat Z final | `ZSAFE_END_PRINT` |
| décision d'accepter une nouvelle correction | future revue humaine + nouveau diff |
| sauvegarde, hashes, diff, installation et rollback | Codex après GO G4 nommé |

## Hors périmètre

- changement de température CFS ;
- nettoyage automatique de fin ou de début ;
- pression d'avance ;
- ironing, débit et profils matière ;
- Mainsail, Fluidd, Moonraker ou UI Creality ;
- BTT Eddy ;
- génération ou adaptation de mesh ;
- retrait du post-traitement Orca `+0,27 mm`.

## Gate humaine suivante

La prochaine décision est binaire : autoriser ou refuser le déploiement et le
test haut du paquet exact `G4-ZSAFE-START-V1`. Aucun autre changement imprimante
n'est inclus. Sans cette phrase de GO explicite, le paquet reste seulement un
artefact local testé.
