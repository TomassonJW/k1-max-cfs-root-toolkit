# Plan de preuves suivant — propriétaire filament minimal

Ce document ne donne aucune autorisation de connexion ou d'action physique.
Il fixe seulement ce qu'une gate ultérieure devra apporter avant qu'une seule
trame puisse entrer dans une liste appelable.

## Priorité 1 — source statique ou spécification

La meilleure preuve serait une source lisible correspondant exactement à
l'empreinte du module capturé, ou une spécification constructeur versionnée.
Elle doit définir :

- la longueur, l'intégrité et la terminaison des trames ;
- chaque commande, sous-commande, état et payload ;
- la corrélation, les événements spontanés, les retries et les timeouts ;
- l'adressage des deux CFS et des quatre slots ;
- le cycle exclusif : prendre la main, confirmer, agir, arrêter, rendre la main ;
- le comportement après perte, reconnexion et changement de mapping.

Une correspondance de nom ou de version sans identité binaire ne suffit pas.

## Priorité 2 — captures passives contrôlées

Si aucune source exacte n'existe, une mission séparée devra d'abord préparer
et faire revoir un protocole de capture passive. Toute connexion à la K1,
toute manipulation de filament et toute action du CFS demanderont alors une
autorité fraîche et explicite.

La campagne minimale devra isoler, une fois chacune, sans déduire les autres :

1. état et présence sur adresses 1 et 2 ;
2. A/B/C/D sur chaque unité ;
3. chargement, retrait, coupe, purge, arrêt et annulation ;
4. réponse normale, erreur, perte, réponse tardive et reconnexion ;
5. changement de route pendant une session ;
6. prise et restitution du propriétaire constructeur.

Chaque cas devra garder l'état initial, le geste humain exact, les octets
horodatés, l'état final, les erreurs et le rollback. Aucun autre effet ne devra
être lancé en parallèle.

## Critère de réouverture

La liste appelable reste vide tant que **toutes** les opérations nécessaires à
un cycle filament minimal ne sont pas reliées à une preuve exacte et que
l'exclusion du propriétaire stock n'est pas démontrée.

Une future gate peut qualifier un sous-ensemble de requêtes de lecture sans
autoriser les effets filament. Elle ne pourra préparer un transport ou un
déploiement qu'après une nouvelle ADR et un GO exact distinct.
