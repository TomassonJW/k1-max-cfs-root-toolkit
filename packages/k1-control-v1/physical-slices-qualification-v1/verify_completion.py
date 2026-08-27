from __future__ import annotations

import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
CONTRACT = PACKAGE / "contract.json"
MATRIX = PACKAGE / "completion-matrix.json"

EXPECTED_REQUIREMENTS = [
    "COLD_CLEAN_MOTION",
    "AUTOMATIC_CLEAN_AND_FINAL_REFERENCE",
    "CFS_START_STATES_AND_TEMPERATURE_OWNER",
    "TOOL_CHANGE_AND_RUNOUT",
    "PAUSE_AND_RESUME",
    "CANCEL_END_AND_SEPARATE_DISENGAGE",
    "EDGE_PROFILE_POINT_EDIT_AND_PHYSICAL_QUALIFICATION",
]

EXPECTED_SLICE_IDS = [
    "CLEAN-MOTION-V1",
    "CLEAN-AND-REFERENCE-V1",
    "CFS-TEMP-OWNER-V1",
    "TOOL-CHANGE-AND-RUNOUT-V1",
    "PAUSE-RESUME-SEMANTICS-V1",
    "END-SEQUENCE-V1",
    "MESH-EDGE-DIAGNOSTIC-V1",
]


class VerificationError(RuntimeError):
    pass


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VerificationError(f"object_required:{path}")
    return value


def require(condition: bool, code: str) -> None:
    if not condition:
        raise VerificationError(code)


def verify() -> dict:
    contract = load_json(CONTRACT)
    matrix = load_json(MATRIX)
    require(contract["contract_id"] == matrix["contract_id"], "contract_id_mismatch")
    require(contract["goal_number"] == 3, "goal_number_mismatch")
    require(contract["macro_goal_count"] == 4, "macro_goal_count_mismatch")
    require(contract["deployment_candidate"] is False, "registry_must_not_deploy")
    for key in ("remote_commands", "gcode_commands", "service_actions"):
        require(contract[key] == [], f"registry_effect_not_empty:{key}")

    requirements = matrix["requirements"]
    require(isinstance(requirements, list), "requirements_list_missing")
    require([item["order"] for item in requirements] == list(range(1, 8)), "order_mismatch")
    require([item["id"] for item in requirements] == EXPECTED_REQUIREMENTS, "scope_mismatch")
    require([item["slice_id"] for item in requirements] == EXPECTED_SLICE_IDS, "slice_id_mismatch")
    for item in requirements:
        require(bool(item["required_proofs"]), f"proofs_missing:{item['id']}")
        evidence = item["evidence"]
        if item["status"] == "PASSED":
            require(evidence is not None, f"passed_without_evidence:{item['id']}")
        if evidence is not None:
            require((ROOT / evidence).is_file(), f"evidence_missing:{item['id']}")

    clean = requirements[0]
    clean_evidence = load_json(ROOT / clean["evidence"])
    require(
        clean_evidence["status"] == "checkpoint_d1_technical_ok_awaiting_human_verdict",
        "clean_motion_status_drift",
    )
    require(clean_evidence["checkpoint_d"]["run_d1"]["human_verdict"] is None, "d1_verdict_drift")
    require(clean_evidence["checkpoint_d"]["d2_executed"] is False, "d2_must_not_be_executed")

    mesh = requirements[-1]
    mesh_evidence = load_json(ROOT / mesh["evidence"])
    require(mesh_evidence["source"]["immutable"] is True, "mesh_source_must_be_immutable")
    require(mesh_evidence["source"]["id"] == "k1_p001_t055_r001_n11x11", "mesh_source_drift")
    require(mesh_evidence["qualification"]["physical_test"] == "not_run", "mesh_physical_status_drift")
    require(mesh_evidence["qualification"]["robust"] is False, "robust_label_premature")

    passed = [item["id"] for item in requirements if item["status"] == "PASSED"]
    pending = [item["id"] for item in requirements if item["status"] != "PASSED"]
    complete = not pending
    require(matrix["goal_status"] == ("PASSED" if complete else "IN_PROGRESS"), "goal_status_mismatch")
    if complete:
        audit_evidence = matrix["completion_audit_evidence"]
        require(audit_evidence is not None, "completion_audit_evidence_missing")
        require((ROOT / audit_evidence).is_file(), "completion_audit_file_missing")
    return {
        "schema": 1,
        "contract_id": contract["contract_id"],
        "status": "GOAL3_LEDGER_OK_COMPLETE" if complete else "GOAL3_LEDGER_OK_IN_PROGRESS",
        "passed_count": len(passed),
        "pending_count": len(pending),
        "pending_requirements": pending,
        "current_human_gate": matrix["current_human_gate"],
        "effects": {
            "printer_connection": False,
            "gcode": False,
            "remote_write": False,
            "service_action": False,
        },
    }


def main() -> int:
    try:
        result = verify()
    except Exception as exc:
        print(json.dumps({"status": "GOAL3_LEDGER_KO", "error": f"{type(exc).__name__}:{exc}"}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
