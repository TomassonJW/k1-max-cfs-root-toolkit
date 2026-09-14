# 79 — Départ et changement de couleur : ce que fait la machine, et qui le décide

Date : 2026-09-14. Audit à froid à 21:30 (sections 1 à 8) : journaux de Klipper
du 9 au 14 septembre, une image de la webcam. Audit en direct de 22:30 à 22:54
pendant une impression multicouleur complète (section 9), correctifs classés à
23:30 (section 10) : journal suivi en continu, images de la webcam, `box.cfg`,
base matière et fichier tranché lus sur la machine. Lecture seule : l'audit n'a
rien modifié sur la machine.

Conventions, comme le document 70 : **[FAIT]** lu dans un journal ou un fichier,
horodaté ; **[HYPOTHÈSE]** cohérent avec les faits, non démontré ;
**[INCONNU]** non observable ou pas encore observé.

## 0. La question

Thomas, le 14 septembre au soir, après `3DBenchy_C2` (quatre filaments) :

- au changement vers le noir, le filament est inséré, purgé un peu, rembobiné
  entièrement, réinséré, purgé un peu, puis l'impression reprend ;
- au départ de presque toutes les impressions : insertion, le moteur du CFS
  pousse mais l'extrudeur ne fait quasi rien, la tête sort du bac à purge et y
  revient (parfois après coupe, rembobinage et réinsertion), vraie purge,
  démarrage.

« Pourquoi ? » et « tu expliques pourquoi c'est n'importe quoi ? »

## 1. Méthode

- `klippy.log` et ses rotations du 9 au 14 septembre, lues par un extracteur qui
  garde les lignes horodatées, retire le bruit série du CFS et regroupe les
  répétitions. Les lignes du module CFS compilé (`box_wrapper`, Creality) sont
  reconnaissables à `cmd_T`, `stage5`, `stage8`, `material_change_flush`,
  `auto_retry` ; celles de notre code commencent par « K1 Control ».
- Relevé de marqueurs sur tous les journaux : départs, relances automatiques,
  codes d'erreur, coupes, purges.
- Horloges du PC et de l'imprimante identiques à la seconde (21:23:05 des deux
  côtés, [FAIT]). La webcam voit l'arrière de la chambre, là où la tête purge ;
  image sombre, machine au repos ([FAIT], 21:25).

## 2. Le départ quand tout va bien

Départ du 12 septembre, fichier à 190 °C, bobine T1B, tête vide
(`filament_sensor false`). Temps comptés depuis la commande `T` émise par
`START_PRINT` à 23:20:20 ([FAIT], `klippy.log.2026-09-12`).

| Temps | Heure | Ce qu'on voit | Ce qui se passe | Qui |
|---|---|---|---|---|
| 0-6 s | 23:20:20 | le plateau descend de 20 mm, la tête va au bac | `z_down`, `box_extrude_material`, `y_pos 305` | Creality |
| 8-42 s | 23:20:28 | rien | chauffe à 200 °C (`flush_temp: 200`, plancher du chargeur, alors que la fiche dit 190) | Creality |
| 42-51 s | 23:21:02 | le CFS pousse, l'extrudeur ne tourne pas | le filament voyage dans le tube jusqu'au capteur de tête (`stage5`) ; il n'a pas encore atteint l'extrudeur | Creality |
| 51-62 s | 23:21:11 | l'extrudeur tourne à peine | il avance de 5 mm pour mordre (`stage7`), puis tire doucement jusqu'à ce que le tampon passe de « plein » à « milieu » (`stage8`, « middle » à 23:21:18) | Creality |
| 62-87 s | 23:21:22 | purge dans le bac | 140 mm à 6 mm/s ; `last_tnn is none` : le module a oublié la couleur précédente, il purge une longueur fixe | Creality |
| 87-92 s | 23:21:47 | la tête sort du bac et y revient plusieurs fois | essuyage pour décrocher la boule (`y_pos 305` / `safe_pos_y 291.5`, six mouvements) | Creality |
| 92 s | 23:21:52 | le plateau remonte | `z_restore` de 20,04 mm, rendu à l'identique | Creality |
| 95-115 s | 23:21:55 | ligne d'amorce sur le plateau | trois passes de 160 mm à Z 0,36 | nous |
| 116-124 s | 23:22:16 | rien | le `T` du fichier retombe sur la même bobine : « same », rien à faire | Creality |

Lecture :

