# Macros de Mainsail - trois panneaux

Statut : **posé le 1er novembre 2026 à 10:44:22**, sur le GO de Thomas
(« Oui, range-les »), K1 relue au repos juste avant. Seule la clé `macros` de
l'espace `mainsail` a été écrite, relue identique ; aucune autre clé n'a
changé. Sauvegarde hors Git, sous
`inventory/raw/20261101-mainsail-macro-groups/`. Captures de Mainsail sur
écran large et sur téléphone : trois panneaux, 11 boutons, couleurs prévues.

- `mainsail_macro_groups.py` : l'outil, lancé sur le PC, jamais sur la K1.
  `plan()` calcule les écritures sur une lecture, sans réseau ; `run()` lit,
  sauvegarde, écrit et relit.

## Ce qui change à l'écran

Mainsail passe en mode expert : il ne montre plus que les macros rangées dans
un groupe, chaque groupe dans son panneau. Les 44 autres boutons (étapes stock
Creality, outils internes) quittent le tableau de bord ; ils restent dans
Klipper et se lancent toujours depuis la console. Aucune macro n'est créée,
modifiée ou supprimée, `printer.cfg` n'est pas touché : tout tient dans la base
de Moonraker, espace `mainsail`, et vaut pour chaque appareil qui ouvre ce
Mainsail.

| Panneau | Couleur | Affiché | Boutons |
| --- | --- | --- | --- |
| Bobines | bleu | toujours | `KCTRL_SLOTS` (toujours), `KCTRL_SLOT`, `KCTRL_FILAMENT` |
| Plateau | gris | au repos | `KCTRL_MESH_CALIBRATE`, `KCTRL_BED_SCREWS`, `KCTRL_SCREWS_ONLY`, `KCTRL_MESH_REF_SHOW`, `KCTRL_Z_LIST` |
| Réglages | gris | au repos | `KCTRL_Z_SAVE`, `KCTRL_Z_REPEAT`, `KCTRL_PROFILE_NAME` |

Au repos veut dire `standby`, `complete`, `cancelled` ou `error` : en
impression ou en pause, il ne reste que le panneau Bobines, avec la seule liste
`KCTRL_SLOTS`. En orange, les quatre boutons qui chauffent, font un homing ou
palpent le plateau : `KCTRL_MESH_CALIBRATE`, `KCTRL_BED_SCREWS`,
`KCTRL_SCREWS_ONLY` et `KCTRL_Z_REPEAT`.

Dans chaque mise en page enregistrée qui contient le panneau Macros, les trois
panneaux viennent juste après lui. L'entrée Macros reste : Mainsail la cache en
mode expert et la remet à sa place en mode simple. Une taille d'écran sans mise
en page enregistrée, ou sans panneau Macros, est laissée à Mainsail, qui ajoute
les panneaux au bas de sa première colonne.

Sur la K1, aucune mise en page n'était enregistrée sous `dashboard` : les trois
panneaux sont au bas de la première colonne, sur écran large comme sur
téléphone. Thomas les déplace, s'il le souhaite, dans les réglages de
Mainsail, section Tableau de bord.

## Lancer

L'essai à blanc d'abord, puis la pose, au repos :

    python packages/k1-control-v1/mainsail-ui/mainsail_macro_groups.py HOST --dry-run
    python packages/k1-control-v1/mainsail-ui/mainsail_macro_groups.py HOST --apply inventory/raw/<capture>/mainsail-before.json
    python packages/k1-control-v1/mainsail-ui/mainsail_macro_groups.py HOST --rollback inventory/raw/<capture>/mainsail-before.json

`HOST` est l'adresse locale de la K1 : en argument seulement, jamais dans un
fichier suivi. L'outil passe par la passerelle K1 Control (port 4409). La
sauvegarde reste sous `inventory/raw/`, hors Git : elle recopie tout l'espace
`mainsail`, qui peut tenir d'autres imprimantes et des adresses privées.

- `--dry-run` lit l'état d'impression, la liste des objets de Klipper et
  l'espace `mainsail`, puis dit ce qu'il écrirait. Il n'écrit rien et tourne
  aussi pendant une impression.
- `--apply` refuse pendant une impression ou une pause, quand une des 11 macros
  manque à Klipper (casse exacte : Mainsail compare les noms tels quels) ou
  quand le fichier de sauvegarde existe déjà. Sinon il écrit la sauvegarde,
  puis les clés `macros` et `dashboard.<mise en page>`, relit et compare.
  Relancé, il ne trouve rien à écrire et ne crée pas de sauvegarde.
