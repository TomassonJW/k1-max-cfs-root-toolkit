# 108 - Départ repris après un chargement stock raté (ADR-079)

Date : 12 novembre 2026, pose le 15 novembre (section 10). Suite du document 107 (garde capteur V2). Conventions
du document 70 : **[FAIT]** lu dans un journal, un fichier ou un test ;
**[HYPOTHÈSE]** cohérent, non démontré ; **[INCONNU]** non observé.

## 1. Demande

Thomas, après le départ arrêté de 17:04 puis le départ réussi de 17:43 : que le
départ fonctionne à chaque fois, sans relance. Construire hors imprimante une
reprise dans le même départ ; la pose attend le repos et son accord.

## 2. Ce qui s'est passé à 17:08

Extrait réduit du journal, 113 lignes, heure et message seuls :
`tests/fixtures/k1-control-v1/start-load-recovery-v1/12-novembre-1704-extrait.log`.

- [FAIT] 17:08:09 : `T0` résolu en T1A sur T1B. Le chargement stock descend le
  plateau jusqu'à `move_z` 30,04.
- [FAIT] 17:09:46 : « buffer is always full », réessai stock, `SET_BOX_MODE`,
  second essai (`move_z` 30,14).
- [FAIT] 17:11:13,560 : de nouveau « buffer is always full », puis
  `!! key837` avec `values [1, "B"]`, puis « printing to pause ».
- [FAIT] 17:11:14,482 : la pause stock veut ramener le plateau de Z 35,01 à
  Z 4,80, tête à X210 Y291,5 au-dessus du bac. La garde du bac refuse
  (`purge_bed_clearance_below_30mm`) et coupe les chauffes.
- [FAIT] 17:11:14,498 : « depart interrompu (start_paused) », puis fin du
  fichier à 17:11:14,518.
- [FAIT] Relancé à 17:43, le même départ a trouvé T1B en tête et l'a purgé
  lui-même au bac : « filament T1B pret (recover) » à 17:46:09, impression
  partie à 17:46:20.

[FAIT] Le filament était donc en tête dès 17:11 : le second départ l'a prouvé
en le purgeant. [HYPOTHÈSE] Le CFS conclut « tampon toujours plein » quand le
filament arrive en tête plus tôt que son compte ne l'attend ; la cause exacte
est dans le module CFS compilé.

[FAIT] La garde du bac a eu raison : la remontée demandée par la pause stock
aurait mis le plateau sous le mécanisme du bac, tête dedans.

## 3. La reprise

Module `kctrl_start`, révision `start-load-recovery-v1`. Paquet
`packages/k1-control-v1/start-load-recovery-v1`.

Pendant le `T1A`..`T4D` d'un départ, les lignes `!!` sont lues au lieu
d'arrêter à la première. Seuls `key837` sur le slot demandé et le refus de la
garde du bac sont tolérés ; tout autre code, ou `key837` sur un autre slot,
arrête le départ comme avant.

Toutes les preuves sont lues avant le premier effet. Il en faut :

| Preuve | Refus sinon |
| --- | --- |
| Une seule reprise par départ | `stock_load_failed_again` |
| Départ encore en phase `material` | la cause d'arrêt déjà connue |
| CFS sorti de son traitement d'erreur | `cfs_error_still_processing` |
| Capteurs tête et sortie à vrai | `stock_load_failed_head_not_loaded` |
| Slot demandé en tête et seul engagé | `stock_load_failed_slot_unproven`, `..._other_route` |
| Mémoire de levée du CFS lisible | `cfs_lift_record_unknown` |
| Remise de la position G-code disponible | `gcode_position_reset_missing` |
| Consigne plateau d'avant le chargement connue | `bed_target_unknown` |
| Pause stock réversible (fichier actif, drapeaux connus) | `stock_pause_not_reversible` |

