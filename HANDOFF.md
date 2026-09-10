# HANDOFF — index de reprise

## 10 septembre, 23:30 — points 4 et 2 écrits et testés (PR #53 + PR point 2), point 5 documenté ; à déployer entre deux impressions

**Point de reprise en un geste :** quand la machine n'imprime pas
(`print_stats.state` ni `printing` ni `paused`, vérifié avant chaque action)
et sur le « go » de Thomas, déployer les deux PR ensemble (la branche du
point 2 contient le point 4) : sauvegardes, copie de `kctrl_tool_change.py`
et `kctrl_slot_map.py` dans `/usr/share/klipper/klippy/extras/` et de
`k1-control-owned-start-print-v2.cfg` dans `/usr/data/printer_data/config/`
(par `git show <branche>:<chemin> | ssh k1max-root 'cat > cible'`), puis
`/etc/init.d/S55klipper_service restart`. Contrôle : `printer/info` à
`ready`, ligne `kctrl_tool_change: wrapped` au journal, `KCTRL_TOOLS` et
`KCTRL_MATCH CHECK=1` répondent. Procédures : documents 74 et 75. Fusionner
PR #53 puis la PR du point 2 (et PR #54) une fois déployées et observées.

### Fait à 22:05–23:30, pendant que Thomas imprime (aucune action machine)

- Point 2 : `match` publié par `kctrl_slot_map`, `KCTRL_MATCH`, `START_PRINT`
  qui prend la bobine appariée avant la table et refuse au rendu sans
  bobine ; 47 tests ; doc 75, ADR-062.
- Point 5 : chaîne de relève relue et prouvée au journal du 5 septembre ;
  aucune paire ce soir ; procédure pour la provoquer ; doc 76.
- Suite 1274 verts, 2 rouges préexistants.

### À savoir

- `KCTRL_MATCH` sans `CHECK=1` refuse pendant une impression ; seul
  `START_PRINT` passe `STARTING=1`.
- Aucune couleur approchée n'est acceptée : la plus proche est nommée dans
  le refus, `KCTRL_SLOT` l'impose, `MATCH=0` part sur la table.
- Reste : contacts bruts capturés par `KCTRL_MESH_ACQUIRE` /
  `KCTRL_BED_SCREWS` ; PR #54 à fusionner.

## 10 septembre, 22:05 — point 4 écrit et testé (PR #53), à déployer entre deux impressions ; puis points 5 et 2 (remplacé par 23:30)

**Point de reprise en un geste :** quand la machine n'imprime pas
(`print_stats.state` ni `printing` ni `paused`, vérifié avant chaque action)
et sur le « go » de Thomas, déployer PR #53 : sauvegardes, copie de
`kctrl_tool_change.py` et `kctrl_slot_map.py` dans
`/usr/share/klipper/klippy/extras/` et de
`k1-control-owned-start-print-v2.cfg` dans `/usr/data/printer_data/config/`
(par `cat fichier | ssh k1max-root 'cat > cible'`), puis
`/etc/init.d/S55klipper_service restart` (module Python, jamais
`FIRMWARE_RESTART` seul). Contrôle : `printer/info` à `ready`, ligne
`kctrl_tool_change: wrapped T0,…,T15` au journal, `KCTRL_TOOLS` répond.
Procédure complète : document 74. Fusionner PR #53 dans `main` une fois
déployée et observée sur un premier `T` réel.

### Fait à 20:50–22:05, pendant que Thomas imprime (aucune action machine)

