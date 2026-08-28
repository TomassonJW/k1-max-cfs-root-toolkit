from copy import deepcopy
import ast
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-owner-exclusion-guard-live-effect-v1"
OBSERVER = ROOT / "packages" / "k1-control-v1" / "cfs-owner-observability-live-read-only-v2"
EFFECT_SUPPORT = PACKAGE / "remote_observer_effect_support_v1.py"
OFFLINE = ROOT / "packages" / "k1-control-v1" / "cfs-owner-observability-adapter-offline-v2"


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = load_module("cfs_owner_exclusion_guard_live_effect_validator_test", PACKAGE / "validate_private_capture.py")
runner = load_module("cfs_owner_exclusion_guard_live_effect_offline_runner_test", OFFLINE / "run_scenarios.py")


def pair(auto_refill, start_seq):
    value = deepcopy(runner.pair())
    for index, observation in enumerate(value):
        observation["sample_seq"] = start_seq + index
        observation["stock_auto_refill"] = auto_refill
        observation["observer_eventtime"] = 100.0 + start_seq + index
    return value


def capture():
    hashes = {
        "/usr/data/printer_data/config/printer.cfg": "f88d6b52477592805384fca2b4d7abd00298deecd82227af2fa580085fe26fa2",
        "/usr/data/printer_data/config/box.cfg": "e7a6b26df58a9fa8e49d3af6845f5a0937a790c8ef494b96ec72fd7392abc7a7",
        "/usr/data/printer_data/config/gcode_macro.cfg": "864fedde88fbb345c220ae5658f7b04779b3981bd78d68eda6fa63c59c79a04f",
    }
    return {
        "schema": 1,
        "mission": "G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-LIVE-EFFECT-V1",
        "status": "CLOSED_OK_EXCLUSION_AND_EXACT_RESTORE_QUALIFIED",
        "observer_connection_id": 424242,
        "reported_cfs_transition_count": 0,
        "reported_cfs_transitions": [],
        "saved_stock_auto_refill": 1,
        "commands_attempted": [
            "BOX_ENABLE_AUTO_REFILL ENABLE=0",
            "BOX_ENABLE_AUTO_REFILL ENABLE=1",
        ],
        "attempts": {"disable": 1, "restore": 1},
        "acknowledgements": {
            "disable": {"response_received": True, "error": False},
            "restore": {"response_received": True, "error": False},
        },
        "proof": {
            "before_disable": pair(1, 1),
            "after_disable": pair(0, 3),
            "before_restore": pair(0, 5),
            "after_restore": pair(1, 7),
        },
        "configuration_hashes": {
            "before": hashes,
            "pre_disable": dict(hashes),
            "post_disable": dict(hashes),
            "final": dict(hashes),
        },
        "effects": {
            "gcode_commands_attempted": 2,
            "stock_auto_refill_policy_changed": True,
            "stock_auto_refill_restored": True,
            "filament_action": False,
            "heater_action": False,
            "motion_action": False,
            "remote_files_written": False,
            "service_action": False,
        },
    }


class CfsOwnerExclusionGuardLiveEffectV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.evidence = json.loads((PACKAGE / "evidence-map.json").read_text(encoding="utf-8"))

    def test_contract_allows_only_one_disable_and_one_exact_restore(self):
        self.assertEqual("single_bounded_live_effect", self.contract["authority"])
        self.assertEqual(1, self.contract["reviewed_commands"]["maximum_attempts_each"])
        self.assertEqual("BOX_ENABLE_AUTO_REFILL ENABLE=0", self.contract["reviewed_commands"]["disable"])
        self.assertEqual("BOX_ENABLE_AUTO_REFILL ENABLE=1", self.contract["reviewed_commands"]["restore"])
        for field in ("filament_action", "heater_action", "motion_action", "remote_file_write", "service_restart"):
            self.assertFalse(self.contract["boundaries"][field])

    def test_synthetic_success_is_replayed_through_the_exact_offline_guard(self):
        result = validator.verify_payload(capture())
        self.assertEqual("OK", result["status"])
        self.assertEqual(0, result["disabled_value_proved"])
        self.assertEqual(1, result["restored_value_proved"])
        self.assertEqual({"disable": 1, "restore": 1}, result["attempts"])
        self.assertTrue(result["owner_granted_then_released"])

    def test_missing_restore_duplicate_command_or_non_target_effect_is_rejected(self):
        missing = capture()
        missing["commands_attempted"].pop()
        with self.assertRaisesRegex(ValueError, "command_sequence_invalid"):
            validator.verify_payload(missing)
        duplicate = capture()
        duplicate["attempts"]["disable"] = 2
        with self.assertRaisesRegex(ValueError, "attempt_count_invalid"):
            validator.verify_payload(duplicate)
        effect = capture()
        effect["effects"]["heater_action"] = True
        with self.assertRaisesRegex(ValueError, "effect_boundary_invalid"):
            validator.verify_payload(effect)

    def test_connection_transition_and_z_drift_are_rejected(self):
        transitioned = capture()
        transitioned["proof"]["after_disable"][1]["cfs_transition_seq"] = 1
        with self.assertRaisesRegex(ValueError, "projection_rejected:cfs_connection_transition_observed"):
            validator.verify_payload(transitioned)
        z_drift = capture()
        z_drift["proof"]["after_restore"][1]["protected"]["runtime_accepted_z_offset_mm"] = -0.05
        with self.assertRaisesRegex(ValueError, "projection_rejected:guard_adapter_rejected"):
            validator.verify_payload(z_drift)

    def test_remote_program_has_only_the_two_reviewed_effect_commands(self):
        source = (PACKAGE / "remote_effect_gate.py").read_text(encoding="utf-8")
        self.assertIn('DISABLE_COMMAND = "BOX_ENABLE_AUTO_REFILL ENABLE=0"', source)
        self.assertIn('RESTORE_COMMAND = "BOX_ENABLE_AUTO_REFILL ENABLE=1"', source)
        for forbidden in ("BOX_QUIT_MATERIAL", "BOX_EXTRUDE", "TURN_OFF_HEATERS", "SAVE_CONFIG", "RESTART"):
            self.assertNotIn(forbidden, source)
        self.assertIn('client.connect("/tmp/klippy_uds")', source)
        self.assertIn('command in {DISABLE_COMMAND, RESTORE_COMMAND}', source)

    def test_python_sources_parse_as_python_38(self):
        for name in ("remote_effect_gate.py", "validate_private_capture.py"):
            ast.parse((PACKAGE / name).read_text(encoding="utf-8"), feature_version=(3, 8))
        combined = (
            EFFECT_SUPPORT.read_text(encoding="utf-8")
            + "\n"
            + (PACKAGE / "remote_effect_gate.py").read_text(encoding="utf-8")
        )
        ast.parse(combined, feature_version=(3, 8))

    def test_private_capture_and_exact_executed_artifacts_are_pinned(self):
        self.assertEqual(self.evidence["safe_result"], validator.verify_evidence(ROOT))
        for name, expected in self.evidence["executed_artifacts"].items():
            self.assertEqual(expected, hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest(), name)
        self.assertFalse(self.contract["rerun_authorized"])
        self.assertEqual("CLOSED_OK_EXCLUSION_AND_EXACT_RESTORE_QUALIFIED", self.contract["verdict"])


if __name__ == "__main__":
    unittest.main()
