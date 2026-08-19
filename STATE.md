# STATE

Last updated: 2026-08-19

## Current phase

**P2 — local diagnosis preparation after read-only acquisition**

The repository baseline and one targeted stock acquisition are complete. The printer was accessed in read-only mode on 2026-08-19. No remote write, restart, movement, heating or calibration occurred.

## Confirmed facts

- Target machine: older-generation Creality K1 Max.
- Printer firmware: `2.3.5.34`, Buildroot 2020.02.1, Linux 4.4.94 on MIPS.
- Firmware metadata reports board `CR4CU220812S11`.
- The active `printer.cfg` header reports `CR4CU220812S12`; this contradiction is unresolved.
- Classic K1 CFS upgrade installed.
- Two CFS units are in use.
- Both CFS units show firmware `1.1.3` on the printer UI; no machine version file has yet confirmed it.
- Active configuration entry point: `/usr/data/printer_data/config/printer.cfg`.
- `printer.cfg` includes `sensorless.cfg`, `gcode_macro.cfg`, `printer_params.cfg` and `box.cfg`.
- `START_PRINT` invokes the CFS, homing, nozzle-cleaning and levelling chains after slicer input.
- `box.cfg` sets `Tn_extrude_temp` to `220`.
- The active saved Z offset is `0.000`; one historical snapshot contains `-0.025` before later snapshots return to zero.
- `/usr/data` is persistent ext4 storage; Klipper logs currently account for about 1.6 GiB.
- OrcaSlicer is the usual slicer; Creality Print remains available.
- The Z-offset or Z-reference problem existed before the yellow bed springs were installed.
- The springs improved bed levelling but changed nothing about the Z problem.
- CFS filament changes can override intended nozzle temperatures.
- Startup and calibration sequences can be excessively long and opaque.
- Earlier G-code post-processing successfully removed a redundant tool command and applied a temporary ironing offset, proving that some slicer-side workarounds are useful but insufficient against later firmware macro overrides.

## Reported but not yet verified from the machine

- Exact CFS firmware source and per-unit hardware revision.
- Physical board marking.
- Exact Klipper commit/version.
- Recovery image compatibility with this exact machine revision.

## Completed

- Public repository created.
- Scope, strategy and safety boundary documented.
- Agent rules, gates, roadmap and acquisition protocol prepared.
- Public/private data separation defined.
- Notion project branch created separately as the long-form personal register.
- Gate G1 passed and target identity confirmed.
- Read-only acquisition `20260819-1627-k1max-stock` completed.
- Raw material retained under ignored local storage.
- Redacted manifest, service map, mount map, checksums, include graph, macro index and findings produced.
- Gate G2 passed with explicit limitations.

## Next safe action

Analyse the captured material locally for Gate G3. Map the implementations and callers of `BOX_*`, `CX_*`, `ACCURATE_HOME_Z` and `CXSAVE_CONFIG`; distinguish Z measurement variability from Z value replacement; prepare a trace protocol for two identical jobs.

Do not reconnect merely to fill a low-value inventory gap. Do not modify the printer.

## Not authorised yet

- Helper Script installation.
- Mainsail, Fluidd or Moonraker changes.
- Firmware downgrade or replacement.
- Any SSH write.
- Service restart or reboot initiated by an agent.
- Macro or configuration modification.
- Z, mesh, temperature or CFS tuning.

## Current blockers

- S11 firmware metadata conflicts with the S12 header in the active configuration.
- Recovery artefacts and procedure have not been matched locally to the exact revision.
- Internal implementations of several `BOX_*` and `CX_*` commands are not yet mapped.
- No paired traces from identical jobs exist yet.

## Exit condition for this phase

Gate G3 has a defensible call graph, separated Z hypotheses, comparable traces and one narrow proposed intervention. This will authorise patch preparation only, not deployment.
