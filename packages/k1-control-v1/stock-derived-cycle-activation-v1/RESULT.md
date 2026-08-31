# Résultat — activation stock-derived V1

Statut : **PRÉFLIGHT RÉEL OK — POSE NON EXÉCUTÉE**.

Le candidat obtient `18/18` scénarios hors imprimante. Ils couvrent notamment
le vrai événement runout, la relève unique T1A vers T2D à la température G-code,
l'absence de cutter sur bobine réellement vide, le cutter sur changement
volontaire, le refus d'une relève ambiguë, l'arrêt froid sans spare et le non
rejeu d'un ticket retrouvé après restart.

La capture
`20260831-191518-g4-k1-control-stock-derived-cycle-activation-v1` a confirmé :

- installation désactivée actuelle toujours saine ;
- K1 en `standby`, chauffes à zéro, axes libérés, aucune route engagée ;
- meilleur mesh `k1_p001_t055_r001_n11x11` et Z `-0,04` inchangés ;
- cinq sources Python acceptées par les environnements Python de la K1 ;
- empreintes prospectives exactes de `printer.cfg` et `moonraker.conf` ;
- aucune chauffe, mouvement, extrusion, trame CFS, palpation ou recalcul de mesh.

La tentative de lancer la pose a été refusée par la gate de sécurité de la
plateforme avant exécution. Aucun fichier distant, service ou état K1 n'a été
modifié par cette tentative. La prochaine action est l'autorisation explicite
de la pose active au repos, puis une validation indépendante. Le premier cycle
physique restera séparé et commencera par le nettoyage manuel frais et la caméra.
