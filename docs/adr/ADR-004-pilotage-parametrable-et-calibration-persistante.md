# ADR-004 — Pilotage paramétrable et calibration persistante

Date : 2026-08-20

Statut : **accepté pour conception et prototype hors imprimante ; déploiement non autorisé**

## Contexte

Le candidat `G4-ZSAFE-START-V1` sécurisait un ordre précis avec un mesh
`default` et `+0,27 mm`. Il ne répondait pas au besoin réel : la valeur change
avec la plaque, la température, la calibration et la référence capteur. Il ne
réglait ni le pilotage quotidien, ni les meshes thermiques, ni les températures
CFS, ni l'ensemble des contrats Orca.

Thomas a confirmé que la cible est un système durable utilisable sur des
milliers d'impressions : réglage Z en direct pendant une calibration,
enregistrement explicite, persistance jusqu'à une nouvelle calibration,
interfaces adaptées, meshes par plaque/température et séquences entièrement
paramétrables dans leurs valeurs.

## Options examinées

1. conserver le paquet fixe et ajouter des lots plus tard : refusé, car la base
   du produit resterait fausse ;
2. installer tout le Creality Helper Script ou son fork CFS : refusé, car les
   versions et correctifs ne sont pas prouvés sur la machine exacte ;
3. installer seulement Mainsail : insuffisant, car une interface générique ne
   définit pas les règles de persistance Z, de mesh ou de température CFS ;
4. remplacer immédiatement firmware, capteur et pile CFS : refusé à ce stade,
   car écran et deux CFS deviendraient un projet de rétro-ingénierie ;
5. conserver le cœur Creality, ajouter une API/UI épinglée et notre propre
   couche d'état/macros : retenu pour le prototype hors imprimante.

## Décision

Un seul produit cohérent est conçu :

- `K1 Control` pour le quotidien et la calibration guidée ;
- Mainsail comme interface experte candidate ;
- Moonraker épinglé et sécurisé comme API candidate ;
- `K1 Control` livré comme interface statique sans second serveur applicatif ;
- un état original séparé pour les calibrations Z, meshes, profils et
  historiques ;
- des macros et wrappers originaux qui conservent les fichiers constructeur ;
- un contrat Orca versionné ;
- une matrice de simulation couvrant les deux CFS.

La correction acceptée est une donnée explicite associée à un contexte. Elle
n'a aucune valeur numérique universelle par défaut. Une fin d'impression ou un
redémarrage ne l'efface pas. Toute nouvelle opération capable de changer la
référence l'invalide jusqu'à une nouvelle sauvegarde volontaire.

Le produit est préparé comme un tout, puis installé par poses réversibles. La
règle D-007 porte sur l'attribution du risque et le rollback, pas sur un produit
morcelé que Thomas devrait régler manuellement à chaque impression.

## Conséquences

- `G4-ZSAFE-START-V1` et ADR-003 sont rejetés et ne peuvent pas servir de gate ;
- le post-traitement Orca actuel reste en place jusqu'à validation atomique du
  nouveau contrat Orca et du côté machine ;
- aucun installateur communautaire n'est exécuté tel quel ;
- la sélection exacte des versions Moonraker/Mainsail dépend encore des preuves
  de ressources, sécurité et coexistence ;
- les outils Creality restent disponibles, mais l'enregistrement Z validé passe
  par le nouveau flux ;
- aucun nouveau G4 n'est proposé avant un prototype hors imprimante complet et
  ses tests.

## Validation attendue

Le contrat historique de cette décision est
`design/production-control-contract.json`. Il est désormais remplacé pour le
cycle de travail par `design/job-lifecycle-contract-v1.json` et
`docs/25-contrat-cycle-impression-nettoyage-cfs-v1.md`. Le prototype doit passer
les tests statiques, le simulateur de séquence, la matrice
Z/mesh/température/CFS, les tests de version Orca et un scénario de rollback
complet avant toute demande de mutation.