- `--rollback` remet chaque clé que la pose touche telle que la sauvegarde la
  tient, ou l'efface quand elle n'y était pas. Relancé, il ne change rien. Il
  tourne aussi pendant une impression : il ne touche que l'affichage.

Ensuite, Thomas recharge sa page de Mainsail. Il peut tout ajuster lui-même
dans les réglages de Mainsail, onglet Macros : groupes, ordre, couleurs,
affichage.

## Ce que dit l'outil

| Ligne | Sens |
| --- | --- |
| `print_stats S; N keys to write` | état lu et nombre de clés à écrire ; `nothing to write` : déjà posé |
| `write macros: ...`, `write dashboard.X: ...` | contenu de chaque écriture prévue |
| `apply OK` | toutes les clés relues comme écrites |
| `apply differs: K` | clés relues autrement qu'écrites |
| `note: other keys changed meanwhile: K` | une autre clé de l'espace a changé pendant la pose, un onglet ouvert par exemple |
| `refused: ...` | rien écrit : impression en cours, macro absente ou sauvegarde déjà là |
| `kept`, `restored` ou `deleted K`, puis `rollback OK` ou `rollback differs: K` | retour arrière, clé par clé |

Codes de sortie : 0 fait ou rien à faire ; 1 refusé, écart à la relecture ou
erreur réseau ; 2 ligne de commande fausse (option inconnue ou abrégée,
adresse absente), sans rien lire.

## Limites connues

- Un onglet de Mainsail déjà ouvert garde l'ancien affichage jusqu'à son
  rechargement. S'il enregistre avant un réglage de macros ou de mise en page,
  il réécrit cette clé de sa mémoire et défait la pose pour elle : recharger
  d'abord.
- Le mode expert cache toute macro hors groupe, y compris une macro nouvelle :
  elle n'apparaît qu'une fois rangée dans un groupe, ici ou dans les réglages
  de Mainsail.
- `--rollback` remet aussi les réglages de macros et de mise en page faits
  après la pose : ils sont perdus. Les autres réglages de Mainsail (thème,
  webcam, fichiers) n'y passent pas.
- Une coupure pendant les écritures en laisse une partie : `--rollback` avec
  la même sauvegarde remet l'état d'avant. La vraie sauvegarde d'avant reste la
  première ; une nouvelle pose sous un autre nom sauvegarderait l'état à moitié
  écrit.
- Le format est celui de Mainsail v2.18.2, la version de la K1 : relire le code
  de Mainsail avant de relancer l'outil après une mise à jour.

## Différences avec l'essai du 1er septembre

`mainsail_macro_panel.py` (commit `10b133f`, retiré ici) visait le même but
avec un seul groupe « K1 Control ». D'après le code de Mainsail v2.18.2 :

- il écrivait le groupe sous `macrogroups.k1control` et les mises en page à la
  racine de l'espace (`mobileLayout`, ...), alors que Mainsail lit
  `macros.macrogroups.<id>` et `dashboard.<mise en page>` : Mainsail ne lit pas
  ces clés-là ;
- il ne passait pas en mode expert, le seul qui affiche les groupes : même bien
  rangé, le groupe serait resté caché, et le panneau Macros, qu'il masquait,
  avec lui ;
- il remplaçait les mises en page par une copie figée au lieu de partir de
  l'état lu, sans sauvegarde ni relecture ;
- il tournait sur la K1 (`127.0.0.1:7125`) ;
- ses 7 macros comprenaient `KCTRL_MESH_ACQUIRE` et `KCTRL_MESH_SAVE_AS_REF`,
  deux étapes que `KCTRL_MESH_CALIBRATE` enchaîne déjà, et rien pour les
  bobines.

Il a tourné : la lecture du 1er novembre montre ses clés à la racine de
l'espace, le groupe `macrogroups.k1control` avec ses 7 macros et les quatre
mises en page `mobileLayout`, `tabletLayout1`, `desktopLayout1` et
`widescreenLayout1`, chacune avec `macrogroup_k1control` affiché et `macros`
masqué. Mainsail ne les lit pas : elles restent en place, inertes, et la pose
ne les touche pas.

Validation : **29 tests ciblés verts** (`tests/test_mainsail_macro_groups.py`) :
fausse Moonraker en mémoire, aucun réseau. Pose réelle : `apply OK`, second
essai à blanc `nothing to write`, relecture indépendante à 10:50 sans écart.
Le format suit le code de Mainsail v2.18.2 : `src/store/gui/macros/`
(actions, mutations, getters), `src/store/gui/getters.ts`,
`src/components/settings/SettingsMacrosTabExpert.vue` et
`src/components/panels/MacrogroupPanel.vue`.
