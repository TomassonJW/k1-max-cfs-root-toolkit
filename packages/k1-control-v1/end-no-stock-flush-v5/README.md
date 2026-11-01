# End no stock flush V5 - la fin coupe l'auto-remplacement CFS avant la coupe

Statut : **prêt, pas posé**. ADR-076, document 104.

- `kctrl_end.py` : la fin V4 (`cancel-retained-v4`) plus la gestion de
  `box.auto_refill`. Avant toute coupe ou commande `BOX_*`, elle le passe à 0
  et exige deux lectures à 0 ; elle le relit avant chaque effet suivant et
  s'arrête en échec s'il est revenu à 1. `key839` ou « filament error »
  donnent l'échec `cfs_filament_error`. Une fin complète le remet, prouvé par
  deux lectures ; une fin en échec le laisse coupé et le départ suivant le
  remet avant toute chauffe, ou refuse de partir. L'annulation garde le
  filament (ADR-074) et ne touche pas à l'auto-remplacement.
- `build_manifest.py` : écrit `manifest.json` avec 23 fichiers épinglés, dont
  la garde à froid `8c637cc4…`, et l'empreinte de la fin V4 remplacée.
- `remote_install.py` : préflight, pose, validation et retour arrière, K1 au
  repos prouvé par deux lectures identiques. Il exige la garde à froid en
  service dans tous les modes.
- `deploy.py` : envoie l'installateur par `ssh k1max-root python3 -` et range le
  reçu.

Pose au repos revérifié, Thomas présent, préflight d'abord. Effet attendu : un
fichier remplacé, Klipper redémarré au repos, aucune chauffe, aucun mouvement,
aucun effet filament. Le reçu donne la révision relue sur le socket et la
valeur d'`auto_refill`.

Validation : **173 tests ciblés verts**
(`tests/test_kctrl_end_no_stock_flush_v5.py`, dont les 85 tests de la V4
rejoués, et `tests/test_end_no_stock_flush_v5_install.py`), plus sept mutants
tous détectés. Faux objets, aucun transport imprimante.

Retour arrière avant celui de la garde à froid. Après lui, plus rien ne remet
l'auto-remplacement au départ : le reçu dit la valeur lue après le
redémarrage.
