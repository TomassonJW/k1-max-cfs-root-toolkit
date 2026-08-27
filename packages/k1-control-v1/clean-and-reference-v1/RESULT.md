# Résultat actuel

Statut : **préflight live OK, effet bloqué par l'identité matière**.

La recette pure produit six checkpoints séparés : chauffe et observation du
flux, un carré E4 chaud, refroidissement sans essuyage, un carré E4 stable à
`140 °C`, une référence finale unique et l'arrêt thermique d'urgence.

Le runner physique complet est maintenant créé et épinglé. Il refuse chaque
effet sans verdict humain exact, présence devant la K1, plateau libre, brosses
et buse visibles et arrêt immédiat possible. Il ne contient aucune extrusion,
commande CFS, écriture distante ou relance automatique.

Deux lectures live stables ont qualifié les codes matière des slots, mais pas
le segment dans la tête. L'historique contient un marqueur de chargement plus
récent que le retrait T1A ; l'identité historique ne peut donc pas être
réutilisée comme certitude. Le préflight live du pilote est vert sans G-code à
`X203 Y273 Z32`, chauffes zéro, `11 × 11` exact et configurations conformes.
La matière et sa cible restent le seul fait requis avant la première chauffe.

Vérifications finales : `14/14` tests propres au paquet, `20/20` avec le
registre du Goal 3, suite complète de `567` tests dont `564` verts et `3`
ignorés connus, et `66` scripts PowerShell relus sans erreur. Effets live
produits : trois lectures strictement sans effet ; aucun G-code, chauffe,
mouvement, CFS, écriture distante ou service.
