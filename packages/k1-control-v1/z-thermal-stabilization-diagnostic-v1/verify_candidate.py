"""Verify the safe-end candidate and the runner-owned 200 s bed soak."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
_SPEC = importlib.util.spec_from_file_location("z_thermal_stabilization_builder", PACKAGE / "build_candidate.py")
assert _SPEC and _SPEC.loader
builder = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = builder
_SPEC.loader.exec_module(builder)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify() -> dict:
    contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
    source = builder.SOURCE.read_bytes()
    candidate = builder.OUTPUT.read_bytes()
    if digest(source) != contract["source"]["sha256"] or len(source) != contract["source"]["bytes"]:
        raise ValueError("source_identity_drift")
    if digest(candidate) != contract["candidate"]["sha256"] or len(candidate) != contract["candidate"]["bytes"]:
        raise ValueError("candidate_identity_drift")
    if candidate != builder.derive_gcode(source):
        raise ValueError("candidate_has_unreviewed_difference")
    executable = candidate.split(b"; EXECUTABLE_BLOCK_END", 1)[0]
    for command in (b"M140 S55", b"M190 S55", b"G4 P200000", b"M140 S0"):
        if executable.splitlines().count(command) != 0:
            raise ValueError("thermal_command_must_be_runner_owned")
    for forbidden in (b"END_PRINT", b"BOX_END", b"BOX_END_PRINT", b"T0", b"T1", b"T2"):
        if any(line.strip() == forbidden for line in executable.splitlines()):
            raise ValueError("forbidden_executable_command")
    safe_end = builder.SAFE_END_TEMPLATE.read_bytes().strip().replace(b"\r\n", b"\n")
    if safe_end not in executable.replace(b"\r\n", b"\n"):
        raise ValueError("safe_end_drift")
    trial, installer = builder.derive_programs()
    trial_text = trial.decode("utf-8")
    reviewed_runner_commands = (
        'send_gcode_wait("M140 S55\\nM190 S55", 360.0)',
        'send_gcode_wait("G4 P200000", 230.0)',
        'send_gcode_wait("M140 S0", 30.0)',
    )
    for command in reviewed_runner_commands:
        if trial_text.count(command) != 1:
            raise ValueError("runner_soak_command_count_drift")
    if trial_text.index('effect": "bed_thermal_soak_completed_once"') > trial_text.index('KCTRL_CONFIRM_MANUAL_NOZZLE_CLEAN_V1'):
        raise ValueError("manual_clean_token_precedes_soak_completion")
    if trial_text.count('send_gcode_wait("SDCARD_RESET_FILE", 30.0)') != 1:
        raise ValueError("terminal_state_normalization_drift")
    remote = contract["derived_remote_programs"]
    if digest(trial) != remote["derived_trial_sha256"] or digest(installer) != remote["derived_installer_sha256"]:
        raise ValueError("derived_remote_program_drift")
    return {
        "status": "Z_THERMAL_STABILIZATION_DIAGNOSTIC_CANDIDATE_OK",
        "source_sha256": digest(source),
        "candidate_sha256": digest(candidate),
        "runner_soak_commands": contract["runner_soak_commands"],
        "soak_order": contract["soak_order"],
        "soak_seconds": contract["thermal_comparison"]["soak_seconds"],
        "automatic_retry": contract["automatic_retry"],
    }


def main() -> int:
    try:
        print(json.dumps(verify(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({"status": "Z_THERMAL_STABILIZATION_DIAGNOSTIC_CANDIDATE_KO", "error": f"{type(exc).__name__}:{exc}"}, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
