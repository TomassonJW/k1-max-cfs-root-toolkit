# Observation V3 + PATHS-V1 du 21 août 2026

Statut : **OK pour la coexistence de la fondation ; ne prouve pas la correction
des défauts d'impression**.

## Périmètre

La fondation déjà installée a été observée sans transmettre de G-code et sans
modifier l'imprimante. Thomas a choisi et lancé manuellement une impression
normale à 12:48 avec le flux Creality/Orca existant.

L'observation couvre trois fenêtres complémentaires :

- abonnement Klipper passif de 12:31 à 15:07 ;
- journal Klipper persistant de 15:07 à 18:43:35 ;
- abonnement Klipper passif détaché de 18:43:35 à 20:31:56.

Le premier observateur a été arrêté côté poste de travail. Le trou de
souscription n'a pas été présenté comme une observation continue : il a été
reconstruit séparément à partir du journal persistant copié en lecture seule.

## Résultat de l'impression

Thomas a confirmé la fin vers 18:43 : qualité correcte, un seul PLA utilisé et
aucune intervention. Ce résultat est une preuve de coexistence utile, pas une
preuve que les incidents aléatoires Z/CFS sont résolus.

## Résultat technique

Le créneau reconstruit contient 209 501 lignes. L'analyse bornée n'a trouvé :

- aucun arrêt Klipper ;
- aucun arrêt MCU ;
- aucune perte de communication ;
- aucune trace Python ;
- aucune erreur interne.

Les 8 530 couples avertissement/erreur très fréquents correspondent au bruit
constructeur déjà observable `Serial_485 #unknown` et `buf_len = 0x0`. Une
unique mention « disconnected » provient du client Webhooks au moment exact de
l'arrêt du premier observateur local ; elle ne concerne pas un CFS.

Le second observateur a atteint sa durée prévue, fermé son abonnement et rendu
`exit_code=0`, sans erreur locale. La validation finale séparée et en lecture
seule a obtenu `VALIDATE_PATHS_V1_OK`. Elle confirme la pile dédiée, les chemins,
les protections, les processus Creality et les deux CFS dans l'état attendu.

## Conclusion

La fondation V3 + PATHS-V1 est retenue comme base finale pour construire K1
Control. Aucune nouvelle campagne d'impression sacrificielle n'est demandée.
La suite est le candidat hors imprimante
`G4-K1-CONTROL-Z-MESH-RUNTIME-V1`, puis sa gate exacte avant toute mutation.
