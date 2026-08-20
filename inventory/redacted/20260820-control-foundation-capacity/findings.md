# Relevé de capacité pour la future interface

Date : 2026-08-20

Portée : lectures SSH bornées, sans écriture et sans commande de chauffe,
mouvement, calibration, impression, service ou redémarrage.

## Résultats

- mémoire totale : `214048 kB`, soit environ 209 Mio ;
- mémoire disponible au moment du relevé : `120452 kB`, soit environ 118 Mio ;
- swap total : `131068 kB`, presque entièrement libre au moment du relevé ;
- environnement Python Klipper : `3.8.2` ;
- stockage persistant `/usr/data` : 6,5 Gio au total, 4,2 Gio disponibles ;
- ports TCP en écoute : `22`, `80`, `8080` et `9999` ;
- aucun port Moonraker `7125` et aucun processus Moonraker observés ;
- Klipper et les services Creality habituels étaient présents.

## Conséquences

- le port Moonraker courant ne présente pas de conflit dans cet instantané ;
- la place disque n'est pas le principal risque ;
- la marge mémoire est limitée. Une seule interface experte est retenue et les
  versions/dépendances doivent être minimales et épinglées ;
- la consommation au repos ne suffit pas à prouver la stabilité pendant une
  impression, la caméra et deux CFS. Un futur paquet doit mesurer la mémoire sur
  la durée et prévoir un rollback si la marge chute.

## Limites

- instantané ponctuel, pas une mesure de pic ;
- le `ps` BusyBox disponible ne donnait pas la mémoire détaillée par processus ;
- aucune API Moonraker n'existe encore, donc les objets CFS exposables restent à
  définir hors ligne puis à vérifier après un futur GO ;
- ce relevé n'autorise aucune installation.
