# L'input shaping mesuré pour de vrai

Statut : mesuré, appliqué, vérifié. Les deux axes ont été balayés avec
l'accéléromètre de la tête, les valeurs sont en mémoire et écrites dans
`printer.cfg`.

## Ce que la machine portait, et ce qu'elle porte

| | Avant | Après |
| --- | --- | --- |
| X | `ei` à `57,2 Hz` | `ei` à `36,0 Hz` |
| Y | `ei` à `57,2 Hz` | `mzv` à `42,6 Hz` |

X était à 60 % de sa fréquence réelle. À 270 mm/s, 36 Hz produit une ondulation
tous les 7,5 mm — la longueur d'onde de 3 à 10 mm relevée à la règle sur la
pièce. Le relief que Thomas sent au doigt sur les couches 2 et 3 est là.

## Le calibrage d'usine, pris sur le fait

Le document 59 supposait, à la lecture de la macro, que X n'était jamais mesuré.
Le balayage de Y l'a confirmé noir sur blanc dans la console :

```
// Fitted shaper 'ei' frequency = 50.6 Hz (vibrations = 0.0%, smoothing ~= 0.126)
// Recommended shaper_type_y = ei, shaper_freq_y = 50.6 Hz
// copy_TestAxis_y_to_x Recommended shaper_type_x = ei, shaper_freq_x = 50.6 Hz
```

`copy_TestAxis_y_to_x` : le code Creality recopie le résultat de Y sur X et
l'annonce. Il ne s'arrête pas là — il écrit tout seul dans le fichier de
configuration, sans qu'aucun `SAVE_CONFIG` ait été demandé :

```
[configfile:set:358] save_config: set [input_shaper] shaper_freq_x = 50.6
```

**À retenir pour la suite : sur cette machine, `SHAPER_CALIBRATE` écrit dans
`printer.cfg`.** La règle « ne jamais lancer `SAVE_CONFIG` » ne protège pas de
cette commande-là. La sauvegarde `printer.cfg.bak-before-shaper-2026-09-02` a
été prise après cette écriture, elle porte donc déjà `50,6` : les valeurs
d'origine (`ei` / `57,2` sur les deux axes) ne survivent que dans le document 59
et dans l'historique du dépôt.

Second bridage, dans `gcode_macro.cfg` : la macro `AUTOTUNE_SHAPERS` porte
`variable_autotune_shapers: "'ei'"`, et `shaper_calibrate.py` lit ce fichier au
démarrage pour restreindre les filtres candidats. La machine n'a le droit
d'évaluer qu'`ei`, le plus lourd des cinq.

## Les cinq filtres, réévalués hors ligne

Les balayages enregistrent leurs données brutes en CSV. Elles ont été relues
avec une copie non bridée de l'analyseur de Klipper — aucun nouveau mouvement,
aucune modification dans `/usr/share`. Contrôle de la méthode : sur Y, `ei`
retombe exactement sur ce que la machine a annoncé (`50,6 Hz`, `0,0 %`,
`4800 mm/s²`). Sur X l'écart est de `37,2` contre `36,0 Hz` annoncé, dû à
l'arrondi du CSV ; la conclusion ne change pas.

### Axe Y — sain

| Filtre | Fréquence | Vibrations restantes | Accélération max conseillée |
| --- | --- | --- | --- |
| zv | 43,8 Hz | 3,5 % | 7500 |
| **mzv** | **42,6 Hz** | **0,1 %** | **5300** |
| ei | 50,6 Hz | 0,0 % | 4800 |
| 2hump_ei | 62,8 Hz | 0,0 % | 4400 |
| 3hump_ei | 75,2 Hz | 0,0 % | 4100 |

`mzv` est retenu : vibrations nulles en pratique, et il autorise `5300 mm/s²`
au lieu de `4800`. Le filtre imposé par Creality était le moins bon des quatre
qui annulent la vibration.

### Axe X — pas sain

| Filtre | Fréquence | Vibrations restantes | Accélération max conseillée |
| --- | --- | --- | --- |
| zv | 43,4 Hz | 39,2 % | 7300 |
| mzv | 25,6 Hz | 16,1 % | 1900 |
| **ei** | **37,2 Hz** | **20,8 %** | **2600** |
| 2hump_ei | 39,0 Hz | 14,4 % | 1500 |
| 3hump_ei | 48,0 Hz | 14,2 % | 1500 |

Aucun filtre ne descend sous 14 %. Un axe en bon état tombe sous 5 % après
correction. `ei` est retenu comme le meilleur compromis : moitié moins de
vibrations que `zv`, et `2600 mm/s²` au lieu de `1500` pour les filtres à
bosses, qui ne gagnent que six points de vibration.

## Ce que ces chiffres disent de la mécanique

Deux signaux concordants :

- **X est descendu à 36 Hz.** C'est bas pour la tête d'une K1 Max.
- **Y est passé de 57,2 à 50,6 Hz**, soit 11 % perdus depuis le calibrage
  d'usine — et celui-là avait bien été mesuré.

Une fréquence de résonance descend quand la raideur baisse ou quand la masse
monte. La masse n'a pas bougé. Les courroies se sont détendues. Le résidu de
14 à 20 % sur X après correction dit la même chose autrement : un filtre corrige
une résonance nette, il ne rattrape pas un axe qui a du jeu.

Le réglage appliqué aujourd'hui améliore réellement l'état actuel. Il ne remplace
pas une reprise de tension de la courroie X, après quoi il faudra rebalayer :
les fréquences auront changé.

## Le plafond d'accélération

Le travail en cours imprime le remplissage plein à `9500 mm/s²`. Les mesures
conseillent `2600` sur X et `5300` sur Y. Au-delà, le filtre lisse tellement les
ordres de mouvement que les angles s'arrondissent et que le détail se noie.

Rien n'a été changé dans le trancheur : c'est un réglage de profil, il appartient
à Thomas. La descente à `2600` est le prochain essai naturel.

## Ce qui a été fait sur la machine

1. Capteurs de filament désactivés le temps des balayages, réactivés après.
2. `G28`, tête au centre à `Z10`.
3. `SHAPER_CALIBRATE AXIS=x` puis `AXIS=y` (4 min chacun).
4. `SET_INPUT_SHAPER SHAPER_TYPE_X=ei SHAPER_FREQ_X=36.0 SHAPER_TYPE_Y=mzv
   SHAPER_FREQ_Y=42.6`, vérifié dans la réponse de Klipper :
   `shaper_type_x:ei shaper_freq_x:36.000` / `shaper_type_y:mzv
   shaper_freq_y:42.600`.
5. Bloc `#*#` de `printer.cfg` corrigé à la main, pour que le réglage survive à
   un redémarrage.

Les données brutes des deux balayages sont dans
`experiments/2026-09-02-resonance-k1max/`, avec le script de réanalyse.

## Ce qui n'a pas été fait

Aucune impression d'essai depuis le nouveau réglage : la preuve que le relief a
disparu reste à faire, et elle se fait à l'ongle sur une pièce à surface pleine.
La tension des courroies n'a pas été touchée. L'accélération du trancheur n'a pas
été baissée.
