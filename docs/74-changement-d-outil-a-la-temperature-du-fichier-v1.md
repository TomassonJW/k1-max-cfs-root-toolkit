# 74 — Le changement d'outil en cours d'impression, à la température du fichier

Date : 2026-09-10, 20:50 à 22:00. Écrit pendant que Thomas imprime ; rien
n'a été touché sur la machine, seules les lectures (journal, fichiers G-code,
`tn_data.json`, `box.cfg`, `gcode.py`) ont servi. Décision : ADR-061.

## Ce qu'on savait, ce qu'on a vérifié ce soir

- **Les T0..T15 sont des commandes Python enregistrées par le module compilé**
  (`box_wrapper`), pas des sections de configuration. Elles peuvent donc être
  reprises comme `M104`/`M109` le sont par le garde de température : Klipper
  rend l'ancien gestionnaire quand on enregistre `None` sur un nom
  (`gcode.py`, `register_command`, lu sur la machine), et refuse un second
  enregistrement (`key57`). Un module chargé **après** `[box]` peut donc
  reprendre les seize noms, et laisser ceux qui n'existent pas.
- **Le fichier dit tout en fin de fichier.** Orca 2.4.2 écrit son profil entre
  `; CONFIG_BLOCK_START` et `; CONFIG_BLOCK_END`, une ligne par clé, les
  valeurs par filament en liste dans l'ordre du trancheur (virgules pour les
  températures, points-virgules pour les types, couleurs et noms). Cube du
  10 septembre : ligne 2079 sur 2750 ; fichier de 13 h : ligne 1 799 345. Rien
  de tout cela dans l'en-tête ; l'ancien balayage du premier mégaoctet ne
  pouvait pas le voir.
- **Avant le `T0` du cube, Orca émet `M104 S190`** (ligne 104, sous
  `;filament start gcode`) : le trancheur pose sa cible juste avant le
  changement, et la commande stock la remplace par celle de la fiche pendant
  le chargement. Après un changement en cours d'impression, la cible reste à
  `max(fiche, 200)` tant que personne ne la remet.
- **Deux démarrages ce soir (19:48 et 20:24), après le déploiement de 12:31 :**
  une seule purge stock (`material_change_flush(None,T1B) = True`), une seule
  ligne d'amorce, `z_down move_z: 20,036` puis `z_restore move_z: 20,036`.
  Le `0,8` de `z_down` posé par la routine de fin (20:11:30, 20:49:00) est
  effacé au fichier suivant (« Move z not clear, move_z:0.8 » à 20:22:28), sans
  mouvement.
- **La table `tnn_map`** est réécrite par `START_PRINT` avant le `T` : à
  20:22:28 `T1A -> T1A`, à 20:24:51 `T1A -> T1B` (le cube part sur T1B, PLA
  noir). Le `T0` du fichier, douze lignes plus bas, retrouve `last_cmd = T1B`
  et ne fait rien.
- **`KCTRL_Z_SAVE`** a été passé par Thomas depuis Mainsail à 20:15 (quatre
  fois, dernière valeur 0,065) : le Z du profil reconstruit est enregistré,
  rien à refaire.

## Ce qui est écrit

| Fichier | Rôle |
|---|---|
| `packages/k1-control-v1/owned-start-print-v2/kctrl_tool_change.py` | reprend T0..T15 ; résolution, alignement, commande stock, contrôle après ; `KCTRL_TOOLS` |
| `packages/k1-control-v1/owned-start-print-v2/kctrl_slot_map.py` | `read_job_filaments` (bloc de configuration lu en queue), `refresh_job`, `job_*` dans le statut, `align()` partagé |
| `packages/k1-control-v1/owned-start-print-v2/k1-control-owned-start-print-v2.cfg` | section `[kctrl_tool_change]` (`sensor`, `pause_on_empty`) après `[kctrl_slot_map]` |
| `tests/test_kctrl_tool_change_v1.py`, `tests/test_kctrl_slot_map_v1.py` | 24 + 7 tests ; fixture `tests/fixtures/k1-control-v1/orca-2.4.2-cube-2026-09-10-tail.gcode` (queue réelle du cube) |

