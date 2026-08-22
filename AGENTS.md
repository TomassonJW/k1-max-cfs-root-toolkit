# AGENTS.md — K1 Max CFS Root Toolkit

## Mission

Build a reproducible, evidence-driven and reversible way to diagnose and improve a rooted Creality K1 Max with the classic CFS upgrade and two chained CFS units.

The printer is production hardware. It is never treated as a disposable sandbox.

## Current authority and phase

The active phase is **P4 — V1 and V2 foundations are closed; V3, PATHS-V1, the
Z/mesh runtime and CALIBRATION-PATH-V1 are installed and validated;
FIRST-CALIBRATION-V1 stopped KO; FIRST-CALIBRATION-V2 is installed and validated;
CALIBRATION-UI-V1 is prepared offline but not authorised; production remains
closed**.

Thomas authorised V1, but the mandatory preflight proved that `logrotate` was
absent. V1 is closed and must never be deployed. Thomas later authorised V2;
real attempts reached a working tunnel-only Mainsail, then proved that Mainsail
`v2.18.2` cannot satisfy the Moonraker-account gate. Every V2 attempt was
rolled back and V2 is closed. V3 keeps the bounded BusyBox syslog, moves the
account boundary to nginx, and is installed. The separate PATHS-V1 package was
created only after its first exact GO arrived, so that GO was not consumed: G4
requires exact reviewed files, commands, backups and rollback before approval.
Thomas then renewed the exact GO after review. PATHS-V1 was deployed under
capture `20260821-111001-g4-control-foundation-v3-paths-v1` and independently
validated. No further printer mutation is authorised; classified read-only
observation remains allowed. The retained observation covered the manual normal
print and its local-monitor gap through the persistent Klipper log, then ended
with `VALIDATE_PATHS_V1_OK`. The runtime preflight correction adds the required
Python stdin marker to two remote commands; it changes no runtime payload, but
G4 still requires a renewed exact GO before deployment because the reviewed
command changed after the first approval. The later renewed GO was consumed by
capture `20260821-213732-g4-k1-control-z-mesh-runtime-v1`. The runtime rejected
its empty store, and the first rollback check raced CFS reconnection. The runtime
was corrected offline, then a further renewed GO was consumed by capture
`20260821-224828-g4-k1-control-z-mesh-runtime-v1`. The exact Creality parser
proved that embedded digits truncate every intended `K1_*` command to `K1`, so
the delayed state load never ran. The rollback then raced Creality's delayed
`CXSAVE_CONFIG`; a bounded exact-backup restoration completed it without another
restart. The runtime is absent again, the exact baseline hash and full health
are restored. A third renewed GO was consumed by capture
`20260822-004338-g4-k1-control-z-mesh-runtime-v1`. The `KCTRL_*` boot command
ran, but Creality's `shlex` layer stripped the single quotes from
`VALUE='empty'`; `ast.literal_eval` then rejected the bare name. The strengthened
rollback completed automatically and the exact baseline and full health were
confirmed again. All runtime text assignments now keep an inner quoted Python
literal, and the deployer preserves a not-ready snapshot. No further printer
mutation is authorised until this changed package receives a new exact GO.
Thomas then renewed the exact GO. Capture
`20260822-011022-g4-k1-control-z-mesh-runtime-v1` obtained the fresh preflight,
`DEPLOY_Z_MESH_RUNTIME_V1_OK` and `VALIDATE_Z_MESH_RUNTIME_V1_OK`. A delayed
Creality `CXSAVE_CONFIG` changed only indentation in generated `bed_mesh` and
`auto_addr` blocks; the exact diff and normalized comparison proved no value or
include change, so the validator pins both reviewed hashes instead of rewriting
the printer. The runtime is retained with `ready=1`, `integrity=empty`,
`accepted_z_valid=0` and `low_moves_armed=0`. No further printer mutation,
including calibration, is authorised by the completed runtime gate.

Le candidat séparé `G4-K1-CONTROL-CALIBRATION-PATH-V1` est maintenant préparé
hors imprimante. Il ajoute un overlay original pour évaluer le premier Z par
une descente centrale bornée, sans extrusion et sans valeur Z cachée. Sa pose
prévue ne ferait qu'ajouter l'include et recharger l'hôte Klipper ; elle ne
chauffe, ne home, ne bouge et n'écrit aucun état. Le nom envoyé sans le préfixe
`GO` a sélectionné cette mission de préparation mais n'autorise aucune mutation.
Une pose exige encore la revue du commit figé puis le GO exact
`GO G4-K1-CONTROL-CALIBRATION-PATH-V1`. La première calibration restera une
gate différente, `G4-K1-CONTROL-FIRST-CALIBRATION-V1`.

