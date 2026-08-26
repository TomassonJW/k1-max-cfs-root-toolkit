# Résultat — CFS-READ-ONLY-AUDIT-V1

Date : 2026-08-26
Capture privée canonique : `20260826-final-cfs-read-only-audit-v1`

## Verdict

Audit en lecture seule : **OK**.
Préflight d'une future purge : **bloqué en sécurité**.
État filament courant : **`engaged_unknown`**.

La K1 observe une présence sur `filament_sensor`, mais ne publie actuellement
aucun outil logique actif, aucune route CFS/slot active et aucune preuve de
débit à la buse. `box.t_command` est vide. Le fichier persistant courant
`tn_data.json` contient l'inventaire des slots, mais ni `tnn_map`, ni
`last_cmd`, ni `last_tnn` exploitable.

## Faits exacts

- `filament_switch_sensor filament_sensor` : activé, présence vraie, broche
  `!PC15` ; son emplacement physique exact n'est pas démontré.
- `filament_switch_sensor filament_sensor_2` : désactivé, présence fausse,
  broche `^!nozzle_mcu:PA10` ; `box.cfg` le référence comme capteur du composant
  `box`, sans démontrer son emplacement physique exact.
- les CFS `T1` et `T2` sont connectés ; les lettres `A..D` désignent leurs
  slots dans les données observées ;
- l'historique prouve qu'un outil logique peut être remappé vers un autre slot
  physique, donc un nom comme `T1A` n'est pas une route physique immuable ;
- les fichiers persistants de matériau décrivent les slots, mais pas le
  filament actuellement engagé jusqu'à la buse ;
- présence, identité, route et débit sont quatre preuves distinctes.

## État final relu

- `standby`, aucune impression active ;
- cibles buse et plateau à zéro ;
- axes non référencés ;
- profil robuste `k1_p001_t055_r001_n06x06` actif ;
- Z accepté `−0,04 mm`, stockage `ok`, mouvements bas désarmés ;
- deux CFS connectés ;
- empreintes des cinq fichiers surveillés identiques avant et après l'audit.

## Conséquence

Aucun `T0`, outil, CFS ou slot ne peut être choisi par défaut. La reprise
physique de `MESH-EDGE-DIAGNOSTIC-V1` reste suspendue jusqu'à une résolution
fraîche et explicite de la route, puis une petite purge réellement visible sous
une autorisation distincte.
