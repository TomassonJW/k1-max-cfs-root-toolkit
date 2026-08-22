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

    def test_supported_presets_validate_with_their_safe_algorithm(self):
        for size, algorithm in ((6, "lagrange"), (9, "bicubic"), (11, "bicubic"), (15, "bicubic")):
            with self.subTest(size=size):
                value = self.core.validate_config(self.config(size, algorithm))
                self.assertEqual(value["x_count"], size)
                self.assertEqual(value["algorithm"], algorithm)

    def test_lagrange_is_rejected_above_six(self):
        for size in (9, 11, 15):
            with self.subTest(size=size):
                with self.assertRaisesRegex(self.core.CalibrationError, "Lagrange est limité à 6"):
                    self.core.validate_config(self.config(size, "lagrange"))

    def test_matrix_above_fifteen_is_rejected(self):
        with self.assertRaisesRegex(self.core.CalibrationError, "3x3-15x15"):
            self.core.validate_config(self.config(16, "bicubic"))

    def test_six_large_meshes_are_aggregated_without_dimension_loss(self):
        size = 15
        matrices = [self.matrix(size, delta) for delta in (-0.004, 0, 0.004, 0.010, 0.014, 0.018)]
        result = self.core.aggregate_meshes(matrices, size, size)
        self.assertTrue(result["accepted"])
        self.assertEqual(len(result["candidate_matrix"]), size)
        self.assertTrue(all(len(row) == size for row in result["candidate_matrix"]))

    def test_static_page_exposes_all_product_presets(self):
        html = INDEX.read_text(encoding="utf-8")
        for size, label in ((6, "Rapide"), (9, "Standard"), (11, "Précis"), (15, "Expert")):
            with self.subTest(size=size):
                self.assertIn(f'<option value="{size}"', html)
                self.assertIn(label, html)
        self.assertIn("requis au-delà de 6", html)

    def test_client_forces_bicubic_above_six(self):
        javascript = APP.read_text(encoding="utf-8")
        self.assertIn("function syncMatrixAlgorithm()", javascript)
        self.assertIn("const requiresBicubic = matrix > 6", javascript)
        self.assertIn("lagrangeOption.disabled = requiresBicubic", javascript)
        self.assertIn('algorithmField.value = "bicubic"', javascript)
        self.assertIn('addEventListener("change", syncMatrixAlgorithm)', javascript)

    def test_contract_matches_the_product_levels(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["selectable_square_matrices"], [3, 4, 5, 6, 9, 11, 15])
        self.assertEqual(
            [(item["matrix"][0], item["algorithm"]) for item in contract["presets"].values()],
            [(6, "lagrange"), (9, "bicubic"), (11, "bicubic"), (15, "bicubic")],
        )

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
        self.assertFalse(manifest["calibration_action"])

    def test_deployer_is_a_separate_exact_gate_without_physical_actions(self):
        deployer = DEPLOYER.read_text(encoding="utf-8-sig")
        self.assertIn("G4-K1-CONTROL-CALIBRATION-UI-MATRIX-V1", deployer)
        self.assertIn("scp.exe", deployer)
        self.assertIn("S56k1_control_moonraker", deployer)
        self.assertNotIn("KCTRL_MESH_CALIBRATE", deployer)
        self.assertNotIn("KCTRL_CAL_PATH_BEGIN", deployer)


if __name__ == "__main__":
    unittest.main()
