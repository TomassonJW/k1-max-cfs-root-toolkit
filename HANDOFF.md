# HANDOFF

Date: 2026-08-20
Phase: P3 / architecture corrected, full offline control prototype started
Next operator: Codex continues the offline prototype; no printer-side gate is pending

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

Le contrat, l'architecture et la comparaison des outils sont dans les documents
10, 11 et ADR-004. Aucun fichier n'a été écrit sur l'imprimante, aucun service
n'a été redémarré et aucun profil Orca actif n'a été modifié.

Une lecture distante bornée a relevé environ 209 Mio de RAM totale, 118 Mio
disponibles, Python 3.8.2, 4,2 Gio libres et aucun port/processus Moonraker. La
marge mémoire impose une pile minimale et un test de durée ; le rapport public
anonymisé est dans `inventory/redacted/20260820-control-foundation-capacity/`.

Un premier écran `K1 Control` sans dépendance et un moteur d'état Python pur sont
présents sous `prototype/`. Ils n'utilisent que des données synthétiques. Les
vues bureau/mobile et les actions calibration, sauvegarde, redémarrage et
invalidation ont été vérifiées dans un navigateur local sans erreur JavaScript.
La suite hors imprimante passe 37 tests.

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

Continuer le prototype complet hors imprimante :

1. utiliser le relevé de capacité maintenant acquis pour sélectionner les
   versions minimales Moonraker/Mainsail ;
2. épingler cette pile et reproduire son installation dans un paquet
   local inspectable, sans exécuter l'installateur constructeur ;
3. connecter le moteur et l'écran existants à un adaptateur Moonraker simulé ;
4. produire le contrat Orca départ/fin/changement d'outil et ses fixtures ;
5. passer la matrice de séquence et des deux CFS ;
6. préparer seulement ensuite un nouveau G4 nommé, avec backup, checksums,
   test haut sans extrusion, critères OK/KO et rollback.

La prochaine étape ne demande aucun test physique. Aucune installation
Mainsail/Moonraker, aucun macro, aucun profil Orca et aucun paramètre CFS ne doit
être modifié sur les systèmes actifs.

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
