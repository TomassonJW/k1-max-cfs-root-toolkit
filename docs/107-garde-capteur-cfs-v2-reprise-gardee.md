# 107 - Garde capteur CFS V2 : l'auto-remplacement reste actif en impression (ADR-078)

Date : 12 novembre 2026. Suite du document 106 (fausse fin T1B) et du document
105 (garde V1, ADR-077). Conventions du document 70 : **[FAIT]** lu dans un
journal, un fichier ou un test ; **[HYPOTHÈSE]** cohérent, non démontré ;
**[INCONNU]** non observé.

## 1. Demande

Thomas, après la reprise du 12 novembre : construire la garde de reprise, pour
qu'une fausse erreur CFS en impression ne redevienne jamais pause, purge de
3000 mm et CFS laissé au repos. Hors imprimante d'abord ; la pose attend le
repos et son accord.

## 2. Cause

[FAIT] La V1 a marqué T1B à 04:25:06 et coupé l'auto-remplacement (relu dans
le journal de la nuit) : c'est le 0 vu à 06:04:09 (document 106, section 1).

[FAIT] À 04:22:06, auto-remplacement actif, le CFS 1 avait déjà répondu
`FILAMENT_ERR` sur T1B avec une ligne nommée : l'impression a continué. Même
issue le 1er novembre à 07:07 et le 31 octobre à 19:01.

[FAIT] À 06:04:09, auto-remplacement coupé, la même erreur avec `key839` a
donné `printing to pause`, la routine « extrude all material » de 06:04:17 à
06:29:54 (3000 mm) puis `SET_BOX_MODE`, CFS 1 à `mode = 0`.

[HYPOTHÈSE] Sur `key839`, le module stock relaie si l'auto-remplacement est
actif et que la case est vue, et met en pause sinon. Trois cas observés le
soutiennent ; le code stock est compilé et n'a pas été lu.

Conclusion : pendant l'impression, la coupe de ADR-077 transforme une fausse
erreur sans effet en pause et purge. Après la fin, elle ne sert plus : la fin
V5 coupe elle-même avant la coupe (ADR-076), et la fenêtre de fin arrête toute
poussée.

## 3. La garde V2

Même module `kctrl_sensor_guard`, même section, révision
`cfs-sensor-guard-v2`. Paquet `packages/k1-control-v1/cfs-sensor-guard-v2`.

| Règle | V1 | V2 |
| --- | --- | --- |
| Capteur contredit 180 s et 400 mm, tête chargée | marque et coupe l'auto-remplacement | marque, une ligne de console, rien d'autre |
| Auto-remplacement lu à 0 en impression | recoupé s'il revient à 1 | remis à 1 après 30 s, deux lectures, essai toutes les 10 s |
| `START_PRINT` | remet ce que la garde a coupé | remet tout 0 lu, sinon refuse le départ |
| Pause sur `key839` ou signalement, case encore vue | rien | ligne « fausse fin probable » et reprise à faire |
| CFS au repos (`mode 0`) dans cette pause | rien | ligne avec `BOX_SET_BOX_MODE ADDR=n MODE=PRINT NUM=x` |
| Fenêtre de fin, arrêt sur poussée, `RELEASE` | 15 min, 1 mm | identique |

La remise à 1 ne part jamais en pause, après la fin du fichier, ni pendant une
phase de la fin K1 Control ; le verrou G-code l'ordonne après une fin ou un
départ en cours. `keep_auto_refill: False` revient au comportement sans remise.

Aucun message ne commence par `!!` ni ne contient « failed » : la fin K1
Control échoue sur ces formes.

## 4. Rejeu de la vraie nuit

[FAIT] Extrait réduit du journal du 12 novembre, 422 lignes, heure et message
seuls, sans identifiant :
`tests/fixtures/k1-control-v1/cfs-sensor-guard-v2/12-novembre-t1b-extrait.log`.
Les lignes réelles passent par l'analyseur de la garde sans changement.

- Coupe de la V1 rejouée à 04:25:06 : la V2 marque T1B à 04:25:07 et remet
  l'auto-remplacement à 1 à 04:25:37, relu à 1. À 06:04:09, l'erreur trouve
  l'auto-remplacement actif, l'état de 04:22:06.
