# Deuxième série — après resserrage des vis

Même protocole que la série précédente, machine refroidie.

- `resonance-x.csv`, `resonance-y.csv` — balayages des deux axes.
- `courroie-a.csv`, `courroie-b.csv` — chaque courroie CoreXY excitée seule, par
  un mouvement en diagonale (`TEST_RESONANCES AXIS=1,1` et `AXIS=1,-1`).

Résultat : les deux courroies sont identiques à `0,3 Hz` près, rien à retendre.
Le resserrage a fait monter X de `36,0` à `40,2 Hz`. Il subsiste sur X un pic à
`14,0 Hz` que ni Y ni les deux courroies ne montrent.

Analyse et décisions : document 61.
