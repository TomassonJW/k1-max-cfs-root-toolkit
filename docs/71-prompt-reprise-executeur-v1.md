# Prompt de reprise — exécution du plan d'audit

À copier-coller tel quel. Écrit le 2026-09-10 à 01:20, à la clôture de la
session qui a corrigé le changement d'outil.

---

## Mission

Tu as audité la séquence de démarrage de la K1 Max + CFS de Thomas Jankowski et
rendu `docs/70-audit-independant-sequence-demarrage-v1.md`. **Tu passes en mode
exécuteur : tu appliques ton propre tableau §4, dans l'ordre, avec preuve à
chaque étape.**

Dépôt : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`,
branche `fix/cfs-temperature-chargement`, PR #51 (ouverte, à garder ouverte
jusqu'à ce qu'une impression aboutisse). Machine : `ssh k1max-root`.

Commence par lire, dans cet ordre : `HANDOFF.md` (bloc du 10 septembre 01:20),
`docs/70-…`, puis le diff de `6fa7032..HEAD`.

## Règles machine, non négociables

- **`SAVE_CONFIG` interdit.** Jamais.
- **Aucune action changeant l'état machine tant que `print_stats.state` vaut
  `printing`.** Vérifier avant chaque action, pas une fois au début.
- Redémarrage Klipper : `/etc/init.d/S55klipper_service restart`. Ne jamais
  enchaîner `RESTART` et `FIRMWARE_RESTART`.
- **Pas de test d'impression maison.** Interdit par le propriétaire.
- **Un seul chemin de reprise.** Ne jamais relancer depuis l'écran après un
  `box_resume_extrude` du CFS — c'est ce qui a produit le `-40.590` de 01:07.
- Rien n'est déployé sur la machine sans accord explicite du propriétaire.
- Jamais `git add -A` ni `git add .` — `git commit --only <chemins>`.
- Ne jamais annoncer « corrigé », « testé » ou « sûr » sans preuve exécutable.

## Point de reprise, en un geste

L'annulation a vidé `Tnn_map`. Avant **toute** impression :

```
KCTRL_SLOT SLOT=T2D TOOL=T1B
```

Sans ça `START_PRINT` lève une erreur explicite et refuse de deviner —
comportement voulu (le repli `slot_last_choice` ne couvre que `T1A`, et le
fichier démarre sur `T1B`).

## Ce qui est acquis, à ne pas refaire

- **Le changement d'outil en tête de séquence fonctionne.** Éprouvé par un
  départ réel : coupe au début, `z_down move_z: 0.8` contre `44.027`, aucun
  `Move out of range` pendant `START_PRINT`, séquence complète jusqu'à la
  première couche.
- **La thèse `last_cmd` est confirmée par le comportement inverse** : quand
  `last_cmd` vaut `T2D` et l'outil demandé `T2D`, le module fait
  `box_resume_extrude` et ne coupe pas.
- Le zéro Z **est** appliqué à la ligne d'amorce (`homing_origin Z = 0.14`,
  écart mesuré entre `gcode_position` et `position`). Ce n'est pas la cause de
  la ligne trop fine.
- `SET_HOTEND_FAN` / `key61` est du bruit de `/usr/bin/master-server`, pas du
  gcode. Ce n'est jamais la cause de rien.

## L'ordre d'exécution

1. **P1 — rendre l'accumulateur Z avant de sortir du bloc CFS.** C'est la cause
   de fond des `Move out of range`. Preuve attendue : `z_restore` puis `None`
   **avant** la ligne d'amorce, et aucun `Move z not clear` au départ suivant.
2. **P2 — faire échouer `START_PRINT` sur erreur CFS.** Constaté cette nuit :
   après `key841`, la séquence a continué à purger et à tracer.
3. **P3 — ne pas émettre de `T` avec du filament en tête et un cutter non
   prouvé.**
4. **P5 — ligne d'amorce.** Défaut assumé : monter le débit *et* la vitesse
   ensemble a fait baisser la section par trait (0,133 mm² contre 0,150 stock,
   0,37 mm de large contre 0,75). Plafonner à 15 mm³/s et/ou descendre
   `variable_line_speed` de 9000 à 6000.
5. **P4 — plancher Z de zone.** Le garde est au dépôt, non déployé, ses deux
   tests sont en `xfail` parce que leur périmètre n'est pas tranché (seuil
   Y 296 contre incident à Y 291,5). Ton §4 le révise à Y ≥ 285 conditionné à
   `printing`. Corrige les tests avec le code, retire les `xfail`.
6. **P6, P7 — documents et température de chargement.**

Puis, et seulement alors : une impression réelle, surveillée, pour prouver
l'ensemble.

## Deux dettes hors périmètre, à ne pas masquer

Rouges avant cette mission, sans rapport avec elle :
`test_cfs_direct_owner_offline_v1::test_unload_requires_head_sensor_to_clear`
et `test_job_lifecycle_offline_v1::test_all_canonical_scenarios_are_implemented_once`
(contrat `end_full_unload` contre `end_keep_engaged`). À traiter dans une
mission propre, pas ici.

## Inconnue à garder ouverte

Le capteur de coupe a échoué cinq fois puis refonctionné deux fois, **sans que
`box.cfg` change d'un octet** (md5 `dd05b5bb69929389d233cc1e487a44de` avant et
après ; sauvegarde `box.cfg.kctrl-bak-avant-calib-cutter-20260910`). Défaillance
intermittente non expliquée. Deux fils du forum Creality cités dans ton §5
pointent des débris et le réglage de `cut_pos` (TC2841).

Réponses au propriétaire en français, courtes. Le résultat, pas le récit.
