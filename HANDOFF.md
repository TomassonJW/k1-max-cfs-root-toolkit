# HANDOFF

Date: 2026-08-22
Phase: P4 / première calibration V1 exécutée KO après deux meshes ; aucun mesh cible ni Z persistés
Next operator: annoncer l'écart d'autonomie, puis analyser le KO hors imprimante sans rerun

## Message obligatoire au début de la prochaine session

Dire clairement à Thomas, avant toute proposition d'exécution :

- **l'autonomie calibration n'est pas encore atteinte** : le runtime existe,
  mais les paramètres doivent encore être orchestrés hors interface réelle ;
- **l'autonomie production n'est pas encore atteinte** : Orca, `START_PRINT`,
  l'ancien `+0,27 mm` et les températures CFS ne sont pas encore basculés vers
  le nouveau contrat ;
- le chemin borné du premier Z est maintenant installé et validé à vide ; la
  prochaine gate effectuera la première calibration sous un contrat séparé et
  même sa réussite ne suffira pas à déclarer le pilotage quotidien autonome ;
- l'interface ne sera déclarée « nickel sans Codex » que lorsque Thomas pourra
  choisir les paramètres, lancer, comprendre le statut, enregistrer, annuler et
  restaurer depuis l'écran, puis imprimer normalement depuis Orca sans commande
  manuelle ni correction cachée.

Ne pas présenter Mainsail `v2.18.2`, la console ou les macros `KCTRL_*` comme
l'interface quotidienne terminée.

## CALIBRATION-PATH-V1 installé et validé

Thomas a nommé `G4-K1-CONTROL-CALIBRATION-PATH-V1` sans préfixe `GO`. Cette
instruction a sélectionné la préparation du lot ; elle n'a autorisé aucune
connexion ni mutation de la K1.

Le candidat ajoute un overlay séparé au runtime existant. Il impose une
descente centrale `5 → 2 → 1 → 0,5 → 0,3 → 0,2 → 0,15 → 0,1 mm`, ajuste le Z
seulement à la dernière hauteur, repositionne physiquement la buse à `0,1 mm`,
exige une confirmation puis une remontée de `5 mm` avant acceptation ou
annulation. Il n'a ni extrusion, ni chauffe, ni CFS, ni valeur Z par défaut.

La pose revue ajoute seulement
`/usr/data/printer_data/config/k1-control-calibration-path.cfg`, une inclusion
après le runtime puis un `RESTART` hôte. Sa validation appelle uniquement une
garde qui doit refuser et prouve que position, origine et cibles de chauffe ne
changent pas. Le rollback préserve entièrement le runtime installé. Détails :
`docs/17-g4-k1-control-calibration-path-v1.md` et ADR-005.

Le déployeur reste en `Plan` par défaut et toute action distante exige
`-Execute -Gate G4-K1-CONTROL-CALIBRATION-PATH-V1`. La pose n'est pas
autorisée avant le GO exact `GO G4-K1-CONTROL-CALIBRATION-PATH-V1` portant sur
le commit figé.

Thomas a envoyé ce GO. Le premier préflight a échoué avant mutation parce que
le candidat Base64 rendait la commande SSH trop longue pour Dropbear. Le
transport du parse Jinja passe maintenant par stdin, sans fichier distant. Le
préflight corrigé de la capture
`20260822-113503-g4-k1-control-calibration-path-v1` est vert : machine exacte,
`standby`, chauffes à zéro, runtime `ready=1`/`empty`, aucun Z accepté, overlay
absent, deux CFS `1.1.3`, fondation et parse Jinja exact conformes. Les axes
étaient référencés avant restart, état admis. Aucun backup, fichier, restart,
G-code ou état distant n'a été créé ou modifié.

La commande revue a changé après le GO consommé. Aucun `Deploy` n'a été lancé.
La prochaine autorisation doit renouveler exactement
`GO G4-K1-CONTROL-CALIBRATION-PATH-V1` sur le commit corrigé.

