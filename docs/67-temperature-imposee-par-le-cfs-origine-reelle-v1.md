# 67 — La température imposée par le CFS : origine réelle et correctif

Date : 2026-09-09
Statut : correctif de base appliqué sur la machine et **prouvé par le journal
du 9 septembre** ; garde-fou chargé le 9 septembre et vérifié en direct sur la
machine. Mise à jour du 9 septembre en section 4.

## 1. Le résultat court

Le chargeur d'origine ne lit **pas** la température du fichier tranché. Il lit
le type de matière de l'emplacement qu'il va tirer, cherche cet identifiant dans
`creality/userdata/box/material_database.json`, et chauffe au
`nozzle_temperature` de cette fiche. La fiche `00001 Generic PLA` porte `220`.

C'est pour cela que **tous** les PLA chargeaient à 220 °C depuis le premier
jour, quelle que soit la température demandée par le G-code, et que le
phénomène existait déjà avec un fichier mono-filament à 190.

Corollaire, et c'est la question qui comptait : la température vient de la
matière de l'emplacement chargé, **pas** de la liste des filaments du fichier.
Un travail à seize filaments ne change rien, et référencer de l'ABS dans un
projet ne fera jamais charger du PLA à 260 °C. Chaque fiche matière porte sa
propre valeur — PETG 250, ABS 260, ASA 270 — et c'est celle de la bobine tirée
qui s'applique.

## 2. La preuve

Journal du 8 septembre, `klippy.log.2026-09-08`, départ de 23:49 :

```
23:49:47  target=190     notre START_PRINT
23:49:53  target=220     le CFS, 3 s apres "flush_temp: 220"
23:52:14  target=190     notre M109, apres 2 min a attendre le refroidissement
23:53:35  target=220     le CFS, deuxieme fois, sur la purge
23:56:57  target=190     retour
```

Trois hypothèses étaient en lice. Deux tombent :

| Hypothèse | Ce qu'elle prédisait | Mesuré |
|---|---|---|
| repli global `Tn_extrude_temp` de `box.cfg` | `200`, valeur posée le 2 septembre | `220` |
| en-tête du fichier tranché | `195` ou `220` selon l'index | ambigu |
| fiche matière de la base | `220` | `220` |

Le départage ne vient pas de la température mais de la vitesse, journalisée
dans le même bloc. Le CFS annonce `max_volumetric_speed: 14`.

- le fichier tranché porte `filament_max_volumetric_speed = 23,24` ;
- la fiche `00001 Generic PLA` porte `filament_max_volumetric_speed = 14`.

Le CFS lit donc la base matière, et le `220` qui sort trois lignes plus loin est
le `nozzle_temperature` de cette même fiche. Le fichier tranché n'est pas
consulté : la ligne `failed to get flush speed from file` du même bloc le dit
elle-même.

Vérifié également : `tn_extrude_temp = 200` était bien chargé les 3, 5 et
8 septembre, et le journal dit `get next material temp: 220` les trois fois.
Le repli n'est donc pas en cause depuis le 2 septembre.

### Ce que cela corrige dans les documents précédents

Le document 54 concluait que la base n'était jamais lue, faute de trouver la
trace `material database get nozzle temp` dans les journaux, et attribuait le
`220` au repli. La trace est absente parce qu'elle appartient à une autre
fonction, pas parce que la base est ignorée. Le document 30 tenait la fiche
matière pour un simple filet de sécurité ; elle est en réalité la source.

Ce que le document 30 disait de juste reste vrai : une fiche matière ne peut
pas porter les quatre valeurs d'une impression — buse première couche, buse
normale, plateau première couche, plateau normal. Elle n'a pas à le faire. Elle
ne porte qu'un seul nombre, la température de la zone de fusion pendant le
chargement et la purge. Les températures d'impression restent au G-code, que
`START_PRINT` réaffirme par `M109`.

## 3. Ce qui est corrigé

### La base matière — appliqué le 9 septembre à 00:32

`00001 Generic PLA` : `nozzle_temperature` et `nozzle_temperature_initial_layer`
passent de `220` à `200`. Sauvegarde
`material_database.json.kctrl-bak-20260909-003232`, relecture conforme.

`00003 Generic PETG` est laissée à `250` : c'est la bonne température pour
charger du PETG.

