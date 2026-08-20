# Overrides

Les correctifs de ce dossier sont des candidats originaux et réversibles. Leur
présence dans Git ne signifie pas qu'ils sont installés sur l'imprimante.

Le candidat statique Geeetech PLA `190/195` a été rejeté avant déploiement et
retiré. Aucun correctif CFS de température n'est actuellement déployable.

This directory will contain original, reviewable configuration overlays and wrapper macros after diagnosis.

It is intentionally empty during P0/P1.

Rules:

- Do not copy the complete vendor configuration tree here.
- Prefer new include files and wrappers over in-place edits.
- One behaviour class per change.
- Each override must name its supported hardware/firmware matrix.
- Each override requires tests, deployment instructions, validation and rollback.
- Nothing in this directory is deployable merely because it exists; Gate G4 still applies.
