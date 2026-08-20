# HANDOFF

Date: 2026-08-20
Phase: P2 / complete-system intake and analyser-first Level A design
Next operator: Codex inventories the private Orca/G-code intake and builds the offline ownership timeline; no printer deployment is available

## Current state

A complete-system audit now proposes a strengthened stock route: preserve
firmware `2.3.5.34`, Creality interfaces and CFS, analyse first, then introduce
original reversible overlays one change class at a time. BTT Eddy is a measured
fallback, not a prerequisite. SimpleAF or an open MMU is a later research route,
not a safe solution for next week's production need.

The private intake is ready under
`inventory/raw/user-inputs/20260820-full-system-audit/`. Its instructions request
an Orca printer-config bundle, existing 3MF projects and G-codes, exact custom
G-code text, photos/notes and any already-held recovery artefact. Everything in
that path is ignored by Git.

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

The static `G4-CFS-TEMP-PLA` candidate was rejected by Thomas before deployment.
It hard-coded Geeetech PLA and `190/195 °C`, so it did not meet the production
need. Its deployable files were removed from `main`; no printer file or service
was changed.

The accepted requirement is now explicit: while a print is active, G-code or
Thomas owns nozzle temperature. Equivalent refill preserves the active target.
An intentional material change receives the next tool's temperature from the
G-code. The CFS database may not silently replace either value.

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

After Thomas sends `DEPOT_AUDIT_PRET`, do not connect to the printer first.
Inventory and sanitise the private inputs locally. Parse the Orca profiles and
G-code into one ordered timeline covering Z, mesh, homing, temperatures,
pressure advance, CFS, purge, pause, refill, tool change and end of job.

Produce the target Orca contract, a rule report and a decision on wrapper
coverage versus targeted compiled-owner replacement. Then prepare, but do not
deploy, the first named G4 safety packet with backup, hashes, no-extrusion
validation and rollback.

Do not repeat A1/B/A2 or the completed long production print. A separate passive
session may accompany the next genuinely different or multi-object useful job;
it must not consume plastic solely for diagnosis.

No temperature deployment is ready. The next bounded mission is read-only and
offline: map every temperature write through startup, `T0`–`T15`, both physical
CFS units, purge, equivalent refill, intentional material change and resume.
Then decide whether wrappers cover every path or whether the compiled owner must
be replaced. The decision must satisfy
`docs/07-dynamic-cfs-temperature-requirements.md` without hard-coded material or
temperature.

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
- Orca `.orca_printer` export for the actual K1 Max profile;
- exact custom start/end/layer/tool-change and Z workaround text;
- existing representative 3MF/G-code for multi-object, hot-bed and CFS cases;
- already-held recovery image/procedure reference.

The first six items, readable extension sources, protocol, private inputs, one non-qualified A1/B/A2 trace and one complete long-production trace now exist. Compiled CFS internals remain opaque, but its refill temperature effect and the final active pressure advance have now been measured directly.
