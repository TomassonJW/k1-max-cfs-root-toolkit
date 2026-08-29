import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "physical-slices-qualification-v1"


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


verifier = load_module("goal3_physical_completion_registry_test", PACKAGE / "verify_completion.py")


class Goal3PhysicalCompletionRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.matrix = json.loads((PACKAGE / "completion-matrix.json").read_text(encoding="utf-8"))
        cls.remaining_plan = json.loads((PACKAGE / "remaining-execution-plan.json").read_text(encoding="utf-8"))

    def test_registry_is_offline_and_cannot_mutate_the_printer(self):
        self.assertEqual("offline_completion_registry_only", self.contract["authority"])
        self.assertFalse(self.contract["deployment_candidate"])
        self.assertFalse(self.contract["printer_connection"])
        self.assertEqual([], self.contract["remote_commands"])
        self.assertEqual([], self.contract["gcode_commands"])
        self.assertEqual([], self.contract["service_actions"])

    def test_scope_is_exactly_seven_goal3_requirements(self):
        requirements = self.matrix["requirements"]
        self.assertEqual(list(range(1, 8)), [item["order"] for item in requirements])
        self.assertEqual(verifier.EXPECTED_REQUIREMENTS, [item["id"] for item in requirements])
        self.assertEqual(verifier.EXPECTED_SLICE_IDS, [item["slice_id"] for item in requirements])
        self.assertTrue(all(item["required_proofs"] for item in requirements))

    def test_goal4_boundary_is_not_relabelled_as_goal3(self):
        boundary = set(self.contract["goal4_boundary"])
        self.assertIn("atomic_orca_cutover", boundary)
        self.assertIn("three_consecutive_representative_production_prints", boundary)
        self.assertIn("final_project_closure", boundary)
        self.assertEqual(4, self.contract["macro_goal_count"])

    def test_current_gate_records_the_safe_run_ko_and_waits_for_a_renewed_gate(self):
        gate = self.matrix["current_human_gate"]
        self.assertEqual(
            "THERMAL_RUN_94CC4B6_CLOSED_KO_BEFORE_SOAK_PRINT_OR_PURGE_SAFE_FINAL_PROVED_SUCCESSOR_CORRECTED_OFFLINE_WAITING_RENEWED_GATE",
            gate["checkpoint"],
        )
        self.assertIn("PLAN_PREFLIGHT_UPLOAD_OK", gate["technical_status"])
        self.assertIn("RUN_KO_BED_COMPLETION_CHECK_TOO_EARLY", gate["technical_status"])
        self.assertIn("SAFETY_STOP_AND_FINAL_READBACK_OK_NO_RETRY", gate["technical_status"])
        self.assertIn("ORDERED_THERMAL_SCRIPT_AND_REAL_POLLING_READY_OFFLINE", gate["technical_status"])
        self.assertEqual(
            "G4-K1-CONTROL-Z-THERMAL-STABILIZATION-DIAGNOSTIC-V1",
            gate["active_gate"],
        )
        self.assertEqual(
            "AUTHORIZE_ONE_200S_SOAK_AND_TWO_LAYER_R2_TRIAL_WITH_HUMAN_PRESENT_PLATE_CLEAR_NOZZLE_CLEAN_IMMEDIATE_STOP_AND_NO_LIVE_Z_ADJUSTMENT",
            gate["required_human_verdict"],
        )
        self.assertTrue(gate["next_effect_blocked"])

    def test_current_ledger_verifies_as_in_progress_without_effect(self):
        result = verifier.verify()
        self.assertEqual("GOAL3_LEDGER_OK_IN_PROGRESS", result["status"])
        self.assertEqual(2, result["passed_count"])
        self.assertEqual(5, result["pending_count"])
        self.assertTrue(all(value is False for value in result["effects"].values()))

    def test_remaining_plan_keeps_T1A_only_work_before_cross_CFS_exit(self):
        stages = {stage["id"]: stage for stage in self.remaining_plan["stages"]}
        self.assertLess(stages["EDGE_SOURCE_PATTERN_T1A"]["order"], stages["WRONG_CHANGE_T1A_TO_T2C"]["order"])
        self.assertLess(stages["PAUSE_RESUME_T1A"]["order"], stages["WRONG_CHANGE_T1A_TO_T2C"]["order"])
        self.assertEqual(["T2C"], stages["WRONG_CHANGE_T1A_TO_T2C"]["route_after"])
        self.assertEqual(["T1A"], stages["RETURN_T2C_TO_T1A_BEFORE_ACTIVE_CAMPAIGN"]["route_after"])
        reengage = stages["REENGAGE_T1A_FOR_CROSS_CFS_CAMPAIGN"]
        self.assertEqual(
            "PASSIVE_OBSERVER_READY_WAITING_PRIOR_DISENGAGE_AND_AMBIGUITY_CHECKPOINT",
            reengage["status"],
        )
        self.assertTrue((ROOT / reengage["artifact"]).is_file())
        reverse = stages["RETURN_T2C_TO_T1A_BEFORE_ACTIVE_CAMPAIGN"]
        self.assertEqual(
            "PASSIVE_OBSERVER_READY_WAITING_T2C_IDENTITY_AND_PRIOR_STAGES",
            reverse["status"],
        )
        self.assertTrue((ROOT / reverse["artifact"]).is_file())
        long_job = stages["START_LONG_T1A_OWNED_TEST_JOB"]
        self.assertEqual(
            "OFFLINE_PRIVATE_CANDIDATE_READY_BLOCKED_THERMAL_T2_IDENTITY_AND_EQUIVALENT_RUNOUT_PROOF",
            long_job["status"],
        )
        self.assertTrue((ROOT / long_job["artifact"]).is_file())

    def test_ambiguity_window_and_runout_human_dependency_are_explicit(self):
        stages = {stage["id"]: stage for stage in self.remaining_plan["stages"]}
        self.assertEqual([], stages["SEPARATE_DISENGAGE_T1A"]["route_after"])
        self.assertEqual([], stages["AMBIGUOUS_IDENTITY_BLOCK_WITHOUT_ROUTE"]["route_before"])
        self.assertIn("exact_equivalent", stages["EQUIVALENT_RUNOUT_RECOVERY_ON_T2"]["blocked_until"])
        self.assertFalse(any(self.remaining_plan["effects_of_this_plan"].values()))

    def test_completion_policy_cannot_hide_missing_physical_evidence(self):
        policy = self.contract["completion_policy"]
        self.assertTrue(policy["all_requirements_must_be_passed"])
        self.assertTrue(policy["human_evidence_cannot_be_replaced_by_automated_tests"])
        self.assertTrue(policy["goal_cannot_be_renamed_or_split_to_avoid_a_missing_requirement"])
        self.assertTrue(policy["goal4_cannot_start_before_goal3_completion_audit"])


if __name__ == "__main__":
    unittest.main()
