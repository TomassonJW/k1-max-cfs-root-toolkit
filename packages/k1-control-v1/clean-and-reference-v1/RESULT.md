# Résultat actuel

Statut : **Geetech et `220 °C` confirmés ; préflight frais vert ; cycle
physique atomique prêt sous observation humaine**.

La recette produit une chauffe et observation du flux, six allers-retours
rapides dans E4, puis un frottement lent piloté par la température réelle. La
buse remonte progressivement de `Z32` à `Z34` et ne termine qu'à
environ `140 °C`, avec les cibles remises à zéro. Viennent ensuite, après le
verdict visuel, une référence finale unique et l'arrêt thermique d'urgence.

Le runner physique complet est maintenant créé et épinglé. Il refuse chaque
effet sans verdict humain exact, présence devant la K1, plateau libre, brosses
et buse visibles et arrêt immédiat possible. Il ne contient aucune extrusion,
commande CFS, écriture distante ou relance automatique.

Deux lectures live stables ont qualifié les codes matière des slots, mais pas
le segment dans la tête. L'historique contient un marqueur de chargement plus
récent que le retrait T1A ; l'identité historique ne peut donc pas être
réutilisée comme certitude. Le préflight live du pilote est vert sans G-code à
`X203 Y273 Z32`, chauffes zéro, `11 × 11` exact et configurations conformes.
Le nouveau préflight sans effet qualifie le programme révisé, les cibles zéro,
la position d'observation sûre, le `11 × 11` actif et les configurations
exactes. La seule barrière avant chauffe est la présence humaine renouvelée.

Un premier passage s'est arrêté après la chauffe faute de verdict reçu dans la
fenêtre interactive. Aucun nettoyage n'a été exécuté. La coupure de sécurité a
confirmé les deux cibles à zéro, les configurations exactes et aucun mouvement.
La chauffe séparée est supprimée du nouveau programme : le cycle suivant finit
obligatoirement chauffes à zéro sans attendre un message.

Vérifications : `19/19` tests du paquet, `25/25` avec le registre Goal 3,
suite complète de `572` tests dont `569` verts et `3` ignorés connus, et
`67/67` scripts PowerShell relus sans erreur. Effets physiques de cette étape :
un placement et une chauffe à `220 °C`, aucun frottement, puis une coupure sans
mouvement. Le cycle atomique révisé n'a encore produit aucun effet.
