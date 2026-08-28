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
        self.assertEqual(1, result["passed_count"])
        self.assertEqual(3, result["pending_count"])

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

    def test_keep_correct_ko_is_retained_and_not_counted_as_passed(self):
        checkpoint = self.campaign["checkpoints"][1]
        evidence = json.loads((ROOT / checkpoint["evidence"]).read_text(encoding="utf-8"))
        self.assertEqual("KO_SAFE_STOP_COLD_BOOT_REQUIRED", checkpoint["evidence_status"])
        self.assertEqual("default", evidence["attempt"]["observed"]["active_profile_at_capture_end"])
        self.assertEqual("T0", evidence["safe_stop"]["last_fresh_read_only_state_before_human_power_off"]["cfs_active_command"])
        self.assertFalse(evidence["safe_stop"]["printer_restart_sent"])

    def test_empty_load_t1a_has_technical_and_human_evidence(self):
        first = self.campaign["checkpoints"][0]
        evidence = json.loads((ROOT / first["evidence"]).read_text(encoding="utf-8"))
        self.assertEqual("PASSED", first["evidence_status"])
        self.assertEqual("CFS_EMPTY_LOAD_T1A_VISIBLE_PURGE_OK", first["human_verdict"])
        self.assertEqual("PASSED", evidence["qualification_status"])
        self.assertEqual([[], ["T1A"]], evidence["technical_evidence"]["route_states"])
        self.assertEqual(220.0, evidence["technical_evidence"]["maximum_nozzle_target_c"])
        self.assertEqual(0.0, evidence["technical_evidence"]["final_nozzle_target_c"])
        self.assertTrue(evidence["human_evidence"]["visible_purge"])
        self.assertEqual("NON_PROBATIVE_OPERATOR_DID_NOT_TRIGGER_ACTION", first["first_capture_classification"])
        self.assertEqual("T1A", first["starting_residual_route_human_confirmed"])
        self.assertFalse(first["rerun_requires_human_clarification"])


if __name__ == "__main__":
    unittest.main()
