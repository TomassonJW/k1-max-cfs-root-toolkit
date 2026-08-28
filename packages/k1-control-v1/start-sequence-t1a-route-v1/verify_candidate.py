"""Verify the local, read-only T1A route gate candidate."""

from __future__ import print_function

import ast
import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
    observer = (PACKAGE / "remote_observer.py").read_text(encoding="utf-8")
    recovery = (PACKAGE / "remote_recovery.py").read_text(encoding="utf-8")
    analyzer = (PACKAGE / "analyze_capture.py").read_text(encoding="utf-8")
    capture = (PACKAGE / "capture_route_gate.ps1").read_text(encoding="utf-8")
    recovery_runner = (PACKAGE / "recover_route_gate.ps1").read_text(encoding="utf-8")
    if contract.get("mission") != "G4-K1-CONTROL-START-SEQUENCE-T1A-ROUTE-V1":
        raise ValueError("mission_mismatch")
    if contract.get("automatic_effect_connector") is not False:
        raise ValueError("automatic_effect_connector_forbidden")
    action = contract.get("operator_action", {})
    if action.get("action") != "load_T1A_once" or action.get("maximum_attempts") != 1:
        raise ValueError("operator_action_not_bounded")
    if action.get("automatic_retry") is not False:
        raise ValueError("automatic_retry_forbidden")
    for forbidden in (
        "gcode/script",
        "BOX_EXTRUDE_MATERIAL",
        "BOX_EXTRUDER_EXTRUDE",
        "BOX_START_PRINT",
        "TURN_OFF_HEATERS",
        "subprocess",
        "os.system",
    ):
        if forbidden in observer:
            raise ValueError("observer_effect_path_forbidden:%s" % forbidden)
    expected_hash = sha256(PACKAGE / "remote_observer.py")
    if expected_hash not in capture:
        raise ValueError("observer_hash_not_pinned")
    recovery_hash = sha256(PACKAGE / "remote_recovery.py")
    if recovery_hash not in recovery_runner:
        raise ValueError("recovery_hash_not_pinned")
    if "Tee-Object -FilePath $CapturePath" not in capture:
        raise ValueError("capture_not_streamed")
    if "automatic_retry = $false" not in capture:
        raise ValueError("automatic_retry_metadata_missing")
    ast.parse(observer, filename="remote_observer.py", feature_version=(3, 8))
    ast.parse(recovery, filename="remote_recovery.py", feature_version=(3, 8))
    ast.parse(analyzer, filename="analyze_capture.py", feature_version=(3, 8))
    return {
        "status": "START_SEQUENCE_T1A_ROUTE_V1_CANDIDATE_OK",
        "observer_sha256": expected_hash,
        "recovery_sha256": recovery_hash,
        "automatic_effect_connector": False,
        "operator_action": "load_T1A_once",
        "maximum_attempts": 1,
        "automatic_retry": False,
        "print_start": False,
    }


def main():
    print(json.dumps(verify(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
