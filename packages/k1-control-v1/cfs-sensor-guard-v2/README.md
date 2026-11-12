# CFS sensor guard V2 - une fausse erreur CFS ne devient plus pause et purge

Statut : **construite et testée hors imprimante, pas posée**. Relevé en lecture
seule sur la K1 le 12 novembre 2026 : 24 fichiers épinglés identiques, V1 en
place. ADR-078, document 107. Remplace la coupe de l'auto-remplacement de
ADR-077 (document 105) ; tout le reste de la V1 est gardé.

- `kctrl_sensor_guard.py` : le module Klipper, même objet `kctrl_sensor_guard`,
  révision `cfs-sensor-guard-v2`.
- `sections.cfg` : la section de la V1, identique. La V1 posée suffit, la
  configuration n'est pas touchée.
- `remote_install.py`, `deploy.py`, `build_manifest.py`, `manifest.json` : la
  pose, voir « Pose » plus bas.

## Pourquoi

Le 12 novembre (document 106), la V1 a marqué T1B à 04:25:06 et coupé
l'auto-remplacement, comme prévu. À 06:04:09, le CFS 1 a de nouveau répondu
`FILAMENT_ERR` sur T1B, `key839` « no filament detected at box extrude
position », alors que son masque `connections` voyait toujours la case B.
Auto-remplacement coupé, le module stock a mis l'impression en pause, poussé
3000 mm au bac (« extrude all material ») puis laissé le CFS au repos
(`mode = 0`) : plus de mou, rien n'est sorti à la première reprise.

La même fausse erreur, auto-remplacement actif, a laissé l'impression tourner
à 04:22:06 cette nuit-là, le 1er novembre à 07:07 et le 31 octobre à 19:01.
Couper l'auto-remplacement en impression a transformé une fausse erreur sans
effet en une heure perdue et une purge de 3 m.

## Ce qui change par rapport à la V1

1. **La marque ne fait que parler.** Un épisode encore suspect après 180 s et
   400 mm imprimés, tête chargée, donne une ligne de console qui nomme le slot.
   Plus de `BOX_ENABLE_AUTO_REFILL ENABLE=0`.
2. **L'auto-remplacement est tenu à 1 pendant l'impression.** Lu à 0 pendant
   30 s, fichier ouvert, en `printing`, hors des phases de la fin K1 Control :
   `BOX_ENABLE_AUTO_REFILL ENABLE=1` sous le verrou G-code, deux lectures à 1,
   nouvel essai toutes les 10 s sinon. Jamais en pause, jamais après la fin du
   fichier : la fin V5 coupe elle-même l'auto-remplacement avant la coupe
   (ADR-076). Option `keep_auto_refill`, vraie par défaut.
3. **`START_PRINT` remet l'auto-remplacement à 1** s'il est lu à 0, prouvé par
   deux lectures, sinon le départ est refusé. La V1 ne remettait que ce qu'elle
   avait coupé.
4. **En pause, deux messages, aucune action.** Après un `key839` ou un
   signalement sur le slot qui imprimait, si le masque `connections` voit encore
   la case : « fausse fin probable », avec la commande de reprise. Si le CFS est
   lu au repos (`mode 0`) pendant cette pause : la ligne
   `BOX_SET_BOX_MODE ADDR=n MODE=PRINT NUM=x` qui rend le mou. Rien n'est fait à
   la routine stock ni au mode.

La fenêtre de fin de 15 min, l'arrêt sur poussée après la fin,
`KCTRL_SENSOR_GUARD_RELEASE`, l'ordre des contrôles (stock, garde capteur,
garde à froid) et l'exigence de `[kctrl_end]` activé sont ceux de la V1.

## Rejeu de la vraie nuit

`tests/fixtures/k1-control-v1/cfs-sensor-guard-v2/12-novembre-t1b-extrait.log` :
422 lignes du journal Klipper de la nuit, heure et message seulement, sans
identifiant. Rejouées dans la V2 :

- coupe de la V1 rejouée de l'extérieur à 04:25:06 : la V2 marque T1B à
  04:25:07 et remet l'auto-remplacement à 1 à 04:25:37, relu. À 06:04:09,
  l'erreur trouve l'auto-remplacement actif, comme à 04:22:06 ;
- avec `keep_auto_refill: False` : « fausse fin probable de T1B » à 06:04:12,
  la purge stock vue (1536,9 s), puis la ligne du CFS 1 au repos ; aucune
  commande envoyée.

## Compromis et limites

- Une fausse erreur dans la seconde et demie qui précède la coupe de la fin V5
  n'est pas couverte par la remise à 1 : elle relève de la fenêtre de fin.
- Un auto-remplacement mis à 0 exprès pendant l'impression est remis à 1 :
  `keep_auto_refill: False` pour le garder.
- En pause, rien n'est automatique : ni arrêt de la purge stock, ni remise du
  mode impression. La ligne « au repos » ne part qu'après une réponse du CFS.
- Le redémarrage de la pose perd la restitution en attente de la V1 ; la V2
  remet l'auto-remplacement au `START_PRINT` suivant.
- Que l'auto-remplacement à 1 évite toujours la pause sur ce `key839` reste
  prouvé par trois cas observés, pas par le code stock, qui est compilé.

## Pose

    python deploy.py survey|preflight|install|validate|rollback

`survey` et `preflight` ne font que lire. `install` et `rollback` redémarrent
Klipper, au repos seulement, sans chauffe, sans mouvement, sans filament.

Une seule cible : `/usr/share/klipper/klippy/extras/kctrl_sensor_guard.py`,
de la V1 (`2f4ceb96...`) à la V2 (`7920ba39...`). La configuration de fin
reste celle posée par la V1 (`8ecf4a40...`) et est épinglée : 24 fichiers en
tout. Les `.pyc` du module sont effacés à la pose et au retour arrière.

Sauvegarde sur la K1 : `/usr/data/k1-control-v1/backups/cfs-sensor-guard-v2`
(`module.before`, `mode.json`, `manifest.json`, `receipt.json`). Échec après la
pose : retour arrière automatique vers la V1 et redémarrage,
`INSTALL_FAILED_ROLLED_BACK`.

Le préflight exige la V1 en service, la K1 au repos sur deux lectures et le
candidat compilé par l'interpréteur de Klipper. Le repos est revérifié juste
avant l'arrêt (`NOT_INSTALLED_NOTHING_CHANGED` sinon). Après le redémarrage,
la V2 doit être fraîche : révision, `hook = inside_cold_guard`,
`keep_auto_refill` vrai, aucune marque, aucun épisode, aucune pause vue.

Retour arrière : celui de la V2 remet la V1 exacte. Celui de la V1 refuse tant
que la V2 est posée : V2 d'abord.

Validation : **98 tests de pose** (`tests/test_cfs_sensor_guard_v2_install.py`)
sur une fausse imprimante en mémoire et **164 tests ciblés** du module
(`tests/test_kctrl_sensor_guard_v2.py`), dont le rejeu des vraies lignes du
12 novembre. Aucun réseau, aucun SSH.
