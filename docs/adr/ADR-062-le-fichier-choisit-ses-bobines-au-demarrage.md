# ADR-062 — Le fichier choisit ses bobines au démarrage

Date : 2026-09-10

Statut : **acceptée ; écrite et testée ; pas encore déployée** (déploiement
sur accord explicite du propriétaire, machine à l'arrêt, redémarrage du
service Klipper, avec ADR-061).

Répond au point 2 du flux quotidien dicté le 10 septembre (`GOALS.md`) :
« le choix des bobines affiché dans Mainsail / Fluidd ». Document 75.

## Contexte

Le popup de choix des bobines n'existe que sur l'écran Creality et dans
Creality Print. Depuis Mainsail ou Fluidd, `START_PRINT` part sur la table
`tnn_map` telle qu'elle est, c'est-à-dire sur le dernier choix de quelqu'un
d'autre : le travail précédent, une relève automatique, un `KCTRL_SLOT`. Le
9 septembre, un travail qui voulait l'eSUN de T2D a chargé et purgé le
Geeetech noir de T1B.

Le fichier tranché déclare le type et la couleur de chacun de ses filaments
en queue de fichier (ADR-061). Le CFS publie le type et la couleur de chaque
bobine chargée, et ses groupes de relève disent lesquelles il tient pour
identiques : même matière **et** même couleur.

## Décision

**`kctrl_slot_map` publie `match`** : pour chaque filament que le fichier en
cours déclare, l'emplacement chargé de même type et de même couleur, et
`match_notes`, la raison de chaque appariement ou de chaque échec. Règle :

- type et couleur exactement égaux, les critères des groupes de relève du
  firmware ;
- un filament déjà sur une bobine qui convient la garde ;
- plusieurs bobines identiques sont interchangeables : la première prise,
  les autres nommées ;
- un filament sans couleur déclarée prend la seule bobine de son type, et
  refuse d'en choisir une parmi plusieurs ;
- aucune couleur approchée : la plus proche est nommée dans le refus, avec
  le `KCTRL_SLOT` qui l'imposerait.

**`START_PRINT` lit `match` au rendu** et le fait passer avant la table et
avant le dernier choix retenu ; `TOOL=` reste au-dessus de tout, `MATCH=0`
rend l'ancien comportement, un fichier sans bloc de configuration ne change
rien. Un filament de départ sans bobine est un refus au rendu, avec la note
du filament. Après `KCTRL_MATERIAL_ALIGN` et avant toute chauffe, la macro
émet **`KCTRL_MATCH STARTING=1`**, qui écrit dans la table chaque filament
que le fichier **utilise** (balayage des `T` du fichier), avec les deux
commandes de `KCTRL_SLOT` (`BOX_MODIFY_TN`, `SAVE_VARIABLE slot_choice_*`),
et refuse avant la première écriture si un filament utilisé n'a pas de
bobine. Un filament déclaré mais non utilisé est signalé, pas écrit, pas
bloquant.

`KCTRL_MATCH` seul, à la console : `CHECK=1` montre sans écrire, `FILE=`
lit un autre fichier, `SKIP=` laisse un filament tel quel ; sans `CHECK=1`
il refuse pendant une impression.

## Ce que ça change pour Thomas

Un démarrage depuis Mainsail prend les bobines que le fichier demande, dit
lesquelles et pourquoi, et s'arrête avant de chauffer quand il en manque une,
en nommant la plus proche et la commande pour l'imposer. Le popup de
l'écran n'est plus le seul endroit où le choix se fait.

## Preuve

`tests/test_kctrl_match_v1.py`, 47 tests : les trois formes de couleur de la
machine ; types par fiche et par groupe ; appariement pur (accord des deux
critères, bobine gardée, déplacée, identiques, plus proche nommée, type
absent, sans couleur, sans type, rien chargé) ; statut sur la queue réelle du
cube du 10 septembre ; commande (écritures exactes, non utilisé signalé,
refus sans écriture, table conforme, `CHECK`, `SKIP`, `FILE`, garde
impression) ; macro (lecture au rendu, ordre après l'alignement et avant
toute chauffe, refus au rendu sans `#`, rendu des cas apparié / `MATCH=0` /
`TOOL=` / refus / sans bloc).

Observation attendue au premier démarrage réel : les lignes « K1 Control:
appariement du fichier sur les bobines » puis « (appariement sur le fichier,
type et couleur) » dans la ligne de départ, puis `cmd_T vtnn=` sur la bobine
appariée.

## Conséquences

- La relève automatique (point 5) et l'appariement suivent la même règle :
  deux bobines interchangeables pour l'un le sont pour l'autre.
- Le dernier choix retenu (`slot_choice_*`) est réécrit par l'appariement :
  après un démarrage apparié, une table effacée par la machine se remplit
  avec les bobines du dernier fichier, pas plus faux qu'avant.
- Un fichier d'un autre trancheur, sans bloc Orca, garde exactement le
  comportement d'avant.
