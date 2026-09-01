# HANDOFF — pause propre sur le capteur cutter

Date de passation : 2026-09-01

Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`

Phase : P4, Goal 3 toujours à `2/7`

État de reprise : **ATTENDRE_GO**, c'est-à-dire attendre uniquement que Thomas
soit de nouveau devant la K1 ; aucun identifiant technique n'est à recopier.

## 1. État livré

Le propriétaire complet du cycle stock-derived, son interface K1 Control et le
propriétaire CFS direct sont installés. Les commandes CFS stock concurrentes
restent exclues pendant la possession K1 Control. Le cycle applique le meilleur
mesh existant `k1_p001_t055_r001_n11x11` et le Z accepté `−0,04 mm`; il ne
recalcule aucun mesh et ne repalpe jamais après insertion de filament.

La quantité de purge a été corrigée à partir des traces réelles. La reprise
fautive ne poussait que `30 mm`. Le chargement initial utilise maintenant le
vecteur Orca du G-code, avec un repli exact de `140 mm`. Les changements
utilisent la matrice de volumes, le diamètre déclaré et `flush_multiplier`. Le
G-code court actuel donne `266,081080 mm` pour `0→1` et `126,804265 mm` pour
`1→0`; la limite de sécurité du propriétaire vaut `400 mm`. Un changement de
matière ou de couleur reste fermé tant que l'outil G-code n'est pas relié sans
ambiguïté à une route CFS réelle.

Deux autres défauts de départ ont été corrigés et posés : une route `T1A` déjà
possédée reste présente pendant l'accès au cutter, et aucune réconciliation
moteur n'est envoyée lorsque le propriétaire direct possède déjà cette route
en phase `loaded`.

Le premier retrait intégré s'est toutefois arrêté avant toute rétraction. La
tête a essayé la position stock `X38 Y304,5`, puis chaque demi-millimètre
jusqu'à la limite Y publiée `307,5`. `cut_pos` est resté à `0`; le garde a donc
refusé le retrait. Il est interdit de dépasser cette limite ou de rejouer la
même trajectoire automatiquement.

Le dernier état physique observé avant la pause est sûr : Klipper `ready`,
impression `standby`, buse autour de `30 °C`, cibles buse et plateau à zéro,
axes libérés, tête à environ `X38 Y230 Z50`, `T1A` toujours chargé selon le
propriétaire direct, capteurs tête et après-cutter actifs, route stock vide,
`auto_refill=0`, mesh `11 × 11` actif et Z `−0,04 mm`. Aucun palpage, mesh,
extrusion ou retrait n'a eu lieu pendant les refus cutter.

## 2. Diagnostic cutter déjà acquis

La configuration exacte relie le cutter à l'entrée `nozzle_mcu:PA8`. Les
traces historiques de cette même K1 prouvent qu'un cycle stock fonctionnel
plaçait la tête à `X38 Y304,5`, publiait `cut_pos=1`, restait en appui pendant
le retrait, puis revenait à `0` après libération. Les données historiques sont
donc suffisantes pour connaître la bonne séquence ; elles ne prouvent pas que
le levier, la lame ou le capteur sont encore mécaniquement conformes aujourd'hui.

Un moniteur strictement en lecture seule est disponible dans
`remote_manual_cutter_sensor_check.py`. Il vérifie d'abord la K1 froide et au
repos, puis surveille jusqu'à trente minutes le passage `0→1→0`. Il n'appelle
aucun G-code et ne commande ni chauffe, ni axe, ni filament. Une fenêtre de
`90 s`, puis une fenêtre longue interrompue à la demande de Thomas, n'ont pas
capté d'appui humain confirmé. Elles sont **inconclusives** et ne démontrent pas
une panne du capteur.

## 3. Liste complète des gestes humains restants

Cette liste doit être annoncée en entier au début de la reprise. Aucun nouveau
micro-test surprise ne doit être ajouté.

1. **Contrôle mécanique à froid.** Thomas vérifie que le petit poussoir/levier
   de cutter solidaire de la tête — celui que la butée du châssis enfonce — se
   déplace librement, actionne la lame et revient sans rester mou, coincé ou
   déboîté. En cas de dommage ou de doute, arrêt et réparation mécanique.
2. **Preuve capteur.** Pendant le moniteur longue durée, Thomas appuie environ
   deux secondes sur ce levier puis relâche. Codex doit observer exactement
   `cut_pos : 0→1→0`. Sans cette preuve, aucun mouvement cutter n'est permis.
3. **Retrait intégré unique.** Après capteur vert, Codex chauffe à la
   température de retrait approuvée, va à la position stock, exige `cut_pos=1`,
   reste en butée pendant toute la coupe et le retrait direct `T1A`, puis ne
   quitte le cutter qu'après libération. Les deux capteurs filament doivent
   devenir libres et les chauffes revenir à zéro. Thomas reste seulement près
   de l'arrêt d'urgence.
4. **Nettoyage manuel avant géométrie.** Après ce retrait, Thomas nettoie la
   buse. Cette confirmation fraîche est obligatoire parce que toute activité
   filament peut laisser un résidu. Elle autorise les références X/Y/Z de la
   prochaine impression ; aucune confirmation ancienne n'est réutilisable.
5. **Cycle complet deux couches.** Codex lance ensuite le G-code déjà préparé :
   références de contact sans filament, application du `11 × 11`, températures
   du G-code, chargement direct `T1A`, purge réelle dans le bac avec la quantité
   G-code, `3 à 4` allers-retours francs pour décrocher la boule, image caméra
   nette sans filament pendant sous la buse, ligne de purge hors zone utile,
   dégagement Z de `5 mm`, impression et surveillance de la première couche.
   Aucun nouveau palpage ne survient après le chargement.
6. **Fin complète.** À la fin des deux couches : dégagement, coupe au cutter
   avec maintien en butée, retrait complet, parc sûr, plateau descendu,
   chauffes zéro et moteurs libérés. Thomas confirme seulement l'absence de
   résidu ou intervient manuellement si la caméra reste ambiguë.
7. **Changement de couleur réel.** Une fois le cycle mono-filament vert,
   préparer deux routes explicitement mappées. Vérifier coupe, retrait,
   chargement, purge calculée par la matrice Orca, décrochage caméra et reprise
   au même contexte de température, sans homing, mesh ou palpage ajouté.
8. **Roulement de bobine vide.** En dernier, configurer une unique bobine spare
   strictement identique — matière, couleur, diamètre et recette thermique.
   Un runout réel doit sélectionner seulement ce spare, conserver les
   températures et la position de travail, exécuter la même purge/caméra puis
   reprendre. Zéro ou plusieurs correspondances doivent laisser l'impression
   en pause. La politique stock précédente est restaurée à la libération de
   K1 Control.

## 4. Vérifications et limites

- propriétaire direct installé : `5/5` tests ciblés et `16/16` scénarios ;
- propriétaire cutter/purge : `3/3` tests ciblés et `17/17` scénarios ;
- activation et moniteur manuel : `9/9` tests ciblés et `22/22` scénarios ;
- pose de l'interface : validation statique et indépendante OK, mais aucun
  bouton d'impression n'a encore été qualifié physiquement ;
- suite globale connue : `874` tests, `12` échecs, `2` erreurs et `3` ignorés.
  Les écarts concernent surtout d'anciens contrats/cartographies non réalignés
  et l'absence de `pytest` dans le Python système. Elle n'a pas été relancée
  pour cette passation documentaire ;
- production, autonomie complète, changement de couleur et roulement réel
  restent **non validés**.

## 5. Références et prochaine mission unique

Relire, dans cet ordre : ce handoff, `docs/49-pilotage-camera-simple-et-autonome-v1.md`,
`docs/adr/ADR-040-quantite-purge-gcode-et-garde-cutter-reel.md`, puis
`packages/k1-control-v1/stock-derived-cycle-activation-v1/RESULT.md`.

La prochaine mission unique est la qualification manuelle du capteur suivie,
si et seulement si elle est verte, du retrait intégré `T1A`. Le critère de fin
est : levier mécaniquement sain, transition `0→1→0` observée, coupe et retrait
réussis, deux capteurs filament libres, chauffes zéro, axes libérés, mesh et Z
inchangés. Les étapes purge/impression restent la continuation immédiatement
suivante, pas une autorité pour contourner un cutter KO.

Nouvelle tâche : non. Nouveau Goal, worktree ou branche de reprise : non. La
tâche source reste visible et non archivée.
