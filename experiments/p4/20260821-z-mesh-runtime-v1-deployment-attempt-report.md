# Essai réel `G4-K1-CONTROL-Z-MESH-RUNTIME-V1`

Date : 2026-08-21

Capture privée : `20260821-213732-g4-k1-control-z-mesh-runtime-v1`

## Résultat

Le GO exact renouvelé a ouvert la pose corrigée. Le préflight immédiat était
vert : machine `standby`, chauffes à zéro, empreinte initiale exacte, runtime
absent, fondation intacte et deux CFS connectés en `1.1.3`.

Le déployeur a vérifié le backup, posé les deux fichiers et l'include, puis
exécuté le `RESTART` hôte Klipper prévu. La première validation runtime a refusé
l'état neuf avec `Etat initial K1 Control non ferme`. La garde
`K1_PRODUCTION_ASSERT_ARMED` n'a donc pas été appelée.

Le rollback automatique a retiré le fichier runtime, son module, l'include et
l'état persistant, puis a relancé Klipper. Sa validation immédiate a cependant
rencontré T1 encore déconnecté pendant la reconnexion. Le restart avait aussi
normalisé uniquement les espaces des blocs générés `bed_mesh default` et
`auto_addr`, ce qui changeait l'empreinte textuelle de `printer.cfg` sans changer
ses valeurs.

Le diagnostic en lecture seule a confirmé l'absence des trois cibles runtime et
une différence limitée à ces espaces. La complétion bornée du rollback a alors
restauré une dernière fois le backup exact, sans nouveau restart. Le préflight
final est vert :

- `printer.cfg` revenu à
  `272640237e20659cf01f3268ed4cb0282b098c3d613e94bf84a3b80caac3c3b0` ;
- runtime absent sur disque et dans Klipper ;
- Klipper `standby`, axes non référencés, chauffes à zéro ;
- T1 et T2 reconnectés en `1.1.3` ;
- fondation V3 + PATHS-V1 intacte.

Aucun mouvement, homing, chauffage, extrusion, ordre CFS, calibration,
impression, firmware restart ou reboot imprimante n'a été exécuté. Les deux
restarts hôte Klipper prévus par la pose et son rollback ont effacé le mesh
transitoire actif `Base` ; le profil persistant `default` est de nouveau actif.
Les backups et preuves de la capture restent sur les chemins privés prévus.

## Cause et correction hors imprimante

Un stockage neuf rapporte `integrity=empty`. Le macro traitait cet état comme un
enregistrement invalide et gardait `ready=0`, ce qui bloquait aussi le démarrage
d'une calibration. La branche `empty` donne maintenant `ready=1` uniquement au
sous-système de calibration, tout en conservant `accepted_z_valid=0`,
`low_moves_armed=0` et `block_reason=no_accepted_z`.

Le déployeur attend maintenant jusqu'à 60 secondes la stabilisation complète de
Klipper et des deux CFS. Pendant un rollback, il attend d'abord que le runtime
soit réellement déchargé, puis restaure de nouveau le backup exact après le
restart et vérifie enfin l'état physique et la fondation.

Le nouveau fichier runtime a pour SHA-256
`3b0e5215d9bd58a343c57a681668ef1e466465980cceac3b1fd5944fec806f96`.
La suite exécute 96 tests : 95 passent localement, un Jinja est ignoré localement.
Les 17 templates et le rendu `empty` fail-closed passent avec le Python/Jinja
exact de la K1, uniquement en mémoire.

## Gate

Le runtime reste absent. Les fichiers et commandes exacts ont changé après le
GO consommé par cet essai. Toute nouvelle pose exige donc une nouvelle revue et
le même GO exact renouvelé :

`GO G4-K1-CONTROL-Z-MESH-RUNTIME-V1`
