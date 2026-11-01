# 105 - Garde capteur CFS contredit : fin sûre sans le PC (ADR-077)

Date : 1er novembre 2026. Paquet
[`cfs-sensor-guard-v1`](../packages/k1-control-v1/cfs-sensor-guard-v1/README.md),
construit et testé hors imprimante, jamais posé. Ce travail n'a rien lu ni rien
écrit sur la K1.

Conventions, comme les documents 70, 80 et 81 : **[FAIT]** lu dans un journal
ou un fichier, horodaté ; **[HYPOTHÈSE]** cohérent avec les faits, non
démontré ; **[INCONNU]** non observable ou pas encore observé. S'y ajoute
**[SIMULATION]** : résultat d'un rejeu hors imprimante, sur faux Klipper et
lignes synthétiques.

## 1. Demande

Thomas veut « un garde fou intelligent qui repère qu'un capteur est foireux
[...] et permet de faire une fin adaptée », dans Klipper, sans le PC.

[FAIT] Trois fins ont mal tourné sur T1A. Chaque fois, le CFS signalait un
défaut de filament sur le slot qui imprimait normalement, tête chargée, puis la
routine stock « extrude all material, last_cmd: T1A » a poussé du filament
après la fin du fichier.

| Date | Fin | Poussées | Arrêt |
| --- | --- | --- | --- |
| 15 septembre | stock, boucle dans `BOX_END` | 80 mm toutes les 40 s, 25 fois de 12:04:05 à 12:20:12, environ 2 000 mm (document 81) | plantage de Klipper à 12:20:13, causé par notre lecture du journal |
| 31 octobre | V4, en échec à 19:07:42, chauffes coupées | douze cycles de 19:08:17 à 19:15:44 (document 104) | arrêt d'urgence de Thomas |
| 1er novembre | V4, en échec à 07:13:57 | 80 mm à 2,33 mm/s à 07:14:08 | surveillance PC (`end-watch-v1`), moins de 0,2 mm poussé |

Le document 104 décompose la chaîne :

1. erreur filament du CFS sur une bobine pleine, auto-remplacement actif ;
2. routine stock lancée pendant la coupe de fin, que la fin V4 ne pouvait pas
   arrêter ;
3. poussées jamais refusées, Creality ayant commenté le refus d'extrusion à
   froid de Klipper.

La garde à froid (ADR-076) coupe le maillon 3 quand la buse est froide, la fin
V5 coupe le maillon 2. La garde capteur agit sur le maillon 1 : elle coupe
l'auto-remplacement quand le capteur du slot se contredit. Elle arrête aussi
toute poussée après la fin, buse chaude comprise, comme la surveillance PC du
1er novembre, mais dans Klipper. Le faux défaut lui-même tient au matériel et
reste hors de sa portée.

## 2. Sources

[FAIT] Deux extraits bruts du journal de Klipper, gardés hors Git :

- le 31 octobre, lignes de 18:27:31 à 19:30:19 ;
- le 1er novembre, lignes de 07:07:08 à 07:14:14 ; l'extrait commence avec
  `FILAMENT_ERR` déjà présent.

Le 13 et le 15 septembre ne sont connus que par les documents 80 et 81 : aucun
journal brut de ces jours n'est disponible ici.

[FAIT] Événements que lit `parse()`, le lecteur de la garde, sur ces extraits.
Bits des masques : A = 1, B = 2, C = 4, D = 8.

