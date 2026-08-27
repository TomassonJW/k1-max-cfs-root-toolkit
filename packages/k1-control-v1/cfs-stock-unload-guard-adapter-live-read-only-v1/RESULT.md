# Résultat — adaptateur CFS live en lecture seule V1

Date : 2026-08-27

Verdict : **OK en lecture seule ; production fermée**.

- capture privée :
  `20260827-110102-g4-k1-control-cfs-stock-unload-guard-adapter-live-read-only-v1` ;
- deux lectures fonctionnelles identiques ;
- Klipper prêt, impression au repos, `T1/T2` connectés, aucune route engagée ;
- cibles buse et plateau à zéro ;
- `sn` et `uuid` retirés avant l'adaptateur ;
- aucune dérive de forme entre la liste blanche et la réponse fraîche ;
- les unités non provisionnées utilisent réellement l'état texte `None`,
  maintenant accepté comme inactif ;
- trois empreintes de configuration identiques avant et après ;
- tests ciblés garde, mapping et adaptateurs : `61/61` ;
- suite complète : `443` tests exécutés, `440` verts et `3` ignorés connus ;
- aucun G-code, garde, retrait, chauffage, mouvement, fichier distant, service
  ou restart.

L'état courant reste `BLOCKED_NO_ENGAGED_ROUTE`. Ce résultat ne crée ni
transport ni candidat de pose et n'autorise aucun essai physique.