Thomas a ensuite envoyé le GO exact. Le premier préflight a joint la K1 puis a
échoué avant toute écriture parce que le candidat Base64 dépassait la ligne de
commande acceptée par Dropbear. Le parse Jinja passe désormais par stdin, sans
fichier distant. Le préflight corrigé de la capture `20260822-113503` est vert
et confirme la base exacte, le runtime vide, les chauffes à zéro, deux CFS et
l'overlay absent. Aucun déploiement n'a été lancé. La commande revue ayant
changé après le GO consommé, la pose exige un nouveau GO exact sur le commit
corrigé.

Thomas a renouvelé ce GO. La capture
`20260822-115608-g4-k1-control-calibration-path-v1` a passé le préflight, créé le
backup exact, posé l'overlay et envoyé le `RESTART`. La validation a interrogé
le socket Klipper pendant sa transition et le premier `RESTART` du rollback a
rencontré le même état. L'action `Rollback` reprise sur le backup exact a obtenu
`ROLLBACK_CALIBRATION_PATH_V1_OK`, puis le préflight final a prouvé la base
exacte, l'overlay absent, les axes non référencés, les chauffes à zéro, le
runtime vide, deux CFS et la fondation conformes. Aucun mouvement, homing,
chauffage, mesh ou état Z n'a eu lieu. Le déployeur attend maintenant le socket
de façon bornée après pose et avant le restart du rollback. Cette commande ayant
changé après le GO consommé, aucune nouvelle pose n'est autorisée avant un
nouveau GO exact. Le préflight réel du déployeur corrigé est vert en lecture
seule.

Thomas a renouvelé une dernière fois le GO. La capture
`20260822-124207-g4-k1-control-calibration-path-v1` a obtenu le préflight frais,
`DEPLOY_CALIBRATION_PATH_V1_OK` puis
`VALIDATE_CALIBRATION_PATH_V1_OK`. L'overlay et son unique include sont retenus
avec leurs empreintes exactes. Le runtime reste `ready=1`/`empty`, les axes sont
non référencés, les chauffes demandées sont à zéro, deux CFS et la fondation sont
conformes, et la garde à vide refuse sans changement de position, origine Z ou
cible. Aucun chauffage, homing, mouvement, extrusion, mesh, réglage ou
enregistrement Z n'a été exécuté. `CALIBRATION-PATH-V1` est clos ; aucune autre
mutation n'est autorisée. La gate suivante
`G4-K1-CONTROL-FIRST-CALIBRATION-V1` a ensuite été préparée hors imprimante :
plaque `PEI_TEXTURED_A`, `55/140 °C`, stabilisation `200 s`, nettoyage stock
borné à `180 °C`, deux meshes `6 × 6` Lagrange, seuil `0,025 mm`, aucun rerun
automatique et chemin Z par checkpoints.

Thomas a ensuite envoyé le GO exact sur le commit figé. La capture
`20260822-140602-g4-k1-control-first-calibration-v1` a obtenu le préflight, le
backup vérifié, `PREPARE_FIRST_CALIBRATION_V1_OK` et
`MESH1_FIRST_CALIBRATION_V1_OK`. Le second mesh a été mesuré une seule fois puis
refusé : écart maximal `0,062125 mm` pour un seuil de `0,025 mm` et moyenne
`0,018049 mm` sur 36 points. Le pilote a coupé les chauffes et s'est arrêté sans
troisième mesh, persistance, session Z ou écriture Z. Le contrôle final en
lecture seule a confirmé la base persistante exacte, le stockage Z absent,
`standby` et les cibles à zéro avant de s'arrêter, comme attendu, sur les axes
encore référencés. Ce GO est consommé et n'autorise aucun rerun.

L'analyse hors imprimante a ensuite préparé
`G4-K1-CONTROL-FIRST-CALIBRATION-V2`. Thomas a donné le GO exact. La capture
`20260822-160948-g4-k1-control-first-calibration-v2` a exécuté exactement six
meshes à `55/140 °C`, `200 s`, `6 × 6` Lagrange. Les deux médianes indépendantes
sont acceptées : moyenne absolue `0,010788694 mm`, RMS `0,013996452 mm` et
maximum `0,034352 mm`. Le profil robuste `k1_p001_t055_r001_n06x06` est
persisté ; aucun septième passage n'a eu lieu.

Le premier commit a rencontré un faux KO du pilote : l'endpoint `update_mesh`
a chargé la matrice robuste sans redémarrer Klipper et a conservé le homing
`xyz`. Le diff exact ne contenait que le profil transitoire attendu. Une reprise
bornée a revérifié backup, hashes, matrice et runtime vide, puis exécuté la
commande de commit déjà revue. Le pilote attend désormais le comportement réel
avec un test dédié.

