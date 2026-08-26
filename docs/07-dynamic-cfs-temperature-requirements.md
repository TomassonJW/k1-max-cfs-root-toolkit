# 07 — Propriété dynamique de la température CFS

Date : 2026-08-20
Statut : exigences acceptées ; précisées par le contrat figé du 26 août 2026 ;
architecture et code encore à prouver

Référence canonique actuelle :
[`docs/25-contrat-cycle-impression-nettoyage-cfs-v1.md`](25-contrat-cycle-impression-nettoyage-cfs-v1.md).

## Objectif

Pendant une impression, le G-code est la source de vérité de la température de
buse. Le CFS exécute le chargement, la coupe, la purge et le remplacement de
bobine, mais il ne choisit jamais une température différente de celle demandée
par le travail en cours.

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

Une enveloppe de macros n'est acceptable que si tous les changements de
température du module compilé passent réellement par des commandes que l'on peut
intercepter. Si le module écrit directement dans le chauffage sans passer par
ces points, il faudra modifier ou remplacer cette partie du pilote au lieu
d'empiler une correction tardive.

## Deux architectures à départager

### A — Propriétaire dynamique autour du pilote actuel

- mémoriser les demandes du G-code par outil ;
- transmettre explicitement la cible aux opérations CFS qui acceptent `TEMP` ;
- envelopper les commandes d'outil et de reprise ;
- contrôler après chaque opération que la cible demandée est toujours active ;
- ne restaurer qu'une valeur mémorisée, jamais une constante.

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

Les essais physiques seront réduits au minimum. Les chemins doivent d'abord être
prouvés par les sources, les traces existantes, des fichiers G-code synthétiques
et une simulation locale.

## Critère de décision

L'architecture choisie doit démontrer, pour chaque chemin de la matrice :

`température active observée = cible explicite de la phase du contrat ou dernière cible explicite de Thomas`

Le prochain candidat G4 ne sera préparé qu'après cette démonstration. Il ne doit
contenir ni température de filament codée en dur, ni profil Geeetech obligatoire,
ni comportement particulier réservé au PLA.
