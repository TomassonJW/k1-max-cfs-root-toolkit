from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-cutter-purge-integrated-r2-offline-v1"
PACKAGE_PATH = str(PACKAGE)
sys.path.insert(0, PACKAGE_PATH)
try:
    from engine import JobTicket, simulate  # noqa: E402
    from fixtures import JOB, REGISTRY, events  # noqa: E402
    from run_scenarios import run  # noqa: E402
finally:
    sys.path.remove(PACKAGE_PATH)
    for module_name in ("engine", "fixtures", "run_scenarios"):
        sys.modules.pop(module_name, None)


def test_scenario_matrix_is_green_and_inert():
    result = run()
    assert result["status"] == "OK"
    assert result["passed"] == result["total"] == 35
    assert result["manifest_names_match"] is True
    assert result["expected_total_match"] is True
    assert all(item["printer_transport"] is False for item in result["cases"])
    assert all(item["physical_action"] is False for item in result["cases"])


def test_complete_cycle_uses_gcode_rules_and_ends_unloaded():
    result = simulate(deepcopy(JOB), deepcopy(REGISTRY), events())
    assert result["phase"] == "closed_safe"
    assert result["failure_code"] is None
    assert result["filament_rule_source"] == "gcode"
    assert result["route"] is None
    assert result["filament_loaded"] is False
    assert result["tool_changes"] == 1
    assert result["equivalent_refills"] == 0
    assert result["printer_transport"] is False
    assert result["deployment_candidate"] is False


def test_equivalent_refill_preserves_the_feature_under_K1_Control():
    flow = events(include_tool_change=False, include_equivalent_refill=True)
    result = simulate(deepcopy(JOB), deepcopy(REGISTRY), flow)
    assert result["phase"] == "closed_safe"
    assert result["failure_code"] is None
    assert result["equivalent_refills"] == 1
    assert result["tool_changes"] == 0
    assert any(item["kind"] == "equivalent_refill_complete" and item["route"] == "T2D" for item in result["trace"])


def test_no_contact_is_accepted_after_load_only_when_count_stays_zero():
    flow = events()
    next(item for item in flow if item["kind"] == "print_started")["probe_count"] = 1
    result = simulate(deepcopy(JOB), deepcopy(REGISTRY), flow)
    assert result["phase"] == "failed_safe"
    assert result["failure_code"] == "contact_after_filament_forbidden"


def test_exact_thermal_profile_is_required_without_nearest_fallback():
    registry = deepcopy(REGISTRY)
    registry[0]["bed_first_c"] = 60.0
    result = simulate(deepcopy(JOB), registry, events())
    assert result["phase"] == "failed_safe"
    assert result["failure_code"] == "exact_thermal_geometry_profile_missing"


def test_gcode_rules_are_not_silently_mixed_with_cfs_defaults():
    job = deepcopy(JOB)
    del job["gcode"]["filament_rules"]["unload_c"]
    result = simulate(job, deepcopy(REGISTRY), events())
    assert result["phase"] == "failed_safe"
    assert result["failure_code"] == "partial_gcode_filament_rules_forbidden"


def test_Y120_memory_is_not_promoted_over_captured_stock_geometry():
    flow = events()
    prime = next(item for item in flow if item["kind"] == "prime_line_complete")
    prime["path_xyz_mm"][1][1] = 120.0
    result = simulate(deepcopy(JOB), deepcopy(REGISTRY), flow)
    assert result["phase"] == "failed_safe"
    assert result["failure_code"] == "prime_line_geometry_unqualified"


def test_end_requires_cutter_and_forbids_full_homing():
    flow = events()
    end = next(item for item in flow if item["kind"] == "end_unload_complete")
    end["g28_count"] = 1
    result = simulate(deepcopy(JOB), deepcopy(REGISTRY), flow)
    assert result["phase"] == "failed_safe"
    assert result["failure_code"] == "end_full_homing_forbidden"


def test_contracts_and_verifier_are_offline():
    contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
    calibration = json.loads((PACKAGE / "calibration-path-contract.json").read_text(encoding="utf-8"))
    stock_delta = json.loads((PACKAGE / "stock-sequence-delta.json").read_text(encoding="utf-8"))
    assert contract["hard_invariants"]["unload_without_cutter"] == "forbidden"
    assert contract["hard_invariants"]["load_without_bin_purge_and_release"] == "forbidden"
    assert contract["hard_invariants"]["full_G28_at_end"] == "forbidden"
    assert contract["derivation"] == "observed_creality_stock_sequence_with_minimal_explicit_delta"
    assert contract["prime_line"]["required_post_line_clearance_origin"] == "explicit_user_correction_not_stock_macro"
    assert calibration["automatic_sequence"][0] == "prove_no_route_and_both_filament_sensors_clear"
    assert calibration["deployment_candidate"] is False
    assert stock_delta["coverage"]["new_discovery_print_required"] is False
    assert stock_delta["implementation_boundary"]["opaque_stock_BOX_calls_allowed_in_final_runtime"] is False
    assert {item["action"] for item in stock_delta["delta"]} >= {
        "KEEP",
        "REPLACE",
        "ADD_EXPLICIT_CORRECTION",
        "KEEP_CHOREOGRAPHY_REIMPLEMENT_DIRECT",
        "KEEP_CAPABILITY_REIMPLEMENT_DIRECT",
    }

    completed = subprocess.run(
        [sys.executable, str(PACKAGE / "verify_candidate.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    result = json.loads(completed.stdout)
    assert result["status"] == "CFS_CUTTER_PURGE_INTEGRATED_R2_OFFLINE_V1_OK"
    assert result["scenarios"] == "35/35"
    assert result["stock_sequence_delta_verified"] is True
    assert result["normal_print_trace_verified"] is True
    assert result["single_change_trace_verified"] is True
    assert result["equivalent_refill_preserved"] is True
    assert result["new_discovery_print_required"] is False
    assert result["printer_transport"] is False
    assert result["physical_action"] is False


class CfsCutterPurgeIntegratedR2OfflineV1Tests(unittest.TestCase):
    def test_scenario_matrix(self):
        test_scenario_matrix_is_green_and_inert()

    def test_complete_cycle(self):
        test_complete_cycle_uses_gcode_rules_and_ends_unloaded()

    def test_equivalent_refill(self):
        test_equivalent_refill_preserves_the_feature_under_K1_Control()

    def test_post_load_contact_guard(self):
        test_no_contact_is_accepted_after_load_only_when_count_stays_zero()

    def test_exact_thermal_profile_guard(self):
        test_exact_thermal_profile_is_required_without_nearest_fallback()

    def test_filament_rule_ownership(self):
        test_gcode_rules_are_not_silently_mixed_with_cfs_defaults()

    def test_prime_line_source(self):
        test_Y120_memory_is_not_promoted_over_captured_stock_geometry()

    def test_end_contract(self):
        test_end_requires_cutter_and_forbids_full_homing()

    def test_offline_evidence_verifier(self):
        test_contracts_and_verifier_are_offline()


if __name__ == "__main__":
    unittest.main()
