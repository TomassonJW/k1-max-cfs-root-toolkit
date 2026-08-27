from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "design" / "manual-nozzle-cleaning-policy-v1.json"
CLEAN_PACKAGE = ROOT / "packages" / "k1-control-v1" / "clean-and-reference-v1"


def load_remote():
    spec = importlib.util.spec_from_file_location("manual_clean_policy_remote", CLEAN_PACKAGE / "remote_clean_reference.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ManualNozzleCleaningPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))
        cls.remote = load_remote()

    def test_policy_is_canonical_manual_only(self):
        self.assertEqual("canonical", self.policy["status"])
        self.assertEqual("manual_cleaning_required", self.policy["decision"])
        self.assertFalse(self.policy["automatic_cleaning"]["allowed"])
        self.assertEqual("human_gate", self.policy["start_sequence_override"]["kind"])
        self.assertEqual([], self.policy["start_sequence_override"]["automatic_effects"])

    def test_historical_requirement_is_retained_with_truthful_resolution(self):
        self.assertEqual("AUTOMATIC_CLEAN_AND_FINAL_REFERENCE", self.policy["historical_requirement_id"])
        self.assertEqual(
            "AUTOMATIC_REJECTED_MANUAL_ONLY_POLICY_ACCEPTED",
            self.policy["historical_requirement_resolution"],
        )
        self.assertFalse(self.policy["evidence"]["final_reference_executed"])

    def test_remote_effect_actions_are_closed_before_transport(self):
        for action in ("clean-cycle", "reference"):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = self.remote.main([action, "GEETECH_LAST_USED", "220"])
            self.assertEqual(2, code)
            self.assertIn("ACTION_CLOSED_MANUAL_CLEANING_REQUIRED", output.getvalue())

    def test_powershell_runner_blocks_effect_actions(self):
        runner = (CLEAN_PACKAGE / "run_clean_reference.ps1").read_text(encoding="utf-8")
        self.assertIn("$Action -in @('CleanCycle', 'Reference')", runner)
        self.assertIn("Voie automatique fermée", runner)


if __name__ == "__main__":
    unittest.main()
