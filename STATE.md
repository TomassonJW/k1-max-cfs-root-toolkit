# STATE

Last updated: 2026-08-20

## Current phase

**P3 — first offline Z-safety package prepared after Gate G3**

The repository baseline, stock acquisition, complete Orca/G-code intake and
passive P1–P5/PETG trace are complete. Gate G3 is passed for offline design and
simulation only. The selected route remains a strengthened stock Level A; no
printer-behaviour deployment is authorised. The separate `G4-SSH-KEY` change is
the only deployed printer-side change.

`G4-ZSAFE-START-V1` is now prepared under `overrides/g4-zsafe-start/`. Its
overlay keeps the public `START_PRINT` name, removes Orca's preliminary `G28/T0`,
loads the stock `default` mesh explicitly, applies `+0.27 mm` before CFS/purge,
guards every low production path and captures the final correction candidate
before the unchanged stock end. Offline tests are green; the package has not
been loaded, parsed or executed on the printer.

## Confirmed facts

- Passive session `20260820-154056-p123` captured P1, P2, P3, P4, two P5
  attempts and one P1 PETG run. All jobs finished; the trace ended with nozzle
  and bed targets at zero.
- P4 proved that the `+0.27 mm` post-processor correction appears only after
  `START_PRINT`; startup purge and other earlier low operations remain
  unprotected.
- Live Z changes invoke `Z_OFFSET_APPLY_PROBE`, but the end-of-print path applies
  the exact inverse and prepares `0.000` for persistence. The current workflow
  therefore erases the correction it appeared to save.
- P1 PETG required a final visible correction of `+0.38 mm`, `+0.11 mm` above
  the file baseline, after briefly reaching `+0.40 mm`.
- P2 and P3 have the same 639 recorded settings and showed no reported physical
  difference despite separate versus assembled objects. One `+0.010 mm` live Z
  click occurred during P3, so the pair is not entirely untouched; it provides
  no evidence that object count alone explains the historical shifts.
- The second corrected P5 completed without a pause and followed nozzle targets
  `115 -> 220 -> 205 -> 220 -> 0 °C`. The first `220 °C` confirms the startup
  override; the second equals the requested target and cannot prove ownership.
- Every file still receives stock PA `0.044` during startup before its own PA
  becomes active roughly three minutes later.

- The accepted design route is a strengthened stock stack before BTT Eddy or a
  full firmware replacement. This authorises offline design, not deployment.
- A private, Git-ignored intake exists under
  `inventory/raw/user-inputs/20260820-full-system-audit/` for Orca exports,
  existing projects, G-codes, custom scripts, photos and recovery artefacts.
- The first private Orca and test-suite intake is complete: 24 baseline files
  and 13 test-suite files were copied locally and verified by SHA-256 without
  changing their sources. Raw files and manifests remain ignored by Git.
- Six candidate G-codes are now available offline. P2 and P3 have the same 639
  recorded settings, duration, material estimate and two-layer geometry, while
  differing as five separate objects versus one assembled object. They form the
  cleanest current object-structure comparison.
- Ironing is enabled on P1, P2 and P3. Because it is shared and occurs at the
  top surface, it does not invalidate their first-layer comparison; top-surface
  defects must nevertheless remain separate from Z observations.
- The supplied `P5-CFS-ONE-CHANGE` is not a one-change file: it contains eleven
  tool commands and ten automatic changes between PLA targets of 205 and 220
  degrees. It is deferred until a replacement G-code proves exactly one change.
- Every supplied G-code still inserts the temporary `+0.27 mm` correction after
  `START_PRINT`, so none protects a purge or low move executed inside that
  stock macro.
- BTT Eddy is not currently mandatory. Its closest K1 Max `2.3.5.34` + CFS
  integration documents beta Z-offset behaviour, repeated recalibration and
  build-plate risk; it remains a measured fallback if deterministic PR Touch
  still fails.
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

- `G4-ZSAFE-START-V1` architecture recorded in ADR-003.
- Original `zsafe_g4.cfg`, Orca start/end snippets and a declarative sequence
  contract prepared without copying or changing a vendor file.
- Offline simulation proves that declared purge and print hazards cannot run
  before final reference, explicit `default` mesh, effective `+0.27 mm` and the
  armed gate.
