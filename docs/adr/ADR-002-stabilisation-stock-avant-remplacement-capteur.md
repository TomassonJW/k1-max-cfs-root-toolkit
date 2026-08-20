# ADR-002 — Stabiliser la pile stock avant de remplacer le capteur ou le firmware

Date : 2026-08-20

Statut : **proposé ; aucune autorisation de déploiement**

## Contexte

La K1 Max CFS `2.3.5.34` présente plusieurs défauts mêlés : référence Z
variable, purge exécutée avant le correctif Z du G-code, carte du plateau stock opaque,
température CFS fixe à `220 °C`, nettoyage insuffisant et profils Orca chargés
de contournements.

Deux CFS doivent être conservés et quatre sont visés. L'écran et les services
Creality restent utiles. PR Touch a montré des reprises et des résultats
internes aberrants, mais les essais A1/B/A2 ne permettent pas encore de prouver
que le matériel du capteur est la cause finale.

## Options

### 1. Installer immédiatement un lot Helper Script

Avantage : mise en place rapide d'interfaces et d'outils connus.

Refus proposé : le lot ne garantit ni l'ordre Z/purge ni la propriété dynamique
des températures CFS. Il ajoute plusieurs changements difficiles à attribuer et
à annuler.

### 2. Niveau A renforcé

Conserver firmware, écran et CFS. Construire un analyseur local, puis déployer
des fichiers originaux, séparés et réversibles pour une seule séquence de
démarrage, le contrat de température dynamique et les profils Orca.

Avantage : meilleur compromis entre délai, sécurité, compatibilité et contrôle.

Limite : si PR Touch reste instable après nettoyage et ordre déterministe, un
autre capteur sera encore nécessaire.

### 3. Niveau A avec BTT Eddy immédiat

Avantage : mesure rapide sans contact et pile capteur plus ouverte.

Refus proposé pour l'instant : l'intégration exacte K1 Max `2.3.5.34` + CFS est
communautaire, le Z-offset employé reste signalé bêta et la calibration
thermique/mécanique ajoute de nouvelles causes avant d'avoir isolé l'ancienne.

### 4. SimpleAF/Klipper moderne et MMU ouvert

Avantage : contrôle maximal et code lisible.

Refus proposé pour la stabilisation immédiate : SimpleAF n'offre pas de prise en
charge prête à l'emploi du CFS propriétaire. La conservation de 2–4 CFS impose
un pilote encore expérimental ou le remplacement physique du système de
filament. Le délai est de plusieurs semaines, pas de quelques jours.

## Décision proposée

Adopter le niveau A renforcé et analyser avant de déployer. Utiliser un outil
local en lecture seule par défaut. Ne déployer qu'un changement G4 nommé à la
fois. Faire du BTT Eddy une porte de décision mesurée, pas un prérequis.

Le contrat de sécurité interdit toute trajectoire basse et toute extrusion avant
référence Z finale cohérente, politique de carte du plateau connue et correction effective
déjà active.

## Conséquences

- le correctif Z Orca actuel reste temporairement en place jusqu'à la bascule
  atomique vers la séquence machine validée ;
- aucun Helper Script complet, Mainsail, Moonraker, firmware ou Eddy n'est
  installé par cette décision ;
- le premier livrable est un analyseur et un paquet de sécurité hors ligne ;
- la température dynamique CFS peut nécessiter le remplacement ciblé de son
  propriétaire compilé si les macros ne couvrent pas tous les chemins ;
- l'évolution vers quatre CFS reste dans le modèle dès le départ ;
- la licence du futur code reste à choisir selon D-009 et les dépendances
  réellement réutilisées.

## Critères d'acceptation de l'ADR

- exports Orca et G-code actuels inventoriés ;
- chronologie complète du démarrage actuel produite ;
- risque de purge avant offset confirmé dans les fichiers ;
- stratégie de récupération S12 et retour arrière de configuration documentés ;
- Thomas accepte explicitement le niveau A renforcé comme première voie.
