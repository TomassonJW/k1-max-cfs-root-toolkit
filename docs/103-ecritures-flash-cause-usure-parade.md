# 103 - Écritures sur la flash : cause, usure et parade

Date : 31 octobre 2026. Statut : diagnostic en lecture seule clos ; option 1
de la parade posée sur la K1 le 31 octobre à 23:48, sur GO de Thomas
(`packages/k1-control-v1/flash-log-level-v1/`) : un seul fichier Creality
changé, sauvegardé, rien redémarré ; effet au prochain allumage, à mesurer.

## 1. En bref

- **Cause.** Creality monte `/usr/data` en mode `sync` : chaque écriture
  attend d'être sur la flash. Pendant une impression, ses serveurs et Klipper
  écrivent 90 à 110 lignes de journal par seconde, 0,8 Mo de texte par minute.
  La partition n'ayant pas de journal ext4, chaque ligne d'environ 150 octets
  force la réécriture d'une page de données de 4 Kio, puis du bloc de 4 Kio
  qui décrit le fichier, puis un vidage du cache de la puce : 46 Mo par minute
  arrivent sur la flash, 59 fois le texte. Au repos, la K1 écrit encore
  environ 24 Mo par minute (21 à 27 selon le moment), surtout dans
  `klippy.log`, où le dialogue de Creality avec les CFS devient deux fois plus
  bavard. K1 Control n'y est pour rien.
- **Usure.** La puce eMMC de 7,8 Go estime elle-même avoir consommé 70 à 80 %
  de la vie de sa mémoire de type A et 0 à 10 % de celle de type B ; sa
  réserve de blocs reste au niveau normal. Le type A est probablement une
  zone rapide en mode SLC, qui encaisse les petites écritures (hypothèse). La
  puce ne dit ni depuis quand ni ce qu'elle fera à 100 % : relire ce registre
  chaque mois et garder hors machine une copie de ce qui ne se recrée pas.
- **Parade recommandée.** Éteindre la K1 quand elle ne sert pas (1,4 Go par
  heure évités), et passer le niveau des journaux Creality de 1 (débogage) à
  3 (avertissements) dans `log_config.json`, au repos, avec sauvegarde et
  retour arrière en deux minutes : environ 10 Mo par minute attendus en
  impression, 4 à 5 fois moins, peu d'effet au repos. Le bavardage CFS de
  `klippy.log` demande une mission à part, car l'audit du bus le lit. Le
  niveau 3 est posé depuis le 31 octobre à 23:48 (section 7).

## 2. Méthode et limites

Toutes les mesures du 31 octobre (capture `20261031-flash-writes-audit-v1`,
brute, hors Git) passent par `ssh … 'nice -n 19 sh -s'` : compteurs du noyau
(`/proc/diskstats`, BDI, ext4), tailles et dates des journaux et des fichiers
d'état, extraits bornés en octets (`tail -c` pour les journaux Creality, `dd`
sur les 128 derniers Kio de `klippy.log`). Aucun fichier écrit sur la K1,
aucune commande Klipper, aucun service touché. Les deux premières captures
renvoyaient des erreurs vers `/dev/null` côté K1 : rien n'est écrit, mais c'est
hors de la lettre du document 01 ; les suivantes n'ont plus aucune
redirection.

Échantillonneur : 60 relevés à 1 s puis 61 à 10 s, soit 667 s, pendant
l'impression ; le même au repos, de 10 à 21 minutes après la fin, puis
31 relevés à 10 s de 20:00 à 20:04. Une veille côté PC relevait aussi les
compteurs disque toutes les 2 minutes, puis toutes les 5 minutes au repos,
jusqu'à 20:15 ; ses relevés sont utilisés jusqu'à 20:00. Le registre de
santé de la puce (EXT_CSD) est lu par
debugfs, le noyau 4.4 ne l'exposant pas ailleurs : une commande de lecture,
rien n'est écrit. Une relance de Klipper et une pause sont lues dans des
extraits bornés des journaux (sections 5 et 9).

Limites : la K1 n'a pas de traceur d'entrées-sorties. La répartition entre
pages de données et blocs d'inode donnée en section 4 est une déduction des
compteurs, pas une mesure directe.

