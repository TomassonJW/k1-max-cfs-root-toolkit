# Correctif départ et fin sûre R2

Ce paquet corrige les deux défauts observés pendant le premier essai physique
du départ possédé.

La purge V1 allait de `X15 Y20` à `X15 Y180`, lentement et sans retour. La
source constructeur `CX_PRINT_DRAW_ONE_LINE` confirme le tracé normal décrit
par Thomas : aller de `X0,1 Y20` à `Y180`, retour à `X0,4 Y20`, `10 mm`
extrudés par passage et vitesse `F3000`. La course réelle autorise `X0,1`
(`X mini = -2`), il n'est donc pas nécessaire de déplacer ce filet dans la
zone imprimable. R2 ajoute seulement un dégagement vers `Y10`, une rétraction
de `1,2 mm` et une remontée à `Z5`. Cette géométrie reste candidate jusqu'au
verdict humain.

La fin d'essai V1 libérait directement les moteurs à hauteur de couche. R2
coupe les chauffes, descend d'abord le plateau à `Z50`, parque la tête à
`X203 Y273`, attend la fin des mouvements, puis libère les moteurs. Aucun
nouveau `G28` n'est exécuté en fin normale puisque les axes sont encore
référencés.

Le fichier thermique précédemment envoyé sur la K1 a été supprimé après
vérification exacte de son empreinte. Aucun nouvel essai n'est permis avant la
validation hors imprimante, la pose contrôlée de la macro corrigée et un
préflight frais.

## Mise à jour préparée

Le déployeur R2 remplace seulement le fichier du propriétaire déjà inclus. Il
ne modifie pas `printer.cfg`. Avant remplacement, il exige la version V1 exacte,
un état sûr et `T1A` unique, puis sauvegarde le fichier avec son empreinte. Il
attend une vraie transition du socket après le restart Klipper, recharge une
seule fois le mesh `11 × 11` et exécute le self-test froid du surveillant. Au
premier écart après mutation, il restaure exactement V1, redémarre Klipper et
revérifie le même état sûr.

La première pose autorisée a été rollbackée : le restart Klipper a fait
disparaître l'association logique `T1A`, et le validateur exigeait à tort sa
conservation pendant une pose froide. V1 et `printer.cfg` ont été restaurés à
leurs empreintes exactes. Deux lectures finales stables confirment un état froid
et sûr, mais aucune route logique engagée. Cela ne prouve pas la position
physique du filament.

Le déployeur corrigé accepte désormais zéro route ou une route unique `T1A`
pendant la pose froide ; toute autre route ou ambiguïté reste bloquée. La
présence de `T1A` redevient, correctement, un préalable séparé du futur essai
physique. Comme le déployeur a changé après l'autorisation consommée, cette
nouvelle préparation n'autorise ni connexion K1, ni nouvelle pose, ni purge.
