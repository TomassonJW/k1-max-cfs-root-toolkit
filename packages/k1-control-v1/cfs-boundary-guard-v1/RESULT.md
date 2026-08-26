# Résultat — CFS Boundary Guard V1

Date : 2026-08-26
Statut : **OK hors imprimante ; primitive stock observée KO ; production fermée**

## Verdict sur l'incident

`20260826-physical-cfs-insert-purge-v1` donne :

```text
verdict=block_driver_primitive
violations=nozzle_target_override,forbidden_geometry_command,homed_axes_changed
evidence_gaps=accepted_z_offset_mm,homing_origin_z_mm,mesh_profile
```

La cible plateau est restée à zéro dans la trace disponible. Les tests séparés
prouvent que toute autre cible plateau, toute commande plateau possédée par le
CFS et toute dérive Z/mesh ferment également la frontière.

## Validation locale

- 9 tests propres au garde sont verts ;
- 324 tests Python du dépôt sont verts ;
- 3 tests historiques restent ignorés ;
- `git diff --check` est vert ;
- aucune connexion K1 réussie pendant la préparation ;
- aucune chauffe, mouvement, purge, impression, écriture distante ou restart.

## Portée

Ce résultat autorise seulement l'analyse hors imprimante suivante. Il ne
qualifie aucune primitive CFS, n'autorise aucune pose et ne rouvre pas
`MESH-EDGE-DIAGNOSTIC-V1`.
