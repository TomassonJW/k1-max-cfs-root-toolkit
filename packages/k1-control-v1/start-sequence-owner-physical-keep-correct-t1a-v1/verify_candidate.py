"""Verify the complete physical KEEP_CORRECT_T1A gate candidate."""

import ast
import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
GCODE = ROOT / "inventory" / "raw" / "20260828-goal3-start-owner-physical-keep-correct-t1a-v1" / "K1-START-OWNER-T1A-2LAYER.gcode"
EXPECTED_GCODE = "eeaf9822a7016f89da45be83e4435f68c1d28441c469a9cde078c9645fcbf429"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def executable_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith(";")]


def verify():
    contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
    trial = (PACKAGE / "remote_trial.py").read_text(encoding="utf-8")
    installer = (PACKAGE / "remote_install.py").read_text(encoding="utf-8")
    analyzer = (PACKAGE / "analyze_capture.py").read_text(encoding="utf-8")
    runner = (PACKAGE / "run_trial.ps1").read_text(encoding="utf-8")
    if contract.get("mission") != "G4-K1-CONTROL-START-SEQUENCE-OWNER-PHYSICAL-KEEP-CORRECT-T1A-V1":
        raise ValueError("mission_mismatch")
    if contract.get("automatic_retry") is not False:
        raise ValueError("automatic_retry_forbidden")
    if digest(GCODE) != EXPECTED_GCODE or GCODE.stat().st_size != 90552:
        raise ValueError("gcode_identity_mismatch")
    lines = executable_lines(GCODE.read_text(encoding="utf-8", errors="replace"))
    if sum(line.startswith("KCTRL_JOB_BEGIN_KEEP_CORRECT_V1 ") for line in lines) != 1:
        raise ValueError("owned_start_call_count")
    joined = "\n".join(lines)
    for forbidden in ("T0", "START_PRINT", "BED_MESH_CALIBRATE", "BOX_", "G29"):
        if forbidden in joined:
            raise ValueError("forbidden_executable_token:%s" % forbidden)
    for source, name in ((trial, "remote_trial.py"), (installer, "remote_install.py"), (analyzer, "analyze_capture.py")):
        ast.parse(source, filename=name, feature_version=(3, 8))
    if digest(PACKAGE / "remote_trial.py") not in runner:
        raise ValueError("trial_hash_not_pinned")
    if digest(PACKAGE / "remote_install.py") not in runner:
        raise ValueError("installer_hash_not_pinned")
    for required in ("HumanPresent", "PlateClear", "ManualNozzleCleanConfirmed", "ImmediateStopAvailable"):
        if required not in runner:
            raise ValueError("human_gate_missing:%s" % required)
    if "automatic_retry = $false" not in runner or "Tee-Object -FilePath" not in runner:
        raise ValueError("runner_safety_contract_missing")
    return {
        "status": "KEEP_CORRECT_T1A_PHYSICAL_CANDIDATE_OK",
        "gcode_sha256": EXPECTED_GCODE,
        "gcode_bytes": GCODE.stat().st_size,
        "trial_sha256": digest(PACKAGE / "remote_trial.py"),
        "installer_sha256": digest(PACKAGE / "remote_install.py"),
        "automatic_retry": False,
        "human_verdict_required": True,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True, separators=(",", ":")))
