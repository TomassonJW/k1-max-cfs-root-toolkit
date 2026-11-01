# 104 - Poussée à froid du 31 octobre : garde en service, fin V5 prête (ADR-076)

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
- Effet d'une poussée refusée sur le moteur du CFS pendant une routine stock.
- Cause de la fausse erreur sur T1A. Capteur de la case A suspecté : après
  extinction, Thomas a dû manipuler la bobine pour que la LED se rallume.
  Échanger T1A avec une autre case avant de démonter le CFS.
- `filament_useup` vaut 1 depuis 18:56, même après extinction ; rôle exact
  inconnu.
- `box.t_command` valait `T0` pendant l'impression de nuit ; les deux
  installateurs exigent qu'il soit vide au repos. S'il le reste après la fin,
  le préflight V5 refusera (`cfs_command_present`).
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

1. Fin de l'impression de nuit : surveillance locale, arrêt d'urgence
   seulement si l'extrudeur pousse après la fin.
2. Pose de la fin V5 au repos revérifié, Thomas présent, préflight d'abord.
3. Échange de cases pour T1A, puis vérification du capteur si l'erreur suit la
   case.
