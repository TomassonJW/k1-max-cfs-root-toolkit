# CFS sensor guard V1 - capteur CFS contredit et fin sûre, dans Klipper

Statut : **versionnée et testée hors imprimante, jamais posée**. ADR-077,
document 105.

- `kctrl_sensor_guard.py` : le module Klipper, objet `kctrl_sensor_guard`. Il
  tourne sur la K1, sans le PC. `parse()` lit une ligne du journal,
  `SensorWatch` porte les règles du slot sur des instants donnés, sans objet
  Klipper ; `KctrlSensorGuard` lit la K1, coupe, rétablit et arrête.
- `sections.cfg` : la section candidate, `enabled: False`.

Aucun script de pose : la pose est une mission à part, après la pose de la fin
V5 (`end-no-stock-flush-v5`) et la validation de sa première fin, au repos
revérifié, Thomas présent, préflight d'abord. Activée, la garde exige
`[kctrl_end]` activé, sinon Klipper refuse de démarrer : sans la fin K1
Control, la fin stock pousse après le fichier et la règle de fin arrêterait
chaque impression.

## Pourquoi

Les fins du 15 septembre (document 81), du 31 octobre et du 1er novembre 2026
(document 104, ADR-076) ont mal tourné sur T1A. Chaque fois, le CFS signalait
un défaut de filament sur le slot qui imprimait normalement, tête chargée, puis
la routine stock « extrude all material, last_cmd: T1A » a poussé du filament
après la fin du fichier :

- le 15 septembre, dans le `BOX_END` de la fin stock : 80 mm toutes les 40 s,
  25 fois, environ 2 m ;
- le 31 octobre, après l'échec de la fin V4 : douze cycles de 19:08:17 à
  19:15:44, jusqu'à l'arrêt d'urgence de Thomas ;
- le 1er novembre, buse en chauffe : arrêtée dès sa première poussée par la
  surveillance PC, moins de 0,2 mm poussé.

Parmi les maillons du document 104, la garde agit sur le premier :
l'auto-remplacement resté actif sur un slot contredit. Elle y ajoute l'arrêt sur
toute poussée après la fin, la règle de la surveillance PC rendue permanente.
Le faux défaut lui-même tient au matériel et reste hors de sa portée.

Une vraie fin de bobine se prouve vite : le masque `connections` du CFS perd le
bit du slot, ou une ligne `extrude = N` seule suit. Le 31 octobre, la vraie fin
de T1B s'est prouvée à +33 s. Le 13 septembre, la même suite de réponses
(document 80) l'aurait prouvée à +81 s si T1B imprimait, à +1 s si c'était
T1A ; aucune trace de la tête ne confirme une vraie fin ce jour-là.

## Pendant l'impression

Un épisode s'ouvre sur un slot quand :

- le CFS de la route engagée répond `FILAMENT_ERR` (0x50) à une demande
  d'état ;
- une ligne `recode_err: filament_err` ou `error: filament_err` cite le slot
  (`'tnn': 'T1A'`), même hors route ;
- une tension (`filament_err_tighten_up_event`) arrive sur la route engagée ;
- le masque `material` du CFS de la route n'a plus le bit du slot.

Le masque `connections` sans le bit du slot, ou la ligne de queue, rendent
l'épisode réel : la bobine est vraiment finie, la garde ne fait rien et le
relais stock reste possible. Le masque `material` seul ne prouve rien : le
31 octobre, il donnait A absent pendant que T1A imprimait.

Un épisode encore suspect après 180 s et 400 mm imprimés pendant l'épisode,
tête chargée (`filament_sensor_2`), marque l'impression, une seule fois.
`BOX_ENABLE_AUTO_REFILL ENABLE=0` part sous le verrou G-code, puis deux
lectures fraîches doivent donner 0 ; la console nomme alors le slot, avec
l'issue de la coupe. Si l'auto-remplacement revient à 1 avant la fin (l'écran
renvoie `ENABLE=1` à sa connexion), la garde le recoupe, au plus toutes les
10 s. Une fois le fichier fini, l'auto-remplacement appartient à la fin K1
Control et la garde n'y touche plus.

