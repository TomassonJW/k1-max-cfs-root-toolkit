# CLEAN-AND-REFERENCE-V1

Deuxième exigence physique du Goal 3.

Statut : **candidat hors imprimante ; effet bloqué jusqu'à résolution explicite
de la matière et revue de la température**.

Cette tranche réutilise uniquement le carré de la brosse du bac qualifié par
E4 : `X203..206 / Y304..305 / Z32`, avec entrée et sortie à
`X203 Y273 Z32`. Elle n'invente ni diagonale, ni nouvelle profondeur, ni
extrusion, ni commande CFS.

Le cycle prévu est volontairement découpé :

1. vérifier l'état sûr, les axes référencés, le profil `11 × 11` exact et les
   configurations ;
2. se placer `3 mm` au-dessus du carré du bac, chauffer à la température
   explicite de la matière précédente et attendre une fenêtre bornée ;
3. demander à Thomas de confirmer que l'écoulement naturel tombe bien dans le
   bac ;
4. exécuter un seul carré E4 à température de nettoyage, puis confirmer
   visuellement l'efficacité ;
5. remonter, revenir au-dessus du bac et refroidir sans essuyage jusqu'à la
   fenêtre de référence `140 ± 2 °C` ;
6. exécuter un seul carré E4 stable à `140 °C`, confirmer la buse propre, puis
   lancer une seule fois `ACCURATE_G28` ;
7. recharger le meilleur profil actuel `11 × 11`, demander les chauffes à zéro
   et relire l'état final.

Toute réponse humaine négative coupe les chauffes et ferme la suite. Aucun
checkpoint physique n'est rejoué automatiquement.
