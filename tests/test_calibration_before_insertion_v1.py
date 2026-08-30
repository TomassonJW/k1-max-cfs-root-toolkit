import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "calibration-before-insertion-v1"


def load_verifier():
    path = PACKAGE / "verify_contract.py"
    spec = importlib.util.spec_from_file_location("calibration_before_insertion_v1", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CalibrationBeforeInsertionV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier = load_verifier()
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.evidence = json.loads((PACKAGE / "preflight-evidence.json").read_text(encoding="utf-8"))

    def test_rule_and_preflight_close_safely(self):
        result = self.verifier.verify()
        self.assertEqual("CALIBRATION_BEFORE_INSERTION_V1_OFFLINE_OK", result["status"])
        self.assertTrue(result["r3_tombstoned"])
        self.assertTrue(result["probing_before_insertion"])
        self.assertTrue(result["reuse_path_has_no_probe"])
        self.assertTrue(result["preflight_closed_on_mesh_drift"])
        self.assertFalse(result["effects"])

    def test_fresh_geometry_finishes_contact_before_insertion(self):
        order = self.contract["final_paths"]["fresh_geometry"]["required_order"]
        self.assertLess(order.index("complete_all_contact_probing"), order.index("resolve_and_insert_filament"))
        self.assertLess(order.index("resolve_and_insert_filament"), order.index("purge_and_prove_flow"))

    def test_valid_geometry_reuse_never_probes(self):
        reuse = self.contract["final_paths"]["reuse_valid_geometry"]
        self.assertIn("no_contact_probe_in_job_start", reuse["required"])
        self.assertTrue(reuse["engaged_correct_filament_may_be_kept"])

    def test_live_preflight_is_effect_free_and_records_drift(self):
        self.assertEqual("default", self.evidence["machine_snapshots"]["active_mesh"])
        self.assertEqual("6x6", self.evidence["machine_snapshots"]["active_probed_matrix"])
        self.assertTrue(self.evidence["machine_snapshots"]["T1A_engaged"])
        self.assertEqual(0.0, self.evidence["machine_snapshots"]["heater_targets_c"]["extruder"])
        self.assertEqual(0.0, self.evidence["machine_snapshots"]["heater_targets_c"]["bed"])
        for key in (
            "gcode_sent",
            "heater_action",
            "motion_action",
            "extrusion_action",
            "cfs_action",
            "remote_file_write",
            "service_action",
        ):
            self.assertFalse(self.evidence["effects"][key])

    def test_next_gate_stays_narrow(self):
        next_gate = self.contract["next_gate"]
        self.assertTrue(next_gate["separate_machine_mutation_authority_required"])
        self.assertIn("probe", next_gate["must_not"])
        self.assertIn("change_cfs_route", next_gate["must_not"])
        self.assertFalse(self.contract["executable_candidate"])
        self.assertFalse(self.contract["production_authorized"])


if __name__ == "__main__":
    unittest.main()