- Journal relu : ADR-060 tient sur deux vrais démarrages (une purge, une
  ligne, Z rendu à l'identique) ; Z 0,065 enregistré par Thomas à 20:15.
- `kctrl_tool_change.py` : enveloppe des seize `T`, refus nets avant la
  commande stock, fiche alignée sur la température du fichier (première
  couche ou courante), pause sur tête vide après un changement, cible
  remise à la valeur du fichier ; `KCTRL_TOOLS`.
- `kctrl_slot_map.py` : bloc de configuration Orca lu en queue de fichier,
  `job_*` publiés dans le statut (base du point 2).
- 24 + 7 tests sur la queue réelle du cube ; suite 1227 verts, 2 rouges
  préexistants. ADR-061, document 74, `GOALS.md` point 4.

### À savoir

- La commande stock `return False` sans erreur Klipper sur un mauvais
  emplacement : c'est l'enveloppe qui rend l'échec visible, pas le firmware.
- La purge stock chauffe toujours à `max(fiche, 200)` ; l'enveloppe remet la
  cible du fichier après. Point 7 de l'audit 70 toujours ouvert, sans effet.
- Suite prévue après déploiement : point 5 (relève auto : documenter
  `auto_refill`, la provoquer exprès sur une impression sans valeur), point 2
  (appariement automatique couleur + matière depuis Mainsail avec `job_*`),
  contacts bruts capturés par `KCTRL_MESH_ACQUIRE` / `KCTRL_BED_SCREWS`, nom
  de sauvegarde unique dans `kctrl_mesh.py`.

## 10 septembre, 12:35 — PR #52 déployée et profil reconstruit appliqué ; prochain geste : le carré 280×280, puis le Z (remplacé par 22:05)

**Point de reprise en un geste :** Thomas imprime le carré 280×280 (plateau à
55 ; le démarrage charge `k1_p001_t055_r001_n11x11` lui-même), règle Z en
direct ; après l'impression, `KCTRL_Z_SAVE PROFILE=k1_p001_t055_r001_n11x11
Z=<valeur affichée>` (jamais tant que `print_stats.state` vaut `printing`),
puis point 6 de `GOALS.md`, `STATE.md`, PR #52. Attendu au journal de ce
démarrage : une seule purge (`material_change_flush`), aucun « complément de
purge », aucune ligne stock à F3000 avant « ligne d'amorce » (ADR-060).

### Fait à 12:30–12:33, sur « tu peux appliquer la PR »

- Trois cfg copiés (sauvegardes `.kctrl-bak-20260910-123029`, md5 identiques
  au dépôt), Klipper redémarré 12:30:53, prêt 12:31:27, aucune erreur ;
  macros de mesure sans « standby », `_KCTRL_PURGE_MARK` et
  `_KCTRL_PURGE_REPORT` absents, `_KCTRL_PURGE_BALL` et `_KCTRL_PRIME_LINE`
  présents.
- `KCTRL_MESH_APPLY` étape 1 puis 2 à 12:32:54 : 120 points, pas de 0,079,
  zéro gardé en X150 Y150 ; profil vivant identique au fichier reconstruit,
  écrit dans `printer.cfg`. Retour possible : `KCTRL_MESH_UNDO` (une étape)
  ou `KCTRL_MESH_APPLY` sur un JSON tiré de
  `experiments/2026-09-10-mesh-brut-sans-rampe/profil-actif-avant.json`.
- Réponses données à Thomas avant d'agir : pas de nouvelle mesure du plateau
  (même rampe) ; la pente avant/arrière est réelle et progressive, 0,18 entre
  les vis ; la validation est le carré.

### À savoir

- La bannière `SAVE_CONFIG` revient à chaque démarrage (`[auto_addr]
  mb_addr_table_uniids`, journal 12:31:27) : permanente, jamais la presser.
- Après un redémarrage le profil actif est `default` ; c'est `START_PRINT`
  qui charge le bon profil (`BED_MESH_PROFILE LOAD=`).
- Petit défaut vu : deux applications dans la même seconde ont reçu le même
  nom de sauvegarde `…-123254.json`, la seconde a écrasé la première ;
  compteur ou microsecondes à ajouter dans `kctrl_mesh.py`.
- La machine n'a ni `bash` ni `sftp-server` : `ssh k1max-root 'sh -s'` et
  copie par `cat fichier | ssh k1max-root 'cat > cible'`.

## 10 septembre, 12:15 — cube fini ; une purge, une ligne écrites et testées ; le maillage est incliné par le firmware, reconstruction prête ; rien de déployé (remplacé par 12:35)

**Point de reprise en un geste :** sur le « go » de Thomas, machine à l'arrêt
(`print_stats.state` autre que `printing`, vérifié avant chaque action) :
(1) déployer la branche `fix/demarrage-une-purge-une-ligne` — copie avec
sauvegarde de `k1-control-owned-start-print-v2.cfg`,
`k1-control-mesh-acquisition-v2.cfg` et `k1-control-mesh-reference-v2.cfg`,
puis `/etc/init.d/S55klipper_service restart`, md5 et journal vérifiés ;
(2) appliquer le profil reconstruit — copier les deux `.json` de
`experiments/2026-09-10-mesh-brut-sans-rampe/` dans
`/usr/data/printer_data/config/`, puis `KCTRL_MESH_APPLY FILE=…etape1.json`
et `…etape2.json` (sauvegarde automatique, `KCTRL_MESH_UNDO` pour revenir) ;
(3) Thomas imprime le carré 280×280, règle Z en direct, puis
`KCTRL_Z_SAVE PROFILE=k1_p001_t055_r001_n11x11 Z=<valeur>` après
l'impression. Ne jamais presser `SAVE_CONFIG` : la bannière levée à 11:43:08
par `Z_OFFSET_APPLY_PROBE` ne porte rien d'utile (sonde à 0, inchangée).

### Observé sur le cube de 11:15, fini à 11:43:07

- Deux purges dans le bac : la purge stock du `T{position - 1}` (complète, à
  200, finie à 11:18:56), puis notre complément de 254 mm à 190, chaîne écrite
  le 2 septembre pour un chargeur qui purgeait alors sur une buse à 109 °C.
  Deux lignes : `CX_PRINT_DRAW_ONE_LINE` trace ses trois cordons lents à
  chaque démarrage normal (`can_break_flag` vaut 3 après tout `M109`), puis
  la nôtre.
- Première couche ratée : buse trop loin à l'avant, trop près à l'arrière.
  Cause : le profil lui-même, pas son application (document 73).
- Z vivant à +0,180 en fin de cube, remis à zéro à 11:43:08 par l'interface ;
  rien d'écrit dans le profil.
- `KCTRL_BED_SCREWS` refusé six fois de 11:43:51 à 11:49:19 : l'état vaut
  `complete` après une impression, pas `standby` (`SDCARD_RESET_FILE` le
  remettrait). Filet corrigé sur la branche : refus seulement pendant
  `printing` ou `paused`.

### Décidé et écrit (branche `fix/demarrage-une-purge-une-ligne`, PR #52)

- ADR-060 : le démarrage ne pousse plus de filament lui-même ; une seule
  ligne, la nôtre ; `_KCTRL_PURGE_BALL TEMP=200 LEN=100` reste en manuel.
- Les quatre macros de mesure refusent `printing` et `paused`, rien d'autre
  (`tests/test_mesh_acquisition_state_gate_v1.py`).
- Document 73 et `experiments/2026-09-10-mesh-brut-sans-rampe/` : la rampe
  mesurée sur les cinq mesures du matin, le profil reconstruit, les vis
  (0,177 mm d'écart réel, arrière plus haut, contre 0,077 vu par le rapport).
- 1196 tests verts, deux rouges préexistants inchangés.

### Mission suivante

`KCTRL_MESH_ACQUIRE` et `KCTRL_BED_SCREWS` capturent les contacts bruts
pendant la mesure ; `KCTRL_MESH_MERGE` et `KCTRL_SCREWS_REPORT` ne lisent plus
jamais les profils enregistrés. À ouvrir après validation du carré sur le
profil reconstruit.

## 10 septembre, 11:25 — le cube a chargé à 190 : l'alignement est observé sur un vrai chargement ; Z en cours de réglage (remplacé par 12:15)

**Point de reprise en un geste :** quand le cube est fini et que Thomas donne
le Z affiché dans Mainsail, `KCTRL_Z_SAVE PROFILE=k1_p001_t055_r001_n11x11
Z=<valeur>` (jamais tant que `print_stats.state` vaut `printing`), puis
mettre à jour le point 6 de `GOALS.md`, `STATE.md`, la PR #51.

### Observé sur le cube de 11:15 (fichier à 190 / 55)

- 11:15:03 : `START_PRINT` a écrit `200/200 -> 190` dans la fiche `00001`
  avant toute chauffe (base modifiée à cette seconde).
- 11:17:32 : `get next material temp: 190` au chargement, à nouveau à
  11:18:27 pour la purge ; filament à la tête, purge stock finie à 11:18:56,
  complément de 120 mm à 190 C, ligne d'amorce à 11:20:02, impression partie
  à 11:20:09. Aucun refus, aucune erreur du chargeur.
- Nuance : la purge stock chauffe à `flush_temp: 200`, pas 190. Journaux du
  5 au 10 septembre : fiche 220 → purge 220, fiche 200 → purge 200, fiche 190
  → purge 200. La purge suit donc la fiche avec un plancher à 200, dont
  l'origine n'est pas isolée (le G-code dit `filament_flush_temp = 0`). Sous
  le filet (205) ; sans effet pour du PLA à 190. Un fichier sous 185 C ferait
  refuser la purge par le filet : à traiter le jour où un tel fichier arrive
  (plafond du filet à `max(fichier + 15, 205)`, ou plancher retrouvé).
- Thomas règle le Z en direct sur la première couche : 0,14 → 0,03 à 11:25.

### Bruit connu, sans effet

- `Unknown command:SET_HOTEND_FAN` au départ (docs/70).
- `Error: no response` toutes les 11 s : balayage d'adresses du bus 485
  (`auto_addr_wrapper`, commande 161), présent toute la journée, sans lien
  avec l'impression.

## 10 septembre, 11:10 — alignement déployé et prouvé ; zéro Z à refaire ; le flux visé est écrit (remplacé par 11:25)

**Point de reprise en un geste :** relire les « Précisions de Thomas du
10 septembre » dans `GOALS.md` (le flux quotidien visé, point par point, avec
l'état de chacun), puis carré 280x280, réglage en direct,
`KCTRL_Z_SAVE PROFILE=k1_p001_t055_r001_n11x11 Z=…`, puis le cube. Ce cube
sera la première observation d'un vrai chargement avec l'alignement : le
journal doit dire `get next material temp: <température du fichier>`.

### Déployé à 11:06, vérifié à 11:07

- Les trois fichiers de la branche sont sur la machine (md5 identiques au
  dépôt), sauvegardes `.kctrl-bak-20260910-1106xx` à côté ; Klipper redémarré,
  prêt, machine à l'arrêt, chauffes à zéro.
- `KCTRL_MATERIAL_ALIGN` : « déjà à 200 C, rien écrit », puis `200 → 205`
  écrit et relu, puis retour `200`, puis refus net sur une fiche absente.

### Ce qui a été ajouté depuis 10:25

- `KCTRL_MATERIAL_ALIGN MATERIAL=<fiche ou type d'emplacement> TEMP=<°C>` :
  écrit la température du fichier dans la fiche que le chargeur va lire,
  atomiquement, et relit. `START_PRINT` l'appelle en première commande. Le
  chargeur relit la base à chaque chargement (prouvé le 9 septembre), la base
  n'est réécrite qu'à l'allumage (prouvé par les `uptime`), donc plus aucune
  correction à la main. Section 8 du document 67.
- 1193 tests verts ; les deux rouges préexistants inchangés.

### Ce qui reste ouvert

- Le changement de bobine en cours d'impression passe par le `cmd_T` d'origine,
  fiche d'usine si le matériau diffère de celui du départ ; à envelopper
  (`T0`..`T15`, `rename_existing`) dans une mission à part.
- La base est une réponse du cloud Creality téléchargée à chaque allumage
  avant la mise à l'heure (`reqId` daté 2020, `result.version` qui change
  d'un allumage à l'autre) ; le serveur Creality qui l'écrit n'est pas isolé.
  Sans conséquence avec l'alignement.

