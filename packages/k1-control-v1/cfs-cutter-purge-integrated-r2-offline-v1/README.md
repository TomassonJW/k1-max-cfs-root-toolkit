# CFS cutter/purge integrated R2 — delta stock hors imprimante

Ce paquet ne crée pas une nouvelle chorégraphie. Il part des séquences Creality
réellement capturées, conserve leurs mouvements utiles et remplace seulement
les décisions incorrectes : repalpations, mesh/Z implicites et températures
CFS cachées. `stock-sequence-delta.json` relie chaque décision aux traces d'une
impression normale complète et d'une impression à changement unique.

Il est volontairement **inerte**. Il n'importe aucun client réseau, n'écrit
rien sur la K1 et ne contient pas de macro installable. Les scénarios utilisent
un profil thermique synthétique ; ils prouvent le refus des ordres dangereux
et la conformité au delta stock, pas l'existence actuelle d'un profil réel
`55/220`.

Le propriétaire final ne rappellera pas les blocs opaques `BOX_*`. Ce n'est pas
un changement gratuit de séquence : leurs journaux prouvent qu'ils imposent
notamment `220 °C` et mélangent température, géométrie et mouvements. Le port
direct devra reproduire le même ordre physique observé, avec des entrées
explicites et vérifiables.

## Ordre retenu

1. aucun filament, buse fraîchement nettoyée ;
2. références X/Y/Z à température de palpage `140 °C` ;
3. sélection exacte par plaque et températures G-code ;
4. chargement du mesh `11 × 11` et du Z canonique, sans nouveau mesh ;
5. montée aux températures d'impression ;
6. plateau abaissé, tête au bac, chargement direct ;
7. purge bac puis `3 ou 4` allers-retours continus, preuve caméra ;
8. ligne constructeur `X0,1/X0,4`, `Y20..180`, puis correction explicite
   demandée : plateau abaissé de `5 mm` ;
9. impression et changements de route atomiques cutter → retrait → chargement →
   purge → décrochage ;
10. si une bobine se vide, remplacement automatique par l'unique bobine de
    secours explicitement déclarée identique, température active conservée,
    contexte restauré puis reprise sans repalpation ;
11. fin : dégagement, cutter, retrait complet, parc sûr, refroidissement et
    moteurs libérés.

Après le premier chargement, toute nouvelle palpation ou recalibration est
refusée. La calibration multi-températures est un parcours K1 Control séparé,
décrit dans `calibration-path-contract.json`.

## Vérification locale

```powershell
python packages\k1-control-v1\cfs-cutter-purge-integrated-r2-offline-v1\run_scenarios.py
python packages\k1-control-v1\cfs-cutter-purge-integrated-r2-offline-v1\verify_candidate.py
python -m unittest tests.test_cfs_cutter_purge_integrated_r2_offline_v1 -v
```

## Couverture déjà acquise

- impression mono-filament complète : départ, chargement, purge, amorçage,
  impression, cutter et retrait final ;
- impression P5 complète avec un changement : coupe, retrait, nouveau
  chargement, purge, restauration Z et reprise ;
- G-code P5 exact de `383733` octets et verdict humain sans pause ni incident
  CFS remarqué sur la seconde tentative.
- moteur propriétaire antérieur déjà vert pour le runout et le choix d'une
  bobine strictement identique, y compris entre les deux CFS.

Aucune nouvelle impression n'est nécessaire pour découvrir la séquence. Le
futur motif court servira uniquement à valider le delta final avec la caméra.

## Ce qui reste fermé

- port direct et qualification physique de la chorégraphie cutter observée ;
- première entrée réelle du registre thermique ;
- maintien prouvé d'`auto_refill=0` après restart ;
- pose K1 et essai physique des `3 ou 4` allers-retours ;
- transport et rollback de la future version installable.

Aucun de ces points n'est contourné par une commande `BOX_*`.
