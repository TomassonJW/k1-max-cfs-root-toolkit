# 99 — Reprise après changement raté : blocage corrigé et posé

Date : 24 septembre 2026. Décision : ADR-072. Paquet :
`packages/k1-control-v1/resume-reload-guard-v1`.

## 1. Incident du 23 septembre

Impression multi-filament. Un changement en cours d'impression échoue
(`key837`), le firmware met en pause. Thomas fait RESUME à l'écran. Le
rechargement `T1A` et la purge se passent bien (fin à 23:08:01), puis plus
rien : l'impression reste figée. Le journal montre la pause de fin de bobine
déclenchée à 23:06:44 par le capteur de tête vidé pendant le rechargement,
puis `do_after_pause: waiting printing to pause` chaque seconde jusqu'à
l'annulation. Mécanisme complet : ADR-072.

Pendant ce même incident, un redémarrage de Klipper lancé en pleine impression
a coupé les moteurs et perdu la pièce. Règle retenue : aucune pose de module
Klipper, ni aucun redémarrage, tant qu'une impression tourne.

## 2. Correctif

`kctrl_tool_change.py` (source `packages/k1-control-v1/owned-start-print-v2/`)
enveloppe les seize rechargements `T1A`..`T4D` : alarme de tête coupée pendant
la commande stock, rallumée après `M400`, sans rien ajouter d'autre. Les
changements `T0`..`T15`, le départ et la fin sont inchangés.

Tests : 48 tests du module (dont reprise à `klippy:ready`, échec du
rechargement, alarme déjà coupée, pendant `START_PRINT`) et 26 tests de
l'installateur (pose, refus, annulation si une impression démarre juste avant
l'arrêt, retour automatique si les seize rechargements manquent, retour
arrière exact). Suite CI : 1 957 verts.

## 3. Pose au repos

L'installateur ne change qu'un fichier. Il épingle 19 autres fichiers (départ,
fin, CFS, `virtual_sdcard`, `pause_resume`, capteurs, configurations) avant et
après, et n'agit que si rien n'imprime, ne chauffe ni ne bouge : impression
`standby|cancelled|complete|error`, cibles à zéro, vitesses nulles, file de
mouvements vide, CFS connecté sans commande, départ et fin au repos. Ce repos
est revérifié juste avant l'arrêt du service. Après redémarrage, il exige les
seize rechargements actifs, sinon il remet l'original.

| Étape | Résultat |
| --- | --- |
| préflight | `PREFLIGHT_OK`, 19 empreintes conformes, candidat compilé par le Python de Klipper |
| pose (24/09, 00:48 horloge K1) | `INSTALLED_IDLE_OK`, 16 rechargements, 0 traceback |
| validation indépendante | `VALIDATED_IDLE_OK`, `standby` |
| relecture fraîche | 19 empreintes inchangées, cible `2e33eb37…`, départ et fin `idle`, CFS 1 et 2 connectés |

Sauvegarde : `/usr/data/k1-control-v1/backups/resume-reload-guard-v1`.
Réponses brutes : `inventory/raw/20260924-resume-reload-guard-v1/` (non versionné).

Le redémarrage n'a pas d'effet sur l'impression suivante : `START_PRINT`
recharge lui-même le mesh de la bande de température et le Z enregistré après
son homing.

Retour arrière, au repos seulement :

```bash
python packages/k1-control-v1/resume-reload-guard-v1/deploy.py rollback
```

## 4. Ce qui reste à observer

- La première vraie reprise après un changement raté : `KCTRL_TOOLS` affiche
  « dernier rechargement de reprise » (outil, erreur, tête, pause).
- Les `key837` eux-mêmes (prise du CFS) restent possibles ; ils sont désormais
  récupérables par RESUME au lieu de figer l'impression.
- Après l'annulation du 23 septembre, la fin affichait `phase=failed`,
  `job_identity_missing` ; elle est revenue à `idle` au redémarrage. À suivre
  si l'état revient après une annulation.
