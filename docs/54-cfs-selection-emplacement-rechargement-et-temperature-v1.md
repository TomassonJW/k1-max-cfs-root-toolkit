# 54 — CFS : choix de l'emplacement, rechargement automatique, température

Date : 2026-09-02
Statut : posé sur la machine, vérifié à froid ; un chargement réel reste à faire

Trois fonctions que le CFS d'origine rendait et que la voie possédée avait
perdues sont rétablies. La quatrième — la température imposée — est traitée.

## 1. Ce qui était cassé, et pourquoi

**Tout partait sur `T1A`.** Le démarrage possédé charge le CFS en appelant
`BOX_EXTRUDE_MATERIAL TNN=<emplacement>` directement. C'est le seul chemin qui
charge de façon fiable sans le mappage que seul le travail écran transporte,
mais il adresse un emplacement **physique** et contourne donc `Tnn_map`, la
table que le firmware consulte normalement. L'emplacement passé venait de
`variable_default_tool`, figé à `T1A`.

**Le rechargement automatique ne pouvait pas se déclencher.** Il est porté par
`BOX_CHECK_MATERIAL_REFILL`, et cette commande n'est appelée qu'à un seul
endroit : la fin du `runout_gcode` du capteur de tête `filament_sensor_2`. Ce
capteur était laissé désarmé (ADR-051), donc la commande n'était jamais
atteinte.

**La température de chargement valait `220 °C`.** Elle vient du repli global
`Tn_extrude_temp` de `box.cfg`, pas de la base matière.

## 2. Preuves faites sur la machine, à froid

Le 2 septembre, machine au repos, plateau bas, aucun mouvement ni chauffe :

| Question | Preuve |
|---|---|
| `BOX_MODIFY_TN` existe et écrit la table | `BOX_MODIFY_TN T1A=T2C` : le firmware réémet `Tnn_map` complet et écrit `tnn_map` dans `tn_data.json` ; `T1A=T1A` restaure à l'identique |
| La fiche éditée à l'écran est inerte | le binaire ne référence que `tn_data.json`, `material_database.json` et `flushing_sign` ; `minTemp`, `maxTemp` et `pressure` vivent dans `material_modify_info.json`, jamais ouvert |
| `MODIFY_BOX_CFG TN_EXTRUDE_TEMP=` n'est **pas** acceptée | elle répond `success,` sans nommer de clé, et `SAVE_BOX_CFG` répond `ok:no save` |
| La commande fonctionne bien par ailleurs | contrôle positif : `MODIFY_BOX_CFG CUT_POS_Y=303.2` répond `success, cut_pos_y=303.2` puis `SAVE_BOX_CFG ok: cut_pos_y=303.2` |
| Le `220` vient du repli, pas de la base | `material database get nozzle temp` : **0 occurrence** sur `550 Mo` de journaux, contre `25` occurrences de `get next material temp: 220` |
| Pourquoi la base n'est jamais lue | ses identifiants font 5 caractères (`00001`) alors que les emplacements stockent 6 (`000001`) ; la recherche échoue et retombe sur le repli |
| `BOX_EXTRUDE_MATERIAL` ne prend pas de température | une seule chaîne `TEMP` dans le binaire, utilisée par `BOX_MATERIAL_FLUSH` |

La pression d'avance ne fait pas partie du sujet : elle est fournie par le
G-code. Le travail tranché du 29 août porte `SET_PRESSURE_ADVANCE ADVANCE=0.03`
à sa ligne 28. Le champ PA de la fiche CFS est décoratif comme le reste de cette
fiche.

## 3. Ce qui a été posé

### Choix de l'emplacement

```
KCTRL_SLOTS                      liste les emplacements, matière, couleur, et celui retenu
KCTRL_SLOT SLOT=T2A              mono-filament, et premier filament d'un travail
KCTRL_SLOT SLOT=T2B TOOL=T1B     deuxième filament du même travail
```

`KCTRL_SLOT` écrit **les deux** routes : `Tnn_map`, pour que la mécanique stock
— changement d'outil en cours d'impression, et surtout le rechargement
automatique qui réécrit cette même table — reste d'accord avec nous, et une
variable persistante que `START_PRINT` relit pour son appel direct. Un
emplacement vide est refusé avec un message explicite, au lieu de partir dans
le vide.

Le multi-filament passe par `TOOL=` : les entrées de `Tnn_map` sont nommées par
position, `T1A` est le premier filament du trancheur, `T1B` le deuxième.

### Rechargement automatique

`filament_sensor_2` est armé à la fin de `START_PRINT`, une fois la première
ligne tracée. Il est désarmé avant le retrait de fin par `END_PRINT` et
`CANCEL_PRINT`, redéfinis en trois et quatre lignes.

La dépendance identifiée par l'ADR-051 est levée sans recopier le corps stock :
`END_PRINT_NO_M84`, où se trouve réellement le retrait, reste intouché ; seuls
ses deux appelants sont redéfinis.

Les groupes de rechange existent déjà : `T1A` et `T1B` forment un couple valide
(même matière `000001`, même couleur `0000000`), `box.auto_refill` vaut `1` et
le réglage écran `filamentAutoRefill` est vrai.

### Température

`Tn_extrude_temp` passe de `220` à `200` dans `box.cfg`. C'est un réglage
statique, non modifiable à chaud — la seule voie est le fichier plus un
redémarrage Klipper.

En PLA, la descente vers la température du G-code passe d'environ `27 s` à
quelques secondes. La température d'impression elle-même n'a jamais été en jeu :
`START_PRINT` la réaffirme par `M109` avant toute extrusion qui atteint le
plateau.

**Réserve PETG.** `200` est correct pour charger du PLA. Une session PETG
demande de remonter cette valeur dans `box.cfg` puis de redémarrer Klipper,
sinon le chargement se fait à `200` sur une zone de fusion qui en demande `250`.
Aucun chargement PETG n'a jamais eu lieu sur cette machine, avant comme après.

## 4. Ce qui n'est pas prouvé

Le rechargement automatique ne peut être prouvé que par une bobine qui s'épuise
réellement en cours d'impression. La chaîne est vérifiée pièce par pièce —
capteur armable et désarmable, groupe de rechange présent, table réécrite par
la bonne commande — mais l'enchaînement complet n'a pas tourné.

## 5. Pièges rencontrés

- **Un `#` dans une chaîne de macro coupe la ligne.** Klipper traite `#` comme
  un début de commentaire partout, y compris à l'intérieur d'un littéral. Un
  `couleur #%s` a mis la machine en `halted` avec `EOL while scanning string
  literal`. Aucun `#` ne doit survivre dans un bloc `gcode:`.
- **`rename_existing` est impossible sur une section que ce fichier redéfinit.**
  Klipper fusionne les sections homonymes, donc le corps stock est écrasé avant
  que le renommage cherche à l'attraper : `key169`.
- **Deux redémarrages rapprochés cassent la liaison MCU.** `TypeError:
  initializer for ctype 'struct serialqueue *'` pendant `_get_identify_data`,
  puis une boucle `is_connected = False`. Sortie :
  `/etc/init.d/S55klipper_service restart`. Ne pas enchaîner `RESTART` et
  `FIRMWARE_RESTART`.

## 6. Sauvegardes laissées sur la machine

```
/usr/data/printer_data/config/box.cfg.kctrl-bak-20260902
/usr/data/printer_data/config/k1-control-owned-start-print-v2.cfg.kctrl-bak-20260902
```
