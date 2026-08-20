# ROADMAP

## P0 — Repository and safety baseline

Status: **completed**

- define scope and non-goals;
- separate public artefacts from private raw data;
- establish agent prohibitions and progression gates;
- prepare read-only acquisition and recovery prerequisites.

Exit: Gate G1.

## P1 — Root and stock acquisition

Status: **completed**

- enable root manually;
- verify machine, board, printer firmware and both CFS firmware versions;
- inventory processes, services, mounts, configuration and log paths;
- copy relevant files from printer to local private storage;
- calculate checksums;
- publish only sanitised manifests and evidence.

Exit: Gate G2.

## P2 — Behaviour map and diagnosis

Status: **completed on 2026-08-20 — Gate G3 passed for offline preparation**

- reconstruct configuration includes and service ownership;
- build call graphs for startup, Z homing, levelling, tool changes, loading, cutting, flushing and resume;
- identify every write to temperature targets, Z offsets and meshes;
- compare two executions of identical G-code;
- separate mechanical repeatability, thermal effects and software resets.
- ingest the real Orca profiles, custom G-code and already-produced projects;
- build an offline timeline showing which component owns Z, mesh, temperature,
  pressure advance and CFS state at each step;
- decide whether dynamic wrappers cover every CFS temperature path or whether
  the compiled owner must be replaced.

Exit: Gate G3.

## P3 — Controlled experiments

Status: **in progress — first Z-safety package to be designed offline**

- establish Z repeatability at defined thermal states;
- characterise meshes by plate and bed temperature;
- record timing and temperature timelines for CFS transitions;
- test hypotheses without combining unrelated changes;
- choose the first minimal intervention.
- simulate useful startup, refill, tool-change, pause, cancel and end scenarios
  before requesting another physical run;
- prepare a no-extrusion, high-clearance validation for the first safety change.

Exit: Gate G4 for one named change.

## P4 — Minimal override layer

Status: **not started**

Candidate work, subject to evidence:

- no low-Z movement or purge before the final Z reference, mesh policy and
  effective first-layer correction are active;
- persistent fine Z correction applied after the last resetting operation;
- fast and reference startup wrappers;
- plate/temperature mesh profiles or adaptive mesh integration;
- parameterised CFS transition temperatures;
- one public Orca start/end/tool-change contract with no hidden Z workaround;
- deploy, validate and rollback scripts;
- Moonraker/Fluidd/Mainsail only where they add observable value without breaking CFS behaviour.

Exit: Gate G5.

## P5 — Production validation

Status: **not started**

- cold boot and three consecutive prints on a known plate without manual Z correction;
- same-material CFS changes;
- cross-CFS change between CFS 1 and CFS 2;
- at least one cross-material transition policy;
- OrcaSlicer upload and control path;
- retained Creality compatibility where required;
- measured startup-time improvement with no first-layer regression.

Exit: stable V1 baseline and tagged release.

## P6 — Community hardening

Status: **not started**

- document hardware and firmware compatibility matrix;
- add automated redaction and config tests;
- translate key documentation if useful;
- accept external reports through reproducible evidence templates;
- select and add an explicit licence;
- publish versioned releases without proprietary payloads.