Le comportement point par point est dans ADR-061. Résumé pour la console :

```
KCTRL_TOOLS                       ce que fera chaque filament du fichier en cours
KCTRL_TOOLS FILE=/usr/data/printer_data/gcodes/x.gcode
```

Et au journal, à chaque `T` d'un fichier :

```
K1 Control: T1 -> filament 2 (T1B) sur T1B, PLA #8080FF, fiche 00001 (PLA) alignee 220/220 -> 195 C
YJY K1X cmd_T vtnn=T1B ...
get next material temp: 195
flush_temp: 200
K1 Control: T1 fait, filament a la tete, cible 195 C
```

## Déploiement, sur accord, machine à l'arrêt

Un module Python demande le redémarrage du **service** Klipper, pas un
`FIRMWARE_RESTART` (il recharge la configuration, pas les modules).

```
# sauvegardes puis copie (pas de scp sur la machine)
git show HEAD:packages/k1-control-v1/owned-start-print-v2/kctrl_tool_change.py | ssh k1max-root 'cat > /usr/share/klipper/klippy/extras/kctrl_tool_change.py'
git show HEAD:packages/k1-control-v1/owned-start-print-v2/kctrl_slot_map.py   | ssh k1max-root 'cat > /usr/share/klipper/klippy/extras/kctrl_slot_map.py'
git show HEAD:packages/k1-control-v1/owned-start-print-v2/k1-control-owned-start-print-v2.cfg | ssh k1max-root 'cat > /usr/data/printer_data/config/k1-control-owned-start-print-v2.cfg'
ssh k1max-root '/etc/init.d/S55klipper_service restart'
```

Contrôle après redémarrage : `printer/info` à `ready`, le journal porte
`kctrl_tool_change: wrapped T0,…,T15; not registered by the box: -`, et
`KCTRL_TOOLS` répond. Si le module compilé n'a pas enregistré un des seize
noms, il apparaît dans « laissées au CFS » et rien ne casse.

Retour : supprimer la section `[kctrl_tool_change]` du cfg (ou remettre la
sauvegarde `.kctrl-bak-…`), redémarrer le service.

## Ce qui reste ouvert

- **Première observation réelle** : un fichier à deux filaments. Attendu au
  journal : la ligne « K1 Control: T1 -> … » avant `cmd_T vtnn=`, puis
  `get next material temp` à la température du fichier.
- **Point 7 de l'audit 70** : la purge stock lit-elle aussi le fichier pour
  sa température ? Les deux démarrages de ce soir (fichier 190, fiche 190,
  purge 200) ne tranchent pas. Sans effet sur cette mission : la fiche est
  alignée avant, et la cible est remise après.
- **Cutter** (`key841`, 00:53) : matériel intermittent, non reproduit depuis.
  L'enveloppe ne double pas la pause du firmware et le dit ; le geste utile
  reste le nettoyage de la lame et le contrôle de `cut_pos_x/y` si ça revient.
- **Point 2 du flux** : `job_types` et `job_colours` sont maintenant lisibles
  par les macros ; l'appariement automatique avec `color_value` et
  `material_type` des emplacements est la mission suivante.

## Fichiers

- `docs/adr/ADR-061-chaque-changement-d-outil-chauffe-a-la-temperature-du-fichier.md`
- `packages/k1-control-v1/owned-start-print-v2/kctrl_tool_change.py`
- `packages/k1-control-v1/owned-start-print-v2/kctrl_slot_map.py`
- `packages/k1-control-v1/owned-start-print-v2/k1-control-owned-start-print-v2.cfg`
- `tests/test_kctrl_tool_change_v1.py`, `tests/test_kctrl_slot_map_v1.py`,
  `tests/fixtures/k1-control-v1/orca-2.4.2-cube-2026-09-10-tail.gcode`
