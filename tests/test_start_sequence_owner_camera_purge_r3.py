import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "start-sequence-owner-camera-purge-r3"


def load_verifier():
    path = PACKAGE / "verify_candidate.py"
    spec = importlib.util.spec_from_file_location("start_sequence_owner_camera_purge_r3", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class StartSequenceOwnerCameraPurgeR3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier = load_verifier()
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.incident = json.loads((PACKAGE / "incident-evidence.json").read_text(encoding="utf-8"))

    def test_candidate_closes_both_camera_gates_offline(self):
        result = self.verifier.verify()
        self.assertEqual("START_SEQUENCE_OWNER_CAMERA_PURGE_R3_OFFLINE_OK", result["status"])
        self.assertTrue(result["camera_before_precise_z"])
        self.assertTrue(result["camera_before_model"])
        self.assertFalse(result["deployment_candidate"])
        self.assertFalse(result["physical_run_authorized"])

    def test_incident_is_closed_without_retry(self):
        self.assertEqual("cancelled", self.incident["controller_evidence"]["final_print_state"])
        self.assertEqual(0.0, self.incident["controller_evidence"]["extruder_target_c"])
        self.assertEqual(0.0, self.incident["controller_evidence"]["bed_target_c"])
        self.assertFalse(self.incident["controller_evidence"]["automatic_retry"])
        self.assertFalse(self.incident["human_observation"]["purge_in_bin"])

    def test_prime_line_is_outside_bed_but_inside_mechanical_travel(self):
        facts = self.contract["machine_facts"]
        self.assertLess(facts["outside_bed_prime_first_x_mm"], 0.0)
        self.assertLess(facts["outside_bed_prime_return_x_mm"], 0.0)
        self.assertGreaterEqual(facts["outside_bed_prime_first_x_mm"], facts["mechanical_x_min_mm"])
        self.assertAlmostEqual(
            0.4,
            facts["outside_bed_prime_return_x_mm"] - facts["outside_bed_prime_first_x_mm"],
        )

    def test_bin_and_brush_positions_match_the_frozen_contract(self):
        facts = self.contract["machine_facts"]
        self.assertEqual([185.5, 305.0, 30.0], facts["cfs_bin_purge_position_mm"])
        self.assertEqual(32.0, facts["qualified_blob_release_z_mm"])
        self.assertEqual([[203.0, 305.0], [206.0, 305.0], [203.0, 305.0]], facts["qualified_blob_release_first_lane"])
        self.assertEqual([[203.0, 304.0], [206.0, 304.0], [203.0, 304.0]], facts["qualified_blob_release_second_lane"])


if __name__ == "__main__":
    unittest.main()
