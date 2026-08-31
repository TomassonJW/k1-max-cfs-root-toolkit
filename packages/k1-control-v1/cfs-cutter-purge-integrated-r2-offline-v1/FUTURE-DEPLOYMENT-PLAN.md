# Plan de pose futur — actuellement inerte

Ce document décrit des gates ; ce n'est ni un installeur ni une autorisation.

1. Porter sans invention la chorégraphie stock déjà capturée : cutter, retrait,
   chargement, purge, restauration et fin. Vérifier chaque mouvement contre
   `stock-sequence-delta.json`.
2. Construire le registre thermique et créer une première entrée réelle via la
   calibration séparée, filament absent et buse propre.
3. Corriger puis prouver la conservation d'`auto_refill=0` à travers le restart,
   sans mouvement CFS.
4. Préparer un paquet installable désactivé : fichiers exacts, sauvegarde,
   rollback, autotest froid et refus de tout effet tant que `enabled=false`.
5. Poser et valider ce paquet désactivé, sans chauffe ni mouvement.
6. Qualifier séparément le port direct cutter/retrait puis
   chargement/purge/décrochage avec
   comparaison caméra. Aucun retry automatique.
7. Qualifier un runout contrôlé avec une unique bobine de secours déclarée
   identique : pause verrouillée, bascule, purge, contexte restauré et reprise.
8. Seulement après ces tranches, lancer un motif très court puis une impression
   normale supervisée. Ces prints valident le delta ; ils ne servent pas à
   redécouvrir la séquence stock.

État actuel : étapes `1` à `8` non autorisées par ce paquet.
