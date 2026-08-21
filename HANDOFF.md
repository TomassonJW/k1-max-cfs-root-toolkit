# HANDOFF

Date: 2026-08-21
Phase: P4 / V1 and V2 closed; V3 foundation and PATHS-V1 installed and validated
Next operator: build the offline `G4-K1-CONTROL-Z-MESH-RUNTIME-V1` package

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
erreur JavaScript. La suite complète passe 57/57 contrôles.

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

## Next bounded mission

Observer pendant huit heures l'état final V3 + PATHS-V1. Cette fenêtre comprend
une impression normale choisie et lancée manuellement par Thomas avec le flux
Creality/Orca déjà approuvé. Codex peut observer passivement, mais ne transmet
aucun G-code et ne lance ni impression, ni chauffe, ni mouvement, ni calibration.

Le post-traitement PHP/Orca `+0,27 mm`, le Start G-code et le G-code de changement
de filament restent strictement inchangés.

Après cette observation, une nouvelle gate nommée sera nécessaire avant la
première tranche qui modifiera Z, mesh, nettoyage, purge, CFS, macros ou Orca.

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
