# Contributing

Contributions are welcome when they improve reproducibility without weakening safety.

## A useful report includes

- exact printer model and hardware revision;
- upgrade kit and number/type of CFS units;
- printer and CFS firmware versions;
- slicer and relevant profile version;
- thermal and plate conditions;
- expected behaviour;
- observed behaviour;
- reproduction steps;
- redacted logs or configuration excerpts;
- whether the result survived reboot;
- known rollback path.

## Contribution rules

- Never include credentials or private network data.
- Do not upload complete firmware images or opaque binaries.
- Prefer hashes, paths, original overlays and minimal patches over copied vendor trees.
- Keep hardware/firmware-specific claims narrow.
- Add or update tests for scripts and transformations.
- Separate observation, hypothesis and confirmed conclusion.
- Describe remote writes explicitly and provide rollback.

## Pull requests

Use one intervention class per pull request. A change to Z handling, CFS temperature logic, startup orchestration or deployment tooling should not be bundled with unrelated work.

Until a licence is selected, contribution does not imply a broad external redistribution grant beyond normal collaboration in this repository.
