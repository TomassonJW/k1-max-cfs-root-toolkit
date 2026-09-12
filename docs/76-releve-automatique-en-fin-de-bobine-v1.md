# 76 — La relève automatique en fin de bobine : ce que la machine fait déjà

Date : 2026-09-10, 22:15 à 22:45. Lectures seules pendant une impression
(`box`, `filament_switch_sensor`, `printer.cfg`, journaux depuis le 5
septembre). Point 5 du flux quotidien (`GOALS.md`). Rien n'a été écrit sur la
machine ; rien n'est à déployer pour ce point.

## La chaîne, telle qu'elle est câblée

1. **Le capteur de tête** `filament_sensor_2` (`printer.cfg` lignes 244-253,
   `switch_pin: ^!nozzle_mcu:PA10`, `pause_on_runout: true`) déclenche
   `runout_gcode` : `respond_info " filament_sensor_2 pause"`, puis si la
   buse peut extruder `G91 / G0 E30 F600 / G90`, puis
   **`BOX_CHECK_MATERIAL_REFILL`**.
2. **`BOX_CHECK_MATERIAL_REFILL`** est une commande du module compilé,
   enregistrée sans description (absente de `help`). Ses chaînes :
   `cmd_check_material_refill`, `material_auto_refill: BOX_MODIFY_TN %s -> %s`,
   `check_material_refill disable filament sensor2`, `Wait for extrusion all
   materials, inside_auto_refill`. Elle cherche dans `same_material` une
   autre bobine du même groupe (même fiche matière **et** même couleur),
   réécrit la table (`BOX_MODIFY_TN`), et rejoue le `T` du filament en cours.
3. **Réglages lus le 10 septembre à 22:30** : `box.auto_refill: 1`,
   `box.enable: 1` ; `filament_sensor_2` `enabled: true, filament_detected:
   true` pendant l'impression en cours.

## C'est arrivé une fois, et ça a marché

Journal `klippy.log.2026-09-05` :

```
15:22:18,394  filament_sensor_2 pause
15:22:26,824  material_auto_refill: BOX_MODIFY_TN T1A -> T1B
15:22:26,829  part: tnn_map ... {'T1A': 'T1B', 'T1B': 'T1B', ...}
15:22:26,837  YJY K1X cmd_T vtnn=T1A
15:22:26,845  YJY K1X cmd_T tnn = sel.box_state.Tnn_map[T1A] = T1B
15:22:26,849  YJY K1X cmd_T self.box_action.z_down
```

Huit secondes entre la détection et la réécriture, puis le changement
d'outil stock sur la bobine de relève. Trois « filament_sensor_2 pause » sur
tous les journaux (5 septembre 15:22, 9 septembre 18:19 et 23:42) ; une
seule ligne `material_auto_refill` : les deux du 9 n'avaient pas de bobine de
relève et sont restées en pause.

## Pourquoi on ne peut pas le prouver ce soir

Les groupes du 10 septembre au soir :

```
[000001, 0000000, [T1B], PLA]   [000001, 0ffffff, [T1D], PLA]
[000001, 0ff1e1e, [T2A], PLA]   [000001, 000a3ff, [T2B], PLA]
[000003, 0ffffff, [T2C], PETG]  [000001, 0b2a1e1, [T2D], PLA]
```

Chaque bobine est seule dans son groupe (T1A et T1C sont vides) : **aucune
paire de relève n'existe**. Une fin de bobine ce soir se terminerait en
pause, comme les deux du 9 septembre.

## Comment le provoquer, quand Thomas le décide

Sur une impression sans valeur, avec deux bobines de même matière **et** même
couleur (deux PLA blancs, par exemple), les deux déclarées avec la même fiche
et la même couleur sur l'écran :

1. `KCTRL_SLOTS` : les deux apparaissent ; l'objet `box` les montre dans un
   même groupe `same_material` (`KCTRL_CHECK` ou `printer.box.same_material`).
2. Lancer l'impression sur l'une des deux ; laisser la bobine se finir, ou
   couper le filament **avant** le CFS (jamais dans la tête).
3. Attendu au journal, dans cet ordre : `filament_sensor_2 pause`,
   `material_auto_refill: BOX_MODIFY_TN <en cours> -> <relève>`, `cmd_T
   vtnn=`, `z_down`, puis la reprise sans `PAUSE` visible dans Mainsail.
4. Si la relève n'a pas lieu : la machine est en pause, `RESUME` après avoir
   rechargé à la main ; rien d'autre à faire.

Aucune procédure maison ne remplace ça : la relève est stock, et la seule
chose à vérifier est qu'elle tient toujours avec l'enveloppe des `T` en
place.

## Interaction avec l'enveloppe des `T` (ADR-061) et l'appariement (ADR-062)

- **Même règle de paire** : l'appariement tient pour interchangeables deux
  bobines de même type et même couleur, exactement ce que le firmware groupe
  pour la relève. Un démarrage apparié sur l'une des deux laisse l'autre en
  relève.
- **L'enveloppe ne gêne pas** : le `T` rejoué par la relève vise le filament
  en cours, déclaré par le fichier, dont la fiche est déjà alignée sur la
  température du fichier ; la bobine de relève partage la même fiche. Après
  le changement, l'enveloppe attend `M400`, vérifie le capteur de tête et
  remet la cible du fichier. Inconnue : si `BOX_CHECK_MATERIAL_REFILL` appelle
  la méthode Python directement plutôt que la commande `T`, l'enveloppe ne
  voit rien et la relève se fait comme aujourd'hui ; dans les deux cas, ça
  imprime.
- **Après relève, la table a changé** : `kctrl_slot_map` relit `tn_data.json`
  au prochain appel (horodatage), `KCTRL_MAP` montre la nouvelle paire.

## Fichiers

- Aucun code. Ce document, `GOALS.md` point 5.
