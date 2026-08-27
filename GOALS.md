# GOALS — pilotage macro

Date de mise à jour : 2026-08-27

Ce fichier sert d'index rapide pour les grandes sessions de travail. Les noms
ci-dessous regroupent les petites gates déjà définies dans `GATES.md` ; ils ne
les remplacent pas et n'autorisent aucune action sur la K1 par eux-mêmes.

Ce document ne crée aucun Goal Codex. Le compteur canonique reste fermé à
**quatre Goals pour terminer le projet** : aucun cinquième Goal obligatoire ne
sera ajouté. Les Goals 1 et 2 sont clos. ADR-029
établit qu'aucun profil actuel n'est robuste : tous ont des défauts de bord. Le
`11 × 11`, meilleur profil observé, est actif et revérifié. Le checkpoint D1 du
Goal 3 est techniquement vert et attend le verdict visuel de Thomas. D2 reste
verrouillé.

## Vue rapide

| Ordre | Grand Goal | État | Résultat concret attendu |
| --- | --- | --- | --- |
| 1 | `GOAL-P4-OFFLINE-CYCLE-CFS-V1` | terminé hors imprimante | système logiciel complet simulé et plan futur inerte vérifié |
| 2 | `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` | terminé en lecture seule ; écart de mesh alors observé, corrigé par une gate distincte | réponses et délais réels qualifiés sans commande ni impression |
| 3 | `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1` | en cours ; D1 CLEAN-MOTION techniquement vert, verdict humain attendu | toutes les fonctions physiques et le profil de bord validés séparément |
| 4 | `GOAL-P4-DAILY-CUTOVER-V1` | prévu après Goal 3 | bascule unifiée, validation production et clôture définitive du projet |

Le registre exécutable
`packages/k1-control-v1/physical-slices-qualification-v1/completion-matrix.json`
fige exactement les sept exigences internes du Goal 3. Il indique actuellement
`0/7` exigences closes : D1 est techniquement vert mais CLEAN-MOTION reste en
cours jusqu'au verdict humain et à la fin de sa trajectoire. Ce registre ne
crée aucun Goal supplémentaire.

## Goal 1 — Terminer le système hors imprimante

Identifiant : `GOAL-P4-OFFLINE-CYCLE-CFS-V1`

État : **terminé hors imprimante**.

Ce qui a été réellement fait :

- construire le transport simulé du garde CFS ;
- couvrir le démarrage, le bon ou mauvais filament, l'absence de filament, les
  changements, le runout, la pause, la reprise, l'annulation et la fin ;
- tester coupures, délais, faux succès et doubles commandes ;
- fixer les règles de nettoyage, de chauffe et d'arrêt thermique ;
- préparer les futurs fichiers d'installation, sauvegardes et retours arrière ;
- fermer les tests, la documentation et Git.

Limite respectée : aucune connexion K1, aucun G-code réel, aucune chauffe, aucun
mouvement et aucun candidat de pose exécutable.