Thomas a repris le chemin Z devant la K1 sous le même GO V2. Une pile de dix
épaisseurs a évalué la cale papier à `0,09 mm`. Les pas provisoires de
`−0,01 mm` ont trouvé une friction nette à `−0,05 mm`; le retour d'un pas à
`−0,04 mm` a rendu la cale libre et vise le jeu final de `0,10 mm`. Thomas a
confirmé ce constat. Le chemin a parqué la buse, enregistré atomiquement
`−0,04 mm` et coupé les chauffes. La validation finale est verte : stockage
`ok`, `accepted_z_valid=1`, `session_active=0`, chemin `committed`, profil
robuste présent, `standby`, cibles zéro, deux CFS et fondation conformes.

Le premier `Validate` a rencontré un faux KO local : il cherchait l'en-tête
persistant non commenté, alors que Klipper génère `#*# [bed_mesh ...]`. Le
contrôle corrigé et testé reconnaît ce format réel ; la relance en lecture seule
a obtenu `VALIDATE_FIRST_CALIBRATION_V2_OK`. FIRST-CALIBRATION-V2 est close et
son GO ne couvre aucun rerun, la pose UI ou la production.

Le candidat séparé `G4-K1-CONTROL-CALIBRATION-UI-V1` est préparé hors
imprimante. Il ajoute un composant au Moonraker épinglé et une page statique
`/k1-control/` pour choisir plaque, températures, stabilisation, matrice,
interpolation et seed Z, puis enregistrer, annuler et restaurer sans console.
Le flux robuste reste côté serveur, la chauffe et la stabilisation sont
annulables, et un backup complet peut restaurer `printer.cfg` et l'état Z. Sa
pose future redémarrerait Moonraker seulement et ne lancerait aucune
calibration. Elle exige une revue figée puis son propre GO exact séparé.

La revue post-calibration a corrigé le candidat UI sans toucher à la K1 : le
préflight et le contrôleur acceptent maintenant uniquement les phases fermées
`idle`, `committed` et `cancelled`; le transport Moonraker utilise le `curl`
Creality sans options incompatibles et encode les espaces par `+`. Le préflight
compile et importe en mémoire les deux sources avec le Python Moonraker `3.8.2`
exact, par stdin et sans fichier distant. Le déployeur est lui-même épinglé dans
le manifeste. Le préflight réel en lecture seule a obtenu
`PREFLIGHT_CALIBRATION_UI_V1_OK`. Aucune pose ni aucun restart n'a eu lieu ; le
GO exact UI reste obligatoire.

Thomas a ensuite donné le GO exact. La capture
`20260822-192821-g4-k1-control-calibration-ui-v1` a obtenu le préflight vert et
le backup exact, puis le premier transfert a échoué avant toute pose :
l'OpenSSH Windows récent a tenté SFTP alors que Dropbear ne fournit pas
`/usr/libexec/sftp-server`. Le rollback automatique a retiré les chemins
candidats, restauré la base exacte, redémarré seulement Moonraker et le
préflight final a de nouveau obtenu `PREFLIGHT_CALIBRATION_UI_V1_OK`. Aucun
chauffage, homing, mouvement, mesh ou Z n'a eu lieu. Le transport utilise
désormais le SCP historique explicite `scp -O` et le rollback nettoie aussi le
staging exact. Le déployeur et son empreinte ayant changé après le GO consommé,
le paquet corrigé a obtenu un nouveau `PREFLIGHT_CALIBRATION_UI_V1_OK` en
lecture seule. Aucune nouvelle pose n'est autorisée avant un nouveau GO exact
`GO G4-K1-CONTROL-CALIBRATION-UI-V1` sur le commit corrigé.

Thomas demande que chaque prochaine reprise commence par un état explicite de
l'autonomie, sans confondre le runtime installé avec une interface terminée :

- **autonomie calibration** : pas encore atteinte ; le candidat d'interface
  couvre ces choix et actions hors imprimante, mais il doit encore être posé,
  validé et réussir une campagne complète sans console ni assistance Codex ;
- **autonomie production** : pas encore atteinte ; elle exige en plus la bascule
  atomique Orca/`START_PRINT`, le retrait prouvé du `+0,27 mm`, la propriété des
  températures CFS et la validation G5 sans intervention Codex.

Au début de la prochaine session, l'agent doit rappeler ces deux statuts,
indiquer la prochaine gate unique et expliquer ce qu'elle rendra autonome. Il
ne doit jamais annoncer « interface prête » sur la seule présence de Mainsail
ou des macros `KCTRL_*`.

Authority order:

1. an explicit decision from Thomas;
2. this repository's `GATES.md`, `STATE.md`, `DECISIONS.md` and current handoff;
3. observed machine state, captured files, logs and checksums;
4. original scripts, tests and documented results in this repository;
5. external documentation, which must not silently override evidence from the exact machine revision.

When instructions conflict, fail closed and report the conflict.

