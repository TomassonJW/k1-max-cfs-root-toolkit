# Les ondulations des couches 2 et 3 — ce que dit l'input shaping

Statut : diagnostic. Rien n'a été modifié sur la machine. La mesure décisive
demande une opération physique et l'accord de Thomas.

## Ce qui a déclenché ce document

Le document 58 attribuait les ondulations au maillage et proposait un
départage en dix secondes : mesurer la longueur d'onde à la règle. Environ
30 mm désignait le maillage, environ 5 mm la résonance.

Thomas a mesuré : **3 à 10 mm**. Le maillage est écarté, définitivement — ses
points sont espacés de 29 mm, il ne peut rien produire de plus serré. Il ajoute
une observation qui compte plus que la première : le défaut est sur les
couches 2 et 3, et **il a disparu à la couche 4**.

## Réponses directes

### Modifier le maillage n'a aucun effet sur l'input shaping

Aucun. Ce sont deux mécanismes qui ne se parlent pas.

Le maillage est une carte d'altitudes : il corrige le Z pendant que la buse se
déplace, pour suivre les creux et les bosses du plateau. L'input shaping est un
filtre sur les ordres de mouvement X et Y : il découpe chaque accélération en
impulsions décalées dans le temps, pour que la seconde annule l'oscillation que
la première a lancée dans le châssis. Le filtre ne lit jamais le maillage, et le
maillage ne connaît pas les fréquences du châssis.

Corriger le maillage n'invalide donc pas le shaper. La crainte est infondée.

### Le décalage du moteur Z non plus

Même raison, en plus net : l'input shaping ne s'applique qu'à X et Y. Le Z n'est
pas filtré du tout. Un décalage sur le Z ne peut pas déplacer une fréquence de
résonance en X ou en Y.

### Celui de la machine n'est pas un vrai calibrage

C'est le point qui mérite qu'on s'y arrête. Voici ce que la machine porte :

```
#*# [input_shaper]
#*# shaper_type_y = ei
#*# shaper_freq_y = 57.2
#*# shaper_type_x = ei
#*# shaper_freq_x = 57.2
```

Deux axes, la même fréquence au dixième près. Sur une CoreXY, X et Y n'ont pas
la même masse en mouvement ni la même raideur : ils tombent rarement sur la même
fréquence, et jamais à 0,1 Hz près.

L'explication est dans la macro d'usine, telle qu'elle est installée :

```
gcode_macro inputshaper:
    G28
    G1 X150 Y150 F6000
    G1 Z10 F600
    SHAPER_CALIBRATE AXIS=y
    CXSAVE_CONFIG
```

Elle ne mesure que **Y**. Le 57,2 Hz de X n'a jamais été mesuré : c'est une
recopie. Et une seconde macro, `autotune_shapers`, impose `'ei'` comme type de
filtre avant même la mesure — le choix du filtre n'est pas déduit des données
non plus.

Autrement dit : la moitié du calibrage a été faite, et l'autre moitié a été
remplie avec la première. Oui, il y a mieux à faire, et ce n'est pas un réglage
exotique — c'est simplement le calibrage complet.

L'accéléromètre est en place en permanence : `[adxl345]` sur `nozzle_mcu`,
`[resonance_tester]` configuré avec un point de sonde au centre du plateau. Il
n'y a aucun matériel à monter. Mesurer X prend quelques minutes.

## Mais la disparition à la couche 4 ne colle pas avec des vibrations

C'est là qu'il faut être honnête plutôt que rapide.

Des vibrations ne s'arrêtent pas parce que la pièce monte. Un défaut de
résonance est présent à toutes les hauteurs, aux mêmes vitesses. S'il s'arrête
net à la couche 4, quelque chose d'autre s'arrête à la couche 4.

Trois réglages du travail en cours s'arrêtent exactement là :

