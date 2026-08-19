# Rapport de nettoyage

Capture : `20260819-1627-k1max-stock`
Matière brute conservée localement : oui, sous un chemin ignoré par Git
Relecteur : Codex, revue humaine encore requise
Date : 2026-08-19

## Catégories détectées dans la capture brute

- adresse IP privée et nom d’hôte ;
- adresses MAC et configuration Wi-Fi ;
- identifiant unique d’appareil utilisé par mDNS et WebRTC ;
- chemins cloud et fichiers potentiellement liés au compte Creality ;
- identifiants uniques de modules dans `SAVE_CONFIG` ;
- historique d’impression, miniatures et journaux ;
- nom d’utilisateur et chemin local Windows dans les transcriptions ;
- configurations constructeur complètes.

## Transformations appliquées

- suppression de toutes les adresses privées, noms d’hôte, MAC, SSID et identifiants uniques ;
- absence de publication des transcriptions et fichiers bruts ;
- représentation des fichiers constructeur par rôle, taille et SHA-256 ;
- publication uniquement des relations de macros et des valeurs nécessaires au diagnostic ;
- généralisation des processus dont les arguments contenaient un identifiant privé ;
- retrait des meshes, historiques, miniatures, données cloud et détails réseau.

## Fichiers retenus en privé

- capture SSH brute et transcriptions locales ;
- configurations complètes et leurs instantanés historiques ;
- fins et archives de journaux ;
- fichiers cloud, réseau, historique, image et CFS utilisateur ;
- clé d’hôte SSH locale ;
- scripts temporaires d’acquisition et d’analyse.

## Vérifications

- les chemins bruts sont couverts par `.gitignore` ;
- aucun fichier constructeur complet n’est ajouté à Git ;
- les scans automatiques d’adresses, hôtes, MAC, identifiants, mots de passe, jetons et clés ne montrent aucun secret dans les sorties publiques ;
- les correspondances au format IPv4 ont été relues : elles sont uniquement des numéros de version ;
- une lecture manuelle ciblée des manifestes, tableaux et conclusions n’a trouvé aucun identifiant résiduel.

## Incertitude résiduelle

Les sommes de contrôle sont publiées pour permettre la comparaison sans divulguer les fichiers. Elles ne sont pas considérées comme des secrets. Les noms génériques des chemins système sont conservés car ils sont nécessaires à la reproductibilité.
