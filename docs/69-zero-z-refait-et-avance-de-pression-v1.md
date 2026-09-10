# 69 — Le zero Z refait apres la hotend, et l'avance de pression

Etat : le zero Z est regle, accepte a la main et enregistre. L'avance de
pression est en cours de mesure sur une tour imprimee le 9 septembre.

## 1. Pourquoi il fallait le refaire

La hotend a ete remplacee (document 66). Le PID a ete refait dans la foulee,
mais pas la hauteur de premiere couche. Une buse neuve ne se retrouve pas au
meme endroit que l'ancienne au millimetre pres, et la premiere couche s'en
ressentait.

## 2. Le piege : une buse trop basse ressemble a une buse bouchee

C'est le point a retenir de la journee, et je m'y suis trompe.

La premiere couche d'essai ne sortait presque rien. Le diagnostic naturel est
« buse bouchee ». Verifie et ecarte : l'extrudeur poussait bien, 1.1 mm/s, la
progression montait, aucune erreur. J'en ai conclu que la buse etait **trop
haute** et j'ai descendu l'offset. C'etait l'inverse.

Sur cette machine, quand la buse est **trop basse**, le plastique n'a pas la
place de sortir. Le resultat visuel est exactement celui d'un bouchage :
extrusion invisible, filets absents. Thomas l'a vu a la main et a tranche :
il fallait monter, pas descendre.

Convention de signe, une bonne fois : une valeur de `homing_origin.z` **plus
grande** = plus d'espace entre la buse et le plateau. Et sur la K1 Max, c'est
le plateau qui descend, la buse ne monte pas.

## 3. La valeur retenue

**+0.145 mm** pour le profil de maillage `k1_p001_t055_r001_n11x11`.

Trouvee a la main, en corrigeant l'offset pendant l'impression d'un carre de
80x80 mm en une seule couche de 0.2 mm. Entre +0.14 et +0.15 la couche est
propre ; +0.145 est le milieu. La valeur precedente etait +0.05.

Enregistree par `KCTRL_Z_SAVE PROFILE=k1_p001_t055_r001_n11x11 Z=0.145` :

```
// K1 Control: Z 0.1450 saved for k1_p001_t055_r001_n11x11
save_variables.z_k1_p001_t055_r001_n11x11: 0.145
```

Aucun `SAVE_CONFIG` n'intervient — il est interdit sur cette machine, il
reecrirait le bloc `#*#` et effacerait le PID et l'input shaper edites a la
main. La valeur vit dans `save_variables` et `START_PRINT` la relit a chaque
depart (ADR-057).

Preuve qu'elle est bien appliquee : au demarrage de la tour d'avance de
pression, `gcode_move.homing_origin[2]` passe de `0.000` a `0.145` au moment
ou `START_PRINT` prend la main.

## 4. Ce que vaut le palpeur apres le remplacement

Cinq contacts a 150,150 : etendue 0.046 mm, ecart type 0.015 mm. C'est bon.
Le probleme de premiere couche ne venait donc pas d'un palpeur bruyant mais
bien d'un zero decale.

## 5. L'avance de pression

Valeur en place avant la mesure : `0.04`.

Tour imprimee : `/usr/data/printer_data/gcodes/kctrl-tour-avance-de-pression.gcode`,
40x40 mm, 250 couches de 0.2 mm soit 50 mm de haut, un seul perimetre a
100 mm/s, trois premiers anneaux ralentis a 30 mm/s, ventilateur a fond a
partir de la deuxieme couche.

```
TUNING_TOWER COMMAND=SET_PRESSURE_ADVANCE PARAMETER=ADVANCE START=0 FACTOR=0.002
```

L'avance vaut donc `0.002 x hauteur_en_mm` : 0 en bas, 0.100 en haut.

**Lecture** : trouver la hauteur ou les angles sont les plus nets — ni bourrelet
au sortir du virage, ni creux avant. Mesurer cette hauteur au pied a coulisse
depuis le plateau, multiplier par 0.002.

**Application**, une fois la valeur lue :

```
SET_PRESSURE_ADVANCE ADVANCE=<valeur>
```

et pour la rendre permanente, edition a la main de `pressure_advance` dans le
bloc `[extruder]` de `printer.cfg`, avec sauvegarde prealable — comme cela a
ete fait pour le PID et l'input shaper. Pas de `SAVE_CONFIG`.

## 6. Avertissement en cours

`save_config_pending: True` sur la machine, avec `prtouch_v2 z_offset: -0.005`
et un bloc `auto_addr`. Ne pas le declencher. Le zero Z retenu ici ne passe pas
par la et n'en a pas besoin.