| Événement | 31 octobre | 1er novembre |
| --- | --- | --- |
| réponse d'état OK (0x0), CFS 1 | 638, de 18:27:34 à 19:30:15 | aucune |
| réponse d'état OK, CFS 2 | 743, de 18:27:35 à 19:30:17 | 92, de 07:07:09 à 07:14:07 |
| réponse `FILAMENT_ERR` (0x50), CFS 1 | 93, de 18:56:06 à 19:10:24 | 95, de 07:07:08 à 07:14:07 |
| réponse 0x30, CFS 1 | 2, à 18:56:02 et 19:01:25 | 2, à 07:07:46 et 07:07:50 |
| ligne nommée T1B | 2, à 18:56:06 | aucune |
| ligne nommée T1A | 6, de 19:02:18 à 19:10:31 | 1, à 07:13:54 |
| tension | 1, à 18:56:07 | aucune |
| masque `connections`, CFS 1 | valeur 2 (B) 6 fois, de 18:56:07 à 18:56:34 ; valeur 0 à 18:56:39 et 19:01:06 | valeur 1 (A) 82 fois, de 07:07:10 à 07:14:03 |
| masque `material`, CFS 1 | valeur 9 (A et D) 55 fois, de 18:56:57 à 19:01:19 ; valeur 8 (D) 73 fois, de 19:01:26 à 19:19:17, dont 71 avant la fin du fichier à 19:07:32 | aucun |
| masques, CFS 2 | `connections` 0 et `material` 15 à 19:01:06 ; `material` 15 encore à 19:19:17 | aucun |
| ligne de queue `extrude = N` | 1, à 18:56:39 | aucune |

[FAIT] Les masques ne paraissent qu'après une erreur filament ou une tension :
aucun avant 18:56:07 le 31 octobre ; le 15 septembre, le premier suit la
tension de 03:45:58 (document 80). Aucune trame porteuse d'identifiant n'est
lue : `parse()` ne retient que les réponses d'état (commande 0xa, taille 7), les
lignes nommées, la tension, les masques et la ligne de queue.

Les rejeux des tests ne reprennent aucune ligne brute. Toutes les lignes CFS y
sont réécrites sans identifiant, aux heures des extraits ou des documents 80 et
81. Sont synthétiques en plus :

- les débits d'impression : 6,4 mm/s le 31 octobre, 4,4 mm/s le 1er novembre,
  4 mm/s le 15 septembre, 5 mm/s le 13 septembre et pour l'impression saine ;
- le 1er novembre, les réponses OK du CFS 1 de 06:30:00 à 07:07:04, avant le
  début de l'extrait ;
- le 13 septembre, les réponses `FILAMENT_ERR` de 12:31:43 à 12:33:39 ;
- le 15 septembre, l'arrêt des masques à 03:55:00, et les poussées stock
  placées après une fin K1 Control que la K1 n'avait pas ce jour-là.

## 3. Vraie fin de bobine ou capteur contredit

[FAIT] Le 31 octobre, la bobine de T1B s'est vraiment vidée. Premier
`FILAMENT_ERR` et ligne nommée T1B à 18:56:06, tension à 18:56:07, masque
`connections` à 2, B encore présent, jusqu'à 18:56:34, puis à 0 avec la ligne
de queue à 18:56:39 : la fin se prouve 33 s après le premier signal. Le capteur
de tête a vu du filament jusqu'à 19:00:56 (document 104), plus de 4 min après
cette preuve : le tube en contenait encore.

[FAIT] Le même soir, T1A imprimait une bobine pleine. Son masque `material` la
donnait absente 71 fois de 19:01:26 à la fin du fichier ; ses réponses
`FILAMENT_ERR` ont commencé à 19:02:18 (document 104). Aucun masque
`connections` ni aucune ligne de queue n'a suivi. Le masque `connections` à 0
de 19:01:06 tombe pendant le relais T1B -> T1A commencé à 19:01:01
(document 104), avant l'épisode de T1A : la garde ne compte un masque que s'il
suit le début de l'épisode.

[FAIT] Le 1er novembre, T1A imprimait aussi une bobine pleine : 95 réponses
`FILAMENT_ERR` de 07:07:08 à 07:14:07, et 82 masques `connections` à 1, A
présent, de 07:07:10 à 07:14:03.

[FAIT] Le 15 septembre (document 80) : `FILAMENT_ERR` et `tnn: T1A` à
03:45:58,664, tension à 03:45:58,719, puis masque `connections` à 1, A présent,
toutes les 5 s environ, 4 872 fois jusqu'à 10:47:28 au moins.

