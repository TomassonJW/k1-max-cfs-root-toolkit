# Moonraker path warnings — read-only report

Date: 2026-08-21
Scope: post-installation diagnosis of the validated V3 control foundation
Printer mutation: none

## Trigger

After the nginx account was verified and the real Mainsail dashboard opened,
Moonraker reported two warnings:

- Klipper's active configuration file is outside Moonraker's `config` root;
- Klipper's `virtual_sdcard` path differs from Moonraker's `gcodes` root.

The dashboard, authentication and Mainsail-to-Moonraker-to-Klipper connection
otherwise worked.

## Read-only findings

The bounded remote inspection confirmed these distinct paths:

| Role | Path | Observed state |
|---|---|---|
| Moonraker data root | `/usr/data/k1-control-v1/state` | present |
| Moonraker config root | `/usr/data/k1-control-v1/state/config` | present and empty |
| Moonraker G-code root | `/usr/data/k1-control-v1/state/gcodes` | present and empty |
| Active Creality config root | `/usr/data/printer_data/config` | present |
| Active Creality G-code root | `/usr/data/printer_data/gcodes` | present |

The installed pinned Moonraker source was inspected in place. Its file manager:

- derives `config` and `gcodes` from the command-line data path;
- warns when Klipper's active config is not inside that `config` root;
- warns when Klipper's `virtual_sdcard` directory is not the same filesystem
  directory as the registered `gcodes` root;
- grants full API access to `gcodes` and grants config write access by default.

This exactly explains both warnings. They are not evidence of a broken Klipper
connection, but they prove that V3 file-manager path integration is incomplete.

## Decision

Do not follow the warning's generic suggestion to change Klipper's
`[virtual_sdcard]` path. On this K1 Max that would move the path used by the
existing Creality print stack and would change print behaviour outside V3.

Moonraker's official installation documentation explicitly allows `config` and
`gcodes` inside its data path to be symbolic links to the already active
directories. Its configuration also allows the config root to be exposed as
read-only with `enable_config_write_access: False`.

References:

- <https://moonraker.readthedocs.io/en/latest/installation/#data-folder-structure>
- <https://moonraker.readthedocs.io/en/stable/configuration/#file_manager>
- <https://moonraker.readthedocs.io/en/latest/external_api/file_manager/>

The proposed correction is a new, separate candidate:
`G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1`. It is not authorised. A previous V3 GO
does not authorise it.

Its offline design must:

1. preserve `/usr/data/printer_data/config` and
   `/usr/data/printer_data/gcodes` as the active Creality paths;
2. replace only the two confirmed-empty Moonraker directories with reversible
   symbolic links after backup and checksum evidence;
3. set `enable_config_write_access: False` and prove that configuration writes
   through Moonraker are refused;
4. restart only the dedicated Moonraker service if execution is later
   authorised; no printer reboot is allowed;
5. prove that both warnings disappear while Klipper, Creality interfaces,
   nginx, resources and both CFS remain green;
6. rollback at the first mismatch.

Because this exposes the real G-code directory to Moonraker's file API, the
offline review must explicitly document upload, deletion and start-print access
before deployment. No G-code may be uploaded, deleted or started during the
path-correction validation.

## Operator guidance until correction

- Mainsail may be used to observe dashboard state and temperatures.
- Do not use its config editor, file upload/delete actions, console, macros,
  movement, homing or heating controls.
- A normal print may use the previously trusted Creality/Orca route unchanged.
- Keep the current Orca/PHP `+0.27 mm` post-processor, Start G-code and
  tool-change G-code unchanged.
- Do not count the eight-hour acceptance observation until the final intended
  foundation state, including any authorised path correction, is installed.

## Evidence boundary

Only path names, directory types, permissions and the relevant installed source
logic were read. No remote file, directory, link, service, port, configuration,
G-code or printer state was changed. Private raw captures remain ignored and
must not be committed.
