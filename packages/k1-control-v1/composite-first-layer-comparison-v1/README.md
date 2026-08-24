# COMPOSITE-FIRST-LAYER-COMPARISON-V1

Ce paquet prépare deux impressions de première couche strictement comparables.
Il réutilise le carré privé déjà imprimé pendant G3 : `200 × 200 × 0,20 mm`,
PLA Geeetech, T0, plateau `55 °C`, buse `190 °C`, environ `9,91 g` et
`18 min 44 s` par passage.

`prepare_gcodes.py` refuse toute source dont l'empreinte diffère de la capture
revue. Il exige une seule couche, la séquence exacte `G28`, `T0`, `START_PRINT`
et l'ancien `SET_GCODE_OFFSET Z=0.27`. Il refuse une commande Bed Mesh déjà
présente.

Les deux sorties ne diffèrent que par la ligne ajoutée juste après
`START_PRINT` :

- passage 1 : `k1_p001_t055_r001_n06x06` ;
- passage 2 : `k1_p001_t055_r001_n11x11`.

L'ancien Z Orca `+0,27 mm` reste volontairement identique. Cette comparaison
mesure seulement l'effet relatif du profil. Elle ne valide ni le Z de
production, ni `START_PRINT`, ni les températures CFS, ni l'autonomie
production.

Après le premier passage, la pièce doit être photographiée, repérée et retirée
avant le second. Le second passage utilise le même côté de plaque, le même
filament et le même G-code. Si le gain n'est pas clair sur les zones concernées,
le profil robuste reste le défaut et le mode Précision reste caché.
