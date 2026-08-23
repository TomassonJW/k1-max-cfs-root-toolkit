import importlib.util
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "calibration-ui-matrix-v1"
CORE = PACKAGE / "k1_control_calibration_core.py"
CONTRACT = PACKAGE / "calibration-ui-matrix-contract.json"
INDEX = PACKAGE / "www" / "index.html"
APP = PACKAGE / "www" / "app.js"
MANIFEST = PACKAGE / "deployment-manifest.json"
DEPLOYER = ROOT / "scripts" / "deploy-k1-control-calibration-ui-matrix-v1.ps1"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_core():
    spec = importlib.util.spec_from_file_location("k1_control_calibration_core_matrix", CORE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CalibrationUiMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = load_core()

    @staticmethod
    def config(size, algorithm):
        return {
            "plate_id": 1,
            "plate_label": "PEI_TEXTURED_A",
            "bed_temp_c": 55,
            "nozzle_temp_c": 140,
            "soak_seconds": 200,
            "probe_revision": 1,
            "nozzle_id": 1,
            "config_id": 1,
            "x_count": size,
            "y_count": size,
            "algorithm": algorithm,
            "seed_offset_mm": -0.04,
        }

    @staticmethod
    def matrix(size, delta=0.0):
        return [
            [row * 0.001 + column * 0.0001 + delta for column in range(size)]
            for row in range(size)
        ]

    def test_only_proven_six_by_six_lagrange_validates(self):
        value = self.core.validate_config(self.config(6, "lagrange"))
        self.assertEqual(value["x_count"], 6)
        self.assertEqual(value["algorithm"], "lagrange")

    def test_all_unproven_matrix_sizes_are_rejected(self):
        for size in (3, 4, 5, 9, 11, 15):
            with self.subTest(size=size):
                with self.assertRaisesRegex(self.core.CalibrationError, "36 points physiques"):
                    self.core.validate_config(self.config(size, "lagrange"))

    def test_bicubic_is_not_exposed_for_the_fixed_grid(self):
        with self.assertRaisesRegex(self.core.CalibrationError, "Seul Lagrange"):
            self.core.validate_config(self.config(6, "bicubic"))

    def test_one_complete_mesh_is_accepted_without_dimension_loss(self):
        size = 6
        result = self.core.aggregate_meshes([self.matrix(size)], size, size)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["method"], "single_firmware_bounded_mesh")
        self.assertEqual(len(result["candidate_matrix"]), size)
        self.assertTrue(all(len(row) == size for row in result["candidate_matrix"]))

    def test_static_page_exposes_only_the_hardware_safe_grid(self):
        html = INDEX.read_text(encoding="utf-8")
        self.assertIn('<option value="6"', html)
        for size in (3, 4, 5, 9, 11, 15):
            self.assertNotIn(f'<option value="{size}"', html)
        self.assertIn("36 points physiques", html)

    def test_client_forces_the_proven_pair(self):
        javascript = APP.read_text(encoding="utf-8")
        self.assertIn("function syncMatrixAlgorithm()", javascript)
        self.assertIn('byId("matrix-size").value = "6"', javascript)
        self.assertIn('byId("algorithm").value = "lagrange"', javascript)
        self.assertIn('addEventListener("change", syncMatrixAlgorithm)', javascript)

    def test_contract_records_the_observed_limit(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["selectable_square_matrices"], [6])
        self.assertEqual(contract["rejected_square_matrices"], [9, 11, 15])
        self.assertEqual(contract["observed_hardware_limit"]["physical_points"], 36)

    def test_deployment_manifest_pins_the_delta_and_rollback_base(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["contract_id"], "G4-K1-CONTROL-CALIBRATION-UI-MATRIX-V1")
        self.assertEqual(manifest["deployer"]["sha256"], sha256(DEPLOYER))
        self.assertEqual(
            {item["source"] for item in manifest["files"]},
            {"k1_control_calibration_core.py", "www/index.html", "www/app.js"},
        )
        for item in manifest["files"]:
            self.assertEqual(item["sha256"], sha256(PACKAGE / item["source"]))
        self.assertEqual(len(manifest["baseline"]["files"]), 3)
        unchanged = {
            item["destination"]: item["sha256"]
            for item in manifest["unchanged"]["files"]
        }
        self.assertEqual(
            unchanged[
                "/usr/data/k1-control-v1/current/moonraker/moonraker/moonraker/components/k1_control_probe_count.py"
            ],
            "8c8c4aaf20856be1880cea56badd2fe81bd488966eab0d55e7672f73eb1db7b0",
        )
        self.assertEqual(
            unchanged["/usr/data/printer_data/config/printer.cfg"],
            "36cfb7e71180268841ab5cedd31628c8d9953ba437c47662ced16df18bb1bacd",
        )
        self.assertFalse(manifest["calibration_action"])

    def test_deployer_is_a_separate_exact_gate_without_physical_actions(self):
        deployer = DEPLOYER.read_text(encoding="utf-8-sig")
        self.assertIn("G4-K1-CONTROL-CALIBRATION-UI-MATRIX-V1", deployer)
        self.assertIn("scp.exe", deployer)
        self.assertIn("S56k1_control_moonraker", deployer)
        self.assertNotIn("KCTRL_MESH_CALIBRATE", deployer)
        self.assertNotIn("KCTRL_CAL_PATH_BEGIN", deployer)
        self.assertIn("for size in (3, 4, 5, 9, 11, 15):", deployer)
        self.assertIn("6x6 bicubic must fail closed", deployer)
        self.assertIn("Assert-ServerInfo", deployer)
        self.assertIn("failed_components", deployer)
        self.assertIn("warnings", deployer)
        self.assertIn("'cancelled', 'rolled_back'", deployer)


if __name__ == "__main__":
    unittest.main()
