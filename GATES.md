# GATES

Progression is evidence-based. Passing a gate authorises only the next bounded phase, not every later action.

These gates control evidence collection and changes affecting the printer. They do not gate normal Git or GitHub operations: under D-010, Codex may complete branches, commits, pushes, pull requests, merges into `main` and cleanup without requesting another operator approval. Repository integration never expands the printer-side authority granted by a gate.

## G0 — Repository bootstrap

Status: **passed**

Criteria:

- public scope and safety boundary exist;
- raw/private paths are ignored;
- agent rules prohibit remote mutation;
- state, roadmap and decisions are explicit.

## G1 — Ready for read-only acquisition

Status: **passed on 2026-08-19**

Required:

- root enabled manually by Thomas;
- exact target host supplied outside Git;
- printer idle;
- visible printer and CFS versions recorded;
- likely board revision recorded but still subject to machine verification;
- recovery image and recovery procedure candidates stored locally, or the absence explicitly acknowledged before connection;
- Codex reads `AGENTS.md` and the acquisition protocol;
- local raw destination is inside an ignored path.

Passing G1 authorises read-only commands and remote-to-local copying only.

## G2 — Stock acquisition complete

Status: **passed on 2026-08-19 with documented limitations**

Required:

- system and firmware manifest completed;
- configuration entry points and includes inventoried;
- services, processes, mounts and persistence paths inventoried;
- relevant files and logs copied to private local storage;
- checksums recorded;
- command log completed;
- sanitisation performed;
- public artefacts reviewed for secrets and vendor redistribution risk;
- no remote mutation occurred.

Passing G2 authorises analysis of captured evidence, not printer changes.

Recorded limitations: listener output was incomplete, CFS versions remain UI-reported, and the online recovery image/procedure has not been validated locally. These do not authorise widening the scope or mutating the printer.

Follow-up evidence on 2026-08-19 resolved the runtime board selection as S12 structure 0 and mapped the readable CX, persistence, homing and PR Touch sources. The CFS state machine remains a compiled boundary. G2 remains passed; G3 still requires comparable traces and a narrow intervention.

## G3 — Diagnosis sufficiently grounded

Status: **passed on 2026-08-20 for offline G4 preparation only**

Execution status: session `20260819-185157-g3-aba` completed A1/B/A2 in one boot session on 2026-08-19. Q1 passed. Q2 failed because Thomas adjusted the bed screws between the prints and again around A2. Q3 failed because the Z retry path differed, Q4 remained incomplete, and Q5 is inconclusive. The session is useful evidence but is not a qualified comparable pair.

Observed evidence includes two Z-establishing phases around cleaning, A2 retrying through index 7 with large internal outliers, and runtime pressure advance `0.044` competing with the files' requested `0.03`. No fourth print is authorised or needed for this session.

Passive production session `20260819-215124-long` then captured one complete normal job. It resolved the pressure-advance uncertainty: startup `0.044` was replaced by file-requested `0.03`, and `0.03` remained active through the automatic CFS refill and print end. It also proved that the initial CFS load/purge and an equivalent-PLA refill use the stock CFS temperature `220 °C` instead of respecting the first-layer target or preserving the prior print temperature. Visible Z origin stayed at `+0.27 mm`; this job did not reproduce the historical Z shift.

Required:

- startup and CFS call graphs exist;
- all known Z-offset, homing, levelling, mesh and temperature writers are mapped;
- at least two identical-job traces are compared where possible;
- Z repeatability and Z reset are treated as separate hypotheses;
- first intervention is named, narrow and justified;
- success and failure criteria are measurable.

Passing G3 authorises preparation of a patch and rollback plan, not deployment.

No additional sacrificial print is required before offline G4 preparation. The
temperature owner remains a separate, dynamic and material-independent package.

The static Geeetech PLA `190/195` candidate prepared on 2026-08-20 was rejected
by Thomas before deployment because it was not material- or temperature-agnostic.
Its deployable files were removed. G3 temperature work now requires proof of a
dynamic owner that follows G-code targets through startup, both CFS units,
equivalent refill and intentional material changes.

Session `20260820-154056-p123` then captured P1, P2, P3, P4, two P5 attempts and
P1 PETG in one passive trace. It directly proved that the current `+0.27 mm`
post-processor executes only after the stock startup sequence, so it cannot
protect an earlier purge. It also proved that live Z adjustments invoke
`Z_OFFSET_APPLY_PROBE`, but the end-of-print path applies the exact inverse and
prepares `0.000` for persistence. P1 PETG finished at `+0.38 mm`, `+0.11 mm`
above the file baseline, before that correction was erased at completion.

