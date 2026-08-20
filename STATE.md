# STATE

Last updated: 2026-08-21

## Current phase

**P4 — V1 et V2 fermées ; V3 préparée hors imprimante et non autorisée**

The repository baseline, stock acquisition, complete Orca/G-code intake and
passive P1–P5/PETG trace are complete. Gate G3 is passed for offline design and
simulation only. No printer-behaviour deployment is authorised. The separate
`G4-SSH-KEY` access change remains the only deployed printer-side change.

Thomas rejected `G4-ZSAFE-START-V1` before deployment. Its fixed `+0.27 mm`,
single `default` mesh and manual clean flow are not a production solution. The
remaining files are historical, marked `rejected_never_deploy`, and fail closed
if loaded accidentally.

The active target is `K1-CONTROL-V1`: one coherent, parameterised product with
a simple daily interface, a Mainsail expert view candidate, persistent accepted
Z calibration, meshes by plate/temperature, safe configurable start/clean/purge,
dynamic two-CFS temperature ownership and one versioned Orca contract. It is
being prepared by reversible slices. The complete offline prototype is now
green. V1 was authorised but stopped before mutation because the required
`logrotate` was absent. V2 reused the bounded stock syslog and reached a working
Mainsail through an SSH tunnel, then was rolled back because Mainsail `v2.18.2`
cannot satisfy the required Moonraker-account gate. V3 moves authentication to
nginx, remains offline-only and changes no print behaviour.

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
  full firmware replacement. It now means one coherent control product, not a
  fixed Z patch followed by unrelated settings. This authorises offline design,
  not deployment.
- The accepted Z rule is explicit: live changes belong to a calibration session;
  only `Enregistrer` creates the persistent record. It survives print end and
  reboot, but a new reference calibration invalidates it.
- Moonraker MIPS is pinned to embedded commit
  `fccffa96c63ed77dc3953e18615e9fe9cd3d69ea`; Mainsail is pinned to `v2.18.2`.
  Their archives, security policy and paths are fixed, but memory and
  coexistence with the screen and two CFS still require the named G4.
- A bounded read-only capacity snapshot found about 209 MiB total RAM, 118 MiB
  available, Python 3.8.2, 4.2 GiB free on `/usr/data`, no Moonraker process and
  no listener on its usual port. No remote mutation occurred.
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

- `G4-ZSAFE-START-V1`, ADR-003 and their former gate are explicitly rejected;
  the historical macro now fails closed if loaded by mistake.
- The durable product need and target behaviour are recorded in
  `docs/10-systeme-pilotage-perenne.md` and ADR-004.
- Mainsail, Moonraker, Creality K1 Series Annex, Creality Helper Script, its CFS
  fork, KAMP and the available calibration approaches were compared against the
  exact captured stack in `docs/11-compatibilite-interfaces-et-calibration.md`.
- A machine-readable `K1-CONTROL-V1` contract now forbids a universal fixed Z,
  requires explicit persistence/invalidation, keys meshes by plate/temperature,
  fixes dynamic temperature ownership and guards every production hazard.
- Offline contract tests were added before any printer-side implementation.
- A dependency-free `K1 Control` web prototype and pure Python Z/mesh/temperature
  state engine now run only on synthetic data under `prototype/`.
- Desktop and narrow-screen browser checks passed. Live adjustment, explicit
  commit, simulated restart persistence and reference-calibration invalidation
  behaved as intended with no JavaScript error.
- The screen now talks to a loopback-only fake Moonraker that applies the Python
  state rules instead of changing browser state directly.
- The executable offline matrix passes all 17 required Z, mesh, sequence,
  temperature, two-CFS, Orca and rollback scenarios.
- The full Orca start/end/tool-change contract and expanded fixtures are ready;
  the active Orca profile and legacy `+0.27 mm` post-processor are unchanged.
- A local bundle containing the three pinned Moonraker/nginx/Mainsail archives
  was built and verified. Binary payloads remain temporary and outside Git.
- V1 had exact paths, first-login tunnel, backup, checksums, no-motion
  validation, resource gates and rollback, but its missing target dependency
  invalidated the package before deployment. V2 preserves these controls.
