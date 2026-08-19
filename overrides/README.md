# Overrides

This directory will contain original, reviewable configuration overlays and wrapper macros after diagnosis.

It is intentionally empty during P0/P1.

Rules:

- Do not copy the complete vendor configuration tree here.
- Prefer new include files and wrappers over in-place edits.
- One behaviour class per change.
- Each override must name its supported hardware/firmware matrix.
- Each override requires tests, deployment instructions, validation and rollback.
- Nothing in this directory is deployable merely because it exists; Gate G4 still applies.
