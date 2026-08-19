# Rapport de nettoyage de l’acquisition ciblée

Capture : `20260819-1726-k1max-targeted-sources`

Matière brute conservée localement : oui, sous un chemin ignoré par Git

Date : 2026-08-19

## Données privées retenues hors Git

- adresse réseau, nom d’hôte et lignes de processus complètes ;
- contenu intégral des scripts et sources constructeur copiés depuis la machine ;
- contenus complets des variantes de configuration ;
- transcriptions SSH et PowerShell ;
- chargeurs, modules compilés et autres fichiers constructeur bruts.

## Sorties publiques

- rôles, tailles et SHA-256 des fichiers nécessaires à la reproductibilité ;
- relations entre commandes sans reproduction du code constructeur ;
- résultat S12/structure 0 sans numéro de série, MAC ou contenu de partition ;
- conclusions séparées de leurs limites.

## Vérifications

- `inventory/raw/` reste ignoré par Git ;
- aucun mot de passe, jeton, clé, SSID, MAC, numéro de série, IP privée ou nom d’hôte n’est publié ;
- aucun fichier constructeur complet ni binaire n’est ajouté à Git ;
- les empreintes des captures privées permettent de détecter toute modification locale ultérieure.