## 10 septembre, 10:25 — correctif du chargement écrit, à déployer ; zéro Z à refaire (remplacé par 11:00)

**Point de reprise en un geste :** déployer les trois fichiers de la branche
`fix/cfs-temperature-chargement` sur la machine (cat vers
`/usr/data/printer_data/config/` pour les deux `.cfg`, vers
`/usr/share/klipper/klippy/extras/` pour `kctrl_slot_map.py`), puis
`/etc/init.d/S55klipper_service restart`. Ensuite carré 280x280, réglage en
direct, `KCTRL_Z_SAVE PROFILE=k1_p001_t055_r001_n11x11 Z=…`.

### Ce que la matinée a établi

- Vis du plateau réglées par Thomas en trois passes (`KCTRL_BED_SCREWS`),
  écart final 0,08 mm ; voile résiduel 0,14 mm hors plan, hors de portée des
  vis.
- Mesh 11x11 refait à 09:52 (`KCTRL_MESH_CALIBRATE`, deuxième essai ; le
  premier a été refusé pour un contact aberrant de 0,07 mm sur la jonction
  sud-ouest / nord-ouest). Écrit dans `printer.cfg`, chargé.
- À 10:06, l'impression du cube s'est figée dans le chargement CFS : la base
  matière avait été **réécrite au redémarrage de 08:44** (Generic PLA à 220),
  la fenêtre a abaissé à 205, le chargeur a attendu 220 pour toujours. Arrêt
  d'urgence à 10:14, redémarrage Klipper, base recorrigée à 10:19.