[FAIT] Le 13 septembre (document 80) : tension sur le CFS 1 à 12:31:43, masque
`connections` à 2 seize fois, puis à 0 à 12:33:04, puis `material` à 9 de
12:33:43 à 12:48:48. Le slot qui imprimait n'est pas établi. Si c'était T1B, la
fin se prouve à 12:33:04, à +81 s ; si c'était T1A, dès le premier masque, à
12:31:44, à +1 s. [INCONNU] Que ce soit une vraie fin : aucune trace de la tête
ne la confirme.

La garde en tire sa règle. Le masque `connections` sans le bit du slot, ou la
ligne de queue, prouvent une vraie fin. Le masque `material` seul ne prouve
rien : il donnait A absente pendant que T1A imprimait une bobine pleine. Le
capteur de tête ne départage rien non plus : il reste vrai tant que le tube
contient du filament.

Un épisode encore suspect après 180 s marque l'impression. Le délai de preuve
le plus long des cas lus vaut 81 s (13 septembre, si T1B imprimait) : 180 s
laissent une marge de 2,2. [HYPOTHÈSE] Une vraie fin se prouve toujours en
moins de 180 s. Si l'une d'elles restait plus longtemps sans preuve, la garde
couperait l'auto-remplacement et cette fin donnerait probablement une pause au
lieu d'un relais (section 7).

Les 400 mm imprimés pendant l'épisode exigent que l'impression avance vraiment :
une pause ou une tête arrêtée ne marquent pas. Ils ne départagent pas une vraie
fin d'un capteur faux. [INCONNU] La quantité qu'une vraie fin consomme avant sa
preuve : aucun journal lu ne donne la position E. Au-dessus de 2,2 mm/s en
moyenne, les 180 s décident ; en dessous, les 400 mm.

## 4. La garde

Module Klipper `kctrl_sensor_guard`, révision `cfs-sensor-guard-v1`, section
`[kctrl_sensor_guard]`, `enabled: False` par défaut. Activée, elle exige
`[kctrl_end]` activé (`end-no-stock-flush-v5`), sinon Klipper refuse de
démarrer : la fin stock pousse après le fichier, et la règle de fin arrêterait
chaque impression.

### Pendant l'impression

Un épisode s'ouvre sur un slot :

- sur une réponse `FILAMENT_ERR` du CFS de la route engagée ;
- sur une ligne `recode_err: filament_err` ou `error: filament_err` qui cite le
  slot, même hors route ;
- sur une tension du CFS de la route engagée ;
- quand le masque `material` de ce CFS perd le bit du slot.

La marque tombe une seule fois par impression : l'épisode du slot engagé reste
suspect après 180 s et 400 mm imprimés pendant l'épisode, tête chargée
(`filament_sensor_2`), et la garde n'est pas aveugle. La garde envoie alors
`BOX_ENABLE_AUTO_REFILL ENABLE=0` sous le verrou G-code et exige deux lectures
fraîches à 0 en moins de 3 s. La console nomme le slot, la durée, les
millimètres et l'issue de la coupe. Si l'auto-remplacement revient à 1 avant la
fin, la garde le recoupe, au plus toutes les 10 s. Après la fin du fichier,
l'auto-remplacement appartient à la fin K1 Control.

Les millimètres se comptent en `printing` seulement, sur la position E prévue
de l'extrudeur, à marée haute : une rétraction et sa reprise comptent une fois.
Un tic, une seconde, compte au plus 100 mm ; une baisse de E de plus de 100 mm,
comme une remise à zéro, repart de la nouvelle position. Un épisode se ferme après deux réponses OK de suite, sans
signalement depuis 15 s, sans masque `connections` depuis 15 s et sans slot
absent du masque `material`.

La garde se dit aveugle, une fois par impression, quand le CFS de la route ne
répond plus depuis 60 s pendant l'impression, ou quand le niveau du logger
racine passe au-dessus de INFO. Aveugle, elle ne marque pas.

### Après la fin du fichier

La fenêtre de fin s'ouvre sur `complete`, `cancelled`, `error`, `standby`, ou
`paused` sans fichier ouvert. Elle dure 15 min comptées depuis la sortie de la
fin K1 Control de ses phases actives. Le crochet se pose sur
`extruder.check_move`, que `toolhead.move` appelle avant de mettre le mouvement
en file.