- High-clearance `VALIDATE_ONLY=1` path, exact backup/install boundaries, OK/KO
  criteria and full rollback documented in
  `docs/09-g4-zsafe-start-package.md`.

- Complete-system audit, A/B/C comparison, safety invariant, input contract and
  time-bounded roadmap documented in
  `docs/08-audit-systeme-complet-et-trajectoire.md`.
- ADR-002 proposes an analyser-first strengthened stock route and defines the
  later BTT Eddy decision gate.
- Private intake folders and exact deposition instructions created and verified
  as ignored by Git.
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
- Exact live copies of `printer.cfg`, `gcode_macro.cfg` and `box.cfg` were
  retrieved read-only and matched their recorded SHA-256 hashes.
- The production G-code contains no `M104`/`M109` request for `220 °C`; the CFS
  module and its generic PLA database own that value.
- The static `G4-CFS-TEMP-PLA` candidate was rejected by Thomas before
  deployment because it hard-coded Geeetech PLA and `190/195 °C`.
- Its deployable patch, helper, OrcaSlicer contract, deployment procedure and
  dedicated test were removed from `main`; the rejected ADR remains as history.
- The accepted requirement is dynamic: G-code or Thomas owns the temperature
  during a print, equivalent refill preserves the active target, and intentional
  material changes receive the next tool's target from G-code.

## Next safe action

Review the exact package `G4-ZSAFE-START-V1`. The next printer-side action is a
human gate: Thomas either refuses it or gives an explicit GO naming this package.
After GO, Codex must re-read and hash the live files before any write, stop on
drift, deploy only the reviewed include/overlay and Orca fields, then run the
high-clearance `VALIDATE_ONLY=1` path before any extrusion.

Do not remove the Orca post-processor yet. Its retirement is an acceptance
criterion of the future package, after the replacement protects both startup
and print moves.

Keep dynamic CFS temperature ownership in a separate later package. Determine
offline whether every stock write can be intercepted; otherwise define the
smallest maintainable replacement for the compiled owner. Never hard-code a
material or temperature.

No additional diagnostic print is requested now. The next physical action is
the explicitly authorised high-clearance validation of `G4-ZSAFE-START-V1`.
Use `k1max-root`; a password prompt remains a failure condition.

## Not authorised yet

- Helper Script installation.
- Mainsail, Fluidd or Moonraker changes.
- BTT Eddy preparation, installation, firmware or calibration.
- Firmware downgrade or replacement.
- Any SSH write other than the completed `G4-SSH-KEY` deployment.
- Service restart or reboot initiated by an agent.
- Macro or configuration modification.
- Z, mesh, temperature or CFS tuning.
- Any static material-specific CFS temperature candidate.
- `G4-ZSAFE-START-V1` deployment, restart, homing, high-clearance validation or
  Orca profile change until the exact named GO is received.

## Current blockers

- A complete Orca printer-config bundle has not yet been exported; the exact
  user profiles, current Z post-processor and representative projects/G-codes
  are nevertheless captured individually and verified.
- The PETG G-code has no matching `P1-PETG.3mf` in the intake.
- Recovery artefacts and procedure have not been matched locally to the exact revision.
- The core `BOX_*` state machine is compiled and its readable source is not present on the machine.
- The literal registration of `ACCURATE_HOME_Z` was not found in readable Python, although the underlying `G28` and PR Touch path is mapped.
- Parts of `ACCURATE_HOME_Z` remain non-observable, although pressure advance ownership is now measured.
- The corrected P5 cannot distinguish temperature ownership after its change
  because both the second filament and the stock CFS request `220 °C`.
- The large historical Z shifts have not been reproduced, although the late
  application and end-of-print erasure mechanisms are now directly proven.
- The overlay has not been parsed by the exact printer runtime. The duplicate
  section merge is proven from captured source and simulated locally, but the
  first real config load remains a G4 validation.
- The first package deliberately supports only the reviewed `+0.27 mm` and the
  existing `default` mesh. PETG `+0.38 mm`, accepted persistence and mesh
  adaptation remain later decisions.

## Exit condition for this phase

Offline exit conditions are met for `G4-ZSAFE-START-V1`: exact files, backup
boundary, reference checksums, reviewed diff, simulation, high-clearance
no-extrusion validation and rollback exist. The phase remains open at the human
G4 because no printer-side result has been observed.
