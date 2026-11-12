# Départ repris après un chargement stock raté

Statut : **construit et testé hors imprimante le 12 novembre 2026, pas posé.**
ADR-079, document 108. Remplace `kctrl_start.py` de `retained-start-v1` ; tout
le reste du départ K1 Control est gardé.

- `kctrl_start.py` : le module Klipper, même objet `kctrl_start`, révision
  `start-load-recovery-v1`.
- `remote_install.py`, `deploy.py`, `build_manifest.py`, `manifest.json` : la
  pose, voir « Pose » plus bas.

## Pourquoi

Le 12 novembre à 17:08 (document 108), le chargement stock de T1B a poussé le
filament jusqu'à la tête, puis le CFS a conclu deux fois « buffer is always
full » et répondu `key837`. Le module stock a mis en pause et voulu remonter
le plateau la tête au-dessus du bac : la garde du bac a refusé, à juste titre,
et le départ s'est arrêté chauffes coupées. Le filament était pourtant en
tête. Relancé à 17:43, le même départ a trouvé T1B en tête, l'a purgé
lui-même au bac (`recover`) et l'impression est partie.

Ce paquet fait ce second départ à l'intérieur du premier : plus besoin de
relancer.

## Ce qui change

Quand `T1A`..`T4D` rend la main pendant le chargement d'un départ :

1. Les lignes `!!` du chargement sont lues. Seuls `key837` sur le slot demandé
   et le refus de la garde du bac sont tolérés ; toute autre erreur arrête le
   départ comme avant.
2. Sans erreur ni pause : rien ne change.
3. Avec `key837`, un refus de la garde ou une pause stock, la reprise exige,
   avant tout effet : phase `material` en cours, CFS sorti de son traitement
   d'erreur, les deux capteurs (tête et sortie) à vrai, le slot demandé en
   tête et seul engagé, la mémoire de levée du CFS lisible, la consigne
   plateau d'avant le chargement connue, une pause stock réversible. Sinon le
   départ s'arrête chauffes coupées, sans réessai.
4. Ensuite : chien de garde repoussé de 180 s, pause stock levée (sans
   `RESUME`, l'écran reçoit `key602`), position G-code d'avant le chargement
   remise sans mouvement, consigne plateau remise, mémoire de levée du CFS
   effacée, puis la purge K1 Control habituelle au bac (plateau descendu,
   entrée et sortie dans l'axe Y, décrochage), puis `M190` sur la consigne
   d'avant.
5. Une seule reprise par départ. Le message final dit
   « filament T1B pret (empty, repris) ».

## Limites

- `key845` et toute autre erreur de chargement restent un arrêt propre.
- Un vrai bouchon donne un tampon non consommé pendant la purge : arrêt
  propre, chauffes coupées.
- Ce que l'écran affiche après `key601` puis `key602` est inconnu.
- Que `BOX_ERROR_CLEAR` efface l'erreur stock est une déduction : sinon arrêt
  avant de pousser (`cfs_error_not_cleared`).
- L'attente `M190` compte dans les 180 s de la reprise.
- Pas encore vu sur une impression réelle.

## Pose

    python deploy.py survey|preflight|install|validate|rollback

`survey` et `preflight` ne font que lire. `install` et `rollback` redémarrent
Klipper, au repos seulement, sans chauffe, sans mouvement, sans filament.

Une seule cible : `/usr/share/klipper/klippy/extras/kctrl_start.py`, de
`retained-start-v1` (`d112cf29...`) à `start-load-recovery-v1`. 24 fichiers
épinglés : ceux de la garde capteur V2, plus `kctrl_sensor_guard.py` V2
(`7920ba39...`). Les `.pyc` du module sont effacés à la pose et au retour.

Le préflight cherche dans les sources constructeur épinglées les noms appelés
par la reprise (`must_pause_work`, `reportInformation`, `pause_command_sent`,
`sd_paused`, `inside_error`, `reset_last_position`) ; un nom absent ferme la
pose. Ceux du CFS, compilé, sont seulement rapportés : le module refuse la
reprise s'ils manquent vraiment.

Sauvegarde : `/usr/data/k1-control-v1/backups/start-load-recovery-v1`. Échec
après la pose : retour automatique et redémarrage,
`INSTALL_FAILED_ROLLED_BACK`. Après le redémarrage, le départ doit être neuf :
révision, phase `idle`, aucune reprise, délai 180 s.

Ordre : ce paquet vient après la garde capteur V2. Les paquets antérieurs
épinglent `kctrl_start.py` à `d112cf29...` : retour arrière de celui-ci
d'abord.

Le relevé en lecture seule n'est pas encore fait : `surveyed: false`,
l'installateur refuse tout sauf `survey`.

Validation : 90 tests du module (`tests/test_start_load_recovery.py`), dont
le rejeu des vraies lignes de 17:08 et 23 tests du départ gardé rejoués sur
ce module, et 102 tests de pose (`tests/test_start_load_recovery_install.py`).
Aucun réseau, aucun SSH.
