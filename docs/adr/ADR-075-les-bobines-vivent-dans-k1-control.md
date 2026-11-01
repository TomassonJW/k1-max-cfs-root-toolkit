# ADR-075 - Les bobines vivent dans K1 Control, sur la K1

Date : 31 octobre 2026. Statut : acceptée par Thomas le 31 octobre 2026,
option 1.

## Contexte

Thomas veut gérer ses bobines dans Mainsail : stock, reste en grammes et en
mètres, bibliothèque des bobines vides, décompte après chaque impression,
synchro avec le CFS ([document 102](../102-gestion-des-bobines-plan-v1.md)).
Il faut choisir où vivent ces données. C'est une décision de propriété des
données et de déploiement : elle revient à Thomas.

## Option 1 - K1 Control, sur la K1 (retenue)

Un composant du Moonraker dédié et des fichiers JSON sous
`/usr/data/k1-control-v1/state/spools/`.

Pour :

- marche même Proxmox éteint, sans aucune dépendance réseau ;
- tout tient dans la fenêtre de Mainsail ;
- le décompte par emplacement se fait au plus près des événements du CFS ;
- même technique que la fenêtre de départ, déjà en service.

Contre :

- stock, calculateur et bibliothèque sont à écrire nous-mêmes ;
- les données sont sur la K1 : d'où trois copies, un journal et l'export sur
  le PC.

## Option 2 - Spoolman sur le Proxmox

Un conteneur [Spoolman](https://github.com/Donkie/Spoolman), relié au
composant `spoolman` de Moonraker.

Pour :

- brique libre et mûre : stock, lieux, étiquettes, plusieurs imprimantes ;
- SpoolmanDB intégré.

Contre :

- la fenêtre dans Mainsail et la synchro CFS restent à écrire ;
- l'édition complète du stock se fait dans la page de Spoolman, à part ;
- une seule bobine active, à changer à chaque changement d'outil ;
- consommation en attente perdue si Moonraker redémarre pendant que Spoolman
  est injoignable ;
- la K1 dépend d'un autre serveur pour une fonction quotidienne.

## Décision

Option 1, choisie par Thomas le 31 octobre 2026 (« Oui, dans la K1 ») après la
mesure des ressources de la K1 pendant une impression (document 102,
section 3). Le modèle de données est calqué sur Spoolman (fabricant, filament,
bobine, mêmes unités) : si Thomas installe Spoolman un jour, un export suffit,
sans ressaisie.

## Conséquences

- Les lots A à K du document 102 se construisent et se prouvent hors
  imprimante ; la pose attend leurs preuves (sections 11 et 12).
- Klipper n'est pas modifié, la pose ne redémarre que le Moonraker dédié, au
  repos, et le reste RFID du CFS n'est jamais écrit.