- L'extrudeur immobile pendant que le CFS pousse est voulu : le filament n'est
  pas encore arrivé. Ce n'est pas un défaut.
- La sortie du bac et le retour sont l'essuyage de fin de purge, pas un
  aller-retour inutile.
- Avant le 10 septembre à 12:31, notre démarrage ajoutait une seconde purge de
  120 mm et une seconde ligne ; retirées par l'ADR-060. Une impression plus
  ancienne montrait donc deux passages au bac.

## 3. Le changement de couleur

### 3.1 Vers le noir, avec relance (14 septembre, T0, bleu T2B → noir T1A)

| Heure | Ce qu'on voit | Ce qui se passe |
|---|---|---|
| 20:34:05 | début | `cmd_T vtnn=T1A` |
| 20:34:08 → 12 | la tête va au couteau | coupe du bleu, capteur de coupe à 1 puis retour |
| 20:34:13 → 40 | le bleu recule | rembobinage du bleu (27 s) |
| 20:34:42 | la tête va au bac | `box_extrude_material(T1A)` |
| 20:34:47 → 55 | le CFS pousse le noir | `stage5` ; l'extrudeur mord 5 mm à 20:34:54 (`stage7` OK) |
| 20:34:55 → 20:35:41 | l'extrudeur tourne à peine, un peu de matière peut sortir | tampon « plein » à chacune des 12 lectures (46 s), « buffer is always full » |
| 20:35:41 | | relance automatique `auto_retry_extruder_gear` |
| 20:35:44 → 58 | la tête va au couteau, le noir recule entièrement | nouvelle coupe, rembobinage rapide (12 s) |
| 20:36:04 → 19 | le noir revient | nouvelle poussée, morsure à 20:36:12, tampon « milieu » à 20:36:19 (7 s) |
| 20:36:23 → 20:37:24 | purge | 140 mm à 2,3 mm/s alors que le fichier en demande 115 (279 mm³) ; roue de mesure du CFS : 142 mm |
| 20:37:24 → 30 | la tête sort du bac et y revient | essuyage, `z_restore`, « T0 fait » à 20:37:30 |

[FAIT] Le rembobinage complet et la réinsertion sont la relance de Creality :
après avoir poussé le filament à la tête, le module exige que le tampon quitte
« plein », preuve que l'extrudeur tire. Douze lectures « plein » de suite et il
conclut que l'extrudeur n'a pas mordu, coupe, rembobine et recommence. Notre
enveloppe `kctrl_tool_change` n'émet ni mouvement, ni extrusion, ni relance :
elle écrit la fiche matière, coupe puis rallume l'alarme de fin de bobine,
remet la température et met en pause si la tête est vide après le changement.

Coût de la relance : 84 s (20:34:55 → 20:36:19).

### 3.2 Les trois changements du 14 septembre

| Changement | Relance | Purge demandée → poussée (roue du CFS) | Durée totale |
|---|---|---|---|
| T3, rouge T2A → bleu T2B, 19:19:16 | aucune | 221 mm (532 mm³) → 280 mm, 140 + 140 (287) | 3 min 20 |
| T0, bleu T2B → noir T1A, 20:34:05 | extrudeur (20:35:41) | 115 mm (279 mm³) → 140 mm (142) | 3 min 25 |
| T1, noir T1A → blanc T1D, 20:45:36 | extrudeur (20:47:06) | 308 mm (743 mm³) → 309 mm, 140 + 168,9 (304) | 4 min 45 |

[FAIT] Les volumes viennent du fichier tranché (Creality Print 5.1.7,
`flush_volumes_matrix`, multiplicateur 1,0, purge dans la tour désactivée). Le
module les convertit en longueur (volume ÷ 2,405 mm², section d'un fil de
1,75 mm), puis pousse à 140 mm/min par tronçons d'au moins 140 mm séparés d'un
essuyage : d'où les sorties et retours au bac au milieu des longues purges, et
une purge plus longue que demandée sous 280 mm (section 9.3). Correction du
14 septembre à 23:30 : la première version de ce tableau donnait les longueurs
demandées, pas les longueurs poussées.

## 4. Fréquences