Thomas a renouvelé ce GO. La capture
`20260822-115608-g4-k1-control-calibration-path-v1` a obtenu un préflight frais
vert, créé et vérifié le backup, posé l'overlay et envoyé le `RESTART`. La
validation a toutefois interrogé le socket Klipper pendant sa transition et a
déclenché le rollback. Les fichiers ont été restaurés immédiatement ; le chemin
est resté un court moment chargé uniquement en mémoire car le `RESTART` du
rollback avait rencontré le même socket indisponible.

Après audit de cet état précis, l'action `Rollback` a été reprise sur le backup
exact et a obtenu `ROLLBACK_CALIBRATION_PATH_V1_OK`. Le préflight final a obtenu
`PREFLIGHT_CALIBRATION_PATH_V1_OK` : overlay absent, `printer.cfg` exact, axes
non référencés, chauffes à zéro, runtime `ready=1`/`empty`, deux CFS et fondation
conformes. Aucun mouvement, homing, chauffage, mesh ou état Z n'a eu lieu.

Le déployeur attend maintenant de façon bornée que le socket réponde avant la
lecture des objets après pose et avant le `RESTART` de rollback. Ce changement
de commande consomme l'autorisation précédente : une nouvelle pose exige encore
un GO exact renouvelé. Le préflight réel du déployeur corrigé est vert en
lecture seule.

Thomas a renouvelé une dernière fois le GO. La capture
`20260822-124207-g4-k1-control-calibration-path-v1` a obtenu le préflight frais,
`DEPLOY_CALIBRATION_PATH_V1_OK` puis
`VALIDATE_CALIBRATION_PATH_V1_OK`. Les quatre empreintes sont exactes, l'overlay
et son unique include sont retenus, le runtime reste `ready=1`/`empty`, les axes
sont non référencés, les chauffes à zéro et les deux CFS sont connectés. La garde
à vide a refusé sans changer position, origine Z ou cibles. Aucun chauffage,
homing, mouvement, extrusion, mesh, réglage ou enregistrement Z n'a été exécuté.

## Current state

Thomas rejected `G4-ZSAFE-START-V1` before deployment. Son `+0,27 mm` fixe, son
mesh `default` unique et son nettoyage manuel ne constituent pas un système
pérenne. Ce nom ne peut plus recevoir de GO. Les artefacts restants sont marqués
`rejected_never_deploy` et le macro échoue volontairement s'il est chargé.

La cible active est un produit cohérent `K1-CONTROL-V1` :

- interface quotidienne simple `K1 Control` ;
- Mainsail comme vue experte candidate, sur Moonraker épinglé et sécurisé ;
- réglage Z pendant une session de calibration, puis sauvegarde explicite ;
- Z accepté conservé après fin/redémarrage et invalidé par une nouvelle
  calibration de référence ;
- meshes par plaque et plage thermique, plus mesh adaptatif par travail ;
- ordre thermique/nettoyage/référence/mesh/Z/CFS/purge verrouillé ;
- températures dynamiques respectées sur les deux CFS ;
- profil Orca complet et versionné.

Le système est conçu et testé comme un tout, puis sera posé par étapes pour
garder un rollback simple. Aucun installateur communautaire n'est accepté tel
quel. Le post-traitement Orca actuel reste inchangé jusqu'à preuve complète de
son remplacement.

Le prototype complet hors imprimante est maintenant vert. L'écran parle à un
faux Moonraker sur `127.0.0.1` et ce faux service applique le moteur d'état
Python. Les 17 scénarios obligatoires passent, dont le blocage d'une purge trop
tôt, T0 vers T5 entre les deux CFS, l'invalidation Z et le rollback SHA-256.

La fondation V3 + PATHS-V1 a maintenant terminé son observation retenue. Thomas
a lancé manuellement l'impression normale à 12:48 et confirmé à la fin : qualité
correcte, un seul PLA, aucune intervention. Le premier observateur local a été
interrompu à 15:07 ; le journal persistant couvre le trou jusqu'à 18:43 sans
arrêt Klipper/MCU, perte de communication, trace Python ou erreur interne. Le
second observateur s'est fermé à 20:31:56 avec `exit_code=0`, puis la validation
en lecture seule a rendu `VALIDATE_PATHS_V1_OK`.

Le vrai adaptateur Moonraker reste fermé par défaut et reconnaît maintenant les
seules commandes structurées du candidat Z/mesh. Les sources Klipper exactes
`save_variables.py`, `gcode_macro.py`, `delayed_gcode.py` et `bed_mesh.py` ont
été copiées en lecture seule et vérifiées dans une capture privée ignorée.

