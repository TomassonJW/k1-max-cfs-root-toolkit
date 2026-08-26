# Résultat — MESH-EDGE-DIAGNOSTIC-V1

Date : 2026-08-26

Capture : `20260826-090956-mesh-edge-diagnostic-v1`

Statut : **passage source invalide sans débit ; rollback et validation finale
verts ; nouvelle impression interdite sans nouvelle reprise explicite**.

## Passage observé

La préparation source et le motif source ont été lancés. La tête a chauffé et
bougé, mais aucun filament n'a été déposé. Le G-code ne résolvait aucun outil
CFS, ne chargeait pas et ne purgeait pas. La mention `T0` était une hypothèse de
Codex, pas un fait fourni par Thomas.

Ce passage ne qualifie ni le mesh ni une buse bouchée.

## Restauration

La reprise a utilisé la session et le backup exacts de la capture. Le contrôle
préalable a obtenu :

    WAIT_COMPLETE_MESH_EDGE_DIAGNOSTIC_V1_OK variant=source

Le rollback borné a ensuite obtenu :

    ROLLBACK_MESH_EDGE_DIAGNOSTIC_V1_OK capture=20260826-090956-mesh-edge-diagnostic-v1

Il a coupé les chauffes, libéré les axes, restauré `printer.cfg` depuis le
backup vérifié, redémarré Klipper, rechargé le profil robuste et supprimé les
quatre G-code temporaires. Aucun homing, mouvement, chauffage, extrusion,
changement CFS ou nouveau motif n'a été lancé pendant cette reprise.

## Validation finale

La validation indépendante a obtenu :

    VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK capture=20260826-090956-mesh-edge-diagnostic-v1

Elle prouve :

- empreinte exacte de la base `printer.cfg` :
  `f88d6b52477592805384fca2b4d7abd00298deecd82227af2fa580085fe26fa2` ;
- profil diagnostic dérivé absent ;
- quatre G-code temporaires absents ;
- profil robuste `k1_p001_t055_r001_n06x06` actif ;
- profil composite source toujours présent ;
- chauffes demandées à zéro ;
- axes non référencés ;
- runtime Z prêt, offset accepté `-0,04 mm`, mouvements bas désarmés et
  stockage intègre ;
- chemin Z fermé ;
- deux CFS connectés ;
- Moonraker/Klipper sans composant échoué ni avertissement.

## Suite

La machine est revenue à sa base sûre. La gate reste suspendue : aucun nouveau
motif n'est autorisé par ce résultat. Une reprise ultérieure doit d'abord
résoudre la route outil logique/CFS/slot depuis l'état frais et obtenir une
purge réellement visible. Un capteur de présence seul ne suffit pas.