| Quoi | Période | Résultat [FAIT] |
|---|---|---|
| Relance au chargement du départ | 15 départs, 10 septembre 01:45 → 12 septembre 23:17, dont 14 allés jusqu'à la purge | **0** ; le 15ᵉ (10 septembre 10:04) a été bloqué par notre ancien plafond de buse (220 °C demandés, ramenés à 205), pause demandée depuis l'interface à 10:11, arrêt d'urgence à 10:13, défaut corrigé depuis par l'alignement de la fiche matière |
| Relance au chargement du départ | 9 septembre | 4 départs sur les journaux du jour (13:23, 16:24, 17:59, 22:45) |
| Relance au chargement du départ | 14 septembre | les 2 départs (18:14, 18:30), rouge T2A cassé au tampon |
| Coupe au départ parce que la tête était encore chargée | 19 départs lancés depuis le 10 septembre | **1** (10 septembre 00:53, coupe ratée, `key841`) |
| Relance « extrudeur n'a pas mordu » aux changements | 3 changements du 14 septembre | **2** (noir, blanc) |

Le « presque toutes les impressions » ne vaut que pour la séquence normale de la
section 2. Coupe, rembobinage et réinsertion au départ sont des incidents.

## 5. Normal, anormal, et qui

| Constat | Verdict | Qui |
|---|---|---|
| Le CFS pousse seul, l'extrudeur attend | normal, voulu | Creality |
| Essuyage : la tête sort du bac et y revient | normal, voulu | Creality |
| Relance quand l'extrudeur n'a pas mordu | normal comme filet | Creality |
| La première morsure rate sur 2 changements sur 3 | **anormal, cause inconnue** (section 6) | matériel ou réglage |
| Le départ du 14 à 18:30 trace la ligne d'amorce à 18:39:33 alors que le CFS est en erreur depuis 18:36:22 (`key845`, `key840` à 18:36:52, `key836` à 18:38:52) | **anormal** ; déjà signalé par le document 70 (D2, P2) le 10 septembre, toujours présent | **nous** (`START_PRINT`) |
| Le chargement du `T` abandonne à 18:18:56 (`key836`, machine mise en pause par le module), puis 4 tentatives de notre code sur un filament cassé, chacune avec les relances internes du module, jusqu'à 18:24:46 ; l'annulation demandée à 18:23:58 n'aboutit qu'à 18:24:57 | **anormal** | **nous** (`_KCTRL_CFS_LOAD` ×4) |
| Purge de 140 mm à l'aveugle au départ | discutable : utile si la tête contient l'ancienne couleur, inutile sinon ; le module a oublié laquelle | Creality |
| Chauffe à 200 °C pour un fichier à 190 | discutable, sans effet pour du PLA (document 67, § 8) | Creality |
| « Buse bouchée » (`key845`, 18:36:22) alors que la roue de mesure du CFS n'a pas bougé de 18:34:46 à 18:36:17 : le filament était cassé en amont | **faux diagnostic** | Creality |
| 3 min 20 à 4 min 45 par changement | lent : la purge en prend les deux tiers, arrondie à 140 ou 280 mm et poussée à 140 mm/min (section 9.3) | Creality (arrondi, vitesse) et fichier (volumes) |

## 6. Pourquoi la première morsure rate : hypothèses à départager

- **[HYPOTHÈSE]** Pointe du filament écrasée ou biseautée par la lame lors de la
  coupe précédente : elle bute à l'entrée de l'extrudeur. La relance recoupe une
  pointe neuve, et le second essai prend en 7 à 8 s.
- **[HYPOTHÈSE]** Faux « plein » : l'extrudeur tire, mais le CFS pousse plus
  vite qu'il ne prend, ou le ressort du tampon frotte.
- **[INCONNU]** Lien avec la bobine ou l'emplacement : relances le 9 sur T1B et
  T2D, le 14 sur T1A et T1D ; T2B passé du premier coup ; T1B sans relance du
  10 au 12. Pas de motif sur ces échantillons.

Pendant l'audit en direct : noter pour chaque morsure les lectures du tampon, la
roue de mesure et l'image ; si la relance revient, regarder la pointe du
filament retiré à la main après l'impression (écrasée ou nette). [FAIT] Fait le
14 septembre au soir : la relance est revenue sur le noir, buse chaude, et la
webcam ne voit ni la buse ni le filament. Suite et tests pour trancher en
section 9.4.

## 7. Audit en direct, protocole

1. Thomas lance une impression multicouleur courte, au moins un passage noir →
   blanc, lumière de la chambre allumée, et prévient. L'agent ne lance, ne
   reprend et n'annule jamais une impression.
