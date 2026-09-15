# ADR-067 — La fin d'impression vide la tête elle-même : coupe, puis rembobinage de l'emplacement nommé, avant la fin stock

Date : 2026-09-15

Statut : **acceptée** (« tente les corrections … GO ! », Thomas, le
15 septembre) ; écrite et testée hors machine (21 tests) ; posée le
15 septembre à 14:03, machine au repos, sauvegarde
`k1-control-owned-start-print-v2.cfg.bak-20260915-adr067`, Klipper prêt à
14:04:02 ; **première fin réelle à observer** (document 81, section 6).

## Contexte

Le 15 septembre à 12:03, la fin de l'impression `…Shell_PLA_8h16m` entre dans
la fin stock (`END_PRINT_NO_M84`, donc `BOX_END`). Le module CFS compilé prend
la branche « extrude all material, last_cmd: T1A » et pousse 80 mm toutes les
40 s pendant 17 minutes, environ 2 m, jusqu'à ce que Klipper meure d'autre
chose (document 81). La Pause demandée entre-temps n'a pas tourné : la macro
de fin tient la file G-code. La veille à 22:53, la même fin avait coupé,
rembobiné et rendu la main en 49 s. Ce qui choisit la branche est dans le
module ; l'objet `box` n'en dit rien.

Après le redémarrage, le retrait de l'écran échoue : `BOX_RETRUDE_MATERIAL`
sans `TNN` ne fait rien quand le module a perdu le filament chargé
(`last_tnn: None`, 13:02). `BOX_RETRUDE_MATERIAL_WITH_TNN TNN=T1A` a rembobiné
`T1A` en 20 s (13:23). Notre enveloppe de changement d'outil
(`kctrl_tool_change.last.slot`) et notre départ savent quel emplacement est à
la tête ; le module, pas toujours.

## Décision

1. `END_PRINT` et `CANCEL_PRINT` appellent `_KCTRL_UNLOAD` (`REASON=fin` ou
   `annulation`) après l'extinction de l'alarme du capteur de tête et avant
   `END_PRINT_NO_M84`, qui reste tel quel.
2. `_KCTRL_UNLOAD` : buse à sa température d'impression, ou 200 °C si la
   cible est plus basse (`TEMP=` pour changer ce plancher) ; `BOX_ERROR_CLEAR` ;
   `BOX_CUT_MATERIAL` ; `M400` ; `BOX_RETRUDE_MATERIAL_WITH_TNN TNN=<slot>` ;
   `M400` ; `_KCTRL_UNLOAD_CHECK`. L'emplacement est, dans l'ordre, `TOOL=`,
   le dernier changement d'outil de notre enveloppe qui a atteint la tête
   (`done`, `start`, `empty`, `paused_by_firmware`), puis le filament du départ
   (`START_PRINT.active_tool`, écrit avant le `T` du départ).
3. Rien ne bouge, et la fin stock fait son propre retrait, quand le CFS est
   inactif, quand le capteur de tête est déjà vide, quand les axes ne sont pas
   référencés (annulation avant le `G28` du départ), ou quand l'emplacement
   est inconnu ou mal formé. Chaque cas dit pourquoi à la console.
4. `_KCTRL_UNLOAD_CHECK`, macro à part, relit le capteur de tête après le
   rembobinage et le dit : « fait, tete vide » ou « incomplet, … la fin stock
   (BOX_END) reessaie ». Aucune des deux macros ne lève : une erreur
   finirait `END_PRINT` avant `TURN_OFF_HEATERS`, et `idle_timeout` vaut
   99999999 s sur cette machine.

Les deux contraintes du rendu Jinja d'ADR-066 fixent la forme : le capteur
est lu au rendu de `_KCTRL_UNLOAD`, c'est l'état d'avant la coupe, le bon ;
l'état d'après vient d'une seconde macro. Une troisième contrainte, apprise à
la pose : Klipper lit le fichier avec `inline_comment_prefixes=(';', '#')`,
un ` ;` dans un message coupe la ligne et le modèle ne se charge plus
(erreur de 14:00, document 81) ; un test l'interdit désormais.

## Conséquences

- Une fin normale fait deux retraits de suite : le nôtre, puis `BOX_END`
  devant une tête vide. Ce que fait `BOX_END` dans ce cas n'est pas encore
  observé ; l'audit en direct le mesure à la prochaine fin (`box_end` →
  `Exiting`, tronçons poussés).
- Une annulation pendant la chauffe attend la cible avant de couper ; une
  annulation cible à 0 (après un arrêt du départ, ADR-066) réchauffe la buse
  à 200 °C pour vider la tête, comme la fin stock l'aurait fait.
- Le retrait à la main reste `BOX_RETRUDE_MATERIAL_WITH_TNN TNN=Txx` (ou
  `_KCTRL_UNLOAD TOOL=Txx REASON=manuel`, qui coupe d'abord), jamais
  `BOX_RETRUDE_MATERIAL` seul après un redémarrage.
- La position finale de la tête reste celle de la fin stock : après un
  retrait, la position de purge (`BOX_GO_TO_BOX_EXTRUDE_POS`), pas le cutter.
- Vérifié hors machine : 21 tests
  (`tests/test_owned_end_unloads_the_head_v1.py`), suite complète verte hors
  les deux rouges volontaires de la CI.
- **Inconnu :** la branche « extrude all material » elle-même n'est pas
  supprimée, seulement privée de filament à pousser ; si `BOX_END` la prend
  quand même devant une tête vide, l'audit le dira et il faudra remplacer
  `BOX_END` par ce qu'il fait d'autre (section 4 du document 81).

## Voir aussi

- ADR-066 — le départ s'arrête net sur une pause ; contraintes du rendu Jinja
- ADR-065 — alarme de fin de bobine coupée pendant un changement d'outil
- ADR-044 — voie de retrait manuel
- Document 81 — fin d'impression en boucle, lectures bornées, alertes
- Document 80 — pauses `key831`, garde du bus
