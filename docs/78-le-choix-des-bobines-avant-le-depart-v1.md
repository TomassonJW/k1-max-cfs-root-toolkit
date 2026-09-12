# 78 — Le choix des bobines avant le départ : la page Bobines

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

## Comment ça se passe

1. **Thomas lance un fichier** depuis Mainsail, Fluidd, l'écran ou Creality
   Print. Chaque départ arrive à Klipper sous la forme
   `SDCARD_PRINT_FILE FILENAME=...`. Le module `kctrl_print_gate` a pris la
   main sur cette commande à la connexion de Klipper ; il retient le fichier
   et **n'appelle pas** le démarrage d'origine. Rien ne chauffe, rien ne
   bouge. Mainsail affiche une fenêtre « Choix des bobines » avec l'adresse
   de la page et un bouton « Annuler cette impression » ; la console dit la
   même chose.
2. **La page Bobines** (`http://192.168.1.64:4409/bobines/`, servie par la
   passerelle K1 Control, à côté de Mainsail) montre à gauche les filaments
   du fichier — numéro, couleur (pastille et nom en français, code hex),
   matière, nom du filament dans le trancheur, et pour chacun s'il est
   réellement utilisé (balayage des `T` du fichier) ou seulement déclaré —
   et à droite toutes les bobines du CFS, unité par unité, avec couleur,
   matière et reste en pourcentage ; un emplacement vide est hachuré et
   inactif.
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
   Bobines ».
5. **« Abandonner cette impression »** demande une confirmation (le bouton
   devient « Sûr ? Confirmer l'abandon » pendant cinq secondes), puis envoie
   `KCTRL_GATE_CANCEL` : le fichier est oublié, rien n'a chauffé.

Quand rien n'attend, la page le dit, montre quand même les bobines, et
propose les huit derniers fichiers avec un bouton « Choisir ses bobines »,
qui lance le fichier par Moonraker (`printer/print/start`) et revient donc
au point 1.

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
| `www/bobines/` (page) | une page seule, sans rien de l'extérieur : `logic.js` (pur : modèle, raccords, compatibilité, noms de couleurs), `app.js` (Moonraker toutes les secondes, clics, boutons, hors-ligne), `styles.css`, `index.html` |
| `nginx-location.conf` | le bloc `location /bobines/` de la passerelle, sans cache |
| `[kctrl_print_gate]` dans le `.cfg` de démarrage | la section, et `START_PRINT` qui lit `confirmed_file` |

La page lit `printer/objects/query?kctrl_print_gate&print_stats` chaque
seconde. Sans réponse en quatre secondes, un bandeau « hors ligne » ; si le
module n'est pas chargé, l'en-tête dit « Porte absente ». Un nouveau fichier
en attente remet le choix à zéro.

## Preuve

- `tests/test_kctrl_print_gate_v1.py`, 38 tests : balayage des `T` (ordre,
  fichier mono, frontière de bloc, `CRLF`, espaces devant) ; prise de main
  à la connexion ; retenue et fenêtre ; statut (filaments, bobines,
  identiques) ; passages sans choix (reprise, impression en cours, carte
  occupée, fichier absent) ; confirmation (écritures exactes et leur ordre,
  chemin complet, casse) ; refus (mauvais fichier, `MAP` mal formé,
  filament utilisé sans bobine, emplacement vide, rien en attente, pendant
  une impression) ; échec du démarrage d'origine oublié, échec d'écriture
  qui garde l'attente ; abandon ; `START_PRINT` rendu avec la porte
  (« raccordé sur la page Bobines », autre fichier, `MATCH=1`).
- `tests/test_bobines_page_v1.py`, 9 tests : rien de l'extérieur, routes et
  commandes exactes, jamais de raccord sans clic, bouton inactif tant que ce
  n'est pas complet, bloc nginx en `root` avant le `location /`, clés du
  statut partagées, et les 14 tests node de `logic.test.mjs` (modèle, clés
  d'attente, raccords, complétude, `MAP`, compatibilité, libellés).
- Page parcourue dans un navigateur contre un faux Moonraker (fichier à
  trois filaments dont deux utilisés, les six bobines du 10 septembre) :
  raccord, déplacement, défaire, raccord d'un PETG sur un PLA signalé,
  lancement (commande `KCTRL_GATE_CONFIRM MAP=T1A:T2A,T1B:T2D FILE="..."`
  reçue, vue « impression en cours » avec les bobines marquées), abandon
  en deux temps, vue au repos avec la liste des fichiers, erreur de Klipper
  rendue telle quelle (« emplacement(s) vide(s) ou unité non connectée »)
  sans perdre le choix.

L'installation sur la machine et ses preuves sont dans `STATE.md` du 12
septembre au soir. **Le premier départ réel par la page reste à observer
par Thomas** : fenêtre dans Mainsail, page, clic, « raccordé sur la page
Bobines » dans la ligne de départ, puis `cmd_T vtnn=` sur la bobine
choisie.

## Limites connues

- Un redémarrage de Klipper pendant l'attente oublie le fichier : le
  relancer.
- Le popup de choix de l'écran Creality existe toujours ; ce qu'il écrit
  dans la table est relu par la page (elle montre la table, pas le popup).
- La page est servie sans mot de passe sur le réseau privé, comme Mainsail
  sur la même passerelle.
- Le choix se fait par filament utilisé ; un filament déclaré mais jamais
  utilisé est montré grisé et ne bloque rien.

## Retour arrière

Recopier les sauvegardes `.bak-<date>` du `.cfg` et de
`nginx-active.conf`, supprimer `kctrl_print_gate.py` et son `.pyc`, retirer
le dossier `www/bobines/`, `S57k1_control_gateway reload`,
`S55klipper_service restart`. Les départs repartent alors sur l'appariement
automatique (ADR-062).
