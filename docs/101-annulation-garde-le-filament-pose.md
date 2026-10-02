# 101 — Annulation qui garde le filament : pose (ADR-074)

## Ce qui est en service

`packages/k1-control-v1/cancel-retained-end-v4/kctrl_end.py` remplace la fin
V3 sur la K1. Posé le 2 octobre 2026 à 12:53 (horloge locale), imprimante au
repos revérifiée juste avant l'arrêt de Klipper, après la fin de l'impression
de Thomas.

Preuves :

- aucune impression pendant la pose : l'historique Moonraker donne la dernière
  impression `…Body2_PETG_6m46s.gcode` terminée (`completed`) à 12:36:23 et
  aucune autre ensuite ; l'installateur a exigé `print_stats` au repos, SD
  inactive, pas de pause, `idle_timeout` hors `Printing`, chauffes à zéro et
  aucun mouvement, deux fois au préflight puis une fois juste avant l'arrêt ;
- `PREFLIGHT_OK` réel : 19 fichiers épinglés identiques, cible égale à la V3
  installée (`18778298…`), candidat compilé par le Python de Klipper ;
- `INSTALLED_IDLE_OK` : sauvegarde, remplacement atomique, redémarrage,
  révision `cancel-retained-v4` lue sur le socket Klipper, 0 traceback ;
- `VALIDATED_IDLE_OK` indépendant : fin `idle`, `retained=false`, portail de
  départ libéré, CFS 1 et 2 connectés, chauffes à zéro, départ au repos ;
- tests : 85 pour le module (toute la suite V3 rejouée sur V4, plus
  l'annulation réelle à 140 °C, la sortie du bac, le plateau trop haut, les
  routes non prouvées, l'erreur firmware, la coupure, les chauffes) et 35 pour
  l'installateur.

Sauvegarde : `/usr/data/k1-control-v1/backups/cancel-retained-end-v4`.
Retour arrière au repos seulement : `deploy.py rollback`.

## Ce que voit Thomas

Annulation avec filament en tête : la console affiche « annulation terminee,
T.. garde en tete, chauffes coupees ; nouveau depart possible directement ».
Lancer l'impression suivante normalement.

Si elle affiche « sans emplacement prouve », le départ demandera de confirmer
l'emplacement ; si elle affiche « annulation incomplete », le départ reste
bloqué : lire la raison entre parenthèses.

## Limites

- Pas encore observé sur une vraie annulation.
- Le redémarrage de pose a rechargé le mesh `default` ; `START_PRINT`
  recharge le profil et le Z de l'impression.
- Le journal de pose a aussi capté nos propres requêtes de statut (filtre
  `kctrl_end` trop large) : sans effet sur la décision, qui lit le socket.
- Deux tests hors sujet échouent déjà sur `main`
  (`test_cfs_direct_owner_offline_v1`, `test_job_lifecycle_offline_v1`).