Les millimètres comptent seulement en `printing`, sur la position E prévue de
l'extrudeur, à marée haute : une rétraction et sa reprise comptent une fois.
Un épisode se ferme quand le CFS répond deux fois OK de suite, sans nouveau
signalement depuis 15 s, sans masque `connections` récent et sans slot absent
du masque `material`.

## Après la fin du fichier

La fenêtre de fin s'ouvre quand le fichier finit (`complete`, `cancelled`,
`error`, `standby`, ou `paused` sans fichier ouvert). Elle dure 15 min comptées
depuis la sortie de la fin K1 Control de ses phases actives. Une poussée nette
de plus de 1 mm hors des étapes qui poussent exprès (`cutting`, `rewinding`,
`finalizing` de `kctrl_end`) arrête la machine. L'arrêt part avant la mise en
file du mouvement : rien de cette poussée ne sort.

C'est la règle de la surveillance PC (`end-watch-v1`) rendue permanente, et
plus stricte : rien n'est permis en `waiting` ni en `heating`. Une rétraction
ne donne pas de crédit à une poussée suivante. La fenêtre vaut aussi après une
annulation.

Le 31 octobre, la garde aurait marqué l'impression à 19:05:34 (T1A, 248 s,
403 mm) et coupé l'auto-remplacement. La fin V4 a échoué à 19:07:42, après un
`key839` à 19:07:36, pendant la coupe ; la routine stock a poussé dès 19:08:17
et la garde l'aurait arrêtée à sa première poussée. Rien ne prouve que la
coupe aurait empêché cette routine : la sûreté de la fin repose sur l'arrêt.

## Au départ suivant

`START_PRINT` remet l'auto-remplacement coupé par la garde, prouvé par deux
lectures à 1, avant que le départ continue ; sinon il refuse le départ. Une fin
K1 Control encore en cours refuse aussi le départ.

## Messages console

- `K1 Control: capteur du slot T1A contredit (248 s, 403 mm imprimes, tete
  chargee).`, suivi sur la même ligne de l'issue de la coupe :
  - `Auto-remplacement CFS coupe et relu a 0, retabli au prochain
    START_PRINT. Une vraie fin de bobine donnera une pause.` ;
  - `Auto-remplacement CFS commande a 0 sans relecture a 0, nouvel essai tant
    qu'il est lu a 1.` ;
  - `Auto-remplacement CFS deja coupe, laisse tel quel. Une vraie fin de
    bobine donnera une pause.` ;
  - `Fin deja lancee: l'auto-remplacement reste a la fin K1 Control.` ;
  - `Coupe de l'auto-remplacement CFS impossible (voir le journal), nouvel
    essai tant qu'il est lu a 1.`
- `K1 Control: auto-remplacement CFS relu a 1 pendant l'impression marquee,
  recoupe`, la première fois seulement.
- `K1 Control: fin du fichier, garde de fin active 15 min. Une poussee de
  filament hors des etapes de fin arrete la machine.
  KCTRL_SENSOR_GUARD_RELEASE avant une poussee a la main.`
- `!! K1 Control: poussee de filament apres la fin, arret d'urgence` : l'arrêt.
- `K1 Control: garde capteur aveugle, aucune reponse du CFS depuis 60 s`, ou
  `..., niveau du journal au-dessus de INFO`, une fois par impression.

En dehors de l'arrêt et des refus de `START_PRINT`, aucun texte de la garde ne
commence par `!!` ni ne contient `failed` : `kctrl_end` fait échouer sa fin sur
l'un ou l'autre. Un `START_PRINT` refusé par la garde affiche `!!` comme tout
refus Klipper ; pendant la fin K1 Control, c'est le refus que la fin V5 oppose
déjà elle-même.

