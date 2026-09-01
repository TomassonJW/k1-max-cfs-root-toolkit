# ADR-046 — Un profil de mesh enregistré doit être référencé au point de palpage

Date : 2026-09-01
Statut : accepté
Cible : Creality K1 Max, S12 structure 0, kit CFS, Klipper `bed_mesh` sans
`zero_reference_position`.

## Le fait

Le profil `k1_p001_t055_r001_n11x11` valait **`+0,321498 mm` au point
`(150, 150)`**, qui est exactement le point où `_HOME_Z` fait sa référence Z.

Cette version de `bed_mesh` ne connaît que `relative_reference_index`, et la
configuration ne le renseigne pas : `relative_reference_index` vaut `None`. Un
profil est donc appliqué **tel quel**, comme un écart absolu par rapport au plan
`Z = 0` de la session où il a été mesuré.

Conséquence directe et mesurable : profil chargé et décalage `Z = −0,04`, la
buse se plaçait `0,28 mm` trop haut au centre du plateau. C'est exactement ce
que Thomas a observé — plateau trop bas par rapport à la buse — sur le premier
essai de carré de calibration.

## Ce que cela explique

Le firmware Creality relance `CX_PRINT_LEVELING_CALIBRATION` à **chaque**
départ d'impression. Ce n'est pas une lubie : sans re-référencement, un profil
enregistré est inutilisable d'une session à l'autre. Retirer ce palpage
parasite, comme le fait le paquet `owned-start-print-v2`, n'est légitime que si
les profils sont eux-mêmes référencés.

Cela explique aussi pourquoi le Z paraissait imprévisible : la valeur du profil
au point de palpage variait d'une campagne à l'autre et s'ajoutait
silencieusement au décalage Z.

## Décision

Tout profil de mesh persistant de ce dépôt est **normalisé à zéro au point de
référence Z de la machine**, `(150, 150)`, avant d'être utilisé en production.
La normalisation retire une constante : la forme du plateau est inchangée, et
seule la composante qui appartenait au décalage Z est déplacée là où elle doit
être.

Le profil `k1_p001_t055_r001_n11x11` a été normalisé : `0,321498` retiré de ses
121 points. Sa nouvelle étendue va de `−0,474738` à `+0,145583`, valeur
`0,000000` au centre. Sauvegarde machine :
`printer.cfg.bak-before-mesh-rezero`.

Une grille dont aucun point ne tombe sur `(150, 150)` ne peut pas être
normalisée exactement. Les grilles de production doivent donc avoir un nombre
**impair** de points en X et en Y sur un intervalle centré, ce que respecte le
`11 × 11` sur `5 → 295`. Le `6 × 6` ne le respecte pas ; il reste un profil de
diagnostic et ne doit pas servir en production.

## Conséquence sur le décalage Z par profil

Une fois le profil normalisé, le Z enregistré pour ce profil redevient ce qu'il
prétend être : l'écart réel entre le contact de palpage et la première couche
correcte. Il est petit, il se règle à la main sur un carré `280 × 280`, et il
est comparable d'une bande de température à l'autre.