## 3. Pendant l'impression

| Mesure | Valeur |
| --- | --- |
| Écritures sur `/usr/data` | 46,6 Mo/min sur 667 s (52,4 la première minute, 46,0 ensuite) ; 45,0 Mo/min relevés par la veille de 18:01 à 18:15 ; environ 40 sur une minute, plus tôt dans la même impression (document 102) |
| Requêtes | 186 par seconde, 4,07 Kio en moyenne, une seule fusion |
| Occupation du disque | 7 % |
| `/overlay` (système), mémoire d'échange | aucune écriture sur `/overlay` ; échange dans le fichier `/usr/data/swap`, 328 Ko utilisés sur 128 Mio, quasi immobile |
| Depuis le démarrage | 10,2 Go en 4 h 24, dont 3 h 34 d'impression |

Journaux : texte ajouté d'après la taille relue sur 667 s, lignes comptées sur
des extraits pris au même moment.

| Journal | Lignes/s | Niveaux | Texte ajouté |
| --- | --- | --- | --- |
| `master-server.log` (Creality) | 41 à 50 | INFO 95 %, WARNING 5 % | 330 ko/min |
| `display-server.log` (Creality) | 28 à 41 | INFO 100 % | 254 ko/min |
| `klippy.log` | 16,5 | INFO 92 %, WARNING 5 %, ERROR 4 % | 177 ko/min |
| `web-server.log` (Creality) | 1,3 à 2,4 | INFO 100 % | 20 ko/min |
| `app-server.log` (Creality) | 0,3 | DEBUG 70 %, INFO 30 % | 7 ko/min |
| `moonraker.log` (K1 Control) | 0 | - | 0 |
| Total | 90 à 110 | | 0,79 Mo/min |

Dans `klippy.log`, 95 % des lignes et près de 80 % du texte viennent du
dialogue de Creality avec les CFS (`serial_485`, `HEART_PROCESS`, adressage
automatique, `buf_len = 0x0` en ERROR) ; l'outil d'audit `silences_cfs.py` lit
précisément ces lignes.

Fichiers d'état de Creality sous `/usr/data/creality/userdata/`, tous réécrits
sur place (même inode) :

| Fichier | Réécriture observée |
| --- | --- |
| `config/print_file_name.json` | toutes les 15 à 16 s, 44 fois en 667 s ; le Klipper de Creality le relit pour reprendre une impression après une coupure de courant (`virtual_sdcard.py`) |
| `config/gcode_layer.json` | à chaque couche, 21 à 22 s ici ; le même module y écrit le numéro de couche |
| `config/z_pos.json` | toutes les 223 à 227 s ici ; relu par `print_stats.py` |
| `box/material_box_info.json`, `box/material_modify_info.json` | 17 fois en 667 s, de 4 à 143 s d'écart |

Ensemble, moins d'une écriture par seconde contre 186 : négligeable.

## 4. Pourquoi 0,8 Mo de texte font 46 Mo sur la flash

Le script d'usine `/usr/bin/mount_mmc_ext4.sh`, appelé au démarrage par
`/etc/init.d/S02mount_mmc_ext4`, vérifie la partition puis la monte avec
`mount -o sync -t ext4` ; si le montage échoue, il la reformate (`mke2fs`) et
la remonte de même. Il est identique à celui du système d'usine en lecture
seule (même empreinte, daté du 12 juin 2025) : personne ne l'a modifié.
`/usr/data` et `/overlay` sont montés `rw,sync,…,barrier`.

La partition n'a pas de journal ext4 : `mke2fs` sans option crée le format
ext2, et le superbloc de `/usr/data` ne liste que `ext_attr resize_inode
dir_index filetype sparse_super large_file`, sans `has_journal`. Le pilote
ext4 la monte donc sans journal : aucune option `data=` au montage, aucun
`/proc/fs/jbd2`. Dans ce cas, le noyau 4.4 traite chaque écriture synchrone
par `generic_file_fsync` : données, puis inode, puis vidage du cache de la
puce, sans condition. Pour chaque ligne ajoutée :

1. il réécrit la dernière page de 4 Kio du fichier, même pour 150 octets
   ajoutés ;
