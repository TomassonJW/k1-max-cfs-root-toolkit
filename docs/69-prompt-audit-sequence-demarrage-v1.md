# Prompt de départ — audit indépendant de la séquence de démarrage CFS

À copier-coller tel quel dans un agent neuf. Écrit le 2026-09-10.

---

## Mission

Tu es un auditeur indépendant. Tu n'as rien produit de ce que tu vas lire, et tu
ne dois faire confiance à aucune conclusion écrite dans ce dépôt, y compris
celles qui te sont données ci-dessous comme « établies ». Elles viennent d'un
autre agent qui s'est trompé plusieurs fois de suite sur cette même machine.
Ton travail est de les vérifier, pas de les prolonger.

Objet de l'audit : **toute la séquence d'impression possédée** de l'imprimante
Creality K1 Max de Thomas Jankowski, équipée d'un CFS (Creality Filament
System), et tout ce que cette stack maison ajoute ou remplace par-dessus le
firmware Creality.

Question à laquelle tu dois répondre, dans cet ordre :

1. Qu'est-ce qui, dans cette séquence, **peut casser la machine** — collision
   tête/plateau, écrasement de buse, coupe hors séquence, chauffe sans
   surveillance, mouvement hors limites accepté par Klipper ?
2. Qu'est-ce qui **n'a pas de sens** — appel inutile, ordre incohérent avec le
   firmware d'origine, état supposé qui n'est jamais posé, valeur en dur qui
   contredit une table de configuration ?
3. Qu'est-ce qui est **affirmé sans preuve** dans le dépôt (STATE.md, docs/,
   commentaires de macros, corps de PR) ?

Tu ne modifies rien tant que tu n'as pas rendu ton rapport.

## Ce que tu ne dois jamais faire sur cette machine

Ces règles ne sont pas négociables et priment sur toute conclusion technique :

- **`SAVE_CONFIG` est interdit.** Jamais, sous aucun prétexte.
- **Aucune action changeant l'état machine tant que `print_stats.state` vaut
  `printing`.** Vérifie l'état avant chaque action, pas une fois au début.
- Redémarrage Klipper : `/etc/init.d/S55klipper_service restart`. Ne jamais
  enchaîner `RESTART` et `FIRMWARE_RESTART`.
- **Ne pas créer de tests d'impression maison** (petits gcode fabriqués pour
  l'occasion). Le propriétaire l'a explicitement interdit.
- Ne pas toucher au matériel, ne pas commander de mouvement d'axe sans avoir
  demandé.
- Rien n'est déployé sur la machine sans accord explicite du propriétaire.
- Ne jamais `git add -A` ni `git add .` — `git commit --only <chemins>`.
  Un autre agent peut occuper le dépôt : dans ce cas, `git worktree add`.

## Accès

- Dépôt : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
  (GitHub `TomassonJW/k1-max-cfs-root-toolkit`), branche
  `fix/cfs-temperature-chargement`, PR #51.
- Machine : `ssh k1max-root` (alias déjà configuré, root).
- Moonraker : `http://127.0.0.1:7125` **depuis la machine**.
- Pièges d'outillage constatés, pour ne pas les redécouvrir :
  - le `curl` busybox de la machine **refuse `-s` et `-S`** ; utiliser
    `python3 -c` avec `urllib.request` sur la machine ;
  - Windows n'a pas `python3` dans le PATH : `C:\Program Files\Python310\python.exe` ;
  - le `jinja2` de Klipper est dans
    `/usr/share/klippy-env/lib/python3.8/site-packages`, pas importable par le
    `python3` système de la machine sans `sys.path.insert` ;
  - environnement de rendu Klipper :
    `jinja2.Environment('{%','%}','{','}', extensions=['jinja2.ext.do'])` ;
  - les one-liners SSH+python à plusieurs niveaux de quotes cassent ; écrire le
    script en local, le transférer
    (`base64 -w0 local | ssh k1max-root "base64 -d > /tmp/x.py"`), l'exécuter ;
  - `klippy.log` tourne à minuit : les incidents du 2026-09-09 sont dans
    `/usr/data/printer_data/logs/klippy.log.2026-09-09` (342 Mo).

