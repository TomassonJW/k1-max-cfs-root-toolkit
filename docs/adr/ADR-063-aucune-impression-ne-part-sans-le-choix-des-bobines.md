# ADR-063 — Aucune impression ne part sans que Thomas ait raccordé ses bobines

Date : 2026-09-12

Statut : **acceptée ; écrite et testée ; installation le 12 septembre au
soir sur le « GO » de Thomas, machine à l'arrêt** (voir `STATE.md`). Le
même soir à 22:52, sur son refus d'ouvrir une page (« je veux démarrer de
Mainsail, un popup s'affiche contenant l'interface »), la même interface
passe en fenêtre qui s'ouvre d'elle-même dans Mainsail ; la décision ne
change pas, sa présentation oui. La lenteur du message d'attente (8 s sur un
fichier de 50 Mo) est corrigée dans la foulée.

Répond au point 2 du flux quotidien (`GOALS.md`) tel que Thomas l'a précisé
le 12 septembre : « je veux pas que Mainsail décide, je veux être obligé de
choisir avant le départ, et faire ce que je veux ». Document 78. Remplace
ADR-062 comme règle de départ ; ADR-062 reste le repli.

## Contexte

ADR-062 fait choisir les bobines par le fichier : même type et même couleur,
exactement, sinon refus avant la chauffe. Installée le 12 septembre à 21:00.
Le soir même, Thomas a posé deux questions : peut-il choisir lui-même la
bobine en voyant les couleurs et les matières du CFS, et que se passe-t-il
quand la couleur n'est pas exactement la même. La réponse d'ADR-062 est
« non » aux deux : la règle exacte ne laisse pas de place à un choix, et une
couleur approchée est un refus.

Ce qu'il veut est l'inverse : la machine ne décide pas, elle attend ; lui
voit les filaments du fichier et les bobines du CFS, et raccorde d'un clic
ce qu'il veut, y compris une autre couleur.

## Décision

**Chaque départ est retenu jusqu'à un choix fait à la main.** Le module
`kctrl_print_gate` reprend `SDCARD_PRINT_FILE`, la commande par laquelle
tout départ arrive à Klipper (Mainsail, Fluidd, écran, Creality Print,
Moonraker). Il garde le démarrage d'origine sous la main et ne l'appelle
qu'après confirmation. Tant que rien n'est confirmé, rien ne chauffe et rien
ne bouge ; Mainsail affiche une fenêtre qui renvoie à la page.

**La page Bobines** (`/bobines/` sur la passerelle K1 Control) montre les
filaments du fichier (couleur, matière, nom, utilisé ou seulement déclaré)
et toutes les bobines du CFS (couleur, matière, reste). Un clic sur un
filament, un clic sur une bobine. Une bobine identique au filament est
signalée, jamais raccordée d'elle-même. Le bouton de lancement n'existe
qu'une fois chaque filament utilisé raccordé.

**La confirmation écrit la table CFS comme `KCTRL_SLOT`** (`BOX_MODIFY_TN`,
`SAVE_VARIABLE slot_choice_*`, `slot_last_choice` pour le filament de
départ), puis appelle le démarrage d'origine. **`START_PRINT` prend la table
telle qu'elle est écrite** quand la porte a confirmé le fichier qu'il
démarre (`confirmed_file`) : l'appariement automatique (`match`) est coupé
pour ce départ, une autre couleur est un choix, pas une erreur. La ligne de
départ dit « raccordé sur la page Bobines ».

**Passent sans choix**, avec le comportement d'origine : la reprise après
coupure (`ISCONTINUEPRINT`), un départ pendant une impression ou une pause,
une carte virtuelle occupée, un fichier introuvable. Dans ces cas, et sur
`MATCH=1`, ADR-062 s'applique comme avant.

## Ce que ça change pour Thomas

Il ne peut plus lancer une impression sans passer par le choix : c'est ce
qu'il a demandé. Il lance depuis Mainsail, la fenêtre Bobines couvre
l'écran d'elle-même, il raccorde, « Lancer l'impression », et ça part ; la
page seule (`/bobines/`) reste pour un téléphone, Fluidd ou l'écran. En
échange, il voit avant chaque départ, côte à côte, ce que le fichier veut et
ce que le CFS porte, et il décide. La machine ne choisit plus jamais une
bobine à sa place au départ.

## Preuve

58 tests du module, 20 tests de la page et de la fenêtre dont les 17 tests
node de la partie pure, la fenêtre parcourue dans une fausse page Mainsail
contre un faux Moonraker puis dans le vrai Mainsail sur la machine (départ
du cube → fenêtre en 0,4 s, réduire, rouvrir, abandonner ; document 78,
section « Preuve »), suite complète verte. Premier départ réel par la
fenêtre le 12 septembre à 23:17 par Thomas (BIN4U, « raccorde sur la page
Bobines » au journal) : « c'est ce que j'attendais ».

## Conséquences

- ADR-062 passe de règle de départ à repli : reprise après coupure, porte
  inactive, `MATCH=1`.
- Le dernier choix retenu (`slot_choice_*`) est celui de la page, donc de
  Thomas ; une table effacée par la machine se remplit avec.
- Un redémarrage de Klipper pendant l'attente oublie le fichier, qui doit
  être relancé.
- La page et la fenêtre vivent dans la passerelle K1 Control, sans mot de
  passe, sur le réseau privé, au même titre que Mainsail.
- L'index de Mainsail servi par la passerelle porte une balise ajoutée par
  `mainsail_overlay_patch.py`. Mainsail est livré dans le dossier de version
  de K1 Control et n'est mis à jour par rien d'autre ; le service
  `S57k1_control_gateway` repose la balise à chaque démarrage de la
  passerelle, et toute nouvelle version de K1 Control recopie `www/bobines/`.
- La relève automatique en fin de bobine (point 5) n'est pas concernée : elle
  suit toujours les groupes du firmware.
