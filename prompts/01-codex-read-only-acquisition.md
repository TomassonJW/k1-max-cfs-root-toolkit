# Codex mission — read-only K1 Max acquisition

Use this prompt only after Gate G1 is satisfied.

---

Work in the local clone of `TomassonJW/k1-max-cfs-root-toolkit`.

Your mission is to inventory and acquire the current stock state of one rooted Creality K1 Max with two classic CFS units. This mission is **strictly read-only on the printer**.

Before doing anything:

1. Read `AGENTS.md`, `STATE.md`, `GATES.md`, `HANDOFF.md`, `docs/01-read-only-acquisition.md` and `docs/02-data-classification-and-redaction.md` in full.
2. Inspect `git status -sb` and do not mix unrelated work.
3. Confirm that Gate G1 is actually satisfied.
4. Obtain the target only from an existing SSH config alias or local environment variable such as `PRINTER_HOST`. Never commit or print credentials.
5. Confirm with a harmless identity command that the target is the expected printer. Stop on any mismatch.

Hard constraints:

- Do not write anything to the printer.
- Do not install, update, restart, stop, kill, reboot, remount, heat, move, home, calibrate, extrude or launch a print.
- Do not use remote redirection, `tee`, `sed -i`, `rm`, `mv`, `cp`, `chmod`, `chown`, `ln`, package managers, installers or uploads.
- Do not add an SSH key to the printer.
- Do not copy the whole root filesystem.
- Fail closed when command side effects are uncertain.

Workflow:

1. Create branch `agent/read-only-stock-acquisition-YYYYMMDD`.
2. Create a unique capture ID.
3. Create ignored local raw directories under `private/` or `inventory/raw/`.
4. Maintain a local command log containing commands and results but no connection secret.
5. Inventory system, board, firmware, both CFS units, mounts, persistence, processes, services, listeners, configuration entry points, include relationships and relevant log paths.
6. Copy relevant existing files from printer to local raw storage only.
7. Calculate and record checksums.
8. Build the startup, homing, levelling and CFS macro/file inventory without changing them.
9. Sanitise a publishable subset according to the data-classification document.
10. Run a secret scan and manually sample the redacted output.
11. Commit only original documentation, manifests, hashes and redacted artefacts whose publication is justified.
12. Update `STATE.md` and `HANDOFF.md` with confirmed facts, unknowns, files withheld and the next safe action.
13. Open a draft pull request. Do not merge it.

Expected public outputs:

- a completed redacted machine manifest;
- a command log without credentials or private target data;
- path/checksum inventory;
- process/service and persistence maps;
- configuration include graph;
- list of relevant macro definitions and callers;
- sanitisation report;
- no raw backup or proprietary firmware payload.

Final report in plain language:

- what you inspected;
- what you copied locally;
- what you published;
- proof that no remote write occurred;
- exact firmware/hardware facts discovered;
- contradictions with current assumptions;
- blockers;
- recommended next analysis step.

Do not begin a second mission or propose an installation during this run.
