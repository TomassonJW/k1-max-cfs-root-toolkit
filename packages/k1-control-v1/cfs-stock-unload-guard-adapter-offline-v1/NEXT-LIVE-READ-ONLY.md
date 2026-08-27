# Prochaine étape proposée — validation live en lecture seule de l'adaptateur

Nom proposé :
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-LIVE-READ-ONLY-V1`.

## En langage courant

Lire un état frais de la K1, retirer les identités matérielles avant tout
traitement, puis vérifier que l'adaptateur produit les mêmes huit champs que
ceux attendus par le garde.

Cette mission ne devra appeler ni `StockUnloadGuard.run`, ni une route d'envoi
de commande. Elle ne fera aucun G-code, retrait, chauffage, mouvement, fichier
distant ou restart. Elle servira seulement à confirmer que l'adaptateur local
comprend encore la forme réelle des réponses.

La mission hors imprimante actuelle n'autorise pas cette connexion. Une future
mission explicite et séparée devra fixer les lectures exactes, la méthode de
nettoyage, les preuves attendues et l'arrêt en cas de champ nouveau ou ambigu.
