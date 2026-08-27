# GOALS — pilotage macro

Date de mise à jour : 2026-08-27

Ce fichier sert d'index rapide pour les grandes sessions de travail. Les noms
ci-dessous regroupent les petites gates déjà définies dans `GATES.md` ; ils ne
les remplacent pas et n'autorisent aucune action sur la K1 par eux-mêmes.

Ce document ne crée aucun Goal Codex. Les Goals 1 et 2 sont clos. La prochaine
mission est une activation runtime bornée du profil robuste avant le Goal 3.
Son paquet est préparé sous
`packages/k1-control-v1/robust-mesh-activation-v1`. Son préflight live en
lecture seule est vert et l'activation attend son GO exact.

## Vue rapide

| Ordre | Grand Goal | État | Résultat concret attendu |
| --- | --- | --- | --- |
| 1 | `GOAL-P4-OFFLINE-CYCLE-CFS-V1` | terminé hors imprimante | système logiciel complet simulé et plan futur inerte vérifié |
| 2 | `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` | terminé en lecture seule, suite bloquée par le mesh actif | réponses et délais réels qualifiés sans commande ni impression |
| 3 | `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1` | prévu, avec Thomas devant la K1 pour les tranches physiques ; attend le profil robuste actif | fonctions physiques validées séparément avec retour arrière |
| 4 | `GOAL-P4-DAILY-CUTOVER-V1` | prévu après Goal 3 | fonctionnement quotidien unifié, ancien Orca retirable en une transaction |

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

État : **terminé en lecture seule ; suite physique bloquée par la dérive du mesh actif**.

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

Résultat de la capture : `CLOSED_READ_ONLY_BLOCKED_MESH_DRIFT`. La K1 utilisait
alors le mesh `default`, dont la matrice différait du profil robuste
`k1_p001_t055_r001_n06x06`. Une lecture fraîche de fin de session montre
maintenant le composite `k1_p001_t055_r001_n11x11` actif. La cause de ce
changement intermédiaire n'est pas qualifiée. Le robuste existe encore mais
n'est toujours pas actif. Le paquet de lecture seule est clos ; aucun candidat
de pose ou connecteur de commande n'a été créé.

Autorité consommée : ce Goal est clos. Il ne donne aucune autorité pour charger
le profil robuste ni commencer le Goal 3.

## Goal 3 — Installer progressivement et qualifier les fonctions physiques

Identifiant : `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1`

État : **prévu ; présence humaine obligatoire pour les tranches physiques ;
bloqué jusqu'à une gate distincte qui vérifie et charge le profil robuste**.

Ce qui sera réellement fait, une petite tranche à la fois :

- installer avec sauvegarde et retour arrière ;
- qualifier le nettoyage et les mouvements sans collision ;
- qualifier un retrait unique et l'arrêt réel des chauffes ;
- vérifier changement de filament, runout, pause, reprise, annulation et fin ;
- reprendre le diagnostic des bords seulement après une route fraîche et une
  purge réellement visible ;
- tester le profil de précision sans remplacer le profil robuste quotidien.

Limite : chaque tranche conserve sa gate, ses critères OK/KO et son autorisation
exacte. Aucun retry automatique et aucune poursuite après un KO.

Fin attendue : toutes les fonctions physiques nécessaires sont validées
séparément et réversibles ; l'ancien démarrage Orca reste encore disponible.

## Goal 4 — Basculer vers le fonctionnement quotidien complet

Identifiant : `GOAL-P4-DAILY-CUTOVER-V1`

État : **prévu après le Goal 3**.

Ce qui sera réellement fait :

- réunir chauffe, nettoyage, filament, calibration, mesh et Z dans K1 Control ;
- faire envoyer à Orca une seule demande de démarrage ;
- retirer ensemble l'ancien départ Orca et le post-traitement `+0,27 mm` ;
- conserver le bon filament engagé en fin d'impression ;
- exposer le retrait par le bouton séparé `Désengager et nettoyer` ;
- prouver le retour complet à l'ancien fonctionnement.

Limite : cette bascule n'ouvre pas encore la production. Gate G5 reste
obligatoire.

Fin attendue : le fonctionnement quotidien est simple, unifié et réversible,
prêt pour la campagne finale de validation.

## Horizons après ces quatre Goals

- **P5 — validation production** : redémarrage à froid, trois impressions
  consécutives, deux CFS, changements de matériaux, Z conservé, pause/reprise,
  Orca et K1 Control sans intervention Codex, puis baseline V1 stable.
- **P6 — durcissement communautaire** : compatibilités, nettoyage automatique
  des données privées, documentation, licence et releases sans contenu
  propriétaire.

## Démarrage recommandé

Première gate à préparer avant le Goal 3 :

> Vérifier une dernière fois l'état sûr, charger uniquement
> `k1_p001_t055_r001_n06x06`, puis relire le profil et sa matrice sans lancer
> d'impression. Revenir immédiatement à l'état précédent au premier écart.

Cette gate runtime ne chauffe, ne référence et ne déplace pas la machine ; elle
ne nécessite donc pas Thomas devant la K1. Sa réussite ne lance pas le Goal 3.
La présence humaine redevient obligatoire avant la première tranche physique.

Identifiant exact de cette gate :
`G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1`. Le GO du grand Goal 3 ne remplace pas
le GO exact de cette mutation runtime, conformément aux gates séparées.

La première tranche physique suivante est désormais cadrée hors imprimante dans
`packages/k1-control-v1/clean-motion-v1` et le document 42. Elle ne contient
encore aucune commande. Une capture live en lecture seule a qualifié les limites
machine et la zone de nettoyage déclarée par le logiciel stock, sans exporter
son code complet. Thomas devra encore confirmer la brosse réelle, la visibilité
et chaque rapprochement à froid. Cette préparation ne contourne pas le verrou
d'activation du robuste.

Modèle conseillé : `gpt-5.6-terra`, raisonnement `high`. Option économique : le
même modèle en `medium`, avec davantage de risque de manquer une incohérence de
profil, de matrice ou de rollback sur du matériel réel.
