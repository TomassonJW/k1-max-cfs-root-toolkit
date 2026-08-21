# Installation réelle `G4-K1-CONTROL-Z-MESH-RUNTIME-V1`

Date : 2026-08-22

Capture privée : `20260822-011022-g4-k1-control-z-mesh-runtime-v1`

Statut : **runtime installé, stabilisé et validé indépendamment**

## Autorité et périmètre

Thomas a renouvelé exactement :

`GO G4-K1-CONTROL-Z-MESH-RUNTIME-V1`

La pose utilisait le candidat revu au commit
`7be8dc6eb5eff7a0145d0c59bd1e17e817d523cd`. Elle autorisait seulement les deux
fichiers runtime, l'inclusion dans `printer.cfg`, le restart hôte Klipper et la
garde de validation sans mouvement. Elle n'autorisait aucune calibration,
chauffe, référence des axes, commande CFS, modification Orca ou impression.

## Préflight

Le préflight frais a obtenu `PREFLIGHT_Z_MESH_RUNTIME_V1_OK` et confirmé :

- machine `standby`, axes non référencés ;
- cibles buse et plateau à zéro ;
- profil mesh persistant `default` actif ;
- deux CFS connectés en version `1.1.3` ;
- fondation V3 + PATHS-V1 intacte ;
- empreinte initiale exacte de `printer.cfg` ;
- runtime et inclusion absents.

## Pose et garde fermée

Le backup a été copié et vérifié avant la première mutation. Le déployeur a
ensuite posé exactement :

- `/usr/data/printer_data/config/k1-control-z-mesh.cfg` ;
- `/usr/share/klipper/klippy/extras/k1_control_store.py` ;
- une inclusion `[include k1-control-z-mesh.cfg]` après `[include box.cfg]`.

Après le restart hôte Klipper, l'initialisation a atteint `ready=1` avec un
stockage neuf `integrity=empty`. La garde
`KCTRL_PRODUCTION_ASSERT_ARMED` a refusé comme prévu avec
`K1 Control: low production moves are blocked`. Le déployeur a comparé avant et
après les positions, l'origine et les cibles de chauffe : aucune n'a changé.
La pose s'est terminée par :

`DEPLOY_Z_MESH_RUNTIME_V1_OK capture=20260822-011022-g4-k1-control-z-mesh-runtime-v1`

## Normalisation Creality observée

La première validation indépendante a détecté une empreinte `printer.cfg`
différente après la réussite initiale. Les hashes des deux fichiers runtime
étaient toujours exactement ceux approuvés. Les versions avant, après insertion
et après stabilisation ont été copiées en lecture seule dans la capture privée.

Le diff complet montre uniquement l'indentation réécrite par le
`CXSAVE_CONFIG` différé de Creality dans les blocs générés `bed_mesh default` et
`auto_addr`. Aucune valeur, section ou inclusion n'a changé. Une comparaison
qui normalise seulement les espaces de ces lignes a obtenu :

`PRINTER_CFG_NORMALIZED_EQUIVALENCE_OK`

Le validateur accepte désormais uniquement les deux empreintes exactes revues :

- juste après insertion :
  `fa8c25b0bc79f94bcdf1c1bca2c48c3d892ca42854cf277962580680d5767f05` ;
- après normalisation Creality :
  `a484e8d802d0ba1a1331ea2060ecc339bd2d1a607e3a0f9bbcca976c66709c6a`.

Il continue d'exiger l'unique inclusion et les hashes exacts des deux fichiers
runtime. Aucun fichier distant n'a été réécrit pour contourner cette
normalisation et aucun rollback n'a été lancé.

## Validation finale

Le second processus indépendant a obtenu :

`VALIDATE_Z_MESH_RUNTIME_V1_OK`

État final observé :

- `printer.cfg` stabilisé :
  `a484e8d802d0ba1a1331ea2060ecc339bd2d1a607e3a0f9bbcca976c66709c6a` ;
- configuration runtime :
  `dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113` ;
- module runtime :
  `696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede` ;
- `standby`, axes non référencés, positions et origine à zéro ;
- cibles buse et plateau à zéro ;
- mesh actif `default` ;
- deux CFS connectés en `1.1.3` ;
- `ready=1`, `integrity=empty`, `accepted_z_valid=0` ;
- `block_reason=no_accepted_z`, `low_moves_armed=0` ;
- fondation et interfaces Creality intactes.

Aucun mouvement, homing, chauffe, extrusion, ordre CFS, calibration,
impression, firmware restart, reboot ou rollback n'a eu lieu. Seul le restart
hôte Klipper prévu par la pose a été exécuté.

La suite finale exécute 100 tests : 99 passent et le seul contrôle Jinja ignoré
faute de dépendance locale reste couvert par la validation sur le Python/Jinja
exact de la K1.

## Limite volontaire et suite

Le runtime est réellement installé, mais il reste volontairement fermé à la
production tant qu'aucun Z n'a été calibré et accepté. Le profil Orca actif,
`START_PRINT`, le post-traitement historique `+0,27 mm` et les commandes CFS
restent inchangés.

Une future calibration réelle doit recevoir sa propre autorisation explicite,
car elle implique chauffe, homing, mesure mesh et écriture d'état. Elle ne fait
pas partie de cette pose désormais terminée.
