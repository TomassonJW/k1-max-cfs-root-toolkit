# 81 — Fin d'impression en boucle (« extrude all material » sur `T1A`), plantage de Klipper causé par notre lecture du journal, retrait de la tête repris par nos soins

Date : 2026-09-15. Journal de Klipper du 14 et du 15 septembre, lu en fenêtre
bornée et en basse priorité, analysé hors de la machine ; les extraits n'entrent
pas dans le dépôt. Correctifs écrits, testés hors machine, et posés machine au
repos à 14:03 (section 6).

Conventions, comme les documents 70 et 80 : **[FAIT]** lu dans un journal ou
un fichier, horodaté ; **[HYPOTHÈSE]** cohérent avec les faits, non démontré ;
**[INCONNU]** non observable ou pas encore observé.

## 0. La question

Thomas, le 15 septembre : la fin de l'impression de la nuit a poussé du
filament en boucle au lieu de le retirer, la Pause n'a rien fait, Klipper a
planté, et les deux retraits suivants depuis l'écran ont échoué. Puis : « le
dernier rétrude effectué via Mainsail a amené la tête au niveau de la purge,
pas du cutter. Comportement chelou ? » Et l'ordre : corriger les gros bugs,
avancer sur notre version, adaptée à la K1 Max, avec les bonnes séquences.

## 1. Réponse courte

1. **La boucle est une branche du module CFS de Creality, hors de notre
   code.** Sa fin d'impression (`BOX_END`, première commande de la fin stock
   `END_PRINT_NO_M84`) a deux comportements. Le 14 à 22:53 : coupe,
   rembobinage, `Exiting` 49 s après `box_end`. Le 15 à 12:03 : « extrude all
   material, last_cmd: T1A », puis 80 mm de `T1A` poussés toutes les 40 s,
   25 fois, environ 2 m, jusqu'au plantage. [FAIT] Ce qui choisit la branche
   est dans le module compilé. [INCONNU] L'hypothèse : la bobine `T1A` était
   tenue pour finie depuis l'alerte de tension de 03:45:58 (document 80), et
   « tout vider » une bobine attachée ne finit jamais. [HYPOTHÈSE]
2. **La Pause n'agit pas pendant une macro de fin** : la macro tient la file
   G-code, la Pause attend derrière elle. [FAIT] Seul l'arrêt d'urgence, ou
   l'annulation depuis l'écran, interrompt.
3. **Le plantage de 12:20 est le nôtre.** À 12:19:44, un `tail -n 600000` sur
   le journal de 490 Mo a fait tomber la mémoire disponible de 94,5 à 9,8 Mo ;
   journal muet 9 s, buse lue à 0 °C, arrêt. [FAIT]
4. **Le retrait manuel échoue sans nom d'emplacement.** Après un redémarrage,
   le module ne sait plus quel filament est à la tête (`last_tnn: None`) :
   `BOX_RETRUDE_MATERIAL` rend la main en 4 ms sans rien faire (13:02).
   `BOX_RETRUDE_MATERIAL_WITH_TNN TNN=T1A` a rembobiné `T1A` en 20 s à 13:23.
   [FAIT]
5. **La tête à la purge après un rembobinage est la séquence stock.** Le
   retrait de l'écran (`BOX_QUIT_MATERIAL`) enchaîne `BOX_ERROR_CLEAR`,
   `BOX_CHECK_MATERIAL`, `BOX_CUT_MATERIAL`, `BOX_RETRUDE_MATERIAL`, puis
   `BOX_GO_TO_BOX_EXTRUDE_POS`, la position de purge (X185 Y305,5). La
   position du cutter n'est visitée que pendant la coupe. [FAIT] Rien de
   chelou.
6. **Correctifs posés** (section 6) : la fin d'impression et l'annulation
   vident la tête par nos soins avant la fin stock, coupe puis rembobinage de
   l'emplacement nommé (ADR-067) ; toute lecture du journal est bornée et un
   test l'impose ; l'audit en direct alerte sur la boucle de fin, la Pause
   inutile, le journal muet et la mémoire basse. La garde du bus du document
   80 est posée à 17:52 (ADR-068).

