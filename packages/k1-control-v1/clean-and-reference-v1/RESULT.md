# Résultat actuel

Statut : **candidat hors imprimante prêt, effet bloqué**.

La recette pure produit six checkpoints séparés : chauffe et observation du
flux, un carré E4 chaud, refroidissement sans essuyage, un carré E4 stable à
`140 °C`, une référence finale unique et l'arrêt thermique d'urgence.

La matière précédente et sa température de nettoyage restent volontairement
vides. Tant qu'elles ne sont pas explicites, aucun runner physique n'est créé
et aucune commande ne peut atteindre la K1.

Vérifications : `8/8` tests propres au candidat, `14/14` avec le registre du
Goal 3, puis suite complète de `561` tests dont `558` verts et `3` ignorés
connus. Connexion, G-code, chauffe, mouvement, CFS et écriture distante : zéro.
