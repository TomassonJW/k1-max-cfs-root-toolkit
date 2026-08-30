import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "packages"
    / "k1-control-v1"
    / "camera-reference-library-and-r3-cold-validation-v1"
)


def load_validator():
    path = PACKAGE / "validate_r3_cold.py"
    spec = importlib.util.spec_from_file_location("camera_reference_r3_cold", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CameraReferenceLibraryAndR3ColdValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_validator()
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.library = json.loads((PACKAGE / "reference-library.json").read_text(encoding="utf-8"))
        cls.next_gate = json.loads((PACKAGE / "next-hot-preflight.json").read_text(encoding="utf-8"))
        cls.pilot = (PACKAGE / "camera_pilot.ps1").read_text(encoding="utf-8")
        cls.remote = (PACKAGE / "validate_with_k1_jinja.ps1").read_text(encoding="utf-8")

    def test_static_cold_validator_closes_both_camera_holds(self):
        result = self.validator.verify()
        self.assertEqual("CAMERA_REFERENCE_LIBRARY_AND_R3_COLD_STATIC_OK", result["status"])
        self.assertTrue(result["camera_before_precise_z"])
        self.assertTrue(result["camera_before_model"])
        self.assertTrue(result["base_pause_resume_only"])
        self.assertTrue(result["watchdog_shutdown_without_confirmation"])

    def test_reference_library_does_not_invent_future_states(self):
        acquired = [item["id"] for item in self.library["references"] if item["acquired"]]
        self.assertEqual(["SAFE_IDLE_PARK"], acquired)
        self.assertFalse(self.library["automatic_semantic_decision"])
        safe_idle = self.library["references"][0]
        self.assertEqual(
            "db0d21de4288c522f0c132f4ae8df1e5fc5c9d46062da584e255577e1382029d",
            safe_idle["sha256"],
        )

    def test_regions_are_inside_the_canonical_frame(self):
        width = self.library["frame"]["width_px"]
        height = self.library["frame"]["height_px"]
        self.assertEqual({"nozzle", "bin", "bed"}, set(self.library["regions"]))
        for region in self.library["regions"].values():
            self.assertGreaterEqual(region["left"], 0)
            self.assertGreaterEqual(region["top"], 0)
            self.assertLessEqual(region["left"] + region["width"], width)
            self.assertLessEqual(region["top"] + region["height"], height)

    def test_camera_pilot_is_get_only_and_cannot_confirm_a_gate(self):
        self.assertIn("Invoke-WebRequest -UseBasicParsing -Method Get", self.pilot)
        self.assertIn("ssh.exe -G", self.pilot)
        self.assertIn("semantic_state_confirmed = $false", self.pilot)
        self.assertIn("automatic_gate_command = $null", self.pilot)
        for forbidden in ("/printer/gcode/script", "BED_MESH_PROFILE", "TURN_OFF_HEATERS", "BOX_"):
            self.assertNotIn(forbidden, self.pilot)

    def test_remote_jinja_validation_is_stdin_only_and_effect_free(self):
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", self.remote)
        self.assertIn("remote_files_written = $false", self.remote)
        self.assertIn("gcode_sent = $false", self.remote)
        self.assertNotIn("scp", self.remote.lower())
        self.assertNotIn("restart", self.remote.lower())

    def test_contract_keeps_deployment_and_physical_run_closed(self):
        self.assertEqual(
            "CLOSED_OK_CAMERA_READ_ONLY_AND_R3_COLD_VALIDATED",
            self.contract["status"],
        )
        self.assertTrue((ROOT / self.contract["evidence"]).is_file())
        self.assertTrue((ROOT / self.contract["next_gate_plan"]).is_file())
        self.assertEqual([], self.contract["effect_connectors"])
        self.assertFalse(any(self.contract["effects"].values()))
        self.assertFalse(self.contract["deployment_candidate"])
        self.assertFalse(self.contract["physical_run_authorized"])

    def test_next_hot_preflight_closed_without_effect(self):
        self.assertEqual(
            "CLOSED_KO_R3_SUPERSEDED_AND_ACTIVE_MESH_DRIFT",
            self.next_gate["status"],
        )
        self.assertIn("nozzle_cleaned", self.next_gate["required_manual_facts_before_start"])
        self.assertIn("T1A_reengaged_with_official_function", self.next_gate["required_manual_facts_before_start"])
        self.assertTrue(self.next_gate["manual_facts_user_confirmed"]["nozzle_recleaned_after_insertion"])
        self.assertEqual("default", self.next_gate["observed_read_only_result"]["active_mesh"])
        self.assertEqual("6x6", self.next_gate["observed_read_only_result"]["active_mesh_shape"])
        self.assertIn(
            "R3_purges_after_insertion_and_before_accurate_z_reference",
            self.next_gate["closure_reasons"],
        )
        self.assertIn("R3_install", self.next_gate["forbidden_in_this_preflight"])
        self.assertFalse(any(self.next_gate["effects"].values()))


if __name__ == "__main__":
    unittest.main()
