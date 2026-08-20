# 11 — Compatibilité des interfaces et outils de calibration

Date : 2026-08-20

Statut : **recherche hors imprimante ; aucun installateur autorisé**

## Machine exacte à préserver

- K1 Max sélectionnant la configuration S12 structure 0 ;
- firmware Creality `2.3.5.34` ;
- Buildroot 2020.02.1, Linux 4.4.94, MIPS ;
- écran et services Creality conservés ;
- deux CFS classiques, version `1.1.3` affichée sur leurs interfaces ;
- aucun processus Moonraker observé dans la capture actuelle ;
- Klipper Creality ancien et modifié, commit exact encore inconnu.

La compatibilité n'est pas déduite du seul mot « K1 ». Elle doit être prouvée
avec cette version, ces services et deux CFS actifs.

## Résultat de la comparaison

| Outil | Apport | Verdict actuel |
|---|---|---|
| Mainsail | mesh, courbes, fichiers, console, macros et vue experte | **candidat retenu**, avec Moonraker épinglé et test de coexistence |
| Moonraker | API nécessaire à Mainsail, Orca et `K1 Control` | **fondation candidate**, à empaqueter et sécuriser nous-mêmes |
| Fluidd | autre interface Moonraker | non retenu : doublon sans avantage prouvé pour ce besoin |
| Creality Helper Script | installe de nombreux composants et correctifs | installateur global refusé ; réutilisation seulement après audit fichier par fichier |
| `save-zoffset.cfg` du Helper Script | sauvegarde des appels Z | **incompatible tel quel** : il sauvegarderait aussi la remise à zéro inverse observée en fin de travail |
| fork CFS de Nik-oli | adaptations KAMP/CFS | **refusé tel quel** : WIP, basé sur `2.3.5.33`, éléments non testés et faute de section trouvée dans le diff KAMP |
| KAMP | mesh et purge adaptés aux objets | idée réutilisable, installateur non retenu ; notre Klipper n'a pas `ADAPTIVE=1` mais accepte des limites de mesh calculées |
| `SCREWS_TILT_CALCULATE` | aide au réglage mécanique du plateau | candidat après validation des quatre coordonnées et du sens des vis |
| Klipper moderne complet | mesh adaptatif natif et pile plus ouverte | pas de remplacement maintenant : risque écran/CFS trop élevé |
| BTT Eddy | autre méthode de mesure du plateau/Z | solution conditionnelle seulement si PR Touch reste instable après suppression des conflits logiciels |

## Pourquoi aucun installateur n'est lancé

### Paquet officiel Creality K1 Series Annex

Le dépôt officiel Creality fournit des installateurs Mainsail et Fluidd. La
copie examinée correspond au commit
`3c965f490c381b16882931c5a0f9803e059665ff` du 2024-05-11. Son paquet Mainsail
embarque Mainsail `v2.7.1`, un Moonraker MIPS/Python 3.8, nginx et des scripts
init Buildroot.

Cela prouve qu'une interface Moonraker est techniquement possible sur la famille
K1. Cela ne prouve pas sa compatibilité actuelle avec le firmware CFS
`2.3.5.34`. L'installateur déplace des services dans `/etc/init.d`, les démarre
et propose une désinstallation large. Sa configuration Moonraker écoute le
réseau et fait confiance aux réseaux privés sans connexion obligatoire. Elle
ne doit pas être utilisée telle quelle.

