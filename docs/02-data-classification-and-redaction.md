# Data classification and redaction

## Objective

Make the public repository genuinely safe by design rather than attempting a last-minute cleanup after sensitive material has entered Git history.

## Class A — Public by default

Examples:

- original project documentation;
- original scripts and tests;
- generic schemas and example manifests;
- hashes of vendor files when hashes reveal no secret;
- measured timings and thermal traces with identifiers removed;
- original override macros;
- minimal patches whose redistribution is permitted.

## Class B — Public only after review and redaction

Examples:

- logs;
- process lists;
- service definitions;
- configuration excerpts;
- command output;
- G-code reproductions;
- screenshots;
- file paths containing usernames or local conventions.

Review for:

- IP addresses and private hostnames;
- MAC addresses;
- SSIDs and Wi-Fi credentials;
- passwords, tokens, cookies and API keys;
- SSH material;
- Creality account/cloud identifiers;
- serial numbers and device IDs;
- personal file paths or usernames;
- unexpected embedded G-code metadata;
- URLs containing signed tokens;
- proprietary content beyond the minimum needed for analysis.

## Class C — Private local only

Examples:

- complete filesystem or configuration backups;
- raw logs;
- unredacted process and network output;
- exact private network topology;
- recovery images and firmware packages;
- original vendor trees copied from the printer;
- private G-code containing user paths or project names;
- root credentials.

Store under ignored local paths such as `private/`, `backups/`, `inventory/raw/` or `recovery/local/`.

## Class D — Must not be retained unnecessarily

Examples:

- plaintext root passwords;
- exposed private keys;
- active cloud tokens;
- credentials accidentally written into command logs;
- third-party personal data unrelated to diagnosis.

Remove securely from working material, rotate the credential when applicable, and do not preserve it merely for completeness.

## Vendor-content rule

Prefer this publication order:

1. path, role, size and checksum;
2. original explanation or call graph;
3. minimal excerpt where legally and technically necessary;
4. patch/diff against a named version;
5. full copied vendor file only when redistribution rights are clear.

## Redaction report

Each public capture should state:

- capture ID;
- raw source retained locally: yes/no;
- categories detected;
- transformations applied;
- files withheld and why;
- reviewer;
- date;
- residual uncertainty.

## Pre-commit checklist

- [ ] No secret scanner finding remains unexplained.
- [ ] No private IP, hostname, SSID, MAC or serial remains without a reason.
- [ ] No credential appears in Git diff or history.
- [ ] Logs have been manually sampled after automated redaction.
- [ ] Vendor content is minimal and publishable.
- [ ] Raw archives and firmware images remain ignored.
- [ ] The public artefact still preserves enough technical meaning to reproduce the finding.
