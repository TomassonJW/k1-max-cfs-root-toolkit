# 77 — Quatre vis seulement : `KCTRL_SCREWS_ONLY`

Date : 2026-09-11, 20:40 à 21:00. Écrit et installé le soir même, machine à
l'arrêt, sur la demande de Thomas : « je veux juste voir si les 4 vis sont de
niveau les unes par rapport aux autres, rien d'autre ».

## Ce qui s'est passé dans la nuit

Un boulon du plateau perdu, remis, et trois relevés `KCTRL_MESH_CALIBRATE`
(02:38, 03:08, 03:33). Les trois sont propres en eux-mêmes (121 contacts,
résidus 0,03–0,05 mm) mais le plateau, lui, n'était pas le même d'un relevé à
l'autre :

| | 10 sept. 20:57 | 02:38 | 03:08 | 03:33 |
|---|---|---|---|---|
| amplitude | 0,36 | 1,43 | 1,40 | 1,16 |
| pente avant → arrière | ~0 | -1,05 (avant haut) | -1,12 | +0,86 (avant bas) |
| bord avant, creux au milieu | 0,06 | — | 0,3 | 0,5 |
| décalage entre quadrants avant et arrière | 0,03–0,05 | 0,56 | 0,39 | 0,25 |

La dernière ligne compte le plus : une seule prise d'origine Z par relevé,
donc un décalage de 0,25 mm entre les quadrants avant et arrière veut dire
que le plateau a bougé pendant la mesure. Et un bord avant plat la veille qui
creuse de 0,5 mm au milieu, c'est une tôle pliée par ses fixations, pas un
voile. La pente, le maillage l'absorbe ; la torsion et le mouvement, non.

## Pourquoi pas `KCTRL_BED_SCREWS`

Elle palpe 25 points et lit les hauteurs de vis dans le profil enregistré.
Le firmware incline chaque profil enregistré de 0,10 mm avant/arrière (doc
73) : le rapport sous-estime la pente entre vis de 0,2 mm, plus que le
huitième de tour qu'on cherche (0,0875 mm). Et 25 points, c'est cinq minutes
par passe.

## Ce qui est écrit

| Fichier | Rôle |
|---|---|
| `packages/k1-control-v1/mesh-acquisition-v2/kctrl_mesh.py` | `KCTRL_SCREWS_PROBE` : quatre `PROBE` aux positions mesurées des vis (paire arrière à X 48,5 / 246,5, pas aux coins), contacts bruts, hors rampe du firmware ; rapport en huitièmes de tour partagé avec le rapport 25 points (`_report_heights`) ; refuse pendant une impression, sans homing, sans sonde |
| `packages/k1-control-v1/mesh-acquisition-v2/k1-control-mesh-reference-v2.cfg` | `KCTRL_SCREWS_ONLY` : lit à température, homing, maillage vidé, `KCTRL_SCREWS_PROBE`, buse coupée, **lit gardé chaud**, plateau descendu à Z90 |
| `tests/test_kctrl_screws_only_v1.py` | 16 tests : positions exactes et ordre, levée entre les points, rapport et tours, refus, macro (ordre, pas de `BED_MESH_CALIBRATE`, lit chaud, pas de `#` dans une chaîne) |

## Pour la console

```
KCTRL_SCREWS_ONLY                 quatre contacts, rapport, plateau descendu, lit gardé à 55 C
KCTRL_SCREWS_ONLY BED_TEMP=60     autre température
TURN_OFF_HEATERS                  quand les vis sont finies
```

Rapport attendu :

```
K1 Control: probing the 4 screws only, raw contacts, travel Z5.0
K1 Control: avant-gauche X18.5 Y23.7 contact at +0.1750 mm
...
K1 Control: screw heights span 0.1750 mm; M4 pitch 0.70 mm, so one eighth of a turn is 0.0875 mm
K1 Control: VISSER (eloigne le plateau) - a faire
   avant-gauche     X18    Y24     +0.1750 mm  ->  visser 2.0 huitiemes
   ...                                          ->  ne pas toucher
K1 Control: DEVISSER (rapproche le plateau) - variante inverse
```

Le bloc VISSER ramène chaque vis à la plus basse : c'est celui qui protège
le boulon fragile, puisqu'on ne desserre jamais. Une passe : chauffe de la
buse à 190, deux homings, quatre contacts, environ trois minutes.

## Vis de niveau ne veut pas dire plateau plat

Les vis fixent quatre points. Entre eux, la tôle a sa forme : dilatation à
chaud (une face plus chaude que l'autre bombe), la feuille magnétique, et
surtout la contrainte des vis quand les quatre points de fixation ne sont pas
dans le plan du châssis : serrer tord la plaque. C'est ce qu'on a vu cette
nuit. Les vis servent à mettre les quatre coins à la même hauteur **sans
forcer** ; le maillage fait le reste, à condition que la plaque ne bouge
plus.

## Installé

11 septembre, 20:45, machine à l'arrêt (`standby`, froide, non homée) :
sauvegardes `.bak-20260911-2050` des deux fichiers, copies aux md5 du dépôt,
module rechargé, `KCTRL_SCREWS_ONLY` et `KCTRL_SCREWS_PROBE` dans `help`.
Première exécution réelle : à observer (le `PROBE` seul de PRTouch n'a pas
encore été vu tourner hors `BED_MESH_CALIBRATE` sur cette machine).
