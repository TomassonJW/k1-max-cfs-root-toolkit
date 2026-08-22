import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "calibration-ui-prtouch-presets-v1"
MANIFEST = PACKAGE / "deployment-manifest.json"
CONTRACT = PACKAGE / "calibration-ui-prtouch-presets-contract.json"
DEPLOYER = ROOT / "scripts" / "deploy-k1-control-calibration-ui-prtouch-presets-v1.ps1"


class PrtouchPresetUiTests(unittest.TestCase):
    def test_every_displayed_matrix_is_executable_by_prtouch_adapter(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["displayed_matrices"], [3, 5, 6, 9, 11, 15])
        self.assertEqual(contract["product_levels"], [6, 9, 11, 15])
        self.assertEqual(contract["forbidden_displayed_matrices"], [4])
        self.assertTrue(contract["server_side_even_matrix_guard_retained"])

    def test_page_removes_four_but_keeps_all_product_levels(self):
        index = (PACKAGE / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('<option value="4">', index)
        for size in (3, 5, 6, 9, 11, 15):
            self.assertIn(f'<option value="{size}"', index)

    def test_client_never_falls_back_to_the_removed_even_matrix(self):
        app = (PACKAGE / "app.js").read_text(encoding="utf-8")
        self.assertIn('matrixField.value = "5"', app)
        self.assertNotIn('matrixField.value = "4"', app)
        self.assertIn('const requiresBicubic = matrix > 6;', app)

    def test_manifest_pins_both_static_files_and_exact_baseline(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["contract_id"],
            "G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-PRESETS-V1",
        )
        self.assertEqual(
            [item["source"] for item in manifest["files"]],
            ["index.html", "app.js"],
        )
        self.assertEqual(
            hashlib.sha256(DEPLOYER.read_bytes()).hexdigest(),
            manifest["deployer"]["sha256"],
        )
        self.assertEqual(
            hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
            manifest["contract"]["sha256"],
        )
        for item in manifest["files"]:
            self.assertEqual(
                hashlib.sha256((PACKAGE / item["source"]).read_bytes()).hexdigest(),
                item["sha256"],
            )

    def test_deployer_has_no_service_or_physical_action(self):
        source = DEPLOYER.read_text(encoding="utf-8")
        self.assertIn("Assert-MutationGate", source)
        self.assertIn("Invoke-ExactRollback", source)
        self.assertIn("service_restart = $false", source)
        self.assertIn("calibration_action = $false", source)
        self.assertIn("printer_motion = $false", source)
        self.assertIn("heater_command = $false", source)
        self.assertNotIn("S56k1_control_moonraker restart", source)
        self.assertNotIn("/printer/gcode/script", source)


if __name__ == "__main__":
    unittest.main()