## 2. Méthode

- Fenêtres de fin lues par `dd` sur le journal, 24 Mo au plus, lignes coupées,
  filtrées sur l'heure, hors dépôt. Rejeu des deux fins dans
  `scripts/audit-en-direct/audit_live.py` après ajout des alertes.
- Macros stock lues dans l'inventaire du 19 août
  (`targeted-sources.raw.txt`) : `END_PRINT`, `END_PRINT_NO_M84`,
  `BOX_QUIT_MATERIAL`, `BOX_LOAD_MATERIAL_WITH_MATERIAL`.
- Émulation locale de la lecture du fichier par Klipper (coupe des `#` et des
  ` ;` en ligne, puis chargement Jinja de chaque macro), après l'erreur de
  14:00 (section 6).

## 3. Ce que montre le journal

Fin normale, 14 septembre (`MultiColo_Cube_PLA_15m31s`) : [FAIT]

| Heure | Ligne |
| --- | --- |
| 22:53:32 | `box_end` |
| 22:54:05 | `filament_sensor false` : tête vide |
| 22:54:21 | `Exiting SD card print` (49 s) |

Fin en boucle, 15 septembre (`…Shell_PLA_8h16m`, sur `T1A`) : [FAIT]

| Heure | Ligne |
| --- | --- |
| 03:45:58 | tension du filament `T1A` signalée par le CFS 1 (document 80) |
| 12:03:16 | `box_end` |
| 12:03:17 | `cmd_485_send_data_with_response timeout, cmd = 10, data=b'\x02\x03\xff\n', timeout = 3600`, puis un cycle d'adressage du bus (`set slave addr`, `online check`, `loader check`) |
| 12:03:20 | `extrude all material, last_cmd: T1A` |
| 12:04:05 → 12:20:12 | 25 tours de ~40 s : `y_pos: 305.0, self.boxcfg.safe_pos_y: 291.5`, `filament_sensor true`, `Act_z is 155.775, no need to move down.` ; 80 mm par tour, ~2 000 mm |
| 12:18:00 | `Tn_data[filament_useup]: 1` |
| 12:19:07 | `webhooks: method:pause_resume/pause` : la Pause de Thomas, sans effet |
| 12:19:44 | notre `tail -n 600000 klippy.log` ; mémoire disponible 94,5 → 9,8 Mo |
| 12:19:44 → 12:19:53 | journal muet |
| 12:20:13 | `Transition to shutdown state: Unhandled exception during run` (buse lue à 0 °C, MCU « Missed scheduling », `key294`) |
| 12:36:09 | prêt après redémarrage |
| 12:49:32 | retrait depuis l'écran : coupe à 12:50:04, aucun `BOX_RETRUDE_MATERIAL` |
| 13:02:11 | second retrait : « Cut sensor not triggered », `key841`, `'NoneType' object has no attribute 'name'`, `macro_cut_err` ; `BOX_RETRUDE_MATERIAL` sans effet (4 ms, `last_tnn: None`) ; tête garée en X38 Y100 |
| 13:23 | `BOX_RETRUDE_MATERIAL_WITH_TNN TNN=T1A` (Thomas, Mainsail) : rembobiné en 20 s, tête à la purge |

Rejeu de ces deux fins dans l'audit après les alertes de la section 6 : [FAIT]

- 15 septembre : « ALERTE fin d'impression : extrude all material sur T1A » à
  12:03:20, tronçons 1 et 2 à 12:04:05 et 12:04:45, « box_end dure depuis
  151 s » à 12:05:47, puis tronçons 5, 10, 15, 20, 25 (2 000 mm à 12:20:12) ;
  « Pause demandée pendant box_end : sans effet » à 12:19:07.