## Commandes

À taper dans la console, sans bouton Mainsail :

- `KCTRL_SENSOR_GUARD_STATUS` : épisodes, marque, coupe, fenêtre de fin,
  crochet et route ;
- `KCTRL_SENSOR_GUARD_RELEASE` : lève la fenêtre de fin avant une poussée, un
  chargement ou un retrait à la main. Pendant la fin K1 Control, la garde reste
  et le dit.

Ces commandes répondent sans jamais lever d'erreur. L'état se lit aussi dans
`printer.kctrl_sensor_guard` : `hook`, `episodes`, `marked`, `cut`, `recuts`,
`auto_refill_restore_pending`, `end_window`, `end_window_left`, `end_level`,
`tripped`, `trip`, `blind`, `failure`, `route`, `tap_seen`, `tap_dropped`.

## Sources lues

Le module CFS stock écrit ses trames dans `klippy.log` au niveau INFO. La garde
pose sur le logger racine un handler qui ne garde que des événements analysés,
sans texte brut : réponses d'état (commande 0xa, taille 7), lignes nommées,
tension, masques, ligne de queue. Les trames qui portent des identifiants
(autres commandes, autres tailles) ne correspondent jamais. La garde n'écrit
jamais sur la liaison CFS : sa seule commande au module stock est
`BOX_ENABLE_AUTO_REFILL`. Rien n'est écrit sur le disque.

La route vient de `box`, avec les règles de `kctrl_end.live_route`, la tête de
`filament_switch_sensor filament_sensor_2`, les millimètres de la position du
toolhead. Un tic par seconde.

La garde se dit aveugle quand le CFS de la route ne répond plus depuis 60 s
pendant l'impression, ou quand le niveau du logger racine passe au-dessus de
INFO. Aveugle, elle prévient une fois et ne marque pas.

Le crochet se pose sur `extruder.check_move`. Si la garde à froid
(`cold-push-guard-v1`) est déjà posée, la garde capteur se glisse entre elle et
le contrôle stock, et la garde à froid garde `cold_installed` vrai ; sinon elle
se pose directement et la garde à froid vient l'envelopper. Quel que soit
l'ordre de démarrage, chaque contrôle appelle d'abord celui qu'il enveloppe :
le contrôle stock juge en premier, puis la garde capteur, puis la garde à
froid.

## Réglages

| Option | Défaut | Bornes | Rôle |
| --- | --- | --- | --- |
| `enabled` | `False` | | rien n'est posé tant qu'il est faux |
| `boxes` | `2` | 1 à 4 | CFS chaînés qui doivent être connectés |
| `episode_seconds` | `180` | 60 à 3600 | durée d'un épisode suspect avant la marque, en s |
| `episode_printed_mm` | `400` | 100 à 5000 | filament imprimé pendant l'épisode avant la marque |
| `blind_seconds` | `60` | 20 à 600 | silence du CFS de la route qui rend la garde aveugle, en s |
| `end_window` | `900` | 60 à 3600 | durée de la fenêtre de fin, en s |
| `end_push_limit` | `1.0` | 0,5 à 10 | poussée nette tolérée dans la fenêtre, en mm |
| `auto_refill_timeout` | `3` | 0,5 à 10 | délai des deux lectures concordantes, en s |

180 s laissent une marge de 2,2 sur le délai de preuve le plus long des
journaux lus, +81 s le 13 septembre si T1B imprimait. Les millimètres qu'une
vraie fin consomme avant sa preuve sont inconnus. Le capteur de tête a vu du
filament jusqu'à 19:00:56 le 31 octobre, plus de 4 min après la preuve de la
vraie fin de T1B : il ne départage rien et sert seulement de condition.

## Compromis

