# Recovery and rollback prerequisites

## Principle

Root access does not make a change safe. A change is deployable only when the exact machine can be returned to a known state.

## Before any mutation

Record and verify:

- physical board/revision evidence;
- printer firmware build and checksum where available;
- both CFS firmware versions;
- exact active configuration paths;
- boot and persistence layout;
- stock files affected by the planned change;
- stock checksums and local backup paths;
- recovery image candidate matched to the exact revision;
- official or community recovery procedure and its assumptions;
- access method if the normal UI or SSH no longer starts.

## Rollback levels

### Level 1 — Configuration rollback

Restore the exact backed-up files, ownership and permissions, then validate the relevant service and printer state.

### Level 2 — Service/component rollback

Remove or disable only the introduced component and restore the previous startup configuration.

### Level 3 — Firmware recovery

Use only a revision-matched recovery image and documented process. Do not assume an image for S11, S12 or another CFS branch is interchangeable.

## Deployment packet required by Gate G4

For one named change, prepare:

- change ID;
- target version matrix;
- exact preconditions;
- files and commands;
- before checksums;
- patch or complete original overlay;
- validation steps;
- success/failure thresholds;
- rollback commands;
- rollback validation;
- stop conditions;
- explicit approval record.

## Failure policy

If post-change validation fails:

1. stop adding changes;
2. preserve logs and observed state;
3. execute the prepared rollback only;
4. verify restoration;
5. document the failure as evidence;
6. do not improvise a second fix on the live machine.

## What this document does not claim

No specific firmware image or recovery procedure has yet been verified for the target machine. That must be established from the real board and firmware inventory before Gate G4.