`scripts/corriger-temperatures-chargement-cfs-v1.py` fait le travail. Sans
`--appliquer` il ne fait que rendre compte : il liste les matières réellement
présentes dans les emplacements du CFS et la température de chargement en
vigueur pour chacune.

```
python3 corriger-temperatures-chargement-cfs-v1.py
python3 corriger-temperatures-chargement-cfs-v1.py --temp 00001=200 --appliquer
```

Deux réserves honnêtes. La base est un fichier du micrologiciel : une mise à
jour Creality peut le remettre à l'état d'origine, et il faudra rejouer le
script. Et on ne sait pas encore si le module relit le fichier à chaque
chargement ou s'il le garde en mémoire depuis le démarrage de Klipper — le
prochain journal de départ tranchera.

### Le garde-fou — écrit, testé hors imprimante, pas encore chargé

`_KCTRL_LOAD_GUARD` : une fenêtre ouverte par `START_PRINT` autour de son seul
bloc CFS, qui **abaisse** toute cible de buse au dessus de
`EXTRUDER_TEMP + 15 °C`. Pour une impression à 190, plafond 205 : une base
corrigée à 200 passe, le `220` d'origine serait ramené à 205.

Elle abaisse au lieu de refuser. Refuser tuerait l'impression au chargement,
exactement la panne retirée le 5 septembre.

Elle n'est délibérément **pas** armée pendant toute l'impression : un travail à
deux filaments de températures différentes doit pouvoir monter pour le second.
C'est aussi pourquoi la correction de la base est le correctif principal et la
fenêtre seulement le filet — les changements de filament en cours d'impression
et les chargements manuels depuis l'écran passent par la base, pas par nous.

Elle vit dans le même fichier que `_KCTRL_PROBE_GUARD` parce que Klipper fusionne
les sections homonymes : un second `[gcode_macro M104]` ailleurs écraserait le
premier et son `rename_existing` ne trouverait plus rien (`key169`, 2 septembre).

## 4. Ce qui est prouvé depuis, et ce qui ne l'est pas

**Mise à jour du 9 septembre.** La question posée ci-dessous est tranchée. Le
journal du 9 septembre dit, trois fois — 13:17, 13:26, 13:46 :

```
get next material temp: 200
flush_temp: 200
```

Le module relit donc bien la base à chaque chargement, la correction de
`00001 Generic PLA` suffit à elle seule, et elle agit alors que le garde-fou
n'était même pas chargé à ce moment-là. C'est la preuve exécutable qui manquait.

Le garde-fou a été chargé le 9 septembre à 15:37 et vérifié en direct, hors
impression : fenêtre ouverte au plafond 100 °C, `M104 S220` donne une cible de
`100,0` et le message `M104 S220 pendant le chargement CFS, ramene a 100 C` ;
fenêtre fermée, la même commande donne `220,0`. Il abaisse, il ne refuse pas, et
il rend la main.

Reste non prouvé : aucun **départ d'impression réel** n'a encore tourné avec le
garde-fou en place. Le texte d'origine, conservé :

Aucun départ réel n'a tourné avec le garde-fou. Une impression de 13 h était en
cours au moment du correctif, et charger une configuration demande un
redémarrage de Klipper, qui tuerait l'impression.

Le module compilé contient `run_script_from_command` — les redéfinitions de
`M104` et `M109` attrapent donc ce qui passe par le répartiteur G-code — mais il
contient aussi `get_heater` et `set_temp`. Si le chargeur pose sa cible
directement par l'API du chauffage, aucune redéfinition de macro ne peut
l'intercepter, et seule la correction de la base agira. Le journal du prochain
départ le dira.

Ce qu'il faudra y lire, et rien de moins :

```
get next material temp: 200
flush_temp: 200
```

et une cible de buse qui ne dépasse jamais 205 entre le début du bloc CFS et la
ligne d'amorce.

## 5. Corroboration extérieure

Le comportement est documenté côté Creality : la documentation CFS retient
220 °C pour « Generic PLA ». Un utilisateur de K1 SE avec CFS décrit la même
mécanique avec un autre nombre — températures réglées dans le trancheur,
imprimante qui part à 230 quand même. Aucune source publique ne décrit la
correction par la base matière ; l'édition de `material_database.json` n'est
mentionnée nulle part comme remède. Le raisonnement tient sur la mesure faite
ici, pas sur une recette trouvée ailleurs.

