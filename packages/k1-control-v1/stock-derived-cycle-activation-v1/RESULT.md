# Résultat — activation stock-derived V1

Statut : **INSTALLÉE ET VALIDÉE INDÉPENDAMMENT AU REPOS — AUCUN ESSAI PHYSIQUE**.

Le candidat obtient `18/18` scénarios hors imprimante et `8/8` tests ciblés.
Ils couvrent notamment le vrai événement runout, la relève unique T1A vers T2D
à la température G-code, l'absence de cutter sur bobine réellement vide, le
cutter sur changement volontaire, le refus d'une relève ambiguë, l'arrêt froid
sans spare et le non-rejeu d'un ticket retrouvé après restart.

La capture finale
`20260831-205322-g4-k1-control-stock-derived-cycle-activation-v1` contient :

- `DEPLOY_STOCK_DERIVED_CYCLE_ACTIVATION_V1_OK` ;
- `VALIDATE_STOCK_DERIVED_CYCLE_ACTIVATION_V1_OK` obtenu par une lecture
  indépendante après la pose ;
- Klipper `ready`, impression `standby`, chauffes à zéro et axes libérés ;
- mesh `k1_p001_t055_r001_n11x11` et Z effectif `-0,04` ;
- propriétaire direct actif, commandes stock concurrentes bloquées et phase
  Moonraker `idle` ;
- politique stock `auto_refill=0`, runout non armé, compteur d'événement à
  zéro et aucune route engagée ;
- aucun fichier de run ou de sélection, aucune commande d'effet et aucun
  envoi de trame CFS.

Les refus intermédiaires ont tous eu lieu avant chauffe, mouvement, extrusion,
palpage, recalcul de mesh ou action filament. Chaque tentative a déclenché le
rollback automatique. Elles ont permis de corriger quatre écarts réels : le
rechargement du module Python, l'identité publiée du propriétaire direct, la
reconnexion asynchrone des deux CFS et la restauration explicite du Z accepté
après un restart hôte. Une capture séparée,
`20260831-205226-g4-k1-control-stock-derived-cycle-activation-v1`, prouve la
remise immédiate du Z effectif à `-0,04` avec `MOVE=0`.

Cette clôture qualifie uniquement l'installation active au repos. Elle ne
qualifie pas encore un départ d'impression, un changement de filament, une
relève de bobine vide ou une fin d'impression réels. La prochaine tranche doit
ajouter le bouton K1 Control/Mainsail et le pilote caméra à ce backend, puis
préparer une première gate physique unique sans réintroduire de palpage après
insertion.
