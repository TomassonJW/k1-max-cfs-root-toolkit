# STATE

Last updated: 2026-08-19

## Current phase

**P2 — G3 comparable-trace protocol ready, execution pending**

The repository baseline, stock acquisition and targeted source follow-up are complete. The printer was accessed only in read-only mode on 2026-08-19. No remote write, restart, movement, heating or calibration occurred.

## Confirmed facts

- Codex has standing authority to manage the complete Git and GitHub lifecycle of this repository, including pull-request fusion into `main`, without another `GO`; printer mutations remain controlled separately by G4.

- Target machine: older-generation Creality K1 Max.
- Printer firmware: `2.3.5.34`, Buildroot 2020.02.1, Linux 4.4.94 on MIPS.
- The manufacturing identity partition reports board `CR4CU220812S12`, structure version `0`.
- The startup selector therefore loads the S12 structure-0 stock configuration; the active header and version match it.
- `/etc/ota_info` still reports `CR4CU220812S11`; this is now classified as inconsistent OTA metadata, not the active configuration identity.
- Classic K1 CFS upgrade installed.
- Two CFS units are in use.
- Both CFS units show firmware `1.1.3` on the printer UI; no machine version file has yet confirmed it.
- Active configuration entry point: `/usr/data/printer_data/config/printer.cfg`.
- `printer.cfg` includes `sensorless.cfg`, `gcode_macro.cfg`, `printer_params.cfg` and `box.cfg`.
- `START_PRINT` invokes the CFS, homing, nozzle-cleaning and levelling chains after slicer input.
- `box.cfg` sets `Tn_extrude_temp` to `220`.
- The CFS `BOX_*` implementation is delivered as a compiled `box_wrapper` module; only its small Python loader is readable.
- `CXSAVE_CONFIG`, the principal `CX_*` startup helpers, `G28` and the PR Touch probing path have been captured and mapped from readable Python sources.
- `G28` invokes the PR Touch Z routine, which uses five measurements, selects the median and applies `self_z_offset` when establishing the Z origin.
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
- Physical board marking; software selection is S12 structure 0, but physical confirmation remains desirable before firmware recovery.
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
- Follow-up read-only acquisition `20260819-1726-k1max-targeted-sources` completed.
- S11/S12 runtime configuration identity resolved as S12 structure 0.
- Readable CX, persistence, homing and PR Touch sources mapped; compiled CFS boundary recorded.
- Comparable `R1`/`R2` trace protocol completed with fixed conditions, Q1–Q5 qualification and a custom-installation decision matrix.
- Private session, event timeline and comparison templates added under `experiments/g3/`.
- Bounded future execution prompt prepared; no trace run, print or calibration was launched.

## Next safe action

Thomas selects one private G-code known to expose the first-layer problem, ideally a short first-layer reproducer, then gives a named `GO` for one `R1`/`R2` session. Codex prepares the ignored raw directory and collects only read-only snapshots and existing logs while Thomas performs every physical launch and safety action.

Do not reconnect before the exact session inputs and authority are recorded. Do not modify the printer or automatically run a third test.

## Not authorised yet

- Helper Script installation.
- Mainsail, Fluidd or Moonraker changes.
- Firmware downgrade or replacement.
- Any SSH write.
- Service restart or reboot initiated by an agent.
- Macro or configuration modification.
- Z, mesh, temperature or CFS tuning.

## Current blockers

- Recovery artefacts and procedure have not been matched locally to the exact revision.
- The core `BOX_*` state machine is compiled and its readable source is not present on the machine.
- The literal registration of `ACCURATE_HOME_Z` was not found in readable Python, although the underlying `G28` and PR Touch path is mapped.
- The protocol is ready, but no qualified pair of identical-job traces exists yet.
- Stock logs may leave `ACCURATE_HOME_Z` or internal `BOX_*` values non-observable; this must be measured before proposing instrumentation.

## Exit condition for this phase

Gate G3 has a defensible call graph, separated Z hypotheses, comparable traces and one narrow proposed intervention. This will authorise patch preparation only, not deployment.
