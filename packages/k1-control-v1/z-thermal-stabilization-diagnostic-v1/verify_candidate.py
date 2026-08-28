"""Verify that the diagnostic differs only by the reviewed 200 s bed soak."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
sys.path.insert(0, str(PACKAGE))
import build_candidate as builder  # noqa: E402


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
    lines = source.splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines) if line.rstrip(b"\r\n") == builder.START]
    if len(matches) != 1:
        raise ValueError("source_start_not_unique")
    index = matches[0]
    newline = b"\r\n" if lines[index].endswith(b"\r\n") else b"\n"
    prelude = newline.join(builder.PRELUDE_LINES) + newline
    lines[index] = prelude + lines[index]
    if candidate != b"".join(lines):
        raise ValueError("candidate_has_unreviewed_difference")
    executable = candidate.split(b"; EXECUTABLE_BLOCK_END", 1)[0]
    for command in (b"M140 S55", b"M190 S55", b"G4 P200000"):
        if executable.splitlines().count(command) != 1:
            raise ValueError("thermal_command_count_drift")
    for forbidden in (b"END_PRINT", b"BOX_END", b"BOX_END_PRINT", b"T0", b"T1", b"T2"):
        if any(line.strip() == forbidden for line in executable.splitlines()):
            raise ValueError("forbidden_executable_command")
    if b"KCTRL_START_ABORT_V1\nKCTRL_CLEAR_MANUAL_NOZZLE_CLEAN_V1\nM107 P1\nM107 P2\nM84" not in executable.replace(b"\r\n", b"\n"):
        raise ValueError("safe_end_drift")
    trial, installer = builder.derive_programs()
    remote = contract["derived_remote_programs"]
    if digest(trial) != remote["derived_trial_sha256"] or digest(installer) != remote["derived_installer_sha256"]:
        raise ValueError("derived_remote_program_drift")
    return {
        "status": "Z_THERMAL_STABILIZATION_DIAGNOSTIC_CANDIDATE_OK",
        "source_sha256": digest(source),
        "candidate_sha256": digest(candidate),
        "inserted_commands": contract["only_inserted_executable_commands"],
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
