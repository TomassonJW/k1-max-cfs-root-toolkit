# ADR-030 — Nettoyage de buse manuel obligatoire

Date : 2026-08-28

Statut : **acceptée après qualification physique ; remplace le nettoyage
automatique comme politique courante**

## Contexte

La brosse du bac a recollé du filament sur la buse. La grande brosse du plateau
a ensuite été testée à deux vitesses. Le V2 à `F6000` n'était pas probant car la
buse avait déjà été nettoyée à la main. Le V3 a été précédé d'un chargement,
d'une petite purge et d'un retrait manuels, puis a exécuté huit allers-retours
diagonaux à `F12000`, à `Z2,5`, avec remontée immédiate à `Z7,5` et sortie de la
brosse.

Le V3 a fini dans un état sûr, mais Thomas a jugé le résultat visible non
convaincant et a décidé de ne plus poursuivre cette voie. Le nettoyage manuel
avait, lui, déjà produit une buse visiblement propre.

## Décision

- Le nettoyage automatique par brosse est rejeté pour l'usage courant.
- Thomas nettoie lui-même la buse à la main avant toute référence Z ou
  impression sensible.
- Une confirmation humaine de buse propre est obligatoire avant la référence Z
  finale.
- `CleanCycle` et `Reference` sont refusés par le runner historique
  `CLEAN-AND-REFERENCE-V1`.
- La géométrie et les captures des brosses restent des preuves historiques,
  mais ne constituent plus une recette exécutable.
- Aucun V4 ne peut être préparé ou exécuté sans une décision future distincte
  qui rouvre explicitement ce sujet.

L'identifiant historique `AUTOMATIC_CLEAN_AND_FINAL_REFERENCE` reste dans le
registre du Goal 3 pour conserver la traçabilité. Sa résolution devient
`AUTOMATIC_REJECTED_MANUAL_ONLY_POLICY_ACCEPTED`; il n'est pas renommé pour
faire disparaître le KO.

## Critères de clôture de l'exigence historique

- les essais physiques et le verdict humain sont conservés ;
- les chauffes sont revenues à zéro et la tête a quitté la brosse ;
- le profil `11 × 11` et les configurations sont restés inchangés ;
- les actions automatiques sont techniquement bloquées ;
- la politique manuelle est versionnée et devient la source courante.

La référence Z finale automatique initialement prévue est annulée. Elle n'est
pas présentée comme exécutée.

## Conséquences

### Positives

- aucun brossage insuffisant ne peut être confondu avec une buse propre ;
- la gate de propreté reste visible et sous contrôle humain ;
- la qualification CFS et les autres fonctions du Goal 3 peuvent continuer
  sans dépendre d'une recette de brosse rejetée.

### Négatives

- le démarrage d'une impression ne peut pas être entièrement autonome ;
- Thomas doit être présent pour nettoyer et confirmer la buse ;
- le Goal 4 devra intégrer explicitement cette étape manuelle dans K1 Control.

## Alternatives refusées

### Continuer avec une V4 plus rapide ou plus profonde

Refusé : le résultat V3 n'est pas convaincant et augmenter l'énergie ou le
contact ajouterait un risque sans preuve de gain.

### Accepter le V3 parce que son état technique final est vert

Refusé : chauffes à zéro et absence de collision ne prouvent pas la propreté de
la buse.

### Supprimer l'exigence du registre

Refusé : cela masquerait le travail physique et le KO. L'exigence historique
reste visible avec sa résolution manuelle explicite.
