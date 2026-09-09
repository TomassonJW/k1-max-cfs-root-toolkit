# 70 — Audit indépendant de la séquence de démarrage (K1 Max + CFS, 2.3.5.34)

Date : 2026-09-10, 01:10. Auditeur : agent neuf, sans reprise des conclusions
du dépôt. Rien n'a été modifié sur la machine ni dans le dépôt en dehors de ce
fichier. Aucune commande de mouvement, de chauffe ou de déploiement n'a été
envoyée.

Convention de ce rapport, appliquée à chaque énoncé :

- **[FAIT]** : lu dans un journal, un fichier ou une source de code, cité.
- **[HYPOTHÈSE]** : explication cohérente avec les faits, non démontrée.
- **[SIMULATION]** : résultat d'un test hors imprimante (pytest) ou d'un calcul.
- **[INCONNU]** : non observable (module compilé) ou non recherché faute de moyen.

## 0. Ce que l'audit a trouvé en premier : la machine est en pause, chauffe allumée

**[FAIT]** Un départ réel a eu lieu le 10 septembre à 00:51:00
(`SDCARD_PRINT_FILE` reçu par Moonraker, `klippy.log` ligne 115919), vingt
minutes après le commit du prompt d'audit (00:31). C'est le premier départ avec
la séquence déployée à 00:03. `STATE.md` et le prompt d'audit disent encore
« aucune impression n'a tourné » : c'est dépassé.

**[FAIT]** État lu par Moonraker à 01:03 :

