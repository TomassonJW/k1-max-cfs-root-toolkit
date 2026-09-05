# 63 — Le départ ne refuse plus une buse déjà en chauffe

Date : 2026-09-05, en fin d'après-midi. Correctif posé sur la machine et prouvé
à froid ; essai d'impression réel non réalisé.

## Ce qui n'allait pas

Le correctif du 5 septembre au matin (document 62) agissait sur le profil Orca
et sur une copie du fichier. Il ne pouvait rien pour les fichiers déjà tranchés,
et la copie corrigée n'a pas été reprise : le troisième départ, à `17:47`, est
reparti de l'original et s'est arrêté au même octet, sur le même refus.

```
17:47:08  work_handler start print, ... MultiBin Shell_PLA_13h38m.gcode
17:50:04  _KCTRL_PROBE_GUARD_ON : the nozzle is already targeting 220 C,
          above the 105 C probing ceiling
17:50:04  Exiting SD card print (position 14513)
```

Trois arrêts, tous à la position `14513`, à `16:21`, `16:43` et `17:47`.

La cause profonde n'est pas dans le fichier : elle est dans le garde. Ouvrir la
fenêtre de palpage refusait une cible buse au-dessus du plafond, alors que la
même macro savait déjà couper et attendre une *température* au-dessus du
plafond. Un fichier tranché qui purge avant `START_PRINT` — ce que fait tout
profil Orca portant `T0` dans son départ machine — ne pouvait donc jamais
démarrer, quelle que soit la correction appliquée en aval.

## Le changement

Une seule règle change dans `_KCTRL_PROBE_GUARD_ON` : une cible au-dessus du
plafond est coupée et annoncée, au lieu d'interrompre la séquence.

C'est légitime parce que la fenêtre n'est ouverte que par trois séquences, et
que les trois sont propriétaires de ce qu'elles s'apprêtent à palper :
`START_PRINT`, l'acquisition de maillage et la mesure du plan. Toutes les trois
reposent la température d'impression après le contact. Une cible encore debout
à cet instant est un reste — une purge de chargement d'outil, un travail
avorté — jamais une intention à respecter.

Ce qui ne change pas : la protection elle-même. Pendant la fenêtre ouverte,
`M104` et `M109` au-dessus du plafond restent refusés, la buse est toujours
ramenée sous le plafond avant tout contact, et un plafond hors bornes est
toujours refusé.

## Preuve

Sur la machine, à froid, après pose du fichier et `FIRMWARE_RESTART` :

| Étape | Buse | Cible |
|---|---|---|
| `M104 S220` puis ouverture de la fenêtre | `75,5 °C` | `220 °C` |
| Retour de `_KCTRL_PROBE_GUARD_ON CEILING=105` | `76,7 °C` | `0 °C` |

Aucune erreur, aucun mouvement, aucun contact. La fenêtre a ensuite été refermée
et la cible remise à zéro. C'est exactement l'état qui tuait les trois départs.

Tests : `1 073` verts et `55` sous-tests verts, avec les deux échecs déjà
inscrits dans la CI (`test_unload_requires_head_sensor_to_clear` et
`test_all_canonical_scenarios_are_implemented_once`). Aucun nouvel échec. Le cas
qui vérifiait le refus `220/105` vérifie maintenant la coupure, et trois cas
s'ajoutent : la coupure est annoncée, elle a lieu après l'ouverture de la
fenêtre — sinon le plafond ne s'appliquerait pas au `M104 S0` lui-même — et un
plafond hors bornes reste refusé.

## État de la machine au moment d'écrire

Table CFS lisible, premier filament sur `T1B`. Profil `k1_p001_t055_r001_n11x11`
présent, Z accepté `+0,050 mm`. Chauffes à zéro, rien en cours.

Le capteur de tête voit encore du filament, laissé par les purges des départs
avortés. Le palpage aura donc lieu avec de la matière dans la buse. Le garde la
maintient sous `105 °C`, ce qui limite l'écoulement, mais une bavure figée sous
la buse fausserait le contact : essuyer la buse à la main avant de relancer,
conformément à ADR-045.

## Portée

Le correctif du profil Orca (document 62) reste utile — il évite un
référencement et une purge inutiles au départ — mais il n'est plus la condition
du démarrage. La copie `_KCTRL-fixed.gcode` sur la machine devient superflue ;
elle est laissée en place, l'original aussi.

Sauvegarde sur la machine : `k1-control-probe-temp-guard-v1.cfg.kctrl-bak-20260905`.
Retour arrière : recopier cette sauvegarde et `FIRMWARE_RESTART`.
