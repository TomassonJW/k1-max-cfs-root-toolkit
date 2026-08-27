# JOB-LIFECYCLE-OBSERVER-V1

Observateur passif des exigences 4, 5 et 6 du Goal 3 : changement de filament,
runout, pause/reprise, annulation, fin normale et désengagement séparé.

Il lit quatre fois par seconde les états d'impression et de pause, progression,
couches, chauffes, position, mesh, Z accepté, routes CFS, commande active et
capteurs. Le nom du fichier imprimé et les identités matérielles ne sont jamais
exportés.

Le programme ne contient aucun chemin de commande : aucun G-code, contrôle du
job, mouvement, chauffage, effet CFS, fichier distant ou service. Les actions
réelles seront déclenchées par Thomas dans les interfaces prévues, sous une gate
humaine distincte. La capture ne remplace jamais son verdict visible.

La baseline réelle est verte : onze lectures sur cinq secondes, machine au
repos, cibles zéro, deux CFS connectés, profil `11 × 11`, Z `−0,04 mm` et
configurations inchangées. Aucun checkpoint d'impression n'est encore qualifié.
