# Goal 2 — qualification K1 en lecture seule

Date : 27 août 2026

## Résultat en langage courant

Le système hors imprimante a été comparé à la vraie K1 sans lui demander
d'action. Deux lectures fraîches ont confirmé que l'imprimante est au repos,
que les chauffes sont coupées, que les axes sont libérés, que les deux CFS sont
connectés et qu'aucune route de filament n'est engagée. Le segment situé après
le cutter est toujours vu par le capteur de tête, donc l'identité du filament
reste inconnue, ce qui est le classement prudent attendu.

La lecture seule elle-même est qualifiée : les deux réponses ont la même forme,
les requêtes d'état prennent `199,212 ms` et `235,525 ms`, sous un plafond de
`5 s`, et les fichiers relus par empreinte n'ont pas changé.

La suite physique reste bloquée. La K1 utilise actuellement le mesh `default`.
Sa matrice `6 × 6` n'est pas celle du profil robuste
`k1_p001_t055_r001_n06x06`. Ce dernier existe encore avec la bonne empreinte,
mais il n'est pas actif. Aucune commande n'a été envoyée pour le charger, car
cela aurait dépassé l'autorité de cette mission.

## Données réellement sorties de la K1

La capture ne contient que :

- les noms de clés nécessaires pour détecter une dérive de forme ;
- les états d'impression, CFS, capteurs, températures, Z et mesh autorisés ;
- des résumés et empreintes de matrices ;
- les empreintes des configurations et composants installés ;
- les noms des sections Moonraker, sans leurs valeurs ;
- les temps de réponse.

Les numéros de série, UUID, noms de fichiers d'impression, contenus de
configuration et contenus de journaux ne sont pas exportés.

## Mapping des deux CFS

Les deux lectures voient `T1` et `T2` connectés, `T3` et `T4` non configurés,
et aucune route. Le cache reste valable entre ces deux lectures. Le contrat
invalide ce cache dès que l'état d'une unité, une route ou l'époque de connexion
change.

Une reconnexion très courte pourrait toutefois se produire entre deux sondages
et retrouver exactement le même état. Le futur composant Moonraker devra donc
compter les changements de connexion à partir des notifications. Aucune
reconnexion n'a été provoquée pendant cette gate.

## Points d'intégration préparés

Le choix recommandé est un composant Moonraker séparé du composant de
calibration. Le collecteur `GET`, son plafond de `5 s`, le nettoyage et la
traduction sont maintenant testables. Restent volontairement absents : le
connecteur de commande, le câblage Moonraker, le script de pose, le restart, la
mutation Orca et toute surface d'effet.

## Limite et prochaine gate

Le Goal 2 est clos avec le statut
`CLOSED_READ_ONLY_BLOCKED_MESH_DRIFT`. Avant toute tranche physique, Thomas devra
être devant la K1 et autoriser une gate distincte qui vérifie puis charge le
profil robuste sans lancer d'impression. Ce Goal n'autorise pas cette action.