- Le correctif (lecture de la fiche avant de chauffer, refus au lieu
  d'abaissement) est écrit et testé hors machine : 77 tests verts sur les deux
  fichiers concernés, 1174 sur la suite. Section 7 du document 67.

### Ce qui n'est pas prouvé

- Le correctif n'a pas encore tourné sur la machine.
- La base sera réécrite au prochain redémarrage ; le contrôle de `START_PRINT`
  le dira, mais rien ne la recorrige tout seul.

## 10 septembre, 01:20 — la machine est propre, la table des bobines est vide

**Point de reprise en un geste :** avant toute impression,
`KCTRL_SLOT SLOT=T2D TOOL=T1B`. Sans ça `START_PRINT` **refuse de démarrer**.

### Ce que la nuit a prouvé

Le correctif du changement d'outil **fonctionne**. Journal du départ de 00:51 :

```
00:53:23  cmd_T last_cmd=None, get_fialment_sensor_detect()=True
00:53:23  z_down move_z: 0.8          <- sain, contre 44.027 la veille
```

La coupe est arrivée **au début** de la séquence, avant tout chargement et
avant toute purge, et l'accumulateur Z n'a plus dérivé pendant `START_PRINT`.
Aucun `Move out of range` pendant le démarrage. La séquence est allée au bout :
chargement, purge, ligne d'amorce, première couche. **C'est le premier départ
complet depuis que le problème existe.**

### Ce qui a arrêté ce départ, et ce n'était pas la séquence

```
00:53:28  [box] cut to return failed          (x5 en 20 s)
00:53:48  key841 "cut error, cut sensor not detected, cutting not rebound"
00:53:48  error: printing to pause
```

Le capteur de coupe n'a pas vu la lame revenir. Cinq essais, abandon, pause.
Piège de lecture à connaître : la pause est décidée à 00:53:48 mais la purge et
la ligne d'amorce se déroulent **après**, jusqu'à 00:55:22, parce que Klipper
vide d'abord la file déjà tamponnée. Le dernier message du journal
(`SET_HOTEND_FAN`, `key61`) n'est **pas** la cause : il vient d'un webhook de
`/usr/bin/master-server`, pas du gcode, et tombe là par coïncidence.

Le cutter a ensuite refonctionné (`cut to return OK` à 01:03:45 et à 01:15:44)
sans que `box.cfg` change d'un octet — md5 `dd05b5bb69929389d233cc1e487a44de`
avant comme après, positions inchangées (`cut_pos_x: 38`, `cut_pos_y: 303.2`,
`cut_pos_offset: 1.3`). **Défaillance intermittente non expliquée.** Sauvegarde
`box.cfg.kctrl-bak-avant-calib-cutter-20260910`.

### La corruption Z de 01:07 : deux reprises superposées

```
01:05:36  cmd_T box_resume_extrude: last_tnn = T2D, tnn = T2D   <- le CFS reprend seul
01:07:05  record_z_pos: 2.410
01:07:05  record_z_pos: -40.590                                  <- 24 ms plus tard, -43.00 mm
01:07:05  Move out of range: 210.000 291.500 -40.590 [357.808]
```

Le CFS avait déjà fait sa reprise ; la relance depuis l'écran en a superposé une
seconde et le compteur Z a soustrait deux fois. **Ce n'est pas `START_PRINT`.**
Règle qui en sort : **un seul chemin de reprise**. Ne jamais relancer depuis
l'écran après un `box_resume_extrude`. La machine n'a pas été figée cette fois
(`idle_timeout: Ready`), aucun redémarrage Klipper n'a été nécessaire.

Confirmé au passage, et c'est la validation de la thèse de cause racine :
quand `last_cmd` vaut `T2D` et que l'outil demandé vaut `T2D`, le module fait
`box_resume_extrude` et **ne coupe pas**. La coupe n'a jamais eu lieu que sur
`last_cmd = None`.

### État machine au moment de la passation, vérifié

| | |
|---|---|
| `print_stats.state` | `cancelled` |
| chauffes | 0 / 0, en refroidissement |
| `homed_axes` | `''` |
| capteur de tête | **False** — filament retiré, tête vide |
| `box.last_cmd` | `None` |
| `kctrl_slot_map.map` | **`{}`**, `error: tnn_map vide` |
| `tn_data.json` | `tnn_map: None`, `last_cmd: None` |
| variables retenues | `kctrl_slot = T1A`, `slot_last_choice = T1B` |
| config déployée | md5 `3ca58a94014711baab93702d50dab0c7` |

L'annulation a vidé la table des bobines. Le repli `slot_last_choice` **ne
s'applique qu'à `T1A`** (par construction, voir
`test_the_remembered_slot_is_only_the_first_filament`), or le fichier démarre
sur `T1B`, et aucun `slot_choice_t1b` n'existe. Donc `chosen` est vide et
`START_PRINT` lève une erreur explicite au lieu de deviner — comportement
voulu, mais il **faut** réécrire la table avant de relancer.

Tête vide au prochain départ = `last_cmd None` + capteur False = **chargement
normal, aucune coupe**. C'est l'état nominal du CFS, et le cutter sort du
chemin critique pour ce départ-là.

### Ce qui reste ouvert, par priorité

Le rapport d'audit indépendant `docs/70-audit-independant-sequence-demarrage-v1.md`
tient la liste complète et sourcée (§4). Les trois premiers :

- **P1 — rendre l'accumulateur Z avant de sortir du bloc CFS.** `RESTORE_POSITION`
  après `BOX_MATERIAL_FLUSH`, ou remplacer `BOX_EXTRUDE_MATERIAL` +
  `BOX_GO_TO_EXTRUDE_POS` par le stock `BOX_START_PRINT_EXTRUDE_MATERIAL
  START_PRINT=8`. C'est la cause de fond des `Move out of range`.
- **P2 — faire échouer `START_PRINT` sur erreur CFS.** Constaté cette nuit :
  après `key841`, la séquence a continué à purger et à tracer comme si de rien
  n'était.
- **P5 — ligne d'amorce trop fine.** Défaut de conception assumé de
  `_KCTRL_PRIME_LINE` : monter le débit **et** la vitesse ensemble a fait
  *baisser* la section par trait — 0,133 mm² contre 0,150 mm² pour la stock,
  soit 0,37 mm de large contre 0,75. Les 3 passes donnent bien 2,7x la matière
  au total, mais chaque trait est deux fois plus fin que le stock. Correctif :
  descendre `variable_line_speed` de 9000 à 6000 (100 mm/s) à débit constant,
  ou suivre l'audit et plafonner à 15 mm³/s — le profil Orca officiel du
  `CR-PLA @K1 Max_CFS-C` déclare 18 mm³/s. Le zéro Z n'est **pas** en cause :
  `homing_origin Z = 0.14` est bien appliqué (écart mesuré entre
  `gcode_position` et `position`).

Non résolu et non expliqué : l'intermittence du capteur de coupe. Deux passages
du forum Creality cités par l'audit pointent des débris et le réglage de
`cut_pos` (TC2841).

### Tests

`tests/test_kctrl_zone_guard_v1.py` : **2 rouges assumés**, ils affirment que le
mouvement incriminé à Y 291,5 est refusé alors que `zone_y_min` vaut 296.
L'audit tranche (P4) : viser Y ≥ 285, et n'appliquer le plancher qu'en dehors
du palpage et pendant `printing`. Le garde n'est **pas déployé**.
Deux autres rouges préexistants et sans rapport :
`test_cfs_direct_owner_offline_v1::test_unload_requires_head_sensor_to_clear`,
`test_job_lifecycle_offline_v1::test_all_canonical_scenarios_are_implemented_once`.

---

# HANDOFF — index de reprise

Soiree du 8 septembre, apres la campagne : la hotend a lache — fils dessoudes,
chauffage commande a fond sans aucune montee. Thomas l'a remplacee par une piece
identique. Les resonances n'ont **pas** ete refaites, a raison : une hotend
identique ne change ni la masse ni la raideur de la tete. Le PID de la buse a
ete refait (`PID_CALIBRATE TARGET=220`) et ecrit a la main dans `[extruder]` :
`Kp 20,695 / Ki 1,533 / Kd 69,844` contre `25,013 / 2,566 / 60,966`. Sauvegarde
`printer.cfg.bak-avant-pid-20260908-233200`. Redemarrage fait a 23:41, valeurs **actives et verifiees** (PID, plus
`ei 42,6` / `mzv 46,6`). La table des bobines a survecu : `T1A -> T1B`.
Avance de pression laissee a `0,04` et zero Z laisse a `+0,05 mm`, sur
decision de Thomas. La machine est prete a imprimer. Voir document 66.

Appliqué le 8 septembre à 22:43, sur accord de Thomas : `ei 42,6 Hz` sur X et
`mzv 46,6 Hz` sur Y, en direct par `SET_INPUT_SHAPER` et à la main dans le bloc
`#*#` de `printer.cfg` (sauvegarde `printer.cfg.bak-avant-application-20260908-224352`).
Attention : `save_config_pending` est à `true`, Klipper garde en mémoire les
`ei 55.8` préparés par `SHAPER_CALIBRATE` ; un `SAVE_CONFIG` écraserait
l'édition manuelle et redémarrerait la machine. Le zéro Z et l'avance de
pression ont été refaits par Thomas lui-même.

Résultat de la campagne du 8 septembre, 22:10-22:25, après remplacement de la
buse et de l'extrudeur. Les quatre balayages ont tourné, les deux axes ont bien
été mesurés séparément. **Rien n'a été appliqué.** Y est nettement meilleur :
`mzv 46,6 Hz`, zéro vibration, accélération admissible `6 397` contre `4 500`.
X reste le point faible : `ei 42,6 Hz` et `22,3 %` de vibrations, contre
`24,7 %` le 2 septembre — le remplacement ne l'a pas réglé, aucun filtre ne
descend sous `12 %`. Courroies équilibrées, pic `44,7 Hz` des deux côtés.
Attention : `SHAPER_CALIBRATE` a écrit `ei 55.8` sur les deux axes dans le bloc
`#*#` — c'est la valeur de Y recopiée sur X, fausse de `13,2 Hz`, et elle
deviendrait active au prochain redémarrage. Les valeurs vivantes en mémoire
sont encore celles du 2 septembre. Sauvegarde :
`printer.cfg.bak-avant-resonance-20260908-221021`. Décision en attente de
Thomas. Voir document 65.

Toujours ouvert : la buse a changé, donc le zéro Z et l'avance de pression
(`0,044`) sont à reprendre avant les prochaines impressions.

Priorité du 8 septembre : la tête d'impression a été modifiée, les mesures de
résonance sont donc à refaire. La campagne est **préparée et validée, pas
lancée** — Thomas bricole encore sur la machine et on se recale avant de
mesurer. Un seul lancement,
`scripts/run-k1-control-resonance-campaign-v1.ps1`, une vingtaine de minutes :
les deux axes réellement mesurés chacun, les deux courroies séparément, les
cinq filtres évalués hors ligne, comparaison avec le 2 septembre, rien
d'appliqué. L'analyseur a été passé sur les CSV du 2 septembre et les reproduit
au dixième près (`ei 40,2 Hz / 24,7 %` sur X, `mzv 39,0 Hz / 0,0 %` sur Y).

À savoir : le calibrage de la machine a tourné ce soir à 21:47 depuis l'écran.
Il n'a mesuré **qu'un seul axe** — les deux CSV ont la même empreinte
`bd083f5c…` — et a écrit `ei 56.2` sur les deux axes dans le bloc `#*#`,
effaçant la série du 2 septembre. Ne pas le relancer depuis l'écran. Notre
campagne échoue explicitement si les deux axes rendent le même fichier.
Question ouverte et bloquante pour la suite : **ce qui a été changé sur la
tête**. Si la partie chaude ou la géométrie ont bougé, le zéro Z et l'avance de
pression (`0,044`) sont à reprendre aussi. Voir document 64.

## Priorité du 5 septembre au soir — le départ ne refuse plus une buse chaude

Trois départs se sont arrêtés au même octet dans la journée : 16:21, 16:43 et
17:47. Le correctif du matin agissait sur le profil de tranchage et sur une
copie du fichier ; il ne pouvait rien pour les fichiers déjà tranchés, et c'est
l'original qui a été relancé.

La cause était dans le garde de palpage, pas dans le fichier : une **cible**
buse au-dessus du plafond interrompait la séquence, alors qu'une **température**
au-dessus du plafond était simplement coupée et attendue. Une cible est
maintenant coupée et annoncée elle aussi. La protection ne change pas : pendant
la fenêtre, `M104` et `M109` au-dessus du plafond restent refusés et la buse est
toujours ramenée sous le plafond avant tout contact.

Posé sur la machine, `FIRMWARE_RESTART` fait, prouvé à froid : cible `220 C`
debout, buse `75,5 C`, la fenêtre s'ouvre sans erreur et la cible retombe à
zéro. Aucun mouvement, aucun contact.

**Pour relancer** : essuyer la buse à la main — le capteur de tête voit encore
le filament laissé par les purges avortées, et une bavure figée fausserait le
contact (ADR-045) — puis lancer depuis l'écran, l'application ou la page web
Creality, pour garder le popup de correspondance des bobines. N'importe lequel
des deux fichiers convient désormais, l'original comme la copie
`_KCTRL-fixed.gcode`. Reprendre du début, pas de reprise en cours de fichier.

État au moment d'écrire : table CFS lisible, premier filament sur `T1B` ;
profil `k1_p001_t055_r001_n11x11` présent, Z accepté `+0,050 mm` ; chauffes à
zéro, rien en cours. Détails : `docs/63-depart-tolere-buse-deja-chaude-v1.md`
et ADR-059. Le correctif du matin est décrit dans le document 62.

La suite du document décrit la clôture historique du 2 septembre.

## Reprise immédiate

**Lancer les impressions depuis l'écran tactile, l'application Creality ou la
page web Creality.** C'est là que vit le popup d'origine : les filaments du
G-code avec leurs couleurs d'un côté, les bobines du CFS de l'autre, on les met
en face, et il n'y a rien d'autre à faire. Fluidd et Mainsail n'ont pas ce
popup — c'est pour cela que tout partait sur `T1A`.

`START_PRINT` lit maintenant la réponse du popup. Le rechargement automatique en
cours d'impression est armé.

Sans écran dans la boucle, trois commandes font le même travail :

```
KCTRL_MAP                        voir la correspondance filament -> emplacement
KCTRL_SLOTS                      voir les bobines et celle qui partira
KCTRL_SLOT SLOT=T2B TOOL=T1B     forcer une correspondance
```

Détail, preuves et journaux : `docs/55-popup-de-correspondance-des-filaments-v1.md`
et ADR-056. Session précédente : doc 54 et ADR-055.

**Le Z accepté se tape maintenant dans l'éditeur de maillage** (port `7130`),
dans la barre du haut, à côté du profil. « Reprendre » recopie le décalage en
vigueur sur la machine — celui que l'on vient de trouver à l'œil pendant une
première couche — et « Enregistrer Z » le garde pour ce profil. Il s'applique au
démarrage d'impression suivant. Doc 56 et ADR-057.

**L'écran brosse la buse tout seul avant de démarrer, c'est normal.** Il envoie
`CX_NOZZLE_CLEAR` directement par l'API, et cette macro Creality chauffe le lit
à `50 C` — sa valeur par défaut, pas celle du fichier. Notre `START_PRINT` ne
brosse pas et ne recalibre rien. Voir un brossage et un lit à 50 au lancement
n'est donc pas le signe que la mauvaise séquence part.

**Les ondulations ne viennent pas du maillage.** Longueur d'onde mesurée à la
règle : `3 à 10 mm`, là où les points du maillage sont espacés de 29 mm. Le
document 58 se trompait de cause. Ce qui reste vrai du 58 : le `11 × 11` porte
bien `0,08 mm` d'ondulation crête à crête sur 60 mm, et un repalpage après
nettoyage sous la feuille magnétique reste utile — mais pour le maillage
lui-même, pas pour ce défaut-là.

**L'input shaping est mesuré et appliqué.** X tournait à `57,2 Hz` recopié de Y
alors qu'il résonne autour de `40 Hz`, et à 270 mm/s cela fait une ondulation
tous les 6 à 7 mm — exactement le relief senti sur les couches 2 et 3. En
vigueur et écrit dans `printer.cfg` après deux séries de mesures : X `ei` à
`40,2 Hz`, Y `mzv` à `39,0 Hz`. Modifier le maillage ou le Z n'a aucun effet sur
ce réglage.

**Les courroies sont bonnes, ne pas y toucher.** Mesurées séparément, elles
tombent à `0,3 Hz` l'une de l'autre — `39,8` et `40,1 Hz`, même largeur, même
énergie. Le resserrage des vis fait par Thomas a fait monter X de `36,0` à
`40,2 Hz` et effondré la forêt de bosses parasites.

**Il reste un pic à `14,0 Hz` sur X, et sur X seulement** : 35 % de l'énergie
sous 30 Hz, contre 4 % sur Y et 1,5 % sur chaque courroie. Trop bas pour une
courroie ou un rail, c'est une masse entière qui se balance — support, pieds,
CFS posés contre la machine, panneaux. À 270 mm/s il produit des vagues de
19 mm, donc ce n'est **pas** le défaut visible (mesuré à 3-10 mm, soit le pic à
43 Hz, que le filtre corrige). Piste de fond, pas urgence. Doc 61.