Le runtime public `packages/k1-control-v1/z-mesh-runtime-v1/` ajoute une seule
structure persistante Z avec valeur précédente et contexte, les sessions
provisoires, l'invalidation, le préchauffage plateau/buse, le homing explicite,
les matrices 3–25 avec interpolation compatible, le commit mesh séparé et la
garde de mouvements bas. Il ne remplace pas `START_PRINT`, n'appelle aucun CFS
et n'extrude pas. Il est installé depuis la capture finale du 2026-08-22. Le
`save_variables.py` exact a été écarté ;
le stockage original contrôle le schéma et la somme, écrit en `0600`, synchronise,
remplace atomiquement et conserve une copie précédente sans restauration
silencieuse.

Thomas a envoyé le GO exact pour cette tranche. Le premier préflight s'est
arrêté sans mutation : les appels Python qui recevaient des arguments omettaient
le marqueur stdin `-`, donc Python cherchait un fichier nommé `0`. Les deux
formes concernées sont corrigées et un test dédié les verrouille. Le second
préflight, strictement en lecture seule, est vert sous la capture privée
`20260821-212431-g4-k1-control-z-mesh-runtime-v1`. Il confirme la machine au
repos, les chauffes à zéro, l'empreinte initiale, les cibles absentes, la
fondation et les deux CFS. Les axes sont encore référencés et `Base` est le mesh
transitoire actif, états admis avant le redémarrage hôte de la future pose.
Aucun fichier distant, backup, G-code, commande Klipper ou service n'a été
modifié. La commande revue ayant changé après le GO, le déploiement attend un GO
exact renouvelé.

Thomas a renouvelé ce GO. La capture
`20260821-213732-g4-k1-control-z-mesh-runtime-v1` a passé son préflight et
vérifié le backup, puis posé le runtime et redémarré l'hôte Klipper. La
validation a refusé l'état neuf : `integrity=empty` suivait la branche invalide
et laissait `ready=0`. La garde `K1_PRODUCTION_ASSERT_ARMED` n'a pas été appelée.

Le rollback automatique a retiré le runtime, mais son contrôle immédiat a vu T1
encore déconnecté. Le restart avait aussi normalisé seulement les espaces des
blocs générés `bed_mesh default` et `auto_addr`. Une complétion bornée a restauré
le backup exact sans autre restart. Le préflight final a confirmé le runtime
absent, le hash initial, Klipper `standby`, les axes non homés, les chauffes à
zéro, T1/T2 `1.1.3` et la fondation intacte. Aucun mouvement, chauffe, extrusion,
ordre CFS, calibration, impression, firmware restart ou reboot n'a eu lieu. Le
mesh transitoire `Base` a été perdu au restart ; `default` est de nouveau actif.

Le candidat offline possède désormais une branche `empty` prête pour calibrer
mais fermée à la production, une attente de stabilisation CFS de 60 secondes et
une seconde restauration du backup exact après le restart de rollback. Son hash
config est `3b0e5215d9bd58a343c57a681668ef1e466465980cceac3b1fd5944fec806f96`.
La suite exécute 96 tests : 95 passent localement et les 17 templates, dont le
rendu `empty`, passent sur le Python/Jinja exact de la K1.

Thomas a renouvelé une nouvelle fois le GO exact. La capture
`20260821-224828-g4-k1-control-z-mesh-runtime-v1` a passé son préflight et
vérifié le backup. Le runtime a été chargé, mais son état `ready` est resté à
zéro. Le journal a prouvé que le parseur G-code de cette K1 tronque
`K1_CONTROL_LOAD_STATE` en `K1`, commande inconnue : un chiffre placé au milieu
d'un nom étendu n'est pas accepté.

Le rollback a retiré le runtime et l'inclusion. Un `CXSAVE_CONFIG` Creality
tardif a ensuite normalisé les espaces des blocs générés. La comparaison locale
n'a trouvé aucun changement de valeur. Une complétion bornée a restauré le
backup exact sans restart, puis le préflight final a confirmé le runtime absent,
le hash initial, `default`, `standby`, axes non homés, chauffes à zéro, T1/T2
`1.1.3` et la fondation intacte. Aucun mouvement, homing, chauffe, extrusion,
ordre CFS, calibration, impression, firmware restart ou reboot n'a eu lieu.