- The real V1 preflight confirmed standby, zero heater targets, S12 structure
  0, firmware `2.3.5.34`, about 117 MiB available RAM, 340 KiB swap in use,
  stock ports, T1/T2 connected on `1.1.3`, and all V1 targets absent.
- The same preflight proved that neither `logrotate` nor `/etc/logrotate.d`
  exists. V1 performed no mutation and is closed.
- V2 uses the existing `/sbin/syslogd -n` through `/dev/log`; BusyBox reports
  its default 200 KiB limit and one rotated backup. No logging dependency is
  installed.
- The exact V2 GO was received. Real attempts exposed Buildroot transport,
  nginx path, permission, Moonraker provider, service-stop and WebSocket-origin
  gaps. The corrected stack loaded the real Mainsail dashboard through a tunnel.
- Mainsail `v2.18.2` has no Moonraker account workflow. V2 could not remove
  loopback trust and still keep Mainsail working, so every attempt was rolled
  back and V2 is closed.
- Final post-rollback checks found `/usr/data/k1-control-v1` and both project
  services absent, ports `7125`/`4409` closed, stock ports `80`/`8080`/`9999`
  listening and all named Creality processes present.
- Thomas selected nginx authentication. Offline inspection proved the pinned
  MIPS binary contains `auth_basic` and `auth_basic_user_file`. V3 uses a
  masked local prompt, one salted SSHA record, HTTP `401/200` checks, private
  IPv4 source limits and strips credentials before proxying to Moonraker.

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

The next state-changing action is a new human gate: Thomas may explicitly
approve or refuse `G4-K1-CONTROL-FOUNDATION-V3`. The V1/V2 GO, the nginx design
choice and a generic `GO` are insufficient. Until that exact V3 approval, do
not upload, install, start or expose any service.

If approved, the first pose installs only Moonraker and Mainsail in observation,
creates and verifies the nginx account through an SSH tunnel, performs no
G-code command, and stops or rolls back on any checksum, login, coexistence or
resource failure.

Do not remove or disable the current Orca `+0.27 mm` post-processor. Its
retirement remains atomic with the later proven machine/Orca replacement.

## Not authorised yet

- Helper Script installation.
- `G4-K1-CONTROL-FOUNDATION-V1` forever: preflight KO, never deployed, name closed.
- `G4-K1-CONTROL-FOUNDATION-V2` forever: real attempts rolled back, name closed.
- `G4-K1-CONTROL-FOUNDATION-V3` until Thomas names it in a new exact GO.
- Any other Mainsail, Fluidd, Moonraker or `K1 Control` installation/change.
- BTT Eddy preparation, installation, firmware or calibration.
- Firmware downgrade or replacement.
- Any SSH write other than the completed `G4-SSH-KEY` deployment.
- Service restart or reboot initiated by an agent.
- Macro or configuration modification.
- Z, mesh, temperature or CFS tuning.
- Any static material-specific CFS temperature candidate.
- Any import or change of Orca fields on the workstation profile.
- `G4-ZSAFE-START-V1` forever: this rejected name cannot receive a GO.
- Any future `K1-CONTROL-V1` deployment until a new exact G4 package exists and
  receives its own explicit approval.

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
- Long-run memory headroom and per-service use still need proof; the one-shot
  read-only capture confirms only the baseline.
- The exact Creality Klipper commit is unknown; the captured `bed_mesh.py` must
  remain the implementation authority for the mesh adapter.
- Persistence of named mesh data outside the manufacturer file must be proven
  against the captured parser and restart behaviour.
- Every reference-changing Creality calibration path must be detected or
  wrapped so that an old accepted Z cannot survive a real recalibration.
- The compiled `BOX_*` owner may contain a late temperature write that no macro
  can intercept. The complete matrix decides whether a small replacement owner
  is required.
- The pinned Moonraker/Mainsail package has not yet run on the real machine, so
  its RAM, stability and coexistence are not proven.
- The real `K1 Control` adapter and the printer-side Z/mesh/start/CFS wrappers
  are intentionally deferred until the observation foundation is accepted.

## Exit condition for this phase

P3 has reached its exit condition: usable local prototype, tested state engine,
complete Orca contract, pinned versions, green 17-scenario matrix and prepared
foundation rollback. P4 remains closed until the exact named G4 is approved.
