# Préflight propriétaire CFS S12 V1

Date : 2026-08-28

Statut : **clos en lecture seule ; surface S12 confirmée ; tous les effets et la
production restent fermés**

Mise à jour : le successeur hors imprimante
`G4-K1-CONTROL-CFS-OWNER-CORE-OFFLINE-V1` est désormais clos avec `21/21`
scénarios. Voir le document 45. La prochaine mission proposée est le garde
d'exclusion stock hors imprimante ; cette note ne modifie pas la preuve live du
présent préflight.

## Résultat en langage courant

Nous n'avons pas remplacé le firmware et nous n'avons rien fait bouger. Une
seule connexion SSH a lu l'état public de Moonraker, les empreintes et les noms
utiles du binaire CFS déjà installé. Les numéros de série et identifiants RFID
ont été retirés sur la K1 avant que la réponse revienne sur le PC.

La K1 était au repos, chauffes à zéro, deux CFS connectés, aucune commande CFS
active et le `11 × 11` sélectionné. Les fichiers sont restés strictement
identiques entre le début et la fin de la collecte.

## Ce qui est maintenant certain sur cette S12

- le chargeur `box.py`, son bytecode et le binaire `box_wrapper` correspondent
  exactement aux empreintes déjà capturées ;
- l'objet Moonraker `box` est réellement actif ;
- les 11 noms nécessaires à notre carte sont présents dans le binaire exact :
  chargement côté CFS, prise côté extrudeur, coupe, retrait, contrôle de
  l'auto-remplacement, reconstruction des groupes identiques, gestion de fin de
  bobine, retry, fin d'impression et reprise après coupure ;
- les 13 rappels internes attendus sont présents, notamment
  `material_auto_refill`, `filament_err_tighten_up_event`,
  `filament_err_retry_process`, `power_loss_clean`, `power_loss_restore`,
  `box_end` et `update_Tnn_map` ;
- les signatures publiques épinglées concordent avec les noms et mots-clés du
  binaire exact, sans transformer cette concordance en validation physique ;
- la configuration active garde `Tn_extrude_temp: 220` et ses propres positions
  de coupe, chargement, sécurité et nettoyage ;
- le même binaire contient des chemins capables de lancer `G28`, `M104`, `M109`,
  `BED_MESH_CLEAR`, `PAUSE` et `RESUME`.

Ces derniers points confirment le choix d'ADR-032 : nous pouvons réutiliser les
petites primitives matérielles, mais nous ne devons pas laisser les grosses
séquences stock décider de la chauffe, du Z, du mesh, de la purge ou de la
reprise.

## Limite de l'aide Klipper

`GET /printer/gcode/help` ne liste que les commandes enregistrées avec un texte
d'aide. Sur cette K1, il expose cinq macros CFS haut niveau mais pas les commandes
compilées plus basses. L'absence dans cette liste ne prouve donc pas l'absence
d'une commande. La preuve retenue est l'ensemble cohérent suivant : objet `box`
actif, chargeur exact, binaire exact, nom présent dans ce binaire et preuves
historiques déjà conservées pour les chemins réellement observés.

## Auto-remplacement de bobine

La fonction reste dans le projet. La surface S12 fournit bien l'état courant,
les groupes de matière identique, les capteurs par CFS, le contrôle du drapeau
stock et les rappels de fin de bobine. Notre propriétaire pourra donc désactiver
le propriétaire stock pendant un travail, choisir lui-même une bobine de même
référence approuvée, charger une seule fois puis reprendre sans homing ni
recalibration.

La capture ne contenait toutefois aucune paire stock reconnue comme identique :
les groupes `T1A`, `T1D`, `T2A`, `T2B`, `T2C` et `T2D` étaient six groupes
séparés. Cela ne bloque pas le développement, mais un futur essai de fin de
bobine devra d'abord vérifier que les deux emplacements choisis portent bien la
même référence approuvée et sont vus comme disponibles.

## Ce que cette gate n'autorise pas

Aucune commande CFS n'a été envoyée. Aucun G-code, chauffage, mouvement,
fichier distant, journal ou redémarrage n'a été utilisé. Aucun chargement,
retrait, cutter, purge, runout, retry, reprise ou fin d'impression n'est qualifié.

À la clôture de ce préflight, la mission proposée était
`G4-K1-CONTROL-CFS-OWNER-CORE-OFFLINE-V1`. Elle a depuis construit le moteur
hors imprimante contre la réponse enregistrée et les cartes publiques épinglées,
sans autorité de pose ou d'effet physique. L'étape courante se trouve dans le
document 45 et dans `HANDOFF.md`.
