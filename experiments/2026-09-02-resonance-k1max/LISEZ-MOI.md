# Résonance de la K1 Max — 2026-09-02

Balayages faits avec l'accéléromètre monté dans la tête (`[adxl345]` sur
`nozzle_mcu`), machine à l'arrêt, plateau vide, buse nettoyée à la main.

- `resonance-x.csv` — balayage réel de l'axe X.
- `resonance-y.csv` — balayage réel de l'axe Y.

La machine a aussi écrit un troisième fichier nommé « x » pendant le balayage de
Y : c'est une copie du fichier Y, produite par le code Creality qui recopie le
résultat d'un axe sur l'autre. Il n'est pas conservé ici, il n'apporte rien.

## Rejouer l'analyse

Le calibrage embarqué n'a le droit d'évaluer qu'un seul filtre (`ei`), imposé par
`variable_autotune_shapers` dans `gcode_macro.cfg`. Le script rejoue les cinq
filtres sur ces mêmes données, sans rien mesurer à nouveau et sans toucher à
`/usr/share` :

```
scp -O resonance-*.csv k1max-root:/tmp/
ssh k1max-root 'mkdir -p /tmp/sc/extras && cd /tmp/sc/extras \
  && cp /usr/share/klipper/klippy/extras/shaper_defs.py . && touch __init__.py \
  && sed "/configfile = self.printer.lookup_object/,/^        try:$/{/^        try:$/!d}" \
       /usr/share/klipper/klippy/extras/shaper_calibrate.py > shaper_calibrate.py'
scp -O reanalyse-cinq-filtres.py k1max-root:/tmp/sc/analyse.py
ssh k1max-root 'python3 /tmp/sc/analyse.py /tmp/resonance-x.csv /tmp/resonance-y.csv'
```

Contrôle de la méthode : sur Y, le filtre `ei` doit retomber sur `50,6 Hz`,
`0,0 %` de vibrations, `4800 mm/s²` — exactement ce que la machine a annoncé
pendant le balayage.

Résultats et décisions : document 60.
