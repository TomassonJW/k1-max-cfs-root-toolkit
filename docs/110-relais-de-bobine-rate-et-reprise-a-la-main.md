# 110 - Relais de bobine raté en pleine impression, reprise à la main

Date : 15 novembre 2026. Impression mono-filament `_events_places_PLA_3h16m`
(PLA noir, 200 °C, plateau 55 °C), lancée vers 11:58 sur T1C. Conventions des
documents 70, 105 et 106 : **[FAIT]** lu dans un journal ou un état, horodaté ;
**[HYPOTHÈSE]** cohérent avec les faits, non démontré ; **[INCONNU]** non
observé.

## 1. Ce qui s'est passé

| Heure K1 | Fait |
| --- | --- |
| 13:31:18 | CFS 1 : `FILAMENT_ERR[0x50]`, masque `connections` de 4 à 0. Vraie fin de la bobine C. L'impression continue sur la queue du filament. |
| 13:39:01 | Capteur de tête vide : pause à la position 3721644 du fichier (X235,225 Y141,302 Z3,8, couche 38), plateau descendu de 46,079 mm. La routine de fin de filament pousse 30 mm. |
| 13:39:10 | Courant extrudeur baissé à 0,28 A par la pause stock. L'auto-remplacement choisit T1B (`T1A -> T1B`, `T1C -> T1B`). |
| 13:39:38 à 13:40:16 | Chargement stock de T1B à 195 °C : étape 7 réussie, étape 8 « tampon toujours plein » à chaque lecture, `EXTRUDE_ERR9[0xe]`. |
| 13:40:35 à 13:40:49 | Reprise stock `auto_retry_extruder_gear` : coupe, rembobinage, recul de 20 mm. |
| 13:40:56 à 13:42:29 | Deuxième chargement : `EXTRUDE_ERR8[0xc]` avec le capteur de tête vrai, délai dépassé, `key836` `[1, "B"]`. Tête au parc X210 Y291,5. |
| 13:42:29 | `kctrl_tool_change: reload T1A ended, error=False, head=True, paused=True`. |

[FAIT] Après l'échec : impression en pause, filament de B dans la tête,
`box.T1.mode` = `"0"`, courant extrudeur 0,28 A, erreur `EXTRUDE_ERR8` répétée
toutes les 4 s, `box.T1.filament` resté à `"C"`, `tn_cur_tnn` = `"T1A"`,
capteur de tête `filament_sensor_2` désactivé.

[HYPOTHÈSE] Tout le relais stock a tourné avec l'extrudeur à 0,28 A, valeur
laissée par la pause. Courant remis à 0,56 A et CFS en mode impression, la tête
a avalé le filament de B dès la première poussée (section 3).

## 2. Pourquoi « Reprendre » ne pouvait pas marcher

[FAIT] Lecture de la macro stock `RESUME` : elle attend la température, ne
recule en Y que si la tête est au-delà de Y291,5, puis remonte le plateau
(`G1 Z-44` ce jour), puis `RESUME_BASE`, qui rejoue le chargement nommé dans
`tn_cur_tnn`.

[FAIT] À 14:19, tête au parc X210 Y291,5, la garde `kctrl_purge_guard` était
verrouillée (`bin_latched: true`) : le chargement stock s'était fait au bac et
la tête n'était jamais repassée sous Y280. Verrouillée, la garde refuse toute
remontée du plateau sous 30 mm et coupe les chauffes. « Reprendre » aurait donc
été refusé, buse et plateau coupés. Non provoqué : déduit de la règle de la
garde, et Thomas a été prévenu de ne pas presser le bouton.

[FAIT] Même sans la garde, le chargement rejoué repasse par la coupe et par le
chargement stock qui venait de rater deux fois.

## 3. Reprise réalisée, sans redémarrage

Demande de Thomas : relancer proprement, sans redémarrer.

| Heure K1 | Geste | Preuve |
| --- | --- | --- |
| 14:2x | `BOX_ERROR_CLEAR`, `RESTORE_E_CURRENT`, `BOX_SET_BOX_MODE ADDR=1 MODE=PRINT NUM=B` | état CFS `OK`, courant relu 0,56 A, `box.T1.mode` = 2 |
| 14:26 | `tn_cur_tnn` vidé dans `print_file_name.json`, copie gardée à côté | fichier relu |
| 14:27 | sortie vers Y273 puis entrée au bac X185,5 Y305, plateau resté bas ; buse 215 °C | garde : rien refusé |
| 14:27 à 14:29 | 4 poussées de 20 mm à F150, `BOX_GET_BUFFER_STATE ADDR=1` après chacune | tampon `full` avant, `middle` après chaque poussée |
| 14:34:35 | `BOX_MODIFY_TN_DATA ADDR=1 PART=filament DATA=B` | `box.T1.filament` = `"B"` |
| 14:35 | buse 200 °C, 15 mm de plus, recul 0,8 mm, 3 passes de décrochage, sortie Y273 | tampon `middle`, garde déverrouillée, 0 refus |
| 14:36 | retour X235,225 Y141,302, Z5,8 puis Z3,8, ventilateurs du fichier, avance de pression | 11 contrôles vrais avant de continuer |
| 14:36:23 | amorce 0,8 mm, F9840, `SAVE_GCODE_STATE NAME=PAUSE_STATE`, capteur de tête réactivé, un seul `RESUME_BASE` | journal : `resume tn_cur_tnn[]` |

[FAIT] 14:36:46 : `printing`, position 3744716. 14:39:33 : position 3892257,
44,6 %, CFS `OK`, aucune pause, aucune erreur. 14:41:33 : toujours
`printing`. Pause totale : 57 min. Purge totale : 95 mm.

[FAIT] `BOX_MODIFY_TN_DATA ADDR=<n> PART=filament DATA=<case>` change seulement
la mémoire de route du module CFS, sans trame ni moteur (document 96). Le
constructeur l'emploie lui-même avec `PART=state`. Sans cette écriture, la fin
`end-no-stock-flush-v5` aurait lu la route T1C et rembobiné une case vide.

[FAIT] Qualité du dépôt au point de reprise : « niquel », dit par Thomas.
Retrait de T1B à la fin de l'impression : réussi (16:15).

## 4. Comparaison avec le 12 novembre (document 106)

| | 12 novembre | 15 novembre |
| --- | --- | --- |
| Déclencheur | fausse fin de T1B, bobine pleine | vraie fin de T1C |
| Routine stock | « extrude all », 3000 mm au bac | relais vers T1B, deux chargements ratés |
| État laissé | CFS au repos | CFS au repos, 0,28 A, route fausse, capteur de tête coupé |
| Reprise | à la main, document 106 section 3 | la même, plus la route et le capteur |

Les deux fois, la pièce a été sauvée par une IA et une console : famille D et
famille E du document 109, toujours ouvertes.

## 5. Ce que la tranche 2 doit faire à la place

1. Avant un relais : courant extrudeur remis à sa valeur de marche, relue.
2. Chargement raté avec filament en tête : même reprise qu'au départ
   (mode impression, poussées de 20 mm au bac, tampon lu vidé), pas de
   deuxième coupe.
3. Reprise prouvée : route écrite (`update_filament_pos`), `tn_cur_tnn` vidé,
   capteur de tête réactivé, sortie du bac à hauteur constante, puis retour au
   point d'arrêt et reprise du fichier.
4. Reprise non prouvée : vraie pause, une phrase claire, tête hors du bac.
5. « Reprendre » pressé garde verrouillée (tête au bac ou au parc) : sortie
   vers Y273 d'abord, jamais de remontée du plateau avant.
