# CLEAN-AND-REFERENCE-V1

Deuxième exigence physique du Goal 3.

Statut : **matière Geetech et cible `220 °C` confirmées ; préflight live de la
séquence atomique vert ; attente de Thomas devant la K1 pour l'essai observé**.

Cette tranche réutilise uniquement le carré de la brosse du bac qualifié par
E4 : `X203..206 / Y304..305 / Z32`, avec entrée et sortie à
`X203 Y273 Z32`. Elle n'invente ni diagonale, ni nouvelle profondeur, ni
extrusion, ni commande CFS.

Le cycle de nettoyage est une seule action surveillée :

1. vérifier l'état sûr, les axes référencés, le profil `11 × 11` exact et les
   configurations ;
2. se placer `3 mm` au-dessus du carré du bac, chauffer à la température
   explicite de la matière précédente et attendre une fenêtre bornée ;
3. sous observation directe de Thomas, exécuter six allers-retours rapides
   dans le carré E4 à `220 °C` ;
5. couper la chauffe de buse, continuer les passages à `F30` dans ce même
   carré et remonter progressivement de `Z32` à `Z34` selon la température
   réellement mesurée ; la durée `20 s` est une estimation, jamais une règle ;
6. finir à `Z34` autour de `140 °C` et remettre immédiatement les deux cibles
   à zéro ;
7. seulement après confirmation visuelle de la buse propre, rétablir la fenêtre
   de référence `140/55 °C`, lancer une seule fois `ACCURATE_G28`, recharger le
   meilleur profil actuel `11 × 11`, remettre les chauffes à zéro
   et relire l'état final.

Toute réponse humaine négative coupe les chauffes et ferme la suite. Aucun
checkpoint physique n'est rejoué automatiquement. La chauffe seule séparée a
été supprimée après un essai interrompu : aucune attente de réponse ne peut
désormais laisser la cible à `220 °C`.

Deux lectures live montrent les deux CFS connectés, aucune route engagée et les
codes matière actuels des huit slots. Elles ne peuvent pas identifier le
segment déjà présent dans la tête. L'historique retenu contient en outre un
marqueur de chargement postérieur au retrait historique T1A ; T1A/`000001` ne
peut donc pas être promu en identité actuelle par déduction.

Le préflight frais du programme atomique est vert à la position d'observation
sûre `X204,5 Y304,5 Z35`, chauffes à zéro, profil `11 × 11` exact et
configurations inchangées. Il n'a envoyé aucun G-code et n'a produit aucun
mouvement ni chauffe.
