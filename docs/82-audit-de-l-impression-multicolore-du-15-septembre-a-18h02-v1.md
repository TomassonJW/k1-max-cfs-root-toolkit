# 82 — Audit de l'impression multicolore du 15 septembre, 18:02 → 18:28 : fin propre, zéro pause, zéro silence du bus, trois relances de chargement

Date : 2026-09-15, 19:00. Lecture seule, machine au repos après l'impression.

## 0. La question

Thomas, le 15 septembre à 18:43 : « Tu peux auditer la dernière impression ? »
La dernière impression est `MultiColo_Cube_PLA_15m31s.gcode`, lancée à 18:02
depuis la page Bobines, la première sous la garde du bus (ADR-068, posée à
17:52) et la première fin réelle avec le retrait par nos soins (ADR-067, posé
à 14:03). Même fichier que l'audit en direct du 14 septembre (document 79,
section 9) : la comparaison est directe.

## 1. Réponse courte

1. **Impression finie, 26 min 01 s, sans pause, sans code du CFS**
   (`completed`, 1 707 mm de filament, cinq `T` passés). [FAIT]
2. **La fin d'impression est réparée** (ADR-067) : notre retrait de `T2B`
   en 28 s (coupe, rembobinage, « tete vide »), puis la fin stock `BOX_END`
   devant une tête vide rend la main en 14 s sans rien pousser. 42 s en tout,
   contre 49 s la veille et 17 minutes de boucle le matin. [FAIT]
3. **Le bus n'a perdu aucune question** (ADR-068) : 1 218 questions au CFS 2
   entre 17:13 et 18:44, 0 muette, 0 `key831`. Trois réponses finies par `F7`
   ; la garde a retenu la question qui suivait la première (314 ms après le
   rapport du capteur du CFS 1, le rapport même du matin) et elle a eu sa
   réponse en 8 ms. [FAIT] Mais le cas du matin, ce rapport toutes les 5 s en
   veille avec la question au CFS 2 juste derrière, ne s'est pas présenté :
   la preuve décisive de la garde attend une veille du capteur. [INCONNU]
4. **Trois chargements sur cinq ont eu la relance « extrudeur »** (`T1A`,
   `T2D`, `T1D`) : sept poussées avant que le capteur de tête voie le
   filament, « buffer is always full », rembobinage court et nouvelle
   poussée. Un chargement raté coûte 85 à 90 s ; c'est toute la différence
   avec la veille (23 min 25 s). Sur les deux impressions cumulées : 5
   relances sur 6 chargements depuis le CFS 1, 1 sur 7 depuis le CFS 2.
   [FAIT] La bobine noire n'est plus la seule suspecte (section 7).
