# Transport hors imprimante du garde de retrait CFS V1

Ce paquet relie localement le garde déjà qualifié à l'adaptateur de réponse K1
déjà qualifié. Il ne contient aucun connecteur réseau, aucune adresse
d'imprimante, aucun appel de processus et aucun délai réel.

Le faux endpoint remet des événements déterministes au transport. Le transport
accepte seulement `BOX_QUIT_MATERIAL` et `TURN_OFF_HEATERS`, une fois chacun.
Une réponse tardive ou perdue rend l'effet inconnu et interdit toute nouvelle
tentative du même ordre. Après une incertitude sur le retrait, l'unique arrêt
thermique reste permis, comme l'exige le garde.

Les réponses de lecture sont synthétiques ou déjà nettoyées. Elles passent par
l'adaptateur pur avant d'atteindre le garde. Une dérive de forme ferme la
séquence avant toute commande.

## Limites

- aucune connexion K1 ;
- aucun G-code réel ;
- aucun sommeil ni attente murale ;
- aucune preuve mécanique ;
- aucun candidat de pose.

La prochaine étape du Goal 1 est d'intégrer cette frontière déterministe dans
la machine d'états complète du cycle d'impression, toujours hors imprimante.