| Réglage | Valeur | Ce qui change à la couche 4 |
| --- | --- | --- |
| `bottom_shell_layers` | 3 | Fin du fond plein : plus aucune surface pleine à regarder |
| `slow_down_layers` | 3 | Fin de la montée en vitesse : la couche 4 est la **première** à pleine vitesse |
| `full_fan_speed_layer` | 3 | Le ventilateur atteint 100 % ; avant, il monte depuis 55 % |

La première ligne suffit à retourner la conclusion. À partir de la couche 4, le
remplissage passe à 15 % et il n'y a plus de surface pleine visible. **Ne plus
voir le défaut n'est pas la preuve qu'il a disparu** — c'est peut-être seulement
la preuve qu'il n'y a plus rien où le voir.

La deuxième ligne va plus loin et pointe dans l'autre sens. `slow_down_layers: 3`
fait démarrer la couche 1 lentement puis monte la vitesse jusqu'à la pleine
vitesse à la couche 4. Si le défaut était causé par la vitesse, la couche 4
serait la pire, pas la première propre. Le fait qu'il cesse au moment précis où
la machine atteint enfin 270 mm/s est un argument **contre** la vibration pure.

## Ce que la longueur d'onde dit quand même

Fréquence = vitesse ÷ longueur d'onde. Aux vitesses réellement pratiquées sur
ces couches :

| Vitesse | 3 mm | 10 mm |
| --- | --- | --- |
| 200 mm/s (couches 2-3, en montée) | 67 Hz | 20 Hz |
| 270 mm/s (remplissage plein, pleine vitesse) | 90 Hz | 27 Hz |

La bande 20–90 Hz encadre le 57,2 Hz du filtre. C'est compatible avec « le
shaper ne tue pas cette oscillation-là », en particulier sur l'axe qui n'a
jamais été mesuré. Ce n'est pas une preuve : la fourchette est trop large et la
vitesse exacte des couches 2 et 3 n'a pas été relevée.

## Le départage, sur la pièce déjà imprimée

Deux familles de défauts donnent des ondulations régulières, et l'ongle les
distingue mieux que l'œil :

- **Relief** — l'ongle accroche, le motif apparaît après un changement de
  direction et s'atténue en s'éloignant du virage : c'est de la vibration. Le
  calibrage de X est alors la bonne réponse.
- **Pas de relief, variation de largeur ou de brillance** — la surface est
  plane au toucher, le motif est uniforme sur toute la longueur sans lien avec
  les virages : c'est un débit qui module, pas un châssis qui oscille. Le
  shaper n'y changera rien.

## Ce qu'il faut faire, dans l'ordre

1. Passer l'ongle sur les couches 2-3 pour trancher relief ou pas relief.
2. Après l'impression en cours, mesurer réellement X :
   `SHAPER_CALIBRATE AXIS=x`, puis `AXIS=y` pour vérifier le 57,2 Hz existant.
   Opération physique et bruyante — accord de Thomas requis, machine à l'arrêt.
3. Appliquer le résultat avec `SET_INPUT_SHAPER`, puis reporter les valeurs à la
   main dans le bloc `#*#` de `printer.cfg`.

Le point 3 n'est pas de la coquetterie. `SHAPER_CALIBRATE` applique le résultat
immédiatement mais ne l'écrit pas ; c'est `CXSAVE_CONFIG` qui écrit, et cette
macro est la variante Creality de `SAVE_CONFIG`, interdite sur cette machine —
elle réécrit le fichier de configuration en entier et ce qu'elle en fait des
sections ajoutées n'a jamais été vérifié ici. L'écriture à la main donne le même
résultat sans le pari.

## Ce qui n'a pas été fait

Aucune mesure de résonance n'a été lancée : l'impression tourne (48 % au moment
du diagnostic). Les fréquences réelles de X et de Y sur cette machine restent
donc **inconnues**. La vitesse effective des couches 2 et 3 n'a pas été relevée
dans le fichier de travail, seule la règle de montée l'est. Rien n'a été écrit
sur la machine.
