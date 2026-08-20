# Journal classé — préflight V1

Date : 2026-08-20

La cible et ses identifiants restent hors Git. Toutes les commandes distantes
ci-dessous étaient en lecture seule.

| Classe | Lecture | Résultat public | Effet machine |
|---|---|---|---|
| identité | architecture, carte, structure, version OTA | MIPS, S12, structure 0, `2.3.5.34` | aucun |
| état Klipper | abonnement d'une seconde et requête d'objets | `standby`, chauffes zéro, axes non homés | aucun |
| CFS | état nettoyé de l'objet `box` | T1/T2 connectés, `1.1.3`, quatre slots | aucun |
| ressources | mémoire, swap, espace `/usr/data` | seuils préalables verts | aucun |
| réseau | `netstat -lnt` BusyBox | ports stock présents, nouveaux ports absents | aucun |
| processus | lectures `ps w` bornées | Klipper et pile Creality présents | aucun |
| cibles | `ls` et tests d'existence | tous les nouveaux chemins absents | aucun |
| outils | recherche de commandes | extraction et SHA présents ; `logrotate` absent | aucun |
| journal stock | processus, socket et aide BusyBox | syslog actif, rotation bornée disponible | aucun |

Le premier essai `netstat -lntp` a seulement confirmé que ce BusyBox ne prend
pas l'option `-p`. La reprise compatible `netstat -lnt` a réussi. Aucun échec
de lecture n'a été interprété comme un succès.
