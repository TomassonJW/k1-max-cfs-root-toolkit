# 64 — Campagne de résonance après modification de la tête

Date : 2026-09-08. Outillage préparé et validé sur données connues. **Aucune
mesure neuve n'a été prise** : la campagne attend le feu vert de Thomas.

## Pourquoi une campagne à nous

Le calibrage de vibrations de la machine a tourné le 8 septembre à `21:47`,
lancé depuis l'écran. Il a produit `/tmp/calibration_data_x_20260908_214708.csv`
et son homologue `_y_`. Les deux fichiers ont la même empreinte,
`bd083f5cee0378bf1fe736e8c71f7b26` : **un seul axe a été mesuré**, le résultat
recopié sur l'autre — c'est `copy_TestAxis_y_to_x` dans le firmware. Il a
ensuite écrit `ei 56.2` sur les deux axes dans le bloc `#*#` de `printer.cfg`,
effaçant la série du 2 septembre.

Deux défauts s'ajoutent : `variable_autotune_shapers: "'ei'"` dans
`gcode_macro.cfg` réduit le choix à un seul filtre sur cinq, et l'écriture se
fait sans demander. Une réanalyse hors ligne du balayage de ce soir, les cinq
filtres ouverts, donne `mzv 46,8 Hz` et zéro vibration résiduelle — contre
`ei 56,2 Hz` retenu par la machine.

## Ce que fait la campagne

`scripts/run-k1-control-resonance-campaign-v1.ps1`, un seul lancement, une
vingtaine de minutes. Trois scripts posés sur la machine :

- `prepare-analyseur.py` — construit dans `/tmp/sc` une copie non bridée de
  `shaper_calibrate.py`, en retirant le bloc qui lit `autotune_shapers` et
  écrit dans `printer.cfg`. Il vérifie que les cinq filtres sont bien de retour
  (`zv, mzv, ei, 2hump_ei, 3hump_ei`) et s'arrête sinon. Posé en premier :
  s'il échoue, autant le savoir avant vingt minutes de balayages.
- `campagne-resonance.py` — quatre balayages : `SHAPER_CALIBRATE AXIS=x`,
  `AXIS=y`, puis `TEST_RESONANCES AXIS=1,1` et `AXIS=1,-1` pour les deux
  courroies séparément. Chaque CSV est sorti et sa source effacée avant le
  balayage suivant. **Le script échoue si les CSV X et Y ont la même empreinte** :
  c'est exactement le défaut du calibrage d'usine, et il ne doit pas passer
  inaperçu chez nous.
- `analyse-campagne.py` — les cinq filtres sur chaque axe, la comparaison des
  deux courroies, l'écart avec le 2 septembre, et la ligne `SET_INPUT_SHAPER` à
  appliquer si les résultats sont retenus. Il refuse d'annoncer un pourcentage
  de vibrations sur une sortie `TEST_RESONANCES`, qui n'est pas normalisée.

Garde-fous de la campagne : refus si Klipper n'est pas prêt, si une impression
est en cours ou en pause, si la buse ou le plateau dépassent `40 °C`, ou si le
capteur de tête voit du filament. Sauvegarde de `printer.cfg` avant, empreinte
avant et après pour prouver qu'il n'a pas bougé. Les deux capteurs de filament
sont désactivés pendant les balayages et remis dans un `finally`.

Rien n'est appliqué. L'écriture des valeurs retenues est une décision séparée,
prise après lecture du rapport.

## Preuve de l'outillage

L'analyseur a été passé sur les quatre CSV du 2 septembre, qui ont une valeur
publiée (document 61). Il les reproduit au dixième près :

| Mesure | Attendu (doc 61) | Rendu par l'analyseur |
|---|---|---|
| X, filtre `ei` | `40,2 Hz`, `24,7 %`, accél. `3000` | `40,2 Hz`, `24,7 %`, `3010` |
| Y, filtre `mzv` | `39,0 Hz`, `0,0 %`, accél. `4500` | `39,0 Hz`, `0,0 %`, `4480` |
| Courroie A | pic `39,8 Hz`, sous 30 Hz `1,5 %` | pic `39,8 Hz`, `1,5 %` |
| Courroie B | pic `40,1 Hz`, sous 30 Hz `1,3 %` | pic `40,1 Hz`, `1,3 %` |

Les cinq filtres ouverts, le meilleur sur X n'est plus `ei` mais `zv` à
`42,2 Hz` — plus d'accélération admissible, mais `34,3 %` de vibrations
résiduelles contre `24,7 %`. C'est le genre d'arbitrage que le bridage à un
seul filtre empêchait de voir.

Écart relevé au passage : la largeur à mi-hauteur des courroies vaut `7,9` et
`8,0 Hz` ici, là où le document 61 annonçait `10,7 Hz` pour les deux. Les pics
et la répartition d'énergie concordent exactement ; c'est donc la définition de
la largeur qui diffère, pas la mesure. Les constantes de comparaison ont été
alignées sur le calcul de ce script.

## Ce qui reste inconnu

L'axe X — celui qui vibrait à `24,7 %` le 2 septembre — n'a pas été mesuré
depuis la modification de la tête. C'est le premier chiffre à regarder.

La nature exacte de la modification n'est pas connue au moment d'écrire. Si la
partie chaude ou la géométrie ont bougé, les vibrations ne suffisent pas : le
zéro Z et l'avance de pression (`0,044` aujourd'hui) sont à reprendre dans le
même passage.
