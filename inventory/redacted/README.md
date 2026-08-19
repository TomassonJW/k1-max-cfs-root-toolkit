# Redacted inventory

This directory contains publishable acquisition artefacts only.

Use one directory per capture:

```text
inventory/redacted/<capture-id>/
├── command-log.md
├── paths-and-checksums.csv
├── services.md
├── mounts.md
├── config-include-graph.md
├── macro-index.md
└── sanitisation-report.md
```

Rules:

- Raw files remain under ignored local paths.
- Private addresses, hostnames, MACs, serials, credentials and cloud identifiers are removed.
- Vendor files are represented by path, role and checksum unless publication is justified.
- Every capture states whether any remote write occurred; during P1 it must be `false`.
- A redacted artefact must remain technically meaningful enough to review the conclusion.
