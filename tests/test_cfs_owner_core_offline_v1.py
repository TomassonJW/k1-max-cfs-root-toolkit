from importlib.util import module_from_spec, spec_from_file_location
import ast
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-owner-core-offline-v1"


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = load_module("cfs_owner_core_offline_runner_test", PACKAGE / "run_scenarios.py")


class CfsOwnerCoreOfflineV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.matrix = json.loads((PACKAGE / "scenarios.json").read_text(encoding="utf-8"))

    def test_contract_is_pure_offline_and_not_deployable(self):
        self.assertEqual("offline_only", self.contract["authority"])
        self.assertEqual(
            "offline_owner_core_closed_green_effects_unqualified",
            self.contract["status"],
        )
        self.assertTrue(all(value is False for value in self.contract["boundaries"].values()))
        self.assertFalse(self.contract["truthful_limits"]["runtime_owner_installed"])
        self.assertFalse(self.contract["truthful_limits"]["production_authorized"])

    def test_s12_safe_source_is_pinned_without_inventing_an_identical_pair(self):
        result = runner.verify_s12_source()
        self.assertEqual("OK", result["status"])
        self.assertTrue(all(result["checks"].values()))
        self.assertFalse(self.contract["truthful_limits"]["recorded_s12_identical_pair_present"])
        self.assertFalse(self.contract["truthful_limits"]["synthetic_identical_pairs_are_physical_proof"])

    def test_all_twenty_one_scenarios_are_deterministic_and_green(self):
        first = runner.run()
        second = runner.run()
        self.assertEqual(first, second)
        self.assertEqual("OK", first["verdict"])
        self.assertEqual(21, first["passed"])
        self.assertEqual(21, first["total"])
        self.assertFalse(first["printer_connection"])
        self.assertFalse(first["gcode_sent"])
        self.assertFalse(first["physical_action"])
        self.assertFalse(first["deployment_candidate"])

    def test_matrix_ids_match_contract_exactly(self):
        matrix_ids = [item["id"] for item in self.matrix["scenarios"]]
        self.assertEqual(self.contract["required_scenarios"], matrix_ids)
        self.assertEqual(len(matrix_ids), len(set(matrix_ids)))

    def test_s12_enabled_stock_policy_only_creates_a_non_dispatchable_intent(self):
        result = runner.run_one("s12_snapshot_requests_stock_owner_exclusion")
        self.assertEqual("lease_pending", result["phase"])
        self.assertFalse(result["lease_active"])
        self.assertEqual(1, result["saved_stock_auto_refill"])
        self.assertEqual(["exclude_stock_auto_refill"], [item["operation"] for item in result["pending_intents"]])
        self.assertTrue(all(item["dispatchable"] is False for item in result["pending_intents"]))
        self.assertEqual(0, result["simulated_observations"])

    def test_lease_requires_verified_exclusion_and_preserves_print_enable(self):
        result = runner.run_one("lease_activates_only_after_verified_exclusion")
        self.assertEqual("owned_idle", result["phase"])
        self.assertTrue(result["lease_active"])
        self.assertEqual([], result["pending_intents"])
        self.assertIn("lease-001:owner-exclusion", result["completed_intent_ids"])

    def test_start_plans_are_distinct_and_keep_never_cuts_or_loads(self):
        keep = runner.run_one("start_keeps_confirmed_route_without_cut_or_load")
        absent = runner.run_one("start_absent_plans_load_then_purge")
        wrong = runner.run_one("start_wrong_plans_cut_retract_load_purge")
        self.assertEqual(["purge_visible"], [item["operation"] for item in keep["pending_intents"]])
        self.assertEqual(
            ["load_selected_route", "purge_visible"],
            [item["operation"] for item in absent["pending_intents"]],
        )
        self.assertEqual(
            [
                "cut_current_filament",
                "retract_current_filament",
                "load_selected_route",
                "purge_visible",
            ],
            [item["operation"] for item in wrong["pending_intents"]],
        )
        for result in (keep, absent, wrong):
            self.assertTrue(all(item["dispatchable"] is False for item in result["pending_intents"]))

    def test_unknown_material_and_multiple_routes_fail_before_new_intent(self):
        unknown = runner.run_one("start_unknown_material_blocks")
        multiple = runner.run_one("multiple_engaged_routes_block")
        self.assertEqual("engaged_material_identity_unproven", unknown["reason_code"])
        self.assertEqual("multiple_engaged_routes", multiple["reason_code"])
        self.assertEqual([], unknown["pending_intents"])
        self.assertEqual([], multiple["pending_intents"])
        self.assertIsNone(multiple["saved_stock_auto_refill"])

    def test_unique_identical_runout_can_cross_to_second_cfs_without_stock_resume(self):
        result = runner.run_one("runout_selects_unique_identical_cross_cfs")
        self.assertEqual("printing", result["phase"])
        self.assertEqual("T2A", result["active_route"])
        self.assertFalse(result["resume_eligible"])
        self.assertEqual(4, result["simulated_observations"])
        resume = next(item for item in result["journal"] if item["kind"] == "owned_resume_accepted")
        self.assertEqual("T2A", resume["active_route"])

    def test_runout_zero_multiple_and_near_matches_all_remain_blocked(self):
        expected = {
            "runout_rejects_no_identical_candidate": "identical_replacement_missing",
            "runout_rejects_multiple_identical_candidates": "identical_replacement_ambiguous",
            "runout_rejects_near_match": "identical_replacement_missing",
        }
        for scenario_id, reason in expected.items():
            with self.subTest(scenario_id=scenario_id):
                result = runner.run_one(scenario_id)
                self.assertEqual("blocked_safe", result["verdict"])
                self.assertEqual(reason, result["reason_code"])
                self.assertFalse(result["resume_eligible"])
                self.assertFalse(result["replay_allowed"])

    def test_mapping_epoch_and_stock_callbacks_invalidate_the_owner(self):
        expected = {
            "stale_mapping_blocks_before_plan": "mapping_revision_changed",
            "connection_epoch_change_invalidates_lease": "connection_epoch_changed",
            "stock_callback_conflict_blocks": "stock_owner_conflict",
        }
        for scenario_id, reason in expected.items():
            with self.subTest(scenario_id=scenario_id):
                result = runner.run_one(scenario_id)
                self.assertEqual(reason, result["reason_code"])
                self.assertFalse(result["replay_allowed"])
                self.assertFalse(result["resume_eligible"])

    def test_protected_state_is_compared_instead_of_trusting_a_boolean(self):
        snapshot = runner.base_snapshot(engaged_routes=["T1A"], head_sensor_present=True)
        events = runner.lease_events(snapshot)
        plan = runner.plan_start_event(snapshot)
        plan["observed"]["protected"]["mesh_profile"] = "default"
        events.append(plan)
        result = runner.simulate(runner.CONTRACT, snapshot, runner.base_inventory(), events)
        self.assertEqual("protected_state_changed", result["reason_code"])
        self.assertEqual([], result["pending_intents"])
        self.assertFalse(result["replay_allowed"])

    def test_boolean_stock_policy_is_rejected_as_an_ambiguous_value(self):
        snapshot = runner.base_snapshot()
        snapshot["stock_auto_refill"] = True
        result = runner.simulate(runner.CONTRACT, snapshot, runner.base_inventory(), [])
        self.assertEqual("stock_auto_refill_invalid", result["reason_code"])
        self.assertEqual("blocked_safe", result["phase"])
        self.assertFalse(result["lease_active"])

    def test_incomplete_protected_state_is_rejected_before_a_lease(self):
        snapshot = runner.base_snapshot()
        del snapshot["protected"]["accepted_z_revision"]
        result = runner.simulate(runner.CONTRACT, snapshot, runner.base_inventory(), [])
        self.assertEqual("protected_state_incomplete", result["reason_code"])
        self.assertEqual("blocked_safe", result["phase"])
        self.assertFalse(result["lease_active"])

    def test_null_identifiers_and_material_fields_are_rejected(self):
        snapshot = runner.base_snapshot()
        events = [{"kind": "prepare_lease", "job_id": None, "lease_id": "lease-001"}]
        missing_job = runner.simulate(runner.CONTRACT, snapshot, runner.base_inventory(), events)
        self.assertEqual("job_id_invalid", missing_job["reason_code"])

        inventory = runner.base_inventory()
        inventory["slots"][0]["material"]["reference_id"] = None
        bad_material = runner.simulate(runner.CONTRACT, snapshot, inventory, [])
        self.assertEqual("material_identity_invalid", bad_material["reason_code"])

        bad_contract = deepcopy(runner.CONTRACT)
        del bad_contract["topology"]
        contract_result = runner.simulate(bad_contract, snapshot, runner.base_inventory(), [])
        self.assertEqual("contract_incomplete", contract_result["reason_code"])

        non_object_contract = runner.simulate(None, snapshot, runner.base_inventory(), [])
        self.assertEqual("contract_invalid", non_object_contract["reason_code"])

    def test_owned_resume_compares_the_full_pause_context(self):
        snapshot = runner.base_snapshot(engaged_routes=["T1A"], head_sensor_present=True)
        events = runner.full_start_events(snapshot) + runner.pause_and_plan_runout_events(snapshot)
        events.extend(
            runner.complete_plan_events(
                snapshot,
                lease_id="lease-001",
                plan_sequence=2,
                operations=["resolve_runout_tail", "load_selected_route", "purge_visible"],
                current_route="T1A",
                target_route="T2A",
                refill=True,
            )
        )
        context = runner.paused_context(snapshot)
        context["resume_position_xyz_mm"]["x"] += 1.0
        events.append(
            {
                "kind": "owned_resume",
                "observed": runner.observed(snapshot, ["T2A"]),
                "owner": "k1_control",
                "stock_resume_command": False,
                "homing": False,
                "z_reference": False,
                "mesh_mutation": False,
                "paused_context": context,
            }
        )
        result = runner.simulate(runner.CONTRACT, snapshot, runner.base_inventory(), events)
        self.assertEqual("owned_resume_invalid", result["reason_code"])
        self.assertIn("paused_context_changed", result["detail"])
        self.assertFalse(result["resume_eligible"])

    def test_unknown_and_duplicate_effects_are_never_replayed(self):
        unknown = runner.run_one("unknown_effect_never_retries")
        duplicate = runner.run_one("completed_intent_cannot_replay")
        self.assertEqual("effect_outcome_unknown", unknown["reason_code"])
        self.assertEqual(0, unknown["simulated_observations"])
        self.assertTrue(unknown["pending_plan_invalidated"])
        self.assertEqual("intent_replay_rejected", duplicate["reason_code"])
        self.assertEqual(1, duplicate["simulated_observations"])
        self.assertTrue(duplicate["pending_plan_invalidated"])
        self.assertFalse(unknown["replay_allowed"])
        self.assertFalse(duplicate["replay_allowed"])
        self.assertTrue(unknown["lease_release_required"])
        self.assertTrue(duplicate["lease_release_required"])

    def test_owned_resume_requires_full_state_and_forbids_hidden_recovery(self):
        result = runner.run_one("owned_resume_requires_full_verification")
        self.assertEqual("owned_resume_invalid", result["reason_code"])
        self.assertFalse(result["resume_eligible"])
        rules = self.contract["execution_rules"]
        self.assertFalse(rules["automatic_stock_resume"])
        self.assertTrue(rules["owned_resume_requires_full_verification"])
        self.assertTrue(rules["owned_resume_forbids_homing_z_reference_and_mesh_mutation"])

    def test_release_restores_exact_previous_policy_including_pre_disabled_zero(self):
        enabled = runner.run_one("lease_release_restores_saved_stock_policy")
        disabled = runner.run_one("lease_release_preserves_pre_disabled_stock_policy")
        for result, previous in ((enabled, 1), (disabled, 0)):
            self.assertEqual("closed_safe", result["phase"])
            self.assertEqual(previous, result["saved_stock_auto_refill"])
            self.assertFalse(result["lease_active"])
            self.assertFalse(result["lease_release_required"])

    def test_journal_is_ordered_and_contains_no_runtime_effect_claim(self):
        result = runner.run_one("runout_selects_unique_identical_cross_cfs")
        self.assertEqual(list(range(1, len(result["journal"]) + 1)), [item["index"] for item in result["journal"]])
        for field in (
            "printer_connection",
            "printer_mutation",
            "gcode_sent",
            "heat",
            "motion",
            "cfs_effect",
            "remote_write",
            "service_action",
            "real_connector_present",
            "command_encoder_present",
            "deployment_candidate",
            "production_authorized",
        ):
            self.assertFalse(result[field], field)

    def test_engine_parses_as_python_38_and_imports_no_transport(self):
        source = (PACKAGE / "engine.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="engine.py", feature_version=(3, 8))
        forbidden = {
            "asyncio",
            "ctypes",
            "http",
            "paramiko",
            "pathlib",
            "requests",
            "serial",
            "socket",
            "subprocess",
            "time",
            "urllib",
        }
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(forbidden.isdisjoint(imported))
        self.assertNotIn("BOX_", source)
        self.assertNotIn("START_PRINT", source)


if __name__ == "__main__":
    unittest.main()
