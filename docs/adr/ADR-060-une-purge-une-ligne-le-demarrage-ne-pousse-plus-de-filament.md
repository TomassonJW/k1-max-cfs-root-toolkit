# ADR-060 — Une purge, une ligne : le démarrage ne pousse plus de filament lui-même

Date : 2026-09-10

Statut : **acceptée ; écrite et testée ; pas encore déployée** (déploiement sur
accord explicite du propriétaire, jamais pendant une impression)

Remplace en partie ADR-053 : l'attente du filament à la tête reste, le
complément de purge et sa mesure sortent du démarrage.

## Contexte

Le cube de 11:15 est la première impression où le CFS a chargé à la
température du fichier (ADR-059, document 67). Thomas a observé le départ et
l'a dit sans détour : deux purges dans le bac, une à 200 °C puis une à 190 °C,
« faut choisir » ; deux lignes d'amorce, une première très lente puis une
seconde rapide et dense, « garder uniquement la seconde ».

Le journal dit d'où viennent les deux doublons.

**Deux purges.** Depuis le 9 septembre à 23:42 (ADR-058 et le test du
changement d'outil), `START_PRINT` émet lui-même `T{position - 1}` avant tout
chargement. Cette commande est le chargement complet du module compilé :
`box_extrude_material`, `extruder_extrude`, `material_change_flush` à
`flush_temp` (200 pour ce fichier), `G92 E0`. À 11:18:56 la purge stock était
finie, à chaud, boule décrochée. Puis le démarrage enchaînait la chaîne écrite
le 2 septembre pour un chargeur stock qui purgeait alors sur une buse à 109 °C
(ADR-053) : `BOX_EXTRUDER_EXTRUDE`, `_KCTRL_PURGE_BALL` de 120 mm à 190 °C,
`BOX_MATERIAL_FLUSH`. Compte rendu de 11:19 : 254 mm poussés après la purge
stock. Cette chaîne était antérieure au `T` et n'a jamais été élaguée quand il
est arrivé.

**Deux lignes.** `CX_PRINT_DRAW_ONE_LINE` ne trace ses trois cordons à 50 mm/s
que derrière `if self.pheaters.can_break_flag == 3` (custom_macro.py, ligne
55). Le 9 septembre nous avions lu ce drapeau comme un verrou de rupture de
filament, et gardé l'appel « pour la rétraction, la chauffe et la remise à zéro
du drapeau ». C'était faux : heaters.py met le drapeau à 1 au début de chaque
attente de température et à 3 à sa fin si elle n'a pas été interrompue (lignes
429 et 453). Le `M109` du démarrage suffit ; le drapeau vaut 3 à chaque
départ normal et la ligne stock est tracée à chaque fois, lentement, avant la
nôtre (journal de 11:19:50). Rien d'autre que cette routine ne lit le drapeau :
aucun `.so` ne le contient, heaters.py ne fait que l'écrire. Sa « rétraction »
`NEED_RETRACTION=12` est une extrusion de 12 mm hors plateau, et la chauffe est
déjà faite au-dessus.

## Décision

**Le démarrage ne pousse plus de filament lui-même.** Le changement d'outil
est tout le chargement : alimentation, tirage jusqu'à la buse, purge stock à
chaud à la température de la fiche alignée sur le fichier. Sortent de
`START_PRINT` : `_KCTRL_PURGE_MARK`, `M109` avant poussée, `BOX_EXTRUDER_EXTRUDE`,
`_KCTRL_PURGE_BALL`, `BOX_MATERIAL_FLUSH`, `M400`, `_KCTRL_PURGE_REPORT`. Les
macros de mesure disparaissent (elles n'ont jamais mesuré, voir ADR-053).
`_KCTRL_PURGE_BALL` reste comme outil manuel : `_KCTRL_PURGE_BALL TEMP=200
LEN=100`.

**Une seule ligne, la nôtre.** `CX_PRINT_DRAW_ONE_LINE` n'est plus appelée.
`_KCTRL_PRIME_LINE` trace ses trois passes à Z 0,36, 150 mm/s, 20 mm³/s.
Aucune remise à zéro du drapeau n'est nécessaire : personne ne le lit.

**Restent** : `KCTRL_WAIT_FILAMENT` et `_KCTRL_ASSERT_FILAMENT_ENGAGED` après le
`T`, comme preuve que le chargement stock a atteint la tête ; le `M109` à la
température du fichier après le chargeur, qui pose ses propres cibles ; les
quatre filets `_KCTRL_CFS_LOAD`, qui ne font rien quand la tête est chargée.

## Ce que ça change pour Thomas

Une boule dans le bac, à 200 °C pour un fichier à 190 (plancher du chargeur,
document 67 § 8). Une ligne d'amorce, la dense. Environ 250 mm de filament et
une minute de moins par démarrage.

## Preuve

- `tests/test_owned_start_purge_v1.py` : le démarrage ne contient plus aucune
  poussée de notre fait, un seul `T`, attente et assertion après lui,
  température du fichier rétablie avant la ligne, `_KCTRL_PURGE_BALL` hors
  démarrage mais toujours défini, macros de mesure absentes.
- `tests/test_owned_start_tool_change_and_prime_v1.py` : `T` avant l'attente,
  aucune purge de notre fait, appel stock absent, une seule ligne.
- `tests/test_cfs_slot_selection_and_refill_v1.py`,
  `tests/test_cfs_load_temperature_ceiling_v1.py` : l'armement du capteur suit
  le `T` et la ligne ; le `T` est dans la fenêtre de chargement.
- Observation attendue au prochain démarrage : une seule purge dans le journal
  (`material_change_flush`), aucun « complement de purge », aucune ligne stock
  à F3000 avant « ligne d'amorce ».

## Conséquences

- La ligne lente du stock servait aussi de trace visuelle que le filament
  coulait. La nôtre le montre autant, en trois passes.
- Un fichier sous 185 °C reste le cas ouvert du document 67 § 8 : la purge
  stock à 200 dépasserait le filet de chargement.