Effets, dans l'ordre : chien de garde repoussé de 180 s ; drapeaux de la pause
stock levés sans `RESUME` ; position G-code d'avant le chargement remise sans
mouvement ; consigne plateau remise ; mémoire de levée du CFS effacée ;
position réelle relue ; `key602` à l'écran ; puis la purge K1 Control
habituelle (plateau descendu, entrée et sortie dans l'axe Y, décrochage) et
`M190` sur la consigne d'avant. Pendant la purge, `BOX_ERROR_CLEAR` doit
effacer l'erreur stock (`cfs_error_not_cleared` sinon) et le tampon doit être
consommé (`buffer_consumption_unconfirmed` sinon).

Tout échec arrête le départ chauffes coupées, sans réessai. Le statut expose
`recovery` (codes, pause, levée, slot, issue) et `recovery_timeout`.

[FAIT] Lu dans les sources constructeur capturées : la pause stock pendant
`START_PRINT` ne pose que des drapeaux (`pause_command_sent`, `sd_paused`,
`must_pause_work`) car le fichier tourne en ligne ; le module stock efface
`record_tn_move_z` avant chaque impression. La reprise fait ces mêmes gestes.

## 4. Rejeu

- [FAIT] Les vraies lignes `!!` de 17:11 sont exactement celles tolérées.
- [FAIT] Le rejeu de 17:08 sur un faux Klipper reprend dans le même départ :
  purge au bac plateau descendu, consigne plateau remise, mémoire de levée à 0,
  « filament T1B pret (empty, repris) ».
- [FAIT] Un vrai bouchon (tampon jamais consommé) arrête toujours proprement.
- [FAIT] Les 23 tests du départ gardé rejoués sur ce module restent verts.

## 5. Compromis et limites

- `key845` et toute autre erreur restent un arrêt propre.
- [INCONNU] Ce que l'écran affiche après `key601` puis `key602`.
- [HYPOTHÈSE] `BOX_ERROR_CLEAR` efface l'erreur stock ; sinon arrêt avant de
  pousser.
- [INCONNU] Les effets de `DO_AFTER_PAUSE` si la pause stock en a lancé.
- Si `key837` n'atteint pas la console, la pause seule suffit comme indice ;
  les autres preuves restent exigées.
- L'attente `M190` compte dans les 180 s de la reprise.
- Les noms du CFS sont compilés : le préflight les rapporte seulement, le
  module refuse la reprise s'ils manquent.

## 6. Preuves

- `tests/test_start_load_recovery.py` : 90 tests, faux Klipper, dont le rejeu
  de 17:08 et les 23 tests du départ gardé.
- `tests/test_start_load_recovery_install.py` : 102 tests de pose sur une
  fausse imprimante : relevé, préflight sans écriture, noms constructeur,
  pose, départ neuf exigé après redémarrage, refus au repos, retour
  automatique, retour arrière exact, épinglage des paquets antérieurs.

## 7. Pose préparée

Une seule cible : `kctrl_start.py`, de `retained-start-v1` (`d112cf29...`) à
`start-load-recovery-v1`. 24 fichiers épinglés, dont la garde capteur V2.
Sauvegarde `/usr/data/k1-control-v1/backups/start-load-recovery-v1`.

Ordre : relevé en lecture seule à l'imprimante au repos, report du relevé dans
le manifeste, puis préflight, pose et validation au repos revérifié, avec
l'accord de Thomas, jamais pendant une impression. Retour arrière de ce paquet
avant celui de tout paquet antérieur.

## 8. Le 15 novembre à 11:28 : la même panne sur T1C

Thomas : filament bien introduit, purgé, sorti de la buse, et pourtant arrêt.

- [FAIT] 11:22:28 : départ de `_events_places_PLA_3h16m.gcode`, filament 1 du
  fichier sur T1C. 11:25:20 : capteur de tête à faux, tête vide.
- [FAIT] 11:25:19,842 : `T0` résolu en T1A sur T1C, chargement stock.
- [FAIT] 11:26:55 : « buffer is always full », capteur de tête à vrai, réessai
  stock.
- [FAIT] 11:28:25,172 : de nouveau « buffer is always full » ; 11:28:25,173 :
  `!! key837` avec `values [1, "C"]`.
- [FAIT] 11:28:26,134 : la garde du bac refuse la remontée de Z 35,01 à
  Z 4,80, tête à X210 Y291,5 ; 11:28:26,158 : « depart interrompu
  (start_paused) ».

Même enchaînement que le 12, autre bobine : ni la bobine ni la garde capteur
V2 ne sont en cause.

## 9. Fréquence, du 12 au 15 novembre

[FAIT] Sept chargements stock depuis une tête vide, lus dans les journaux
datés :

| Issue | Nombre | Quand |
| --- | --- | --- |
| Net au premier essai | 3 | 13/11 13:59, 13/11 22:16, 14/11 11:42 |
| Sauvé par le second essai stock | 2 | 12/11 01:45 (T1B), 13/11 19:20 (T1C) |
| Raté deux fois, départ arrêté | 2 | 12/11 17:11 (T1B), 15/11 11:28 (T1C) |

Intermittent : quatre chargements sur sept disent au moins une fois « buffer
is always full ».

## 10. Pose du 15 novembre

Sur l'accord de Thomas (« Oui, installe »), imprimante au repos.

État laissé par le départ arrêté : `print_stats` en erreur, pause stock
restée posée, tête référencée à X210 Y291,5 Z35,01, verrou de la garde du bac
posé, chauffes à zéro. L'installateur a refusé deux fois, à raison :
`BUSY paused`, puis `BUSY bin_guard_not_at_rest`.

- [FAIT] `CLEAR_PAUSE` : il ne baisse que les deux drapeaux de pause ;
  `is_paused` relu à faux.
- [FAIT] Avec un second accord de Thomas, sortie canonique du bac : `G90`
  puis `G1 Y273 F3000`. Tête relue à X210 Y273 Z35,02, plateau immobile,
  `bin_latched` à faux.
- [FAIT] 11:51 : `SURVEY_OK`, aucune dérive sur les 24 épingles, module à
  `d112cf29...`, les quatre noms du CFS présents. Manifeste passé à
  `surveyed: true` (`surveyed_on` 2026-11-15), 192 tests verts.
- [FAIT] 11:52 : `PREFLIGHT_OK` (24 épingles). 11:53 : `INSTALLED_IDLE_OK`
  puis `VALIDATED_IDLE_OK`. Klipper redémarré une fois, ni chauffe, ni
  filament, aucune trace d'erreur au journal.
- [FAIT] Relecture indépendante : module à `dbdb1554...`, mode 644 ;
  sauvegarde `module.before` à `d112cf29...` ; départ en révision
  `start-load-recovery-v1`, phase `idle`, aucune reprise, délai 180 s ; garde
  du bac, garde à froid et garde capteur V2 en place ; Moonraker sans
  composant en échec.

Collatéral du redémarrage : le filament est en tête, mais le CFS ne déclare
aucune route (son chargement a échoué) et la preuve « prise ratée attribuable »
vit dans le processus Klipper, donc elle a disparu. Le départ suivant aurait
refusé (`retained_identity_or_continuity_unproven`). [FAIT] Avec l'accord de
Thomas, `KCTRL_RETAINED_ADOPT SLOT=T1C`, sans mouvement, chauffe ni trame
CFS ; `retained_attribution` relu à `T1C`. Preuve de l'emplacement : les
lignes de 11:25:19 à 11:28:25 ci-dessus, aucune opération filament depuis.

À retenir pour une pose juste après un départ arrêté ainsi : lever la pause,
sortir la tête vers Y273 à hauteur constante, poser, puis réattribuer
l'emplacement en tête. Sans urgence, relancer d'abord (branche `recover`) et
poser à la fin de l'impression évite ces trois gestes.

## 11. Suite

1. Relire le premier départ où un chargement stock rate : la console doit
   dire « reprise automatique par purge au bac » puis « filament ... pret
   (empty, repris) ». La relance du 15 passe par `recover`, pas par la
   reprise.
2. [INCONNU] Affichage de l'écran après `key601` puis `key602`.
