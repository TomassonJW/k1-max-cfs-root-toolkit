# 57 — La surextrusion à l'arrivée du remplissage sur les parois

Date : 2026-09-02
Statut : diagnostic établi sur les réglages réels du travail en cours ;
**aucune correction appliquée, aucun test lancé** — la calibration décisive
demande une impression, donc un nettoyage manuel de la buse et le feu vert de
Thomas (ADR-045)

## 1. Le symptôme

À chaque impression, un bourrelet là où une ligne de remplissage vient buter
contre une paroi. Systématique, sur toutes les couches.

## 2. Ce n'est pas le maillage

Le maillage décale la buse en hauteur. Son effet est maximal sur la première
couche et s'estompe couche après couche : à la dixième, il ne reste rien. Un
défaut qui revient identique **sur toutes les couches** ne peut pas venir de
là. Le maillage actuel n'est pas en cause dans cette histoire.

## 3. Les chiffres relevés

Machine (`factory_printer.cfg`, objet `extruder`, objet `toolhead`) :

| Réglage | Valeur |
|---|---|
| `pressure_advance` par défaut | 0.04 |
| `pressure_advance_smooth_time` | **0.040 s** |
| `max_accel` | 9500 mm/s² |
| `square_corner_velocity` | 10 mm/s |

Travail `_CORPS_PLA_2h37m.gcode`, pied de fichier et ligne 126 :

| Réglage | Valeur |
|---|---|
| `enable_pressure_advance` | 1 |
| `pressure_advance` du filament | **0.03**, émis en ligne 126 : `SET_PRESSURE_ADVANCE ADVANCE=0.03` |
| `sparse_infill_speed` | 270 mm/s |
| `internal_solid_infill_speed` | 270 mm/s |
| `inner_wall_speed` | 250 mm/s |
| `outer_wall_speed` | 165 mm/s |
| `sparse_infill_acceleration` | 95 % de 9500, soit ≈ 9025 mm/s² |
| `infill_wall_overlap` | 15 % |
| `filament_flow_ratio` | 0.98 |
| `line_width` / `layer_height` | 0.42 / 0.20 mm |

## 4. Le calcul qui explique le bourrelet

Une ligne de remplissage arrive à 270 mm/s et doit tomber à la vitesse de
coin, 10 mm/s, en 9025 mm/s². La rampe de décélération dure :

    (270 - 10) / 9025 ≈ 0,029 s

**0,029 s de freinage, contre un `smooth_time` de 0,040 s.** Le lissage du
Pressure Advance étale sa correction sur plus longtemps que le freinage
lui-même : la rétraction qui devait vider la pression du bloc de fusion arrive
en partie **après** la fin du trait. La matière encore sous pression sort donc
là où la ligne s'arrête, c'est-à-dire contre la paroi. C'est exactement le
bourrelet décrit.

Deuxième facteur, plus ordinaire : 0.03 est probablement trop bas pour ce
filament à ce débit. Un PA insuffisant produit le même défaut, en plus doux —
gros à la fin des traits, maigre à leur début.

Le `infill_wall_overlap` à 15 % est déjà en dessous du réglage d'usine (25 %) :
ce n'est pas lui qui pousse la matière dans la paroi.

## 5. Réponses aux trois questions

**Le PA se règle-t-il par filament ?** Oui, et c'est déjà le cas ici. La valeur
0.03 vient du profil de filament du trancheur, qui l'impose à la machine au
démarrage du travail et écrase le 0.04 de `factory_printer.cfg`. Chaque
filament — chaque marque, et parfois chaque couleur — a le sien. Il dépend de
la matière, de la buse et de la température, pas de la pièce.

**Le PA change-t-il avec la vitesse ?** Non, et c'est tout l'intérêt : il
s'exprime en secondes et s'applique au débit instantané, donc une valeur juste
reste juste à toutes les vitesses. Ce qui change avec la vitesse, c'est la
**visibilité** d'une valeur fausse : à 270 mm/s et 9000 mm/s², une erreur
invisible à 60 mm/s devient un bourrelet. Et ce qui doit, lui, suivre les
accélérations de la machine, c'est le `smooth_time` — voir le calcul ci-dessus.

**Le maillage est-il en cause ?** Non, section 2.

## 6. Le plan, dans cet ordre

1. **`pressure_advance_smooth_time` : 0.040 → 0.020.** Un seul chiffre, effet
   immédiat sur le symptôme, réversible. 0.040 est la valeur par défaut de
   Klipper, pensée pour des machines dix fois plus lentes.
2. **Recalibrer le PA du PLA** par une tour de réglage — `TUNING_TOWER` fait
   varier `SET_PRESSURE_ADVANCE` en continu sur la hauteur d'un carré, on lit
   la bande la plus propre, on reporte la valeur dans le profil de filament du
   trancheur. Une tour par filament.
3. **Refaire la mesure à la nouvelle valeur** avant de toucher au débit. Le
   `flow_ratio` à 0.98 ne se juge honnêtement qu'une fois le PA correct.

Rien de tout cela n'est encore fait : les points 2 et 3 sont des impressions.

## 7. Ce qui n'est pas prouvé

Le raisonnement de la section 4 tient sur des chiffres relevés et sur le
symptôme décrit ; il n'a pas été confronté à une pièce. La preuve est la tour
de réglage.