- [Creality Wiki — CFS filament loading guide](https://wiki.creality.com/en/cfs/cfs-filament-loading-guide)
- [Creality Wiki — Parameter Description: Material](https://wiki.creality.com/en/software/creality-print/parameter-material)
- [Creality Cloud — K1 SE + CFS, la buse ne suit pas le trancheur](https://www.crealitycloud.com/post-detail/687c65e270e6870dbc3d6d5b)
- [Creality Community Forum — how to update material database](https://forum.creality.com/t/how-to-update-material-database/36527)

## 7. Le 10 septembre : la base revient d'elle-même, et le filet étrangle

**Ce qui s'est passé.** La machine a redémarré le matin (démarrage 08:44). Au
redémarrage, le micrologiciel a réécrit `material_database.json` — horodatage
`2020-03-01 13:00:19`, l'horloge d'avant la synchronisation, md5 différent à la
fois de la sauvegarde d'avant correction et du fichier de `/rom`. La fiche
`00001 Generic PLA` était revenue à `220`. La première réserve de la section 3
s'est donc réalisée sans mise à jour Creality : un simple redémarrage suffit.

À 10:06, impression d'un cube PLA à 190 °C. `START_PRINT` ouvre la fenêtre au
plafond 205 ; le chargeur lit la fiche, demande 220 ; la fenêtre ramène à 205 ;
le chargeur **attend 220** et redemande chaque seconde :

```
10:06:14  get next material temp: 220
10:06:15  K1 Control: M104 S220 pendant le chargement CFS, ramene a 205 C
10:06:16  K1 Control: M104 S220 pendant le chargement CFS, ramene a 205 C
   ... toutes les secondes, pendant cinq minutes ...
10:11:47  K1 Control: M104 S220 pendant le chargement CFS, ramene a 205 C
```

L'annulation depuis Mainsail attendait derrière la séquence. Sortie par arrêt
d'urgence à 10:14, puis redémarrage du service Klipper.

**La leçon.** « Abaisser au lieu de refuser » reposait sur une hypothèse fausse :
que le chargeur pose une cible et continue. Il pose une cible et l'attend. Une
cible abaissée est donc une attente sans fin, pire qu'un refus.

**Ce qui change (branche `fix/cfs-temperature-chargement`).**

1. `START_PRINT` lit la fiche matière de l'emplacement qu'il va charger
   **avant de chauffer ou de bouger** : `kctrl_slot_map` publie
   `material_temp` (température par identifiant de fiche, relue quand le
   fichier change) ; la macro convertit le type six caractères de l'emplacement
   en identifiant cinq caractères et compare au plafond `EXTRUDER_TEMP + 15`.
   Fiche au-dessus du plafond, ou fiche inconnue : refus immédiat, message
   donnant la commande de correction. Rien n'a chauffé, rien n'a bougé.
2. La fenêtre `_KCTRL_LOAD_GUARD` **refuse** au lieu d'abaisser. Elle ne devrait
   plus jamais être atteinte ; si elle l'est, l'impression meurt au chargement,
   ce qui se termine, au lieu de tourner sans fin.
3. La base a été recorrigée à 10:19 (`00001 → 200`, sauvegarde
   `material_database.json.kctrl-bak-20260910-101913`, seules les deux clés de
   température diffèrent, vérifié champ par champ).

**Ce qui reste vrai.** La base sera réécrite au prochain redémarrage. Le
contrôle du point 1 le dira avant chaque impression, avec la commande à passer.
Une réécriture automatique au démarrage (script d'init) n'est pas faite : le
moment exact où le micrologiciel réécrit le fichier n'est pas connu.

**Non prouvé sur la machine** : le comportement du chargeur compilé face à un
refus (`action_raise_error`) au milieu de sa boucle. Le point 1 rend ce cas
théorique ; il n'a pas été provoqué exprès.

## 6. Fichiers

- `scripts/corriger-temperatures-chargement-cfs-v1.py`
- `packages/k1-control-v1/mesh-acquisition-v2/k1-control-probe-temp-guard-v1.cfg`
- `packages/k1-control-v1/owned-start-print-v2/k1-control-owned-start-print-v2.cfg`
- `packages/k1-control-v1/owned-start-print-v2/kctrl_slot_map.py`
- `tests/test_cfs_load_temperature_ceiling_v1.py`
- `tests/test_kctrl_slot_map_v1.py`
