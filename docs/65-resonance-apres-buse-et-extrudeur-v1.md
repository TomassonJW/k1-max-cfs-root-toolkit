# 65 — Résonances après remplacement de la buse et de l'extrudeur

Date : 2026-09-08, 22:10 à 22:25. Campagne complète exécutée sur la machine.
Mesures brutes dans `experiments/2026-09-08-resonance-tete-modifiee-mesures/`.
**Aucune valeur n'a été appliquée.**

## Contexte mécanique

Thomas a remplacé la buse et l'extrudeur — la mâchoire de l'extrudeur était
cassée après trois ou quatre mois. La tête a donc changé de masse et de raideur,
ce qui déplace les résonances : c'est la raison de cette campagne.

## Ce qui a été mesuré

Quatre balayages, chacun un peu plus de trois minutes, exécutés d'affilée :
`SHAPER_CALIBRATE AXIS=x`, `AXIS=y`, puis `TEST_RESONANCES AXIS=1,1` et
`AXIS=1,-1`. Les quatre CSV ont des empreintes distinctes — les deux axes ont
bien été mesurés séparément, ce que le calibrage de la machine ne fait pas.

### Axe Y — nettement meilleur

| | 2 septembre | 8 septembre |
|---|---|---|
| Filtre retenu | `mzv` | `mzv` |
| Fréquence | `39,0 Hz` | `46,6 Hz` |
| Vibrations résiduelles | `0,0 %` | `0,0 %` |
| Accélération admissible | `4 500` | `6 397` |

`+7,6 Hz` et `+42 %` d'accélération admissible, à qualité égale. La tête est
plus raide ou plus légère qu'avant. C'est un gain franc.

### Axe X — toujours le point faible

| Filtre | Fréquence | Vibrations | Accél. max |
|---|---|---|---|
| `zv` | `48,8 Hz` | `37,8 %` | `9 280` |
| `mzv` | `29,4 Hz` | `17,7 %` | `2 546` |
| `ei` | `42,6 Hz` | `22,3 %` | `3 380` |
| `2hump_ei` | `39,0 Hz` | `12,3 %` | `1 543` |
| `3hump_ei` | `48,0 Hz` | `12,1 %` | `1 530` |

Le 2 septembre, `ei` donnait `40,2 Hz` et `24,7 %`. Aujourd'hui `ei` donne
`42,6 Hz` et `22,3 %` : la fréquence monte un peu, les vibrations baissent à
peine. **Le remplacement n'a pas réglé X.** Aucun filtre ne descend sous
`12 %`, et pour y arriver il faut tomber à `1 530 mm/s²` d'accélération, la
moitié de ce qu'on utilise.

Un axe sain ressemble à Y : zéro pour cent, plusieurs filtres au choix. X ne
l'est pas, et ne l'était pas non plus avant l'intervention. C'est mécanique, pas
logiciel.

### Courroies — équilibrées

Pic principal `44,7 Hz` sur les deux, largeur à mi-hauteur `8,9 Hz` sur les
deux, écart nul. Elles étaient à `39,8` et `40,1 Hz` le 2 septembre : les deux
ont monté ensemble, ce qui est cohérent avec une tête plus raide. Rien à
reprendre de ce côté.

## Ce que la machine a écrit pendant la campagne

`SHAPER_CALIBRATE` écrit dans `printer.cfg` de sa propre initiative — c'est le
défaut connu, et le script l'a détecté par empreinte avant/après :

```
-#*# shaper_freq_y = 56.0        +#*# shaper_freq_y = 55.8
-#*# shaper_freq_x = 56.0        +#*# shaper_freq_x = 55.8
```

`55,8 Hz` est la valeur `ei` de **l'axe Y**, recopiée sur X. Or l'`ei` de X vaut
`42,6 Hz`. Le fichier contient donc, à cet instant, une valeur fausse de
`13,2 Hz` sur X, qui deviendrait active au prochain redémarrage.

Les valeurs vivantes en mémoire sont encore celles du 2 septembre
(`ei 40,2` sur X, `mzv 39,0` sur Y). Sauvegarde d'avant campagne :
`printer.cfg.bak-avant-resonance-20260908-221021`.

## Recommandation

Y : prendre `mzv 46,6 Hz`, sans réserve.

X : **ne pas** prendre `zv 48,8 Hz`, que l'analyseur désigne comme meilleur
parce qu'il maximise l'accélération admissible — `37,8 %` de vibrations
résiduelles est un mauvais échange. Prendre `ei 42,6 Hz`, qui garde
`3 380 mm/s²`, ou `2hump_ei 39,0 Hz` si la qualité prime sur la vitesse, au prix
d'une accélération divisée par deux.

Plafond d'accélération à retenir : celui de X, soit `3 380 mm/s²` avec `ei`.

À faire avant de reprendre les impressions, indépendamment des vibrations :
la buse a changé, donc le zéro Z est faux et l'avance de pression (`0,044`) ne
vaut plus rien. Les deux sont à reprendre.

## Application — 8 septembre, 22:43

Thomas a validé. `ei 42,6 Hz` sur X, `mzv 46,6 Hz` sur Y, appliqués des deux
façons.

**En direct**, par `SET_INPUT_SHAPER`. La commande est bien active et
validante : `SHAPER_TYPE_X=nawak` est refusé par
`Unsupported shaper type: nawak`, nos valeurs sont acceptées. À noter, sur cette
version l'objet `input_shaper` n'est pas publié dans l'état de l'imprimante —
il n'apparaît pas dans les 122 objets exposés — donc les valeurs vivantes ne
sont pas relisibles par requête. La preuve tient au refus d'une valeur absurde
et à l'acceptation des nôtres, pas à une relecture.

**Dans le fichier**, à la main dans le bloc `#*#`, `SAVE_CONFIG` étant interdit
ici. Trois lignes changées, quatre lignes relues et conformes. Sauvegarde :
`printer.cfg.bak-avant-application-20260908-224352`.

```
#*# shaper_type_y = mzv      #*# shaper_type_x = ei
#*# shaper_freq_y = 46.6     #*# shaper_freq_x = 42.6
```

### Un piège à connaître

`configfile.save_config_pending` est à `true` : Klipper garde en mémoire les
valeurs que `SHAPER_CALIBRATE` a préparées, c'est-à-dire `ei 55.8` sur les deux
axes. Si un `SAVE_CONFIG` était exécuté, il réécrirait le fichier avec ces
valeurs-là, effacerait l'édition manuelle et redémarrerait la machine. C'est une
raison de plus de ne jamais lancer `SAVE_CONFIG` sur cette imprimante. Le
drapeau retombera au prochain redémarrage.

Autre repère relevé au passage : `max_accel` vaut `20000` dans `[printer]`.
C'est le plafond absolu de la machine, pas l'accélération d'impression ; le
`3 380 mm/s²` conseillé par la mesure se règle côté tranchage. Non modifié.
