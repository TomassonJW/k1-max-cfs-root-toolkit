import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "clean-motion-v1"


class CleanMotionV1ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.form = json.loads((PACKAGE / "human-observation-form.json").read_text(encoding="utf-8"))

    def test_gate_is_not_deployable_and_contains_no_commands(self):
        self.assertEqual("protocol_prepared_no_candidate_commands", self.contract["status"])
        self.assertFalse(self.contract["deployment_candidate"])
        self.assertFalse(self.contract["printer_connection"])
        self.assertEqual([], self.contract["remote_commands"])
        self.assertEqual([], self.contract["gcode_commands"])
        self.assertEqual([], self.contract["service_actions"])

    def test_robust_activation_is_a_hard_prerequisite(self):
        prerequisites = self.contract["prerequisites"]
        self.assertEqual(
            "G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1",
            prerequisites["robust_mesh_activation_gate"],
        )
        self.assertEqual("ACTIVATION_OK", prerequisites["robust_mesh_activation_required_status"])
        self.assertEqual("k1_p001_t055_r001_n06x06", prerequisites["required_active_profile"])

    def test_physical_geometry_is_explicitly_missing(self):
        required = set(self.contract["physical_facts_required_before_candidate_commands"])
        self.assertIn("brush_left_right_front_back_bounds_observed_by_human", required)
        self.assertIn("safe_clearance_z_observed_by_human", required)
        self.assertIn("first_contact_z_observed_at_cold_slow_speed", required)
        self.assertTrue(all(value is None for value in self.form["observed_geometry_mm"].values()))
        self.assertEqual("NOT_RUN", self.form["status"])

    def test_every_effect_phase_requires_or_follows_human_checkpoints(self):
        phases = self.contract["phases"]
        self.assertEqual(
            [
                "A_READ_ONLY_BASELINE",
                "B_HUMAN_STATIC_OBSERVATION",
                "C_COLD_REFERENCE_AND_HIGH_CLEARANCE",
                "D_SLOW_APPROACH_CHECKPOINTS",
                "E_COLD_DRY_TRAJECTORY",
                "F_SAFE_RETURN_AND_FINAL_READ",
            ],
            [phase["id"] for phase in phases],
        )
        self.assertFalse(phases[0]["effect"])
        self.assertFalse(phases[1]["effect"])
        self.assertTrue(phases[2]["human_confirmation_before_effect"])
        self.assertTrue(phases[3]["human_confirmation_before_each_checkpoint"])
        self.assertTrue(phases[4]["human_confirmation_before_effect"])

    def test_forbidden_effects_and_terminal_stop_conditions_are_explicit(self):
        forbidden = self.contract["forbidden"]
        for name in (
            "heating",
            "extrusion",
            "cfs_action",
            "probing_brush_with_prtouch",
            "mesh_measurement",
            "z_offset_write",
            "configuration_write",
            "service_restart",
            "automatic_retry",
            "unobserved_motion",
        ):
            self.assertTrue(forbidden[name])
        self.assertIn("state_or_position_becomes_ambiguous", self.contract["stop_conditions"])


if __name__ == "__main__":
    unittest.main()
