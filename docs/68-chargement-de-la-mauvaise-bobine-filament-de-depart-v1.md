# 68 — La mauvaise bobine au départ : le filament sur lequel le fichier démarre

Date : 2026-09-09
Statut : corrigé et chargé sur la machine ; prouvé hors imprimante et sur la
machine pour tout ce qui peut l'être sans imprimer ; il manque un départ réel

## 1. Ce qui s'est passé le 9 septembre à 13:23

Le fichier `DRAWER4U_4x2x4 LU - Topped Rail - MultiBin Shell_PLA_4h34m.gcode`
déclare deux filaments et n'en imprime qu'un : il contient une seule ligne
`T1`, à la ligne 275, juste après `START_PRINT`. `T1` est le **deuxième**
filament du trancheur.

La table du CFS disait :

```
T1A -> T1B     filament 1, Geeetech noir
T1B -> T2D     filament 2, eSUN PLA+
```

`START_PRINT` lisait `T1A` en dur. Il a donc chargé, purgé et amorcé le
**Geeetech noir de T1B** pour un travail qui voulait l'**eSUN de T2D**. Puis la
ligne `T1` du fichier est arrivée : le CFS a vu que l'emplacement chargé
n'était pas celui du filament demandé et a lancé un changement d'outil en plein
démarrage. Il s'est arrêté là :

```
13:30:17  can_break_flag is 3
13:46:45  Tnn_retry_process: macro_box_extrude_err
13:46:45  error: macro_box_extrude_err, tnn: T1B, last_tnn: None
13:48:00  annulation
```

## 2. Ce qui n'est pas en cause

**La température.** Le même journal dit `get next material temp: 200` et
`flush_temp: 200` à 13:17, 13:26 et 13:46. La correction de la base matière du
document 67 tient : le CFS ne monte plus à 220 pour charger du PLA. C'est la
preuve exécutable qui manquait hier.

Le `220` qui reste dans le journal vient du fichier, pas de la machine :

```
; nozzle_temperature_initial_layer = 190,220
START_PRINT EXTRUDER_TEMP=220 BED_TEMP=55
```

Le travail part sur le filament 2, dont le profil Orca demande 220 °C. Orca a
correctement résolu `[nozzle_temperature_initial_layer]` sur le filament de
départ. Pour imprimer à 200, c'est le profil filament eSUN qu'il faut changer.

**`BOX_MODIFY_TN`.** Mesuré sur la machine le 9 septembre : `BOX_MODIFY_TN
T1A=T1B T1B=T2D` puis `BOX_MODIFY_TN T1A=T1B` laisse `T1B: T2D` intact. La
commande fusionne dans `Tnn_map`, elle ne la remplace pas. Un travail à seize
couleurs ne perd donc pas ses quinze autres emplacements quand le démarrage
réécrit celui sur lequel il part.

## 3. Le correctif

`kctrl_slot_map` répond maintenant à une deuxième question : **sur lequel des
seize filaments le travail démarre**. Il lit la première ligne `Tn` du fichier
que `virtual_sdcard` fait tourner, avec n de 0 à 15, dans la numérotation du
trancheur. `T0` est le premier filament et le nom logique `T1A`, `T15` le
seizième et `T4D`.

Le fichier est relu seulement quand il change — même règle de cache que
`tn_data.json` : un `os.stat` à chaque interrogation, une lecture par
impression. La lecture s'arrête au premier `T`, donc en pratique sur le premier
bloc de 64 ko.

`START_PRINT` enchaîne les deux résolutions :

1. quel filament du fichier — `TOOL_INDEX=` s'il est fourni, sinon la lecture
   du fichier ;
2. quel emplacement physique — `Tnn_map` pour ce filament, et le dernier choix
   retenu **uniquement** si le travail part sur `T1A`. Retenir un choix unique
   et le servir pour le filament neuf serait la même devinette aveugle.

La ligne de départ le dit maintenant en toutes lettres :

```
K1 Control start: bed 55 C, nozzle 220 C, filament 2 du fichier (T1B) ->
emplacement T2D (table CFS), mesh k1_p001_t055_r001_n11x11, Z 0.0500
```

`TOOL_INDEX=` existe pour un G-code qui veut l'imposer lui-même : Orca expose
le numéro sous `[initial_extruder]`. Ce n'est pas nécessaire — la lecture du
fichier marche sur tout ce qui est déjà tranché — mais c'est la source la plus
sûre pour les fichiers à venir.

## 4. Ce qui est prouvé

Sur la machine, après redémarrage de Klipper, sur le fichier réel du matin :

```
// filament 2 (T1B) -> T2D   matiere 000001, couleur 0b2a1e1   <== charge au depart
// depart sur le filament 2 (T1B), premier T du fichier
```

C'est exactement la bobine que le travail voulait, et exactement celle qui
n'avait pas été chargée.

Le plafond de chargement, testé en direct sur la machine :

```
fenetre ouverte, M104 S220 -> cible 100.0
fenetre fermee, M104 S220 -> cible 220.0
```

Il abaisse, il ne refuse pas. Une impression ne peut plus mourir au chargement
à cause du plafond.

Hors imprimante : 72 tests sur ces trois fichiers, et la suite complète à
1069 verts.

## 5. Ce qui n'est pas prouvé

Aucun départ réel n'a encore tourné avec ce correctif. Deux choses ne se voient
que là :

- que le `T1` du fichier soit bien un non-événement une fois la bonne bobine
  déjà chargée. Le CFS compare des emplacements physiques — le journal du matin
  le montre : il a changé parce que `T2D` ne valait pas `T1B`. Avec `T2D`
  chargé, il devrait ne rien faire. Devrait ;
- que le chargement lui-même passe sans `macro_box_extrude_err`.

Ce qu'il faudra lire dans le journal du prochain départ :

```
K1 Control start: ... filament 2 du fichier (T1B) -> emplacement T2D
get next material temp: 200
flush_temp: 200
```

et aucun changement d'outil entre l'amorce et la première couche.

## 6. Corroboration extérieure

Le placeholder `initial_extruder` d'OrcaSlicer est documenté et donne le
filament de départ dans le G-code machine. Côté CFS, le forum Creality décrit
bien des chargements qui partent sur la mauvaise bobine et des sous-extrusions
au premier changement de couleur, sans que personne ne publie de correctif :
la lecture du premier `Tn` du fichier est notre solution, pas une recette
trouvée ailleurs.

- [OrcaSlicer — placeholders intégrés](https://github.com/orcaslicer/orcaslicer/wiki/built_in_placeholders_variables)
- [OrcaSlicer — G-code machine](https://www.orcaslicer.com/wiki/printer_settings/machine%20gcode/printer_machine_gcode)
- [Creality Forum — chargement depuis le CFS, comportement étrange](https://forum.creality.com/t/loading-filament-from-cfs-odd-behaviour/39935)
- [Creality Forum — CFS, sous-extrusion au changement de couleur](https://forum.creality.com/t/cfs-what-tha-heck-is-wrong/40785)

## 7. Fichiers

- `packages/k1-control-v1/owned-start-print-v2/kctrl_slot_map.py`
- `packages/k1-control-v1/owned-start-print-v2/k1-control-owned-start-print-v2.cfg`
- `packages/k1-control-v1/mesh-acquisition-v2/k1-control-probe-temp-guard-v1.cfg`
- `tests/test_kctrl_slot_map_v1.py`
- `tests/test_cfs_slot_selection_and_refill_v1.py`