Première mission interne close :
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-TRANSPORT-OFFLINE-V1`, `13/13` scénarios.

Résultat : les `27/27` scénarios canoniques sont verts, les tests ciblés du cycle
obtiennent `20/20` et le plan futur épingle trois sources, trois destinations,
les sauvegardes et le rollback sans contenir de commande distante. La suite
complète exécute `476` tests, dont `473` verts et `3` ignorés connus.

Autorité consommée : ce Goal est clos. Il ne donne aucune autorité sur
l'imprimante ni sur le Goal 2.

## Goal 2 — Vérifier le système sur la vraie K1 sans impression

Identifiant : `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1`

État : **terminé en lecture seule ; l'écart de mesh alors observé est clos par
une gate distincte**.

Ce qui a été réellement fait :

- deux lectures fraîches, nettoyées sur la K1 avant leur retour local ;
- forme de réponse stable et plafond de lecture fermé à `5 s` ;
- lectures d'état mesurées à `199,212 ms` et `235,525 ms` ;
- deux CFS connectés, aucune route engagée, commande vide, chauffes à zéro ;
- Z accepté à `−0,04 mm`, mouvements bas désarmés et configurations exactes ;
- collecteur `GET`, traduction pure et règle d'invalidation du mapping testés ;
- points d'intégration Moonraker préparés sans ajouter de composant.

Vérifications : `32/32` tests ciblés Goal 2 et cycle, puis `488` tests dans la
suite complète dont `485` verts et `3` ignorés connus ; `29/29` scripts
PowerShell relus sans erreur.

Limite : aucune impression, aucun G-code, aucun retrait, aucune chauffe, aucun
mouvement, aucun fichier distant, aucun restart et aucune reconnexion CFS
provoquée.

Résultat historique de la capture : `CLOSED_READ_ONLY_BLOCKED_MESH_DRIFT`. La
K1 utilisait
alors le mesh `default`, dont la matrice différait du profil quotidien
`k1_p001_t055_r001_n06x06`. Une lecture fraîche de fin de session montre
ensuite le composite `k1_p001_t055_r001_n11x11` actif. La cause de ce
changement intermédiaire n'est pas qualifiée. Une gate a chargé à tort le
`6 × 6` sous l'ancienne nomenclature, puis
`G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-V1` a remis et revérifié le meilleur
profil actuel `11 × 11`. Le paquet de
lecture seule reste clos ; aucun candidat de pose ou connecteur de commande n'a
été créé dans le Goal 2.

Autorité consommée : ce Goal est clos. Il ne donnait par lui-même aucune
autorité pour changer le profil actif ni commencer le Goal 3 ; ces actions
ont depuis reçu leur autorité distincte.

## Goal 3 — Installer progressivement et qualifier les fonctions physiques

Identifiant : `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1`

État : **en cours ; checkpoint D1 de CLEAN-MOTION techniquement vert ; verdict
visuel de Thomas attendu ; D2 non lancé ; meilleur profil actuel `11 × 11`
actif**.

Le checkpoint C a référencé XYZ, rechargé le `11 × 11`, commandé `Z=50 mm` et
attendu la fin. Un premier faux KO local a confondu la position physique
compensée `50,23 mm` avec la consigne. Aucun mouvement n'a été rejoué ; la
validation corrigée en lecture seule est verte. Thomas a donné
`CHECKPOINT C OK`. Ce checkpoint ne doit pas être rejoué.

D1 a ensuite déplacé une seule fois la tête à froid jusqu'à
`X81 Y280 Z50`, encore `24,5 mm` avant la zone stock déclarée. La machine est
restée froide, au repos, sans route CFS, configurations inchangées et profil
`11 × 11` actif. D1 ne doit pas être rejoué. D2 reste interdit jusqu'au verdict
visuel positif de Thomas sur l'absence de bruit, contact, obstacle ou perte de
visibilité.

Ce qui sera réellement fait, une petite tranche à la fois :

- installer avec sauvegarde et retour arrière ;
- qualifier le nettoyage et les mouvements sans collision ;
- qualifier un retrait unique et l'arrêt réel des chauffes ;
- vérifier changement de filament, runout, pause, reprise, annulation et fin ;
- reprendre le diagnostic des bords seulement après une route fraîche et une
  purge réellement visible ;
- corriger les bords point par point depuis la source `11 × 11`, puis tester un
  candidat dérivé sans écraser les profils existants.

Limite : chaque tranche conserve sa gate, ses critères OK/KO et son autorisation
exacte. Aucun retry automatique et aucune poursuite après un KO.

Fin attendue : toutes les fonctions physiques nécessaires sont validées
séparément et réversibles ; l'ancien démarrage Orca reste encore disponible.
La clôture exige les sept lignes `PASSED` et un audit transversal conforme au
registre ; un test logiciel ne peut jamais remplacer une observation physique.

## Goal 4 — Basculer, valider la production et clôturer définitivement

Identifiant : `GOAL-P4-DAILY-CUTOVER-V1`

État : **prévu après le Goal 3**.

Ce qui sera réellement fait :

- réunir chauffe, nettoyage, filament, calibration, mesh et Z dans K1 Control ;
- faire envoyer à Orca une seule demande de démarrage ;
- retirer ensemble l'ancien départ Orca et le post-traitement `+0,27 mm` ;
- conserver le bon filament engagé en fin d'impression ;
- exposer le retrait par le bouton séparé `Désengager et nettoyer` ;
- prouver le retour complet à l'ancien fonctionnement ;
- redémarrer à froid et exécuter trois impressions consécutives représentatives ;
- exercer les deux CFS, un changement de filament et les reprises intégrées ;
- confirmer la conservation du Z, du mesh et des configurations après reboot ;
- vérifier Orca et K1 Control sans correction manuelle ni intervention Codex ;
- fermer la documentation, les données privées, Git et la baseline V1.

La validation production auparavant repoussée en P5 fait désormais partie de
ce Goal 4. Elle ne crée donc plus un cinquième Goal caché.

Fin attendue : fonctionnement quotidien simple, unifié, réversible et validé en
production. Quand ce Goal passe, le projet est **terminé** et aucune gate
obligatoire ne reste ouverte.

## Après les quatre Goals

Il n'existe plus de phase obligatoire P5 ou P6 après le Goal 4. Les éventuelles
compatibilités communautaires ou améliorations futures deviennent un backlog
optionnel, extérieur à la définition de fin du projet. Elles ne peuvent pas
repousser la clôture.

## Démarrage recommandé

La nomenclature de cette ancienne gate est obsolète. La correction
`G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-V1` est close OK : une seule commande
a remis `k1_p001_t055_r001_n11x11`, aucun rollback n'a été nécessaire et deux
lectures indépendantes ont confirmé le profil et sa matrice.

La première tranche physique est cadrée dans
`packages/k1-control-v1/clean-motion-v1` et le document 42. Une capture live en
lecture seule a qualifié les limites machine et la zone de nettoyage déclarée
par le logiciel stock, sans exporter son code complet. Thomas a confirmé le
plateau libre, la brosse visible, la buse observable et l'arrêt immédiat
possible. Le checkpoint C a été exécuté une fois, sa validation technique
corrigée est verte et Thomas l'a accepté. Aucun mouvement ne doit être rejoué ;
le prochain incrément est un rapprochement lent distinct.

La présence humaine est acquise pour le démarrage, mais chaque rapprochement
reste un checkpoint humain. `gpt-5.6-terra` avec raisonnement `high` est
conseillé pour piloter les arrêts et les preuves ; l'option `medium` est moins
coûteuse mais augmente le risque de reprise si un checkpoint physique est mal
interprété.