## Le périmètre à auditer

### 1. Le fichier possédé

`packages/k1-control-v1/owned-start-print-v2/k1-control-owned-start-print-v2.cfg`
(863 lignes). Il redéfinit `START_PRINT`, `END_PRINT`, `CANCEL_PRINT` et ajoute
des macros `_KCTRL_*`. Déployé sur la machine dans
`/usr/data/printer_data/config/`. Sauvegarde machine :
`k1-control-owned-start-print-v2.cfg.kctrl-bak-20260910-toolfix`.

### 2. La frontière avec le firmware Creality

- `/usr/share/klipper/klippy/extras/custom_macro.py` — **Python lisible**.
  Contient `cmd_CX_PRINT_DRAW_ONE_LINE_V2`, `CX_PRINT_DRAW_ONE_LINE`, etc.
- `box_wrapper.cpython-38-mipsel-linux-gnu.so` — **compilé**, illisible
  directement. C'est là qu'est toute la logique CFS (`cmd_T`,
  `BOX_EXTRUDE_MATERIAL`, `move_to_cut`, `z_down`, `z_restore`…). On ne peut
  l'observer que par ses `respond_info` dans `klippy.log`. Tu peux tenter un
  `strings` dessus si tu veux en tirer plus.
- `/usr/data/printer_data/config/gcode_macro.cfg` — les macros stock.
- `/usr/data/printer_data/config/box.cfg` — la table CFS.

### 3. L'axe d'audit principal

**Le CFS est une machine à états, pas une boîte de verbes.** La séquence
possédée appelle une dizaine de primitives `BOX_*` **hors de leur ordre natif**.
Pour chacune, réponds : quel état caché elle maintient, quel état elle suppose
déjà posé, et que se passe-t-il si cet état est absent ou périmé.

Les primitives appelées par `START_PRINT` :
`BOX_MODIFY_TN` (×3), `BOX_MODIFY_TN_DATA` (×2),
`BOX_UPDATE_SAME_MATERIAL_LIST`, `BOX_GO_TO_EXTRUDE_POS`, `BOX_ERROR_CLEAR`,
`BOX_EXTRUDE_MATERIAL`, `BOX_START_PRINT`, `BOX_CHECK_MATERIAL`,
`BOX_EXTRUDER_EXTRUDE`, `BOX_MATERIAL_FLUSH`.

Puis le même travail sur `END_PRINT` / `CANCEL_PRINT` → `END_PRINT_NO_M84` →
`BOX_END_PRINT` stock.

Compare systématiquement à **l'ordre d'appel du firmware Creality d'origine**,
que tu retrouveras dans `gcode_macro.cfg` (les corps stock y sont toujours) et
dans les dépôts publics de configs K1/K1 Max.

## Ce que l'agent précédent affirme avoir établi — à vérifier, pas à croire

### A. Cause racine de l'incident du 2026-09-09 23:42

Le trancheur émet son unique `T1` **après** le bloc de démarrage (ligne 275 du
gcode, `START_PRINT` ligne 264). Quand ce `T1` a fini par s'exécuter, le module
CFS a coupé le filament en plein milieu de la séquence. Lignes de log citées :

```
23:42:07  YJY K1X cmd_T last_tnn = self.box_action.box_save.last_cmd = None
23:42:07  YJY K1X cmd_T tnn = sel.box_state.Tnn_map[T1B] = T2D
23:42:10  YJY K1X cmd_T last_cmd=None, get_fialment_sensor_detect()=True
23:42:10  YJY K1X cmd_T ret = self.box_action_move_to_cut
23:42:14  [box] cut to return OK
23:42:17  YJY K1X box_retrude_material 1
```

