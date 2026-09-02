# 58 — Les ondulations sur les longues lignes

Date : 2026-09-02
Statut : mesuré sur le maillage réellement en vigueur ; **rien n'a été corrigé**,
et l'expérience qui tranche entre les deux causes restantes demande un palpage,
donc une buse nettoyée à la main et le feu vert de Thomas (ADR-045)

## 1. Le symptôme

Des ondulations, seulement sur les longues lignes, seulement dans certaines
zones. Première couche : plutôt sur les bords. Deuxième couche : en plein
milieu. Rien sur les courts trajets.

Ce n'est pas le même défaut que le bourrelet de la doc 57. Le bourrelet est
local, à l'arrivée d'un trait sur une paroi, et c'est du Pressure Advance. Les
ondulations sont étalées, périodiques, et c'est autre chose.

## 2. Ce n'est pas l'interpolation

Première hypothèse posée, puis démentie par le calcul. Klipper interpole le
maillage en bicubique (`algo: bicubic`, `tension: 0.2`, `mesh_pps: 2`), et une
spline qui traverse un point aberrant dépasse de part et d'autre.

La spline cardinale de Klipper a été rejouée sur le maillage en vigueur, ligne
par ligne. **Dépassement maximal : 0,007 mm.** À `tension = 0.2`, l'interpolation
est douce ; elle n'invente pas d'ondulation. Hypothèse écartée.

## 3. C'est le maillage lui-même

Le maillage `k1_p001_t055_r001_n11x11` en vigueur, 121 points, pas de 29 mm :

| Mesure | Valeur |
|---|---|
| Amplitude totale | `0,252 mm` (de `−0,202` à `+0,050`) |
| Écarts entre deux points voisins ≥ `0,030 mm` | **85 sur 220, soit 39 %** |
| Plus gros écart entre voisins | `0,126 mm` sur 29 mm |
| Courbure locale maximale | `0,186 mm` en `x34 y121` |
| **Ondulation crête à crête sur 60 mm de ligne droite** | **`0,076` à `0,082 mm` selon la ligne** |

La hauteur de couche est de `0,200 mm`. Une ondulation de `0,08 mm` fait donc
varier l'écrasement de **40 %** le long d'un même trait. C'est visible, et c'est
exactement ce que la machine exécute : Klipper suit le maillage fidèlement.

`fade_start: 5.0`, `fade_end: 50.0` : le maillage est appliqué **à 100 % jusqu'à
5 mm de hauteur**, soit vingt-cinq couches. La même ondulation est donc rejouée
identiquement couche après couche. C'est pourquoi la deuxième couche en montre
autant que la première.

## 4. Pourquoi seulement sur les longues lignes, et par zones

La période de l'ondulation est celle du maillage : **29 mm**. Un trait court
reste à l'intérieur d'une maille et ne voit rien. Il faut traverser plusieurs
mailles pour que la vague devienne lisible — d'où « uniquement sur les longues
distances ».

Et le bruit n'est pas réparti uniformément. Carte de la courbure locale
(`|d²/dx²| + |d²/dy²|`, en mm) :

```
      x34    x63    x92    x121   x150   x179   x208   x237   x266
y266  0.065  0.020  0.040  0.068  0.034  0.035  0.038  0.116  0.067
y237  0.056  0.055  0.027  0.017  0.019  0.072  0.048  0.069  0.068
y208  0.081  0.112  0.138  0.028  0.020  0.108  0.021  0.066  0.133
y179  0.057  0.068  0.060  0.067  0.058  0.025  0.115  0.067  0.075
y150  0.083  0.058  0.047  0.039  0.018  0.040  0.031  0.046  0.075
y121  0.186  0.070  0.036  0.021  0.048  0.131  0.054  0.023  0.085
y92   0.104  0.137  0.029  0.038  0.037  0.044  0.021  0.009  0.103
y63   0.143  0.045  0.084  0.079  0.139  0.048  0.105  0.041  0.052
y34   0.147  0.081  0.095  0.034  0.054  0.017  0.044  0.059  0.064
```

Le bord gauche (`x34`) est cassant sur toute sa hauteur, le bord droit (`x266`)
aussi, et il existe une tache au milieu, autour de `x179`–`x208` entre `y121` et
`y208`. Bords **et** milieu : la description colle.

## 5. Ce bruit ne peut pas être la forme du plateau

Une plaque ne peut pas onduler de `±0,04 mm` avec une période de 29 mm. Sa forme
réelle est la cuvette qu'on lit sans effort dans les mêmes chiffres : avant bas
(`−0,19`), arrière bas (`−0,15`), milieu haut (`≈ 0,00`), soit `0,25 mm` de
creux d'un bord à l'autre. Tout ce qui varie plus vite que ça est ajouté par la
mesure.

Deux causes possibles, indiscernables sans expérience :

1. **Le palpeur bruite.** Sur cette machine, le palpeur est la buse elle-même.
   Un résidu de matière décale un point sans décaler ses voisins.
2. **La tôle ne repose pas à plat.** Une poussière ou un grain sous la feuille
   magnétique produit une vraie bosse locale de quelques centièmes, à cet
   endroit-là seulement.

## 6. L'expérience qui tranche

Nettoyer la buse à la main, retirer la feuille magnétique, essuyer les deux
faces et le plateau chauffant, reposer la feuille, **repalper le même 11 × 11 à
55 °C**, et comparer point à point avec celui en vigueur.

- Les mêmes bosses aux mêmes endroits → c'est la tôle, et le nettoyage l'a peut-
  être déjà réglé.
- Des bosses ailleurs → c'est le palpage, et il faut moyenner davantage ou
  descendre à un maillage plus grossier.

Un maillage `7 × 7` ou `6 × 6` capte la cuvette aussi bien — elle est douce — et
échantillonne trois fois moins de bruit.

## 7. Un détail à ne pas surinterpréter

Le `6 × 6` conservé du 1er septembre et le `11 × 11` en vigueur ne décrivent pas
la même surface : corrélation `0,38`, écart de forme médian `0,083 mm`, et un
basculement net de `0,44 mm` en `Y` entre les deux. Les deux relevés sont
séparés par plusieurs jours pendant lesquels la machine a été manipulée ; la
comparaison ne prouve donc rien sur la fidélité du palpage. Elle est notée ici
pour qu'on ne la redécouvre pas en croyant tenir une preuve.

## 8. Le test de 10 secondes, à faire à l'œil

Mesurer la **longueur d'onde** des vagues sur la pièce, à la règle :

| Longueur d'onde | Cause |
|---|---|
| **≈ 30 mm** | le maillage, tout ce qui précède |
| **≈ 5 mm** | résonance : à 270 mm/s avec un shaper à 57,2 Hz, la vague fait `270 / 57.2 ≈ 4,7 mm` |
| **fine et régulière, ~2 mm** | courroies, artefacts verticaux fins |
| **décroît après un virage** | ringing, pas de rapport avec le maillage |

## 9. Le plateau n'est pas trop chaud

`55 °C` pour du PLA est normal, et surtout la température ne produit pas de
vague de 30 mm de période. Elle déforme le plateau lentement et globalement ;
le maillage en vigueur a d'ailleurs été palpé à `55 °C`, donc cette déformation
est déjà dans les chiffres.

## 10. Ce qui n'est pas prouvé

La section 5 repose sur un argument physique et sur la carte de courbure, pas
sur une contre-mesure. La preuve est le repalpage de la section 6.