Une poussée nette de plus de 1 mm hors des phases `cutting`, `rewinding` et
`finalizing` de `kctrl_end` demande l'arrêt de Klipper et lève l'erreur
`K1 Control: poussee de filament apres la fin, arret d'urgence` : rien de cette
poussée ne sort. Rien n'est permis en `waiting` ni en `heating`, et une
rétraction ne donne pas de crédit à une poussée suivante. L'arrêt ne dépend pas
de la marque : la fenêtre vaut pour toute impression, annulation comprise.
`KCTRL_SENSOR_GUARD_RELEASE` lève la fenêtre avant une poussée à la main.

### Au départ suivant

`START_PRINT` remet l'auto-remplacement coupé par la garde, prouvé par deux
lectures à 1, avant le départ stock ; sinon il refuse le départ. Une fin K1
Control encore en cours refuse aussi le départ.

### Lecture du journal

Le module CFS stock écrit ses trames au niveau INFO par le logger racine. La
garde y pose un handler qui ne garde que des événements analysés, jamais de
texte brut. Ce handler s'exécute dans le fil du module CFS, à chaque ligne : il
reste court et ne lève jamais. La garde n'écrit jamais sur la liaison CFS ; sa
seule commande au module stock est `BOX_ENABLE_AUTO_REFILL`. Rien n'est écrit
sur le disque.

Filtrer le bavardage CFS du journal (option 4 du document 103) doit donc se
faire au handler du fichier, jamais au logger racine : la garde deviendrait
aveugle.

### Ordre des crochets

Si la garde à froid (`cold-push-guard-v1`) est déjà posée, la garde capteur se
glisse entre elle et le contrôle stock ; sinon elle se pose directement et la
garde à froid vient l'envelopper. Dans les deux ordres, le contrôle stock juge
en premier, puis la garde capteur, puis la garde à froid.

## 5. Rejeux

### 31 octobre

[SIMULATION] T1B : vraie fin prouvée à 18:56:39, à +33 s, jamais marquée.

[SIMULATION] T1A : épisode ouvert à 19:01:26 par le masque `material`, encore
suspect à 19:05:32, marqué à 19:05:34 après 248 s et 403 mm, coupe prouvée par
deux lectures. Fin comme la V4 : `key839` à 19:07:36 pendant la coupe, échec à
19:07:42 ; la première poussée stock, 80 mm à 19:08:17, est refusée en phase
`failed`, 0 mm en file, et Klipper s'arrête.

[HYPOTHÈSE] L'heure de la marque dépend du débit du rejeu. En pause de 19:00:56
à 19:04:31, l'impression ne compte rien ; à 6,4 mm/s ensuite, les 400 mm
tombent à 19:05:34. Sous 2,2 mm/s en moyenne entre la reprise et la fin du
fichier, la marque ne serait pas tombée avant la fin. L'arrêt, lui, n'en
dépend pas.

[INCONNU] Que la coupe de 19:05:34 aurait empêché la routine stock : aucun
journal ne montre encore `FILAMENT_ERR` avec l'auto-remplacement à 0
(document 104). La sûreté de la fin repose sur l'arrêt.

### 1er novembre

[SIMULATION] Épisode ouvert à 07:07:08, début de l'extrait, marqué à 07:10:08
après 180 s et 796 mm, coupe prouvée. Fin du fichier à 07:13:52, fin K1 Control
simulée en `heating` ; la poussée stock de 80 mm à 07:14:08 est refusée, 0 mm,
et Klipper s'arrête. Avec trois poussées de 0,5 mm, les deux premières passent
et la troisième arrête, à 1,5 mm nets. Une poussée stock pendant `cutting`
passe (section 7). En vrai, la V4 avait échoué à 07:13:57 : `failed` n'est pas
non plus une phase qui pousse exprès, le rejeu du 31 octobre y arrête la
machine.

[HYPOTHÈSE] En vrai, la marque serait tombée bien plus tôt : le document 104
relève une erreur filament sur T1A à 00:49:08, en fin de chargement, et
`filament_useup` à 1. [INCONNU] Ce que le CFS a répondu entre 00:49 et 07:07 :
l'extrait ne le contient pas.

