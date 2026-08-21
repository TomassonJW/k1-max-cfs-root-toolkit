# G4 control foundation V3 PATHS-V1 — offline report

Date: 2026-08-21
Candidate: `G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1`
Printer mutation: none

## Authority result

Thomas sent the exact candidate GO before the repository contained an exact
PATHS-V1 patch, command set, backup, validation or rollback. G4 requires those
items before approval, so the GO was recorded but not consumed. This report
covers local preparation and classified read-only preflight only.

## Prepared change

The candidate keeps the installed V3 artefact immutable and adds a separate
PATHS-V1 Moonraker configuration. Its only semantic configuration difference is:

```ini
[file_manager]
enable_config_write_access: False
```

The dedicated deployer is limited to:

- replacing the two proven-empty Moonraker directories with exact symbolic
  links to the active Creality `config` and `gcodes` roots;
- atomically replacing the pinned Moonraker configuration;
- restarting only the dedicated Moonraker service;
- restoring the original configuration and empty directories on the first KO.

No G-code upload, deletion, start, script, heater, movement, homing,
calibration, CFS command or printer restart exists in its execution path.

## Read-only real-machine preflight

The guarded preflight completed with `PREFLIGHT_OK`. It confirmed:

- MIPS, S12 structure 0 and firmware `2.3.5.34`;
- the exact installed V3 `moonraker.conf` SHA-256
  `7e9cc023da9addc62f492f6cddf6ab901dbc9e97821e8306b05cfbd1b6e576f7`;
- both Moonraker roots are still real empty directories;
- both Creality roots are real directories and active `printer.cfg` exists;
- Moonraker, authenticated nginx and the Creality ports/processes are present;
- Klipper is `standby`, no filename is active, heater targets are zero and axes
  are not homed;
- both CFS units are connected, version `1.1.3`, with four slots each;
- Moonraker currently reports `config=rw` and `gcodes=rw`;
- each of the two expected path warnings is present exactly once;
- about 107 MiB of RAM remained available and swap use was zero in this sample.

Private listener and runtime details remain in the ignored local evidence
directory and are not committed.

## Offline gates

- PowerShell plan/parser gate: green;
- dedicated PATHS-V1 tests: 7/7 green;
- complete repository suite after integration: 64/64 green;
- printer mutation: not attempted.

## Remaining gate

A renewed exact `GO G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1` is required after
review of the concrete package. The deployer will repeat the full preflight
immediately before any backup or mutation and will rollback on the first
mismatch.