Le candidat offline emploie désormais `KCTRL_*` dans le runtime, le stockage,
l'adaptateur et les futurs contrats Orca. Un test rejoue le parseur exact. Le
rollback attend la reconnexion CFS et une fenêtre silencieuse avant sa dernière
restauration, puis revérifie le hash après trois secondes. Les hashes courants
sont `1590b918dcdfe70e801c0be40fee4f19ab6b1e2dfa93936975b88aed5d4b1c79`
et `696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede` ;
la suite locale passe `98/98` et l'environnement exact de la K1 retourne
`K1_EXACT_RUNTIME_OK templates=17 commands=18` en mémoire.

Thomas a renouvelé une troisième fois le GO exact. La capture
`20260822-004338-g4-k1-control-z-mesh-runtime-v1` a passé le préflight, vérifié
le backup et chargé les objets `KCTRL_*`. Le démarrage différé a bien exécuté
`KCTRL_LOAD_STATE`, puis la première affectation texte a échoué avec
`Unable to parse 'empty' as a literal`. Le parseur Creality applique
`shlex.split` avant `ast.literal_eval` : `VALUE='empty'` perd ses guillemets et
arrive comme nom Python nu.

Le rollback automatique renforcé a retiré le runtime, attendu les deux CFS et
la fenêtre silencieuse, puis restauré et revérifié le backup exact. Le préflight
final confirme runtime absent, hash initial, `default`, `standby`, axes non
homés, chauffes à zéro, T1/T2 `1.1.3` et fondation intacte. Aucun mouvement,
homing, chauffe, extrusion, ordre CFS, calibration, impression, firmware
restart ou reboot n'a eu lieu.

Les 24 affectations texte utilisent désormais des littéraux protégés comme
`VALUE='"empty"'`. Le déployeur sauvegarde aussi son dernier snapshot avant
rollback si `ready` reste à zéro. Le hash config courant est
`dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113` ; le
module reste à
`696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede`.
La suite exécute 99 tests : 98 passent, et le contrôle exact en mémoire retourne
`K1_EXACT_RUNTIME_OK templates=17 commands=18 string_values=24`.

Thomas a renouvelé le GO exact. La capture
`20260822-011022-g4-k1-control-z-mesh-runtime-v1` a passé son préflight, vérifié
le backup et terminé par `DEPLOY_Z_MESH_RUNTIME_V1_OK`. Le runtime a chargé
l'état vide avec `ready=1`, puis `KCTRL_PRODUCTION_ASSERT_ARMED` a refusé comme
prévu sans changement de position, origine Z ou cible de chauffe.

La validation indépendante a d'abord vu une empreinte `printer.cfg` normalisée
par le `CXSAVE_CONFIG` différé de Creality. Le diff complet des copies privées
montre uniquement l'indentation des blocs générés `bed_mesh default` et
`auto_addr`, sans changement de valeur, section ou inclusion. La comparaison
normalisée obtient `PRINTER_CFG_NORMALIZED_EQUIVALENCE_OK`; le validateur épingle
les deux empreintes exactes et ne réécrit pas la machine.

La validation indépendante finale retourne
`VALIDATE_Z_MESH_RUNTIME_V1_OK`. État retenu : runtime installé, une inclusion,
`standby`, axes non homés, chauffes à zéro, `default`, T1/T2 `1.1.3`,
`ready=1`, `integrity=empty`, `accepted_z_valid=0`,
`block_reason=no_accepted_z`, `low_moves_armed=0` et fondation intacte. Aucun
mouvement, homing, chauffe, extrusion, ordre CFS, calibration, impression,
firmware restart, reboot ou rollback n'a eu lieu.
La suite finale exécute 100 tests : 99 passent et le contrôle Jinja local
ignoré reste couvert sur l'environnement exact de la K1.

