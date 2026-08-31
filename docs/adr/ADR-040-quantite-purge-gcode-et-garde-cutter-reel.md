# ADR-040 — Quantité de purge G-code et garde cutter réel

Date : 2026-09-01

Statut : **acceptée ; correctifs installés ; cycle physique bloqué sur le cutter**

## Contexte

La reprise locale après `EXTRUDE_ERR8` n'avait poussé que `30 mm`. Elle a produit
un petit filet, insuffisant pour former une boule de purge et permettre son
décrochage dans le bac. Cette reprise n'était pas la purge stock du cycle.

Les traces réelles montrent deux sources de quantité distinctes :

- un chargement initial stock pousse `140 mm` de filament ;
- un changement de couleur utilise la matrice volumique Orca du G-code. Pour le
  petit G-code stock-derived courant, elle correspond à `266,081080 mm` de
  l'outil 0 vers l'outil 1 et `126,804265 mm` dans l'autre sens. Une ancienne
  trace de production contient aussi une transition à `318,465793 mm`.

Le premier cycle réel a ensuite exposé trois écarts avant impression :

1. le garde X/Y exigeait à tort la disparition de `T1A` avant la coupe ;
2. le ticket demandait une réconciliation alors que le propriétaire direct
   possédait déjà `T1A` en phase `loaded` ;
3. l'approche cutter stock `X38 Y304,5` n'a pas déclenché `cut_pos` sur la
   machine actuelle.

Les deux premiers écarts ont été corrigés et testés. Pour le troisième, un
pilote borné a testé la position stock puis `Y305,0`, avant qu'une lecture des
limites réelles révèle `position_max Y=307,5`. La révision suivante a avancé
lentement par pas de `0,5 mm` jusqu'à `Y307,5`. `cut_pos` est resté à `0` à
chaque position. Aucune commande de retrait n'a donc été envoyée.

## Décision

1. La purge initiale vient d'abord du vecteur `flush_volumes_vector` du G-code.
   Si ce vecteur est absent, le repli qualifié vaut exactement `140 mm`.
2. Les volumes de transition Orca sont convertis en longueur avec le diamètre
   de filament déclaré. La limite technique du propriétaire passe à `400 mm`.
3. Un changement de matière ou de couleur reste refusé tant que la
   correspondance exacte outil G-code vers route CFS n'est pas résolue. Une
   purge générique ne remplace pas cette correspondance.
4. Une route déjà possédée en phase `loaded` va directement à la coupe ; aucune
   réconciliation n'est envoyée. Une route seulement déduite des deux capteurs
   conserve la réconciliation obligatoire.
5. Le retrait reste interdit tant que `cut_pos` n'a pas réellement basculé à
   `1`. La tête doit rester en appui pendant toute la rétraction, puis la
   libération doit ramener `cut_pos` à `0`.
6. Après l'échec à la limite Y publiée par la machine, aucun dépassement et
   aucun retry automatique ne sont permis. Une vérification mécanique du
   levier, du cutter et de son capteur est obligatoire avant reprise.

## Conséquences

- Le correctif purge est installé sous
  `20260901-g4-k1-control-stock-purge-profile-hotfix-v1`.
- Le garde de conservation de route est installé sous
  `20260901-g4-k1-control-stock-cutter-route-guard-hotfix-v1`.
- La distinction route possédée/réconciliation est installée sous
  `20260901-g4-k1-control-stock-preclean-owned-route-hotfix-v1`.
- Les scénarios hors imprimante passent à `22/22` pour l'activation et `17/17`
  pour le propriétaire Klipper.
- Le cycle réel reste bloqué avant coupe. L'état final confirmé est : `T1A`
  chargé, deux capteurs filament actifs, chauffes à zéro, axes libérés, mesh
  `11 × 11` actif et Z accepté `−0,04 mm`.
- Aucune palpation, recalibration de mesh ou rétraction filament n'a eu lieu
  pendant les essais cutter refusés.

## Alternatives refusées

- **Multiplier arbitrairement les `30 mm`** : ignore la quantité stock et la
  matrice de couleur du G-code.
- **Réconcilier systématiquement** : place à tort un propriétaire déjà chargé
  en échec `phase_invalid`.
- **Retirer malgré `cut_pos=0`** : peut casser ou arracher le filament dans la
  tête.
- **Dépasser `Y307,5`** : sort de l'enveloppe publiée par la machine et risque
  une contrainte mécanique sans preuve.

## Preuves liées

- trace stock initiale :
  `inventory/raw/g3-production/p123-20260820-154056/20260820-154056-p123.raw.txt` ;
- G-code courant :
  `packages/k1-control-v1/stock-derived-cycle-activation-v1/K1-STOCK-DERIVED-T1A-2LAYER.gcode` ;
- capture caméra après refus :
  `inventory/raw/20260901-g4-k1-control-stock-cycle-physical-v1/cutter-refusal-after-y3045.jpg` ;
- pilote borné :
  `packages/k1-control-v1/stock-derived-cycle-activation-v1/remote_cutter_reach_recovery.py` ;
- invariants physiques : ADR-034 et ADR-037.
