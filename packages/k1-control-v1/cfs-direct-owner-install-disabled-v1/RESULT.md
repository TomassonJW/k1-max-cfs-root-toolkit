# Résultat hors imprimante — installation désactivée V1

Statut : **OFFLINE_PREPARED_NOT_AUTHORIZED**

Le composant Klipper réel et son paquet de pose sont construits. Les `13/13`
scénarios locaux prouvent notamment :

- l'état désactivé sans transport ni trame ;
- le refus des trois entrées d'effet avant leurs arguments ;
- la conservation intacte des commandes stock quand le composant est désactivé ;
- leur remplacement borné quand une simulation active le propriétaire ;
- le refus si l'auto-remplacement stock n'est pas à zéro ;
- le refus si une commande stock est active ou si un des deux CFS manque ;
- le chargement simulé par le coeur `24/24` sans chauffe, géométrie, mesh ou purge ;
- le retrait simulé avec une seule traction locale exacte et `M400` avant la
  seconde phase CFS.

Aucune connexion K1, écriture distante, relance de service, chauffe, mouvement
ou trame CFS n'a été produite par cette préparation.

La prochaine action utile sera la pose désactivée avec backup et rollback exacts,
puis seulement une qualification physique unique `T1A` chargement/retrait.
