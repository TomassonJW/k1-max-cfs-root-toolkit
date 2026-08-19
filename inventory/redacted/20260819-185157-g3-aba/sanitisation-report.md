# Rapport de nettoyage — 20260819-185157-g3-aba

- Capture : `20260819-185157-g3-aba`
- Date : 2026-08-19
- Source brute conservée localement : oui, sous chemin ignoré
- Relecteur : Codex

## Données détectées dans la source brute

- cible SSH et nom d'hôte privé ;
- nom de compte et chemin Windows local ;
- flux Klipper complet ;
- noms des G-codes privés ;
- détails internes CFS et PR Touch ;
- contenu constructeur déjà inventorié séparément.

## Transformations

- aucune adresse, cible SSH, identité Windows ou chemin personnel publié ;
- noms privés remplacés par les identifiants logiques A1, B et A2 ;
- journaux complets remplacés par une chronologie minimale ;
- aucune photo publiée ;
- aucun fichier constructeur recopié ; son comportement est seulement reformulé ;
- empreintes des G-codes conservées car elles ne révèlent pas leur contenu.

## Fichiers retenus hors Git

- capture console complète ;
- transcription PowerShell ;
- fiches détaillées de session ;
- G-codes complets ;
- sorties contenant des coordonnées ou données internes inutiles au rapport public.

## Incertitude résiduelle

Le rapport publie des valeurs internes Z nécessaires au diagnostic, mais ne les présente pas comme un offset utilisateur. La valeur finale de pression d'avance n'est pas déduite en l'absence de lecture directe après le démarrage.
