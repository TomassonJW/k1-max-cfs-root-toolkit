# 104 - Poussée à froid du 31 octobre : garde en service, fin V5 prête (ADR-076), récidive du 1er novembre

## Incident

Heures de Paris, lues dans le journal Klipper de la K1.

| Heure | Fait |
|---|---|
| 19:00:56 | capteur de tête : fin de T1B, bobine réellement vide ; pause |
| 19:01:01 | relais stock `T1B -> T1A`, chargement de T1A |
| 19:02:18 | premier `FILAMENT_ERR[0x50]` sur T1A, bobine pleine ; répété toutes les 4 s environ jusqu'à la fin |
| 19:04:31 | reprise ; rechargement T1A de K1 Control réussi, tête chargée |
| 19:07:32 | fin du fichier, la fin V4 démarre |
| 19:07:36 | `key839` sur la case A du CFS 1, puis « extrude all material, last_cmd: T1A » |
| 19:07:42 | coupe confirmée ; fin V4 en échec (`firmware_reported_error`), chauffes coupées |
| 19:08:17 à 19:15:44 | douze cycles de la routine stock, environ toutes les 40 s, tête au bac (Y305, Z 53,94) |
| 19:16:12 | arrêt d'urgence de Thomas |

Pendant la boucle, la buse est descendue de 159 à 36 °C. Le PTFE est sorti de
son raccord et le filament est resté pris dans la tête. Le soir même, Thomas
présent, la tête a été vidée et T1A rembobinée ; il n'a trouvé aucun morceau
cassé ni coincé.

## Cause

1. Une erreur filament du CFS sur T1A, bobine pleine, avec l'auto-remplacement
   actif.
2. Pendant la coupe de fin, `key839` a lancé la routine stock ; la fin V4 s'est
   arrêtée et a coupé la chauffe, sans pouvoir arrêter cette routine.
3. Creality a commenté le refus d'extrusion à froid de Klipper
   (`kinematics/extruder.py`, lignes 234-237 de `check_move`) : rien n'a refusé
   les poussées.

Il fallait les trois. La garde coupe le troisième maillon, la fin V5 le
deuxième. Le premier tient au matériel (voir « Inconnues »).

## Garde à froid, en service

`packages/k1-control-v1/cold-push-guard-v1/` remplace `kctrl_purge_guard.py` ;
la partie bac est inchangée, le candidat ne fait qu'ajouter des lignes. Posée
le 31 octobre 2026 à 23:46, K1 au repos : l'installateur a exigé deux lectures
identiques juste avant l'arrêt de Klipper (rien n'imprime, ne chauffe ni ne
bouge, CFS connecté, fin et départ au repos).

Reçus, hors Git, dans `inventory/raw/20261031-cold-push-guard-v1/` :

- 23:43 `PREFLIGHT_OK`, 23 fichiers épinglés identiques ;
- 23:46 `INSTALLED_IDLE_OK`, révision `cold-push-guard-v1` lue sur le socket
  Klipper, 0 traceback ;
- 23:46 `VALIDATED_IDLE_OK` indépendant, aucun refus compté ;
- 23:47 `PROBE_REFUSED_OK` : une poussée de 0,5 mm sur la tête vide, buse à
  24 °C sans consigne, refusée ; position E inchangée, un seul refus compté.

Thomas a ensuite redémarré la K1 ; la garde a été relue active après ce
redémarrage. L'impression de nuit est partie à 00:45 avec elle, sur la fin V4.

Sauvegarde : `/usr/data/k1-control-v1/backups/cold-push-guard-v1`. Retour
arrière au repos seulement, après celui de la fin V5. Ne rejouer ni la pose ni
la sonde.

## Nuit du 1er novembre : même chaîne, arrêtée au début de la poussée

L'impression de nuit s'est terminée normalement. Sa fin a reproduit la chaîne
du 31 octobre, buse chaude cette fois. Heures de Paris, journal Klipper de la
K1 :

| Heure | Fait |
|---|---|
| 00:49:08 | erreur filament sur T1A en fin de chargement, `filament_useup` à 1 |
| 07:13:50 | interrogation CFS en impression : `FILAMENT_ERR`, rien de lancé |
| 07:13:52 | fin du fichier, la fin V4 démarre |
| 07:13:54 | interrogation suivante : `key839` sur la case A du CFS 1, puis « extrude all material, last_cmd: T1A », consigne buse 195 °C |
| 07:13:57 | coupe confirmée ; fin V4 en échec (`firmware_reported_error`), sans rembobinage |
| 07:14:06 | garde du bac : plateau déjà bas (Z 56,95), rien à descendre ; tête vers le bac (X185,5 Y305) |
| 07:14:08 | poussée stock de 80 mm à 2,33 mm/s lancée ; arrêt d'urgence de la surveillance locale |

