# Troisième essai réel `G4-K1-CONTROL-Z-MESH-RUNTIME-V1`

Date : 2026-08-22

Capture privée : `20260822-004338-g4-k1-control-z-mesh-runtime-v1`

Statut : **pose KO, rollback automatique complet, baseline exacte restaurée ; correction hors imprimante, nouveau GO requis**

## Autorité et périmètre

Thomas a renouvelé exactement :

`GO G4-K1-CONTROL-Z-MESH-RUNTIME-V1`

Ce GO autorisait uniquement la pose du candidat `KCTRL_*` alors revu au commit
`d9df447b393d2bc10998f032cb582f85c654a240`. Il n'autorisait aucune calibration,
chauffe, référence des axes, commande CFS, modification Orca ou impression.

## Préflight et pose

Le préflight frais a confirmé :

- dépôt local et distant alignés sur le commit revu ;
- imprimante `standby`, axes non référencés, cibles buse et plateau à zéro ;
- profil mesh persistant `default` actif ;
- deux CFS connectés en version `1.1.3` ;
- fondation V3 + PATHS-V1 intacte ;
- empreinte exacte de `printer.cfg` et cibles runtime absentes.

Le déployeur a ensuite vérifié le backup, posé les deux fichiers et l'inclusion,
puis envoyé uniquement le `RESTART` hôte Klipper prévu. Les objets runtime ont
été chargés, mais `ready` est resté à zéro. La garde
`KCTRL_PRODUCTION_ASSERT_ARMED` n'a pas été appelée.

## Cause exacte

À `00:45:08`, le `delayed_gcode KCTRL_BOOT` a bien exécuté
`KCTRL_LOAD_STATE`. La première affectation texte a échoué avec :

`Unable to parse 'empty' as a literal`

Le parseur Creality applique `shlex.split` aux arguments avant que
`SET_GCODE_VARIABLE` appelle `ast.literal_eval`. La forme
`VALUE='empty'` perd donc ses guillemets et devient le nom Python nu `empty`,
invalide. Ce défaut concernait les 24 affectations texte du runtime, pas
seulement l'état initial.

L'extrait brut et sa trace sont conservés uniquement dans la capture privée
ignorée. Aucun identifiant matériel n'est publié dans ce rapport.

## Rollback et état final

Le déployeur a exécuté son rollback automatique : restauration de
`printer.cfg`, retrait du runtime et de son état, restart hôte Klipper, attente
des deux CFS et de la fenêtre silencieuse Creality, puis dernière restauration
du backup exact et nouvelle vérification de son empreinte.

Le préflight final séparé est vert : runtime absent, empreinte initiale exacte,
profil `default`, `standby`, axes non référencés, chauffes à zéro, deux CFS
`1.1.3` et fondation intacte. Aucun mouvement, homing, chauffe, extrusion,
ordre CFS, calibration, impression, firmware restart ou reboot n'a eu lieu.
Les dossiers privés de backup et de staging de la capture restent conservés
comme preuves ; ils ne sont ni chargés ni inclus par Klipper.

## Correction hors imprimante

Toutes les affectations texte utilisent désormais un littéral Python protégé à
travers les deux couches, par exemple `VALUE='"empty"'`. Le déployeur sauvegarde
aussi le dernier snapshot sous `validation-runtime-not-ready.json` avant un
futur rollback si `ready` ne monte pas.

Empreintes du nouveau candidat :

- configuration : `dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113` ;
- module : `696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede` ;
- `printer.cfg` attendu après inclusion :
  `fa8c25b0bc79f94bcdf1c1bca2c48c3d892ca42854cf277962580680d5767f05`.

La suite locale exécute 99 tests : 98 passent et le seul contrôle Jinja ignoré
faute de dépendance locale est remplacé par le contrôle en mémoire sur
l'environnement exact de la K1 :

`K1_EXACT_RUNTIME_OK templates=17 commands=18 string_values=24`

## Gate suivante

Le GO reçu est consommé par cette tentative. La configuration et le déployeur
ont changé après l'approbation ; aucune nouvelle pose n'est autorisée avant une
revue du diff exact et un nouveau :

`GO G4-K1-CONTROL-Z-MESH-RUNTIME-V1`
