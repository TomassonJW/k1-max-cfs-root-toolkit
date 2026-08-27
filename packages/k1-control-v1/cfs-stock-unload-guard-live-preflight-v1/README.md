# CFS Stock Unload Guard Live Preflight V1

Cette gate relie le garde hors imprimante aux champs réellement lisibles sur la
K1. Elle ne lance aucun retrait et n'envoie aucun G-code.

Le collecteur effectue uniquement :

- une lecture de `server/info` ;
- une lecture de la liste des objets Klipper ;
- deux lectures des objets nécessaires, espacées de deux secondes ;
- les empreintes des trois configurations avant et après.

La sortie brute reste sous `inventory/raw/`, ignoré par Git, car l'objet `box`
peut contenir des identités matérielles. Le vérificateur public ne doit publier
que les états fonctionnels nécessaires.

Cette mission ne fournit ni transport de production, ni déployeur, ni commande
de retrait.

## Résultat

Les deux instantanés valides sont stables : Klipper est prêt, la K1 est au
repos, `T1` et `T2` sont connectés, les consignes sont à zéro et aucune route
CFS n'est actuellement engagée.

La K1 n'expose pas de champ direct `stock_unload_state`. La capture historique
montre en plus que `box.t_command` est resté vide pendant tout le retrait stock.
Le garde hors imprimante est donc corrigé : la fin est déduite du retour de la
requête, de la route réellement libérée et de `t_command` vide. HTTP `ok` seul
reste insuffisant.

La prochaine étape est hors imprimante : construire le petit adaptateur qui
transforme une réponse K1 nettoyée en état compris par le garde.
