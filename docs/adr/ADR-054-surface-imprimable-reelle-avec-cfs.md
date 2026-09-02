# ADR-054 — La surface imprimable réelle est 300 × 295, et les 5 mm manquants ne se reprennent pas

Date : 2026-09-02

Statut : **acceptée ; constat de configuration, aucun changement machine**

## Contexte

Une pièce de 297 × 297 refusait de s'imprimer, et une de 295 sortait déjà « de
la zone ». La machine annonce 300 × 300 × 300, donc l'écart n'était pas évident.

Relevé sur la machine, `printer.cfg` :

```
[stepper_x]  position_min: -2      position_max: 306.5
[stepper_y]  position_min: -0.5    position_max: 307.5   gcode_position_max: 295
[stepper_z]  position_min: -10     position_max: 305
```

`gcode_position_max` n'est pas une convention d'affichage. `virtual_sdcard.py`
relit chaque ligne du fichier pendant l'impression, et dès qu'un `G0`/`G1`
porte un `Y` supérieur à la valeur, il émet `key586 "Move out of gcode print
range"` et met l'impression en pause sur place :

```python
if cfs_enable or enforce_gcode_position_max:
    try:
        self.check_gcode_print_range(line, toolhead)
    except:
        self.gcode.run_script("PAUSE")
```

Le contrôle ne s'arme que si un CFS est déclaré — c'est le cas ici, avec deux
unités chaînées. Creality documente la même chose côté produit : 300 × 295 × 300
avec le CFS, contre 300 × 300 × 300 sans.

## Décision

**La surface utilisable est `X 0 → 300`, `Y 0 → 295`, `Z 0 → 300`.** La bande
`Y 295 → 307,5` est le couloir de service du CFS : coupe à `Y303,2`, purge à
`Y305`. Elle reste interdite au G-code.

**`gcode_position_max` n'est pas relevé.** Les cinq millimètres existent parce
que la tête traverse la bande arrière pour aller couper et purger, à la hauteur
courante. Une pièce qui dépasse `Y295` se fait labourer au premier changement de
filament. Le gain ne vaut pas le risque, et le garde-fou stock est le seul filet
qui reste si un fichier mal tranché passe.

**La zone imprimable du trancheur est déclarée à 300 × 295.** Le piège n'est pas
la limite mais le centrage : un trancheur qui centre sur un plateau de 300 place
un carré de 295 entre `Y2,5` et `Y297,5`, donc hors zone. Centré sur 300, le
maximum réel en `Y` tombe à `290`. Déclarer 300 × 295 recentre sur `Y147,5` et
rend les 295 pleins.

## Limite connue

Le contrôle ne lit que les lignes commençant par `G0` ou `G1`. Les arcs `G2`/`G3`
passent sans être examinés. Avec l'ajustement d'arcs activé dans le trancheur,
une pièce qui frôle le fond peut donc sortir de la zone sans pause ni message.
L'ajustement d'arcs reste désactivé sur ce parc.

Le contrôle ne regarde pas non plus `X` : au-delà de `X300` la tête reste dans
sa course mécanique jusqu'à `306,5` et imprimerait simplement à côté du plateau,
sans avertissement.

## Conséquences

- Aucune modification machine. Ce document est un constat, pas un changement.
- Toute pièce dont l'emprise dépasse `295 mm` en `Y` est à refuser au tranchage,
  pas à découvrir en pause à la moitié de l'impression.

## Voir aussi

- ADR-040 — quantité de purge G-code et garde cutter réel, `Y307,5` jamais dépassé
- ADR-053 — la purge de démarrage attend le filament, puis pousse ce qu'elle annonce
