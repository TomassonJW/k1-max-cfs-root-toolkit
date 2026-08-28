from copy import deepcopy
import ast
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-owner-exclusion-guard-offline-v1"


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = load_module("cfs_owner_exclusion_guard_runner_test", PACKAGE / "run_scenarios.py")


class CfsOwnerExclusionGuardOfflineV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.matrix = json.loads((PACKAGE / "scenarios.json").read_text(encoding="utf-8"))

    def test_contract_is_offline_only_and_every_boundary_is_false(self):
        self.assertEqual("offline_only", self.contract["authority"])
        self.assertEqual(
            "offline_exclusion_guard_closed_green_effects_unqualified",
            self.contract["status"],
        )
        self.assertTrue(all(value is False for value in self.contract["boundaries"].values()))
        self.assertFalse(self.contract["truthful_limits"]["stock_command_effect_physically_qualified"])
        self.assertFalse(self.contract["truthful_limits"]["production_authorized"])

    def test_immutable_sources_match_the_pinned_hashes(self):
        sources = {
            "owner_core_contract_sha256": ROOT / "packages" / "k1-control-v1" / "cfs-owner-core-offline-v1" / "contract.json",
            "s12_preflight_contract_sha256": ROOT / "packages" / "k1-control-v1" / "cfs-s12-owner-preflight-v1" / "contract.json",
            "s12_evidence_map_sha256": ROOT / "packages" / "k1-control-v1" / "cfs-s12-owner-preflight-v1" / "evidence-map.json",
        }
        for key, path in sources.items():
            with self.subTest(key=key):
                self.assertEqual(self.contract["source_pins"][key], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_all_twenty_five_scenarios_are_deterministic_and_green(self):
        first = runner.run()
        second = runner.run()
        self.assertEqual(first, second)
        self.assertEqual("OK", first["verdict"])
        self.assertEqual(25, first["passed"])
        self.assertEqual(25, first["total"])
        self.assertFalse(first["printer_connection"])
        self.assertFalse(first["gcode_sent"])
        self.assertFalse(first["physical_action"])
        self.assertFalse(first["deployment_candidate"])
        self.assertTrue(all(not item["result"]["replay_allowed"] for item in first["details"]))

    def test_matrix_ids_match_the_contract_exactly(self):
        ids = [item["id"] for item in self.matrix["scenarios"]]
        self.assertEqual(self.contract["required_scenarios"], ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_only_reviewed_non_dispatchable_one_shot_commands_exist(self):
        enabled = runner.run_one("enabled_prepares_single_disable")
        restore = runner.run_one("release_restores_saved_one")
        self.assertEqual("BOX_ENABLE_AUTO_REFILL ENABLE=0", enabled["pending_intent"]["command"])
        self.assertEqual("BOX_ENABLE_AUTO_REFILL ENABLE=1", restore["pending_intent"]["command"])
        for result in (enabled, restore):
            self.assertFalse(result["pending_intent"]["dispatchable"])
            self.assertEqual(1, result["pending_intent"]["maximum_attempts"])

    def test_owner_is_granted_only_after_two_reads_prove_disabled(self):
        pending = runner.run_one("enabled_prepares_single_disable")
        proven = runner.run_one("disable_verified_grants_owner")
        ack_only = runner.run_one("disable_ack_without_effect_blocks")
        self.assertFalse(pending["owner_granted"])
        self.assertTrue(proven["owner_granted"])
        self.assertFalse(ack_only["owner_granted"])
        self.assertEqual("blocked_unknown", ack_only["phase"])

    def test_unknown_disable_never_retries_and_can_only_prepare_restore(self):
        rollback = runner.run_one("disable_unknown_then_zero_prepares_rollback")
        retry = runner.run_one("disable_retry_forbidden")
        self.assertEqual(1, rollback["attempts"]["disable"])
        self.assertEqual("restore_stock_auto_refill", rollback["pending_intent"]["operation"])
        self.assertFalse(rollback["owner_granted"])
        self.assertEqual(1, retry["attempts"]["disable"])
        self.assertFalse(retry["replay_allowed"])

    def test_restore_requires_observed_saved_value_not_acknowledgement(self):
        verified = runner.run_one("restore_verified_closes_safe")
        ack_only = runner.run_one("restore_ack_without_effect_blocks")
        uncertain_but_safe = runner.run_one("restore_unknown_then_saved_closes_safe_ko")
        self.assertEqual("closed_safe", verified["phase"])
        self.assertEqual("blocked_unknown", ack_only["phase"])
        self.assertEqual("closed_safe_ko", uncertain_but_safe["phase"])
        self.assertFalse(uncertain_but_safe["release_required"])

    def test_saved_zero_needs_neither_disable_nor_restore(self):
        result = runner.run_one("release_saved_zero_closes_without_intent")
        self.assertEqual({"disable": 0, "restore": 0}, result["attempts"])
        self.assertIsNone(result["pending_intent"])
        self.assertEqual("closed_safe", result["phase"])

    def test_recovery_observes_without_replaying_disable(self):
        guard = runner.Guard(self.contract)
        guard.prepare_acquire(runner.pair(1, 1))
        invalid = runner.pair(0, 3)
        invalid[0]["sample_seq"] = invalid[1]["sample_seq"]
        blocked = guard.observe_disable("unknown", invalid)
        self.assertEqual("blocked_unknown", blocked["phase"])
        recovered = guard.recover_disable(runner.pair(0, 5))
        self.assertEqual("rollback_pending", recovered["phase"])
        self.assertEqual(1, recovered["attempts"]["disable"])
        self.assertEqual(1, recovered["attempts"]["restore"])

    def test_recovery_observes_saved_value_without_replaying_restore(self):
        guard = runner.acquired(1)
        guard.prepare_release(runner.pair(0, 5))
        guard.observe_restore("unknown", runner.pair(0, 7))
        recovered = guard.recover_restore(runner.pair(1, 9))
        self.assertEqual("closed_safe_ko", recovered["phase"])
        self.assertEqual(1, recovered["attempts"]["restore"])
        self.assertFalse(recovered["release_required"])

    def test_mapping_epoch_print_policy_and_protected_state_are_compared(self):
        for field, value in (
            ("mapping_revision", "changed-map"),
            ("connection_epoch", "changed-epoch"),
            ("stock_cfs_print_enable", 0),
        ):
            with self.subTest(field=field):
                guard = runner.Guard(self.contract)
                guard.prepare_acquire(runner.pair(1, 1))
                reads = runner.pair(0, 3)
                for item in reads:
                    item[field] = value
                result = guard.observe_disable("accepted", reads)
                self.assertEqual("owner_identity_changed", result["reason_code"])
                self.assertFalse(result["owner_granted"])
        self.assertEqual("non_target_state_changed", runner.run_one("protected_drift_blocks")["reason_code"])

    def test_adapter_rejects_extra_fields_and_ambiguous_values(self):
        self.assertEqual("snapshot_unknown_field", runner.run_one("unknown_field_rejected")["reason_code"])
        self.assertEqual("stock_auto_refill_invalid", runner.run_one("boolean_policy_rejected")["reason_code"])
        reads = runner.pair(1)
        for item in reads:
            item["protected"]["nozzle_target_c"] = 180
        result = runner.Guard(self.contract).prepare_acquire(reads)
        self.assertEqual("heater_target_not_zero", result["reason_code"])

    def test_no_runtime_or_transport_import_surface_exists(self):
        forbidden = {"requests", "urllib", "socket", "subprocess", "paramiko", "fabric", "asyncssh"}
        for path in PACKAGE.glob("*.py"):
            tree = ast.parse(
                path.read_text(encoding="utf-8"),
                filename=str(path),
                feature_version=(3, 8),
            )
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module.split(".")[0])
            self.assertFalse(imports & forbidden, "%s imports %s" % (path.name, sorted(imports & forbidden)))

    def test_contract_mutations_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "contract_boundary_invalid"):
            changed = deepcopy(self.contract)
            changed["boundaries"]["printer_connection"] = True
            runner.Guard(changed)
        with self.assertRaisesRegex(ValueError, "contract_authority_invalid"):
            changed = deepcopy(self.contract)
            changed["authority"] = "live"
            runner.Guard(changed)
        with self.assertRaisesRegex(ValueError, "contract_disable_intent_invalid"):
            changed = deepcopy(self.contract)
            changed["reviewed_intents"]["disable_stock_auto_refill"]["command"] += " EXTRA=1"
            runner.Guard(changed)
        with self.assertRaisesRegex(ValueError, "contract_snapshot_invalid"):
            changed = deepcopy(self.contract)
            changed["snapshot"]["stable_reads"] = 1
            runner.Guard(changed)


if __name__ == "__main__":
    unittest.main()
