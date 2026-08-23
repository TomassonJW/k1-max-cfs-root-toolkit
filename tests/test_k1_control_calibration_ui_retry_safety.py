import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "calibration-ui-retry-safety-v1"
APP = PACKAGE / "app.js"
CONTRACT = PACKAGE / "calibration-ui-retry-safety-contract.json"
MANIFEST = PACKAGE / "deployment-manifest.json"
DEPLOYER = ROOT / "scripts" / "deploy-k1-control-calibration-ui-retry-safety-v1.ps1"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CalibrationUiRetrySafetyTests(unittest.TestCase):
    def test_incomplete_retry_resets_dangerous_confirmations_once(self):
        javascript = APP.read_text(encoding="utf-8")
        self.assertIn("function isIncompleteRetry(value)", javascript)
        self.assertIn(
            '["cancelled", "failed", "mesh_rejected", "rolled_back"]',
            javascript,
        )
        retry_guard = javascript.split("function isIncompleteRetry(value)", 1)[1].split(
            "function hydrateForm()", 1
        )[0]
        self.assertNotIn("mesh_index", retry_guard)
        self.assertNotIn("mesh_target_count", retry_guard)
        self.assertIn("`${state.campaign_id}:${phase}`", javascript)
        self.assertIn('byId("replace-existing").checked = isIncompleteRetry(state)', javascript)
        self.assertIn('byId("plate-clear").checked = false', javascript)

    def test_contract_keeps_explicit_replacement_available(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(
            contract["contract_id"],
            "G4-K1-CONTROL-CALIBRATION-UI-RETRY-SAFETY-V1",
        )
        self.assertIn("rolled_back", contract["reset_when"]["phases"])
        self.assertIn("mesh_index equals", contract["reset_when"]["single_mesh_rule"])
        self.assertFalse(contract["one_time_reset"]["replace_existing"])
        self.assertFalse(contract["one_time_reset"]["plate_clear"])
        self.assertTrue(contract["operator_can_reenable_replace_explicitly"])
        self.assertFalse(contract["service_restart"])
        self.assertFalse(contract["calibration_action"])

    def test_manifest_pins_one_static_file_and_exact_rollback(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["contract_id"],
            "G4-K1-CONTROL-CALIBRATION-UI-RETRY-SAFETY-V1",
        )
        self.assertEqual(manifest["file"]["source"], "app.js")
        self.assertEqual(manifest["file"]["sha256"], sha256(APP))
        self.assertEqual(manifest["contract"]["sha256"], sha256(CONTRACT))
        self.assertEqual(manifest["deployer"]["sha256"], sha256(DEPLOYER))
        self.assertEqual(manifest["service_action"], "none")
        self.assertFalse(manifest["calibration_action"])

    def test_deployer_has_no_physical_or_service_action(self):
        deployer = DEPLOYER.read_text(encoding="utf-8-sig")
        self.assertIn("G4-K1-CONTROL-CALIBRATION-UI-RETRY-SAFETY-V1", deployer)
        self.assertIn("app.js.before", deployer)
        self.assertIn("scp.exe", deployer)
        self.assertNotIn("S56k1_control_moonraker", deployer)
        self.assertNotIn("KCTRL_MESH_CALIBRATE", deployer)
        self.assertNotIn("KCTRL_CAL_PATH_BEGIN", deployer)
        self.assertNotIn("M104", deployer)
        self.assertNotIn("M140", deployer)
        self.assertIn("Assert-ServerInfo", deployer)
        self.assertIn("failed_components", deployer)
        self.assertIn("warnings", deployer)
        self.assertIn("'restored', 'rolled_back'", deployer)


if __name__ == "__main__":
    unittest.main()