Source : [CrealityOfficial/K1_Series_Annex](https://github.com/CrealityOfficial/K1_Series_Annex).

### Creality Helper Script

La copie examinée correspond au commit
`b46787a61b3ce2f04ec04d115a73a46c26814057` du 2025-05-21. Le script apporte de
nombreux composants utiles, mais il combine installation, mises à jour et
correctifs de comportement.

Son correctif Z renomme globalement `SET_GCODE_OFFSET` et enregistre chaque
valeur `Z` ou `Z_ADJUST`. Sur cette machine, la séquence Creality applique
l'inverse de la correction en fin de travail. Le correctif enregistrerait donc
précisément la valeur qui efface le réglage. Il n'est pas installé.

Source : [Guilouz/Creality-Helper-Script](https://github.com/Guilouz/Creality-Helper-Script).

### Fork K1 CFS

La copie examinée correspond au commit
`6b9236873a7fcf18743912fbf634a1487ee6a591` du 2025-05-14. Son README le décrit
comme en cours de travail, basé sur le firmware CFS `2.3.5.33`, avec des modules
non testés. Le diff KAMP examiné contient en plus une section mal orthographiée
`gcoce_macro`, susceptible d'empêcher le chargement de la configuration.

Source : [Nik-oli/Creality-Helper-Script-K1-CFS](https://github.com/Nik-oli/Creality-Helper-Script-K1-CFS).

### KAMP et mesh adaptatif

La copie KAMP examinée correspond au commit
`b0dad8ec9ee31cb644b94e39d4b8a8fb9d6c9ba0` du 2024-08-12. KAMP dépend de
`exclude_object` et du traitement des objets par Moonraker. Le dépôt Klipper
moderne fournit maintenant un mode adaptatif natif, mais la source `bed_mesh.py`
capturée sur cette K1 ne contient pas cette logique.

Elle accepte cependant les limites et le nombre de points à l'exécution. Le
bon chemin est donc de calculer les limites depuis Orca, puis d'appeler la
fonction existante avec des bornes contrôlées. Un mesh adaptatif reste propre à
un travail et ne devient pas un profil global.

Sources : [KAMP](https://github.com/kyleisah/Klipper-Adaptive-Meshing-Purging) et
[documentation officielle Klipper Bed Mesh](https://www.klipper3d.org/Bed_Mesh.html).

### Mainsail et Moonraker

Mainsail fournit les vues expertes utiles, mais dépend de Moonraker. Moonraker
requiert Python 3.7 ou plus ; l'environnement capturé contient Python 3.8. La
compatibilité processeur ne sera pas supposée : le binaire et toutes ses
dépendances seront tirés d'une source K1 examinée, épinglés par empreinte et
testés hors ligne avant proposition.

L'installation future devra :

- n'activer aucune mise à jour automatique ;
- éviter les ports Creality existants ;
- imposer une authentification adaptée au réseau local ;
- limiter l'API aux fonctions nécessaires ;
- mesurer RAM, CPU, stockage et stabilité ;
- conserver un arrêt et un retrait complets sans modifier les macros CFS ;
- vérifier Creality Web/Print, l'écran et les deux CFS avant toute suite.

Sources : [documentation Mainsail](https://docs.mainsail.xyz/),
[installation Moonraker](https://moonraker.readthedocs.io/en/latest/installation/)
et [API Moonraker](https://moonraker.readthedocs.io/en/latest/external_api/introduction/).

## Sélection exacte issue du prototype

La fondation est maintenant figée ainsi :

- paquet Moonraker MIPS du Helper Script au commit
  `b46787a61b3ce2f04ec04d115a73a46c26814057` ;
- Moonraker embarqué au commit
  `fccffa96c63ed77dc3953e18615e9fe9cd3d69ea` du 2025-01-12 ;
- Mainsail `v2.18.2`, commit
  `009ae11fc0676a6f3b0d4697f5d28aa345c697ff` ;
- nginx MIPS du même paquet, sur le port dédié `4409` ;
- authentification portée par nginx, car le test réel a prouvé que Mainsail
  `v2.18.2` ne possède pas de flux de compte Moonraker ;
- aucune mise à jour automatique et aucun installateur communautaire exécuté.

Mainsail `v2.18.2` annonce Moonraker `v0.8.0-306` comme minimum. Le commit
Moonraker retenu est plus récent et son paquet contient déjà les dépendances
Python 3.8/MIPS. Les trois archives ont été récupérées ou lues localement,
vérifiées par taille et SHA-256, puis assemblées par le préparateur local.

## Points encore à prouver sur la machine

Une lecture distante sans effet a confirmé le 2026-08-20 :

- environ 209 Mio de RAM totale et 118 Mio disponibles dans l'instantané ;
- environ 128 Mio de swap, presque entièrement libre ;
- Python Klipper `3.8.2` ;
- 4,2 Gio libres sur `/usr/data` ;
- ports TCP `22`, `80`, `8080` et `9999` occupés, `7125` libre ;
- aucun processus Moonraker.

Le rapport public est dans
`inventory/redacted/20260820-control-foundation-capacity/`.

La marge mémoire impose une pile minimale, une seule interface experte et une
mesure longue avant acceptation. Restent à prouver après un futur GO nommé :

- consommation de chaque nouveau service et marge pendant une impression ;
- objets Klipper exposés pour le mesh, le Z, la température et le CFS ;
- effet mémoire pendant une observation longue sans impression de test dédiée.

Le prototype local utilise maintenant un faux Moonraker et la matrice est verte.
La compatibilité d'installation reste conditionnelle aux contrôles de
`G4-K1-CONTROL-FOUNDATION-V3` sur la machine réelle. V1 a été arrêtée sans
mutation lorsque son préflight a prouvé l'absence de `logrotate`. V2 a utilisé
le `syslogd` BusyBox déjà actif et borné, atteint un Mainsail fonctionnel, puis
a été rollbackée parce que son contrat de compte Moonraker était incompatible.
V3 conserve la pile prouvée et déplace le compte vers nginx.
