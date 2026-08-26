# ADR-019 — Router les températures par phase, pas par réécriture du slot CFS

Date : 2026-08-26
Statut : décision hors imprimante ; aucune pose ni action physique autorisée

## Contexte

Le chemin stock de chargement a résolu `220 °C` depuis le type matière du slot,
alors que la purge demandait `190 °C`. La base matière contient bien une
température de buse, mais une impression a au moins deux phases thermiques pour
la buse et deux pour le plateau. Le même type matière peut en outre être partagé
par plusieurs slots et utilisé pendant un refill.

## Décision

Le contrat du travail est la source principale des températures. Il expose
séparément la buse et le plateau de première couche et de régime normal. Toute
frontière CFS reçoit la température de buse correspondant à sa phase exacte et
surveille aussi la cible du plateau.

La base matière CFS reste un filet de sécurité statique et une information
d'inventaire. Elle n'est pas réécrite à chaque travail tant que la K1 exacte ne
prouve pas, hors ambiguïté, sa relecture à chaud, son isolation par slot, son
rollback et son innocuité pour refill, runout et reprise.

Une réaffirmation `M104` après un changement d'outil est une défense utile mais
pas une preuve de réussite : elle arrive trop tard si le chargement ou la purge
a déjà utilisé une mauvaise température.

Le propriétaire thermique ne reçoit aucun droit géométrique. Le positionnement
de purge à `Z=30 mm`, les références X/Y, le mesh, l'origine Z et le Z accepté
restent sous les gardes d'ADR-017.

## Options refusées

### Écrire la température de première couche dans le slot

Refusé comme solution complète. Une seule valeur matière ne représente ni la
température normale ni les deux températures du plateau.

### Réécrire la base matière avant chaque travail

Refusé sans preuves supplémentaires. La base est globale par type matière, son
rafraîchissement à chaud n'est pas documenté sur cette K1 et sa synchronisation
peut toucher plusieurs slots et le refill.

### Réaffirmer seulement les températures après `T`

Refusé comme propriétaire principal. Cette mesure protège la suite du G-code,
pas la chauffe et la purge déjà exécutées dans le chemin stock.

### Confier le plateau au CFS

Refusé. Aucun contrat public ou champ de slot qualifié ne lui attribue les
températures de plateau de première couche et normales.

## Conséquences

- la prochaine mission canonique est
  `G4-K1-CONTROL-CFS-DYNAMIC-TEMP-ROUTING-V1` ;
- elle reste hors imprimante et compare les points d'interception avant de
  concevoir un paquet installable ;
- son simulateur doit couvrir deux CFS, refill, changement, runout,
  pause/reprise et filament déjà engagé ;
- un résultat hors ligne vert n'autorise ni pose ni essai physique ;
- `MESH-EDGE-DIAGNOSTIC-V1` et la production restent fermés.

## Résultat de la mission canonique

La mission est close par ADR-020. La base matière reste un filet statique,
la réaffirmation post-`T` une défense et l'interception étroite est refusée sans
point d'extension et séparation géométrique prouvés. Le choix hors ligne est un
ticket thermique servi par `minimal_separate_filament_owner` ; son simulateur
obtient `25/25`, sans transport ni candidat de pose.
