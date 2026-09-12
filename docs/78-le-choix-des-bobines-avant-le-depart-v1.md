# 78 — Le choix des bobines avant le départ : la fenêtre Bobines dans Mainsail

Date : 2026-09-12, soir. Décision : ADR-063. Point 2 du flux quotidien
(`GOALS.md`). Remplace, pour l'usage courant, l'appariement automatique du
document 75 (ADR-062), qui reste en repli.

## La demande

Le 12 septembre, sur l'appariement automatique livré le matin même, Thomas a
tranché : « je veux pas que Mainsail décide, je veux être obligé de choisir
avant le départ, et faire ce que je veux ». L'interface doit montrer la
couleur des filaments du fichier et la couleur des bobines du CFS, « un
affichage de toutes les bobines présentes dans le CFS, et un simple clic, je
peux juste raccorder les filaments du gcode ».

Deux conséquences directes. L'appariement exact (même type, même couleur)
n'est plus la règle de départ : il ne sait rien faire d'une couleur qui ne
colle pas, alors que Thomas, lui, sait ce qu'il veut. Et la machine ne part
jamais seule : chaque départ attend un choix.

Le soir même, devant la première version (une page à ouvrir soi-même,
annoncée par un message Mainsail qui donnait son adresse), Thomas a refusé :
« je veux exactement l'interface que tu as créée mais dans un popup, pas
dans une page que je dois ouvrir à chaque fois ; je veux démarrer de
Mainsail, un popup s'affiche contenant l'interface, et une fois les
filaments bien sélectionnés, l'impression part ». Et ce message « met des
plombes à arriver à l'écran ». Cette version corrige les deux : la même
interface s'ouvre d'elle-même par-dessus Mainsail dès qu'un départ est
retenu, et la retenue est annoncée en moins de trois secondes même sur un
fichier de 50 Mo (section « Pourquoi c'était lent »).

## Comment ça se passe

1. **Thomas lance un fichier** depuis Mainsail, Fluidd, l'écran ou Creality
   Print. Chaque départ arrive à Klipper sous la forme
   `SDCARD_PRINT_FILE FILENAME=...`. Le module `kctrl_print_gate` a pris la
   main sur cette commande à la connexion de Klipper ; il retient le fichier
   et **n'appelle pas** le démarrage d'origine. Rien ne chauffe, rien ne
   bouge. Klipper émet aussi son message « Choix des bobines » (avec un
   bouton « Annuler cette impression ») ; la console dit la même chose et
   donne l'adresse de la page pour qui n'est pas dans Mainsail.
2. **La fenêtre Bobines couvre Mainsail d'elle-même**, sans rien ouvrir :
   `overlay.js`, chargé par une balise ajoutée à l'index de Mainsail que sert
   la passerelle K1 Control, sonde l'attente toutes les 750 ms et se montre
   dès qu'un fichier est retenu. Elle montre à gauche les filaments du
   fichier — numéro, couleur (pastille et nom en français, code hex),
   matière, nom du filament dans le trancheur, et pour chacun s'il est
   réellement utilisé (balayage des `T` du fichier) ou seulement déclaré —
   et à droite toutes les bobines du CFS, unité par unité, avec couleur,
   matière et reste en pourcentage ; un emplacement vide est hachuré et
   inactif. La même interface existe en page seule,
   `http://192.168.1.64:4409/bobines/`, pour un téléphone, Fluidd ou
   l'écran.
3. **Un clic sur un filament, un clic sur une bobine.** Le filament suivant
   s'active tout seul. Sous chaque bobine, pendant qu'un filament est actif,
   une ligne dit ce que le raccord veut dire : « identique au fichier »,
   « même matière, autre couleur », « autre matière : PETG au lieu de PLA ».
   Une bobine identique porte un badge « identique », **sans être
   raccordée d'elle-même** : rien ne se raccorde sans clic. Un second clic
   sur la même bobine défait le raccord ; cliquer une autre bobine déplace
   le filament ; une bobine déjà prise peut changer de filament.
4. **« Lancer l'impression »** ne s'active que quand chaque filament utilisé
   a sa bobine. Il envoie `KCTRL_GATE_CONFIRM MAP=T1A:T2D,... FILE="..."`.
   Le module vérifie (fichier toujours en attente, même nom, filaments
   connus, emplacements chargés, aucune impression en cours), écrit la table
   CFS comme le ferait `KCTRL_SLOT` (`BOX_MODIFY_TN`, `SAVE_VARIABLE
   slot_choice_*`, `slot_last_choice` pour le filament de départ), ferme la
   fenêtre Mainsail, puis appelle le démarrage d'origine. `START_PRINT` voit
   que la porte a confirmé ce fichier précis (`confirmed_file`) et prend la
   table **telle qu'elle est écrite**, autre couleur comprise : l'appariement
   automatique ne tourne pas. La ligne de départ dit « raccordé sur la page
   Bobines ». La fenêtre dit « Impression lancée » avec les bobines
   retenues, puis se retire au bout de quatre secondes ; Mainsail suit.
5. **« Abandonner cette impression »** demande une confirmation (le bouton
   devient « Sûr ? Confirmer l'abandon » pendant cinq secondes), puis envoie
   `KCTRL_GATE_CANCEL` : le fichier est oublié, rien n'a chauffé.
6. **« Réduire »**, Échap ou un clic à côté de la fenêtre la mettent de côté
   pour ce fichier ; une pastille « Une impression attend son choix de
   bobines · Ouvrir » reste en bas à droite de Mainsail et la rouvre avec
   les raccords déjà faits. Un autre fichier retenu rouvre la fenêtre de
   lui-même. Sous la fenêtre réduite, le message Klipper reste visible ;
   son « Annuler cette impression » vaut abandon.

Quand rien n'attend, la fenêtre n'existe pas. La page seule, elle, le dit,
montre quand même les bobines, et propose les huit derniers fichiers avec un
bouton « Choisir ses bobines », qui lance le fichier par Moonraker
(`printer/print/start`) et revient donc au point 1.

## Ce qui passe sans choix

- La reprise après coupure de courant (`ISCONTINUEPRINT`) : le firmware
  reprend ses bobines, la porte laisse passer.
- Un `SDCARD_PRINT_FILE` pendant qu'une impression tourne ou est en pause,
  ou pendant que la carte virtuelle est occupée : le comportement d'origine.
- Un fichier introuvable : le démarrage d'origine, qui rend l'erreur
  habituelle.
- Un fichier sans bloc de configuration Orca : il attend quand même, avec
  les filaments trouvés par balayage (type et couleur inconnus, à raccorder
  à vue).

Dans ces cas-là, ou si `MATCH=1` est donné à `START_PRINT`, l'appariement
automatique (ADR-062) reste en place comme avant.

## Ce qui est écrit

Le détail par fichier et l'installation sont dans
`packages/k1-control-v1/spool-choice-gate-v1/README.md`.

| Pièce | Ce qu'elle fait |
| --- | --- |
| `kctrl_print_gate.py` (module Klipper) | reprend `SDCARD_PRINT_FILE` à la connexion ; retient le fichier ; publie filaments du fichier, bobines du CFS, identiques, dernier événement ; `KCTRL_GATE_CONFIRM`, `KCTRL_GATE_CANCEL`, `KCTRL_GATE` |
| `www/bobines/` (interface) | sans rien de l'extérieur : `logic.js` (pur : modèle, raccords, compatibilité, noms de couleurs, règle d'affichage de la fenêtre), `bobines.js` (l'interface, montée une fois par `mount(root, options)` : Moonraker, clics, boutons, hors-ligne), `styles.css` ; `overlay.js` (la fenêtre dans Mainsail : shadow DOM, sondage toutes les 750 ms, pastille) ; `index.html` + `app.js` (la page seule) |
| `mainsail_overlay_patch.py` | ajoute (ou retire, `--remove`) la balise `<script type="module" src="/bobines/overlay.js">` avant `</body>` de l'index de Mainsail, avec copie datée |
| `nginx-location.conf` | les trois blocs de la passerelle : redirection `/bobines`, `location /bobines/`, `location = /index.html` (l'index de Mainsail jamais mis en cache, pour que la balise soit vue au chargement suivant) |
| `[kctrl_print_gate]` dans le `.cfg` de démarrage | la section, et `START_PRINT` qui lit `confirmed_file` |

La fenêtre lit `printer/objects/query?kctrl_print_gate&print_stats` toutes
les 750 ms, la page chaque seconde. Sans réponse en quatre secondes, un
bandeau « hors ligne » ; si le module n'est pas chargé, l'en-tête dit
« Porte absente ». Un nouveau fichier en attente remet le choix à zéro. La
fenêtre vit dans un shadow DOM : ni les styles de Mainsail ni les siens ne
passent la frontière.

## Pourquoi c'était lent, et ce qui a changé

La retenue n'était annoncée qu'après le balayage des `T` du fichier, et ce
balayage passait une expression régulière sur chacun de ses blocs d'un
mégaoctet : 8,2 s sur le fichier BIN4U de 50,9 Mo, mesurés sur la machine.
Un bloc ne mérite l'expression que si l'une de ses lignes peut commencer par
un `T`, ou par un blanc : ce test préalable (`may_hold_tool`) ne laisse
passer qu'un bloc sur quarante-neuf sur ce fichier, et le balayage seul
tombe à 0,85 s. Mesuré sur la machine après installation, du
`printer/print/start` à la retenue visible dans le statut : 2,4 s pour
BIN4U (lecture depuis la carte comprise), 0,25 s pour le cube. Dans
Mainsail, la fenêtre a suivi 0,4 s après le départ du cube.

## Preuve

- `tests/test_kctrl_print_gate_v1.py`, 58 tests : balayage des `T` (ordre,
  fichier mono, frontière de bloc, `CRLF`, espaces devant, blocs sans `T`
  jamais passés à l'expression, `may_hold_tool` sur huit cas) ; prise de main
  à la connexion ; retenue et fenêtre ; statut (filaments, bobines,
  identiques) ; passages sans choix (reprise, impression en cours, carte
  occupée, fichier absent) ; confirmation (écritures exactes et leur ordre,
  chemin complet, casse) ; refus (mauvais fichier, `MAP` mal formé,
  filament utilisé sans bobine, emplacement vide, rien en attente, pendant
  une impression) ; échec du démarrage d'origine oublié, échec d'écriture
  qui garde l'attente ; abandon ; `START_PRINT` rendu avec la porte
  (« raccordé sur la page Bobines », autre fichier, `MATCH=1`).
- `tests/test_bobines_page_v1.py`, 20 tests : rien de l'extérieur, page et
  fenêtre montées sur la même interface, la fenêtre se montre seule et ne
  liste jamais les fichiers, feuille de style valable dans un shadow DOM,
  routes et commandes exactes, jamais de raccord sans clic, bouton inactif
  tant que ce n'est pas complet, balise ajoutée une fois avant `</body>`
  avec copie (idempotent, réversible, refus sans `</body>`), trois blocs
  nginx en `root` avec les en-têtes repris avant le `location /`, clés du
  statut partagées, et les 17 tests node de `logic.test.mjs` (modèle, clés
  d'attente, raccords, complétude, `MAP`, compatibilité, libellés, règle
  d'affichage de la fenêtre : choix, réduite, lancée quatre secondes,
  cachée).
- Fenêtre parcourue dans un navigateur, injectée dans une fausse page
  Mainsail aux styles hostiles, contre un faux Moonraker : apparue 62 ms
  après le départ, styles intacts, raccords T1B/T1D, « Réduire » → pastille
  → rouverte avec les raccords, « Lancer » → `KCTRL_GATE_CONFIRM
  MAP=T1A:T1B,T1B:T1D FILE="..."` reçu, « Impression lancée » puis retrait
  après quatre secondes, nouveau fichier → choix à zéro, Échap → pastille,
  abandon en deux temps → `KCTRL_GATE_CANCEL` ; en 375 px, plein écran sur
  une colonne avec la barre d'actions collée en bas.
- Dans le vrai Mainsail, le 12 septembre à 22:55 : départ du cube par
  `printer/print/start` → fenêtre en 0,4 s ; « Réduire » → pastille, message
  Klipper visible derrière ; pastille → fenêtre ; abandon en deux temps →
  « Impression abandonnée, rien n'a chauffé », fenêtre retirée, `pending 0`,
  état `standby`.
- Page parcourue dans un navigateur contre un faux Moonraker (fichier à
  trois filaments dont deux utilisés, les six bobines du 10 septembre) :
  raccord, déplacement, défaire, raccord d'un PETG sur un PLA signalé,
  lancement (commande `KCTRL_GATE_CONFIRM MAP=T1A:T2A,T1B:T2D FILE="..."`
  reçue, vue « impression en cours » avec les bobines marquées), abandon
  en deux temps, vue au repos avec la liste des fichiers, erreur de Klipper
  rendue telle quelle (« emplacement(s) vide(s) ou unité non connectée »)
  sans perdre le choix.

L'installation sur la machine et ses preuves sont dans `STATE.md` du 12
septembre au soir. **Premier départ réel par la fenêtre le 12 septembre à
23:17, par Thomas** (« ok super, j'ai pu lancer, c'est ce que j'attendais ») :
BIN4U, journal « bobines raccordees pour BIN4U… », « lance avec T1A=T1B »,
ligne de départ « filament 1 du fichier (T1A) -> emplacement T1B
(raccorde sur la page Bobines) », impression en cours à 23:20.

## Limites connues

- Un redémarrage de Klipper pendant l'attente oublie le fichier : le
  relancer.
- Le popup de choix de l'écran Creality existe toujours ; ce qu'il écrit
  dans la table est relu par la page (elle montre la table, pas le popup).
- La page est servie sans mot de passe sur le réseau privé, comme Mainsail
  sur la même passerelle.
- Le choix se fait par filament utilisé ; un filament déclaré mais jamais
  utilisé est montré grisé et ne bloque rien.
- La balise vit dans l'`index.html` de Mainsail, lui-même livré dans le
  dossier de version de K1 Control (`releases/K1-CONTROL-V1.0.0`, `current`
  y pointe) ; rien ne met Mainsail à jour par ailleurs (pas
  d'`update_manager` Moonraker), seule une nouvelle version de K1 Control
  livrerait un index neuf. Pour que la fenêtre y survive :
  `S57k1_control_gateway` relance `mainsail_overlay_patch.py` (posé dans
  `state/`, hors du dossier de version) à chaque démarrage de la passerelle,
  et la procédure de version recopie `www/bobines/`. Le nginx de la machine
  n'a ni `sub_filter` ni `addition` : impossible d'ajouter la balise à la
  volée sans toucher au fichier. Ce service modifié est écrit et testé le 12
  septembre à 23:30 ; à poser sur la machine à l'arrêt (voir HANDOFF).
- Fluidd et l'écran n'ont pas la fenêtre : la page seule.
- Le message Klipper « Choix des bobines » reste derrière la fenêtre et se
  voit quand elle est réduite ; c'est voulu, il porte l'abandon.

## Retour arrière

`python3 mainsail_overlay_patch.py --remove
/usr/data/k1-control-v1/current/www/mainsail/index.html` (ou recopier
`index.html.bak-<date>`), recopier les sauvegardes `.bak-<date>` du `.cfg`
et de `nginx-active.conf`, supprimer `kctrl_print_gate.py` et son `.pyc`,
retirer le dossier `www/bobines/`, `S57k1_control_gateway reload`,
`S55klipper_service restart`. Les départs repartent alors sur l'appariement
automatique (ADR-062).
