# Première prise T1B — essai V1 clos

Le chargement et la purge ont réussi, avec rotation, débit et décrochage
confirmés par Thomas. L'observateur a ensuite provoqué un arrêt d'urgence
injustifié sur la réponse à une commande externe inconnue. La fin est restée
inactive. Ne pas rejouer ce G-code.

`grip_guard.py` contient la **correction locale postérieure à l'essai** :
elle conserve l'arrêt à huit réponses `full`, et journalise uniquement la
réponse exacte observée à `SET_HOTEND_FAN VALUE=1` sans en faire un arrêt.
Tout autre `!!` reste un arrêt. Ce fichier ne change aucune commande Klipper,
ne fournit aucun bouchon de ventilateur et n'est pas installé sur la K1.
L'ancien observateur exécuté est conservé dans la capture brute privée.

Voir [le compte rendu](../../../docs/89-prise-t1b-et-arret-observateur-v1.md).
