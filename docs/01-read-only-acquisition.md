# Read-only stock acquisition

## Purpose

Capture enough evidence to understand the exact K1 Max/CFS software stack without altering the printer.

This protocol is intentionally conservative. Root access is used for visibility, not as permission to modify the machine.

## Preconditions

- Gate G1 is satisfied.
- The printer is idle and not heating, moving, calibrating or printing.
- Thomas has manually enabled root access.
- The target is supplied outside Git through an SSH alias or environment variable.
- Raw output directories are ignored by Git.
- No helper, package or custom interface has been installed through this project.

## Capture identity

Create a unique capture ID such as:

`YYYYMMDD-HHMM-k1max-stock`

Use it consistently for the raw directory, redacted output and reports.

## Read-only command classes

Commands may be used only when available on the target and when their invocation has no write side effect:

- identity: `uname`, `hostname` with output redacted, read-only `/etc/*release` inspection;
- filesystems: `cat /proc/mounts`, `mount` without options, `df`, `du` on targeted paths;
- processes: `ps`, read-only `/proc` inspection;
- networking: socket/listener inventory with addresses redacted; no scan of other hosts;
- files: `ls`, `find` on bounded paths, `stat`, `readlink`, `realpath`, `cat`, `head`, `tail`, `grep`;
- hashes: `sha256sum`, `md5sum` only when needed for compatibility comparisons;
- logs: read or copy existing logs without truncation or rotation;
- remote-to-local copy: `scp` or equivalent from printer to workstation.

The agent must inspect command availability and BusyBox behaviour instead of assuming a desktop Linux environment.

## Prohibited command patterns

Do not use:

- remote shell redirection such as `>`, `>>`, `2>`, pipelines ending in a writer or `tee`;
- `sed -i`, editors, `rm`, `mv`, `cp`, `install`, `touch`, `mkdir`, `ln` on the printer;
- `chmod`, `chown`, `mount -o`, `umount`;
- package managers, Git clone/pull, curl-to-shell or helper installers;
- `service`, `systemctl`, init-script actions, `kill`, `pkill`, `reboot`, `poweroff`;
- Moonraker or printer API calls that can start jobs, move axes, heat, extrude, home or calibrate;
- SCP, rsync or SFTP uploads to the printer;
- recursive copy of the whole root filesystem.

## Acquisition order

### 1. Local preflight

- inspect repository status;
- create ignored raw and backup directories locally;
- create a command log locally;
- confirm the target without committing it;
- verify that public output paths contain no previous raw data.

### 2. Minimal connection test

Run one harmless identity command. If the result identifies an unexpected host or firmware family, stop.

### 3. System and firmware identity

Capture, where present:

- kernel and architecture;
- OS/build identifiers;
- board/revision markers;
- printer firmware version;
- both CFS firmware versions or the paths/services that expose them;
- Klipper, Moonraker and Creality component versions;
- boot and root-filesystem characteristics.

### 4. Persistence and mount map

Record:

- mount points and filesystem types;
- read-only/read-write status as observed, without remounting;
- directories known to survive reboot;
- locations used for active configuration, generated configuration, logs and user data.

Do not infer persistence from a path name alone.

### 5. Process and service map

Capture:

- active processes and command lines with secrets redacted;
- init system and service definitions;
- ownership relationships between Creality UI/services, Klipper, Moonraker and CFS components;
- listening local services with private addresses removed from public output.

### 6. Configuration discovery

Locate the active configuration entry point, then follow includes deliberately.

For each relevant file record:

- absolute source path in the private manifest;
- redacted/public logical path or alias;
- size, timestamps and checksum;
- inclusion parent;
- likely role;
- whether it appears generated or hand-maintained;
- whether it survives reboot.

Prioritise:

- `printer.cfg` and includes;
- Z probe/pressure-sensor configuration;
- startup, homing and levelling macros;
- CFS box/tool/load/unload/cut/flush/resume macros;
- persistent variable storage;
- Moonraker and UI configuration;
- service definitions and startup scripts.

### 7. Existing log acquisition

Copy only relevant existing logs. Preserve raw copies locally, then create redacted extracts for analysis.

Do not rotate, truncate or provoke new logs during this phase.

### 8. Sanitisation

Apply `docs/02-data-classification-and-redaction.md` before staging anything.

### 9. Deliverables

- `machine/manifest.<capture-id>.yml` or equivalent redacted manifest;
- `inventory/redacted/<capture-id>/command-log.md`;
- `inventory/redacted/<capture-id>/paths-and-checksums.csv`;
- `inventory/redacted/<capture-id>/services.md`;
- `inventory/redacted/<capture-id>/config-include-graph.md`;
- sanitisation report;
- updated `STATE.md` and `HANDOFF.md`.

## Completion test

The acquisition is complete only if another reviewer can understand what was collected, from where, under which version, and verify that no remote write occurred.
