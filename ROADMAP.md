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

Status: **in progress — comparable trace protocol ready**

- reconstruct configuration includes and service ownership;
- build call graphs for startup, Z homing, levelling, tool changes, loading, cutting, flushing and resume;
- identify every write to temperature targets, Z offsets and meshes;
- compare two executions of identical G-code;
- separate mechanical repeatability, thermal effects and software resets.

Exit: Gate G3.

## P3 — Controlled experiments

Status: **not started**

- establish Z repeatability at defined thermal states;
- characterise meshes by plate and bed temperature;
- record timing and temperature timelines for CFS transitions;
- test hypotheses without combining unrelated changes;
- choose the first minimal intervention.

Exit: Gate G4 for one named change.

## P4 — Minimal override layer

Status: **not started**

Candidate work, subject to evidence:

- persistent fine Z correction applied after the last resetting operation;
- fast and reference startup wrappers;
- plate/temperature mesh profiles or adaptive mesh integration;
- parameterised CFS transition temperatures;
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
