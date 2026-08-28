"""Verify the passive, one-shot wrong-change gate."""

import ast
import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
    observer = (PACKAGE / "remote_observer.py").read_text(encoding="utf-8")
    analyzer = (PACKAGE / "analyze_capture.py").read_text(encoding="utf-8")
    runner = (PACKAGE / "capture_gate.ps1").read_text(encoding="utf-8")
    if contract.get("mission") != "G4-K1-CONTROL-WRONG-CHANGE-T1A-TO-T2C-V1":
        raise ValueError("mission_mismatch")
    if contract.get("starting_route") != "T1A" or contract.get("target_route") != "T2C":
        raise ValueError("route_contract_mismatch")
    if contract.get("automatic_retry") is not False:
        raise ValueError("automatic_retry_forbidden")
    for forbidden in (
        'method="POST"',
        "/printer/gcode/script",
        "/printer/print/start",
        "BOX_",
        "subprocess",
        "os.system",
        ".write_text(",
    ):
        if forbidden in observer:
            raise ValueError("observer_effect_surface:%s" % forbidden)
    ast.parse(observer, filename="remote_observer.py", feature_version=(3, 8))
    ast.parse(analyzer, filename="analyze_capture.py", feature_version=(3, 8))
    observer_hash = digest(PACKAGE / "remote_observer.py")
    if observer_hash not in runner:
        raise ValueError("observer_hash_not_pinned")
    for required in ("HumanPresent", "ImmediateStopAvailable", "HumanConfirmedT2CIdentity"):
        if required not in runner:
            raise ValueError("human_gate_missing:%s" % required)
    if "automatic_retry = $false" not in runner or "Tee-Object -FilePath" not in runner:
        raise ValueError("runner_safety_contract_missing")
    return {
        "status": "WRONG_CHANGE_T1A_TO_T2C_CANDIDATE_OK",
        "observer_sha256": observer_hash,
        "observer_effect": False,
        "automatic_retry": False,
        "human_visible_purge_verdict_required": True,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True, separators=(",", ":")))
