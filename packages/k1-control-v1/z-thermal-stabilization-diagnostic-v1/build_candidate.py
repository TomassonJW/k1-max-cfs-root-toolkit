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
SAFE_PACKAGE = ROOT / "packages" / "k1-control-v1" / "start-sequence-owner-safety-r2"
SAFE_END_TEMPLATE = SAFE_PACKAGE / "orca-end.gcode"
BASE_TRIAL_SHA256 = "5f461db624acaa8682ec20bcd3eed001da39688f1e19a880d8096685c350a68f"
BASE_INSTALLER_SHA256 = "ff84e23462dc642d916bc7d83cfca0eea53414253b7ad940c1cb46be56a5ffa0"
OLD_START_OWNER_SHA256 = "25291e1534f0ba100d3171b983796089a24cd49fdfcef76817406d325e6d8e03"
R2_START_OWNER_SHA256 = "678582e808d74f6b720ef3d6b52dc2c443c7a0652a62c484319e2b22fba7b0bc"
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
OLD_MOTION_PROJECTION = '''        "motion": {
            "homed_axes": child(status, "toolhead").get("homed_axes"),
            "gcode_position": child(status, "gcode_move").get("gcode_position"),'''
NEW_MOTION_PROJECTION = '''        "motion": {
            "homed_axes": child(status, "toolhead").get("homed_axes"),
            "physical_position": child(status, "toolhead").get("position"),
            "gcode_position": child(status, "gcode_move").get("gcode_position"),'''
OLD_SAFETY_GCODE = '''        request_json("/printer/gcode/script", method="POST", payload={"script": "TURN_OFF_HEATERS\\nM84"})
        actions.append("turn_off_heaters_and_release_axes_once")'''
NEW_SAFETY_GCODE = '''        current = snapshot(0.0)
        homed_axes = current["motion"].get("homed_axes") or ""
        if "xyz" in homed_axes:
            stop_script = "TURN_OFF_HEATERS\\nG90\\nG1 Z50 F600\\nG1 X203 Y273 F1200\\nM400\\nM84"
            stop_action = "turn_off_heaters_safe_park_and_release_once"
        else:
            stop_script = "TURN_OFF_HEATERS\\nM84"
            stop_action = "turn_off_heaters_and_release_unhomed_axes_once"
        request_json("/printer/gcode/script", method="POST", payload={"script": stop_script})
        actions.append(stop_action)'''
OLD_TERMINAL_RELEASE_CHECK = '''    if item["motion"]["homed_axes"] not in (None, ""):
        raise GateError("axes_not_released_after_run")'''
NEW_TERMINAL_RELEASE_CHECK = '''    if item["motion"]["homed_axes"] not in (None, ""):
        raise GateError("axes_not_released_after_run")
    position = item["motion"].get("physical_position")
    if not isinstance(position, list) or len(position) < 3:
        raise GateError("final_physical_position_missing")
    if abs(finite(position[0], "final_physical_position_invalid") - 203.0) > 0.5:
        raise GateError("final_park_x_invalid")
    if abs(finite(position[1], "final_physical_position_invalid") - 273.0) > 0.5:
        raise GateError("final_park_y_invalid")
    if finite(position[2], "final_physical_position_invalid") < 49.5:
        raise GateError("final_bed_clearance_invalid")'''
START = b"KCTRL_JOB_BEGIN_KEEP_CORRECT_V1 BED=55 PROBE_NOZZLE=140 FIRST_NOZZLE=190 PLATE=1 PROBE_REV=1 NOZZLE_ID=1 CONFIG_ID=1 X_COUNT=11 Y_COUNT=11"
PRELUDE_LINES = (
    b"; K1_CONTROL_THERMAL_SOAK_DIAGNOSTIC_V1_BEGIN",
    b"M140 S55",
    b"M190 S55",
    b"G4 P200000",
    b"; K1_CONTROL_THERMAL_SOAK_DIAGNOSTIC_V1_END",
)
OLD_END_LINES = (
    b"KCTRL_START_ABORT_V1",
    b"KCTRL_CLEAR_MANUAL_NOZZLE_CLEAN_V1",
    b"M107 P1",
    b"M107 P2",
    b"M84",
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
    if trial_text.count(OLD_START_OWNER_SHA256) != 1:
        raise ValueError("base_start_owner_hash_drift")
    trial_text = trial_text.replace(OLD_START_OWNER_SHA256, R2_START_OWNER_SHA256)
    if trial_text.count(OLD_PREFLIGHT_PRINT_GUARD) != 1:
        raise ValueError("base_preflight_print_guard_drift")
    trial_text = trial_text.replace(OLD_PREFLIGHT_PRINT_GUARD, NEW_PREFLIGHT_PRINT_GUARD)
    for old, new, code in (
        (OLD_MOTION_PROJECTION, NEW_MOTION_PROJECTION, "base_motion_projection_drift"),
        (OLD_SAFETY_GCODE, NEW_SAFETY_GCODE, "base_safety_stop_drift"),
        (OLD_TERMINAL_RELEASE_CHECK, NEW_TERMINAL_RELEASE_CHECK, "base_terminal_release_check_drift"),
    ):
        if trial_text.count(old) != 1:
            raise ValueError(code)
        trial_text = trial_text.replace(old, new)
    installer_text = installer.decode("utf-8")
    installer_text = installer_text.replace(OLD_GCODE_NAME, GCODE_NAME)
    installer_text = installer_text.replace(
        "eeaf9822a7016f89da45be83e4435f68c1d28441c469a9cde078c9645fcbf429",
        "0000000000000000000000000000000000000000000000000000000000000000",
    )
    return trial_text.encode("utf-8"), installer_text.encode("utf-8")


def derive_gcode(source: bytes) -> bytes:
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
    old_end = newline.join(OLD_END_LINES)
    safe_end_lines = tuple(line.encode("utf-8") for line in SAFE_END_TEMPLATE.read_text(encoding="utf-8").splitlines() if line.strip())
    safe_end = newline.join(safe_end_lines)
    if candidate.count(old_end) != 1:
        raise ValueError("old_unsafe_end_not_unique")
    return candidate.replace(old_end, safe_end)


def build() -> dict:
    source = SOURCE.read_bytes()
    if digest(source) != SOURCE_SHA256:
        raise ValueError("source_gcode_hash_drift")
    candidate = derive_gcode(source)
    if OUTPUT.is_file():
        if OUTPUT.read_bytes() != candidate:
            raise ValueError("persisted_candidate_drift")
    else:
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