**La surextrusion à l'arrivée du remplissage sur les parois est diagnostiquée**,
et ce n'est pas le maillage : le `pressure_advance_smooth_time` de `0,040 s` est
plus long que les rampes de freinage de la machine, qui durent `0,029 s`. Rien
n'a été corrigé ni testé, la calibration demande une impression. Doc 57.

## État réel

La machine est au repos et cohérente avec le dépôt. Relevé à la clôture :
Klipper `ready`, impression `standby`, chauffes à `0`, maillage actif
`k1_p001_t055_r001_n11x11`. Les empreintes des deux fichiers que nous possédons
sur la machine sont identiques à celles du dépôt :

```
k1-control-owned-start-print-v2.cfg   c46527dc369d7d327a1521a1feba8f13
kctrl_wait.py                         b8a680c3cdd5c1faac0f066920eeb548
kctrl_slot_map.py                     e446f4de6e14308e243ac363acb7a335

mesh-editor/server.py                 5fb3fb44765c8f1f2404029530e1de26
mesh-editor/www/app.mjs               6c0af23d7d0adf546051b92726c781ba
mesh-editor/www/index.html            894334d9bf9ff81ccf9ba2cd69b742a4
mesh-editor/www/styles.css            957f037e67bacd1102bff7653e3f37d3
```

Suite complète en local : `1053` verts, `2` rouges laissés volontairement (voir
plus bas).

Une CI GitHub tourne désormais à chaque poussée et sur chaque PR
(`.github/workflows/tests.yml`) : `pytest` et les tests du front de l'éditeur
de maillage. Elle couvre `834` tests. Elle **ne peut pas** couvrir seize
modules qui s'appuient sur les captures brutes de `inventory/raw/`, que
`.gitignore` garde volontairement hors du dépôt — identité machine, relevés
privés, G-code de plusieurs mégaoctets. Ces seize-là ne tournent que sur la
machine qui détient les preuves, et ils sont nommés un par ligne dans le
workflow plutôt que masqués derrière un motif.

### Ce que cette session a fermé

**La purge de démarrage est sous notre contrôle et bornée des deux côtés.**
Rien ne pousse de filament tant que le capteur de tête ne le voit pas :
`KCTRL_WAIT_FILAMENT SENSOR=filament_sensor_2 TIMEOUT=15`, une commande Python
et non un macro — un `G4` dans un macro appelé depuis `START_PRINT` n'est jamais
mis en file, ce qui a été mesuré et documenté dans l'ADR-053. La buse est
chauffée et attendue avant la première poussée. Le complément de purge vaut
`120 mm` : `200` donnent la boule qui se décroche, `180` débordent du bac,
`120` est le plafond retenu par Thomas. Réglable à chaud par
`SET_GCODE_VARIABLE MACRO=_KCTRL_PURGE_BALL VARIABLE=purge_mm VALUE=<n>`.

**L'éditeur de maillage corrige au pas et par sélection multiple.** Pas de
`0,005` / `0,01` / `0,02` / `0,05`, accélération à la répétition, rectangle avec
`Maj`, ajout et retrait avec `Ctrl`, anneau, annulation par groupe. ADR-052.

**La surface imprimable réelle est établie** : `X 0 → 300`, `Y 0 → 295`,
`Z 0 → 300`. La limite `Y` est appliquée ligne par ligne pendant l'impression
dès qu'un CFS est déclaré et met l'impression en pause. Elle n'est pas relevée,
et pourquoi est écrit dans l'ADR-054.

### Écarts ouverts, mesurés

- **`Tn_extrude_temp` est descendu à `200`** dans `box.cfg` le 2 septembre. La
  clé n'est pas modifiable à chaud : `MODIFY_BOX_CFG TN_EXTRUDE_TEMP=` répond
  `success` sans rien enregistrer, et `SAVE_BOX_CFG` confirme `ok:no save`. Une
  session PETG demande de remonter la valeur dans le fichier puis de redémarrer
  Klipper. Voir doc 54 et ADR-055.
