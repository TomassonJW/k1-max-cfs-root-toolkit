# Préflight réel `G4-K1-CONTROL-Z-MESH-RUNTIME-V1`

Date : 2026-08-21

Capture privée : `20260821-212431-g4-k1-control-z-mesh-runtime-v1`

## Résultat

Le premier GO exact a permis de lancer le préflight. Il a échoué avant toute
mutation : le programme Python fourni sur stdin recevait `0` comme nom de
fichier. Aucun dossier de sauvegarde distant, fichier runtime, include, G-code,
commande Klipper ou redémarrage de service n'a été exécuté.

Le déployeur a été corrigé sur deux lignes : les appels Python qui ont des
arguments utilisent désormais explicitement `python -`. Un test de
non-régression vérifie les deux formes. La suite complète est verte : 94 tests
exécutés, 93 passés et un contrôle Jinja ignoré localement, déjà couvert sur
l'environnement Python/Jinja exact de la K1.

Le second préflight, classé en lecture seule, est vert :

- machine `standby`, sans fichier actif ;
- cibles buse et plateau à `0` ;
- `printer.cfg` conforme à l'empreinte revue ;
- runtime, include et état persistant absents ;
- fondation V3 + PATHS-V1, ports et processus conformes ;
- deux CFS connectés en version `1.1.3` ;
- axes `xyz` encore référencés et mesh transitoire `Base` actif, ce que le
  préflight autorise avant le redémarrage hôte de la pose.

Les preuves détaillées restent privées et ignorées par Git, car l'état CFS brut
contient des identifiants machine.

## Décision de sécurité

Le runtime n'est pas installé. La correction ne change aucun des deux fichiers
runtime ni leur empreinte, mais elle modifie une commande revue après le GO.
Conformément à G4, la pose corrigée attend donc un GO exact renouvelé :

`GO G4-K1-CONTROL-Z-MESH-RUNTIME-V1`