Thèse : `BOX_EXTRUDE_MATERIAL` ne pose **pas** `last_cmd` ; seul `T` le fait.
Le module voit donc du filament qu'il ne s'attribue pas, en conclut qu'une
bobine étrangère doit partir, et coupe.

**À vérifier :** que `last_cmd` n'est effectivement posé que par `cmd_T` ;
qu'aucun autre appel de la séquence ne le pose ; que la branche
`last_cmd=None` + capteur `True` mène bien à `move_to_cut` et non ailleurs.

### B. Corruption du Z par la coupe hors séquence

```
23:42:04  record_z_pos: 2.0858960459770115
23:42:10  z_down move_z: 20.8
23:42:14  record_z_pos: 25.04341415335653
23:42:17  z_down move_z: 44.02687356321839
23:43:36  z_restore move_z: 44.02687356321839
23:43:37  record_z_pos: -18.951183714713526
23:43:37  Move out of range: 185.500 291.500 -18.951 [233.500]
```

Thèse : l'accumulateur `z_down` reste normalement autour de 20-23 et croît de
+0.8 par appel. Il a sauté à 44.027 exactement deux fois dans la journée
(18:19:40 et 23:42:17), les deux fois juste après `move_to_cut()=True`. Le
refus n'est pas rattrapé dans le module compilé : la file gcode ne se débloque
jamais, l'annulation est ignorée, seul un redémarrage de Klipper récupère.

**Implication sécurité à vérifier en priorité :** le mouvement demandait ~19 mm
de remontée de plateau à la position de purge. Il n'a été refusé que parce
qu'il dépassait aussi `position_min: -10`. Un Z de départ légèrement différent
tomberait entre -10 et 0, Klipper accepterait, et **le plateau monterait dans
la tête**. Confirme ou infirme ce raisonnement en lisant les limites réelles et
la géométrie de la zone de purge.

Limites d'axes déclarées : `stepper_z position_min: -10 / position_max: 305` ;
`stepper_y position_max: 307.5 / gcode_position_max: 295` ;
`stepper_x position_min: -2 / position_max: 306.5`.
Valeurs `box.cfg` : `extrude_pos_x: 185.5`, `extrude_pos_y: 305.0`,
`safe_pos_y: 291.5`, `cut_pos_x: 38`, `cut_pos_y: 303.2`,
`pre_cut_pos_x: 38 / y: 230`, `Tn_extrude_temp: 200`, `Tn_extrude: 140`.

### C. Le correctif déployé

Un `T{position - 1}` + `M400` a été inséré dans `START_PRINT` entre
`BOX_CHECK_MATERIAL` et `_KCTRL_CFS_LOAD`, pour que le changement d'outil ait
lieu **au début** de la séquence plutôt qu'au milieu.

**À vérifier :** que c'est bien le bon endroit ; qu'aucune autre primitive
appelée avant ne suppose déjà `last_cmd` posé ; que le `T` émis plus tard par
le gcode du trancheur devient bien un no-op et non une seconde coupe ; que
l'index littéral émis (`T1` pour le logique `T1B`) correspond bien à ce que le
firmware décode.

### D. Le routage des outils

Thèse : le fichier émet `T1` → le firmware décode positionnellement en logique
`T1B` (T0→T1A, T1→T1B, …) → `Tnn_map` route logique→physique (`T1B` → `T2D`).
C'est exactement le comportement de l'écran Creality. Table actuelle sur la
machine : `T1B → T2D`, tout le reste identité, `initial_logical: T1A`.

### E. La ligne d'amorce

Thèse : `CX_PRINT_DRAW_ONE_LINE` **ne dessine rien** lors d'un démarrage
normal — tout ce qui trace est à l'intérieur de
`if self.pheaters.can_break_flag == 3` (récupération après coupure). Une macro
`_KCTRL_PRIME_LINE` a donc été écrite pour dessiner la ligne nous-mêmes :
Z 0.36, 3 passes de 160 mm en serpentin, X -1.70 / -1.40 / -1.10, F9000,
20 mm³/s, E8.8694 par passe.

