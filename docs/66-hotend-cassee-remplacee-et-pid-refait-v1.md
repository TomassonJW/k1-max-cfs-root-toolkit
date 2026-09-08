# 66 — Hotend cassée, remplacée, PID refait

Date : 2026-09-08, soirée. Panne diagnostiquée à distance, pièce remplacée par
Thomas, PID mesuré et écrit.

## La panne

Juste après la campagne de résonance, la buse ne montait plus en température.
Relevé à distance :

| | Valeur |
|---|---|
| Température buse | `27,3 °C` |
| Consigne | `100 °C` |
| Puissance commandée | `1,00`, soit le maximum |
| Variation sur 30 s | `+0,4 °C` |
| Plateau | `49,8 °C` pour une consigne de `50`, normal |

Chauffage commandé à fond, aucune montée, alors que le plateau chauffait
normalement : la carte et l'alimentation étaient donc hors de cause. Le
diagnostic annoncé était la cartouche chauffante ou son câblage, c'est-à-dire
précisément ce qu'on débranche en changeant la buse.

Signe annexe : un `M104 S0` envoyé pour couper la consigne est resté sans
réponse au bout de 30 secondes. La file de commandes était bloquée, très
probablement par une attente de chauffe qui ne pouvait pas aboutir.

**Constat de Thomas après démontage : les fils étaient dessoudés de la hotend.**
Rupture mécanique, pas une erreur de remontage. Hotend remplacée par une pièce
de rechange identique.

## Ce qu'il fallait refaire, et ce qu'il ne fallait pas

Les résonances **n'ont pas été refaites**, et c'est volontaire : une hotend de
rechange identique ne change ni la masse ni la raideur de la tête, qui sont les
seules grandeurs que mesurent ces balayages. Les valeurs du 8 septembre restent
valables (`ei 42,6 Hz` sur X, `mzv 46,6 Hz` sur Y).

Le PID de la buse, lui, devait être refait : la cartouche chauffante et la sonde
sont neuves, et les coefficients en place avaient été réglés pour les
précédentes.

## Le PID

`PID_CALIBRATE HEATER=extruder TARGET=220`, 195 secondes.

| | Avant | Après |
|---|---|---|
| `pid_Kp` | `25,013` | `20,695` |
| `pid_Ki` | `2,566` | `1,533` |
| `pid_Kd` | `60,966` | `69,844` |

Moins de proportionnel et d'intégral, plus de dérivé : la nouvelle hotend réagit
plus vite, la régulation est donc adoucie et davantage amortie.

Les valeurs sont écrites à la main dans la section `[extruder]` de `printer.cfg`,
`SAVE_CONFIG` étant interdit ici. Sauvegarde :
`printer.cfg.bak-avant-pid-20260908-233200`. Relecture vérifiée après écriture.

**Elles ne sont pas encore actives** : `PID_CALIBRATE` restitue l'ancienne
régulation en fin de mesure, et le fichier n'est relu qu'au démarrage. Un
redémarrage de Klipper est nécessaire — il effacera au passage la table des
bobines du CFS, qu'il faudra repositionner avec `KCTRL_SLOT`.

## Reste à faire avant d'imprimer

Le zéro Z et l'avance de pression (`0,04`) sont à reprendre : la pointe de la
buse n'est plus à la même hauteur et la zone de fusion a changé.
