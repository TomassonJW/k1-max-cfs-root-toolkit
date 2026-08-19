# HANDOFF

Date: 2026-08-19  
Phase: P2 / Gate G3 preparation
Next operator: Codex for local analysis, then Thomas for a future trace gate

## Current state

The public repository baseline and read-only acquisition `20260819-1627-k1max-stock` are complete. No printer mutation occurred. Raw captures remain local and ignored; redacted outputs are under `inventory/redacted/20260819-1627-k1max-stock/`.

## Confirmed acquisition outcomes

- firmware `2.3.5.34`, Buildroot 2020.02.1, Linux 4.4.94 MIPS;
- firmware board identity `CR4CU220812S11` versus active configuration header `CR4CU220812S12`;
- active configuration and four includes mapped;
- CFS temperature value `Tn_extrude_temp: 220` identified;
- active saved Z offset at zero and one transient historical `-0.025` identified;
- startup, CFS, homing and levelling macro chains indexed;
- persistent storage and large Klipper log footprint documented;
- no remote write performed.

## Next bounded Codex mission

Work locally from the ignored capture. Build a source-level map for `BOX_*`, `CX_*`, `ACCURATE_HOME_Z` and `CXSAVE_CONFIG`, determine which components can write or replace Z and temperature state, and prepare the two-run comparison protocol required by G3.

Do not reconnect to the printer unless a named evidence gap cannot be resolved locally. Do not deploy or prepare a combined patch.

## Stop conditions

Codex must stop without attempting a workaround if:

- the target host is ambiguous;
- root access fails;
- a required action may write to the printer;
- a command is not confidently read-only;
- the machine is printing or performing calibration;
- a captured file contains secrets or unclear proprietary content;
- the observed hardware or firmware contradicts the assumed target.

The last condition is currently active as an investigation item: S11 and S12 metadata conflict. It blocks mutation, not local analysis.

## Information to bring back for analysis

- redacted manifest;
- active configuration entry point and complete include graph;
- macro names and paths for startup, homing, levelling and CFS operations;
- process/service map;
- mount and persistence map;
- relevant redacted logs;
- one G-code file that reproduced the bad first layer, kept private until reviewed;
- ideally, two logs from identical G-code executions with different Z outcomes.

The first six items now exist in private/redacted form. Comparable execution traces and one private reproducing G-code remain missing.