Une impression marquée garde l'auto-remplacement coupé pour tous les slots
jusqu'au prochain `START_PRINT`. Une vraie fin de bobine pendant cette
impression donnera donc probablement une pause au lieu d'un relais vers le
slot de secours : recharger, puis reprendre.

## Limites connues

- Seul l'E de l'extrudeur de tête est surveillé.
- Une poussée mise en file avant l'ouverture de la fenêtre ou après elle n'est
  pas vue, ni une poussée pendant une étape permise. Une poussée stock pendant
  `cutting` passe, comme une boucle stock dans le `BOX_END` de `finalizing`,
  la forme du 15 septembre. La fin V5 n'entre dans `BOX_END` qu'après deux
  lectures fraîches sans filament en tête ni route CFS, auto-remplacement
  coupé ; qu'il ne puisse plus y boucler reste inconnu. La sortie d'annulation
  qui garde le filament (ADR-074) tourne aussi en `finalizing`.
- Un nœud de filament ne se distingue pas d'un capteur faux.
- Seule une impression `virtual_sdcard` ferme la fenêtre : du G-code tapé ou
  envoyé après la fin compte comme après la fin.
- Une poussée, un chargement ou un retrait à la main dans la fenêtre arrête la
  machine : `KCTRL_SENSOR_GUARD_RELEASE` d'abord. Après un arrêt, Klipper
  quitte seul (bogue TMC Creality) et Thomas rallume.
- Un dé-rétract de `RESUME` après la fin arrête la machine au-delà de 1 mm.
- Imprimer sans `START_PRINT` arme quand même la fenêtre ; la marque et sa
  restitution suivent `START_PRINT`.
- Un `START_PRINT` refusé plus loin que la garde (fin K1 Control, départ
  stock) réarme la fenêtre ; un refus de la garde elle-même laisse tout en
  l'état.
- Une restitution en attente se perd au redémarrage de Klipper ; l'écran remet
  d'habitude l'auto-remplacement à 1 à sa connexion.
- Un épisode encore ouvert au `START_PRINT` repart de zéro (`carried`).
- Que l'auto-remplacement à 0 empêche la routine stock reste probable, pas
  prouvé (document 104).
- Une nouvelle étape de `kctrl_end` qui pousse exprès doit entrer dans
  `END_PUSH_PHASES`.
- Désactiver la fin V5 impose de désactiver d'abord la garde, sinon Klipper
  refuse de démarrer.
- Un `BOX_ENABLE_AUTO_REFILL` refusé fait afficher `!!` par Klipper à chaque
  essai, au plus toutes les 10 s pendant l'impression ; la garde ne l'envoie
  jamais pendant les phases de la fin K1 Control.
- Filtrer le bavardage CFS du journal (option 4 du document 103) doit se faire
  au handler du fichier, jamais au logger racine, qui rendrait la garde
  aveugle. Un niveau racine au-dessus de INFO se voit (`log_level`) ; un filtre
  posé sur le logger racine ne se verrait qu'en `no_cfs_reply`, après 60 s
  d'impression.
- Les déclencheurs de la surveillance PC sur le refus du bac et sur la cible
  chaude tenue 15 min ne sont pas repris.
- Hypothèse : `BOX_ENABLE_AUTO_REFILL` pendant l'impression ne fait que poser
  le drapeau.

Validation : **126 tests ciblés verts** (`tests/test_kctrl_sensor_guard_v1.py`) :
faux Klipper sur horloge simulée, aucun réseau, aucun SSH. Ils rejouent à la
seconde, sur les chronologies du document 105, les fins du 15 septembre, du
31 octobre et du 1er novembre, la vraie fin de T1B du 31 octobre, la suite du
13 septembre et des impressions saines. Les lignes CFS sont synthétiques, sans
identifiant. Le rejeu du 15 septembre place les poussées stock après une fin
K1 Control que la K1 n'avait pas ce jour-là. Chacun des 18 mutants du module,
joués hors dépôt, en fait échouer au moins un.
