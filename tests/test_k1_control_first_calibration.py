import importlib.util
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "first-calibration-v1"
CONTRACT = PACKAGE / "first-calibration-contract.json"
COMPARE = PACKAGE / "compare_meshes.py"
RUNNER = ROOT / "scripts" / "run-k1-control-first-calibration-v1.ps1"
MANIFEST = PACKAGE / "execution-manifest.json"


def load_compare_module():
    spec = importlib.util.spec_from_file_location("first_calibration_compare", COMPARE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FirstCalibrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_candidate_is_offline_and_requires_exact_gate(self):
        self.assertEqual(self.contract["status"], "offline_review_candidate")
        self.assertFalse(self.contract["printer_mutation_authorized"])
        self.assertIn("$RequiredGate = 'G4-K1-CONTROL-FIRST-CALIBRATION-V1'", self.runner)
        self.assertIn("[string]$Action = 'Plan'", self.runner)
        self.assertIn("Assert-ExactGate", self.runner)

    def test_manifest_pins_every_executable_artifact(self):
        self.assertFalse(self.manifest["printer_mutation_authorized"])
        for artifact in self.manifest["artifacts"]:
            path = ROOT / artifact["path"]
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(actual, artifact["sha256"], artifact["path"])

    def test_first_calibration_context_is_explicit(self):
        self.assertEqual(self.contract["identity"]["plate_label"], "PEI_TEXTURED_A")
        self.assertEqual(self.contract["identity"]["plate_id"], 1)
        self.assertEqual(self.contract["thermal"]["bed_target_c"], 60)
        self.assertEqual(self.contract["thermal"]["nozzle_target_c"], 140)
        self.assertEqual(self.contract["thermal"]["soak_seconds"], 600)
        self.assertEqual(self.contract["thermal"]["cleaning"]["hot_max_c"], 180)

    def test_two_meshes_are_required_without_automatic_rerun(self):
        mesh = self.contract["mesh"]
        self.assertEqual(mesh["probe_count"], [6, 6])
        self.assertEqual(mesh["bounds_mm"], [5.0, 5.0, 295.0, 295.0])
        self.assertEqual(mesh["algorithm"], "lagrange")
        self.assertEqual(mesh["measurements"], 2)
        self.assertEqual(mesh["qualification"]["maximum_delta_mm"], 0.025)
        self.assertFalse(mesh["qualification"]["automatic_rerun"])
        self.assertEqual(
            self.runner.count("KCTRL_MESH_CALIBRATE X_COUNT=6 Y_COUNT=6 ALGORITHM=lagrange"),
            3,
        )
        self.assertNotIn("Mesh3", self.runner)

    def test_z_path_has_no_hidden_default_and_requires_confirmation(self):
        z = self.contract["z"]
        self.assertEqual(z["seed_offset_mm"], 0.0)
        self.assertIn("explicit neutral seed", z["seed_reason"])
        self.assertEqual(z["height_ladder_mm"], [5.0, 2.0, 1.0, 0.5, 0.3, 0.2, 0.15, 0.1])
        self.assertTrue(z["gap_confirmation_required"])
        self.assertIn("ConfirmGap exige -ConfirmGapObserved", self.runner)
        self.assertIn("Accept exige -ConfirmAccept", self.runner)

    def test_forbidden_production_changes_are_absent(self):
        forbidden = self.contract["forbidden"]
        for value in (
            "print_start",
            "extrusion",
            "cfs_command",
            "orca_profile_change",
            "start_print_change",
            "legacy_plus_0_27_removal",
            "automatic_third_mesh",
        ):
            self.assertIn(value, forbidden)
        for token in ("START_PRINT", "BOX_", "G92 E", "G1 E", "EXTRUDE"):
            self.assertNotIn(token, self.runner)

    def test_cancel_and_rollback_have_distinct_effects(self):
        self.assertTrue(self.contract["cancel"]["qualified_mesh_preserved"])
        self.assertFalse(self.contract["rollback"]["qualified_mesh_preserved"])
        self.assertTrue(self.contract["rollback"]["installed_runtime_preserved"])
        self.assertTrue(self.contract["rollback"]["installed_calibration_path_preserved"])
        self.assertIn("CANCEL_FIRST_CALIBRATION_V1_OK", self.runner)
        self.assertIn("ROLLBACK_FIRST_CALIBRATION_V1_OK", self.runner)

    def test_backup_checksums_the_exact_config_and_empty_state_marker(self):
        self.assertIn("$EmptyFileHash = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'", self.runner)
        self.assertIn("$EmptyFileHash  state-baseline-absent", self.runner)
        self.assertIn("sha256sum -c checksums.sha256", self.runner)

    def test_preflight_checks_local_and_remote_execution_prerequisites(self):
        self.assertIn("Get-Command python.exe", self.runner)
        self.assertIn("command -v '$tool'", self.runner)
        self.assertIn("$PrinterConfig.first-calibration-rollback", self.runner)
        self.assertIn("$PrinterConfig.first-calibration-final", self.runner)

    def test_save_config_and_rollback_wait_for_the_actual_restart(self):
        self.assertIn("function Wait-MeshCommitRestart", self.runner)
        self.assertIn("function Wait-RollbackRestart", self.runner)
        self.assertIn("-not $snapshot.toolhead.homed_axes", self.runner)
        self.assertIn("$profiles -contains $MeshProfile", self.runner)
        self.assertIn("$profiles -notcontains $MeshProfile", self.runner)
        self.assertNotIn("$after = Wait-KlipperSnapshot -Attempts 90", self.runner)

    def test_ui_autonomy_is_not_claimed_by_this_gate(self):
        ui = self.contract["daily_ui_future_contract"]
        self.assertFalse(ui["this_gate_proves_calibration_autonomy"])
        self.assertIn("save_cancel_and_restore_actions", ui["must_later_expose"])


class FirstCalibrationMeshComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_compare_module()

    @staticmethod
    def matrix(delta=0.0):
        return [[row * 0.01 + column * 0.001 + delta for column in range(6)] for row in range(6)]

    def test_close_repeated_mesh_is_accepted(self):
        result = self.module.compare(self.matrix(), self.matrix(0.024))
        self.assertTrue(result["accepted"])
        self.assertEqual(result["compared_points"], 36)
        self.assertAlmostEqual(result["maximum_delta_mm"], 0.024)

    def test_drifting_mesh_is_rejected(self):
        result = self.module.compare(self.matrix(), self.matrix(0.026))
        self.assertFalse(result["accepted"])
        self.assertGreater(result["maximum_delta_mm"], result["tolerance_mm"])

    def test_wrong_shape_and_non_finite_values_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "6 lignes"):
            self.module.compare([[0.0]], [[0.0]])
        invalid = self.matrix()
        invalid[2][3] = float("nan")
        with self.assertRaisesRegex(ValueError, "non finie"):
            self.module.compare(invalid, self.matrix())


if __name__ == "__main__":
    unittest.main()
