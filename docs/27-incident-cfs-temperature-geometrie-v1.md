# Incident CFS : température et géométrie V1

Date : 2026-08-26
Statut : audit hors imprimante clos ; séquence brute refusée ; production fermée

## Résultat

Le filament `CFS1 / slot A`, Geeetech PLA noir, a été engagé et une purge a été
visible. Cette preuve de débit est réelle. Elle ne valide pas la séquence qui
l'a obtenue.

La commande demandait `190 °C`, mais le firmware a imposé `220 °C`. Il a aussi
référencé X/Y alors que ce comportement n'était ni demandé ni sûr dans cette
phase. Le plateau n'avait pas été descendu : le mécanisme de purge arrière a
donc rencontré la zone du plateau et la matière a été déposée dessus. Thomas
n'a constaté aucun dommage visible.

Après récupération, le homing a été refait proprement et la position stock
`X=185,5 / Y=305 / Z=30 mm` a été contrôlée à froid. Thomas a confirmé que cette
hauteur suffit largement ; `60 mm` était inutilement conservateur.

## Ce qui est prouvé, et ce qui ne l'est pas

| Élément | Verdict |
|---|---|
| route physique `CFS1 / A` vers la buse | prouvée par la purge visible de ce passage |
| cible buse demandée | `190 °C` |
| cible buse cachée observée | `220 °C` |
| cible plateau pendant l'incident | restée à `0 °C` dans la trace disponible |
| homing interne | X/Y observé |
| hauteur de purge sûre | `Z=30 mm`, confirmée à froid par Thomas |
| dommage matériel | aucun dommage visible selon Thomas |
| Z accepté/mesh pendant la frontière fautive | non qualifié fraîchement |

La dernière ligne est volontairement prudente. Le Z persistant `−0,04 mm` et le
profil robuste ont été retrouvés dans l'état sûr ultérieur, mais cela ne prouve
pas chaque état transitoire du passage fautif.

## Cause

La séquence a utilisé des primitives CFS de bas niveau hors de leur contexte
stock complet. Le fichier exact `box.cfg` fixe `Tn_extrude_temp: 220` et réserve
`extrude_pos_z: 30.0`. Le macro de chargement complet ajoute homing,
positionnement, nettoyage et restauration autour des primitives filament.

Le problème n'est donc pas seulement un oubli de descendre le plateau. Le même
appel mélange trois propriétaires : filament, température et géométrie. Tant que
ces responsabilités ne sont pas séparées, un passage peut réussir à purger tout
en restant dangereux ou thermiquement faux.

## Décision opérationnelle

- ne pas rejouer la séquence brute du 26 août ;
- ne pas corriger seulement `220 °C` après coup ;
- protéger ensemble buse, plateau, Z accepté, origine Z, mesh et homing ;
- déplacer la K1 vers la purge sous le contrôle du pilote de mouvement, avant
  toute primitive CFS ;
- considérer le cœur compilé comme non fiable jusqu'à qualification de chaque
  primitive ;
- garder la K1 froide et immobile jusqu'au paquet exact suivant.

Le prototype hors imprimante se trouve dans
`packages/k1-control-v1/cfs-boundary-guard-v1/`. Son verdict sur la trace de
l'incident est `block_driver_primitive`.
