# HANDOFF

Date: 2026-08-19  
Phase: P2 / Gate G3 preparation after targeted source acquisition
Next operator: Codex for local trace design, then Thomas for a future controlled trace gate

## Current state

The baseline acquisition `20260819-1627-k1max-stock` and targeted follow-up `20260819-1726-k1max-targeted-sources` are complete. No printer mutation occurred. Raw captures remain local and ignored; only redacted inventories and conclusions are publishable.

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

Work locally from both ignored captures to prepare the two-run comparison protocol required by G3. Do not reconnect for further source hunting: `BOX_*` is compiled, and `ACCURATE_HOME_Z` is not literally defined in the readable Python tree. Instrument or observe these boundaries only in a future explicitly approved trace phase.

Do not deploy or prepare a combined patch.

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

The first six items and the readable extension sources now exist in private/redacted form. Comparable execution traces and one private reproducing G-code remain missing. Compiled CFS behaviour must be measured, not inferred from unavailable source.
