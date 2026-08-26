# 07 — Propriété dynamique de la température CFS

Date : 2026-08-20
Statut : exigences acceptées ; précisées par le contrat figé et par l'incident
réel du 26 août 2026 ; garde hors imprimante préparée, propriétaire réel encore
à prouver

Référence canonique actuelle :
[`docs/25-contrat-cycle-impression-nettoyage-cfs-v1.md`](25-contrat-cycle-impression-nettoyage-cfs-v1.md).

## Objectif

Pendant une impression, le G-code est la source de vérité de la température de
buse. Le CFS exécute le chargement, la coupe, la purge et le remplacement de
bobine, mais il ne choisit jamais une température différente de celle demandée
par le travail en cours.

La consigne du plateau et l'identité Z/mesh font partie de la même frontière de
sécurité. Le CFS ne commande pas le plateau et ne référence, ne décale, ne
charge ni n'efface aucun état Z/mesh à l'intérieur d'une phase filament.

La solution doit rester valable si Thomas change de marque, de matériau, de
profil ou de température. Elle ne doit contenir aucune température de filament
fixe et aucune liste fermée de matériaux autorisés.

## Règles fonctionnelles

| Situation | Température qui doit gagner |
|---|---|
| Chargement au début du travail | température de première couche fournie par le G-code |
| Passage aux couches normales | dernière température demandée par le G-code |
| Bobine épuisée, remplacement par une bobine équivalente | cible active juste avant la pause |
| Changement de couleur avec matière équivalente | cible du prochain outil fournie par le G-code |
| Changement entre matières différentes | retrait de l'ancien, purge de transition et cible du prochain outil, tous explicitement fournis ou validés par le contrat |
| Réglage manuel pendant l'impression | dernière cible demandée par Thomas |
| Chargement manuel hors impression | température explicitement choisie pour cette opération ; le contrat d'impression ne s'applique pas |

Une valeur de la base CFS peut servir d'information ou de valeur par défaut hors
impression. Elle ne peut pas écraser une cible explicite pendant un travail.

## Contrat attendu du G-code

Le fichier doit pouvoir exprimer sans valeur codée en dur dans la machine :

- la température de première couche ;
- la température normale de chaque filament logique ;
- les températures de retrait, purge de transition et prochain filament lors
  d'un vrai changement de matière ;
- les modifications `M104` et `M109` décidées par le profil ou par Thomas.

Pour un remplacement automatique par une bobine équivalente, aucun nouveau
paramètre de matériau n'est nécessaire : la machine conserve simplement la cible
active. Pour un vrai changement de matière, l'opération CFS reçoit explicitement
la cible de retrait de l'ancien filament, la cible de purge compatible et la
cible du prochain outil. Ces valeurs appartiennent au contrat, pas au CFS.

Si une vraie transition n'a aucune température exploitable, la solution doit
s'arrêter avant l'extrusion et expliquer la donnée manquante. Elle ne doit pas
inventer `195`, `220` ou une autre valeur.

## Chemins à couvrir avant de choisir l'implémentation

L'analyse doit prouver le comportement de chaque chemin :

1. `M104`, `M109` et éventuelles autres commandes de chauffe émises par le
   fichier ou l'interface ;
2. chargement et purge de démarrage ;
3. commandes logiques `T0` à `T15` ;
4. commandes physiques des deux CFS ;
5. `BOX_MATERIAL_FLUSH` et son paramètre `TEMP` ;
6. épuisement, pause automatique, sélection équivalente et reprise ;
7. relecture cachée de l'outil physique après `RESUME` ;
8. changement volontaire de matériau ;
9. annulation, erreur CFS et reprise manuelle ;
10. chargement et retrait hors impression.

Pour chacun de ces chemins, la preuve couvre désormais trois familles d'état :

- cible buse explicite de la phase ;
- cible plateau explicite du travail ou de Thomas ;
- Z accepté, origine Z courante, profil mesh et axes référencés.