- 14 septembre : « fin d'impression : box_end » à 22:53:32, « box_end ->
  Exiting en 49 s, 0 tronçon(s) » à 22:54:21, aucune alerte.

## 4. Ce que fait la fin stock, et ce qu'elle ne dit pas

`END_PRINT` stock = `END_PRINT_NO_M84` + `M84`. `END_PRINT_NO_M84` = `BOX_END`,
`BOX_END_PRINT`, `Qmode_exit`, `EXCLUDE_OBJECT_RESET`, `PRINT_PREPARE_CLEAR`,
`M220 S100`, `SET_VELOCITY_LIMIT …`, `TURN_OFF_HEATERS`, `M107 P1`, `M107 P2`,
`END_PRINT_POINT`, `WAIT_TEMP_START`, `BOX_GET_FIVE_WAY_STATE`. [FAIT] Donc :

- la buse est encore à sa température d'impression quand `BOX_END` commence ;
  les chauffes ne sont coupées qu'après ;
- `BOX_END` fait plus que vider la tête (remise des états du module) : on ne
  le remplace pas, on passe avant lui ;
- ce que fait `BOX_END` devant une tête déjà vide n'a pas encore été observé.
  [INCONNU] L'audit en direct le dira à la prochaine fin (section 6).

L'objet `box` publie `enable`, `filament`, `state`, `auto_refill`,
`filament_useup`, `same_material`, `T1`..`T4`, `cut_pos`, `t_command`,
`custom_command_result` ; aucun n'annonce la branche que prendra `BOX_END`.
[FAIT]

## 5. Hypothèses et inconnues

- [HYPOTHÈSE] La branche « extrude all material » est celle d'une bobine
  finie : le module pousse le bout de filament restant vers la buse au lieu de
  le rembobiner. `T1A` tenue pour finie depuis 03:45:58 (tension), la bobine
  étant encore là, le bout ne vient jamais ; `filament_useup` repasse à 1 à
  12:18:00 sans que la boucle s'arrête.
- [INCONNU] La condition exacte de cette branche, et si elle s'arrête seule.
- [INCONNU] Le lien entre le `timeout` du bus à 12:03:17 (`cmd = 10`, 3 600 s)
  et la branche prise trois secondes plus tard.
- [INCONNU] La boucle d'adressage du bus (`Error: no response` toutes les
  ~2 s) vue depuis 12:43 et après le redémarrage.
- [INCONNU] La cause de la coupe ratée de 13:02 (« Cut sensor not
  triggered ») : filament déjà coupé à 12:50, ou cutter intermittent
  (document 79).
- [INCONNU] Si l'arrêt d'urgence interrompt tout de suite la boucle sur ce
  firmware.

## 6. Correctifs et vérification

