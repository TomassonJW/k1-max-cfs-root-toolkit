# Journal public de l’acquisition

Capture : `20260819-1627-k1max-stock`
Date : 2026-08-19
Mode distant : lecture seule

| Étape | Classe de commandes | Résultat | Écriture distante |
|---|---|---|---|
| Découverte locale | Résolution de nom, réponse HTTP et test du port SSH | machine identifiée | aucune |
| Préflight | Statut Git, règles du dépôt, création du stockage brut ignoré | OK | aucune |
| Identité SSH | `uname -a` | K1 Max MIPS sous Linux confirmée | aucune |
| Inventaire système | identité, version, montages, espace, processus et scripts d’initialisation | OK | aucune |
| Acquisition finale | lectures ciblées, listes de fichiers, `stat`, `sha256sum`, contenus de configuration et fins de journaux | OK | aucune |
| Analyse locale | extraction des faits, graphe d’inclusion, index des macros et nettoyage | OK | aucune |

Les commandes distantes mutantes, les redirections distantes, les installations, les redémarrages, les mouvements, la chauffe et les calibrations n’ont pas été utilisés.

Le mot de passe a été saisi uniquement dans une fenêtre SSH interactive. Il n’a été ni enregistré ni intégré à un fichier du projet.
