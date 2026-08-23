# CALIBRATION-UI-MATRIX-V1

Statut : installée et validée sous la capture
`20260823-161103-g4-k1-control-calibration-ui-matrix-v1`.

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

Le premier GO reçu le 23 août a été arrêté hors imprimante avant toute
connexion : le préflight conservait encore les assertions des grandes matrices
et le validateur cherchait d'anciens marqueurs. La correction prouve désormais
le refus des tailles non qualifiées sur le Python Moonraker exact et contrôle
BED-MESH-V2, `printer.cfg`, le profil robuste, le Z, les deux CFS ainsi que
`failed_components=[]` et `warnings=[]`. Le déployeur ayant changé, la pose
attend un nouveau GO exact sur le commit corrigé.

Le GO renouvelé a ouvert un préflight SSH strictement en lecture seule. Il a
confirmé l'état terminal sûr `rolled_back`, mais la garde MATRIX ne le listait
pas encore parmi les états fermés. Elle l'accepte désormais uniquement avec
`busy=false`, conformément au core et aux autres gardes. Aucune pose ni aucun
restart n'ont eu lieu ; ce nouveau changement du déployeur exige encore le même
GO exact sur le nouveau commit corrigé.

Le GO persistant a ensuite permis de terminer la gate sans redemander la même
autorisation. Le préflight, le déploiement et deux validations sont verts. Le
backup exact est conservé, seul Moonraker a été redémarré et aucune calibration
ou action physique n'a été lancée. MATRIX-V1 est close.
