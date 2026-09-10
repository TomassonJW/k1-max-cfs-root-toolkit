# 75 — L'appariement automatique des bobines depuis Mainsail

Date : 2026-09-10, 22:30 à 23:30. Écrit pendant que Thomas imprime ; aucune
action machine, lectures seules. Décision : ADR-062. Point 2 du flux
quotidien (`GOALS.md`).

## Le problème

Le choix des bobines n'existe que dans le popup de l'écran Creality et dans
Creality Print. Un démarrage depuis Mainsail ou Fluidd part sur la table
`tnn_map` telle qu'elle est : ce que le travail précédent, une relève
automatique ou le dernier `KCTRL_SLOT` y a laissé. Un fichier bleu part en
noir sans un mot. C'est le cas du 9 septembre (Geeetech noir chargé et purgé
pour un travail qui voulait l'eSUN de T2D).

## Ce qu'on sait, et d'où

- **Le fichier dit sa couleur et sa matière** : bloc `; CONFIG_BLOCK_START`
  en queue de fichier, `filament_type = PLA;PLA`,
  `filament_colour = #000000;#8080FF`, dans l'ordre du trancheur (doc 74).
  `kctrl_slot_map` les publie déjà (`job_types`, `job_colours`).
- **Le CFS dit ce qu'il porte** : l'objet `box` publie par unité
  `material_type` (identifiant de fiche, `000001`) et `color_value`
  (`0ff1e1e`, sept caractères, un zéro devant), et les groupes de relève
  `same_material` sous la forme `[id, couleur, [emplacements], type]`. Le 10
  septembre au soir : `[000001, 0000000, [T1B], PLA]`, `[000001, 0ffffff,
  [T1D], PLA]`, `[000001, 0ff1e1e, [T2A], PLA]`, `[000001, 000a3ff, [T2B],
  PLA]`, `[000003, 0ffffff, [T2C], PETG]`, `[000001, 0b2a1e1, [T2D], PLA]`.
- **La fiche donne le nom de la matière** : `material_database.json`,
  `base.meterialType` (orthographe du firmware), `PLA`, `PLA-CF`, `PETG`,
  49 fiches. C'est ce qui permet de nommer un emplacement qui n'est dans
  aucun groupe.
- **Une macro est rendue d'un bloc avant sa première commande** : une
  commande émise dans `START_PRINT` ne peut pas changer une variable que le
  même gabarit lit. D'où le partage en deux : le statut publie l'appariement,
  la macro le lit au rendu, et la commande l'écrit.

## Ce qui est écrit

| Fichier | Rôle |
|---|---|
| `packages/k1-control-v1/owned-start-print-v2/kctrl_slot_map.py` | `colour_key`, `read_material_records` (températures et types), `slot_identities` (ce qui est chargé où, type par groupe puis par fiche), `match_job` (pur), statut `match`, `match_notes`, `match_ok`, commande `KCTRL_MATCH` |
| `packages/k1-control-v1/owned-start-print-v2/k1-control-owned-start-print-v2.cfg` | `START_PRINT` : la bobine appariée passe avant la table, refus au rendu avec la note du filament, `KCTRL_MATCH STARTING=1` après l'alignement et avant toute chauffe, `MATCH=0` pour l'ancien comportement |
| `tests/test_kctrl_match_v1.py` | 47 tests : formes de couleur, fiches, identités, appariement pur, statut sur la queue réelle du cube, commande (écritures, refus, `CHECK`, `SKIP`, `FILE`, garde impression), macro (ordre des commandes, rendu des trois cas) |

## Règle d'appariement

Type **et** couleur, exactement, les mêmes critères que les groupes de relève
du firmware : deux bobines que l'appariement tient pour interchangeables sont
celles que le CFS échangerait en fin de bobine. Un filament déjà sur une
bobine qui convient la garde (un choix d'écran ou de `KCTRL_SLOT` juste n'est
pas défait). Un filament sans couleur déclarée prend la seule bobine de son
type, et refuse de choisir entre plusieurs. Rien d'approché : la bobine la
plus proche est **nommée** dans le refus, avec la commande pour l'imposer.

## Pour la console

```
KCTRL_MATCH CHECK=1                       ce qui serait écrit, sans écrire
KCTRL_MATCH                               écrit les filaments utilisés dans la table (machine à l'arrêt)
KCTRL_MATCH FILE=/usr/data/printer_data/gcodes/x.gcode
KCTRL_MATCH SKIP=T1B                      laisse le filament 2 tel qu'il est
START_PRINT ... MATCH=0                   part sur la table telle quelle
START_PRINT ... TOOL=T2C                  impose, comme avant
```

Au démarrage, attendu au journal :

```
K1 Control: appariement du fichier sur les bobines, 2 filaments declares, 2 filaments utilises
  filament 1 (T1A) PLA 000000 -> T1B, deja en table
  filament 2 (T1B) PLA FF1E1E -> T2A (etait T1B, PLA 000000)
  1 entree(s) ecrite(s) dans la table CFS: T1B=T2A
K1 Control start: bed 60 C, nozzle 220 C, filament 1 du fichier (T1A) -> emplacement T1B (appariement sur le fichier, type et couleur), mesh ..., Z ...
```

Et le refus, avant toute chauffe :

```
K1 Control: filament 2 (T1B) PLA 8080FF: aucune bobine PLA de cette couleur; PLA chargees: T1B 000000, T1D FFFFFF, ...; la plus proche est T2D (B2A1E1), KCTRL_SLOT SLOT=T2D TOOL=T1B pour l'imposer; KCTRL_SLOT SLOT=... TOOL=T1B pour imposer une bobine, START_PRINT ... MATCH=0 pour partir sur la table CFS telle quelle
```

Sur le cube du 10 septembre (`#000000;#8080FF`, un seul `T` utilisé, le
premier) : le noir s'apparie sur T1B, le bleu n'a pas de bobine mais n'est
pas utilisé, le démarrage passe. Un fichier qui utiliserait ce bleu refuse.

## Garde

`KCTRL_MATCH` sans `CHECK=1` refuse pendant `printing` ou `paused` : réécrire
la table sous une impression redirigerait son prochain changement d'outil.
Seul `START_PRINT`, qui passe `STARTING=1`, écrit pendant que le fichier
compte comme en cours.

## Déploiement, sur accord, machine à l'arrêt

Mêmes fichiers et même procédure que le document 74 (`kctrl_slot_map.py`
dans `extras/`, le cfg dans la config, redémarrage du **service** Klipper).
Contrôle : `KCTRL_MATCH CHECK=1 FILE=<un fichier à deux couleurs>` répond
avec la table qu'il écrirait.

## Ce qui reste ouvert

- **Première observation réelle** : un démarrage Mainsail sur un fichier dont
  la couleur ne correspond pas à la table. Attendu : les lignes ci-dessus,
  puis `cmd_T vtnn=` sur la bobine appariée.
- **Couleur approchée** : volontairement refusée. Si Thomas préfère qu'une
  couleur proche passe avec avertissement, c'est un seuil à ajouter dans
  `match_job`, pas une refonte.
- **Fichiers sans bloc de configuration** (autre trancheur) : l'ancien
  comportement, table telle quelle, avec la note dans le statut.
