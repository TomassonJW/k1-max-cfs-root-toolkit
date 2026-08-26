# ADR-018 — Fermer l'adaptateur stock et préparer un propriétaire CFS minimal

Date : 2026-08-26
Statut : décision hors imprimante ; aucune pose ni essai physique autorisé

## Contexte

ADR-017 exige six invariants autour de toute frontière CFS. L'audit exact du
binaire et du journal de l'incident montre que le chemin stock de chargement
prend simultanément la main sur la température de buse et la géométrie. La
consigne matière stock `220 °C` devient la cible réelle malgré la consigne de
purge `190 °C`.

Le script de l'incident appelle ensuite `BOX_EXTRUDER_EXTRUDE` et
`BOX_MATERIAL_FLUSH`, mais sans snapshots complets entre ces appels. Leur
innocuité individuelle n'est donc pas prouvée. Le binaire compilé contient par
ailleurs une surface fonctionnelle beaucoup plus large que ces trois commandes.

## Décision

L'adaptateur stock V1 est fail-closed : aucune primitive n'est appelable. Une
primitive ne peut entrer dans cette liste que si une preuve déterministe couvre
les six invariants avant, pendant et après son appel, ainsi que la propriété de
la température et le débit visible.

K1 Control reste propriétaire de la géométrie et des deux cibles thermiques.
Le transport filament à l'intérieur de la frontière reste non attribué tant
qu'une primitive étroite n'est pas qualifiée.

Si cette qualification reste impossible hors imprimante, la branche retenue
est un propriétaire filament minimal séparé, limité au protocole nécessaire. Il
ne remplace pas tout `box_wrapper` et ne touche pas aux fonctions CFS stock non
requises.

## Options refusées

### Autoriser `BOX_MATERIAL_FLUSH` parce qu'elle accepte `TEMP`

Refusé. La trace montre `temp: 190.0` dans ses paramètres alors que la cible
réelle reste à `220 °C`. Un paramètre visible ne prouve pas la propriété.

### Considérer une chaîne absente du binaire comme une absence d'effet

Refusé. Le binaire est compilé et dépouillé. Une écriture peut être indirecte,
construite ou déléguée à une autre méthode.

### Remplacer le module complet

Refusé à ce stade. Le module couvre communication multi-CFS, capteurs, écran,
refill, reprise et gestion d'erreurs. Le rayon de panne serait disproportionné.

### Faire un nouvel essai physique pour séparer les commandes

Différé. L'audit courant est en lecture seule et la production reste fermée. Un
essai physique n'est acceptable qu'après préparation et revue d'un paquet
réversible dédié.

## Conséquences

- les trois commandes brutes du 26 août restent interdites en séquence ;
- aucune pose d'adaptateur n'existe à ce stade ;
- le contrat local est testable mais son résultat vert signifie « refus sûr » ;
- le prochain incrément est une conception hors imprimante du propriétaire
  minimal ou une preuve statique plus forte ;
- `MESH-EDGE-DIAGNOSTIC-V1` et la production restent bloqués.