### 15 septembre

[SIMULATION] D'après les documents 80 et 81 : `FILAMENT_ERR` et ligne nommée
T1A à 03:45:58, tension, masques `connections` à 1 ; marque à 03:48:58 après
180 s, coupe prouvée. Le rejeu arrête les masques à 03:55:00 pour vérifier
aussi la fermeture de l'épisode ; en vrai, ils ont continué jusqu'à 10:47:28 au
moins et l'épisode serait resté ouvert. La marque tombe avant dans les deux cas.

Les poussées stock de 80 mm à 12:04:05, 12:04:45 et 12:05:25 sont placées après
une fin K1 Control simulée de 12:03:16 à 12:04:00. Ses propres poussées, 2,
−20, −15 et 1,5 mm pendant `cutting`, `rewinding` et `finalizing`, passent. La
première poussée stock arrête la machine à 12:04:05, en `complete` ; les deux
suivantes sont refusées.

[FAIT] Ce jour-là, la K1 avait la fin stock et la boucle tournait dans
`BOX_END` (document 81). Sous la V5, `BOX_END` tourne en `finalizing` : la
garde n'arrêterait pas cette forme (section 7).

### 13 septembre

[SIMULATION] Route T1B : vraie fin prouvée à 12:33:04, à +81 s. Route T1A :
prouvée à 12:31:44, à +1 s. Aucune marque, aucune coupe.

### Impression saine

[SIMULATION] Aucun épisode, aucune marque, aucune coupe. Les poussées de la fin
K1 Control passent. La console annonce une fois la fenêtre de fin, qui expire
15 min après la sortie de la fin de ses phases actives.

## 6. Console et fin K1 Control

`kctrl_end` fait échouer sa fin sur une ligne de console qui commence par `!!`
ou contient `failed`. En dehors de l'arrêt et des refus de `START_PRINT`, aucun
texte de la garde ne fait l'un ou l'autre, et `KCTRL_SENSOR_GUARD_STATUS` comme
`KCTRL_SENSOR_GUARD_RELEASE` répondent sans jamais lever. Un
`BOX_ENABLE_AUTO_REFILL` refusé fait afficher `!!` par Klipper ; la garde ne
l'envoie jamais pendant les phases de la fin K1 Control. Les rejeux du
31 octobre, du 1er novembre, du 15 septembre et de l'impression saine le
vérifient sur toutes leurs lignes de console ; seule la ligne `key839` du
firmware est admise le 31 octobre. Les messages sont listés dans le README du
paquet.

## 7. Compromis et limites

Une impression marquée garde l'auto-remplacement coupé pour tous les slots
jusqu'au prochain `START_PRINT`. Une vraie fin de bobine pendant cette
impression donnera donc probablement une pause au lieu d'un relais vers le slot
de secours : recharger, puis reprendre.

Limites principales ; la liste complète est dans le README :

- une boucle stock dans le `BOX_END` de `finalizing`, la forme du 15 septembre,
  n'est pas bornée. La V5 n'entre dans `BOX_END` qu'après deux lectures
  fraîches sans filament en tête ni route CFS, auto-remplacement coupé ; qu'elle
  ne puisse plus y boucler reste inconnu ;
- une poussée stock pendant `cutting` passe ;
- une poussée, un chargement ou un retrait à la main dans la fenêtre arrête la
  machine : `KCTRL_SENSOR_GUARD_RELEASE` d'abord. Après un arrêt, Klipper
  quitte seul (bogue TMC Creality) et Thomas rallume ;
- les déclencheurs de la surveillance PC sur le refus du bac et sur la cible
  chaude tenue 15 min ne sont pas repris.

## 8. Preuves

- `tests/test_kctrl_sensor_guard_v1.py` : 126 tests verts, faux Klipper sur
  horloge simulée, aucun réseau, aucun SSH. Ils chargent la fin V5, la garde
  à froid et la politique de départ (`retained-start-v1`) du dépôt, pas des
  copies.
