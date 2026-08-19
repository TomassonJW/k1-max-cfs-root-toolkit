# HANDOFF

Date: 2026-08-19  
Phase: P2 / Gate G3 remains open after non-qualified A1/B/A2 session
Next operator: Codex for offline analysis and a separate passwordless-SSH G4 proposal; Thomas only for normal production printing

## Current state

The baseline acquisition, targeted source follow-up and physical session `20260819-185157-g3-aba` are complete. Thomas performed the prints and mechanical adjustments; Codex made no remote change. Raw captures remain local and ignored; only redacted inventories and conclusions are publishable.

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

Do not repeat A1/B/A2 or launch a fourth sacrificial print. Compare any future problematic multi-object G-code offline, then capture read-only evidence around a normal long production print and the next differently configured job.

Prepare passwordless SSH as a separate named mutation: dedicated key, exact remote file, backup and checksum, validation, rollback and no password retained. Do not bundle it with printer behaviour changes.

For the first behaviour overlay, keep five independent candidates: deterministic Z reference, explicit mesh policy, end-of-print nozzle cleaning plus pre-probe fallback, final pressure-advance ownership after CFS, and read-only observability. Select only one under a future G4.

## Stop conditions

Codex must stop without attempting a workaround if:

- the target host is ambiguous;
- root access fails;
- a required action may write to the printer;
- a command is not confidently read-only;
- the machine is printing or performing calibration;
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

The first six items, readable extension sources, protocol, private inputs and one non-qualified A1/B/A2 trace now exist. Compiled CFS behaviour and the final active pressure advance must still be measured rather than inferred.