La pile est figée : Moonraker MIPS embarqué au commit
`fccffa96c63ed77dc3953e18615e9fe9cd3d69ea`, nginx MIPS du même paquet et
Mainsail `v2.18.2`. Les trois archives ont été réellement assemblées et vérifiées
dans un bundle local temporaire. Aucun binaire communautaire n'est publié dans
Git.

Thomas a autorisé exactement `G4-K1-CONTROL-FOUNDATION-V1`. Son préflight réel
a confirmé la bonne machine, `standby`, les chauffes à zéro, T1/T2 connectés,
les ressources et l'absence des cibles. Il a ensuite détecté l'absence de
`logrotate` et de `/etc/logrotate.d`, prérequis obligatoire de V1. La pose s'est
arrêtée avant toute mutation ; V1 est définitivement fermée.

Thomas a ensuite autorisé exactement `G4-K1-CONTROL-FOUNDATION-V2`. Les essais
réels ont corrigé les écarts SCP/Dropbear, nginx/Buildroot, permissions,
fournisseur Moonraker, arrêt de service et origine WebSocket. Mainsail a chargé
le tableau de bord réel par tunnel, puis le test a prouvé que la version
`v2.18.2` ne sait pas créer ni utiliser un compte Moonraker. V2 a été rollbackée
et son nom est fermé. Aucun port LAN n'a été ouvert.

Thomas a choisi `CHOIX AUTH — NGINX`. Le remplacement
`G4-K1-CONTROL-FOUNDATION-V3` garde Moonraker en boucle locale et porte le compte
sur nginx. Le module MIPS requis est prouvé hors imprimante. Le mot de passe est
saisi deux fois en local, seul un hachage SSHA salé est transmis, les requêtes
anonymes doivent recevoir `401`, et les identifiants sont retirés avant le proxy
vers Moonraker. Les GO V3 renouvelés ont permis de corriger, avec rollback entre
chaque KO, le transport stdin, les droits `root:www-data` du fichier et du
dossier parent, puis la transition nginx vers l'écoute LAN. La capture finale
`20260821-015722-g4-control-foundation-v3` est installée et validée. Thomas a
créé puis vérifié son compte dans le vrai tableau de bord Mainsail. Moonraker
reste sur `127.0.0.1:7125` et Mainsail authentifié écoute sur `0.0.0.0:4409`.
Le raccourci `Ouvrir Mainsail K1 Max` sur le Bureau crée automatiquement le
tunnel SSH sécurisé et ouvre Mainsail sans commande manuelle.

Après connexion, Moonraker a affiché deux avertissements : son data path crée
`/usr/data/k1-control-v1/state/config` et `state/gcodes`, alors que la pile
Creality active utilise `/usr/data/printer_data/config` et
`/usr/data/printer_data/gcodes`. Une inspection distante bornée et sans mutation
a confirmé que les deux dossiers Moonraker sont présents et vides. Le code exact
installé produit ces avertissements lorsque les chemins ne désignent pas les
mêmes dossiers. La connexion Mainsail → Moonraker → Klipper fonctionne ; seule
l'intégration du gestionnaire de fichiers est incomplète.

Il ne faut pas appliquer la suggestion générique de modifier
`[virtual_sdcard]`. La correction retenue devait garder les chemins Creality,
relier les racines Moonraker selon la méthode officielle, rendre `config` non
modifiable par l'API et traiter explicitement le pouvoir d'écriture restant sur
`gcodes`. Le rapport public est dans
`experiments/p4/20260821-moonraker-path-warnings-read-only-report.md`.

Après revue du document 15, du déployeur et des tests, Thomas a renouvelé
exactement `GO G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1`. La capture
`20260821-111001-g4-control-foundation-v3-paths-v1` a obtenu un préflight vert,
sauvegardé l'état initial, posé les deux liens attendus et redémarré uniquement
Moonraker. Le dernier message du wrapper local a été perdu après deux heartbeats ;
Codex n'a pas relancé la mutation. Les preuves finales étaient présentes et une
commande séparée en lecture seule a obtenu `VALIDATE_PATHS_V1_OK`.