5. Le reste est celui du document 79 : purge de changement arrondie à 280 mm
   par le module (2 min 14 s, deux tiers d'un changement), `key61`
   (`SET_HOTEND_FAN`) bruit connu, 99 Mo de mémoire après coup, aucune
   erreur Klipper.

## 2. Méthode

- Trames du bus : `scripts/audit-en-direct/bus.sh` (fenêtre bornée de 28 Mo,
  `nice`, lignes coupées) puis `silences_cfs.py`, et un relevé des trois
  réponses finies par `F7` avec la question qui suit chacune.
- Événements : fenêtre `dd` de 28 Mo sans les trames du bus ni les appels
  Moonraker, filtrée par mots-clés, dans le dossier brouillon de la session
  (hors dépôt).
- Rejeu de `audit_live.py` sur la fenêtre brute de 18:00 à 18:39 (39 650
  lignes, 5,6 Mo, hors dépôt) : tableau des changements et alertes de fin.
- `purges.sh` (fenêtre de 28 Mo) pour les volumes de purge et les relances.
- Compteurs de la garde par `printer/objects/query?serial_485+serial485`, et
  historique Moonraker pour les heures de départ et de fin.

Toute lecture du journal est bornée (document 81) ; aucune commande envoyée
à la machine.

## 3. Chronologie

| Heure | Événement |
| --- | --- |
| 18:02:18 | Fenêtre Bobines : 5 filaments déclarés, 5 utilisés, à raccorder |
| 18:02:25 | Bobines raccordées (7 s) |
| 18:02:28 | Départ : lit 55 °C, buse 195 °C, filament 1 (`T1A`), maillage `k1_p001_t055_r001_n11x11`, Z 0,065 |
| 18:03:33 → 18:04:43 | Palpage, plafond buse 105 °C |
| 18:04:44 → 18:08:02 | Chargement de `T1A` : 7 poussées, capteur de tête à 18:06:20, « buffer is always full », relance extrudeur, `filament_useup` → 1 à 18:07:21, purge 140 mm, ligne d'amorce à 18:08:02 (198 s) |
| 18:08:09 | `key61` (`SET_HOTEND_FAN`), bruit connu (document 70) |
| 18:08:10 → 18:08:18 | `T0` du fichier, même filament : 8 s, alarme coupée puis rallumée |
| 18:09:08 → 18:13:58 | `T1` → `T2D`, 290 s, relance |
| 18:14:25 → 18:19:09 | `T2` → `T1D`, 284 s, relance |
| 18:19:36 → 18:22:56 | `T3` → `T2A`, 200 s |
| 18:23:26 → 18:26:47 | `T4` → `T2B`, 201 s |
| 18:27:47 | « K1 Control: retrait (fin) de T2B (dernier changement d'outil) : coupe, puis rembobinage » |
| 18:28:15 | « retrait (fin) de T2B fait, tete vide » ; `box_end` |
| 18:28:29 | `Finished SD card print`, `Exiting` : `box_end` → `Exiting` en 14 s, 0 tronçon |

| Poste | 14 septembre | 15 septembre | Écart |
| --- | --- | --- | --- |
| Départ, du lancement à la fin du `T0` du fichier | 5 min 55 s | 5 min 50 s | −5 s |
| 4 changements de couleur | 13 min 26 s | 16 min 15 s | +2 min 49 s (deux relances) |
| Impression proprement dite | 3 min 15 s | 3 min 14 s | — |
| Fin | 49 s | 42 s | −7 s |
| Total | 23 min 25 s | 26 min 01 s | +2 min 36 s |

## 4. La fin (ADR-067)

[FAIT] `END_PRINT` a appelé `_KCTRL_UNLOAD REASON=fin`. L'emplacement est venu
du dernier changement d'outil de notre enveloppe (`T2B`, `done`) ; la buse
était à 210 °C. `BOX_ERROR_CLEAR` a écrit son bruit stock (« error(None) not
in error list »), la coupe et `BOX_RETRUDE_MATERIAL_WITH_TNN TNN=T2B` ont
pris 28 s (`RETRUDE_PROCESS` à 18:28:15), `_KCTRL_UNLOAD_CHECK` a relu le
capteur : « tete vide ». Puis `END_PRINT_NO_M84` : `box_end` à 18:28:15,
deux lectures `GET_FILAMENT_SENSOR_STATE` (connexions 0 et 0), `Exiting` à
18:28:29. Rejeu de l'audit en direct : « box_end -> Exiting en 14 s, 0
troncon(s) pousse(s) », aucune alerte.

L'inconnue du document 81 (ce que fait `BOX_END` devant une tête vide) est
levée pour ce cas : il relit les capteurs et rend la main. Reste non observé
le cas du matin, une fin avec `filament_useup` à 1 : ici le drapeau est
repassé à 0 dès le second chargement (18:11:41) et y est resté.

## 5. Le bus (ADR-068)

[FAIT] `silences_cfs.py` sur la fenêtre 17:13:54 → 18:44:18 :

| Trame précédente | Écart | Répond | Muette |
| --- | --- | --- | --- |
| réponse d'un CFS finie par `F7` | < 1 s | 2 | 0 |
| autre | < 300 ms | 21 | 0 |
| autre | ≥ 300 ms | 1 195 | 0 |

Aucune réponse au CRC faux. Les trois réponses finies par `F7` :

| Heure | Réponse | Question suivante | Résultat |
| --- | --- | --- | --- |
| 18:06:24.883 | CFS 1, commande `08` (capteur de filament, valeur 1), pendant la relance de `T1A` | +314 ms, CFS 1, commande `08` | réponse en 8 ms |
| 18:15:14.959 | CFS 1, commande `10` | +869 ms, CFS 2, commande `0a` | réponse en 10 ms |
| 18:15:19.037 | CFS 1, commande `10` | +835 ms, CFS 2, commande `0a` | réponse en 6 ms |

Compteurs de la garde à 18:43 : `kctrl_calls` 3 911, `kctrl_seen` 3 108,
`kctrl_marked` 3, `kctrl_held` 1, `kctrl_unknown` 0. Les trois réponses sont
vues, une seule question a été retenue (la première, 314 ms au lieu de
quelques dizaines), les deux autres venaient d'elles-mêmes après 800 ms.

[INCONNU] Le rapport du capteur n'est venu qu'une fois, pendant un
chargement ; le matin il revenait toutes les 5 s en veille, et la question
suivante allait au CFS 2. Cette impression ne dit donc pas encore si la garde
suffit dans ce cas ; elle dit qu'elle ne gêne rien (une retenue de 300 ms
sur 3 911 questions).

## 6. Les changements

Rejeu de `audit_live.py` (`changements.tsv`) :

| Début | `T` | Vers | Durée | Poussées avant le capteur de tête | Relance | Purge demandée → poussée |
| --- | --- | --- | --- | --- | --- | --- |
| 18:04:44 | départ | `T1A` | 198 s | 7 | oui | 140 mm |
| 18:09:08 | `T1` | `T2D` | 290 s | 7 | oui | 266 mm (640 mm³) → 280 |
| 18:14:25 | `T2` | `T1D` | 284 s | 7 | oui | 244 mm (587 mm³) → 280 |
| 18:19:36 | `T3` | `T2A` | 200 s | 1 | non | 192 mm (462 mm³) → 280 |
| 18:23:26 | `T4` | `T2B` | 201 s | 1 | non | 181 mm (437 mm³) → 280 |

Un changement sans relance (`T3`) : 2 s de préparation, 4 s de déplacement
au cutter, 25 s de rembobinage, 28 s de poussée, 2 min 14 s de purge
(280 mm à 140 mm/min, document 79 section 10, correctif 1), 3 s de remise en
place : la purge fait 67 % du changement. Un changement avec relance
(`T1`) : la poussée dure 66 s au lieu de 28 (sept cycles de 7 s), puis
« buffer is always full », rembobinage court (22 s) et nouvelle poussée
(11 s) : 85 à 90 s de plus.

Alarme du capteur de tête coupée et rallumée à chaque `T` (ADR-065), cibles
rendues au fichier (200, 225, 210, 205, 210 °C), aucune pause.

## 7. Hypothèses et inconnues

- [FAIT] Relances par emplacement, deux impressions cumulées (document 79,
  section 9.4, et celle-ci) : `T1A` 3 sur 3, `T1D` 2 sur 3, `T2D` 1 sur 2,
  `T2A` 0 sur 2, `T2B` 0 sur 3. Par unité : CFS 1, 5 sur 6 ; CFS 2, 1 sur 7.
  Aujourd'hui les trois ratés sont les trois premiers chargements et les
  deux réussis les deux derniers, même ordre que la veille.
- [HYPOTHÈSE] Le chemin du CFS 1 jusqu'au hub (tube, raccord, entrée du
  hub) oppose plus de résistance : le filament met sept poussées à
  atteindre le capteur de tête et arrive avec trop peu d'élan pour que
  l'extrudeur morde. L'hypothèse « bobine noire » du document 79 ne tient
  plus seule : le blanc `T1D` et la lavande `T2D` ont eu la même relance.
