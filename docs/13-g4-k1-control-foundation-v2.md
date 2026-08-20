# 13 — G4-K1-CONTROL-FOUNDATION-V2

Date : 2026-08-20

Statut : **paquet de remplacement préparé hors imprimante ; non autorisé**

## Pourquoi V2 existe

Le préflight approuvé de V1 s'est arrêté avant toute copie : la K1 ne possède
ni `logrotate`, ni `/etc/logrotate.d`. V2 retire cette dépendance au lieu
d'installer un paquet supplémentaire.

La machine possède déjà :

- `/sbin/syslogd -n` actif ;
- la socket `/dev/log` ;
- BusyBox `syslogd`, dont la rotation par défaut est bornée à 200 Kio avec une
  sauvegarde ;
- la rotation quotidienne interne de Moonraker avec deux sauvegardes.

nginx enverra donc ses erreurs au syslog existant. Aucun service de journal,
cron, paquet ou fichier sous `/etc/logrotate.d` n'est ajouté.

`K1-CONTROL-V1` reste le nom de la première génération du système complet.
`FOUNDATION-V2` désigne la deuxième révision de son paquet d'installation,
après le rejet sûr de V1 ; ce ne sont pas deux interfaces concurrentes.

## Périmètre exact

V2 ajoute uniquement :

- Moonraker MIPS figé au commit
  `fccffa96c63ed77dc3953e18615e9fe9cd3d69ea` ;
- nginx MIPS du même paquet audité ;
- Mainsail `v2.18.2` ;
- deux nouveaux services portant des noms propres au projet ;
- des dossiers versionnés sous `/usr/data/k1-control-v1` ;
- un port local `7125` et, après création du compte, le port LAN `4409`.

V2 ne modifie pas `printer.cfg`, `gcode_macro.cfg`, `box.cfg`, `START_PRINT`,
`END_PRINT`, le Z, le mesh, les CFS, le firmware, les interfaces Creality ou le
profil Orca. Le post-traitement actuel `+0,27 mm` reste actif.

## Préflight obligatoire et sans effet

Avant toute copie :

1. confirmer S12 structure 0 et firmware `2.3.5.34` ;
2. confirmer `print_stats=standby`, cibles chauffe à zéro et machine non homée ;
3. confirmer T1 et T2 en état `connect`, version `1.1.3` ;
4. relever RAM, swap, stockage, ports et processus Creality ;
   exiger au moins 512 Mio libres sous `/usr/data` ;
5. confirmer `/sbin/syslogd -n`, `/dev/log` et ses valeurs de rotation BusyBox ;
6. confirmer l'absence des deux services et de `/usr/data/k1-control-v1` ;
7. reconstruire le bundle et vérifier les trois archives par taille et SHA-256.

Toute différence arrête la pose avant mutation.

## Chemins créés

- `/usr/data/k1-control-v1/releases/K1-CONTROL-V1.0.0` ;
- `/usr/data/k1-control-v1/current` ;
- `/usr/data/k1-control-v1/state` ;
- `/usr/data/k1-control-v1/logs` ;
- `/usr/data/k1-control-v1/tmp` ;
- `/usr/data/k1-control-v1/backups/<UTC_CAPTURE_ID>` ;
- `/usr/data/k1-control-v1/staging/<UTC_CAPTURE_ID>` ;
- `/etc/init.d/S56k1_control_moonraker` ;
- `/etc/init.d/S57k1_control_gateway`.

Aucun fichier constructeur n'est remplacé.

## Pose en deux temps

### 1. Fondation locale

Le futur script exige simultanément `-Execute` et le texte exact
`G4-K1-CONTROL-FOUNDATION-V2`. Il :

1. répète le préflight ;
2. crée le backup daté avec marqueurs d'absence et relevés initiaux ;
3. transfère une seule archive de transport et compare son SHA-256 local/distant ;
4. vérifie `checksums.sha256` avant extraction ;
5. extrait les trois archives dans la nouvelle version ;
6. copie les configurations et les deux services originaux ;
7. crée `current` seulement après les contrôles ;
8. teste la configuration nginx avant de démarrer quoi que ce soit ;
9. démarre Moonraker sur `127.0.0.1:7125` et attend sa disponibilité ;
10. démarre Mainsail uniquement sur `127.0.0.1:4409` ;
11. compare les processus, ports, RAM, swap, taille disque, Klipper et CFS au
    relevé initial ;
12. rollback automatiquement au premier KO.

### 2. Compte puis LAN

Thomas crée lui-même le premier compte par le tunnel :

`ssh -N -L 4409:127.0.0.1:4409 k1max-root`

Après connexion vérifiée, une seconde action explicitement demandée au script
remplace seulement `nginx-active.conf` par la configuration LAN déjà vérifiée,
puis recharge le nouveau nginx. Le remplacement passe par un fichier suivant,
un test nginx et un fichier précédent restauré automatiquement sur KO.
Moonraker reste en boucle locale.

## Ce qui est automatique et ce qui reste humain

Le script automatise le préflight, les empreintes, la copie, les comparaisons,
le démarrage borné, les contrôles de coexistence, l'ouverture atomique au LAN
et le rollback. Il ne sait pas décider à la place de Thomas que le premier
compte est utilisable, que l'interface est adaptée à son usage, ni qu'une
impression réelle est bonne.

Restent donc manuels :

- le GO nommé avant toute pose ;
- la création et la vérification du premier compte par tunnel ;
- l'autorisation explicite d'ouvrir Mainsail au LAN ;
- le choix et le lancement d'une impression normale ;
- l'observation pendant huit heures ;
- un futur test de persistance après redémarrage, car ce lot n'autorise aucun
  redémarrage de l'imprimante.

Ce paquet pose seulement la base de contrôle et l'interface experte. Il ne
prétend pas encore corriger le Z, le mesh, les températures ou les séquences :
ces fonctions seront ajoutées en lots séparés après validation de la base.

## Contrôles sans G-code

- empreintes locale, transport, staging et fichiers installés identiques ;
- `7125` uniquement sur `127.0.0.1` ;
- `4409` local avant le compte, LAN seulement après ;
- connexion Mainsail obligatoire ;
- ports Creality `80`, `8080`, `9999` inchangés ;
- Klipper, écran, application Creality, T1 et T2 toujours présents ;
- aucune requête `printer.gcode.script` ;
- Moonraker au plus à 45 Mio au repos ;
- au moins 70 Mio de RAM disponible ;
- hausse de swap au plus 8 Mio ;
- logs du projet au plus 16 Mio.

Après cet OK provisoire, Thomas lance une impression normale de son choix.
Codex observe seulement. L'OK final exige huit heures de stabilité comprenant
cette impression.

## Rollback

Au premier KO :

1. arrêter seulement les deux nouveaux services ;
2. restaurer leurs anciens fichiers ou leurs marqueurs `ABSENT` ;
3. restaurer l'ancienne cible de `current` ou son absence ;
4. déplacer la version en échec sous le backup daté ;
5. laisser les fichiers constructeur et Orca intacts ;
6. comparer ports, processus, RAM, swap, Klipper, écran et CFS au relevé initial.

## Nouvelle gate humaine

Aucune pose V2 n'est autorisée avant le texte exact :

`GO G4-K1-CONTROL-FOUNDATION-V2`

Le GO V1 déjà donné ne vaut pas pour V2.
