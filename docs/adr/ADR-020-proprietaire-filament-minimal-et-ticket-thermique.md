# ADR-020 — Utiliser un ticket thermique et un propriétaire filament minimal

Date : 2026-08-26
Statut : **décision hors imprimante ; aucun transport ni déploiement autorisé**

## Contexte

ADR-019 impose une cible par phase avant le premier effet CFS. L'audit exact du
module montre que `get_material_target_temp` lit la matière du slot avant de
porter la cible stock, mais aucun point d'extension stable n'est démontré. Le
chemin stock garde aussi la géométrie et a déjà déclenché un homing caché.

La base matière ne représente qu'un palier de buse. Une commande après `T`
arrive trop tard. Une interception du seul retour thermique laisserait encore
la géométrie dans le chemin stock et reposerait sur un module Cython compilé.

## Décision

K1 Control utilisera un ticket thermique immuable par frontière. Il lie phase,
opération, outil logique, route fraîche, cibles buse/plateau et quatre états
géométriques. La preuve de route n'est jamais réutilisable.

Le transport filament cible devient un propriétaire minimal séparé. Il ne
remplace pas tout `box_wrapper` et ne reçoit aucun droit de chauffe, plateau,
homing, Z ou mesh. Il ne pourra appeler que des messages série qualifiés un par
un dans une mission ultérieure.

Cette décision est aujourd'hui une architecture hors ligne :

- `printer_transport=false` ;
- `deployment_candidate=false` ;
- `physical_test_authorized=false`.

## Options refusées

### Réécrire la base matière par travail

Refusé comme propriétaire. Une valeur globale ne porte pas first/normal,
plateau et trois températures de transition, et sa relecture à chaud n'est pas
prouvée.

### Réaffirmer après `T`

Conservé comme défense seulement. Une purge déjà faite à une cible fausse reste
un KO.

### Intercepter seulement `get_material_target_temp`

Refusé sans point d'extension stable et sans séparation géométrique. Le binaire
exact est compilé avec Cython `0.29.32`, sans source lisible qualifiée. Même un
retour thermique corrigé ne retire pas les mouvements internes du chargement
stock.

### Remplacer tout `box_wrapper`

Refusé. Le rayon de panne couvre écran, deux CFS, capteurs, refill, runout et
reprises.

## Conséquences

- le contrat de travail expose aussi la température de chargement ;
- chaque route CFS/slot est fraîche et consommée une fois ;
- refill équivalent conserve la dernière cible explicite ;
- pause normale n'appelle aucun CFS ;
- annulation ou dérive coupe les deux cibles et bloque la reprise ;
- les six invariants d'ADR-017 restent inchangés ;
- le vert hors ligne ne vaut ni pose ni validation physique.

## Prochaine décision attendue

La mission `G4-K1-CONTROL-CFS-MINIMAL-OWNER-PROTOCOL-V1` devra cartographier
hors imprimante le sous-ensemble série minimal, ses accusés et son exclusion
mutuelle avec le propriétaire stock. Aucun message inconnu ne deviendra
appelable par défaut.
