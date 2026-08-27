from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-temp-owner-v1"


def load_verifier():
    spec = importlib.util.spec_from_file_location("cfs_physical_campaign_verifier", PACKAGE / "verify_physical_campaign.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CfsPhysicalCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.campaign = json.loads((PACKAGE / "physical-campaign.json").read_text(encoding="utf-8"))
        cls.verifier = load_verifier()

    def test_campaign_is_exactly_four_non_overlapping_checkpoints(self):
        result = self.verifier.verify()
        self.assertEqual("CFS_PHYSICAL_CAMPAIGN_READY_INCOMPLETE", result["status"])
        self.assertEqual(0, result["passed_count"])
        self.assertEqual(4, result["pending_count"])

    def test_campaign_covers_both_cfs_units(self):
        rendered = json.dumps(self.campaign, sort_keys=True)
        self.assertIn("T1A", rendered)
        self.assertIn("T2C", rendered)
        self.assertEqual(["T1", "T2"], self.campaign["completion"]["both_cfs_units_must_be_observed"])

    def test_every_effectful_checkpoint_requires_a_unique_human_verdict(self):
        verdicts = [item["accepted_human_verdict"] for item in self.campaign["checkpoints"]]
        self.assertEqual(len(verdicts), len(set(verdicts)))
        self.assertTrue(self.campaign["completion"]["visible_purge_requires_human_evidence"])

    def test_ambiguous_case_is_effect_free(self):
        ambiguous = self.campaign["checkpoints"][-1]
        self.assertEqual("AMBIGUOUS_IDENTITY_BLOCK", ambiguous["id"])
        self.assertEqual([], ambiguous["expected_effects"])
        self.assertTrue(ambiguous["requires_read_only_decision_adapter"])

    def test_current_attempt_remains_unqualified_but_rerun_is_ready(self):
        first = self.campaign["checkpoints"][0]
        self.assertEqual("READY_FOR_RERUN_HUMAN_CONFIRMED_PREVIOUS_T1A_RESIDUAL", first["evidence_status"])
        self.assertEqual("NON_PROBATIVE_OPERATOR_DID_NOT_TRIGGER_ACTION", first["first_capture_classification"])
        self.assertEqual("T1A", first["starting_residual_route_human_confirmed"])
        self.assertFalse(first["rerun_requires_human_clarification"])
        self.assertNotEqual("PASSED", first["evidence_status"])


if __name__ == "__main__":
    unittest.main()