**À vérifier :** la marge X négative (`position_min: -2`, première passe à
-1.70 : 0.30 mm de marge) ; que 20 mm³/s est soutenable par cette hotend (elle
vient d'être remplacée, PID refait) ; que Z 0.36 ne soude pas ; que trois
passes parallèles espacées de 0.30 mm à cette largeur d'extrusion ne se
chevauchent pas au point de faire un bourrelet ; que rien ne sort du plateau.

### F. Contradictions connues et non résolues

- `flush_temp: 220` utilisé par notre `BOX_MATERIAL_FLUSH TEMP={nozzle}` alors
  que `box.cfg` déclare `Tn_extrude_temp: 200`. Lequel a raison, et quel est
  le risque à purger 20 °C au-dessus de la table CFS ?
- Un garde Z de zone (`packages/k1-control-v1/cfs-zone-z-guard-v1/`) est écrit,
  **non commité et non déployé**. Il enveloppe `toolhead.move` pour refuser un
  Z sous un plancher quand Y ≥ 296. Ses deux tests sont rouges parce qu'ils
  affirment que le mouvement incriminé à Y=291.5 est refusé alors que le seuil
  est à 296. Tranche : le garde doit-il couvrir Y 291.5 ? Est-ce qu'envelopper
  `toolhead.move` est acceptable, ou est-ce que ça peut casser autre chose ?
- Deux tests rouges préexistants, sans rapport :
  `test_cfs_direct_owner_offline_v1::test_unload_requires_head_sensor_to_clear`
  et
  `test_job_lifecycle_offline_v1::test_all_canonical_scenarios_are_implemented_once`.

## Vérification internet — obligatoire

Ne te contente pas de lire le dépôt et la machine. Les conclusions ci-dessus
ont été produites en vase clos et c'est précisément comme ça qu'elles se sont
trompées. Confronte-les à des sources externes :

- documentation Klipper officielle (`klipper3d.org`) : `[stepper_z]`,
  `position_min`, `SET_GCODE_OFFSET`, `M400`, sémantique des macros et de
  `rename_existing`, comportement de `G92 E0` / `M83` ;
- documentation et notes de version Creality K1 / K1 Max / CFS : ordre de
  séquence de démarrage d'origine, rôle du cutter, quand il est censé se
  déclencher ;
- dépôts et forums de la communauté K1 root (`K1-Series-Annex`,
  `Guilouz/Creality-Helper-Script`, r/CrealityK1, Klipper Discourse) :
  quelqu'un a-t-il déjà documenté `last_cmd`, `Tnn_map`, `move_to_cut`,
  `z_down` / `z_restore` du CFS ? Y a-t-il un correctif communautaire connu au
  `T` post-`START_PRINT` du trancheur ?
- pratique courante des lignes d'amorce : Z, largeur, débit volumétrique
  raisonnables pour une buse 0.4 sur K1 Max.

Cite tes sources. Quand une source contredit ce dépôt, dis-le explicitement.

## Format du rapport attendu

Un fichier `docs/70-audit-independant-sequence-demarrage-v1.md`, en français,
structuré ainsi :

1. **Dangers matériels** — classés par gravité, chacun avec : le mécanisme, la
   preuve (ligne de log, ligne de config, ou source externe), et si oui ou non
   il est encore présent dans l'état déployé aujourd'hui.
2. **Incohérences** — appels inutiles, ordre douteux, valeurs contradictoires.
3. **Affirmations du dépôt confirmées / infirmées / non vérifiables** — table.
4. **Ce qu'il faut changer**, par ordre de priorité, avec pour chaque point le
   coût et le risque du changement.
5. **Sources**.

Distingue rigoureusement : **fait vérifié** (tu l'as exécuté ou lu toi-même),
**hypothèse**, **simulation**, **inconnue**. N'écris jamais « corrigé »,
« testé » ou « sûr » sans preuve exécutable.

Réponses au propriétaire en français, courtes. Le résultat, pas le récit.