## Hard prohibitions during P0/P1

Until Gate G4 is explicitly opened for a named change, an agent must not:

- write, create, replace, rename or delete any file on the printer;
- install or update a package, helper script, service, firmware or dependency;
- run a firmware downgrade or recovery flash;
- restart, stop, kill, enable or disable any process or service;
- reboot or power-cycle the printer;
- remount a filesystem or change permissions, ownership or links;
- run remote commands using output redirection, `tee`, `sed -i`, `rm`, `mv`, `cp`, `chmod`, `chown`, `ln`, `mount`, package managers or an installer;
- upload a file to the printer through SSH, SCP, Moonraker, Creality APIs or another path;
- modify `printer.cfg`, included configuration, `START_PRINT`, homing, levelling or CFS macros;
- launch a print, extrusion, heater command, movement or calibration on its own initiative;
- persist an SSH key or credential on the printer;
- commit raw captures, backups, credentials, private network data, cloud identifiers, serial numbers or unreviewed vendor files.

A command being reversible in theory does not make it authorised.

## Allowed work during P0/P1

An agent may:

- inspect the local repository and create ignored local working directories;
- connect to the exact host supplied by Thomas;
- run read-only commands listed or classified in `docs/01-read-only-acquisition.md`;
- copy files **from the printer to the local workstation** without changing the remote source;
- calculate hashes locally or remotely using read-only tools;
- build an inventory, dependency map and macro call graph;
- sanitise local copies;
- commit only reviewed, redacted and legally publishable artefacts;
- update repository documentation, tests and the current handoff;
- stop immediately when a path, command or side effect is uncertain.

## SSH and secret handling

- Receive the printer target through an existing SSH config alias or a local environment variable such as `PRINTER_HOST`.
- Never write an IP address, password, token, SSID, MAC address or private hostname into tracked files.
- Do not echo credentials into a shell history, log, prompt or report.
- Prefer an already configured local SSH agent. Creating persistent access on the printer is outside P0/P1.
- Record the executed command class and result, not secret-bearing connection strings.

## Acquisition discipline

Before connecting:

1. read `STATE.md`, `GATES.md`, `HANDOFF.md` and `docs/01-read-only-acquisition.md`;
2. inspect `git status` and avoid mixing unrelated changes;
3. create a unique capture ID;
4. create raw storage only under ignored local paths;
5. verify that the printer is idle and that Thomas has completed the manual root step.

During acquisition:

- execute the smallest command set needed;
- log each command and whether it succeeded;
- avoid broad recursive reads until targeted paths are known;
- preserve timestamps and calculate checksums where practical;
- never infer that two similarly named files have the same role.

After acquisition:

- retain raw material outside Git;
- produce a redaction report;
- commit only sanitised outputs;
- update `STATE.md` and `HANDOFF.md` with facts, unknowns and the next safe action;
- open a draft pull request, review its publishable scope, then complete the normal GitHub integration without requiring another operator approval.

## Mutation discipline after G4

A future mutation task requires all of the following:

- exact scope and expected effect;
- source and destination paths;
- pre-change backup with checksum;
- reviewed diff;
- validation command or physical test;
- explicit rollback procedure;
- explicit authorisation from Thomas for that named change;
- one change class at a time.

Prefer original overlay files and wrappers over editing manufacturer files in place. Never combine root setup, helper installation, macro replacement, CFS changes and Z tuning into one deployment.

## Git discipline

### Permanent Git and GitHub authority for this repository

Thomas permanently delegates to Codex the complete Git and GitHub lifecycle for this project. Codex may inspect, branch, stage, commit, fetch, pull, rebase, merge, push, tag, create or update pull requests, mark them ready, merge them into `main`, and clean up merged mission branches without requesting another `GO` or human validation.

This standing authority applies to repository integration only. Gates G0–G5 and named deployment approvals continue to govern every action that can affect the printer. Platform-enforced safety controls also remain applicable.

Codex must still preserve unrelated work, worktrees and useful history; keep secrets, raw captures and unreviewed vendor material out of Git; avoid force-push or published-history rewrites unless Thomas explicitly names that exceptional operation; and verify both local and remote state after integration.

- Use a dedicated branch for each acquisition, experiment or deployment.
- Keep commits narrow and readable.
- Never commit secrets or unreviewed raw files, even temporarily.
- Do not rewrite published history or force-push without explicit instruction.
- Record vendor file hashes and paths; do not publish copied vendor content unless redistribution is clearly permitted.
- Update tests and documentation with each behaviour-changing patch.

## Reporting

Reports must distinguish:

- confirmed facts;
- measured results;
- hypotheses;
- unverified assumptions;
- changes made;
- changes not made;
- validation performed;
- remaining risks;
- next safe action.

Never report a printer change unless the remote state was actually modified and verified.
