# Résultat — capture passive du retrait officiel CFS V1

Date : 2026-08-27

Verdict de capture : **OK**.

Verdict du protocole propriétaire : **KO borné**.

## Ce qui a réellement fonctionné

- la K1 était au repos, chauffes demandées à zéro et CFS connecté ;
- la route active a été lue avant l'action : `T1A` ;
- la macro constructeur `BOX_QUIT_MATERIAL` a été lancée une seule fois ;
- elle a terminé en environ 106 secondes ;
- le retrait vers le tampon puis vers le CFS a obtenu deux réponses réussies ;
- l'état du premier CFS est passé de filament `A` à aucun filament engagé ;
- les trois fichiers de configuration contrôlés sont restés identiques ;
- l'état final est `standby`, CFS connecté et cibles thermiques à zéro.

## Ce que la capture révèle aussi

La K1 a demandé automatiquement `220 °C` au cours du retrait, alors que cette
chauffe n'est pas visible dans les cinq lignes de la macro de haut niveau. La
macro n'a pas remis cette cible à zéro après sa fin.

Une première tentative locale d'arrêt avec `%20` dans l'URL a été interprétée
comme une commande inconnue. L'API HTTP a malgré tout répondu `ok`. Seule la
vérification de l'effet réel a détecté l'échec. `TURN_OFF_HEATERS`, sans espace,
a ensuite ramené effectivement la cible à zéro.

Le CFS considère `T1A` comme désengagé, mais le capteur de filament de la tête
reste actif. Le retrait officiel enlève donc la partie amont après la coupe ; il
ne vide pas à lui seul le segment restant dans la tête.

## Ce qui reste non prouvé

- aucune confirmation humaine ou capteur dédié ne prouve directement la coupe ;
- la requête série sortante complète avec son en-tête et son CRC reste absente ;
- aucune prise de contrôle exclusive du bus n'est qualifiée ;
- B/C/D, le second CFS, chargement, purge et fautes ne sont pas qualifiés ;
- les messages `auto_addr` sans réponse, présents avant, pendant et après le
  retrait, doivent être étudiés séparément.

La prochaine solution fiable proposée n'imite donc pas encore le protocole
série. Elle encadre la commande constructeur avec des contrôles avant/après et
un arrêt garanti des chauffes.