2. L'agent suit le journal pendant toute l'impression et prend des images de la
   webcam (`http://192.168.1.64:8080/?action=snapshot`) au départ et à chaque
   changement.
3. Pour chaque séquence : image, ligne de journal, auteur (Creality ou nous),
   durée, filament jeté, anomalie.
4. Vérifie aussi l'ADR-065 : « runout alarm off during Tn », « runout alarm on
   again after Tn », aucune pause.
5. Ajoute à ce document une section « Audit en direct » et classe les
   correctifs.

[FAIT] Déroulé le 14 septembre de 22:30 à 22:54 : sections 9 et 10.

## 8. Décisions

- Accord de Thomas le 14 septembre au soir : corriger nos deux défauts de la
  section 5 avant l'audit, le départ s'arrête net si le CFS est en erreur, deux
  tentatives de chargement au lieu de quatre. [FAIT] Écrit et testé hors
  machine le 14 septembre à 22:10 (ADR-066) : le départ lit la pause après le
  changement d'outil, après les tentatives et avant la ligne d'amorce, et
  s'arrête chauffes coupées. [FAIT] Installé le même soir à 22:16, machine à
  l'arrêt, démarrage sans erreur. [FAIT] Premier départ réel à 22:30 passé sans
  arrêt, CFS sans erreur (section 9.5) ; comportement sur une vraie pause
  toujours à observer.
- [FAIT] Le module CFS ne publie aucune erreur dans son objet `box` (champs lus
  le 14 septembre vers 21:45 : `filament`, `state`, `auto_refill`, `enable`,
  `filament_useup`, `same_material`, `T1` à `T4`, `cut_pos`, `t_command`,
  `custom_command_result`). Quand il abandonne, il écrit « error: printing to
  pause » et met la machine en pause (18:18:56, 18:36:22, 18:36:52,
  18:38:52) : c'est le seul signal lisible par une macro.
- Volumes de purge du trancheur, à revoir seulement après l'audit, chiffres en
  main : chiffres en section 9.3, correctif 1 de la section 10, à essayer par
  Thomas dans le trancheur.

## 9. Audit en direct, 14 septembre, 22:30 → 22:54

### 9.1 L'impression, et où passe le temps

`MultiColo_Cube_PLA_15m31s.gcode`, cinq filaments : noir T1A, lavande T2D, blanc
T1D, rouge T2A, bleu T2B, raccordés sur la page Bobines à 22:30:53. Départ à
22:30:56, fin à 22:54:21 (23 min 25 s). Journal suivi en continu par
`scripts/audit-en-direct/`, 64 images de la webcam (non versionnées). Pendant
l'impression, l'outil fermait chaque changement une fraction de seconde avant la
ligne « alarm on again » et le notait à tort sans alarme rallumée ; corrigé, et
rejoué sur le journal enregistré, il donne les tables ci-dessous.