| # | Correctif | Où | Preuve |
| --- | --- | --- | --- |
| 1 | **La fin vide la tête elle-même** : `END_PRINT` et `CANCEL_PRINT` appellent `_KCTRL_UNLOAD` avant `END_PRINT_NO_M84` : buse à sa température d'impression (200 °C au moins), `BOX_ERROR_CLEAR`, `BOX_CUT_MATERIAL`, `BOX_RETRUDE_MATERIAL_WITH_TNN TNN=<emplacement>`, puis `_KCTRL_UNLOAD_CHECK` relit le capteur de tête. L'emplacement vient du dernier changement d'outil de notre enveloppe, sinon du départ (`START_PRINT.active_tool`, nouveau), sinon `TOOL=`. Sans CFS, tête déjà vide, axes non référencés ou emplacement inconnu : un message et la fin stock fait son retrait. Aucune des deux macros ne lève (ADR-067). | `packages/k1-control-v1/owned-start-print-v2/k1-control-owned-start-print-v2.cfg` | 21 tests, `tests/test_owned_end_unloads_the_head_v1.py` ; posé le 15 septembre à 14:03 (sauvegarde `.bak-20260915-adr067`), Klipper prêt à 14:04:02, les deux macros présentes. **Première fin réelle à observer.** |
| 2 | **Lectures du journal bornées** : fenêtre `dd bs=1048576 skip=…` de 32 Mo au repos (64 pour le bus), 3 Mo si `print_stats` vaut `printing` ou `paused`, `nice -n 19`, `cut -c1-W` avant tout `tail -n N` avec N × W ≤ 4 Mo. | `scripts/run-k1-control-cfs-read-only-audit-v1.ps1`, `packages/k1-control-v1/clean-and-reference-v1/capture_recent_cfs_history_read_only.ps1`, `scripts/audit-en-direct/purges.sh`, `scripts/audit-en-direct/bus.sh` (nouveau, pour `silences_cfs.py`) | 7 tests, `tests/test_lectures_journal_bornees_v1.py` : tout script du dépôt qui nomme `klippy.log` n'y touche que par `dd` borné, `wc -c`, `stat` ou `tail -n 0 -F`. |
| 3 | **Alertes de l'audit en direct** : « extrude all material » pendant `box_end` ; tronçons comptés ensuite (1, 2, puis tous les 5) ; `box_end` au-delà de 150 s ; Pause pendant `box_end` ; journal muet plus de 8 s alors que les `Stats` tombaient ; `memavail` sous 40 Mo ; `filament_useup` qui change. | `scripts/audit-en-direct/audit_live.py` | 7 tests, `tests/test_audit_live_alertes_v1.py` ; rejeu des fins du 14 et du 15 (section 3). |
| 4 | **Garde du bus** (document 80, remède 3) : enveloppe de `serial_485` qui retient 300 ms la question suivant une réponse finie par `F7`. Écrite, testée, **posée le 15 septembre à 17:52** (ADR-068, sauvegarde `serial_485.py.bak-20260915`), compteurs lisibles dans l'objet `serial_485 serial485`. | `packages/k1-control-v1/cfs-bus-guard-v1/serial_485.py` | 8 tests, `tests/test_cfs_bus_guard_v1.py` (faux transport) ; au repos, `kctrl_calls` monte de deux par seconde et `kctrl_seen` avec ; preuve décisive à la prochaine impression (`silences_cfs.py`). |

Incident de pose, 14:00 : Klipper en erreur au premier redémarrage, « EOL
while scanning string literal ». Cause : Klipper lit le fichier avec
`inline_comment_prefixes=(';', '#')` ; un ` ;` dans un message de
`_KCTRL_UNLOAD_CHECK` coupait la ligne et le modèle Jinja ne se chargeait
plus. Message corrigé, test ajouté (aucun ` ;` ni `#` dans un message),
seconde pose à 14:03, prêt à 14:04:02. [FAIT]

Essai à blanc du 15 septembre à 17:49, tête vide, machine au repos :
`_KCTRL_UNLOAD REASON=essai` répond « retrait (essai), capteur de tete deja
vide, rien a couper » (`last` = `vide`) et `_KCTRL_UNLOAD_CHECK TOOL=T1A
REASON=essai` « retrait (essai) de T1A fait, tete vide ». Les deux modèles se
rendent sur le Klipper réel ; aucun mouvement, aucune chauffe. [FAIT]

Vérification à la prochaine fin d'impression, avec `audit-live.sh` lancé
avant la fin : messages « K1 Control: retrait (fin) de Txx (…) : coupe, puis
rembobinage » puis « retrait (fin) de Txx fait, tete vide », puis
« fin d'impression : box_end » et « box_end -> Exiting en N s, 0 tronçon(s) »
sans alerte. Si `BOX_END` fait autre chose devant une tête vide, l'audit le
dira.

## Voir aussi

- ADR-067 — la fin d'impression vide la tête avant la fin stock
- ADR-068 — la garde du bus est posée
- ADR-066 — deux contraintes du rendu Jinja
- Document 80 — pauses `key831`, garde du bus
- Document 79 — audit des séquences de départ et de changement
