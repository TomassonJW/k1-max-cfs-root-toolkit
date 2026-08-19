# Scripts

Planned script classes:

- local read-only acquisition helpers;
- redaction and secret scanning;
- manifest and checksum generation;
- configuration call-graph extraction;
- local validation and tests;
- later, gated deployment and rollback tooling.

During P0/P1, scripts must default to no remote write and fail closed on ambiguity.

A future remote-mutating script must:

- require an explicit change ID;
- refuse to run without a verified backup;
- show the exact diff and target paths;
- support dry-run where meaningful;
- validate after deployment;
- provide a tested rollback path;
- never accept or print credentials through tracked configuration.
