# HANDOFF

Date: 2026-08-19  
Phase: P0  
Next operator: Thomas, then Codex

## Current state

The public repository baseline is being established. No SSH acquisition or printer mutation has occurred through this project.

## Next safe action for Thomas

1. On the printer, record the visible printer firmware, board/revision indication if exposed, and both CFS firmware versions.
2. Enable the supported root account manually.
3. Do not install a helper script, Mainsail, Fluidd, packages or a different firmware.
4. Do not paste the root password into GitHub, Notion or ChatGPT.
5. Configure a local SSH target or temporary environment variable outside the repository.
6. Clone the repository locally.

## Next bounded Codex mission

Use `prompts/01-codex-read-only-acquisition.md` after Gate G1 is satisfied.

Expected outputs:

- ignored raw capture under `private/` or `inventory/raw/`;
- redacted machine manifest;
- command log without credentials;
- configuration and service inventory;
- checksums and source-path map;
- sanitisation report;
- updated `STATE.md` and `HANDOFF.md`;
- draft pull request containing only publishable artefacts.

## Stop conditions

Codex must stop without attempting a workaround if:

- the target host is ambiguous;
- root access fails;
- a required action may write to the printer;
- a command is not confidently read-only;
- the machine is printing or performing calibration;
- a captured file contains secrets or unclear proprietary content;
- the observed hardware or firmware contradicts the assumed target.

## Information to bring back for analysis

- redacted manifest;
- active configuration entry point and complete include graph;
- macro names and paths for startup, homing, levelling and CFS operations;
- process/service map;
- mount and persistence map;
- relevant redacted logs;
- one G-code file that reproduced the bad first layer, kept private until reviewed;
- ideally, two logs from identical G-code executions with different Z outcomes.