2. il réécrit le bloc de 4 Kio qui contient l'inode du fichier, dont la taille
   et la date ont changé ;
3. il vide le cache d'écriture de la puce (actif d'après son registre), qui ne
   peut donc rien regrouper.

Les compteurs collent à ce modèle : 186 écritures par seconde pour 90 lignes
environ, deux par ligne, de 4,07 Kio en moyenne avec une seule fusion ; 53 %
des octets sont des pages de données (compteur `BdiWritten`, une page par
ligne, un peu plus quand une ligne chevauche deux pages), 47 % les blocs
d'inode, que ce compteur ne voit pas (déduction). Une ligne de 150 octets
coûte ainsi environ 8 Kio : 55 à 60 fois le texte.

Restent inconnus : si certains programmes écrivent une ligne en plusieurs
fois, chaque morceau coûtant alors 8 Kio, et la part des autres métadonnées
(tables d'allocation, blocs d'index), rares. Aucun autre écrivain notable :
sur une minute d'impression, les seuls fichiers modifiés dans `/usr/data` et
`/overlay` sont les journaux Creality, `klippy.log` et les fichiers d'état
ci-dessus. K1 Control n'y figure pas : son journal ne grossit pas et sa base
date de 14:23, avant l'impression. La mémoire d'échange et `/overlay` sont
hors de cause.

## 5. Au repos

Première mesure de 19:17 à 19:29, 10 à 21 minutes après la fin de
l'impression ; relevés de la veille toutes les 5 minutes jusqu'à 20:00 ;
seconde mesure de 20:00 à 20:04. Klipper, arrêté en urgence à 19:16, a
redémarré à 19:18:27, puis Creality l'a relancé à 19:18:49 (section 9) : la
relance réécrit environ 1 Mo de configuration dans `klippy.log` en dix
secondes, d'où un pic à 95 Mo/min. Hors de ce pic :

| Mesure | Au repos | En impression |
| --- | --- | --- |
| Écritures sur `/usr/data` | 23,6 Mo/min en moyenne de 19:19 à 20:04 (25,4 de 19:19 à 19:28, 23,1 de 20:00 à 20:04) ; de 20,6 à 26,5 par tranche de 5 minutes | 46,6 Mo/min |
| Requêtes | 82 à 106 par seconde selon la tranche | 186 par seconde |
| Texte des journaux | 0,55 Mo/min de 19:19 à 19:28, 0,43 de 20:00 à 20:04 ; amplification 46 puis 54 | 0,79 Mo/min, amplification 59 |

| Journal | Lignes/s, 19:19 à 19:28 | Texte | Lignes/s, 20:00 à 20:04 | Texte |
| --- | --- | --- | --- | --- |
| `klippy.log` | 36 à 38 | 393 ko/min | 36 | 367 ko/min |
| `display-server.log` (Creality) | 4,8 | 76 ko/min | 3,4 | 26 ko/min |
| `master-server.log` (Creality) | 3,5 (INFO 68 %, WARNING 32 %) | 53 ko/min | 5,1 (INFO 80 %, WARNING 20 %) | 37 ko/min |
| `web-server.log` (Creality) | 0,4 | 13 ko/min | 0 | 0 |
| `app-server.log` (Creality) | 0,2 | 11 ko/min | 0 | 0 |
| `moonraker.log` (K1 Control) | 0 | 0 | 0 | 0 |

Au repos, `klippy.log` fait 36 des 45 lignes par seconde : le même dialogue
CFS (`serial_485`, `HEART_PROCESS`, adressage automatique, `buf_len = 0x0`),
deux fois plus rapide qu'en impression, toujours 36 lignes par seconde
45 minutes après la relance. Les serveurs Creality écrivent moins de texte,
mais toujours environ 9 lignes par seconde. Or la flash suit surtout le
nombre de lignes, pas leur longueur (deux requêtes par ligne, 92 par seconde
pour 45 lignes de 20:00 à 20:04) : d'une mesure à l'autre, le texte baisse de
21 %, la flash de 9 % seulement. La cause des tranches à 26 Mo/min, de
19:45 à 19:55, n'est pas identifiée : la veille ne relevait que les compteurs
disque.

