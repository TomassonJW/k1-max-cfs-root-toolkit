from __future__ import annotations

import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
CAMPAIGN = PACKAGE / "physical-campaign.json"
EXPECTED_IDS = [
    "EMPTY_LOAD_T1A",
    "KEEP_CORRECT_T1A",
    "WRONG_CHANGE_T1A_TO_T2C",
    "AMBIGUOUS_IDENTITY_BLOCK",
]


class CampaignError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise CampaignError(code)


def verify() -> dict:
    campaign = json.loads(CAMPAIGN.read_text(encoding="utf-8"))
    checkpoints = campaign["checkpoints"]
    require([item["order"] for item in checkpoints] == [1, 2, 3, 4], "checkpoint_order_drift")
    require([item["id"] for item in checkpoints] == EXPECTED_IDS, "checkpoint_scope_drift")
    require(campaign["automatic_retry"] is False, "automatic_retry_enabled")
    require(campaign["completion"]["all_checkpoints_must_pass"] is True, "partial_completion_allowed")
    require(campaign["completion"]["visible_purge_requires_human_evidence"] is True, "purge_human_gate_missing")
    require(campaign["terminal_invariants"]["heater_targets_zero"] is True, "heater_stop_missing")

    routes = set()
    verdicts = set()
    for checkpoint in checkpoints:
        routes.update(checkpoint.get("starting_routes", []))
        routes.update(checkpoint.get("expected_final_routes", []))
        verdict = checkpoint["accepted_human_verdict"]
        require(verdict not in verdicts, "duplicate_human_verdict")
        verdicts.add(verdict)
        require(bool(checkpoint["required_observations"]), "required_observations_missing")

    require(any(route.startswith("T1") for route in routes), "T1_not_covered")
    require(any(route.startswith("T2") for route in routes), "T2_not_covered")
    ambiguous = checkpoints[-1]
    require(ambiguous["expected_effects"] == [], "ambiguous_case_has_effect")
    require(ambiguous["requires_read_only_decision_adapter"] is True, "ambiguous_adapter_missing")

    passed = [item["id"] for item in checkpoints if item["evidence_status"] == "PASSED"]
    pending = [item["id"] for item in checkpoints if item["evidence_status"] != "PASSED"]
    return {
        "schema": 1,
        "campaign_id": campaign["campaign_id"],
        "status": "CFS_PHYSICAL_CAMPAIGN_COMPLETE" if not pending else "CFS_PHYSICAL_CAMPAIGN_READY_INCOMPLETE",
        "passed_count": len(passed),
        "pending_count": len(pending),
        "pending_checkpoints": pending,
        "effects": {
            "printer_connection": False,
            "gcode": False,
            "cfs_action": False,
            "remote_write": False,
        },
    }


def main() -> int:
    try:
        result = verify()
    except Exception as exc:
        print(json.dumps({"status": "CFS_PHYSICAL_CAMPAIGN_KO", "error": f"{type(exc).__name__}:{exc}"}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
