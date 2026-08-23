# CALIBRATION-UI-MATRIX-V1

Statut : correction fondée sur la campagne réelle du 23 août 2026.

Ce delta corrige les choix de matrice après preuve sur la K1 exacte.

- le pilote propriétaire `prtouch_v2_wrapper.py` possède 36 emplacements et a
  levé un `IndexError` exactement au point 37 d'une demande `9 × 9` ;
- l'interface expose donc uniquement `6 × 6` avec Lagrange ;
- `9 × 9`, `11 × 11` et `15 × 15` sont refusés côté serveur ;
- le contournement communautaire par changement de `pr_version` est rejeté car
  il modifie la sécurité du capteur et un retour signale un blocage au démarrage ;
- une calibration normale mesure un seul mesh complet. La qualification initiale
  en six passages reste conservée comme preuve historique, pas comme routine.

La pose future remplacera uniquement le contrôleur de calibration et deux
fichiers statiques, après backup exact, puis redémarrera seulement Moonraker.
Elle ne lance aucune calibration.

Après revue du commit figé, la seule autorisation de pose recevable est :
`GO G4-K1-CONTROL-CALIBRATION-UI-MATRIX-V1`.
