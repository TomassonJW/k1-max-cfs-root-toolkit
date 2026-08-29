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

    def test_current_gate_waits_for_start_owner_safety_r2(self):
        gate = self.matrix["current_human_gate"]
        self.assertEqual(
            "START_OWNER_SAFETY_R2_STOCK_EDGE_PURGE_AND_SAFE_END_OFFLINE_CORRECTION",
            gate["checkpoint"],
        )
        self.assertIn("FIRST_R2_DEPLOY_ROLLED_BACK", gate["technical_status"])
        self.assertIn("FINAL_SAFE_NO_LOGICAL_ROUTE", gate["technical_status"])
        self.assertEqual(
            "G4-K1-CONTROL-START-SEQUENCE-OWNER-SAFETY-R2",
            gate["active_gate"],
        )
        self.assertEqual(
            "RENEW_EXACT_GO_FOR_CORRECTED_COLD_INSTALL_THEN_REESTABLISH_T1A_UNDER_A_SEPARATE_PHYSICAL_GATE",
            gate["required_human_verdict"],
        )
        self.assertTrue(gate["next_effect_blocked"])

    def test_current_ledger_verifies_as_in_progress_without_effect(self):
        result = verifier.verify()
        self.assertEqual("GOAL3_LEDGER_OK_IN_PROGRESS", result["status"])
        self.assertEqual(2, result["passed_count"])
        self.assertEqual(5, result["pending_count"])
        self.assertTrue(all(value is False for value in result["effects"].values()))

    def test_completion_policy_cannot_hide_missing_physical_evidence(self):
        policy = self.contract["completion_policy"]
        self.assertTrue(policy["all_requirements_must_be_passed"])
        self.assertTrue(policy["human_evidence_cannot_be_replaced_by_automated_tests"])
        self.assertTrue(policy["goal_cannot_be_renamed_or_split_to_avoid_a_missing_requirement"])
        self.assertTrue(policy["goal4_cannot_start_before_goal3_completion_audit"])


if __name__ == "__main__":
    unittest.main()
