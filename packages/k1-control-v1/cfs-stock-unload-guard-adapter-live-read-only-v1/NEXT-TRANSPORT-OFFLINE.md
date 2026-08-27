# Prochaine étape proposée — transport hors imprimante du garde CFS

Nom proposé :
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-TRANSPORT-OFFLINE-V1`.

## En langage courant

Définir hors imprimante la petite couche qui devra, plus tard, lire l'état K1
et envoyer uniquement les deux commandes déjà figées par le garde. Cette étape
testera les délais, erreurs, réponses trompeuses et coupures à partir de données
synthétiques ou déjà enregistrées.

Elle ne se connectera pas à la K1, n'enverra aucun G-code et ne lancera aucun
retrait. Elle permettra seulement de vérifier que le futur transport reste
séparé du garde et qu'il échoue sans relance automatique.

Une connexion ou un essai réel restera une gate différente, avec ses commandes
exactes revues et une autorisation propre.
