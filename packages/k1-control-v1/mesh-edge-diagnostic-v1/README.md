# MESH-EDGE-DIAGNOSTIC-V1

Statut : **passage source physique invalide, sans dépôt de filament ; gate
suspendue avant tout nouveau motif**.

Le premier essai a démontré une lacune de protocole : le motif minimal chauffait
et commandait l'extrusion, mais ne résolvait aucun outil CFS, ne chargeait pas le
filament et n'exigeait aucune purge visible. L'ancien texte supposait `T0` sans
que Thomas ait fourni ce fait. Ce passage ne qualifie ni le mesh ni la buse.

Le paquet ne doit plus lancer de motif sans confirmation fraîche de la route
filament et d'une purge réellement visible. Un capteur de présence seul ne
prouve pas le débit. La reprise physique exige d'abord le rollback exact du
profil temporaire et des quatre G-code, puis une nouvelle gate hors imprimante.

Ce paquet prépare une comparaison physique bornée entre le profil composite
source et un profil diagnostic dérivé. La géométrie couvre `X/Y=5..295 mm` avec
trois cadres, 121 cellules, quatre repères asymétriques et une croix centrale.

La seule correction demandée est `Éloigner +0,010 mm` au point
`X=34, Y=266` (`ligne 9`, `colonne 1`). Le moteur validé de
`mesh-editor-offline-v1` la normalise sur la surface bicubique exacte `31 × 31`.
Le Z global reste absent.

Le générateur refuse un autre G-code source, un offset Z exécutable ou une
géométrie différente entre les deux variantes. Les sorties restent privées
sous `.codex-work/` et ne sont pas versionnées.

Commande de préparation :

    python packages\k1-control-v1\mesh-edge-diagnostic-v1\prepare_diagnostic.py SOURCE.gcode .codex-work\mesh-edge-diagnostic-v1

Livrables privés :

- document dérivé et bloc Klipper déterministe ;
- préparation sans chauffe ni extrusion et motif source composite ;
- préparation sans chauffe ni extrusion et motif corrigé ;
- manifeste avec empreintes, géométrie et budget matière.

Chaque motif est séparé de sa préparation. Celle-ci référence les axes, arme le
profil et le Z, puis se termine sans extrusion. L'état réel peut ainsi être
prouvé avant de lancer le motif, sans `PAUSE/RESUME` stock et sans
`START_PRINT` qui extrude avant la garde.

Le paquet ne choisit aucun outil physique. Le PLA déclaré doit être résolu vers
le CFS et le slot réellement engagés au moment du préflight. Si cette résolution
est incertaine, le motif reste bloqué.

La pose temporaire du profil, les deux motifs et le rollback restent des étapes
séparées. Elles exigent d'abord une gate hors ligne verte, puis un
préflight K1 frais et la confirmation factuelle de Thomas devant l'imprimante.
Le mode Précision reste caché.
