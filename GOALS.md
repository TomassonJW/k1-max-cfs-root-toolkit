# GOALS — pilotage macro

Date de mise à jour : 2026-08-27

Ce fichier sert d'index rapide pour les grandes sessions de travail. Les noms
ci-dessous regroupent les petites gates déjà définies dans `GATES.md` ; ils ne
les remplacent pas et n'autorisent aucune action sur la K1 par eux-mêmes.

Ce document ne crée aucun Goal Codex. Le Goal 1 est clos ; le Goal 2 reste à
lancer sous une autorité de connexion en lecture seule séparée.

## Vue rapide

| Ordre | Grand Goal | État | Résultat concret attendu |
| --- | --- | --- | --- |
| 1 | `GOAL-P4-OFFLINE-CYCLE-CFS-V1` | terminé hors imprimante | système logiciel complet simulé et plan futur inerte vérifié |
| 2 | `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` | prêt sous autorité séparée | réponses et délais réels compris sans commande ni impression |
| 3 | `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1` | prévu, avec Thomas devant la K1 | fonctions physiques validées séparément avec retour arrière |
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

État : **prêt à lancer sous une autorité séparée**.

Ce qui sera réellement fait :

- lire les états, réponses, délais et erreurs réels ;
- vérifier que le nettoyage des identités et la traduction restent exacts ;
- comparer le comportement réel au système simulé ;
- préparer les commandes exactes et leur retour arrière sans les envoyer ;
- arrêter la session sur toute donnée nouvelle ou ambiguë.

Limite : aucune impression, aucun G-code, aucun retrait, aucune chauffe, aucun
mouvement et aucun fichier distant.

Fin attendue : un paquet réel entièrement revu est prêt pour une future
qualification physique, sans avoir produit d'effet sur la K1.

Autorité : une connexion K1 exigera une autorisation explicite propre à la gate
alors préparée.

## Goal 3 — Installer progressivement et qualifier les fonctions physiques

Identifiant : `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1`

État : **prévu ; présence humaine obligatoire**.

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

Objectif à utiliser pour le prochain grand Goal :

> Comparer le système hors imprimante à un état K1 frais en lecture seule,
> comprendre les formes, erreurs et délais réels, puis préparer les futures
> commandes sans en envoyer aucune et sans modifier la machine.

Modèle conseillé : `gpt-5.6-terra`, raisonnement `high`. Option économique : le
même modèle en `medium`, avec plus de risque de manquer une dérive de forme, de
délai ou d'état avant les futures qualifications physiques.