L'API expose maintenant `config=r` vers `/usr/data/printer_data/config` et
`gcodes=rw` vers `/usr/data/printer_data/gcodes`. Moonraker ne rapporte aucun
avertissement, Klipper est prêt et `standby`, les chauffes sont à zéro, les axes
ne sont pas homés, les deux CFS `1.1.3` sont connectés, nginx et les interfaces
Creality sont intacts. Aucun G-code, mouvement, chauffe, calibration, impression,
redémarrage imprimante ou rollback n'a été exécuté.

Le contrat, l'architecture et la comparaison des outils sont dans les documents
10, 11, 13, 14 et ADR-004. Les essais V2 et les tentatives V3 en KO ont
rollbacké uniquement les nouveaux chemins de fondation. La pose V3 finale
conserve les deux services dédiés et les ports prévus. Aucun profil Orca actif
ni comportement d'impression n'a été modifié.

Une lecture distante bornée a relevé environ 209 Mio de RAM totale, 118 Mio
disponibles, Python 3.8.2, 4,2 Gio libres et aucun port/processus Moonraker. La
marge mémoire impose une pile minimale et un test de durée ; le rapport public
anonymisé est dans `inventory/redacted/20260820-control-foundation-capacity/`.

Un écran `K1 Control` sans dépendance, un moteur d'état Python pur, un faux
Moonraker, le contrat Orca et la matrice exécutable sont présents sous
`prototype/`, `orca/` et `tests/`. Les vues bureau/mobile et les actions
calibration, sauvegarde, redémarrage et invalidation ont été vérifiées sans
erreur JavaScript. La suite courante exécute 131 tests : 129 passent et deux
contrôles Jinja locaux sont ignorés. Les 17 templates du runtime installé ont
déjà passé le Python/Jinja exact de la K1. L'overlay installé a également passé
son parse exact en mémoire avant toute écriture. Les noms de
commandes des deux lots sont contrôlés contre le parseur Creality exact.

## Preuves historiques utiles

The private intake is ready under
`inventory/raw/user-inputs/20260820-full-system-audit/`. Its instructions request
an Orca printer-config bundle, existing 3MF projects and G-codes, exact custom
G-code text, photos/notes and any already-held recovery artefact. Everything in
that path is ignored by Git.

Thomas has now supplied the active individual Orca profiles, the Z
post-processor, five 3MF projects and six candidate G-codes. The two private
capture batches contain 24 and 13 files respectively; every copy passed a local
SHA-256 comparison and no source file was changed.

Offline inspection selects P1-SINGLE, P2-FIVE-OBJECTS and
P3-ONE-MERGED-OBJECT as the first bounded session. P2 and P3 share all 639
recorded settings, estimated duration, material use and layer count; their
useful difference is five separate objects versus one assembled object. Ironing
is active on all three and does not invalidate the first-layer comparison.

Thomas supplied a corrected `P5-CFS-ONE-CHANGE` containing one intended `T0` to
`T1` transition. Its private copy and hashes are recorded; the first alternating
version remains private evidence only.

Passive session `20260820-154056-p123` is complete. It captured P1, P2, P3, P4,
two P5 attempts and P1 PETG. The trace ended with all heater targets at zero;
Codex stopped only the passive observer after Thomas confirmed completion.

The decisive Z finding is runtime evidence, not an inference from the file. On
P4, the visible Z stays at `0.00` through the stock startup and only becomes
`+0.27 mm` when the post-processor executes afterward. The current workaround
cannot protect the preceding purge. Live Z clicks call `Z_OFFSET_APPLY_PROBE`,
but P3 and PETG both end by applying the exact inverse and preparing `0.000` for
persistence. P1 PETG finished at `+0.38 mm`, `+0.11 mm` above its file baseline,
before that value was erased.

P2 and P3 share all 639 recorded settings and produced no reported visible
difference between separate and assembled objects. One `+0.010 mm` live Z click
occurred during P3, so this is not a fully untouched pair. It does not disprove
the historical large shifts and gives no evidence that object count alone
triggers them.

The first P5 attempt had three pauses after a likely filament break and is
excluded. The second completed without a pause. Its nozzle targets were
`115 -> 220 -> 205 -> 220 -> 0 °C`: the startup override is confirmed, while
the final `220 °C` cannot distinguish G-code from CFS ownership because both
request the same value.

