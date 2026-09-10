# 72 — Résonances mesurées après l'impression du 10 septembre (plateau plié)

Date : 2026-09-10, 02:05 à 02:23. Campagne complète exécutée à froid sur la
machine avec les scripts de `experiments/2026-09-08-resonance-tete-modifiee/`.
Mesures brutes dans `experiments/2026-09-10-resonance-apres-plateau-plie-mesures/`.
Demandée par Thomas après l'annulation de l'impression de 01:45 (première
couche ratée, plaque du plateau déformée, zéro Z à refaire).

## Résultat : rien n'a bougé côté vibrations

| Axe | 8 septembre (appliqué) | 10 septembre (mesuré) | Écart |
|---|---|---|---|
| X, filtre `ei` | 42,6 Hz, 22,3 % restant, accél. 3 380 | 42,8 Hz, 19,6 % restant, accél. 3 412 | +0,2 Hz |
| Y, filtre `mzv` | 46,6 Hz, 0,0 % restant, accél. 6 397 | 47,0 Hz, 0,1 % restant, accél. 6 507 | +0,4 Hz |
| Courroie A | pic 44,7 Hz, largeur 8,9 | pic 44,3 Hz, largeur 8,9 | -0,4 Hz |
| Courroie B | pic 44,7 Hz, largeur 8,9 | pic 44,3 Hz, largeur 10,4 | -0,4 Hz |

Les deux courroies restent à la même fréquence (écart 0,0 Hz) : tension
comparable, rien à reprendre. La déformation du plateau n'a pas touché la
mécanique X/Y : les résonances de la tête sont celles du 8 septembre à moins
d'un demi-hertz, ce qui est dans le bruit d'une mesure à l'autre.

## Décision : valeurs inchangées

`ei 42,6 Hz` sur X et `mzv 46,6 Hz` sur Y restent en place. Passer à 42,8 /
47,0 ne changerait rien de mesurable ; changer la configuration sans gain
n'a pas de sens. Le rapport propose `zv 48,0` sur X comme au 8 septembre : même
réponse qu'alors, 33 % de vibrations restantes, écarté.

## Ce que la machine a fait pendant la campagne, et ce qui a été remis

Comme le 8 septembre, `SHAPER_CALIBRATE` a réécrit le bloc `#*#` de
`printer.cfg` de sa propre initiative avec `ei 55,8` sur les deux axes (la
valeur `ei` de Y recopiée sur X). Le fichier a été remis à l'identique depuis
la sauvegarde `printer.cfg.bak-avant-resonance-20260910-020552` (md5
`106a0951…` des deux côtés, relu), et les valeurs vivantes réaffirmées par
`SET_INPUT_SHAPER SHAPER_TYPE_X=ei SHAPER_FREQ_X=42.6 SHAPER_TYPE_Y=mzv
SHAPER_FREQ_Y=46.6` (réponse `ok`). Aucun `SAVE_CONFIG`, aucun redémarrage.
Les deux capteurs de filament ont été réactivés (relu `enabled: True`).
Tête laissée en X150 Y150 Z10, référencée, froide.

Rappel du piège : `save_config_pending` reste levé jusqu'au prochain
redémarrage ; un `SAVE_CONFIG` réécrirait `ei 55,8`. Interdit, comme avant.

## Ce qui reste, hors de ce document

Le plateau : inspection de la plaque, mesh complet 11x11 à 55 °C, puis zéro Z
remesuré (`KCTRL_Z_SAVE`). Voir STATE.