- Suite complète, commande de la CI rejouée sur le poste (Python 3.10.6,
  pytest 9.1.1) : 2 642 tests verts, 6 ignorés, 2 échecs attendus (`xfail`)
  et 41 sous-tests verts ; les 16 modules adossés aux captures brutes sont
  exclus comme en CI, les deux rouges volontaires désélectionnés et toujours
  rouges. Tests node : 7 et 33 verts.
- Mutants, joués sur une copie hors dépôt : chacun fait échouer au moins un
  test.

| Mutant | Tué par |
| --- | --- |
| un épisode ouvert par le seul masque `material` devient réel | `test_a_material_mask_alone_opens_a_suspect_episode_that_marks` |
| la marque n'exige plus la tête chargée | `test_a_head_without_filament_or_unread_blocks_the_mark[False]` |
| les millimètres comptent aussi en `paused` | `test_31_october_t1a_is_marked_and_the_stock_push_after_the_end_is_stopped` |
| `heating` devient une phase qui pousse exprès | `test_1_november_marks_after_180_s_and_stops_the_stock_push_while_heating` |
| la coupe se dit prouvée sans relire | `test_an_unconfirmed_cut_is_retried_while_the_refill_reads_1` |
| `cancelled` n'ouvre plus la fenêtre | `test_every_end_state_opens_the_window[cancelled]` |
| une rétraction donne du crédit | `test_a_retraction_buys_no_credit_for_a_later_push` |
| un épisode peut commencer avant son impression | `test_an_episode_never_starts_before_its_job` |
| la marque ignore la cécité | `test_a_log_level_above_info_blinds_the_watch_and_is_told_once` |
| l'arrêt rend la main au lieu de lever | `test_31_october_t1a_is_marked_and_the_stock_push_after_the_end_is_stopped` |
| la coupe ne vérifie plus que l'impression est la même | `test_a_start_during_the_read_back_takes_the_cut_out_of_the_old_job` |
| plus de recoupe | `test_an_unconfirmed_cut_is_retried_while_the_refill_reads_1` |
| `parse()` accepte une réponse de taille autre que 7 | `test_parse_rejects_every_other_line[msg: 0xf7 0x1 0x19 0x50 0xa 0x0]` |
| un épisode se ferme malgré un masque `connections` récent | `test_15_september_marks_on_the_contradicted_slot_and_trips_after_the_owned_end` |
| `START_PRINT` ne remet plus l'auto-remplacement | `test_a_refused_cut_neither_counts_nor_speaks_again_and_needs_no_restore` |
| la ligne de queue ne prouve plus une vraie fin | `test_the_tail_line_alone_makes_the_live_route_real` |
| la marque n'exige plus les 400 mm | `test_31_october_t1a_is_marked_and_the_stock_push_after_the_end_is_stopped` |
| `paused` compte comme une fin même fichier ouvert | `test_31_october_t1a_is_marked_and_the_stock_push_after_the_end_is_stopped` |

## 9. Inconnues

- Comportement stock sur `FILAMENT_ERR` avec l'auto-remplacement à 0
  (document 104).
- Délai de preuve et millimètres consommés par d'autres vraies fins que celles
  lues ici.
- Que `BOX_END` puisse encore boucler sous la V5.
- [HYPOTHÈSE] `BOX_ENABLE_AUTO_REFILL` pendant l'impression ne fait que poser le
  drapeau ; ses écritures sur la flash ne sont pas mesurées (documents 103 et
  104).
- Cause de la fausse erreur sur T1A : capteur de la case A suspecté
  (document 104).

## 10. Suite

1. Rien à poser avant la fin V5 posée et sa première fin validée (document 104,
   section « Suite »).
2. Ensuite, mission de pose : script d'installation avec sauvegarde, préflight,
   validation et retour arrière, au repos revérifié, Thomas présent, préflight
   d'abord. Ordre de pose : garde à froid (en service), fin V5, garde capteur.
   Retour arrière dans l'ordre inverse : garde capteur d'abord, puis fin V5.
3. Backlog : borner la poussée nette en `finalizing` ; filtrer le bavardage CFS
   au handler du fichier si l'option 4 du document 103 est retenue.