The baseline acquisition, targeted source follow-up, physical session `20260819-185157-g3-aba` and separate `G4-SSH-KEY` deployment are complete. Thomas performed the prints and mechanical adjustments. Codex changed only root SSH access by adding one dedicated public key; no printer behaviour, service or configuration was changed. Raw captures remain local and ignored; only redacted inventories and conclusions are publishable.

Passwordless SSH is now available through local alias `k1max-root`. It selects the dedicated ECDSA P-256 key and forbids password fallback. Two independent final connections passed. A future password prompt must be treated as a failure and diagnosed, not shown to Thomas as a normal step.

Read-only session `20260819-215124-long` started from standby, captured one complete long production job and stopped automatically after the machine returned to standby. The observer used one persistent Klipper subscription and followed only new log data. It sent no print, movement, heating, calibration or configuration command.

This session closed the pressure-advance observability gap: startup applied `0.044`, then the print file restored `0.03`, which remained active through the CFS refill and to the end. The CFS did not overwrite pressure advance during this refill.

The automatic equivalent-PLA refill did overwrite temperature. Runout paused the print, selected another PLA slot and resumed in about 2 minutes 54 seconds. The resumed target returned to `220 °C` and stayed there until Thomas manually restored `190 °C`. Visible Z origin remained `+0.27 mm` throughout, with no live correction reported.

The same defect occurs during startup. The job supplies `190 °C` for the first layer and later uses `195 °C`, but the first CFS tool operation reports that it cannot read the purge speed and falls back to a `220 °C` purge. The file only regains control after the CFS load and purge. Thomas judged the final part broadly correct; granular ironing remains a separate OrcaSlicer-tuning hypothesis.

Read-only follow-up proved that the production file contains no temperature
command at `220 °C`. The generic PLA entry used by the CFS stores `220 °C`, while
per-slot state stores material type and colour but not a slot-specific
temperature or pressure advance. During refill, stock `RESUME` restores
`195 °C`, then the file reader replays the new physical tool and the compiled
CFS module reapplies `220 °C` afterward.

The static `G4-CFS-TEMP-PLA` candidate was rejected by Thomas before deployment.
It hard-coded Geeetech PLA and `190/195 °C`, so it did not meet the production
need. Its deployable files were removed from `main`; no printer file or service
was changed.

The accepted requirement is now explicit: while a print is active, G-code or
Thomas owns nozzle temperature. Equivalent refill preserves the active target.
An intentional material change receives the next tool's temperature from the
G-code. The CFS database may not silently replace either value.

Codex has permanent authority to complete all normal Git and GitHub operations for this repository, including push, pull-request management, fusion into `main` and cleanup, without requesting another `GO`. This authority does not replace the printer mutation gates.

## Confirmed acquisition outcomes

- firmware `2.3.5.34`, Buildroot 2020.02.1, Linux 4.4.94 MIPS;
- manufacturing identity and runtime selector report S12 structure 0;
- `/etc/ota_info` still reports S11 and is classified as inconsistent OTA metadata;
- active configuration and four includes mapped;
- CFS temperature value `Tn_extrude_temp: 220` identified;
- active saved Z offset at zero and one transient historical `-0.025` identified;
- startup, CFS, homing and levelling macro chains indexed;
- readable `CX_*`, `CXSAVE_CONFIG`, `G28` and PR Touch implementations captured and mapped;
- CFS `BOX_*` implementation identified as a compiled `box_wrapper` module;
- `G28` confirmed to establish Z through five PR Touch samples, their median and `self_z_offset`;
- persistent storage and large Klipper log footprint documented;
- no remote write performed.

## FIRST-CALIBRATION-V1 préparé hors imprimante

Le candidat `G4-K1-CONTROL-FIRST-CALIBRATION-V1` est maintenant présent sous
`packages/k1-control-v1/first-calibration-v1/`. Il n'installe aucun nouveau
fichier : son pilote local orchestre seulement les commandes déjà installées,
par checkpoints séparés.

Le contexte est figé : `PEI_TEXTURED_A` ID `1`, plateau `55 °C`, buse `140 °C`,
stabilisation `200 s`, nettoyage stock borné jusqu'à `180 °C`, homing après
nettoyage, deux meshes `6 × 6` Lagrange sur `5–295 mm` et seuil absolu maximum
`0,025 mm` sur les 36 points. Un KO s'arrête sans troisième mesh automatique.

