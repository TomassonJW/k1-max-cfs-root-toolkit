# AGENTS.md — K1 Max CFS Root Toolkit

## Mission

Build a reproducible, evidence-driven and reversible way to diagnose and improve a rooted Creality K1 Max with the classic CFS upgrade and two chained CFS units.

The printer is production hardware. It is never treated as a disposable sandbox.

## Current authority and phase

The active phase is **P4 — V1 and V2 are closed; V3 and its separate
`G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1` correction are installed, validated and
retained after the completed observation; two renewed
`G4-K1-CONTROL-Z-MESH-RUNTIME-V1` deployments reached runtime validation and
rolled back completely; the command-parser and rollback-quiescence correction
is now offline and requires another exact review and GO**.

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
are restored, and no further printer mutation is authorised until the renamed
`KCTRL_*` package and strengthened rollback receive a new exact GO.

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