- Avec `keep_auto_refill: False` : ligne « fausse fin probable de T1B » à
  06:04:12, purge stock vue (1536,9 s, en pause), ligne du CFS 1 au repos après
  06:29:55 ; aucune commande envoyée.
- Les chronologies de la V1 (15 septembre, 13 septembre, 31 octobre,
  1er novembre) sont rejouées sous la V2 : même fenêtre de fin, même arrêt,
  jamais de marque sur une vraie fin.

## 5. Pose préparée

[FAIT] Relevé en lecture seule le 12 novembre à 10:29 : `SURVEY_OK`, aucun
écart sur 24 fichiers épinglés, module V1 (`2f4ceb96...`, mode `0644`), aucun
`.pyc`, ni fichier d'étape ni sauvegarde, configuration `8ecf4a40...` avec la
section. K1 en `standby`, `auto_refill` à 0, tête vide, garde V1 au travail 3
marquée T1B, restitution en attente.

Pose : seul le module change, de `2f4ceb96...` à `7920ba39...`. Sauvegarde
`/usr/data/k1-control-v1/backups/cfs-sensor-guard-v2`. Le redémarrage efface
la restitution en attente de la V1 ; la V2 remettra l'auto-remplacement au
prochain `START_PRINT`. Retour arrière de la V2 vers la V1 exacte, avant celui
de la V1.

## 6. Compromis et limites

- Une fausse erreur dans la seconde et demie qui précède la coupe de la fin V5
  n'est pas couverte par la remise à 1 : la fenêtre de fin la couvre.
- Un 0 posé exprès en impression est remis à 1, sauf `keep_auto_refill: False`.
- Rien n'est automatique en pause : ni arrêt de la routine stock, ni remise du
  mode impression. La ligne « au repos » attend une réponse du CFS.
- Une vraie fin de bobine en pause reçoit la ligne « au repos », jamais
  « fausse fin ».

## 7. Preuves

- `tests/test_kctrl_sensor_guard_v2.py` : 164 tests, faux Klipper sur horloge
  simulée, dont les vraies lignes du 12 novembre.
- `tests/test_cfs_sensor_guard_v2_install.py` : 98 tests de pose sur une fausse
  imprimante : relevé, préflight sans écriture, pose, refus au repos, retour
  automatique sur une V2 qui ne tourne pas comme prévu, retour arrière exact,
  champs lus comparés aux vrais modules V1 et V2.

## 8. Inconnues

- [INCONNU] Le code stock qui choisit entre relais et pause sur `key839`.
- [INCONNU] La cause de la fausse erreur sur la case B ; nettoyage du capteur
  de sortie proposé (document 106).
- [INCONNU] Une première impression sous la V2.

## 9. Suite

1. Fait : posée au repos le 12 novembre à 16:27 (section 10).
2. Relire la première impression sous la V2 : aucune pause sur fausse erreur,
   `kept` et `keep`, `blind` nul, `tap_dropped` à 0.
3. Procédure de reprise en un geste dans K1 Control (document 106, section 5).

## 10. Pose, 12 novembre 2026

[FAIT] Sur l'accord de Thomas, imprimante dite disponible, depuis `main` après
la PR #106 :

- `PREFLIGHT_OK` : 24 fichiers épinglés identiques, `standby`, V1 en service
  (travail 3, T1B marqué, restitution en attente), `auto_refill` à 0 ;
- `INSTALLED_IDLE_OK` à 16:27:34 : module remplacé, Klipper redémarré une fois,
  aucune trace d'erreur dans le journal depuis l'arrêt ; ni chauffe, ni
  mouvement, ni filament ;
- `VALIDATED_IDLE_OK` : révision `cfs-sensor-guard-v2`, `hook =
  inside_cold_guard`, `keep_auto_refill` vrai, `blind` nul, `tap_seen` 10,
  `tap_dropped` 0, aucune marque ;
- relecture : empreinte `7920ba39...`, sauvegarde
  `/usr/data/k1-control-v1/backups/cfs-sensor-guard-v2` complète.

[FAIT] `auto_refill` lu à 1 juste après le redémarrage, sans action de la
garde : l'écran le renvoie à sa connexion. `box.t_command` vide après le
redémarrage, comme attendu.

Retour arrière : `python deploy.py rollback` dans le paquet V2, au repos ; il
remet la V1 exacte.