- [HYPOTHÈSE] La température n'explique rien : ratés à 195, 225 et 210 °C,
  réussites à 205 et 210 °C.
- [INCONNU] Pourquoi `filament_useup` passe à 1 au premier chargement de
  `T1A` (après la relance) et à 0 aux suivants ; le matin il valait 1 à la
  fin, et la fin a bouclé. Le module seul le sait.
- [INCONNU] Une veille du capteur du CFS 1 (rapport toutes les 5 s) ne s'est
  pas produite : la garde n'a pas été mise à l'épreuve dans le cas exact du
  matin.

## 8. Ce qui reste à faire, classé

| # | Quoi | Qui | État |
| --- | --- | --- | --- |
| 1 | Trancher les relances : échanger une bobine entre le CFS 1 et le CFS 2 (le noir en `T2B`, le bleu en `T1A`) et charger chacune trois fois depuis l'écran ; si la relance suit l'unité, regarder le tube CFS 1 → hub et l'entrée du hub | Thomas | à faire |
| 2 | Purge de changement : aligner les volumes du trancheur sur les paliers 140 et 280 mm du module (document 79, correctif 1) | à instruire | ouvert |
| 3 | Garde du bus : attendre une veille du capteur (rapport toutes les 5 s) et relire `kctrl_marked`, `kctrl_held`, puis `silences_cfs.py` | observation | ouvert |
| 4 | Fin d'impression avec `filament_useup` à 1 : à observer si le cas revient ; l'audit en direct alerte | observation | ouvert |

## Voir aussi

- Document 79 — audit des séquences de départ et de changement, audit du 14
- Document 80 — pauses `key831`, garde du bus
- Document 81 — fin d'impression en boucle, lectures bornées, alertes
- ADR-067 — la fin d'impression vide la tête avant la fin stock
- ADR-068 — la garde du bus est posée