- **Le rechargement automatique n'est pas encore prouvé de bout en bout.** Toute
  la chaîne est vérifiée pièce par pièce, mais seule une bobine réellement
  épuisée en cours d'impression peut le démontrer.
- **Le popup de correspondance n'a pas été vu tourner.** La table qu'il écrit
  est lue et prouvée à froid, mais aucune impression n'a été lancée depuis
  l'écran. Premier vrai départ à faire par Thomas. Voir doc 55.
- **Le multi-filament n'a jamais tourné sur cette machine.** Les changements de
  couleur passent par le `cmd_T` stock, qui lit les volumes de purge dans le
  fichier tranché ; rien de tout cela n'a été exécuté ici.
- **Le rapport de purge ne mesure rien d'utile.** Il a affiché `-2 mm` : les
  routines box émettent des `G92 E0` dans l'étape matière et l'axe extrudeur
  repart de zéro sous le repère. Il le dit désormais au lieu d'afficher un
  chiffre faux. Le compteur honnête est la position du moteur pas à pas, que
  `G92` ne touche pas, et se lit en Python.
- **Le Z accepté est stocké en un seul enregistrement global**, pas par profil
  de mesh. Préalable bloquant à toute campagne multi-températures.
- **Chaque `FIRMWARE_RESTART` remet le maillage actif sur `default`.** Il faut
  recharger `k1_p001_t055_r001_n11x11` derrière, sinon l'impression part sur un
  maillage vide.
- **L'éditeur de maillage est un service depuis le 2 septembre au soir**,
  `/etc/init.d/S58k1_control_mesh_editor`, posé par
  `scripts/deploy-k1-control-mesh-editor-v1.ps1`. Il démarre avec la machine.
  `Ouvrir-Editeur-Maillage-K1-Max.cmd`, à la racine, monte le tunnel et le
  relance s'il manque. Le démarrage au boot lui-même n'a pas encore été prouvé :
  aucun redémarrage complet n'a eu lieu depuis la pose.
- **`Tnn_map` ne survit pas à la machine.** Un arrêt d'urgence ou une coupure
  rend un `tn_data.json` sans la table, et seul le popup de l'écran la remplit.
  `START_PRINT` se rabat désormais sur `slot_last_choice`, le dernier
  emplacement choisi par `KCTRL_SLOT`, et le dit sur sa ligne de démarrage.
  `KCTRL_SLOTS` affiche la même résolution avant de lancer. Voir ADR-058.
- **Deux tests laissés rouges volontairement**, ils signalent des divergences
  réelles et non des tests à réparer :
  `test_all_canonical_scenarios_are_implemented_once` (divergence
  `end_full_unload` du design contre `end_keep_engaged` du moteur) et
  `test_unload_requires_head_sensor_to_clear`.

### Pièges de la machine, à ne pas redécouvrir

- `FIRMWARE_RESTART` relit la configuration mais **pas** les modules Python.
  Modifier `kctrl_wait.py` ou `kctrl_slot_map.py` exige
  `/etc/init.d/S55klipper_service restart`, qui remet le maillage actif sur
  `default` — le recharger derrière. Si
  les contrôles de mouvement de l'écran meurent ensuite :
  `/etc/init.d/S99start_app restart`.
- **Vérifier `print_stats.state` avant toute commande machine.** Une impression
  peut avoir été lancée depuis l'écran entre deux échanges, sans que rien ne le
  signale ici. Le 2026-09-02 un `TURN_OFF_HEATERS` est parti sur une machine
  qu'on croyait au repos : la buse est tombée de `190` à `175 C` en pleine
  première couche avant d'être rétablie.
- **Ne jamais lancer `SAVE_CONFIG` sur cette imprimante.** Attention : la règle
  ne couvre pas tout. `SHAPER_CALIBRATE` écrit dans `printer.cfg` de lui-même,
  sans qu'aucun `SAVE_CONFIG` soit demandé — observé le 2026-09-02, journal
  `save_config: set [input_shaper] shaper_freq_x = 50.6`. Sauvegarder le fichier
  **avant** de lancer la commande, pas après. Doc 60.
- `scp` n'existe pas ici. Déployer par `ssh hote "cat > /chemin" < fichier`.
- `grep` n'a pas `--include`, `pkill` n'existe pas, `curl` refuse `-s`, `-S`,
  `-o` et `-w`.
