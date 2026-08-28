# Validation live en lecture seule du garde d’exclusion CFS V1

Cette gate relie deux lectures réelles, nettoyées sur la K1, à l’adaptateur pur
du garde d’exclusion. Elle ne peut ni importer le garde, ni envoyer une commande,
ni écrire un fichier distant, ni produire un effet physique.

Le collecteur exécute une seule session SSH et exactement deux requêtes HTTP
`GET` vers le Moonraker local. Les identifiants CFS ne quittent pas la K1. Trois
empreintes de configuration sont comparées avant et après.

Le contrat refuse d’inventer une époque de connexion. Les objets K1 actuels
montrent l’état des CFS mais ne signalent pas une reconnexion qui reviendrait au
même état entre deux lectures. Si ce champ reste absent, la gate doit se fermer
en KO borné même si tous les autres champs sont stables.

La capture V1 a aussi montré que `gcode_move.homing_origin[2]` vaut presque
zéro et ne peut pas remplacer le Z accepté stocké. V1 est donc close et ne doit
pas être rejouée. Une correction hors imprimante devra retourner la valeur Z
acceptée explicitement et concevoir séparément une vraie époque de connexion.
