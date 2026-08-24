# COMPOSITE-FIRST-LAYER-COMPARISON-V2

Cette révision compare deux copies du même carré `260 × 260 × 0,20 mm` issu du
G-code Orca sans offset Z caché. Elle ajoute uniquement `KCTRL_PRODUCTION_ARM`
après `START_PRINT`.

Cette garde :

- charge le profil demandé ;
- lit le Z accepté dans le stockage K1 Control ;
- applique ce Z sans mouvement supplémentaire ;
- vérifie le profil et le Z effectifs avant d'ouvrir les mouvements bas.

Les deux sorties ne diffèrent que par la paire `X_COUNT/Y_COUNT` sur cette ligne
de garde : `6/6` pour le profil robuste, puis `11/11` pour le composite.

Chaque sortie exécute ensuite `PAUSE` avant la première extrusion. Pour la
reprise composite, Thomas règle provisoirement le Z à `−0,24 mm` depuis l'écran,
Codex vérifie l'origine Z effective, puis la reprise est autorisée. Cette valeur
n'est pas persistée.

Le passage robuste a servi à régler le Z en direct et a montré une compensation
locale insuffisante, surtout vers `X0/Y0`. Le passage composite peut être lancé
sur la plaque libérée afin d'obtenir une comparaison relative. La séquence de
départ stock restant imparfaite, ce test ne qualifie pas encore le Z absolu ni
la production autonome.

## Résultat physique

La V2 est close avec un **gain partiel et un KO de promotion UI**. Le composite
améliore nettement une grande zone centrale, mais plusieurs bandes de bord sont
beaucoup plus mauvaises. L'interpolation bicubique exacte ne diffère de la
surface directe que de `0,009877883 mm` au maximum ; elle n'explique donc pas
seule les défauts visibles.

Le profil source `11 × 11` est conservé, le mode Précision reste caché et le
même carré `260 × 260` ne doit pas être rejoué sans correction. La suite est un
éditeur de profil dérivé et un motif de diagnostic des bords. Voir
`RESULT.md`, `docs/23-audit-mesh-manuel-et-cycle-production-cfs.md` et ADR-015.
