# Cold push guard V1 - pas de poussée de filament buse froide

Statut : **installé et validé à froid le 31 octobre 2026, 23:46-23:47**.
Reçus hors Git dans `inventory/raw/20261031-cold-push-guard-v1/`. ADR-076,
document 104.

- `kctrl_purge_guard.py` : la garde du bac, inchangée, plus une enveloppe de
  `extruder.check_move`. Une poussée est refusée quand la buse est sous 170 °C
  et qu'aucune consigne ne l'atteint ; un retrait passe toujours. Le refus est
  une erreur de commande, sans chauffe, mouvement ni arrêt d'urgence.
  `cold_refused` compte les refus et `cold_last` décrit le dernier.
- `build_manifest.py` : écrit `manifest.json` avec les 23 fichiers épinglés et
  les empreintes du candidat et de l'installateur.
- `remote_install.py` : préflight, pose, validation, sonde et retour arrière,
  K1 au repos prouvé par deux lectures identiques.
- `deploy.py` : envoie l'installateur par `ssh k1max-root python3 -` et range le
  reçu.

La pose a remplacé un seul fichier et redémarré Klipper au repos. La sonde a
demandé une poussée de 0,5 mm sur la tête vide, buse à 24 °C : refusée,
position E inchangée, un seul refus compté.

Validation : **68 tests ciblés verts** (`tests/test_kctrl_cold_push_guard.py`,
`tests/test_cold_push_guard_install.py`), avec de faux objets et sans
transport imprimante.

Retour arrière au repos seulement, après celui de la fin V5
(`end-no-stock-flush-v5`) : l'installateur refuse tant qu'elle est en place.
**Ne rejouer ni la pose ni la sonde.**
