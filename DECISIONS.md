# DECISIONS

## D-001 — Public repository with strict sanitisation

Date: 2026-08-19  
Status: accepted

The repository is public to maximise community value. Raw backups, credentials, private network information, unnecessary hardware identifiers and unreviewed vendor files remain local and ignored.

## D-002 — Observe the stock CFS stack before replacing it

Date: 2026-08-19  
Status: accepted

The initial target is rooted stock firmware plus controlled observation and later minimal overrides. A full Klipper replacement is not the default because preserving two-CFS behaviour, toolhead hardware, screen integration and proprietary state machines may otherwise become a large reverse-engineering project.

## D-003 — Codex is a bounded operator, not a permanent observer

Date: 2026-08-19  
Status: accepted

ChatGPT carries diagnosis, experiment design and review. Codex receives finite local/SSH missions for inventory, scripting, deployment and verification. This reduces context cost and limits accidental remote mutation.

## D-004 — Raw acquisition stays outside Git

Date: 2026-08-19  
Status: accepted

Complete backups and raw logs are stored under ignored local paths. Git receives manifests, hashes, original code, patches and redacted evidence only.

## D-005 — Yellow bed springs are not the Z root cause

Date: 2026-08-19  
Status: accepted

The same Z problem existed before and after spring installation. The springs improved bed levelling but had no observed effect on the Z-offset issue. Future diagnosis must not reopen this causal hypothesis without new contradictory evidence.

## D-006 — Publish original overlays and patches, not vendor payloads

Date: 2026-08-19  
Status: accepted

Manufacturer files may be inventoried by path, role and checksum. Public changes should be expressed as original override files, minimal patches or documented diffs whenever redistribution rights are unclear.

## D-007 — One intervention class at a time

Date: 2026-08-19  
Status: accepted

Root setup, interface installation, startup changes, Z correction, mesh strategy and CFS temperature logic are separate lots. Combining them would destroy diagnostic attribution and make rollback unreliable.

## D-008 — No OrcaSlicer fork during initial stabilisation

Date: 2026-08-19  
Status: accepted

OrcaSlicer integration is valuable, but a slicer fork is a separate software product. It is deferred until printer-side behaviour is stable and a specific remaining integration gap has been proven.

## D-009 — Licence remains open

Date: 2026-08-19  
Status: open

A public reuse licence is desirable for community adoption, but no licence is selected silently because licence grants are not fully reversible. Add a `LICENSE` only after Thomas chooses the intended reuse model.

## D-010 — Permanent Git and GitHub delegation to Codex

Date: 2026-08-19
Status: accepted

Thomas delegates the complete Git and GitHub lifecycle of this repository to Codex on a standing basis. Normal operations — including branches, commits, pushes, pull requests, readiness transitions, merges into `main`, tags and cleanup of merged mission branches — require no additional `GO` or human validation.

This decision does not authorise printer mutation and does not relax sanitisation, secret handling, preservation of unrelated work or platform safety controls. Force-pushes and published-history rewrites remain exceptional and require an explicit instruction naming that operation.

## D-011 — Comparable stock traces precede custom installation

Date: 2026-08-19
Status: accepted

The custom installation decision is deferred until one controlled A1/A2 pair has been qualified under the G3 protocol. The pair uses one byte-identical private G-code file, fixed plate/nozzle/filament/CFS conditions, one boot session and matched thermal starting windows. D-012 adds B between them to isolate geometry without replacing the identical-file pair.

No extra trial beyond the approved session plan is performed automatically. A non-comparable pair is reported as such. The first default intervention remains a narrow, reversible overlay; a broader stack replacement requires evidence that minimal interventions cannot solve the confirmed mechanism while preserving the screen and both CFS units.

## D-012 — Geometry is isolated before reboot and CFS tests

Date: 2026-08-19
Status: accepted

Local comparison confirmed that inputs A (`200 × 200 mm`) and B (`200 × 201 mm`) have identical slicer settings and control commands. The first physical sequence is therefore A1/B/A2 in one boot session with one Geeetech filament. A1/A2 provide the identical-file pair; B isolates the one-millimetre geometry change.

No reboot or multi-filament CFS transition is added until this sequence has been analysed. This prevents random stock bed checks, boot state, temperature, pressure advance and CFS behaviour from being mixed into one result.

## D-013 — No sacrificial print campaign after the first G3 session

Date: 2026-08-19
Status: accepted

Session `20260819-185157-g3-aba` completed A1/B/A2 but did not produce a qualified geometry comparison because the bed screws changed between the trials. It nevertheless confirmed variable Z retries, multiple Z-establishing phases and a competing pressure-advance value.

Thomas's reported production symptom — especially after a long print followed by a differently configured or multi-object file — is treated as valid diagnostic context, not as a claim that must be proven through repeated plastic-consuming tests. Future traces will be collected passively around useful production jobs. No fourth print or broad combinatorial campaign is launched without one narrow question that cannot be answered offline or from existing logs.