Le relevé du mouvement au moment de l'arrêt montre moins de 0,2 mm poussés sur
les 80 mm prévus. La garde à froid n'avait pas à refuser : la buse était à
194 °C. Klipper a quitté seul à 07:14:14 sur une exception TMC Creality, comme
au document 88 ; rien n'a été redémarré. À 07:39, la K1 n'est pas rallumée.

État physique laissé : filament coupé dans la tête, pas rembobiné, partie haute
dans le tube ; tête au-dessus du bac, plateau à 57 mm ; chauffes coupées ; un
peu de matière a pu couler. La caméra était dans le noir.

Preuves, hors Git, dans `inventory/raw/20261101-night-end-watch/` de la copie
principale du dépôt : script et journal de la surveillance, extraits du
journal Klipper des deux soirs, empreintes `SHA256SUMS`. Les extraits portent
des identifiants CFS : jamais à publier.

Ce que la nuit apprend :

- `key839` ne vient pas de la coupe : il tombe à la première interrogation du
  CFS après la fin du fichier (3,8 s après le 31 octobre, 1,5 s cette nuit).
  Pendant l'impression, la même interrogation rendait `FILAMENT_ERR` sans rien
  lancer. Ce qui le déclenche, la fin du fichier ou la mise hors service du
  capteur de tête par la fin V4, ne se distingue pas dans le journal.
- La fin V5 coupe l'auto-remplacement dès la fin du fichier, avant de mettre le
  capteur hors service : environ une seconde avant l'interrogation de 07:13:54,
  trois secondes le 31 octobre. Probable, pas prouvé : l'interrogation revient
  toutes les 4,1 à 4,8 s ; si c'est la fin du fichier qui déclenche, une fin
  qui tombe juste avant une interrogation peut arriver trop tard (environ une
  fois sur neuf, estimation) ; et aucun journal ne montre encore `FILAMENT_ERR`
  avec l'auto-remplacement à 0.
- La correction à la source reste la fausse erreur de T1A : les deux fins
  d'impression sur T1A depuis son apparition ont lancé la routine.

## Matin du 1er novembre : retrait normal de T1A à chaud

Thomas présent. Heures de Paris, reçus des commandes et journal Klipper de la
K1 :

| Heure | Fait |
|---|---|
| 08:36 | K1 rallumée par Thomas |
| 08:47:29-45 | rembobinage de T1A à froid, axes non référencés : refusé après 13,5 s (`key849`, « failed to exit connections »), sortie A toujours occupée ; erreur de méthode, la tête n'avait pas rétracté le filament à chaud |
| 09:07 | CFS 1 remis au repos (IDLE, arrêt moteur), `G28 X Y`, `BED_MESH_CLEAR` ; Z non référencé |
| 09:17-09:18 | buse à 220 °C ; `BOX_CUT_MATERIAL` : capteur de coupe déclenché puis relâché, tête à Y291,5 |
| 09:19 | rétraction de la tête `E-20` puis `E-15` ; rembobinage refusé en 24 ms (`RETRUDE_ERR4`), capteur de bobine A lu vide |
| 09:20:44 | buse ramenée à 150 °C |
| 09:27:07-21 | capteur de bobine A relu présent ; rembobinage réussi en 13,5 s, sortie A libre, capteur de tête libre |
| 09:33 | nettoyage de la buse confirmé par Thomas ; 09:35:38, chauffes coupées, cibles relues à zéro deux fois |

À 09:41:39, la K1 est au repos : `standby`, cibles zéro, XY référencés, Z non
référencé, tête à X38 Y291,5, `t_command` vide, `filament_useup` et
`auto_refill` à 1. Les seules commandes de l'extrudeur sont les deux
rétractions de 09:19.

Ce que la matinée apprend :

- Un rembobinage ne vient qu'après la procédure normale : chauffe, coupe au
  cutter, rétraction de la tête à chaud, puis `BOX_RETRUDE_PROCESS`. À froid,
  la tête tient encore le filament et le CFS refuse (`key849`).
- Un `RETRUDE_ERR4` immédiat (24 ms, rien ne tourne) veut dire que le capteur
  de bobine de la case lit vide : attendre qu'il relise présent, puis relancer
  le seul rembobinage, sans rechauffer.
- Le capteur de bobine de la case A a lu vide à 09:19 puis présent à 09:27,
  bobine pleine : nouvel indice contre ce capteur (section « Inconnues »).

Preuves, hors Git, dans `inventory/raw/20261101-t1a-hot-unload/` de la copie
principale du dépôt : reçus des commandes, extraits du journal Klipper, trois
images de la caméra, relevé des macros, empreintes `SHA256SUMS`. Les reçus
portent des identifiants CFS : jamais à publier.

## Fin V5, prête, pas posée

`packages/k1-control-v1/end-no-stock-flush-v5/` remplace `kctrl_end.py`
(`cancel-retained-v4` vers `end-no-stock-flush-v5`). Elle coupe
l'auto-remplacement CFS avant toute coupe, le relit avant chaque effet et le
remet après une fin complète ou au départ suivant (ADR-076).

