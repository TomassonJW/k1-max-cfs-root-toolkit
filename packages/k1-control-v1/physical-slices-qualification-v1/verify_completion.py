from __future__ import annotations

import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
CONTRACT = PACKAGE / "contract.json"
MATRIX = PACKAGE / "completion-matrix.json"
REMAINING_PLAN = PACKAGE / "remaining-execution-plan.json"
MANUAL_CLEANING_POLICY = ROOT / "design" / "manual-nozzle-cleaning-policy-v1.json"

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
    remaining_plan = load_json(REMAINING_PLAN)
    require(contract["contract_id"] == matrix["contract_id"], "contract_id_mismatch")
    require(contract["goal_number"] == 3, "goal_number_mismatch")
    require(contract["macro_goal_count"] == 4, "macro_goal_count_mismatch")
    require(contract["deployment_candidate"] is False, "registry_must_not_deploy")
    require(remaining_plan["goal"] == contract["contract_id"], "remaining_plan_goal_mismatch")
    require(not any(remaining_plan["effects_of_this_plan"].values()), "remaining_plan_must_be_effect_free")
    stages = remaining_plan["stages"]
    require([stage["order"] for stage in stages] == list(range(1, len(stages) + 1)), "remaining_plan_order_mismatch")
    require(len({stage["id"] for stage in stages}) == len(stages), "remaining_plan_duplicate_stage")
    for stage in stages:
        require(stage["automatic_retry"] is False, f"remaining_plan_retry_enabled:{stage['id']}")
        if stage["human_gate"]:
            require(stage["id"] != "GOAL3_REQUIREMENT_BY_REQUIREMENT_COMPLETION_AUDIT", "audit_cannot_be_human_effect_gate")
        artifact = stage["artifact"]
        if artifact is not None:
            require((ROOT / artifact).is_file(), f"remaining_plan_artifact_missing:{stage['id']}")
    stage_order = {stage["id"]: stage["order"] for stage in stages}
    require(stage_order["EDGE_SOURCE_PATTERN_T1A"] < stage_order["WRONG_CHANGE_T1A_TO_T2C"], "edge_must_precede_T2C_exit")
    require(stage_order["PAUSE_RESUME_T1A"] < stage_order["WRONG_CHANGE_T1A_TO_T2C"], "pause_must_precede_T2C_exit")
    require(stage_order["NORMAL_END_KEEP_T1A"] < stage_order["WRONG_CHANGE_T1A_TO_T2C"], "normal_end_must_precede_T2C_exit")
    require(stage_order["SEPARATE_DISENGAGE_T1A"] < stage_order["AMBIGUOUS_IDENTITY_BLOCK_WITHOUT_ROUTE"], "disengage_must_create_ambiguity_window")
    require(stage_order["AMBIGUOUS_IDENTITY_BLOCK_WITHOUT_ROUTE"] < stage_order["REENGAGE_T1A_FOR_CROSS_CFS_CAMPAIGN"], "ambiguity_must_be_tested_before_reengagement")
    require(stage_order["START_LONG_T1A_OWNED_TEST_JOB"] < stage_order["MID_PRINT_TOOL_CHANGE_T1A_TO_T2C"], "tool_change_requires_active_job")
    require(stage_order["MID_PRINT_TOOL_CHANGE_T1A_TO_T2C"] < stage_order["EQUIVALENT_RUNOUT_RECOVERY_ON_T2"], "runout_must_follow_cross_CFS_change")
    runout = next(stage for stage in stages if stage["id"] == "EQUIVALENT_RUNOUT_RECOVERY_ON_T2")
    require(bool(runout.get("blocked_until")), "runout_equivalence_proof_missing")
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
        clean_evidence["status"] == "closed_ok_human_qualified_two_brush_cold_motion",
        "clean_motion_status_drift",
    )
    require(clean_evidence["checkpoint_d"]["run_d1"]["human_verdict"] == "D1_OK", "d1_verdict_drift")
    require(clean_evidence["checkpoint_d"]["d2_executed"] is True, "d2_execution_missing")
    require(clean_evidence["checkpoint_d"]["run_d2"]["human_verdict"] == "D2_OK", "d2_verdict_drift")
    require(clean_evidence["checkpoint_d"]["d3_executed"] is True, "d3_execution_missing")
    require(clean_evidence["checkpoint_d"]["run_d3"]["human_verdict"] == "D3_OK", "d3_verdict_drift")
    require(
        clean_evidence["manual_geometry_capture_v2_primary_brush"]["human_verdict"] == "OK",
        "primary_geometry_verdict_drift",
    )
    require(
        clean_evidence["manual_geometry_capture_v1_secondary_purge_brush"]["human_verdict"] == "GEOMETRY_OK",
        "secondary_geometry_verdict_drift",
    )
    brush_trials = clean_evidence["brush_trial_candidate"]
    require(
        brush_trials["e1"]["explicit_human_requested_rerun"]["human_verdict"]
        == "KO_TOO_FAR_FROM_BOTH_BRUSHES_TO_CLEAN",
        "e1_verdict_drift",
    )
    require(brush_trials["e2"]["human_verdict"] == "E2_OK", "e2_verdict_drift")
    require(
        brush_trials["e3"]["human_verdict"] == "QUASI_OK_END_MARGIN_TOO_LARGE",
        "e3_verdict_drift",
    )
    require(
        brush_trials["e3"]["r2_run"]["human_verdict"] == "E3_R2_OK_WITH_RECIPE_REFINEMENT",
        "e3_r2_verdict_drift",
    )
    require(brush_trials["e4"]["human_verdict"] == "E4_OK", "e4_verdict_drift")

    cleaning = requirements[1]
    require(cleaning["status"] == "PASSED", "cleaning_policy_not_passed")
    require(
        cleaning.get("resolution") == "AUTOMATIC_REJECTED_MANUAL_ONLY_POLICY_ACCEPTED",
        "cleaning_resolution_drift",
    )
    cleaning_evidence = load_json(ROOT / cleaning["evidence"])
    require(
        cleaning_evidence["status"] == "CLOSED_AUTOMATIC_CLEANING_REJECTED_MANUAL_CLEANING_REQUIRED",
        "automatic_cleaning_not_closed",
    )
    v3 = cleaning_evidence["live_read_only_evidence"]["primary_brush_v3_clean_cycle"]
    require(
        v3["human_visual_verdict"] == "KO_NOT_CONVINCING_AUTOMATIC_CLEANING_ABANDONED",
        "v3_human_verdict_drift",
    )
    require(v3["heater_targets_zero"] is True, "v3_heaters_not_zero")
    require(v3["final_reference_executed"] is False, "final_reference_must_not_be_invented")
    policy = load_json(MANUAL_CLEANING_POLICY)
    require(policy["status"] == "canonical", "manual_cleaning_policy_not_canonical")
    require(policy["automatic_cleaning"]["allowed"] is False, "automatic_cleaning_still_allowed")
    require(
        policy["historical_requirement_resolution"]
        == "AUTOMATIC_REJECTED_MANUAL_ONLY_POLICY_ACCEPTED",
        "manual_cleaning_policy_resolution_drift",
    )

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