Fichiers d'état : `print_file_name.json` est effacé à la fin de l'impression,
comme le prévoit le code de Creality ; `gcode_layer.json` et `z_pos.json` ne
bougent plus ; `material_box_info.json` et `material_modify_info.json` sont
réécrits 30 fois en 672 s de 19:17 à 19:29, de 4 à 38 s d'écart, puis plus du
tout après 19:32 environ. Négligeable.

Bilan : allumée sans imprimer, la K1 écrit environ 1,4 Go par heure, la moitié
de son rythme d'impression. Une journée de 4 h d'impression fait environ
40 Go si la machine reste allumée 24 h, dont 28 au repos, et 11 Go si elle est
éteinte après. Ce démarrage, 5 h 56 dont 4 h 37 d'impression, a écrit 14,1 Go.

## 6. Usure de la flash

**La puce.** eMMC 5.1 (registre `EXT_CSD_REV` à 8) du fabricant `0x45`
(SanDisk, aujourd'hui Western Digital), nommée `DG4008`, fabriquée en juin
2023, 7,82 Go (15 273 600 secteurs), compatible HS400. Hypothèse non
confirmée par une source publique, d'après la forme du nom : SanDisk iNAND
7250 `SDINBDG4-8G`. La fiche de cette gamme décrit une eMMC 5.1 HS400 en
flash MLC à deux bits par cellule, liste `SDINBDG4-8G` comme modèle 8 Go et
annonce « up to 3K P/E cycles in MLC »
([PB02-iNAND-7250-US-EN-0317-01](https://pccomponents.com/datasheets/SanDisk-inand7250.pdf),
même phrase dans la révision
[-0817-02](https://static.chipdip.ru/lib/242/DOC043242106.pdf)).

**Ce que dit la puce.** Son registre de santé (EXT_CSD), lu le 31 octobre au
repos :

| Champ (octet) | Valeur | Sens selon la norme eMMC 5.1 |
| --- | --- | --- |
| `PRE_EOL_INFO` (267) | `0x01` | normal ; l'alerte vient à `0x02` (80 % des blocs de réserve consommés), puis `0x03` (90 %) |
| `DEVICE_LIFE_TIME_EST_TYP_A` (268) | `0x08` | 70 à 80 % de la vie estimée de la mémoire de type A consommée |
| `DEVICE_LIFE_TIME_EST_TYP_B` (269) | `0x01` | 0 à 10 % pour la mémoire de type B |

La norme laisse au fabricant le sens de A et de B, non publié pour cette
puce ; l'usage courant décrit par NetModule associe A aux blocs en mode SLC
et B aux blocs MLC. Hypothèse cohérente avec la mesure : les petites écritures
forcées, chacune suivie d'un vidage du cache (section 4), usent d'abord une
zone rapide en mode SLC, tandis qu'une page réécrite des dizaines de fois
n'atteint la zone principale qu'une fois remplie.

Lecture : la limite la plus proche est la zone A, pas le calcul théorique
plus bas. Si elle s'use au même rythme qu'avant, ses 20 à 30 % restants
dureront un quart à un peu moins de la moitié du temps d'usage déjà écoulé
(20/80 à 30/70) : après deux ans d'usage comparable, par exemple, 6 à
10 mois. L'historique manque pour trancher : la partition a été créée par la
machine elle-même, à une date que son horloge par défaut ne donne pas
(1er mars 2020 affiché). La valeur 100 % est une estimation du fabricant, pas
un arrêt programmé ; ce que la puce fait au-delà n'est pas publié. Le prochain
pas, de `0x08` à `0x09`, donnera la vraie vitesse : relire ce registre chaque
mois.

**Calcul théorique pour la zone principale, puce neuve.**

- Endurance : 3 000 cycles d'effacement par bloc, le maximum annoncé ; une
  version commerciale peut faire moins. Budget : 7,82 Go × 3 000 = 23,5 To
  écrits dans la flash.
- Amplification interne de la puce : ni publiée, ni mesurable d'ici. 1 est le
  plancher physique ; 3 l'hypothèse de travail ; 8 l'hypothèse pessimiste, car
  chaque écriture de 4 Kio forcée sur la flash peut occuper une page interne
  plus grande. Ces trois valeurs ne sont pas sourcées.
- Rythme : 2,8 Go par heure d'impression (46,6 Mo/min) ; 1,4 Go par heure
  allumée sans imprimer (23,6 Mo/min, section 5).

| Usage par jour | Écrit par jour | Amplification 1 (23,5 To) | 3 (7,8 To) | 8 (2,9 To) |
| --- | --- | --- | --- | --- |
| 4 h d'impression, éteinte ensuite | 11 Go | 5,7 ans | 1,9 an | 8,6 mois |
| 8 h d'impression, éteinte ensuite | 22 Go | 2,9 ans | 11,5 mois | 4,3 mois |
| 4 h d'impression, allumée 24 h sur 24 | 40 Go | 1,6 an | 6,5 mois | 2,4 mois |

Rester allumée sans imprimer multiplie par 3,5 l'usure d'une journée de 4 h.
Éteindre après usage et appliquer la parade 1 la ramènerait de 40 à environ
2,4 Go, seize fois moins ; la zone A gagnerait d'autant si son usure
suit le nombre d'écritures (hypothèse).

**Déjà consommé.** Le compteur ext4 de `/usr/data` affiche 43 Go enregistrés
au dernier arrêt propre (« 40 GB », compté en Gio) et 57 Go avec ce
démarrage. C'est un minimum : il ne s'enregistre qu'à un arrêt propre du
système, et chaque coupure à l'interrupteur perd la session en cours. Ce seul
démarrage, 5 h 56 dont 4 h 37 d'impression, a écrit 14,1 Go.

## 7. Parade : option 1 posée le 31 octobre

### Geste immédiat : éteindre la K1 quand elle ne sert pas

Allumée sans imprimer, la K1 écrit 1,4 Go par heure, 28 Go pour vingt heures
d'attente : deux fois et demie une journée de 4 h d'impression. L'éteindre à
l'interrupteur une fois la buse refroidie, comme d'habitude, supprime ce poste
sans rien changer à la machine. Jamais pendant une impression.

### Option 1, recommandée : journaux Creality au niveau « avertissement »

Le fichier `/usr/data/creality/userdata/log/log_config.json` (157 octets, daté
du 7 juin 2026, absent du système d'usine, vraisemblablement créé par les
programmes Creality) règle le niveau de leurs journaux : `"log_level":1`. Le fichier
documente lui-même 0 défaut, 1 débogage, 2 information, 3 avertissement,
4 erreur. Passer à 3.

- Effet attendu, si les programmes le respectent : les lignes Creality passent
  de 70 à 90 par seconde à environ 2 (les WARNING de `master-server`) ; le
  total à 19 environ, `klippy.log` restant tel quel ; la flash à environ
  10 Mo/min en impression (proportion des lignes, de 8 à 12). Au repos,
  l'effet est faible : les lignes Creality n'y font que 9 par seconde sur 45,
  de 24 à environ 19 Mo/min. Le niveau 2 ne servirait à rien : les lignes
  actuelles sont déjà des INFO.
- Procédure : paquet `packages/k1-control-v1/flash-log-level-v1/`, préparé
  le 31 octobre et testé hors imprimante (`deploy.py preflight`, vert sur la
  K1 le 31 octobre à 23:28, puis `install`). L'installateur lit le fichier,
  exige son empreinte d'origine, calcule le changement de ce seul chiffre et
  exige l'empreinte attendue ; il sauvegarde fichier, mode et manifeste sous
  `/usr/data/k1-control-v1/backups/flash-log-level-v1/`, relit le repos par
  le socket de Klipper juste avant d'écrire, puis remplace le fichier d'un
  bloc. Il ne redémarre rien : le fichier n'étant vraisemblablement lu qu'au
  lancement des programmes, le nouveau niveau vaut au prochain allumage, fait
  par Thomas. Le fichier Creality n'est pas versionné, seules ses empreintes
  (avant `027ab3db…`, après `fcd855a5…`). Jamais pendant une impression.
- Pose : le 31 octobre 2026, sur GO de Thomas, juste après la garde de purge
  et avant l'impression de nuit, verrou K1 pris entre les deux sessions.
  Préflight vert à 23:48:10, `INSTALLED_OK` à 23:48:19, `VALIDATED_OK` à
  23:48:21 (niveau 3, reçu `INSTALLED_OK`). Aucun redémarrage ni G-code.
- Validation : `deploy.py validate`, qui ne lit que le fichier ; après
  l'allumage, `mesure.py` au repos puis pendant l'impression suivante, en
  arrière-plan (mêmes compteurs que la section 2, plus le temps depuis
  l'allumage ; essayé en lecture seule le 31 octobre à 23:28, au repos :
  23,4 Mo/min sur 5 s, niveau 1) ; écran, application et page web Creality
  fonctionnels ; `print_file_name.json` toujours réécrit (reprise après
  coupure intacte).
- Retour arrière : `deploy.py rollback`, au repos ; il remet le fichier
  sauvegardé, empreinte identique, et l'ancien niveau revient au prochain
  allumage. Deux minutes.
- Risques : perte des traces INFO utiles à la rétro-ingénierie (le
  document 55 s'appuie sur des lignes INFO de `master-server.log`) : remettre
  1 le temps d'une enquête. Aucun composant de K1 Control ne lit ces journaux
  (le choix des emplacements lit `tn_data.json`). Une mise à jour du firmware
  peut remettre 1 : relire après chaque mise à jour. Si les programmes ignorent
  le fichier, la mesure le montrera : retour arrière, puis option 2.

Qui lit ce fichier : huit programmes Creality contiennent le nom
`log_config.json` (`master-server`, `display-server`, `app-server`,
`web-server`, `wifi-server`, `upgrade-server`, `audio-server`, `Monitor`),
mais aucun ne contient `log_level` ni `log_route` : la lecture passe
vraisemblablement par une bibliothèque commune, non vérifiée. Le respect du
réglage reste donc à prouver par la mesure. `klippy.log` n'en dépend pas.

### Option 2 : journaux Creality en mémoire vive

Monter une mémoire vive (`tmpfs`) sur le dossier des journaux Creality au
démarrage, `log_config.json` recopié dedans. Gain proche de l'option 1,
mais : il faut ajouter un script de démarrage au système (`/overlay`) ; les
journaux disparaissent à chaque extinction ; Creality ne fait tourner un
journal qu'à 20 Mio, il faudrait 80 Mio de mémoire et plus alors qu'il en
reste 95 Mo pendant une impression (document 102) ; avec une taille plafonnée,
le comportement des programmes sur un disque plein est inconnu. À n'envisager
qu'avec l'option 1.

### Option 3 : retirer le mode `sync`, non recommandée sans décision

Remonter `/usr/data` sans `sync` laisserait le noyau regrouper les écritures :
le gain le plus fort, estimé sous 3 Mo/min. Mais la partition n'a pas de
journal (section 4) : `sync` est vraisemblablement la seule protection de
Creality contre les coupures à l'interrupteur. Sans lui, une coupure peut
perdre les écritures des dernières secondes (reprise après coupure par
`print_file_name.json`, `SAVE_CONFIG`, état de K1 Control), laisser vide un
fichier réécrit sur place ou abîmer la partition, que le script d'usine
répare (`fsck -y`) ou, en dernier recours, reformate. Le faire proprement
exigerait d'abord d'ajouter un journal, partition démontée, donc hors du
fonctionnement normal, puis de modifier le montage d'usine. Décision
structurante : ADR et choix de Thomas.

### Option 4, mission à part : filtrer le bavardage CFS de `klippy.log`

Au repos, `klippy.log` fait 36 des 45 lignes par seconde et `log_config.json`
n'y change rien. Klipper écrit par le module `logging` de Python et chaque
ligne nomme son module (`serial_485`, `auto_addr_wrapper`…). Un petit module
K1 Control chargé par Klipper pourrait y poser un filtre : écarter les lignes
INFO répétitives du dialogue CFS, garder les WARNING et ERROR. Idée non
testée. Gain estimé : de 24 à environ 6 Mo/min au repos, 2 avec l'option 1 ;
environ 2 Mo/min en impression avec l'option 1.

Coût : l'audit du bus (`silences_cfs.py`, documents 80 à 82, ADR-068) lit
justement ces lignes. Il faudrait un interrupteur d'audit, ou ne filtrer
qu'hors impression. Mission séparée avec ADR et validation hors imprimante ;
pose au repos revérifié, puisqu'elle redémarre Klipper ; retour arrière par
retrait de l'include.

Les options 1 à 3 laissent `klippy.log` tel quel : la recette d'audit en
dépend. Seule l'option 4 y touche, d'où ses conditions.

## 8. Inconnues

- si les programmes Creality respectent `log_config.json`, quand ils le
  lisent, et depuis quand le niveau 1 est actif (fichier daté du 7 juin
  2026) ;
- l'amplification interne de la puce ;
- l'identité exacte de la puce (`DG4008` vers `SDINBDG4-8G` non confirmé) et
  le sens de ses mémoires de type A et B ;
- l'historique d'usage, donc la vitesse réelle d'usure de la zone A, et ce
  que la puce fera au-delà de 100 % ;
- le rythme au repos plus de 45 minutes après une relance de Klipper, et la
  cause de ses variations de 21 à 27 Mo/min d'une tranche de 5 minutes à
  l'autre.

## 9. Constats annexes, hors périmètre

- Le serveur SSH (`dropbear`) a hérité d'un descripteur ouvert sur un ancien
  `display-server.log` effacé (20 Mio) : place non rendue jusqu'au prochain
  redémarrage ; il n'y écrit pas.
- `klippy.log` reçoit environ 0,66 ERROR par seconde (`buf_len = 0x0`, liaison
  CFS) pendant l'impression : à comprendre à part.
- Si le montage de `/usr/data` échoue au démarrage, le script d'usine
  reformate la partition : une flash fatiguée peut effacer l'état de
  K1 Control et ses sauvegardes. Garder une copie hors machine.
- Les journaux Klipper datés montent jusqu'à 367 Mo pour une journée
  (23 septembre).
- Pause vers 98 % de l'impression : la veille l'a vue en pause à 19:01 et
  19:03, de nouveau en impression à 19:05, terminée à 19:07. Origine non
  cherchée ; lien avec le bug de fin d'impression ci-dessous non vérifié.
- Arrêt d'urgence de Klipper à 19:16:12, neuf minutes après la fin :
  « Shutdown due to webhooks request », tête à X185,5 Y305 Z53,9. Thomas l'a
  déclenché lui-même après un gros bug en fin d'impression, qu'il traite dans
  une autre session. Klipper repart à 19:18:27, puis Creality envoie de
  lui-même un `firmware_restart` (« auto firmware restart ») à 19:18:49 ;
  Klipper répond de nouveau à 19:19:14. Les scripts de cette mesure
  n'envoyaient que des lectures, et aucune entre le sondage de 19:07:46 et le
  relevé au repos lancé à 19:17:46.

## 10. Sources

- Western Digital, iNAND 7250 Industrial Embedded Flash Drive, fiches
  PB02-iNAND-7250-US-EN-0317-01 et -0817-02 (liens en section 6).
- JEDEC JESD84-B51 (eMMC 5.1), registre EXT_CSD : octets 267
  `PRE_EOL_INFO`, 268 et 269 `DEVICE_LIFE_TIME_EST_TYP_A/B` ; positions
  vérifiées dans
  [include/linux/mmc/mmc.h](https://github.com/torvalds/linux/blob/master/include/linux/mmc/mmc.h),
  sens des valeurs dans le décodage d'U-Boot
  ([cmd/mmc.c](https://github.com/u-boot/u-boot/blob/master/cmd/mmc.c)).
- NetModule, [Linux MMC HowTo](https://netmodule-linux.readthedocs.io/en/latest/howto/mmc.html) :
  types A et B rapprochés des blocs SLC et MLC, usage courant non garanti
  pour cette puce.
- Linux 4.4, [fs/ext4/fsync.c](https://github.com/torvalds/linux/blob/v4.4/fs/ext4/fsync.c)
  et [fs/libfs.c](https://github.com/torvalds/linux/blob/v4.4/fs/libfs.c) :
  sans journal, chaque synchronisation écrit données et inode, puis vide le
  cache de la puce.
- Capture brute `inventory/raw/20261031-flash-writes-audit-v1/`, hors Git.