[FAIT] Aucune pause, aucun code d'erreur du CFS, une seule relance Creality (au
départ) et un `EXTRUDE_ERR8` sans suite (section 9.3). Seul code remonté :
`key61` (`SET_HOTEND_FAN` inconnu de l'écran) à 22:36:43, bruit connu
(document 70).

| Poste | Durée | Part |
|---|---|---|
| Départ, du lancement à la fin du `T` du fichier | 5 min 55 s | 25 % |
| 4 changements de couleur | 13 min 26 s | 57 % |
| Impression proprement dite | 3 min 15 s | 14 % |
| Fin : coupe et rembobinage | 49 s | 3 % |

Le cube est un cas extrême : peu de matière, quatre changements. Les chiffres
qui comptent pour une vraie pièce sont ceux d'un changement (section 9.3).

### 9.2 Le départ, 5 min 55 s

| Heure | Durée | Ce qui se passe | Qui |
|---|---|---|---|
| 22:30:57 → 22:32:01 | 64 s | plateau à 55 °C puis 20 s de repos | nous |
| 22:32:01 → 22:33:34 | 93 s | palpage, buse à 100 °C (routines de palpage Creality appelées par notre départ) | nous |
| 22:33:34 → 22:34:23 | 49 s | plateau descendu de 20 mm, tête vide, buse chauffée de 100 à 200 °C (37 s), noir poussé jusqu'à la morsure | Creality |
| 22:34:23 → 22:35:10 | 47 s | tampon « plein » à 12 lectures de suite, buse à 200-202 °C | Creality |
| 22:35:10 → 22:35:50 | 40 s | relance `auto_retry_extruder_gear` : recul de 20 mm, rembobinage, nouvelle poussée, morsure à 22:35:43, tampon « milieu » à 22:35:50 | Creality |
| 22:35:50 → 22:36:24 | 34 s | purge de 140 mm à 360 mm/min (roue 122 mm), essuyage, plateau remonté | Creality |
| 22:36:24 → 22:36:35 | 11 s | contrôles de l'ADR-066, silencieux ; buse ramenée de 200 à 195 °C | nous |
| 22:36:35 → 22:36:43 | 8 s | ligne d'amorce | nous |
| 22:36:43 → 22:36:52 | 9 s | `T0` du fichier : même bobine, rien à faire | Creality |

Lecture :

- Sans la relance, 80 s de moins (87 s entre la morsure et « milieu » au lieu
  de 7) : le `T` aurait duré 90 s, comme au départ du 12 septembre (92 s,
  section 2), et le départ entier 4 min 35 s.
- La purge du départ ne connaît pas la couleur précédente (« last_tnn is
  none ») : 140 mm à la vitesse de `box.cfg` (`Tn_extrude_velocity: 360`, « failed
  to get flush speed from file »).

### 9.3 Les quatre changements, 201 à 202 s chacun

Secondes depuis le `T` :

| Changement | Coupe faite | Rembobiné | Morsure | Tampon « milieu » | Purge | Fin |
|---|---|---|---|---|---|---|
| T1, noir T1A → lavande T2D, 22:37:42 | 6 | 30 | 57 (`EXTRUDE_ERR8` sans suite) | 62 | 65 → 199 | 202 |
| T2, lavande T2D → blanc T1D, 22:41:31 | 6 | 39 | 52 | 60 | 64 → 198 | 201 |
| T3, blanc T1D → rouge T2A, 22:45:19 | 6 | 35 | 53 | 60 | 64 → 198 | 201 |
| T4, rouge T2A → bleu T2B, 22:49:10 | 6 | 36 | 53 | 61 | 65 → 199 | 202 |

Soit : approche et coupe 6 s, rembobinage 24 à 33 s, poussée jusqu'à la morsure
14 à 27 s, morsure à « milieu » 5 à 7 s, attente 3 à 4 s, **purge 134,4 s à
chaque fois (66 %)**, remontée du plateau 3 s.

| Purge | Volume du fichier | Longueur demandée | Poussée | Roue du CFS |
|---|---|---|---|---|
| départ, tête vide | — | — | 140 mm à 360 mm/min | 122 mm |
| noir → lavande | 640 mm³ | 266 mm | 140 + 140 à 140 mm/min | 259 mm |
| lavande → blanc | 587 mm³ | 244 mm | 140 + 140 | 258 mm |
| blanc → rouge | 462 mm³ | 192 mm | 140 + 140 | 284 mm |
| rouge → bleu | 437 mm³ | 181 mm | 140 + 140 | 290 mm |

[FAIT]

- Changements : 1120 mm poussés pour 883 demandés (+27 %) ; avec le départ,
  1260 mm, environ 3,8 g de PLA.
- Une purge de changement = deux tronçons de 60 s à 140 mm/min (5,6 mm³/s) et
  deux essuyages.
- Sur les sept purges de changement du jour : 115 mm demandés → 140 poussés ; 181 à 266 →
  280 ; 308 → 309 (140 + 168,9). `box.cfg` déclare `box_first_clean_length: 140`,
  `box_need_clean_length: 140` et `box_need_clean_length_max: 140`.
- Vitesse : 140 mm/min sur tous les changements des journaux du 9 au
  14 septembre. Juste avant, le module écrit « max_volumetric_speed: 14 » puis
  « get material extrusion speed: 2 ». La fiche 00001 (Generic PLA) de la base
  matière dit `filament_max_volumetric_speed: 10`, le fichier tranché 23 et 24.
- Fichier tranché : tour d'amorçage activée (`prime_volume = 25`), purge dans
  la tour désactivée, `nozzle_volume = 200`.

[HYPOTHÈSE] Le tronçon minimal de 140 mm vient de `box_need_clean_length`, et
la vitesse vaut 10 × la vitesse volumique écrite dans le journal.
[INCONNU] D'où vient ce 14 ; la règle exacte des tronçons au-delà de 308 mm.
Le module est compilé : ni l'une ni l'autre ne se lit dans le code.

### 9.4 La relance du noir

[FAIT]

- Buse à 200-202 °C pendant les 12 lectures « plein » (200 °C atteints à
  22:34:11, 12 s avant la morsure) ; même schéma à 20:35:41, buse chaude, pendant
  un changement. Une buse pas assez chaude n'est pas la cause.
- Relances « extrudeur » du 14 septembre par bobine : noir T1A 2 sur 2
  chargements, blanc T1D 1 sur 2, bleu T2B 0 sur 2, rouge T2A 0 sur 1, lavande
  T2D 0 sur 1 (hors filament rouge cassé de 18:14 et 18:30, autre relance).
- La webcam voit le fond de la chambre, pas la buse ni le filament : elle ne
  départage rien.

[HYPOTHÈSE] Le noir lui-même (diamètre, dureté, pointe mal coupée) ou
l'emplacement T1A (tube, entraînement). Les hypothèses de la section 6 restent
ouvertes.

Pour trancher, trois gestes de Thomas, sans rien changer à la machine :

1. Décharger le noir, regarder la pointe (écrasée, biseautée ou nette) et
   mesurer le diamètre au pied à coulisse en quelques points (au-delà de
   1,78 mm, il force à l'entrée de l'extrudeur).
2. Échanger le noir et le bleu (0 relance sur 2) dans le CFS, puis charger
   chacun trois fois depuis l'écran : si la relance suit le noir, c'est la
   bobine ; si elle reste sur T1A, c'est l'emplacement.
3. Pendant un chargement qui reste « plein », regarder la buse : si de la
   matière sort, l'extrudeur tire et le « plein » est faux (tampon).

### 9.5 Nos contrôles

- ADR-065 [FAIT] : sur les cinq `T` du fichier (22:36:43, 22:37:42, 22:41:31,
  22:45:19, 22:49:10), « runout alarm off during Tn » puis « runout alarm on
  again after Tn », aucune pause. Le `T` du départ passe hors de cette enveloppe,
  par conception.
- ADR-066 [FAIT] : départ passé sans arrêt, CFS sans erreur ; aucune tentative
  de chargement lancée (aucune ligne « CFS attempt ») ; 11 s entre la fin du `T`
  et la ligne d'amorce, dont la baisse de la buse de 200 à 195 °C.
  [INCONNU] L'arrêt sur une vraie pause, pas encore rencontré.

### 9.6 La fin

[FAIT] À 22:53:32, `box_end` : coupe à 22:53:38, rembobinage jusqu'à 22:54:06,
capteur de tête à vide, fin à 22:54:21. Chaque impression laisse donc la tête
vide.

[HYPOTHÈSE] Le bout de filament resté sous le couteau reste dans la tête, de la
couleur de fin d'impression : la purge de 140 mm du départ suivant le chasse.

## 10. Correctifs classés

| # | Correctif | Gain | Qui décide | État |
|---|---|---|---|---|
| 1 | Volumes de purge du trancheur alignés sur le tronçon de 140 mm : 336 mm³ au plus pour les transitions qui le supportent (vers une couleur plus foncée). De 437 à 640 mm³ demandés, la machine a toujours poussé 280 mm | 67 s et 140 mm par changement concerné (ce soir : blanc → rouge et rouge → bleu) | Thomas, dans Creality Print, sans toucher la machine | à essayer sur le cube, couleurs à juger à l'œil |
| 2 | Vitesse de purge : 140 mm/min, alors que la purge du départ tourne à 360 (ce soir sans erreur) et que le fichier annonce 23-24 mm³/s | jusqu'à 73 s par changement à 360 mm/min ; avec le correctif 1, une purge de 140 mm en 23 s au lieu de 60 | décision de Thomas : réglage du module Creality, source de la vitesse inconnue (section 9.3) | à instruire en lecture seule avant tout essai |
| 3 | Relance au chargement du noir | environ 80 s, une coupe et un rembobinage à chaque raté | Thomas, trois gestes de la section 9.4 | à faire |
| 4 | Purge de 140 mm à l'aveugle au départ : elle chasse le bout coupé de la fin d'impression (section 9.6) | — | — | on garde |
| 5 | `key61`, `SET_HOTEND_FAN` inconnu de l'écran | — | — | bruit connu (document 70) |
| 6 | Arrêt de l'ADR-066 sur une vraie erreur du CFS | sécurité | — | à observer à la première erreur |