Pose au repos revérifié, Thomas présent, préflight d'abord. L'installateur
exige la garde à froid en service, épingle 23 fichiers (dont la garde
`8c637cc4…`), sauvegarde, redémarre Klipper, relit la révision sur le socket
et rend la valeur d'`auto_refill` lue. Son retour arrière passe avant celui de
la garde : après lui, plus rien ne remet l'auto-remplacement au départ, et le
reçu dit la valeur lue après le redémarrage.

## Preuves

Tests ciblés, tous verts le 1er novembre à 03:30 :

| Fichier | Tests |
|---|---|
| `tests/test_kctrl_cold_push_guard.py` | 18 |
| `tests/test_cold_push_guard_install.py` | 50 |
| `tests/test_kctrl_end_no_stock_flush_v5.py` | 111, dont les 85 de la V4 rejoués |
| `tests/test_end_no_stock_flush_v5_install.py` | 62 |

Mutants de la V5 : chaque protection retirée à son tour fait échouer les
nouveaux tests.

| Protection retirée | Tests en échec |
|---|---|
| V4 à la place de la V5 | 26 |
| relecture avant chaque effet | 4 |
| `key839` nommé | 5 |
| remise au départ | 4 |
| coupure avant la coupe | 12 |
| deux lectures au lieu d'une | 1 |
| preuve de la remise | 5 |

Suite complète : 2422 verts, 17 échecs et 53 erreurs. Ces 70 cas sont
identiques sur un export propre de la branche sans les fichiers V5 : ils
viennent de captures ignorées absentes du poste, sans lien avec ces paquets.

## Console

Garde : « K1 Control: poussee de filament refusee, buse froide (24 C, minimum
170 C) sans chauffe demandee. » La commande refusée n'a rien poussé.

Fin V5, une fois posée :

- fin complète : « K1 Control: fin terminee, tete vide et chauffes coupees » ;
- fin en échec : « K1 Control: fin incomplete (raison) ; auto-remplacement CFS
  laisse coupe, retabli au prochain depart » ; le départ reste bloqué jusqu'au
  redémarrage, comme avant ;
- départ refusé : « K1 Control: auto-remplacement CFS non retabli, depart
  refuse ». Un redémarrage de Klipper le remet.

## Inconnues

- Comportement stock sur `FILAMENT_ERR` avec l'auto-remplacement à 0 : connu
  par des notes tierces seulement.
- Déclencheur exact de `key839` : fin du fichier ou capteur de tête mis hors
  service par la fin (section « Nuit du 1er novembre »).
- Effet d'une poussée refusée sur le moteur du CFS pendant une routine stock.
- Cause de la fausse erreur sur T1A. Capteur de la case A suspecté : après
  extinction, Thomas a dû manipuler la bobine pour que la LED se rallume ; le
  1er novembre, il a lu vide à 09:19 puis présent à 09:27, bobine pleine.
  Échanger T1A avec une autre case avant de démonter le CFS.
- `filament_useup` vaut 1 depuis le 31 octobre à 18:56, même après extinction ;
  encore 1 à 00:53, à 07:13 et à 09:41 après le rembobinage. Rôle exact et
  moyen de le remettre à 0 inconnus.
- `box.t_command` valait `T0` pendant l'impression de nuit ; il est vide au
  repos à 09:27 et à 09:41. Les deux installateurs exigent qu'il soit vide au
  repos : s'il revient à `T0` après une fin, le préflight V5 refusera
  (`cfs_command_present`).
- Écritures sur la flash de `BOX_ENABLE_AUTO_REFILL` : non mesurées.
- Enregistrement de `BOX_ENABLE_AUTO_REFILL` au démarrage : sa méthode est dans
  la même classe stock que les primitives déjà exigées par la V4. S'il
  manquait, la V5 refuserait de démarrer et l'installateur reviendrait à la V4.
- Dérive des fichiers épinglés depuis le 31 octobre : le préflight la montrera.

## Correction d'une lecture fausse

`filament_sensor` (`!PC15`, carte mère) lit « présent » dans toutes les
captures depuis le 21 août, chemin vide compris : avec le CFS, il ne renseigne
sur rien. Le module CFS lit `filament_sensor_2`, le capteur de tête. Les
documents qui concluent sur PC15 (ADR-044, ADR-049, ADR-053, document 26)
sont à relire avec cette correction.

## Suite

1. Fait le 1er novembre : rallumage à 08:36, retrait normal de T1A à chaud et
   nettoyage de la buse de 09:07 à 09:35 (section « Matin du 1er novembre »).
2. Échange de cases pour T1A, puis vérification du capteur si l'erreur suit la
   case. Lire `box.filament_useup` avant tout geste filament.
3. Pose de la fin V5 au repos revérifié, Thomas présent, préflight d'abord ;
   surveillance locale de la première fin sous V5 par
   `packages/k1-control-v1/end-watch-v1/watch_end.py`, essai à blanc d'abord
   (README du paquet).
