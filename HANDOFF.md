# HANDOFF

Date: 2026-08-20
Phase: P2 / CFS temperature package prepared locally; next-job Z comparison pending
Next operator: Thomas decides whether to open named deployment `G4-CFS-TEMP-PLA`; Codex otherwise prepares the next passive observer

## Current state

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

Candidate `G4-CFS-TEMP-PLA` is now prepared locally and tested against exact
copies of the three active configuration files. It lowers the fixed CFS
operation temperature to `195 °C`, requires an explicit Geeetech PLA `190/195`
contract and adds a bounded post-resume guard for a previously memorised
`190 °C` target. It fails closed for every other material or temperature. It has
not been copied to the printer and no service has been restarted.

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

## Next bounded Codex mission

Do not repeat A1/B/A2 or the completed long production print. Open a separate passive session around the next genuinely different or multi-object production job. This is intended to test the reported post-job Z instability without consuming plastic solely for diagnosis.

The separate local CFS preparation is complete. The next printer-side action is
a human gate decision: either Thomas explicitly says `GO G4-CFS-TEMP-PLA` while
the machine is idle, or the candidate remains local. Deployment must follow
`overrides/cfs-temperature-contract/DEPLOYMENT.md` exactly and stop on any source
hash mismatch. It must not absorb pressure, ironing, Z, mesh or nozzle cleaning.

Keep every later printer behaviour change behind its own named G4. Do not treat the completed SSH convenience change as permission to modify Z, mesh, cleaning, CFS or services.

For the first behaviour overlay, keep five independent candidates: deterministic Z reference, explicit mesh policy, end-of-print nozzle cleaning plus pre-probe fallback, final pressure-advance ownership after CFS, and read-only observability. Select only one under a future G4.

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

The first six items, readable extension sources, protocol, private inputs, one non-qualified A1/B/A2 trace and one complete long-production trace now exist. Compiled CFS internals remain opaque, but its refill temperature effect and the final active pressure advance have now been measured directly.
