# Index des macros et premières relations

## Macros déclarées

44 macros ont été recensées dans `gcode_macro.cfg` et `box.cfg`.

| Domaine | Macros principales |
|---|---|
| Démarrage | `START_PRINT`, `PRINT_PREPARED`, `PRINT_PREPARE_CLEAR`, `PRINT_CALIBRATION` |
| Homing et nivellement | `ACCURATE_G28`, `G29`, `IF_NEED_HOME`, `INPUTSHAPER`, `AUTOTUNE_SHAPERS`, `BEDPID` |
| CFS et matériau | `BOX_CHECK_MATERIAL`, `BOX_LOAD_MATERIAL_WITH_MATERIAL`, `BOX_LOAD_MATERIAL_WITHOUT_MATERIAL`, `BOX_QUIT_MATERIAL`, `BOX_INFO_REFRESH`, `LOAD_MATERIAL`, `QUIT_MATERIAL` |
| Températures et ventilateurs | `WAIT_TEMP_START`, `WAIT_TEMP_END`, `M106`, `M107`, `M141` |
| Pause et reprise | `PAUSE`, `RESUME`, `WAIT_PAUSE`, `FIRST_FLOOR_PAUSE`, `FIRST_FLOOR_RESUME` |
| Fin et annulation | `END_PRINT`, `END_PRINT_NO_M84`, `END_PRINT_POINT`, `CANCEL_PRINT` |
| Mouvement et mode | `M204`, `M205`, `M900`, `QMODE`, `QMODE_EXIT` |

## Relations confirmées utiles au diagnostic

- `START_PRINT` appelle la préparation, le homing, le nettoyage, le nivellement et la chaîne CFS avant la ligne de purge.
- `ACCURATE_G28` délègue à `ACCURATE_HOME_Z`, fourni par une extension Klipper constructeur.
- `G29` appelle `G28`, `ACCURATE_G28` et `BED_MESH_CALIBRATE`, puis `CXSAVE_CONFIG`.
- `BOX_LOAD_MATERIAL_WITH_MATERIAL` enchaîne contrôle, coupe, retrait, positionnement, nettoyage, chargement et purge.
- `BOX_LOAD_MATERIAL_WITHOUT_MATERIAL` enchaîne contrôle, chargement et purge.
- `LOAD_MATERIAL` et `QUIT_MATERIAL` imposent une attente de température avec `M109`.
- `RESUME` utilise également `M104` et `M109` avant de restaurer l’extrusion.

## Pistes fondées sur les données

### Température CFS

`box.cfg` fixe `Tn_extrude_temp` à `220 °C`. `START_PRINT` appelle ensuite `BOX_START_PRINT_EXTRUDE_MATERIAL`, et les macros de chargement appellent la purge CFS. C’est une piste concrète pour l’écrasement de température signalé, mais le code interne du module CFS doit encore être cartographié avant de conclure.

### Z-offset

Le fichier actif conserve `z_offset = 0.000`. Parmi les instantanés datés capturés, un seul contient `-0.025`, puis l’instantané suivant revient à `0.000`. Cela soutient l’hypothèse d’une valeur remise à zéro ou remplacée, mais ne prouve pas encore quel acteur l’effectue.

## Limites

Certaines commandes `BOX_*`, `CX_*`, `ACCURATE_HOME_Z` et `CXSAVE_CONFIG` proviennent d’extensions Python constructeur, pas de macros déclarées dans les quatre fichiers inclus. Leur code n’a pas été copié dans cette capture. Il faudra d’abord acquérir en lecture seule uniquement les modules concernés, en une connexion bornée, si l’analyse locale des configurations ne suffit pas.
