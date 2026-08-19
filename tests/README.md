# Tests

The test suite will grow with the project.

Initial priorities:

- secret/redaction fixtures;
- manifest schema validation;
- detection of remote-write command patterns;
- G-code tool-command post-processing fixtures;
- macro call-graph parsing;
- configuration patch idempotence;
- deployment dry-run and rollback checks;
- recorded Z and temperature timeline analysis.

Fixtures must be synthetic or fully redacted. Do not use raw printer backups as test data in Git.
