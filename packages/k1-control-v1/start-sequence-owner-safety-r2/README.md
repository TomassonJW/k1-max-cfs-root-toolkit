# Correctif départ et fin sûre R2

Ce paquet corrige les deux défauts observés pendant le premier essai physique
du départ possédé.

La purge V1 allait de `X15 Y20` à `X15 Y180`. La ligne restait sur le bord
gauche, mais son filet terminal partait de `Y180`, en pleine zone utile. R2
place la ligne à `X5`, l'exécute de `Y180` vers `Y20`, rétracte `1,2 mm` puis
remonte à `Z5`. Le filet terminal doit donc rester près du coin avant gauche.
Cette géométrie reste candidate jusqu'au verdict humain.

La fin d'essai V1 libérait directement les moteurs à hauteur de couche. R2
coupe les chauffes, descend d'abord le plateau à `Z50`, parque la tête à
`X203 Y273`, attend la fin des mouvements, puis libère les moteurs. Aucun
nouveau `G28` n'est exécuté en fin normale puisque les axes sont encore
référencés.

Le fichier thermique précédemment envoyé sur la K1 a été supprimé après
vérification exacte de son empreinte. Aucun nouvel essai n'est permis avant la
validation hors imprimante, la pose contrôlée de la macro corrigée et un
préflight frais.
