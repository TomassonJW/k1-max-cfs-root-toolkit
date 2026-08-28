# Essai physique du départ possédé avec `T1A` conservé

Cette gate lance une seule fois le petit fichier de deux couches déjà vérifié.
Elle exige `T1A`, le mesh `11 × 11`, le Z accepté `−0,04 mm`, le propriétaire au
repos, des chauffes à zéro et les configurations exactes.

Le nettoyage de buse reste manuel. Le pilote n'envoie ensuite qu'un jeton de
confirmation, puis démarre le fichier exact une fois. Il surveille le filament,
les températures et les phases du propriétaire. Il ne relance jamais l'essai.

La macro stock `END_PRINT` a été retirée avant le premier lancement réel après
lecture de son corps installé : elle appelait encore `BOX_END` et
`BOX_END_PRINT`. La fin bornée coupe les chauffes, désarme et remet le
propriétaire au repos, coupe les ventilateurs puis libère les moteurs.

La preuve automatique ne remplace pas deux constats humains : une purge visible
et correcte, puis une première couche correctement déposée. Sans ces deux
constats, l'exigence physique reste ouverte.
