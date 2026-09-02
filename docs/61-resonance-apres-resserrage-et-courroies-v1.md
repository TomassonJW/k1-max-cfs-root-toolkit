# Deuxième série de mesures : après resserrage, et les deux courroies

Statut : mesuré, appliqué, vérifié. Thomas a revérifié la mécanique et resserré
les vis avant cette série. Quatre balayages : X, Y, et chaque courroie CoreXY
séparément.

## Les courroies sont bonnes — il n'y a rien à faire de ce côté

Chaque courroie est excitée seule en faisant tourner un seul moteur, ce qui
déplace la tête en diagonale.

| | Pic principal | Largeur à mi-hauteur | Énergie 30-45 Hz | Énergie sous 30 Hz |
| --- | --- | --- | --- | --- |
| Courroie A (1,1) | 39,8 Hz | 10,7 Hz | 51,5 % | 1,5 % |
| Courroie B (1,-1) | 40,1 Hz | 10,7 Hz | 49,3 % | 1,3 % |

`0,3 Hz` d'écart, même largeur, même répartition d'énergie. Les deux courroies
sont tendues pareil et correctement. Le travail fait il y a deux ou trois mois
tient. **Ne pas y toucher.**

## Le resserrage a servi

| | Avant | Après |
| --- | --- | --- |
| X, fréquence retenue | 36,0 Hz | **40,2 Hz** |
| X, énergie sous 30 Hz | 47,9 % | **35,3 %** |
| X, pics larges parasites | 5 (14,7 / 18,7 / 24,1 / 26,8 / 32,1 Hz) | **1** |

La forêt de bosses larges s'est effondrée. Il reste deux pics nets : le pic
principal à `43,2 Hz` (largeur `8,9 Hz`) et un pic à `14,0 Hz`. Monter en
fréquence, c'est gagner en raideur : quelque chose était bien desserré.

Y est passé de `50,6` à `46,6 Hz` en `ei`. Cette baisse n'est pas expliquée avec
certitude : la première série a été faite juste après une impression de 2 h 37,
machine chaude, la seconde sur une machine refroidie, et la tension d'une
courroie varie avec la température. À prendre comme une incertitude, pas comme
une dégradation constatée.

## Ce qui reste : un pic à 14 Hz, sur X seulement

| Essai | Énergie sous 30 Hz |
| --- | --- |
| Axe X | **35,3 %** |
| Axe Y | 4,4 % |
| Courroie A | 1,5 % |
| Courroie B | 1,3 % |

Trois essais sur quatre n'ont rien en bas. Seul le mouvement purement latéral en
fait sortir un pic net à `14,0 Hz`, à 69 % de la hauteur du pic principal.

`14 Hz` est trop bas pour une courroie ou un rail : c'est la fréquence à laquelle
une masse entière se balance. Ce qui se balance latéralement, ce n'est pas la
tête, c'est la machine. À vérifier, dans l'ordre du plus probable :

- ce sur quoi l'imprimante est posée — une table qui fléchit se voit ici ;
- les quatre pieds, tous en contact, aucun qui balance ;
- ce qui est posé **sur** ou **contre** la machine : les deux CFS chaînés sont
  une masse importante, et une masse haute abaisse fortement la fréquence de
  balancement de l'ensemble ;
- les panneaux et la porte, fermés et serrés — une caisse ouverte est une caisse
  molle.

Réserve de méthode : sous 15 Hz environ, la réponse normalisée de Klipper est
peu fiable. Ce qui rend ce pic crédible n'est pas sa valeur absolue, c'est qu'il
est absent des trois autres essais de la même machine, mesurés de la même façon.

## Ce pic n'est pas le défaut que Thomas voit

Fréquence = vitesse ÷ longueur d'onde, donc l'inverse aussi. À 270 mm/s :

| Pic | Longueur d'onde produite |
| --- | --- |
| 14,0 Hz | **19 mm** |
| 43,2 Hz | **6,3 mm** |

Thomas a mesuré `3 à 10 mm` à la règle. C'est le pic à 43 Hz, et c'est celui que
le filtre corrige. Le pic à 14 Hz gonfle le chiffre de « vibrations restantes »
— il explique pourquoi X affiche `24,7 %` — mais il produit une ondulation
lente de 19 mm, pas celle qui se voit sur la pièce.

Autrement dit : le réglage appliqué traite bien le défaut visible. Le 14 Hz est
une piste de fond, pas une urgence.

## Les cinq filtres sur les nouvelles données

### Axe X

| Filtre | Fréquence | Vibrations restantes | Accélération max |
| --- | --- | --- | --- |
| zv | 42,2 Hz | 34,3 % | 6900 |
| mzv | 26,4 Hz | 21,9 % | 2000 |
| **ei** | **40,2 Hz** | **24,7 %** | **3000** |
| 2hump_ei | 42,8 Hz | 20,9 % | 1900 |
| 3hump_ei | 52,8 Hz | 20,7 % | 1900 |

`ei` retenu : les filtres à bosses ne gagnent que quatre points de vibration et
coûtent un tiers de l'accélération.

### Axe Y

| Filtre | Fréquence | Vibrations restantes | Accélération max |
| --- | --- | --- | --- |
| zv | 40,4 Hz | 3,0 % | 6400 |
| **mzv** | **39,0 Hz** | **0,0 %** | **4500** |
| ei | 46,6 Hz | 0,0 % | 4000 |
| 2hump_ei | 58,0 Hz | 0,0 % | 3700 |
| 3hump_ei | 69,4 Hz | 0,0 % | 3500 |

`mzv` retenu : vibrations nulles et la meilleure accélération parmi ceux qui les
annulent.

## Appliqué

```
shaper_type_x = ei    shaper_freq_x = 40.2
shaper_type_y = mzv   shaper_freq_y = 39.0
```

Vérifié dans la réponse de Klipper (`shaper_freq_x:40.200`,
`shaper_freq_y:39.000`) et écrit à la main dans le bloc `#*#`. Comme prévu au
document 60, `SHAPER_CALIBRATE` avait de nouveau écrit tout seul dans
`printer.cfg` — `46,6 Hz` recopié sur les deux axes — et cela a été corrigé
après coup. Sauvegarde prise **avant** la série :
`printer.cfg.bak-avant-mesures2-2026-09-02`.

Capteurs de filament réactivés, machine à l'arrêt, axes pris, tête au centre.
L'imprimante est libre.

## Plafond d'accélération

`3000 mm/s²` conseillé sur X, `4500` sur Y. Le profil du trancheur imprime le
remplissage plein à `9500`. Rien n'a été changé dans Orca : c'est le profil de
Thomas.

## Ce qui n'a pas été fait

Aucune impression d'essai depuis le nouveau réglage. La preuve que le relief a
disparu se fait à l'ongle sur les couches 2 et 3 d'une pièce à surface pleine.
Les courroies n'ont pas été touchées, et n'ont pas à l'être. L'origine du pic à
14 Hz n'est pas identifiée.
