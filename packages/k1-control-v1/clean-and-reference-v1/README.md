# CLEAN-AND-REFERENCE-V1

Deuxième exigence physique du Goal 3.

Statut : **pilote physique complet et préflight live sans effet verts ; effet
bloqué jusqu'à résolution explicite de la matière présente dans la tête et de
sa température de nettoyage**.

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

Deux lectures live montrent les deux CFS connectés, aucune route engagée et les
codes matière actuels des huit slots. Elles ne peuvent pas identifier le
segment déjà présent dans la tête. L'historique retenu contient en outre un
marqueur de chargement postérieur au retrait historique T1A ; T1A/`000001` ne
peut donc pas être promu en identité actuelle par déduction.

Le préflight live du pilote est vert à la position `X203 Y273 Z32`, chauffes à
zéro, profil `11 × 11` exact et configurations inchangées. La valeur
`CFS_TYPE_000001_PROVISIONAL / 220 °C` utilisée pour tester ce préflight reste
explicitement interdite pour les actions physiques tant qu'elle n'est pas
confirmée.
