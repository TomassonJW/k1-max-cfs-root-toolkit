# ADR-072 — Après un changement raté, RESUME recharge sans alarme de fin de bobine

Statut : **installé et validé au repos le 24 septembre 2026** (`resume-reload-guard-v1`).
Pas encore observé sur une vraie reprise après changement raté. Document 99.

## Constat

Le 23 septembre au soir, un changement de filament en cours d'impression a
échoué (`key837`) et le firmware a mis l'impression en pause. Au RESUME,
`virtual_sdcard` exécute d'abord le rechargement de l'emplacement logique du
changement raté (`resume_tnn`, ici `T1A`), puis reprend le fichier.

Ce rechargement retire puis réinsère le filament. À 23:06:43 il retire ; à
23:06:44 le capteur de tête se vide. L'alarme de fin de bobine était armée
(`START_PRINT` l'arme pour la relève) : Klipper déclenche une pause de fin de
bobine. Cette pause prend le verrou G-code et attend l'arrêt du fichier
(`do_after_pause: waiting printing to pause`, une ligne par seconde). Le
fichier, rechargement et purge terminés à 23:08:01, attend ce verrou pour
exécuter sa ligne suivante. Chacun attend l'autre : impression figée.

ADR-065 coupait déjà cette alarme autour des changements `T0`..`T15` du
fichier. Le rechargement de reprise n'est pas un `Tn` : c'est `T1A`..`T4D`,
routé par `gcode.py` vers le même gestionnaire du module CFS, et il n'était
pas protégé.

## Décision

`kctrl_tool_change` enveloppe aussi les seize commandes `T1A`..`T4D` :

1. si l'alarme de tête est armée, elle est coupée ;
2. la commande stock s'exécute telle quelle ;
3. `M400`, puis l'alarme est rallumée, même si la commande échoue.

Rien d'autre. Pas d'alignement de fiche, pas de refus, pas de contrôle, pas
de `last` (la fin et le départ le lisent), pas de `PAUSE` et aucune exception
propre à l'enveloppe :

- `virtual_sdcard` exécute ce rechargement **hors** de son `try` qui arrête
  proprement une impression sur erreur : une exception ajoutée ici ferait
  plus de dégâts que le problème corrigé ;
- après ce rechargement, `virtual_sdcard` exécute encore une ligne du fichier
  avant de regarder une pause : une `PAUSE` ajoutée ne tomberait pas au bon
  endroit.

Un rechargement qui échoue de nouveau reste traité par le firmware, comme le
changement d'avant : pause à l'écran, puis RESUME possible. Pendant
`START_PRINT`, la commande stock s'exécute seule.

Les commandes sont reprises au chargement du module et, pour celles que le CFS
aurait enregistrées plus tard, à `klippy:ready`. Le journal de la pose montre
que les seize sont déjà là au chargement.

## Conséquences

- Le RESUME après un changement raté ne peut plus se bloquer sur l'alarme de
  fin de bobine.
- Pendant le seul rechargement, une vraie fin de bobine n'est pas signalée par
  l'alarme ; la commande stock lit toujours le capteur et l'alarme revient
  dès la fin des mouvements.
- La cause matérielle des `key837` (prise du CFS) n'est pas traitée ici : un
  changement peut encore échouer ; il redevient récupérable par RESUME.
- `KCTRL_TOOLS` affiche les rechargements protégés et le dernier rechargement ;
  l'état Klipper expose `reloads` et `last_reload`.
- Une pose de module Klipper ne se fait qu'au repos : un redémarrage de
  Klipper pendant une impression coupe les moteurs et perd la pièce.
