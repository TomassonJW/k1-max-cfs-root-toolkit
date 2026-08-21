# G4 control foundation V3 PATHS-V1 — runtime report

Date: 2026-08-21
Capture: `20260821-111001-g4-control-foundation-v3-paths-v1`
Gate: exact renewed GO received after package review
Result: installed and independently validated

## Scope actually changed

- replaced the two proven-empty Moonraker data roots with symbolic links to the
  active Creality roots;
- installed the reviewed PATHS-V1 `moonraker.conf`;
- restarted only `/etc/init.d/S56k1_control_moonraker`.

No `printer.cfg`, `[virtual_sdcard]`, macro, Orca profile, Z, mesh, temperature,
CFS firmware or print behaviour was changed. No G-code, heater, movement,
homing, calibration, extrusion, print or printer reboot was requested.

## Pre-change proof and backups

The repeated real-machine preflight was green: exact MIPS/S12/firmware baseline,
V3 services and ports present, two initial roots real and empty, both warnings
present exactly once, Klipper `standby`, targets zero, axes not homed and both
CFS units connected on `1.1.3`.

Backups were created and verified before Moonraker was stopped:

| Backup | SHA-256 |
|---|---|
| `moonraker.conf.before` | `7e9cc023da9addc62f492f6cddf6ab901dbc9e97821e8306b05cfbd1b6e576f7` |
| `empty-roots.before.tar` | `7bd189adecdd54f40013a9ee1b247825fd75c76e9fc48b5195757f12f40a4e83` |

## Final verified state

| Check | Result |
|---|---|
| config link | `/usr/data/printer_data/config` |
| gcodes link | `/usr/data/printer_data/gcodes` |
| installed config SHA-256 | `fef837a1acaa59af400ac63c244df78dec6e70a71e1707d61f242f56cb1c7fba` |
| Moonraker config permission | `r` |
| Moonraker gcodes permission | `rw` |
| Moonraker warnings | none |
| failed Moonraker components | none |
| Klipper | connected, ready and `standby` |
| heater targets | nozzle `0`, bed `0` |
| homed axes | none |
| CFS T1/T2 | connected, `1.1.3`, four slots each |
| available RAM | `111224 KiB` |
| swap used | `40 KiB` |

The listener, nginx authentication, Creality process and resource gates all
passed. Raw listener details and private runtime evidence remain ignored.

## Wrapper incident and recovery discipline

The guarded local command emitted two heartbeats, then its deferred terminal
cell disappeared without returning the final line. The deployment was not
restarted. The child process had ended and the complete final evidence set was
present. A separate read-only `Validate` action then returned
`VALIDATE_PATHS_V1_OK`, and independent `readlink` and SHA-256 checks matched the
expected final state.

This was a terminal/wrapper observability loss, not a repository or printer KO.
No rollback was required.

## Remaining risk and next action

The authenticated Mainsail file API still has `rw` access to the real G-code
root. This is intentional and documented; validation did not call any write or
print endpoint.

The next mission is the eight-hour observation of this final retained state,
including one normal print selected and started manually by Thomas through the
existing trusted Creality/Orca workflow.
