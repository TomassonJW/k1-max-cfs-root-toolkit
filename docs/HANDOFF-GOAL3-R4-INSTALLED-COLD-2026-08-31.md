# Handoff — Goal 3, R4 installé et validé à froid

Date : 2026-08-31
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Capture privée :
`inventory/raw/20260831-000831-g4-k1-control-start-sequence-owner-preinsert-geometry-r4/`

## Résultat

R4 est installé sur la K1 avec l'empreinte exacte
`c7d7dd06ee81092d73cde9e41ba371642340e8f0270154f3cef15e0e98ef9d4e`.

Le premier préflight s'est fermé avant effet parce que le déployeur attendait
encore la V1. Une lecture unique a montré la R2 installée exacte
`678582e8…`, sans dérive distante. Le correctif `bccf344` a épinglé cette vraie
source de backup et de rollback, puis le préflight corrigé est passé.

La pose a ensuite :

- sauvegardé et revérifié la R2 exacte ;
- remplacé un seul fichier de macros ;
- observé une vraie transition du socket Klipper ;
- remis une fois `k1_p001_t055_r001_n11x11` ;
- validé puis réinitialisé le surveillant à froid ;
- confirmé l'empreinte R4 par une lecture indépendante.

Le rollback n'a pas été utilisé. Aucun chauffage, mouvement, ordre CFS,
extrusion ou travail n'a été lancé.

## État final réel

- Klipper prêt, impression `standby`, zéro avertissement ;
- cibles buse et plateau à zéro ;
- axes libérés ;
- `11 × 11` actif ;
- Z accepté `−0,04 mm` ;
- propriétaire `idle`, surveillant désarmé, jetons à zéro ;
- deux CFS connectés, commande vide, aucune route logique engagée.

Avant le restart, `T1A` était engagé. Le restart n'a commandé aucun mouvement de
filament, mais la route logique est désormais vide. La télémétrie ne peut donc
pas prouver où se trouve physiquement le filament. Ne pas lancer de palpation ni
utiliser le chemin de réutilisation tant que cet état n'est pas résolu.

## Prochaine action unique

Préparer puis exécuter le premier run court R4. Il doit traiter la reprise comme
un seul enchaînement, sans recréer de micro-gates :

1. Thomas utilise l'interface officielle pour retrouver puis retirer réellement
   le filament si nécessaire ;
2. Thomas nettoie la buse ;
3. Codex vérifie l'état vide, chauffe et termine toute géométrie de contact ;
4. Thomas insère `T1A` avec la fonction officielle ;
5. Codex pilote la purge dans le bac, E4, les deux contrôles caméra et une
   première couche courte ;
6. au premier doute, Codex annule, coupe les chauffes et ne rejoue rien.

Cette pose n'autorise pas ce run chaud. Le Goal 3 reste à `2/7`.

Modèle conseillé pour le run : `gpt-5.6-sol` en raisonnement `high`, car il faut
croiser l'état CFS, le mouvement réel, deux images caméra et la première couche.
Option économique acceptable : `gpt-5.6-terra` en `high`, avec plus de risque de
reprise si les preuves physiques sont ambiguës.

La tâche source reste visible et ne doit pas être archivée.
