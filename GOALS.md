# GOALS — pilotage macro

Date de mise à jour : 2026-08-27

Ce fichier sert d'index rapide pour les grandes sessions de travail. Les noms
ci-dessous regroupent les petites gates déjà définies dans `GATES.md` ; ils ne
les remplacent pas et n'autorisent aucune action sur la K1 par eux-mêmes.

Aucun Goal Codex n'est actuellement créé ou lancé par ce document.

## Vue rapide

| Ordre | Grand Goal | État | Résultat concret attendu |
| --- | --- | --- | --- |
| 1 | `GOAL-P4-OFFLINE-CYCLE-CFS-V1` | prêt à lancer hors imprimante | système logiciel complet simulé et paquet réel préparé |
| 2 | `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` | prévu après Goal 1 | réponses et délais réels compris sans commande ni impression |
| 3 | `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1` | prévu, avec Thomas devant la K1 | fonctions physiques validées séparément avec retour arrière |
| 4 | `GOAL-P4-DAILY-CUTOVER-V1` | prévu après Goal 3 | fonctionnement quotidien unifié, ancien Orca retirable en une transaction |

## Goal 1 — Terminer le système hors imprimante

Identifiant : `GOAL-P4-OFFLINE-CYCLE-CFS-V1`

État : **prêt à lancer**.

Ce qui sera réellement fait :

- construire le transport simulé du garde CFS ;
- couvrir le démarrage, le bon ou mauvais filament, l'absence de filament, les
  changements, le runout, la pause, la reprise, l'annulation et la fin ;
- tester coupures, délais, faux succès et doubles commandes ;
- fixer les règles de nettoyage, de chauffe et d'arrêt thermique ;
- préparer les futurs fichiers d'installation, sauvegardes et retours arrière ;
- fermer les tests, la documentation et Git.

Limite : aucune connexion K1, aucun G-code réel, aucune chauffe, aucun mouvement
et aucun candidat de pose autorisé.

Première mission interne :
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-TRANSPORT-OFFLINE-V1`.

Fin attendue : le cycle complet fonctionne de façon déterministe sur des
réponses synthétiques ou enregistrées, et chaque future action réelle est
préparée mais reste fermée.

Autorité : `GO_DIRECT` uniquement dans le clavardage où `$session-tas` a été
explicitement invoqué ; sinon attendre une demande de lancement. Cette règle ne
donne aucune autorité sur l'imprimante.

## Goal 2 — Vérifier le système sur la vraie K1 sans impression

Identifiant : `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1`

État : **prévu après le Goal 1**.

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

> Terminer et intégrer tout le système hors imprimante du cycle d'impression et
> du garde CFS, depuis le transport simulé jusqu'à la préparation complète des
> futures étapes réelles, sans connexion K1, sans G-code réel et sans action
> physique.

Modèle conseillé : `gpt-5.6-terra`, raisonnement `high`. Option économique : le
même modèle en `medium`, avec plus de risque d'oublier un cas de délai, de
double commande ou de reprise après erreur.
