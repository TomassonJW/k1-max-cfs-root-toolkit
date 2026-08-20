# STATE

Last updated: 2026-08-20

## Current phase

**P2 — first passive production trace complete; next-job comparison pending**

The repository baseline, stock acquisition and targeted source follow-up are complete. The A1/B/A2 physical session was executed by Thomas while Codex collected logs in read-only mode. The separate `G4-SSH-KEY` change has since added one dedicated SSH public key. Codex performed no restart, movement, heating, calibration, print, cancellation or printer-behaviour change.

## Confirmed facts

- Codex has standing authority to manage the complete Git and GitHub lifecycle of this repository, including pull-request fusion into `main`, without another `GO`; printer mutations remain controlled separately by G4.
- Passwordless root SSH is active through the local alias `k1max-root`. The alias selects one dedicated ECDSA P-256 key, refuses password fallback and passed two independent final connections.
- The machine runs Dropbear `2019.78`; Ed25519 public-key authentication is unavailable in this version, so the working key is ECDSA P-256.
- Passive session `20260819-215124-long` completed automatically after a normal long production print returned to standby. Codex performed no printer-side mutation.
- The stock startup applied pressure advance `0.044`; the print file then restored `0.03` at the first layer. The active value remained `0.03` through the automatic CFS refill and to the end.
- The CFS detected runout, selected another slot it classified as equivalent PLA and resumed automatically in about 2 minutes 54 seconds.
- At startup, the CFS reported that it could not read the purge-speed data and then used its fixed `220 °C` purge temperature despite first-layer and normal print targets of `190 °C` and `195 °C`; the compiled implementation prevents proving the exact causal link between those two events.
- During that equivalent-material refill, the temperature sequence was `195 -> 140 -> 220 -> 195 -> 220 °C`. The resumed print stayed at `220 °C` until Thomas manually restored `190 °C` at `23:04`.
- Visible Z homing origin remained `+0.27 mm` for the whole session; no live Z correction was reported.
- After completion and return to standby, the stock runtime briefly requested `150 °C` before returning the nozzle target to zero.
- Thomas judged the finished part broadly correct, with rough/granular ironing areas provisionally attributed to OrcaSlicer settings rather than the observed CFS temperature ownership.

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
- Session `20260819-185157-g3-aba` completed A1, B and A2 without reboot and without a fourth print.
- B and A2 each exposed multiple Z-establishing phases around nozzle cleaning; A2 reached retry index 7 and contained large internal outliers before converging near the `0.21–0.26` group.
- The stock runtime injected pressure advance `0.044` during B and A2 even though both private G-codes request `0.03` after `START_PRINT`; the final active value was not observable in this capture.
- Thomas changed bed-screw tension between the trials and again around A2. This may have improved the layer but makes the geometry comparison non-qualified.
- A1, B and A2 all completed with broadly usable physical results after manual tuning.

## Reported but not yet verified from the machine

- Exact CFS firmware source and per-unit hardware revision.
- Physical board marking; software selection is S12 structure 0, but physical confirmation remains desirable before firmware recovery.
- Exact Klipper commit/version.
- Recovery image compatibility with this exact machine revision.
- Whether a long print followed by a differently configured or multi-object file triggers the large historical Z shift reported by Thomas.

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
- Comparable A1/B/A2 trace protocol completed with fixed conditions, Q1–Q5 qualification and a custom-installation decision matrix.
- Private session, event timeline and comparison templates added under `experiments/g3/`.
- Bounded execution prompt prepared and used; all physical actions were performed by Thomas.
- Private G3 files A/B compared locally: 637 slicer settings and all 34 non-motion control commands are identical.
- Both files apply Z protection `+0.27 mm` and pressure advance `0.03` after `START_PRINT`; B changes only the Y dimension from `200` to `201 mm` and the resulting movements.
- The stock bed check selects four near-corner points randomly, measures each three times and can regenerate and save the mesh when at least two corners exceed its tolerance.
- A1/B/A2 is now the selected first physical sequence; reboot and multi-filament CFS tests are deferred.
- A1/B/A2 session report and cleaned event summary produced. Q1 passed, Q2–Q4 did not pass and Q5 is inconclusive.
- `G4-SSH-KEY` prepared, approved, deployed and validated without any service restart.
- Final `/root/.ssh/authorized_keys` state: one active ECDSA key, root ownership, mode `600`, final recorded SHA-256 `eae61f0314dbcdfaa9a02a42352592e3b175a5d35a0d501cb909b365697eb6af`.
- Local SSH configuration was backed up before adding the tested `k1max-root` alias.
- Read-only production observer added and validated with a six-second subscription probe: one persistent Klipper connection, three state samples, no repeated query traffic and no socket-close errors inside the capture.
- Long production capture `20260819-215124-long` completed with 6,748 state records and an automatic observer shutdown after standby.
- Cleaned findings, event summary and sanitisation report produced for the long capture; raw evidence remains local and ignored.
- Final pressure advance ownership measured: startup `0.044`, then file-requested `0.03` active through the CFS refill and print end.
- Equivalent-PLA CFS refill temperature override measured and confirmed: stock resume returned to `220 °C` instead of preserving the prior print temperature.

## Next safe action

Prepare a separate passive session for the next genuinely different or multi-object production job. Record any live Z correction with its time and value. Do not repeat the completed long print solely for diagnosis.

In parallel, prepare but do not deploy one narrow CFS temperature-ownership overlay covering the initial load/purge and automatic refill. It must consume explicit first-layer, normal-print and new-material temperatures, preserve the pre-pause value for equivalent refill, and remove the silent `220 °C` fallback. Keep pressure ownership, ironing and Z changes in separate future G4 packages.

Use `k1max-root` for future bounded SSH work; a password prompt is now a failure condition, not a normal step. Keep the next printer-behaviour change separate and subject it to its own named G4.

## Not authorised yet

- Helper Script installation.
- Mainsail, Fluidd or Moonraker changes.
- Firmware downgrade or replacement.
- Any SSH write other than the completed `G4-SSH-KEY` deployment.
- Service restart or reboot initiated by an agent.
- Macro or configuration modification.
- Z, mesh, temperature or CFS tuning.

## Current blockers

- Recovery artefacts and procedure have not been matched locally to the exact revision.
- The core `BOX_*` state machine is compiled and its readable source is not present on the machine.
- The literal registration of `ACCURATE_HOME_Z` was not found in readable Python, although the underlying `G28` and PR Touch path is mapped.
- The executed pair is not qualified because the bed screws changed and A1 startup capture is incomplete.
- Parts of `ACCURATE_HOME_Z` remain non-observable, although pressure advance ownership is now measured.
- No real multi-object problematic G-code is available locally for offline comparison.

## Exit condition for this phase

Gate G3 has a defensible call graph, separated Z hypotheses, comparable traces and one narrow proposed intervention. This will authorise patch preparation only, not deployment.
