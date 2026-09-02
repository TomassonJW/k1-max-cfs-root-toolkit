# ADR-058 — La table CFS s'efface, et le dernier choix la relève

Date : 2026-09-02

Statut : **accepté**. Amende le point 3 de l'ADR-056, vérifié sur la machine.

## Contexte

L'ADR-056 a fait de `Tnn_map` la source unique de « quelle bobine », supprimé
la variable persistante `kctrl_slot` et posé qu'une table illisible est un
refus de démarrer. Le raisonnement tenait tant que la table survivait à la
machine.

Elle n'y survit pas. Le 2 septembre au soir, un arrêt d'urgence puis un
redémarrage ont rendu un `tn_data.json` ne contenant plus que `base_data` :
plus de `tnn_map` du tout. Toute impression lancée depuis Mainsail était alors
refusée par le garde de `START_PRINT`, avec une phrase qui envoyait vers
l'écran — c'est-à-dire vers le seul chemin que Thomas n'utilise pas.

Le refus était juste : partir sur `T1A` en silence reste la panne d'origine.
C'est la conclusion qui manquait. Un refus qu'aucune action ordinaire ne lève
n'est pas une garde, c'est une impasse : la machine perd la réponse toute
seule, et l'opérateur n'a rien fait de mal.

## Décision

**Le dernier emplacement explicitement choisi est retenu, et relève la table
quand la machine l'a effacée.**

1. `KCTRL_SLOT` écrit `Tnn_map` — inchangé, c'est toujours la première
   écriture — puis enregistre le choix sous `slot_last_choice`, uniquement pour
   le premier filament du travail, `T1A`. Les autres entrées sont les couleurs
   suivantes d'un même travail : les retenir ferait repartir l'impression
   suivante sur la mauvaise bobine.
2. `START_PRINT` résout dans cet ordre : `TOOL=` imposé, puis la table, puis le
   dernier choix retenu, puis le refus. Le repli n'est pas une devinette : il
   rejoue une décision explicite, `BOX_MODIFY_TN` la réécrit aussitôt dans la
   table, et la ligne de démarrage nomme d'où vient l'emplacement.
3. `KCTRL_SLOTS` applique exactement la même résolution et l'affiche, pour que
   la réponse se lise avant de lancer plutôt qu'après un refus. Un test épingle
   que les deux macros lisent les deux mêmes sources dans le même ordre.

La mémoire ne peut pas contredire la table : elle n'est lue que si la table est
absente, et la première chose qui suit sa lecture est sa réécriture dans la
table.

## Preuves

Sur la machine, le 2 septembre, sans impression en cours :

| Question | Preuve |
|---|---|
| La table disparaît vraiment | `tn_data.json` après l'arrêt d'urgence : `base_data` seul, aucune clé `tnn_map` |
| Le choix est retenu | `slot_last_choice = 'T1A'` dans `k1-control-saved-vars.cfg` après `KCTRL_SLOT SLOT=T1A` |
| Le repli s'applique quand la table manque | table retirée du fichier, puis `KCTRL_SLOTS` : `premier filament sur T1A (dernier choix retenu, table CFS effacee)` |
| Il ne s'applique pas quand elle est là | table remise : `premier filament sur T1A (table CFS)` |
| La configuration est acceptée | `FIRMWARE_RESTART` → `Printer is ready` |

La branche de repli de `START_PRINT` elle-même n'a pas été exécutée : elle
n'existe qu'au démarrage d'une impression, qui chauffe et imprime. C'est la
même expression que celle de `KCTRL_SLOTS`, prouvée ci-dessus, et deux tests
l'épinglent.

## Conséquences

Une reprise après coupure ne demande plus rien. Le premier lancement qui suit
dit sur quelle bobine il part et pourquoi.

Le refus subsiste quand rien n'a jamais été choisi : là, aucune décision
n'existe à rejouer, et la phrase renvoie vers `KCTRL_SLOTS` puis `KCTRL_SLOT`,
qui sont dans Mainsail, plutôt que vers l'écran.

Ce qui reste ouvert : le popup de l'écran, lui, connaît les couleurs du fichier
tranché. Le repli ne les connaît pas. Un travail multicolore lancé depuis
Mainsail après une coupure repart donc sur les emplacements du dernier travail,
pas sur ceux que le fichier demande. Voir doc 55 pour la table que le firmware
sait construire seul.