- Un `.pyc` voisin de `kctrl_wait.py` est présent et cohérent avec la source
  (généré à l'import). Après tout redéploiement du module, vérifier qu'il a bien
  été régénéré avant de conclure sur un comportement.

## Règle absolue avant tout palpage

**Aucune calibration, aucun palpage Z, aucun démarrage d'impression sans que
Thomas ait nettoyé la buse à la main et l'ait dit.** Le nettoyage manuel impose
que le filament soit rétracté avant. Le nettoyage automatique de brosse n'a
jamais fonctionné et a été retiré de la séquence possédée : il n'existe aucun
substitut. Une mesure prise sur une buse sale n'est pas dégradée, elle est
fausse et se propage dans un profil persistant. Voir ADR-045.

Ordre imposé : retrait filament, nettoyage manuel confirmé, chauffe, palpage.

## Voie CFS stock : rétablie et prouvée

Le blocage de trois semaines est levé. Après bascule des trois inclusions en
variante `disabled` et redémarrage Klipper, un cycle complet retrait puis
chargement a été exécuté depuis l'écran et capturé par
`gcode/subscribe_output` : coupe réelle (`cut sensor state:1` puis `:0`),
rembobinage CFS effectif, puis chargement jusqu'à `box.T1.filament: A` avec
purge visible et filament correctement inséré, confirmé par Thomas.

État physique après ce cycle : `box.state connect`, `box.T1.filament A`,
`T1.mode 2`, les deux capteurs filament vrais, cibles de chauffe à zéro,
`X/Y` référencés, `print_stats standby`. La machine peut produire.

Le tronçon de filament qui maintenait `filament_sensor` à vrai venait d'un
rembobinage sans coupe antérieur ; il n'a jamais bouché le chemin. Aucune
intervention mécanique n'est nécessaire.

ADR-044 fixe la règle : aucune garde ne doit être réinstallée sur les
primitives `BOX_*` sans une capture équivalente pour son remplaçant.

**Défaut relevé au passage, traité depuis** : la purge annonçait
`flush_temp: 220`, issu de `Tn_extrude_temp` codé en dur dans `box.cfg`. La
valeur est à `200` depuis le 2 septembre. Voir doc 54.

## Verrou CFS et sortie de secours

Le 1er septembre, aucun retrait de filament n'était possible : le composant
`k1_control_cfs_direct_owner`, posé `enabled: true` avec
`stock_commands_blocked: true`, refuse toute commande `BOX_*`, et son propre
retrait n'a jamais été implémenté. Onze refus `stock_effect_command_blocked`
ont été capturés, y compris sur les tentatives manuelles depuis l'écran. Le
firmware Creality n'est pas en cause. Voir ADR-043 et le document 52.

**Sortie de secours officielle**, dans `printer.cfg` :

```
[include k1-control-cfs-direct-owner-disabled-v1.cfg]
[include k1-control-stock-derived-cycle-owner-disabled-v1.cfg]
[include k1-control-stock-geometry-handoff-disabled-v1.cfg]
```

puis redémarrage Klipper. Les includes `k1-control-z-mesh.cfg` et
`k1-control-calibration-path.cfg` restent en place : le Z et le mesh sont
conservés. Retour arrière : remettre les trois `-active-`. Sauvegarde machine :
`printer.cfg.bak-before-cfs-unblock`.

## Prochaine action

Machine froide, Thomas présent, dans cet ordre :

D'abord, deux gestes courts qui ne demandent pas la machine chaude :

- **Enregistrer le Z réellement voulu.** Le profil porte `+0,040 mm` alors que
  Thomas a imprimé à `0`. Ouvrir l'éditeur de maillage, « reprendre »,
  « Enregistrer Z » : le démarrage suivant part sur la bonne hauteur.
- **Passer `pressure_advance_smooth_time` à `0,020 s`**, puis une tour de
  réglage du Pressure Advance pour le PLA. Doc 57 porte le calcul et l'ordre
  des opérations.
- **Juger la pièce en cours à l'ongle**, couches 2 et 3 : le relief doit avoir
  disparu. C'est la seule preuve que le nouveau réglage fonctionne, et elle
  n'est pas encore faite. Réserve : cette impression a subi une chute de
  température de `190` à `175 C` en première couche, sans effet attendu sur les
  couches 2 et 3. Doc 60 et 61.
- **Baisser l'accélération du trancheur.** Le profil imprime le remplissage
  plein à `9500 mm/s²` ; les mesures conseillent `3000` sur X et `4500` sur Y.
  Au-delà, le filtre arrondit les angles. Doc 60.
- **Chercher d'où vient le pic à 14 Hz** : support qui fléchit, pied qui
  balance, CFS posés contre la machine, panneaux mal fermés. Ce n'est pas le
  défaut visible, mais c'est ce qui empêche X de descendre sous 20 % de
  vibrations restantes. Doc 61.
- **Nettoyer sous la feuille magnétique, la reposer, repalper le `11 × 11`** et
  comparer au maillage en vigueur. C'est l'expérience qui tranche. Doc 58.

Ensuite :

1. **Un vrai départ depuis l'écran tactile**, buse nettoyée à la main au
   préalable. C'est le seul test qui prouve le popup, la correspondance et le
   chargement sur la bobine choisie. Vérifier ensuite `KCTRL_MAP` : il doit
   montrer ce qui a été choisi à l'écran.
2. **Un multi-filament**, deux couleurs, pour voir les changements d'outil et
   les purges du trancheur. Jamais exécuté sur cette machine.
3. **Confirmer les `120 mm`** de purge à l'œil au-dessus du bac.
4. **Refaire le compteur de purge en Python**, sur la position du moteur pas à
   pas, immune aux `G92`. Il remplacera l'arithmétique par un nombre.
5. Correctif Z-par-profil, puis bande de température supplémentaire.
5. Ligne d'amorce sur `CX_PRINT_DRAW_ONE_LINE_V2`, vitesse portée d'environ
   `F3000` à `F9000`.
6. Rendre le serveur de l'éditeur de maillage persistant au redémarrage.
7. Retirer la ligne `KCTRL_PRODUCTION_ARM` du profil Orca.
8. Capture automatique du Z avant que `END_PRINT` le remette à zéro.
9. Rechargement automatique en fin de bobine — bloqué tant que `END_PRINT` ne
   nous appartient pas, à faire délibérément et à froid.

Lire dans cet ordre à la reprise : ce fichier, `STATE.md`, puis les ADR 053 et
054 pour la purge et la surface imprimable, 052 pour l'éditeur de maillage.

## Archive

L'état du 1er septembre — capteur du cutter qualifié, voie CFS stock
rétablie, recadrage de périmètre — est consigné dans les ADR-041 et 042 et
dans `STATE.md`. Il n'est plus repris ici parce qu'il ne pilote plus
l'action.

La passation détaillée précédente, `HANDOFF-CUTTER-SENSOR-PAUSE-2026-09-01.md`,
reste consultable pour l'historique des preuves. Sa liste de gestes humains est
en revanche **périmée** : son point 2, l'appui manuel sur le levier, est retiré
par ADR-041.

Le contenu ci-dessous est conservé comme archive historique. Il décrit l'état
antérieur à la qualification du capteur et ne doit plus piloter l'action.

# Archive — reprise après refus réel du cutter le 1er septembre 2026

La quantité de purge est corrigée et installée : la reprise fautive utilisait
`30 mm`, alors que le chargement initial stock observé utilise `140 mm`. Le
cycle lit désormais le vecteur et la matrice Orca du G-code ; le fichier
d'essai courant demande notamment `266,081080 mm` pour une transition `0→1`.

Le dernier essai s'est arrêté proprement avant retrait. La tête a essayé la
position stock `X38 Y304,5`, puis des pas de `0,5 mm` jusqu'à la limite publiée
`Y307,5`. Le capteur `cut_pos` est resté à `0` partout. Aucune commande de
retrait n'a donc été envoyée. `T1A` reste chargé, les deux capteurs filament
sont actifs, les chauffes sont à zéro, les axes sont libérés, le mesh
`k1_p001_t055_r001_n11x11` est actif et le Z accepté reste `−0,04 mm`.

Ne pas rejouer automatiquement le cutter et ne jamais dépasser `Y307,5`. La
prochaine étape est une vérification mécanique réelle, à froid, du levier du
cutter et de son capteur. ADR-040 et le `RESULT.md` du paquet
`stock-derived-cycle-activation-v1` sont les références canoniques.

Un moniteur manuel en lecture seule est prêt. Le préflight froid et la caméra
sont verts ; sa première fenêtre de `90 s` n'a vu aucune transition, mais
l'appui humain n'a pas été confirmé. Ne pas en déduire une panne. La prochaine
preuve est l'appui puis le relâchement du poussoir/levier solidaire de la tête,
avec observation obligatoire de `cut_pos : 0→1→0`.

Le texte ci-dessous est l'archive de la reprise précédente.

# Archive — reprise après KO borné de la V1 physique directe

La gate
`G4-K1-CONTROL-CFS-DIRECT-OWNER-PHYSICAL-LOAD-UNLOAD-V1` est close KO et ne
doit jamais être rejouée. Capture privée :
`20260831-132914-g4-k1-control-cfs-direct-owner-physical-load-unload-v1`.
L'activation s'est arrêtée sur `stock_auto_refill_invalid` après restart, avant
chauffe, trame CFS, moteur filament ou mouvement d'axe. Le rollback a remis
`enabled=false`, zéro cible, axes libérés, `11 × 11` et Z `−0,04`. Les deux
capteurs sont toujours actifs : le filament initial est resté engagé.

Thomas a corrigé la frontière produit et ADR-037 la rend canonique : tout
retrait passe d'abord par la position cutter et la coupe ; tout chargement est
immédiatement suivi d'une purge dans le vrai bac, de `3 à 4` allers-retours
francs de décrochage, puis d'une preuve caméra. Aucun palpage ou mesh après
insertion. La prochaine mission est uniquement
`G4-K1-CONTROL-CFS-CUTTER-PURGE-INTEGRATED-R2-OFFLINE-V1` : construire et
tester la chorégraphie complète hors imprimante, y compris la persistance
d'`auto_refill`, avant toute nouvelle action physique.

Le texte ci-dessous décrit l'état précédent et reste une archive.

La reprise canonique est désormais :

`docs/51-proprietaire-cfs-direct-candidat-pose-desactivee-v1.md`

ADR-036 est acceptée et `cfs-direct-owner-offline-v1` obtient `24/24`. Le cycle
intégré ne dépend plus d'aucun effet `BOX_*`. Le candidat désactivé obtient
`13/13`, puis il est posé sous
`20260831-123137-g4-k1-control-cfs-direct-owner-install-disabled-v1`. Le
composant est chargé avec `enabled=false`, transport non pris, commandes stock
non remplacées et zéro trame CFS. Une validation intégrée et deux validations
indépendantes sont vertes. L'état final est froid, au repos, axes libérés,
`11 × 11` actif, Z `−0,04`, deux CFS connectés et aucune route logique.

L'ancienne tranche annoncée était
`G4-K1-CONTROL-CFS-DIRECT-OWNER-PHYSICAL-LOAD-UNLOAD-V1` : activer sous
surveillance, qualifier un seul cycle direct `T1A`, puis remettre un état sûr.
Cette tranche est maintenant close KO et remplacée par ADR-037.

Lire le document 51, ADR-036, puis les derniers blocs de `STATE.md`, `GATES.md`
et `DECISIONS.md`. Le contenu ci-dessous est conservé comme archive des
clôtures antérieures ; il ne décrit plus l'état actuel et ne doit pas piloter
la prochaine action.

L'observabilité V2 est qualifiée hors imprimante puis sur la vraie K1. La gate
d'effet a ensuite désactivé une fois l'auto-remplacement stock, prouvé deux fois
la valeur `0`, restauré une fois la valeur précédente `1` et prouvé deux fois
ce retour exact. Le verdict final est
`CLOSED_OK_EXCLUSION_AND_EXACT_RESTORE_QUALIFIED`. Les captures sont consommées
et ne doivent pas être rejouées.

`GOAL-P4-OFFLINE-CYCLE-CFS-V1` est terminé hors imprimante et
`GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` est terminé en lecture seule. La capture
canonique de ce second Goal reste
`20260827-142853-goal-p4-k1-read-only-qualification-v1`. Le Goal 3 reste en
cours à `2/7` ; le nettoyage automatique est clos KO et le nettoyage manuel
est obligatoire.

`G4-K1-CONTROL-CFS-OWNER-CORE-OFFLINE-V1` reste clos avec `21/21` scénarios.
Son successeur `G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-OFFLINE-V1` est
maintenant clos avec `25/25` scénarios et `15/15` tests ciblés. Le garde pur
sauvegarde la valeur stock, prépare au plus une désactivation non exécutable,
exige deux lectures qui prouvent l'effet puis restaure exactement la valeur
précédente. Un acquittement seul ne prouve rien et un résultat incertain n'est
jamais rejoué.

Le vrai Z accepté `−0,04 mm` vient de `KCTRL_STATE`, sous une connexion
Moonraker persistante. `T1/T2`, l'absence de route, les chauffes zéro, le mesh
`11 × 11` et les configurations sont inchangés. Aucun filament, mouvement,
chauffage, fichier distant ou service n'a été touché. Le Goal 3 reste à `2/7`.

La prochaine mission unique est `G4-K1-CONTROL-START-SEQUENCE-OWNER-V1`.
Il faut d'abord rendre son candidat hors imprimante installable et réversible ;
la pose et l'essai physique resteront une tranche distincte. La production et
les primitives filament non qualifiées restent fermées.

## Archive historique — clôture initiale du Goal 2

Date de passation : 2026-08-27
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Branche cible : `main`
Nouvelle tâche créée : non
Goal actif : absent après clôture

## État à annoncer immédiatement à Thomas

- **`GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` est terminé.**
- La lecture réelle est qualifiée sans effet, mais la suite physique est
  bloquée : le mesh actif `default` diffère du profil robuste requis.
- Le profil robuste `k1_p001_t055_r001_n06x06` existe encore avec sa bonne
  empreinte ; il n'a pas été chargé, car le Goal 2 l'interdisait.
- Aucune impression, G-code, écriture distante, chauffe, mouvement, restart,
  action CFS ou reconnexion provoquée n'a eu lieu.
- La production reste fermée et le mode Précision reste caché.
- Cette session source doit rester visible et ne doit pas être archivée.

## État livré

La capture privée retenue est
`20260827-142853-goal-p4-k1-read-only-qualification-v1`. Le nettoyage a lieu sur
la K1 avant le retour local : aucun numéro de série, UUID, nom de fichier
d'impression ou contenu de configuration n'est exporté.

Deux lectures stables confirment Klippy prêt, l'imprimante en `standby`, les
cibles à zéro, les axes libérés, `T1/T2` connectés, `T3/T4` non configurés,
aucune route engagée, `t_command` vide, le capteur de tête actif et le Z accepté
à `−0,04 mm`. L'identité filament reste donc classée `engaged_unknown`.

Les lectures d'état ont pris `199,212 ms` et `235,525 ms`, sous le plafond de
`5 s`. La forme est identique entre les deux réponses. Les douze empreintes de
configuration, composants Moonraker et fichiers UI correspondent aux versions
revues et sont identiques avant/après.

Le seul écart bloquant est réel : le mesh actif `default` et le profil robuste
requis `k1_p001_t055_r001_n06x06` sont tous deux des matrices `6 × 6`, mais
leurs empreintes diffèrent. Le robuste existe toujours ; il n'est simplement
pas actif. Le statut fermé est `CLOSED_READ_ONLY_BLOCKED_MESH_DRIFT`.

Le collecteur `GET`, la traduction pure, le délai et la règle d'invalidation du
mapping sont qualifiés. Une reconnexion très courte qui revient au même état
entre deux sondages reste invisible ; le futur composant Moonraker devra donc
prendre son époque dans les notifications.

Le pilotage macro est maintenant centralisé dans `GOALS.md` :

1. `GOAL-P4-OFFLINE-CYCLE-CFS-V1` — terminé hors imprimante ;
2. `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` — terminé en lecture seule avec KO
   borné du mesh actif ;
3. `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1` — installer et qualifier les
   fonctions physiques par petites tranches avec Thomas présent, après le
   chargement contrôlé du profil robuste ;
4. `GOAL-P4-DAILY-CUTOVER-V1` — basculer enfin vers le fonctionnement quotidien
   complet avant la campagne G5.

Ces noms sont des regroupements de pilotage. Ils ne remplacent pas les gates de
`GATES.md` et ne donnent aucune autorité d'installation ou de production.

## Git vérifié avant le commit de cette passation

- base de mission : `5927a7ff49b67dc52a9ae5af6f1a1193ff19003a` ;
- `main` local et `origin/main` étaient alignés sur cette base ;
- divergence : `0/0` ;
- checkout propre au départ ;
- un seul worktree ; travail réalisé sur `codex/k1-read-only-qualification-v1` ;
- aucune branche de mission ou ressource étrangère observée ;
- le SHA final contenant cette passation sera communiqué dans le compte rendu.

## Vérifications réutilisables

- preuve live nettoyée : **OK**, `2/2` lectures ;
- schéma réel : **OK**, stable et épinglé ;
- délai de lecture : **OK**, maximum observé `235,525 ms` sous `5 s` ;
- empreintes distantes : **OK**, exactes et inchangées ;
- CFS, Z et état au repos : **OK** pour la lecture seule ;
- mesh actif conforme au contrat quotidien : **KO borné** ;
- validation physique ou humaine : **non exécutée**, hors périmètre ;
- effet sur la K1 : **aucun** ;
- suite complète : **OK**, `488` tests exécutés, `485` verts et `3` ignorés ;
- scripts PowerShell : **OK**, `29` fichiers relus sans erreur.

## Prochaine mission unique

### Gate préalable au `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1`

Thomas doit être devant la K1. La prochaine gate vérifiera l'état sûr et les
empreintes, chargera uniquement `k1_p001_t055_r001_n06x06`, puis relira le nom
actif et la matrice sans lancer d'impression. Elle s'arrêtera au premier écart
et gardera un retour arrière exact.

Relire dans cet ordre : `HANDOFF.md`, `GOALS.md`, le document 41, le `RESULT.md`
et le contrat du paquet `k1-read-only-qualification-v1`, puis le plan futur.

Cette action modifie l'état d'exécution de la K1 et exige une nouvelle
autorisation explicite ; le Goal 2 clos ne l'autorise pas. Concrètement, le
prochain GO permettra seulement de charger le profil robuste déjà présent et
de vérifier sa matrice, pas d'imprimer ni de commencer toutes les tranches du
Goal 3.

Modèle conseillé : `gpt-5.6-terra`, raisonnement `high`, car la tâche est petite
mais touche du matériel réel et doit distinguer précisément profil, matrice et
rollback. Option économique : `gpt-5.6-terra` en `medium`, avec un risque plus
élevé de reprise si un état transitoire ou une incohérence de preuve apparaît.
