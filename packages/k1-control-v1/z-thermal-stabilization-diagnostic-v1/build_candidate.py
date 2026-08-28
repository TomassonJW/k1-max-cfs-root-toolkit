"""Build the private 200 s thermal-soak diagnostic from the qualified G-code."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "inventory" / "raw" / "20260828-goal3-start-owner-physical-keep-correct-t1a-v1" / "K1-START-OWNER-T1A-2LAYER.gcode"
OUTPUT = ROOT / "inventory" / "raw" / "20260829-goal3-z-thermal-stabilization-diagnostic-v1" / "K1-Z-THERMAL-SOAK-200S-T1A-2LAYER.gcode"
SOURCE_SHA256 = "d98c2a7fe9bb9bc1620cd3cc622edd4a48eaa7bd9c507bd0573de7bc5dab9f7f"
BASE_PACKAGE = ROOT / "packages" / "k1-control-v1" / "start-sequence-owner-physical-keep-correct-t1a-v1"
BASE_TRIAL = BASE_PACKAGE / "remote_trial.py"
BASE_INSTALLER = BASE_PACKAGE / "remote_install.py"
BASE_TRIAL_SHA256 = "5f461db624acaa8682ec20bcd3eed001da39688f1e19a880d8096685c350a68f"
BASE_INSTALLER_SHA256 = "ff84e23462dc642d916bc7d83cfca0eea53414253b7ad940c1cb46be56a5ffa0"
OLD_MISSION = "G4-K1-CONTROL-START-SEQUENCE-OWNER-PHYSICAL-KEEP-CORRECT-T1A-V1"
MISSION = "G4-K1-CONTROL-Z-THERMAL-STABILIZATION-DIAGNOSTIC-V1"
OLD_GCODE_NAME = "K1-START-OWNER-T1A-2LAYER.gcode"
GCODE_NAME = "K1-Z-THERMAL-SOAK-200S-T1A-2LAYER.gcode"
OLD_PREFLIGHT_PRINT_GUARD = '''    if item["print"].get("state") != "standby" or item["print"].get("filename"):
        raise GateError("printer_not_standby")'''
NEW_PREFLIGHT_PRINT_GUARD = '''    print_state = item["print"].get("state")
    print_filename = item["print"].get("filename")
    if print_state not in ("standby", "complete"):
        raise GateError("printer_not_terminal")
    if print_state == "standby" and print_filename:
        raise GateError("standby_filename_present")
    if print_state == "complete" and not print_filename:
        raise GateError("complete_filename_missing")'''
START = b"KCTRL_JOB_BEGIN_KEEP_CORRECT_V1 BED=55 PROBE_NOZZLE=140 FIRST_NOZZLE=190 PLATE=1 PROBE_REV=1 NOZZLE_ID=1 CONFIG_ID=1 X_COUNT=11 Y_COUNT=11"
PRELUDE_LINES = (
    b"; K1_CONTROL_THERMAL_SOAK_DIAGNOSTIC_V1_BEGIN",
    b"M140 S55",
    b"M190 S55",
    b"G4 P200000",
    b"; K1_CONTROL_THERMAL_SOAK_DIAGNOSTIC_V1_END",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def derive_programs() -> tuple[bytes, bytes]:
    trial = BASE_TRIAL.read_bytes()
    installer = BASE_INSTALLER.read_bytes()
    if digest(trial) != BASE_TRIAL_SHA256 or digest(installer) != BASE_INSTALLER_SHA256:
        raise ValueError("base_remote_program_hash_drift")
    trial_text = trial.decode("utf-8")
    trial_text = trial_text.replace(OLD_MISSION, MISSION)
    trial_text = trial_text.replace(OLD_GCODE_NAME, GCODE_NAME)
    trial_text = trial_text.replace("KEEP_CORRECT_T1A_PHYSICAL_", "Z_THERMAL_STABILIZATION_DIAGNOSTIC_")
    if trial_text.count(OLD_PREFLIGHT_PRINT_GUARD) != 1:
        raise ValueError("base_preflight_print_guard_drift")
    trial_text = trial_text.replace(OLD_PREFLIGHT_PRINT_GUARD, NEW_PREFLIGHT_PRINT_GUARD)
    installer_text = installer.decode("utf-8")
    installer_text = installer_text.replace(OLD_GCODE_NAME, GCODE_NAME)
    installer_text = installer_text.replace(
        "eeaf9822a7016f89da45be83e4435f68c1d28441c469a9cde078c9645fcbf429",
        "0000000000000000000000000000000000000000000000000000000000000000",
    )
    return trial_text.encode("utf-8"), installer_text.encode("utf-8")


def build() -> dict:
    source = SOURCE.read_bytes()
    if digest(source) != SOURCE_SHA256:
        raise ValueError("source_gcode_hash_drift")
    lines = source.splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines) if line.rstrip(b"\r\n") == START]
    if len(matches) != 1:
        raise ValueError("executable_start_line_not_unique")
    index = matches[0]
    newline = b"\r\n" if lines[index].endswith(b"\r\n") else b"\n"
    prelude = newline.join(PRELUDE_LINES) + newline
    if PRELUDE_LINES[0] in source:
        raise ValueError("source_already_contains_soak")
    lines[index] = prelude + lines[index]
    candidate = b"".join(lines)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(candidate)
    trial, installer = derive_programs()
    return {
        "status": "Z_THERMAL_STABILIZATION_DIAGNOSTIC_BUILD_OK",
        "source_sha256": digest(source),
        "candidate_sha256": digest(candidate),
        "candidate_bytes": len(candidate),
        "derived_trial_sha256": digest(trial),
        "derived_installer_sha256": digest(installer),
        "output": str(OUTPUT),
    }


def main() -> int:
    import json

    print(json.dumps(build(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