| Objet | Valeur |
|---|---|
| `print_stats.state` | `paused` (durée d'impression 54 s, 159 mm extrudés) |
| `toolhead.position` | X -1.1, Y 180.0, Z 2.47 (fin de la ligne d'amorce possédée) |
| `extruder` | 220,1 °C, cible **220** |
| `heater_bed` | 55,4 °C, cible 55 |
| `filament_sensor_2` (tête) | filament détecté, capteur actif |
| `box` | `connect`, `enable 1`, `last_cmd None`, `error None` |

**[FAIT]** Chronologie du départ de 00:51 (`klippy.log`, lignes 115962 à 120840) :

```
00:51:04  K1 Control start: ... filament 2 du fichier (T1B) -> emplacement T2D ... Z 0.1400
00:51:05  master-server envoie SET_HOTEND_FAN VALUE=1 (webhooks gcode/script, id 265572462)
00:52:06  fenetre de palpage ouverte, plafond 105 C ; G28 ; palpage ; mesh
00:53:22  fenetre de chargement CFS ouverte, plafond 235 C
00:53:23  cmd_T vtnn=T1B ; last_cmd = None ; Tnn_map[T1B] = T2D ; z_down move_z: 0.8
00:53:23  last_cmd=None, get_fialment_sensor_detect()=True  ->  move_to_cut
00:53:28 .. 00:53:47  "[box] cut to return failed"  x5
00:53:48  "Cut sensor not triggered."  key841 cut error  ->  "error: printing to pause"
00:53:50  do_after_pause: printing to pause ; BOX_MOVE_TO_SAFE_POS ; Z 50.0
00:53:58  move_to_cut()=False ; cut_err vtnn=T1B return False
00:54:24  K1 Control: complement de purge de 120 mm a 220 C   (la macro continue)
00:55:01  92 mm pousses ; fenetre CFS fermee ; descente 42 -> 0.05
00:55:15  ligne d'amorce, 3 passes a Z 0.36, 20 mm3/s, 26.6 mm
00:55:22  virtual_sdcard: Exiting SD card print (position 19371)  -> etat paused
00:55:22  key61 Unknown command: SET_HOTEND_FAN   (reponse a la requete de 00:51:05)
00:56:25  M104 S260 recu par webhooks ; 00:57:11  M104 S220
```

Lecture : le changement d'outil émis tôt par `START_PRINT` a pris la branche
« couper » parce que la tête contenait encore le filament du blocage de 23:43.
Le coupe-filament a échoué cinq fois. Le module CFS a demandé la pause à
00:53:50, mais `START_PRINT` est une seule ligne du fichier : la macro a
continué 90 secondes, a poussé 120 mm d'un filament ni coupé ni identifié, a
tracé la ligne d'amorce, puis la file s'est mise en pause. Depuis 00:55, la
buse est à 220 °C, à 2,5 mm au-dessus de la ligne d'amorce, avec du filament
dedans. À 01:03 elle y était encore.

**[FAIT]** Si l'impression est reprise telle quelle, la ligne 275 du fichier
(`T1`) sera exécutée avec `last_cmd = None` et le capteur de tête à `True` :
c'est exactement la combinaison qui a mené à `move_to_cut` à 00:53:23. Le
coupe-filament étant en échec, le résultat le plus probable est une nouvelle
pause au même endroit **[HYPOTHÈSE]**.

Aucune action n'a été prise : cette décision (annuler, ou reprendre après
intervention sur la tête) appartient au propriétaire.

**[FAIT]** Relecture après rédaction (10/09, ~01:15) : `print_stats.state` =
`cancelled`, cibles buse et plateau à 0, capteur de tête à `False`, axes non
referencés, Z 150. Le propriétaire a annulé et vidé la tête entre-temps ; le
P0 du §4 est donc exécuté. L'état du coupe-filament reste non vérifié.

## 1. Dangers matériels, par gravité décroissante

### D1 — Descente Z calculée, pas relue : un Z négatif au-dessus du plateau est accepté entre -10 et 0

**Mécanisme.** **[FAIT]** Le module CFS tient un accumulateur `move_z` : chaque
levée qu'il commande l'incrémente (`z_down move_z: …`), et `z_restore` redescend
de la valeur accumulée. `virtual_sdcard.py` lignes 981-984 remet cet
accumulateur à zéro au début de chaque fichier (`Move z not clear` puis
`move_z = None`), et nulle part ailleurs. **[FAIT]** Sur cette machine, toutes
les commandes de mouvement passent par `toolhead.move`, qui appelle
`record_z_pos(newpos[2])` *avant* `kin.check_move` (toolhead.py Creality) ;
`corexy.py` refuse tout Z hors `[position_min, position_max]` = `[-10, 305]`
(`printer.cfg`). Un Z entre -10 et 0 passe la vérification.

**Preuve.** **[FAIT]** Cinq occurrences dans les journaux, pas deux :

| Date | Accumulateur avant `z_restore` | Z demandé | Position X/Y | Refusé ? |
|---|---|---|---|---|
| 05/09 12:53 | 20,0 puis 20,08 | -19,917 | 210 / 291,5 (essuyeur droit) | oui (< -10) |
| 05/09 18:16 | 20,0 | -18,037 | 210 / 291,5 | oui |
| 05/09 19:15 | 20,0 puis 20,08 | -19,117 | 210 / 291,5 | oui |
| 09/09 18:20 | 20,0 → 20,8 → 44,027 | -18,951 | 185,5 / 291,5 (poste de purge) | oui |
| 09/09 23:43 | 20,0 → 20,8 → 44,027 | -18,951 | 185,5 / 291,5 | oui |

Détail du 09/09 23:4x : `record_z_pos 24.97` → `z_down 20.0` à 23:41:17,
juste après « complément de purge de 120 mm » (donc levée commandée par
`BOX_GO_TO_EXTRUDE_POS`, appelé par `_KCTRL_PURGE_BALL`) ; le 13:26 du même
jour, la même levée de 20 suit `BOX_EXTRUDE_MATERIAL` (tête vide). Ensuite
`cmd_T` ajoute 0,8 puis 23,2 (levée réelle 2,09 → 25,04), et `z_restore`
descend de 44,027 depuis 25,076 : -18,951. Les cinq fois, la sécurité qui a
sauvé la machine est `position_min: -10`, par pur excès de l'erreur (18 à 20 mm).
**[SIMULATION]** Avec un accumulateur parasite de 8 mm au lieu de 20, la cible
aurait été -6 : acceptée, exécutée, plateau 6 mm au-dessus du plan de buse à
Y 291,5, c'est-à-dire *sur* le plateau (`mesh_max: 295`).

**Racine.** **[HYPOTHÈSE forte]** La séquence possédée appelle
`BOX_EXTRUDE_MATERIAL` et `BOX_GO_TO_EXTRUDE_POS` sans jamais appeler la
primitive de retour (`RESTORE_POSITION`, dont le stock
`BOX_LOAD_MATERIAL_WITH_MATERIAL` fait sa dernière ligne, et qui journalise
`z_restore move_z: None` quand il n'y a rien à rendre — vu à 13:48 et 15:25).
Le 20 reste donc dans l'accumulateur jusqu'au premier changement d'outil de
l'impression. Le stock `BOX_START_PRINT_EXTRUDE_MATERIAL` laisse aussi 20,12 le
08/09 23:51 — le défaut existe donc aussi côté Creality — mais le stock n'émet
jamais de `T` sur une tête déjà chargée sur le bon emplacement.

**Toujours présent dans l'état déployé ?** **Oui.** La séquence du 10/09
appelle toujours `BOX_GO_TO_EXTRUDE_POS` sans retour. Le correctif « T émis
tôt » n'enlève que *le* déclencheur du fichier mono-filament ; tout fichier
multi-filaments (deuxième `T` réel) retrouve l'accumulateur parasite à son
premier changement. **[FAIT]** Le garde de zone proposé (`Y >= 296`) ne couvre
pas Y 291,5, lieu des cinq refus ; son propre docstring le reconnaît.

### D2 — `START_PRINT` ignore l'erreur CFS et continue à pousser et à tracer

**[FAIT]** 00:53:48 → 00:55:15 : après `key841` et la demande de pause du
module, la macro a enchaîné `_KCTRL_CFS_LOAD` ×4 (chacun commence par
`BOX_ERROR_CLEAR`, mais le corps est sauté car le capteur de tête voit déjà du
filament — cfg ligne 449), `KCTRL_WAIT_FILAMENT` (satisfait), `M109`,
`BOX_EXTRUDER_EXTRUDE`, purge de 120 mm à 220 °C, `BOX_MATERIAL_FLUSH`,
descente à Z 0,05 en X -1,8 / Y 0, ligne d'amorce à 20 mm³/s. Le `T` a
retourné `False` sans lever d'erreur Klipper ; aucune assertion de la macro ne
regarde `printer.box.error` ou l'issue du `T`. Le filament poussé était celui
laissé dans la tête à 23:43 ; qu'il soit le bon (eSUN T2D) est vraisemblable
**[HYPOTHÈSE]** mais n'a été vérifié par rien.

**Toujours présent :** oui, c'est la séquence déployée.

### D3 — Coupe-filament en échec physique

**[FAIT]** 00:53:28-00:53:47 : `[box] cut to return failed` ×5, puis
`Cut sensor not triggered`, `key841`. `STATE.md` écrit « le cutter réparé passe
en 1,5 s » : c'est réfuté par ce journal. Le même code a précédé le blocage du
09/09 23:43 (cité dans le docstring du garde de zone). Tant que la coupe échoue,
**tout** changement d'outil échoue, quel que soit l'ordre des macros. Sources
communautaires sur ce code (TC2841) : débris sur la lame, `cut_pos_x/y` à
ajuster de 0,1 mm, rondelles derrière le cutter (voir §5).

### D4 — Chauffe maintenue en pause, buse chargée au-dessus de l'amorce

**[FAIT]** Cible 220 °C tenue depuis 00:55 au moins jusqu'à 01:03, buse à
2,5 mm de la ligne d'amorce, filament dans la tête. Un `M104 S260` est arrivé
par l'interface à 00:56:25, ramené à 220 à 00:57:11 (auteur : l'interface,
donc vraisemblablement le propriétaire — **[INCONNU]**). Dégradation du PLA
dans la buse et coulure sur l'amorce ; pas de risque de collision.

### D5 — Approche stock à Z 0,05 en X -1,8 / Y 0, buse froide, hors du mesh

**[FAIT]** `custom_macro.py` (machine) : `CX_PRINT_DRAW_ONE_LINE` fait
inconditionnellement `G1 X-1.8 Y0 Z2 F6000`, rétraction 12 mm, `G1 Z0.1 F600`,
puis chauffe. Journal 00:55:02 : `record_z_pos 0.051` (0,1 + offset 0,14 +
correction mesh au coin). X -1,8 est à 0,2 mm de `position_min: -2`. C'est le
comportement d'usine, conservé par la séquence possédée « pour la rétraction
et le drapeau ». Danger modéré : le point est hors de la grille de mesh
(extrapolation), et la descente précède la chauffe.

### D6 — Ligne d'amorce à 20 mm³/s

**[FAIT]** Bannière 00:55:15 : « 3 passes de 160 mm à Z 0.36, 150 mm/s,
20.0 mm3/s, 26.6 mm de filament ». **[FAIT]** Le profil filament officiel
Creality pour cette machine (`CR-PLA @K1 Max_CFS-C`) plafonne à 18 mm³/s ; la
ligne stock de `custom_macro.py` (E10 sur 160 mm à 50 mm/s) fait ≈ 7,5 mm³/s
**[SIMULATION]**. Le fichier tranché déclare 23/24 pour les deux filaments,
mais la fiche matière CFS déclare 14 (`max_volumetric_speed: 14` dans le
journal). Risque : sous-extrusion ou claquement d'extrudeur sur l'amorce, pas de
danger mécanique. X -1,7 / -1,4 / -1,1 recopient les coordonnées stock de cette
version de `custom_macro.py` ; marge 0,3 mm à `position_min`.

### D7 — `z_pos.json` enregistre le Z *demandé*, même refusé

**[FAIT]** `record_z_pos` précède `check_move` ; le 09/09 23:43 le fichier a
reçu -18,951 (relu tel quel dans `print_stats.z_pos` avant le départ de 00:51).
`gcode_move.py` utilise `tn_move_z` et le dernier Z pour le Z de reprise après
coupure. Aujourd'hui `z_pos.json` vaut 2,086 (écrit 00:55). Danger dormant,
conditionné à une coupure de courant juste après un refus.

## 2. Incohérences de la séquence déployée

1. **[FAIT]** Le `T{position-1}` est émis *avant* `_KCTRL_CFS_LOAD` ×4, qui
   devient redondant s'il réussit et inopérant s'il échoue avec du filament en
   tête (le corps est sauté). Le seul cas où la boucle sert est « tête vide et
   `T` a échoué sans charger », qui n'a jamais été observé.
2. **[FAIT]** `BOX_ERROR_CLEAR` en tête de chaque tentative efface l'erreur que
   le `T` vient de poser ; `printer.box.error` vaut `None` à 01:03 alors que
   la coupe a échoué à 00:53.
3. **[FAIT]** `BOX_CHECK_MATERIAL` (= `WAIT_EXTRUSION_ALL_MATERIALS`, macro
   cfg) est appelé avant le `T` ; rôle non établi dans ce contexte **[INCONNU]**.
4. **[FAIT]** `M400` après le `T` : `cmd_T` est synchrone côté Python ; l'appel
   est inoffensif mais ne garantit rien de plus.
5. **[FAIT]** Le commentaire du cfg du garde de zone attribue `SET_HOTEND_FAN`
   à « la même routine CFS ». Faux : la commande est envoyée par
   `/usr/bin/master-server` via `webhooks gcode/script` (00:51:05, id
   265572462), et n'existe que dans `prtouch_v3_wrapper.so` ; le module
   `box_wrapper.so` ne contient pas la chaîne. Elle n'a jamais « arrêté la
   routine avant son Z fautif » : elle a été traitée après la fin de
   `START_PRINT`, 4 minutes plus tard.
6. **[FAIT]** `flush_temp: 220` à 18:20, 23:42 (deux fois chacun) alors que la
   base matière `00001` vaut 200 et que 13:17/13:26/13:46 donnaient 200. Les
   200 viennent tous de `box_extrude_material(T1B)` hors `cmd_T` ; les 220 de
   `cmd_T … box_extrude_material(T2D)`. Même identifiant matière `000001` dans
   les deux emplacements (`tn_data.json`) : la base ne peut pas expliquer 220.
   **[HYPOTHÈSE]** Le chemin `cmd_T` lit la température du filament dans le
   fichier tranché (`nozzle_temperature_initial_layer = 190,220`, filament 2).
   Le document 67 (« la base est la source ») ne vaut donc que pour le chemin
   `BOX_EXTRUDE_MATERIAL` direct.
7. **[FAIT]** `last_cmd` était `T2D` dans `tn_data.json` à 00:0x et `None` en
   mémoire à 00:53:23 (`part: tnn_map … last_cmd: None`). Le module efface
   `last_cmd` au démarrage d'impression (ou ne le relit pas). Le raisonnement
   « le `T` du fichier retombe sur le même outil et ne fait plus rien » exige
   que le `T` émis tôt *aboutisse* ; il n'aboutit pas avec du filament en tête
   et un cutter en panne.
8. **[FAIT]** Le dépôt affirme qu'un `G4` dans une macro imbriquée « n'est
   jamais mis en file » (`kctrl_wait.py`). La documentation Klipper dit
   l'inverse : `G4` → `toolhead.dwell`, élément de la file de mouvement ; ce
   qui n'est pas visible, c'est l'*état* pendant le rendu du template.
9. **[FAIT]** Tests : `4 failed, 1159 passed` (exécuté 01:00). Les deux tests
   du garde de zone visent Y 291,5 avec `zone_y_min 296` ; les deux autres
   (`test_cfs_direct_owner_offline_v1`, `test_job_lifecycle_offline_v1`) sont
   préexistants.
10. **[FAIT]** Trois fichiers non suivis dans le dépôt (garde de zone + test) ;
    branche `fix/cfs-temperature-chargement`.

## 3. Affirmations du dépôt : confirmées, réfutées, invérifiables

| # | Affirmation (STATE / docs / cfg) | Verdict | Preuve |
|---|---|---|---|
| A1 | Le trancheur pose `T1` après `START_PRINT` (ligne 275) | **Confirmée** | fichier, lignes 264 et 275 ; profil Orca officiel `K1 Max_CFS-C` émet `T[initial_no_support_extruder]` juste après `START_PRINT` |
| A2 | `last_cmd` n'est renseigné par rien de ce que `START_PRINT` appelait | **Confirmée, à nuancer** | `None` à 18:20, 23:42, 00:53 ; mais `T2D` persisté après le `cmd_T` complet de 23:43, effacé au départ suivant |
| A3 | Branche `last_cmd=None` + capteur `True` → `move_to_cut` | **Confirmée** | journal 00:53:23, 23:42, 18:19 ; doc de rétro-ingénierie FrederickAlt (§5) |
| B1 | Accumulateur `z_down` 44,027 et `z_restore` → -18,951 | **Confirmée** | journal 18:20 et 23:43 ; 3 cas antérieurs le 05/09 non mentionnés par le dépôt |
| B2 | Un Z entre -10 et 0 serait accepté | **Confirmée** | `corexy.py` `_check_endstops`, `position_min: -10` ; `manual_move` passe par `move` |
| B3 | Le refus « n'est pas rattrapé et la file ne repart jamais » | **Confirmée pour 23:43** | pause puis redémarrage Klipper à 00:03 |
| C1 | Le `T` émis tôt « prend l'autre branche, pas de coupe » | **Réfutée** | 00:53:23 : `move_to_cut`, tête chargée |
| C2 | « Le cutter réparé passe en 1,5 s » | **Réfutée** | 5 échecs, `key841`, 00:53 |
| C3 | « Le `T` du fichier ne fait plus rien » | **Invérifiable** (jamais atteint) | la file s'est arrêtée avant la ligne 275 ; `last_cmd` toujours `None` |
| C4 | « Aucune impression n'a tourné avec ce démarrage » | **Dépassée** | départ 00:51, en pause |
| D1 | Routage `T1` → `T1B` → `Tnn_map` → `T2D` | **Confirmée** | journal 00:53:23 ; `tn_data.json` |
| D2 | `BOX_MODIFY_TN` fusionne dans `tnn_map` | **Confirmée** | `tn_data.json` (16 clés, seule `T1B` remappée) ; doc FrederickAlt « persists all 16 keys » |
| D3 | `tn_data.json` perd `tnn_map` à la fin normale d'une impression | **Confirmée par source externe** | doc FrederickAlt : `BOX_END_PRINT` retire `enable`, `tnn_map`, `last_cmd` |
| E1 | `CX_PRINT_DRAW_ONE_LINE` ne trace que si `can_break_flag == 3` | **Confirmée** | `custom_macro.py` machine ; journal 23:42 (`can_break_flag = 3` puis trait) |
| E2 | Paramètres `_KCTRL_PRIME_LINE` (Z 0,36, 3 passes, F9000, 20 mm³/s, 26,6 mm) | **Confirmée** | cfg ; bannière 00:55:15 |
| E3 | 20 mm³/s est un bon défaut | **Non soutenue** | profil Creality 18, stock ≈ 7,5, fiche CFS 14 |
| F1 | Température de chargement « réglée et prouvée » à 200 | **Partiellement réfutée** | 220 sur le chemin `cmd_T` (18:20, 23:42) |
| F2 | Le 220 vient du profil Orca eSUN | **Cohérente, non prouvée** | même matière `000001` des deux côtés ; fichier dit 220 pour le filament 2 |
| F3 | Tests rouges : 2 garde + 2 sans rapport | **Confirmée** | pytest 01:00 |
| G1 | `SET_HOTEND_FAN` vient de la routine CFS et l'arrête avant le Z fautif | **Réfutée** | `master-server` via webhooks ; commande dans `prtouch_v3_wrapper.so` seulement |
| G2 | Le garde `Y >= 296` protège le lieu de l'incident | **Réfutée** | incident à Y 291,5 (×5) |
| G3 | `gcode_position_max: 295` interdit à un fichier d'aller au-delà | **Confirmée, avec réserve** | `virtual_sdcard.py` 1070 : contrôle textuel des `G0/G1 Y…` seulement si CFS actif ou `enforce_gcode_position_max` ; ne borne ni les macros ni le module |
| H1 | « `G4` imbriqué jamais mis en file » | **Réfutée** | doc Klipper `Command_Templates`, `toolhead.dwell` |
| H2 | `BOX_START_PRINT_EXTRUDE_MATERIAL START_PRINT=8` charge et renseigne `last_cmd` | **Invérifiable** | non documenté publiquement ; chaîne `extrude all material, last_cmd: %s` dans le module |
| H3 | Le module relit la base matière à chaque chargement | **Confirmée pour `BOX_EXTRUDE_MATERIAL`** | 200 le 09/09 13:xx après édition à 00:32 |

## 4. Ce qu'il faut changer, par priorité

| Prio | Changement | Coût | Risque | Statut de preuve attendu |
|---|---|---|---|---|
| **P0** | Sortir de la pause en connaissance de cause : **annuler** plutôt que reprendre (la reprise rejoue `T1` → coupe → même panne), couper la chauffe, retirer le filament de la tête par l'interface officielle, inspecter la lame et le capteur de coupe (débris, `cut_pos`). Décision propriétaire, pas d'action agent. | 0 | nul | `print_stats.state` = `standby`, cibles 0, `filament_sensor_2` = False |
| **P1** | Rendre l'accumulateur Z avant de quitter le bloc CFS : appeler `RESTORE_POSITION` (stock, fin de `BOX_LOAD_MATERIAL_WITH_MATERIAL`) après `BOX_MATERIAL_FLUSH`, ou remplacer la paire `BOX_EXTRUDE_MATERIAL` + `BOX_GO_TO_EXTRUDE_POS` par le stock `BOX_START_PRINT_EXTRUDE_MATERIAL START_PRINT=8` et mesurer si `last_cmd` en sort renseigné. | faible | faible (macro stock) | journal : `z_restore move_z: 20.0` puis `None` **avant** la ligne d'amorce ; aucun `Move z not clear` au départ suivant |
| **P2** | Faire échouer `START_PRINT` sur erreur CFS : après le `T`, lire `printer.box.error` / l'issue et `action_raise_error` ; sortir `BOX_ERROR_CLEAR` de la boucle pour qu'il ne masque pas un `cut_err`. | faible | faible | test hors imprimante + journal : arrêt à `cut_err`, pas de purge |
| **P3** | Ne jamais émettre de `T` avec du filament en tête et un cutter non prouvé : condition sur `filament_sensor_2` = False, sinon arrêt avec message. | faible | faible | journal : pas de `move_to_cut` au démarrage |
| **P4** | Plancher Z là où l'incident se produit : Y ≥ 285 (poste de purge, essuyeurs, `safe_pos_y`) et Z < 0 refusé **seulement** hors `G28`/palpage et pendant `print_stats.state == printing` ; corriger les deux tests. Ne pas déployer avant P1, qui supprime la cause. | moyen | moyen (enveloppe `toolhead.move`) | tests verts ; déclenchement simulé hors impression |
| **P5** | Ligne d'amorce : ramener à ≤ 15 mm³/s (F6750, ou moins de matière), garder Z 0,36. | faible | nul | bannière + inspection visuelle |
| **P6** | Documents : corriger `STATE.md` (départ 00:51, cutter, `SET_HOTEND_FAN`), le commentaire du cfg de garde, la note `G4` de `kctrl_wait.py`, et le §4 du document 67 (chemin `cmd_T` = 220). | faible | nul | relecture |
| **P7** | Élucider la source de température du chemin `cmd_T` (fichier vs base) par un essai contrôlé : même bobine, fichier à 200 vs 220, comparer `get next material temp`. | faible | nul | journal |

Tout ce tableau reste à faire ; rien n'a été modifié.

## 5. Sources

Locales (machine `k1max-root`, firmware 2.3.5.34) :

- `/usr/data/printer_data/logs/klippy.log` (10/09 00:49-01:00, lignes 112604-127569), `klippy.log.2026-09-09` (13:17-13:48, 18:15-18:21, 23:38-23:44), `klippy.log.2026-09-05` (12:46-12:53, 16:18-16:20, 18:15-18:16, 19:12-19:15).
- `/usr/share/klipper/klippy/toolhead.py` (`move`, `record_z_pos`, `manual_move`), `kinematics/corexy.py` (`check_move`, `_check_endstops`), `extras/virtual_sdcard.py` (lignes 916, 975-990, 1054-1096), `stepper.py` (325-331), `extras/gcode_move.py` (`recordPrintFileName`), `extras/custom_macro.py` (`cmd_CX_PRINT_DRAW_ONE_LINE_V2`), chaînes de `extras/box_wrapper.cpython-38-mipsel-linux-gnu.so` et `prtouch_v3_wrapper.cpython-38-mipsel-linux-gnu.so`, `/usr/bin/master-server` (contient `SET_HOTEND_FAN`).
- `/usr/data/printer_data/config/printer.cfg`, `box.cfg`, `gcode_macro.cfg`, `k1-control-owned-start-print-v2.cfg` (md5 `3ca58a94014711baab93702d50dab0c7`), `k1-control-probe-temp-guard-v1.cfg`, `kctrl_slot_map.py`, `kctrl_wait.py`.
- `/usr/data/creality/userdata/box/tn_data.json`, `material_database.json`, `/usr/data/creality/userdata/config/z_pos.json`, `print_file_name.json`, `current_work_info.json`.
- `/usr/data/printer_data/gcodes/DRAWER4U_4x2x4 LU - Topped Rail - MultiBin Shell_PLA_4h34m.gcode` (lignes 264, 275, en-tête 201560-201820).
- Dépôt : `STATE.md`, `docs/67…`, `docs/68…`, `packages/k1-control-v1/owned-start-print-v2/*`, `packages/k1-control-v1/cfs-zone-z-guard-v1/*`, `tests/test_kctrl_zone_guard_v1.py`, pytest 10/09 01:00.

Klipper officiel :

- Config_Reference — `position_min` : https://www.klipper3d.org/Config_Reference.html
- Command_Templates — évaluation complète avant exécution : https://www.klipper3d.org/Command_Templates.html
- G-Codes — `SET_GCODE_OFFSET`, `SET_FILAMENT_SENSOR` : https://www.klipper3d.org/G-Codes.html
- Status_Reference — `toolhead.position`, `gcode_move.homing_origin` : https://www.klipper3d.org/Status_Reference.html
- `klippy/toolhead.py` (`manual_move` → `move` → `check_move`, `G4` → `dwell`) : https://raw.githubusercontent.com/Klipper3d/klipper/master/klippy/toolhead.py
- `klippy/kinematics/corexy.py` : https://raw.githubusercontent.com/Klipper3d/klipper/master/klippy/kinematics/corexy.py
- `klippy/configfile.py` (`strict=False`, dernière section gagne) : https://raw.githubusercontent.com/Klipper3d/klipper/master/klippy/configfile.py
- Source Creality publiée (1.3.x, sans `gcode_position_max`) : https://github.com/CrealityOfficial/K1_Series_Klipper

Creality / CFS (rétro-ingénierie et communauté ; aucune page wiki Creality n'a pu être lue, corps vide) :

- FrederickAlt, docs du module `box_wrapper` (flux de changement, persistance `tn_data.json`, `last_cmd`, `z_down`/`z_restore`, capteur de coupe) : https://github.com/FrederickAlt/CREALITY-K1-AND-K1-MAX-CFS-RETRUDE-BEFORE-CUT-MOD/tree/master/docs
- HelixScreen, `CREALITY_CFS_INTERNALS.md` (`BOX_*` K1, `BOX_MODIFY_TN`, primitives muettes en reprise) : https://raw.githubusercontent.com/prestonbrown/helixscreen/main/docs/devel/CREALITY_CFS_INTERNALS.md
- gitstonelabs, codes d'erreur (`key841` coupe) : https://raw.githubusercontent.com/gitstonelabs/creality-cfs-klipper/main/docs/protocol.md
- `printer.cfg` / `box.cfg` d'un K1 Max 2.3.5.34 (`gcode_position_max: 295`, `safe_pos_y: 291.5`) : https://github.com/crazyslicster/SLICK1MAX
- Profil Orca officiel `Creality K1 Max_CFS-C` (`START_PRINT` puis `T[initial_no_support_extruder]`) : https://raw.githubusercontent.com/OrcaSlicer/OrcaSlicer/main/resources/profiles/Creality/machine/Creality%20K1%20Max_CFS-C%200.4%20nozzle.json
- Profil filament officiel `CR-PLA @K1 Max_CFS-C` (18 mm³/s) : https://raw.githubusercontent.com/OrcaSlicer/OrcaSlicer/main/resources/profiles/Creality/filament/CR-PLA%20%40K1%20Max_CFS-C-all.json
- Ligne d'amorce stock (`custom_macro.py`, version 1.3.x : X 0,1/0,4, F3000, E10) : https://raw.githubusercontent.com/fmillion-mnsu/creality-k1-script-mods/main/custom_macro.py
- Forum Creality — erreur de coupe TC2841, débris et réglage `cut_pos` : https://forum.creality.com/t/k1-max-cfs-tc2841-and-other-issues/42987 et https://forum.creality.com/t/k1max-cfs-upgrade-cutter-issue/39088
- Forum Creality — tête accrochée par la goulotte : https://forum.creality.com/t/k1-max-cfs-chute/40736
- Forum Creality — ligne d'amorce sans filament / ordre chargement-amorce en 2.3.5.34 : https://forum.creality.com/t/after-cfs-update-no-purge-line-anymore/37467
- Forum Creality — CX2585, coordonnées Y hors plage après kit CFS : https://forum.creality.com/t/y-axis-print-coordinates-out-of-range-cx2585-error-after-cfs-upgrade-k1/39277
- Happy-Hare #777 — `T0 already registered` par le module box : https://github.com/moggieuk/Happy-Hare/issues/777
- KAMP `Line_Purge.cfg` — vitesse d'amorce dérivée du débit : https://raw.githubusercontent.com/kyleisah/Klipper-Adaptive-Meshing-Purging/main/Configuration/Line_Purge.cfg
