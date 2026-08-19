# HANDOFF

Date: 2026-08-19  
Phase: P2 / passive long-production capture active
Next operator: Thomas launches and watches a normal useful print; Codex only observes

## Current state

The baseline acquisition, targeted source follow-up, physical session `20260819-185157-g3-aba` and separate `G4-SSH-KEY` deployment are complete. Thomas performed the prints and mechanical adjustments. Codex changed only root SSH access by adding one dedicated public key; no printer behaviour, service or configuration was changed. Raw captures remain local and ignored; only redacted inventories and conclusions are publishable.

Passwordless SSH is now available through local alias `k1max-root`. It selects the dedicated ECDSA P-256 key and forbids password fallback. Two independent final connections passed. A future password prompt must be treated as a failure and diagnosed, not shown to Thomas as a normal step.

Read-only session `20260819-215124-long` started from standby. Initial active pressure advance is `0.03`, visible Z homing origin is `+0.27 mm`, and both heaters are untargeted near `31 °C`. The observer uses one persistent Klipper subscription and follows only new log data. It cannot send a print, movement, heating, calibration or configuration command.

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

Do not repeat A1/B/A2 or launch a fourth sacrificial print. Let Thomas use the active session for a normal long production print. When it is complete and the machine has returned to standby, close the observer and retain the raw capture. Then open a separate passive session around the next differently configured or multi-object job.

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

The first six items, readable extension sources, protocol, private inputs and one non-qualified A1/B/A2 trace now exist. Compiled CFS behaviour and the final active pressure advance must still be measured rather than inferred.
