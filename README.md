# K1 Max CFS Root Toolkit

Unofficial, evidence-driven tooling and documentation for taking controlled ownership of a rooted Creality K1 Max equipped with the classic K1 CFS upgrade and multiple CFS units.

> **Status:** P4. V3, PATHS-V1 et le runtime Z/mesh sont installés et validés.
> Le runtime est vide et fermé à la production. Le chemin borné du premier Z
> est préparé hors imprimante sous `G4-K1-CONTROL-CALIBRATION-PATH-V1`, mais
> n'est ni installé ni autorisé.

## Target configuration

The initial investigation targets one real machine:

- Creality K1 Max, older hardware generation;
- classic K1 CFS upgrade kit;
- two chained CFS units;
- Unicorn nozzle and upgraded toolhead hardware;
- confirmed printer firmware `2.3.5.34`; manufacturing identity and runtime selection indicate S12 structure 0, while stale OTA metadata still names S11;
- OrcaSlicer as the usual slicer, with Creality Print retained where proprietary CFS integration remains useful.

The repository must not generalize findings to every K1/K1 Max/CFS revision until hardware and firmware compatibility have been demonstrated.

## Problems being investigated

- Z reference or effective Z offset changes between prints;
- the same Z problem existed before the bed springs were installed, so the springs are not treated as its root cause;
- automatic calibration can invalidate an otherwise correct first-layer adjustment;
- startup sequences are long, opaque and sometimes redundant;
- CFS filament-change sequences can override requested nozzle temperatures;
- slicer G-code alone cannot reliably control later firmware macros;
- configuration changes need to survive reboot and remain recoverable.

## Intended outcome

A predictable printer that can reboot and run repeated jobs with:

- a reproducible Z reference;
- an explicit, persistent and traceable fine Z correction;
- bed meshes associated with known plate and temperature conditions;
- deliberate **fast** and **reference** startup paths;
- controlled CFS loading, cutting, flushing and resume temperatures;
- working two-CFS operation;
- upload and routine control from OrcaSlicer when technically possible;
- stock compatibility retained where it still provides value;
- backup, diff, deployment, validation and rollback procedures.

## Strategy

1. Root the printer manually.
2. Preserve the stock state.
3. Run a strictly read-only inventory and acquisition pass.
4. Analyse configuration, services, macros, logs and real execution order.
5. Test explicit hypotheses with reproducible protocols.
6. Design one coherent control product before installing isolated fixes.
7. Prove its Z state, mesh, start sequence, CFS temperatures, Orca contract and
   interfaces against an offline simulator.
8. Install it in small reversible slices only after the complete product is
   ready and each named mutation has its own explicit gate.
9. Replace larger parts of the stack only if evidence shows that targeted
   ownership layers cannot solve the problem.

This is deliberately **not** an “install every helper script” project.

## Safety boundary

The printer is production hardware, not a disposable development environment.

Until the repository gate explicitly changes:

- no remote write to the printer;
- no package installation;
- no firmware change or downgrade;
- no service restart or reboot initiated by an agent;
- no replacement of `START_PRINT`, CFS macros or central configuration;
- no destructive shell command;
- no publication of raw backups, credentials, network details, serial identifiers or proprietary firmware files.

Read [`AGENTS.md`](AGENTS.md), [`GATES.md`](GATES.md) and the protocol applicable
to the mission before any SSH session. The active product contract is defined in
[`docs/10-systeme-pilotage-perenne.md`](docs/10-systeme-pilotage-perenne.md).
Le candidat actuellement revu est décrit dans
[`docs/17-g4-k1-control-calibration-path-v1.md`](docs/17-g4-k1-control-calibration-path-v1.md).
Son nom seul ne vaut pas GO et sa pose future ne lancerait aucune calibration.

## Repository map

- `AGENTS.md` — binding operating rules for Codex and any other agent;
- `STATE.md` — current real state and next safe action;
- `ROADMAP.md` — phased plan;
- `GATES.md` — conditions required before progressing;
- `DECISIONS.md` — durable project decisions and rationale;
- `HANDOFF.md` — current operational handoff;
- `docs/` — acquisition, redaction, diagnostics and recovery procedures;
- `design/` — machine-readable offline product and safety contracts;
- `prototype/` — dependency-free local UI and state model using synthetic data only;
- `experiments/g3/` — public templates for private comparable trace sessions;
- `prompts/` — bounded prompts for Codex missions;
- `machine/` — publishable machine manifests and schemas;
- `inventory/redacted/` — sanitised evidence suitable for Git;
- `overrides/` — original, reviewable override candidates; presence in Git never authorises deployment;
- `scripts/` — original acquisition, validation, deployment and rollback tooling;
- `tests/` — reproducible checks and fixtures.

Raw captures and backups belong in ignored local directories such as `private/`, `backups/` and `inventory/raw/`.

## Evidence rule

A value or procedure is considered validated only when:

- the machine, hardware, firmware and thermal conditions are known;
- the test can be repeated;
- the expected and observed result are recorded;
- no major regression is detected;
- the rollback path is known.

A negative result is useful evidence. The unchanged Z issue before and after the spring modification is recorded as such.

## Community scope

The long-term aim is to publish reusable diagnostics, original scripts, original macros, patches, redacted traces and compatibility findings. The repository must not redistribute Creality firmware, opaque binaries, secrets or large copied configuration sets without a clear right to do so.

## Licence

No reuse licence has been selected yet. Until a `LICENSE` file is added, do not assume permission to redistribute repository content outside normal GitHub viewing and contribution workflows.