P2 and P3 share their 639 recorded slicer settings and produced no reported
visible difference despite separate versus assembled objects. One live
`+0.010 mm` Z click occurred during P3, so this is not a fully untouched pair.
It does not reproduce the historical large Z shift and provides no support for
the simplistic claim that object count alone causes it. A bed-screw change after
P3 prevents extending the comparison to P4.

The second corrected P5 completed one intentional tool change without a pause.
Its measured nozzle targets were `115 -> 220 -> 205 -> 220 -> 0 °C`. The first
`220 °C` confirms the startup override. The final `220 °C` equals the requested
second-filament target, so this test cannot distinguish G-code ownership from a
stock CFS rewrite. The first P5 attempt had three pauses after a likely filament
break and is excluded from behavioural qualification.

These results satisfy G3 because the Z reset and physical repeatability
hypotheses are separated and runtime ownership is measured. Ils avaient d'abord
conduit à un paquet Z fixe, rejeté ensuite par Thomas. G3 autorise maintenant la
conception et le prototype hors imprimante du système cohérent décrit dans
ADR-004 : calibration persistante, mesh, séquence, interface, Orca et
températures CFS. Il n'autorise aucun déploiement ni autre mutation.

## G4 — One mutation ready for deployment

Status: **passed and deployed on 2026-08-19 for `G4-SSH-KEY` only**

The named change installed one dedicated ECDSA P-256 public key in
`/root/.ssh/authorized_keys`. The original file and directory were absent. The
final file contains exactly one active key, is owned by root with mode `600`,
and two independent connections succeeded with password authentication disabled.

An initial Ed25519 attempt was rejected because the observed Dropbear `2019.78`
predates Ed25519 `authorized_keys` support. Its malformed first transfer was
repaired, the unsupported key was removed, and its unused local private key was
deleted. Private evidence and backup checksums remain outside Git.

This pass does not authorise any other printer mutation. Every future named
change must satisfy G4 independently.

Candidate `G4-CFS-TEMP-PLA`: **rejected and never deployed**. It must not be
reopened. A future G4 requires a new name and a dynamic, material-independent
design backed by the full transition matrix.

Candidate `G4-ZSAFE-START-V1`: **rejected by Thomas on 2026-08-20 and never
deployed**. Son nom ne peut plus recevoir de GO. Les fichiers restants sont des
preuves historiques marquées `rejected_never_deploy` ; le macro échoue
volontairement s'il est chargé par erreur.

Current behaviour candidate: **none**. Le travail actif est le prototype local
`K1-CONTROL-V1`. Il ne deviendra un ou plusieurs candidats G4 nommés qu'après la
réussite du contrat, de l'interface simulée, de la matrice Z/mesh/CFS/Orca, de
la preuve de compatibilité et des rollbacks.

Required for each named change:

- exact files and commands identified;
- pre-change backup and checksums available;
- patch reviewed in Git;
- validation procedure written;
- rollback procedure written and plausible;
- no unrelated changes bundled;
- explicit approval from Thomas for this exact deployment.

Pour le système de pilotage, un G4 exige aussi :

- version exacte et empreinte de Moonraker/Mainsail si inclus ;
- preuve de ressources, ports, sécurité et coexistence avec les services
  Creality et deux CFS ;
- aucune valeur Z ou température matière universelle cachée ;
- prototype complet hors imprimante déjà vert ;
- ancien post-traitement Orca conservé jusqu'à preuve atomique de son
  remplacement.

Passing G4 authorises only that named mutation.

## G5 — V1 production baseline

Status: **not passed**

Required:

- cold boot followed by three successful consecutive prints on a known plate without manual Z-offset correction;
- requested temperatures respected during validated CFS transitions;
- both CFS units exercised;
- fast and reference startup paths behave as documented;
- configuration survives reboot;
- a saved live Z calibration survives print end and reboot, while a new
  reference calibration invalidates it;
- plate/temperature mesh selection and per-job adaptive mesh behave as declared;
- rollback has been tested or safely simulated;
- repository state matches the deployed state;
- normal jobs need no Codex intervention or per-print manual file edit;
- remaining limitations are explicit.
