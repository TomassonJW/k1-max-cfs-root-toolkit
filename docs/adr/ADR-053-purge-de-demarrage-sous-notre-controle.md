# ADR-053 — Purge de démarrage sous notre contrôle

Date : 2026-09-02

Statut : **acceptée ; installée ; à juger sur la première impression**

## Contexte

Au démarrage d'une impression, la purge au-dessus du bac laisse un filet mince
qui reste accroché à la buse au lieu de former une boule qui se décroche et
tombe. Ce filet est ensuite traîné sur le plateau et finit dans la première
couche.

La purge du parcours possédé était intégralement celle du stock :
`BOX_MATERIAL_FLUSH TEMP={nozzle}`, sans longueur. Sa quantité vient donc de
`box.cfg`, qui déclare sur cette machine :

```
box_first_clean_length: 140
box_need_clean_length: 140
box_need_clean_length_max: 140
```

Soit `140 mm`. La correction de quantité décidée en ADR-040 — vecteur
`flush_volumes_vector` du G-code, repli qualifié à `140 mm` — vit dans
`k1_control_cfs_direct_owner.py`, un composant **désactivé**. Elle n'est donc
pas sur le parcours réel, ce qui explique la sensation d'une purge « remise »
plus faible : elle n'a jamais été renforcée là où l'impression passe.

## Décision

La longueur de purge est possédée par le paquet, pas déléguée.

Un macro `_KCTRL_PURGE_BALL` pousse une quantité explicite au-dessus du bac,
**avant** `BOX_MATERIAL_FLUSH` :

```
BOX_EXTRUDER_EXTRUDE TNN={tool}
_KCTRL_PURGE_BALL TEMP={nozzle}
BOX_MATERIAL_FLUSH TEMP={nozzle}
```

Défaut : `300 mm` à `300 mm/min`, soit environ `440 mm` au total avec la purge
stock — un peu plus de trois fois la quantité précédente. Réglable à chaud, la
valeur prend effet au démarrage suivant :

```
SET_GCODE_VARIABLE MACRO=_KCTRL_PURGE_BALL VARIABLE=purge_mm VALUE=400
```

Quatre points la rendent sûre.

**La longueur n'est pas passée à `BOX_MATERIAL_FLUSH LEN=`.** `box.cfg` déclare
`box_need_clean_length_max: 140` : une longueur supérieure pourrait être bornée
sans un mot. Une purge silencieusement bornée est le pire cas — rien ne le
signale et le défaut ne se voit que sur la plaque.

**La tête est positionnée explicitement.** `BOX_GO_TO_EXTRUDE_POS` est appelé
avant d'extruder. `BOX_MATERIAL_FLUSH` se positionne tout seul, mais cette
purge passe avant lui, et `300 mm` extrudés au mauvais endroit ne valent pas le
pari d'une hypothèse sur la position héritée.

**La température est la nôtre.** `M109 S{nozzle}` avec la valeur du G-code,
atteinte avant que le filament ne bouge. C'est la seule purge du parcours dont
la température ne vient pas de la table matière du CFS — `Tn_extrude_temp: 220`
reste imposé par le stock à la purge suivante, et reste un point ouvert.

**La purge stock reste la dernière au-dessus du bac.** Ce que
`BOX_MATERIAL_FLUSH` fait en fin de routine pour décrocher la boule et essuyer
est ce qui a toujours fonctionné ici. Notre purge grossit la boule ; c'est
toujours le stock qui la lâche.

## Le capteur surveillé est le bon, et il ne dit pas ce qu'on croit

L'hypothèse était raisonnable : on purgerait dans le vide parce qu'on
surveillerait le mauvais capteur. Vérification faite sur la machine, ce n'est
pas ça.

```
filament_sensor    (!PC15, MCU principal)      filament_detected: True
filament_sensor_2  (^!nozzle_mcu:PA10, tête)   filament_detected: False
```

`filament_sensor_2` est bien celui de la tête — il est câblé sur le MCU de la
tête — et c'est bien celui que la séquence interroge. Il lisait `True` pendant
l'impression et lit `False` maintenant, voyant éteint, parce que `END_PRINT` a
déchargé par le cutter. Le capteur fonctionne et il est correctement lu.

Mais il ne dit pas ce qu'on lui fait dire. Il est placé **après le cutter et
avant les galets de l'extrudeur**. Voir du filament au capteur signifie que le
filament est arrivé au capteur, pas que la buse est amorcée. Entre les deux, il
reste tout le trajet jusqu'à la zone de fusion, que `BOX_EXTRUDER_EXTRUDE`
couvre avec ses `Tn_extrude: 140`. Une purge de `140 mm` derrière ça peut donc
sortir bien moins de `140 mm` de matière par la buse.

Deuxième écart trouvé dans les traces du 2 septembre à 00 h 22 : au moment de
la purge stock, `extruder: target=220 temp=109.3`. Le CFS impose sa cible et
la purge part alors que la buse est à `109 °C`. `_KCTRL_PURGE_BALL` fait un
`M109` sur la température du G-code et attend réellement de l'atteindre, ce que
la purge stock ne garantit pas.

D'où la mesure plutôt qu'une théorie de plus : `_KCTRL_PURGE_MARK` relève l'axe
extrudeur avant l'étape matière, `_KCTRL_PURGE_REPORT` annonce le total poussé
après la purge stock. Les deux se lisent après un `M400`, parce qu'un macro se
rend au moment où sa commande est traitée et que `M400` bloque la file jusqu'à
la fin des mouvements : la position relevée a donc réellement eu lieu. Le
prochain démarrage affichera dans la console le nombre réel, en millimètres.

## Vérification

Le rendu Jinja est testé hors machine, avec l'environnement de Klipper
(délimiteurs à accolade simple) : la longueur commandée est exactement la
longueur poussée, pour `30`, `61`, `119`, `300`, `421` et `1000 mm`. Le
découpage est fait en tranches pleines plus un reste, et non en tranches
égales : des tranches égales portent leur arrondi une fois par tranche, et une
purge à qui on demande `1000` et qui pousse `1000,008` est une purge dont le
nombre ne veut plus rien dire.

Sur la machine : configuration relue, `FIRMWARE_RESTART` accepté, macro
enregistré. **La quantité réelle reste à juger à l'œil sur la première
impression** — c'est le seul juge de « boule » contre « filet ».

## Conséquences

- Le démarrage s'allonge d'environ une minute.
- Environ `1,3 g` de PLA par démarrage d'impression, contre `0,4 g` avant.
- La sauvegarde de la configuration précédente est
  `/usr/data/printer_data/config/.bak-owned-start-v2-prepurge`.
- `Tn_extrude_temp: 220` reste imposé par le CFS sur la purge stock. Le sortir
  de la boucle de température est un travail séparé.

## Alternatives refusées

- **Passer `LEN=` à `BOX_MATERIAL_FLUSH`** : susceptible d'être borné à `140`
  sans le dire.
- **Remplacer entièrement la purge stock** : sa fin de routine décroche la
  boule, et son contenu exact n'est pas lisible — c'est un `.so` compilé.
  Retirer ce qui fonctionne pour ne garder que ce qu'on comprend ferait courir
  le risque d'une boule traînée sur la plaque.
- **Multiplier une valeur supposée** : la quantité de départ n'était pas
  `8 mm`, elle était `140 mm`. Multiplier une supposition aurait donné une
  purge encore trop faible.

## Voir aussi

- ADR-040 — quantité de purge G-code et garde cutter réel
- ADR-049 — chargement CFS, une poussée ne suffit pas