Le second mesh qualifié pourra être enregistré sous
`k1_p001_t055_r001_n06x06`, puis la session Z partira du seed neutre explicite
`0,0 mm` et suivra les paliers déjà installés. Chaque mouvement bas reste une
action distincte. L'acceptation exige confirmation humaine et remontée de
`5 mm`.

Le mode `Plan` de `scripts/run-k1-control-first-calibration-v1.ps1` est purement
local. Les actions distantes exigent le GO exact, la capture privée et les
checkpoints précédents. `Cancel` ferme le Z provisoire et conserve le mesh ;
`Rollback` restaure le `printer.cfg` exact et l'état Z vide tout en conservant
le runtime et le chemin installés. Détails : document 18 et ADR-006.

Thomas a ensuite envoyé le GO exact. La capture
`20260822-140602-g4-k1-control-first-calibration-v1` a passé le préflight, créé
et vérifié le backup, puis terminé la préparation et le premier mesh. Le second
mesh a été exécuté une seule fois et sa qualification est KO : maximum
`0,062125 mm`, moyenne `0,018049 mm`, seuil `0,025 mm` sur 36 points.

L'arrêt prévu a coupé les chauffes. Aucun troisième mesh, profil persistant,
session Z ou état Z n'a été produit. Un contrôle final en lecture seule a
confirmé la base exacte, le profil cible absent, le stockage Z absent,
`standby` et les cibles à zéro avant de signaler les axes `xyz` encore
référencés. Le GO est consommé et ne couvre aucun rerun.

## Next bounded mission

Analyser hors imprimante l'écart des deux matrices et décider avec Thomas s'il
faut préparer un protocole révisé distinct. Ne lancer aucun troisième mesh,
nouvelle chauffe, homing, mouvement ou écriture Z sous le GO consommé.

La gate précédente est close avec `DEPLOY_CALIBRATION_PATH_V1_OK` et
`VALIDATE_CALIBRATION_PATH_V1_OK` sous la capture
`20260822-124207-g4-k1-control-calibration-path-v1`.

Autorisation actuelle : **LECTURE_ET_ANALYSE_HORS_IMPRIMANTE**. L'overlay et son
include restent installés ; le backup de la capture KO reste sur la K1.

La bascule Orca reste une gate ultérieure unique : wrappers de travail côté
machine, trois champs Orca et retrait du post-traitement doivent changer
ensemble, après validation de ce runtime.

Le post-traitement PHP/Orca `+0,27 mm`, le Start G-code et le G-code de changement
de filament restent strictement inchangés. Aucune commande Z, mesh, chauffe,
homing ou calibration ne peut être envoyée sous le GO consommé. Une future
campagne exigera un protocole distinct revu et sa propre autorisation exacte.

## Stop conditions

Codex must stop without attempting a workaround if:

- the target host is ambiguous;
- root access fails;
- a required action may write to the printer;
- a command is not confidently read-only;
- the machine is printing or calibrating before an unplanned operation; the already authorised passive observer may remain connected during the job;
- a captured file contains secrets or unclear proprietary content;
- the observed hardware or firmware contradicts the assumed target.

The S11/S12 configuration-selection conflict is resolved in favour of S12 structure 0. Firmware recovery remains blocked until an exact image is matched despite the stale S11 OTA metadata.

## Information to bring back for analysis

- redacted manifest;
- active configuration entry point and complete include graph;
- macro names and paths for startup, homing, levelling and CFS operations;
- process/service map;
- mount and persistence map;
- relevant redacted logs;
- one G-code file that reproduced the bad first layer, kept private until reviewed;
- ideally, two logs from identical G-code executions with different Z outcomes.
- Orca `.orca_printer` export for the actual K1 Max profile;
- exact custom start/end/layer/tool-change and Z workaround text;
- existing representative 3MF/G-code for multi-object, hot-bed and CFS cases;
- already-held recovery image/procedure reference.

The first six items, readable extension sources, protocol, private inputs, one non-qualified A1/B/A2 trace and one complete long-production trace now exist. Compiled CFS internals remain opaque, but its refill temperature effect and the final active pressure advance have now been measured directly.
