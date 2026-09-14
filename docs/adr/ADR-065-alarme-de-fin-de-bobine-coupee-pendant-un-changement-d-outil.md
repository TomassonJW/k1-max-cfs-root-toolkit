# ADR-065 — Pendant un changement d'outil, l'alarme de fin de bobine est coupée ; le capteur reste lu

Date : 2026-09-14

Statut : **acceptée ; écrite et testée ; à installer entre deux impressions**
(copie de `kctrl_tool_change.py`, redémarrage du service Klipper).

Amende l'étape 3 d'ADR-061. Point 4 du flux quotidien (`GOALS.md`) : « le
multi-filament en cours d'impression est bien géré ».

## Contexte

Première impression multicouleur, `3DBenchy_C2`, quatre filaments, le
14 septembre 2026. Premier changement en cours d'impression : T3, bleu, sur
T2B, à 19:19:16. La commande stock coupe le filament rouge et le retire. À
19:19:35, le capteur de tête `filament_sensor_2` passe à vide ; Klipper le
prend pour une bobine terminée (« runout event detected ») et demande une
pause. Le changement tient la file G-code : la pause attend et tombe à
19:22:36, 12 ms après « K1 Control: T3 fait, filament a la tete ». Le
`runout_gcode` stock enchaîne `BOX_CHECK_MATERIAL_REFILL` (19:22:42, « no auto
refill »), qui coupe le capteur et le laisse coupé.

La cause est chez nous. `START_PRINT` arme ce capteur après la ligne d'amorce,
pour la relève automatique (point 5). `END_PRINT` et `CANCEL_PRINT` le
désarment avant leur déchargement. Les changements d'outil, qui vident le
capteur de la même façon, ne le faisaient pas : chaque impression
multicouleur se serait arrêtée à son premier changement de couleur.

Question de Thomas : couper un capteur, n'est-ce pas dangereux ? Ne peut-on
pas « expliquer que c'est normal » ?

## Décision

`kctrl_tool_change` coupe l'alarme de fin de bobine du capteur de tête
(`SET_FILAMENT_SENSOR SENSOR=filament_sensor_2 ENABLE=0`) juste avant la
commande stock, **si elle était armée**. Il la rallume après un `M400`, une
fois les mouvements du changement exécutés. C'est vrai aussi quand la commande
stock échoue, quand le firmware met en pause, et pendant `START_PRINT`. Une
alarme déjà coupée reste coupée. Deux lignes au journal : « runout alarm off
during Tn » et « runout alarm on again after Tn ».

Pourquoi ce n'est pas aveugler la machine :

- **`SET_FILAMENT_SENSOR` ne coupe que la réaction.** Dans
  `filament_switch_sensor.py` de la machine, la commande ne change qu'un
  drapeau, `sensor_enabled`, lu à un seul endroit : la décision d'alarme.
  L'état du capteur est mis à jour avant ce test ; `filament_detected` reste
  donc exact, armé ou non. L'enveloppe relit cet état après le changement :
  tête vide, pause, comme avant. Le module CFS compilé
  (`box_wrapper.cpython-38-mipsel-linux-gnu.so`) lit `filament_present` ;
  le nom `sensor_enabled` n'apparaît nulle part dans le binaire (vérifié le
  14 septembre) : ses contrôles de chargement ne lisent pas ce drapeau.
- **Le changement stock fonctionne avec l'alarme coupée, observé.** T0 (noir,
  T1A) du même Benchy, à 20:34:05, alarme laissée coupée par la vérification
  de 19:22:42 : « T0 fait, filament a la tete » à 20:37:30, aucune alarme,
  aucune pause.
- **C'est le geste de Creality lui-même.** Sa relève coupe ce capteur avant
  de changer de bobine (« check_material_refill disable filament sensor2 »),
  et notre fin d'impression aussi.

« Expliquer que c'est normal » revient au même, en plus fragile. Avec
`pause_on_runout`, Klipper met en pause en Python (`send_pause_command`) avant
d'exécuter la moindre macro. Pour qu'une variable « changement en cours »
soit lue, il faudrait réécrire l'alarme stock : pause différée sur une vraie
fin de bobine, relève modifiée.

## Conséquences

- Une impression multicouleur ne s'arrête plus à chaque changement. Une vraie
  fin de bobine en cours d'impression déclenche toujours la pause et la relève.
- La fenêtre sans alarme dure le temps du changement (environ 3 minutes,
  19:19:16 → 19:22:36), couverte par les contrôles ci-dessus.
- Si le réarmement échoue après une erreur stock, c'est l'erreur stock qui
  remonte, et l'échec est journalisé. Si Klipper redémarre en plein
  changement, l'alarme revient armée (défaut de Klipper).
- Jusqu'à l'installation, chaque impression multicouleur s'arrête à son
  premier changement. `RESUME` suffit ; la suite de l'impression n'a plus
  d'alarme, puisque la vérification stock l'a coupée.

## Preuve

- `tests/test_kctrl_tool_change_v1.py`, 7 nouveaux tests, 31 au total. Le
  banc réduit `note_filament_present` de la machine et reproduit l'incident :
  la même commande sans l'enveloppe déclenche l'alarme. Alarme coupée pendant
  la commande stock, jamais déclenchée, rallumée après `M400`. Vide détecté
  et pause malgré l'alarme coupée. Rallumage sur erreur stock, sur pause du
  firmware, dans `START_PRINT`. L'erreur stock n'est pas masquée par un
  rallumage impossible. Une alarme déjà coupée n'est pas touchée. Sur le
  module d'avant, 5 de ces tests échouent.
- À observer à la première impression multicouleur après installation :
  « runout alarm off during Tn » puis « Tn fait », pas de « runout event
  detected », pas de pause.