Une enveloppe de macros n'est acceptable que si tous les changements de
température du module compilé passent réellement par des commandes que l'on peut
intercepter. Si le module écrit directement dans le chauffage sans passer par
ces points, il faudra modifier ou remplacer cette partie du pilote au lieu
d'empiler une correction tardive.

Le passage réel `20260826-physical-cfs-insert-purge-v1` a disqualifié la
séquence brute déjà utilisée : malgré une demande à `190 °C`, elle a imposé
`220 °C` et référencé X/Y. La cible plateau est restée à zéro pendant cette
observation. L'état Z/mesh pendant la frontière n'a pas été capturé avec une
preuve assez complète pour conclure à son invariance. Une future solution doit
donc le vérifier, pas le supposer.

## Deux architectures à départager

### A — Propriétaire dynamique autour du pilote actuel

- mémoriser les demandes du G-code par outil ;
- transmettre explicitement la cible aux opérations CFS qui acceptent `TEMP` ;
- envelopper les commandes d'outil et de reprise ;
- contrôler après chaque opération que la cible demandée est toujours active ;
- ne restaurer qu'une valeur mémorisée, jamais une constante.

Un contrôle après coup n'est pas une propriété de température : il peut arrêter
la reprise, mais il ne peut pas rendre correcte une purge déjà commencée à la
mauvaise température. Chaque primitive utilisée doit donc être qualifiée comme
respectant la cible pendant toute sa durée.

Le contrôleur place et stabilise les cibles buse et plateau avant l'entrée dans
la frontière CFS. Aucun `M104`, `M109`, `M140` ou `M190` ne doit apparaître à
l'intérieur de cette frontière, même avec une valeur numériquement identique.

Cette voie préserve au maximum l'écran et les deux CFS. Elle n'est recevable que
si l'analyse prouve qu'aucun chemin interne important ne la contourne.

### B — Corriger ou remplacer le propriétaire de température du pilote CFS

- conserver les fonctions matérielles et la correspondance des deux CFS ;
- empêcher le pilote de consulter sa température générique pendant un travail ;
- lui fournir la cible explicite de chaque phase courante ;
- garder un mode manuel séparé hors impression.

Cette voie est plus profonde mais devient nécessaire si le module compilé
contourne les macros. Elle exige une compatibilité démontrée avec le firmware
`2.3.5.34`, l'écran et les deux CFS `1.1.3`.

## Matrice minimale de validation

- démarrage avec une première couche différente de la température normale ;
- PLA avec deux températures différentes choisies dans OrcaSlicer ;
- PETG avec ses propres températures ;
- remplacement automatique par une bobine équivalente ;
- changement volontaire PLA vers PETG et retour ;
- transition entre le premier et le second CFS ;
- modification manuelle de la cible pendant une impression ;
- pause, reprise, annulation et erreur de chargement ;
- vérification qu'aucune cible imprévue n'apparaît, y compris `220 °C`.
- vérification que la cible plateau ne change jamais à l'initiative du CFS ;
- vérification qu'aucune commande buse ou plateau n'est émise dans la frontière ;
- vérification que le Z accepté, l'origine Z, le mesh et les axes référencés ne
  changent jamais dans une frontière CFS.

Les essais physiques seront réduits au minimum. Les chemins doivent d'abord être
prouvés par les sources, les traces existantes, des fichiers G-code synthétiques
et une simulation locale.

## Critère de décision

L'architecture choisie doit démontrer, pour chaque chemin de la matrice :

`température active observée = cible explicite de la phase du contrat ou dernière cible explicite de Thomas`

et simultanément :

`plateau, Z accepté, origine Z, mesh et axes = état explicitement attendu par le contrat`

Le prochain candidat G4 ne sera préparé qu'après cette démonstration. Il ne doit
contenir ni température de filament codée en dur, ni profil Geeetech obligatoire,
ni comportement particulier réservé au PLA.
