# 79 — Départ et changement de couleur : ce que fait la machine, et qui le décide

Date : 2026-09-14, 21:30. Audit à froid, lecture seule : journaux de Klipper du
9 au 14 septembre, une image de la webcam. Rien n'a été modifié sur la machine.
La seconde partie, en direct pendant une impression multicouleur complète,
reste à faire (section 7).

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
| 20:36:23 → 20:37:24 | purge | 116 mm à 2,3 mm/s (volume 279 mm³ du fichier) |
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

| Changement | Relance | Purge | Durée totale |
|---|---|---|---|
| T3, rouge T2A → bleu T2B, 19:19:16 | aucune | 221 mm (532 mm³), deux tronçons | 3 min 20 |
| T0, bleu T2B → noir T1A, 20:34:05 | extrudeur (20:35:41) | 116 mm (279 mm³) | 3 min 25 |
| T1, noir T1A → blanc T1D, 20:45:36 | extrudeur (20:47:06) | 308 mm (743 mm³), deux tronçons | 4 min 45 |

[FAIT] Les volumes viennent du fichier tranché (Creality Print 5.1.7,
`flush_volumes_matrix`, multiplicateur 1,0, purge dans la tour désactivée). La
purge avance à 140 mm/min, par tronçons de 140 mm séparés d'un essuyage : d'où
les sorties et retours au bac au milieu des longues purges.

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
| 3 min 20 à 4 min 45 par changement | lent ; longueurs fixées par le trancheur | fichier |

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
filament retiré à la main après l'impression (écrasée ou nette).

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

## 8. Décisions

- Accord de Thomas le 14 septembre au soir : corriger nos deux défauts de la
  section 5 avant l'audit, le départ s'arrête net si le CFS est en erreur, deux
  tentatives de chargement au lieu de quatre. [FAIT] Écrit et testé hors
  machine le 14 septembre à 22:10 (ADR-066) : le départ lit la pause après le
  changement d'outil, après les tentatives et avant la ligne d'amorce, et
  s'arrête chauffes coupées. Installation à suivre.
- [FAIT] Le module CFS ne publie aucune erreur dans son objet `box` (champs lus
  le 14 septembre vers 21:45 : `filament`, `state`, `auto_refill`, `enable`,
  `filament_useup`, `same_material`, `T1` à `T4`, `cut_pos`, `t_command`,
  `custom_command_result`). Quand il abandonne, il écrit « error: printing to
  pause » et met la machine en pause (18:18:56, 18:36:22, 18:36:52,
  18:38:52) : c'est le seul signal lisible par une macro.
- En attente : volumes de purge du trancheur, à revoir seulement après l'audit,
  chiffres en main.
