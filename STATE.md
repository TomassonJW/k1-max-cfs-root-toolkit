# STATE

Last updated: 2026-08-19

## Current phase

**P0 — safe repository bootstrap**

The repository exists and the initial public scope has been created. The printer has not been accessed, inventoried or modified through this project.

## Confirmed facts

- Target machine: older-generation Creality K1 Max.
- Classic K1 CFS upgrade installed.
- Two CFS units are in use.
- OrcaSlicer is the usual slicer; Creality Print remains available.
- The Z-offset or Z-reference problem existed before the yellow bed springs were installed.
- The springs improved bed levelling but changed nothing about the Z problem.
- CFS filament changes can override intended nozzle temperatures.
- Startup and calibration sequences can be excessively long and opaque.
- Earlier G-code post-processing successfully removed a redundant tool command and applied a temporary ironing offset, proving that some slicer-side workarounds are useful but insufficient against later firmware macro overrides.

## Reported but not yet verified from the machine

- Printer firmware: `CR4CU220812S11_ota_img_V2.3.5.34`.
- Board identity: S11.
- Exact CFS firmware versions.
- Active Klipper, Moonraker and Creality component versions.
- Active configuration paths and persistence boundaries.

## Completed

- Public repository created.
- Scope, strategy and safety boundary documented.
- Agent rules, gates, roadmap and acquisition protocol prepared.
- Public/private data separation defined.
- Notion project branch created separately as the long-form personal register.

## Next safe action

Thomas manually enables root access using the printer's supported interface, records the versions visible on screen, and does **not** install any helper or change any configuration.

After that, Codex may run the bounded mission in `prompts/01-codex-read-only-acquisition.md`.

## Not authorised yet

- Helper Script installation.
- Mainsail, Fluidd or Moonraker changes.
- Firmware downgrade or replacement.
- Any SSH write.
- Service restart or reboot initiated by an agent.
- Macro or configuration modification.
- Z, mesh, temperature or CFS tuning.

## Current blockers

- Exact firmware and board identity are not verified.
- Recovery artefacts and recovery procedure have not been matched to the exact machine revision.
- No stock inventory or raw backup exists yet.

## Exit condition for this phase

Gate G1 is satisfied and a strictly read-only acquisition can begin.
