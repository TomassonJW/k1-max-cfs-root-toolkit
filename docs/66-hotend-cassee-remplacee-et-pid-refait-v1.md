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

## Activation vérifiée — 8 septembre, 23:41

Redémarrage de Klipper, revenu prêt en 14 secondes. Relu depuis la machine
après redémarrage :

```
PID actif       : Kp 20.695  Ki 1.533  Kd 69.844
input_shaper    : x = ei 42.6 Hz | y = mzv 46.6 Hz
avance pression : 0.04
```

Les trois écritures manuelles de la soirée sont donc actives ensemble.

**La table des bobines a survécu** au redémarrage, contrairement à ce qui était
attendu : `T1A -> T1B`, cohérent avec le dernier choix enregistré. Rien n'a eu à
être repositionné.

Précision utile pour la suite : `save_config_pending` reste à `true` en
permanence sur cette machine, mais pas à cause de nos valeurs. Le firmware
prépare en boucle une écriture de `[auto_addr] mb_addr_table_uniids`, visible
dans le journal juste après chaque démarrage. Ce drapeau n'est donc pas un
indicateur fiable de « quelque chose de nous est en attente ». Et depuis ce
redémarrage, la mémoire contient nos valeurs relues du fichier : un
`SAVE_CONFIG` accidentel ne les écraserait plus — il reste interdit pour les
autres raisons connues.

## Décisions de Thomas sur le reste

**Avance de pression : inchangée à `0,04`, volontairement.** Elle a déjà été
mesurée plusieurs fois, avec des configurations différentes, et redonne toujours
la même valeur pour ce filament — ce qui est le comportement attendu, l'avance
de pression étant une propriété du couple filament/hotend et non un réglage
libre. Le vrai manque est ailleurs : une valeur unique ne convient pas à la fois
aux petits et aux gros débits. L'adaptatif se règle dans le trancheur, qui émet
des valeurs différentes selon le débit ; chantier séparé, non ouvert ici.

**Zéro Z : inchangé.** Thomas confirme que l'écart est identique après
remplacement, la correction `+0,05 mm` du profil `k1_p001_t055_r001_n11x11` est
conservée.
