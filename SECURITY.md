# Security policy

## Scope

This repository deals with root access to network-connected production hardware. A configuration mistake can interrupt printing, damage hardware or expose credentials and private network information.

## Never publish

- root passwords, SSH private keys or authorised-key material;
- Wi-Fi credentials, SSIDs or cloud tokens;
- private IP addresses or internal hostnames unless deliberately anonymised;
- MAC addresses, serial numbers or account identifiers without a demonstrated need;
- complete raw backups or unreviewed logs;
- proprietary firmware images or opaque vendor binaries;
- copied vendor configuration whose redistribution rights are unclear.

## Reporting a repository security issue

Open a minimal GitHub issue only when the report contains no exploit secret, credential or private machine data. For a sensitive report, contact the repository owner privately through an already trusted channel and provide only the minimum evidence required.

## Operational safety

- Treat every remote write as a deployment.
- Require backup, checksum, reviewed diff, validation and rollback before deployment.
- Do not expose the printer directly to the public Internet for convenience.
- Do not create a persistent remote-access path merely to simplify agent use.
- Stop when machine identity or command side effects are uncertain.

## Supported security state

The current repository phase supports read-only acquisition only. No remote mutation workflow is considered approved or production-ready yet.
