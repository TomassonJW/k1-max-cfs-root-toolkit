# ADR-077 - Un capteur CFS contredit marque l'impression ; après la fin, toute poussée hors des étapes K1 Control arrête la machine

Date : 1er novembre 2026. Statut : accepté ; construite et testée hors
imprimante, pas posée.

## Contexte

Trois fins ont poussé du filament après le fichier, sur T1A : le 15 septembre
(document 81), le 31 octobre et le 1er novembre (document 104). Chaque fois, le
CFS signalait un défaut de filament sur une bobine pleine qui imprimait
normalement, tête chargée, auto-remplacement actif ; puis la routine stock
« extrude all material, last_cmd: T1A » a poussé. La garde à froid (ADR-076)
refuse ces poussées buse froide, et la fin V5 coupe l'auto-remplacement avant
la coupe. Rien n'arrête une poussée buse chaude hors de la fin : le
1er novembre, seule la surveillance PC l'a arrêtée. Thomas demande une garde
dans Klipper, sans le PC, qui repère le capteur contredit et rend la fin sûre.

Le 31 octobre montre aussi une vraie fin de bobine : T1B, prouvée en 33 s par
le masque `connections` et la ligne de queue. Le même soir, le masque
`material` donnait A absente pendant que T1A imprimait une bobine pleine, et le
capteur de tête a vu du filament plus de 4 min après la preuve de la vraie fin
de T1B (document 105).

## Décision

Module Klipper `kctrl_sensor_guard`, paquet
`packages/k1-control-v1/cfs-sensor-guard-v1`, section `[kctrl_sensor_guard]`,
désactivé par défaut. Activé, il exige `[kctrl_end]` activé, sinon Klipper
refuse de démarrer.

1. Pendant l'impression, un signalement ouvre un épisode sur un slot : réponse
   `FILAMENT_ERR` du CFS de la route, ligne nommée, tension, masque `material`
   sans le slot. Le masque `connections` sans le slot, ou la ligne de queue, le
   rendent réel : la garde ne fait rien et le relais stock reste possible.
2. Un épisode de la route encore suspect après 180 s et 400 mm imprimés, tête
   chargée, garde non aveugle, marque l'impression une fois :
   `BOX_ENABLE_AUTO_REFILL ENABLE=0` sous le verrou G-code, deux lectures à 0
   en 3 s, recoupe au plus toutes les 10 s jusqu'à la fin du fichier. La
   console nomme le slot.
3. Après la fin du fichier, pour toute impression, annulation comprise : pendant
   15 min après la sortie de la fin K1 Control de ses phases actives, une
   poussée nette de plus de 1 mm hors de `cutting`, `rewinding` et `finalizing`
   demande l'arrêt de Klipper et lève une erreur dans `extruder.check_move`,
   avant la mise en file : rien n'en sort. `KCTRL_SENSOR_GUARD_RELEASE` lève la
   fenêtre avant une poussée à la main.
4. Au `START_PRINT` suivant, l'auto-remplacement coupé par la garde est remis,
   prouvé par deux lectures à 1, sinon le départ est refusé.
5. La garde lit le journal par un handler sur le logger racine, qui ne garde que
   des événements analysés. Elle ne parle au module stock que par
   `BOX_ENABLE_AUTO_REFILL` et n'écrit rien sur le disque.

## Alternatives écartées

- Faire confiance au masque `material` : le 31 octobre, il donnait A absente
  71 fois pendant que T1A imprimait une bobine pleine.
- Départager par le capteur de tête : il voit du filament tant que le tube en
  contient.
- Couper l'auto-remplacement dès le premier signalement : la vraie fin de T1B
  du 31 octobre aurait perdu son relais.
- Filtrer le bavardage CFS au logger racine : la garde deviendrait aveugle.
- Garder la seule surveillance PC : elle exige le PC allumé et connecté pendant
  chaque fin.

## Conséquences

- Une impression marquée garde l'auto-remplacement coupé pour tous les slots
  jusqu'au prochain `START_PRINT` : une vraie fin de bobine pendant cette
  impression donnera probablement une pause au lieu d'un relais. Une vraie fin
  prouvée en plus de 180 s aurait le même effet ; le plus long délai de preuve
  lu vaut 81 s.
- Contrôle stock, garde capteur, puis garde à froid jugent chaque poussée, dans
  cet ordre, quel que soit l'ordre de démarrage.
- Désactiver la fin V5 impose de désactiver d'abord la garde.
- Pose seulement après la pose de la fin V5 et la validation de sa première
  fin, au repos revérifié, Thomas présent, préflight d'abord. Ordre : garde à
  froid (en service), fin V5, garde capteur ; retour arrière dans l'ordre
  inverse, garde capteur d'abord.
- Une boucle stock dans le `BOX_END` de `finalizing`, la forme du 15 septembre,
  n'est pas bornée, ni une poussée stock pendant `cutting`.
- Une poussée à la main dans la fenêtre arrête la machine :
  `KCTRL_SENSOR_GUARD_RELEASE` d'abord. Après un arrêt, Klipper quitte seul
  (bogue TMC Creality) et Thomas rallume.
- Filtrer le journal (option 4 du document 103) se fera au handler du fichier.
