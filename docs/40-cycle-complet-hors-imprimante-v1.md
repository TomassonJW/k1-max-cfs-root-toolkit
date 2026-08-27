# Cycle complet K1 Control hors imprimante V1

Date : 2026-08-27

Grand Goal : `GOAL-P4-OFFLINE-CYCLE-CFS-V1`

Verdict : **Goal 1 clos OK ; système local complet ; aucune K1 touchée**.

## Résultat concret

Le contrat figé du cycle est maintenant une machine d'états exécutable. Elle
enchaîne admission, classification du filament, chauffe plateau, référence
grossière, nettoyage, référence finale, chargement mesh/Z, décision filament,
purge, amorçage, impression simulée et fin sûre.

Les branches séparées couvrent :

- bon filament conservé ;
- mauvais filament retiré puis remplacé ;
- filament absent chargé ;
- identité inconnue ou capteurs contradictoires bloqués avant chauffe et
  mouvement ;
- changement volontaire de couleur ou de matière ;
- passage entre les deux CFS ;
- runout équivalent sans changement caché de cible ;
- pause normale sans CFS ;
- reprise simple ou réamorçage volontaire ;
- annulation et reboot sans rejouer le cycle ;
- fin avec filament conservé ;
- action séparée `Désengager et nettoyer` via le garde simulé.

## Sécurité exécutée dans le modèle

Chaque frontière CFS demande une route fraîche, une cible explicite avant
effet, un identifiant unique, un délai, une preuve de fin et l'absence de
commande thermique ou géométrique cachée. Les routes et identifiants ne sont
pas réutilisables.

Un débit non prouvé, une trajectoire arrière bloquée, un timeout, une route
périmée, un doublon ou une réécriture tardive à `220 °C` mène à l'arrêt sûr :
cibles zéro, reprise fermée, aucun retry.

Une reconnexion CFS invalide immédiatement la route et l'identité en cours,
efface les preuves de débit et d'amorçage, puis exige une reprise explicite.

Le nettoyage utilise une recette matière explicite, un plan de brosse calibré
humainement et aucun palpage de la brosse. Le vert local ne prétend pas que ce
plan ou ces mouvements sont physiquement qualifiés.

## Preuves locales

- transport du garde : `13/13` scénarios ;
- cycle complet : `27/27` scénarios canoniques ;
- tests ciblés du cycle : `20/20` après ajout du plan futur ;
- suite complète : `476` exécutés, `473` verts et `3` ignorés connus ;
- sources du futur cœur compatibles avec la grammaire Python `3.8` ;
- trois sources futures épinglées ;
- futur périmètre de fichiers : trois chemins ;
- futures tranches physiques : sept, toutes avec présence humaine ;
- commandes distantes, G-code et actions de service dans le plan : zéro.

## Plan futur inerte

`future-deployment-blueprint.json` fixe les sources, destinations prévues,
sauvegardes, empreintes, rollback et ordre des futures tranches. Il ne contient
aucun connecteur réel, aucune commande distante, aucun script de pose et aucune
modification Orca.

## Ce qui reste réellement à faire

Le Goal 2 a comparé ce modèle à une lecture K1 fraîche, sans effet. La lecture,
les délais et les empreintes sont qualifiés, mais le mesh actif `default`
diffère du profil robuste requis. Une gate humaine distincte devra d'abord
charger et vérifier ce profil. Les Goals suivants qualifieront ensuite, une
petite tranche à la fois, géométrie, nettoyage, débit, retrait, changements,
pause/reprise et fin. La production et le mode Précision restent fermés.
