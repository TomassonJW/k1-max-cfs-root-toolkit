import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "calibration-ui-navigation-v1"
MANIFEST = PACKAGE / "deployment-manifest.json"
CONTRACT = PACKAGE / "calibration-ui-navigation-contract.json"
APP = PACKAGE / "app.js"
NAVI = PACKAGE / "navi.json"
DEPLOYER = ROOT / "scripts" / "deploy-k1-control-calibration-ui-navigation-v1.ps1"


class CalibrationUiNavigationTests(unittest.TestCase):
    def test_manifest_pins_the_two_files_and_static_alias_write_set(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["contract_id"],
            "G4-K1-CONTROL-CALIBRATION-UI-NAVIGATION-V1-R2",
        )
        self.assertEqual(
            [item["source"] for item in manifest["files"]],
            ["app.js", "navi.json"],
        )
        self.assertEqual(manifest["service_action"], "none")
        self.assertFalse(manifest["printer_cfg_changed"])
        self.assertFalse(manifest["authentication_changed"])
        self.assertEqual(
            manifest["static_alias"],
            {
                "destination": "/usr/data/k1-control-v1/current/www/mainsail/access-k1-control",
                "target": "k1-control",
                "service_worker_vendor_file_changed": False,
            },
        )
        for item in manifest["files"]:
            path = PACKAGE / item["source"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"])
        self.assertEqual(
            hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
            manifest["contract"]["sha256"],
        )
        self.assertEqual(
            hashlib.sha256(DEPLOYER.read_bytes()).hexdigest(),
            manifest["deployer"]["sha256"],
        )

    def test_navigation_is_same_origin_and_keeps_authentication(self):
        navigation = json.loads(NAVI.read_text(encoding="utf-8"))
        self.assertEqual(len(navigation), 1)
        self.assertEqual(navigation[0]["title"], "K1 Control")
        self.assertEqual(navigation[0]["href"], "/access-k1-control/")
        self.assertEqual(navigation[0]["target"], "_self")
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertFalse(contract["navigation"]["authentication_change"])
        self.assertFalse(contract["navigation"]["vendor_service_worker_changed"])
        self.assertTrue(navigation[0]["href"].startswith("/access"))

    def test_z_instructions_match_every_closed_or_active_phase(self):
        source = APP.read_text(encoding="utf-8")
        self.assertIn('phase === "starting_z"', source)
        self.assertIn("Préparation du Z en cours", source)
        self.assertIn('phase === "z_confirmed"', source)
        self.assertIn("Tu peux enregistrer le Z", source)
        self.assertIn('phase === "accepted"', source)
        self.assertIn("La calibration est terminée", source)
        self.assertNotIn(': "Qualifie d’abord le mesh robuste.";', source)

    def test_deployer_has_backup_rollback_and_no_physical_command(self):
        source = DEPLOYER.read_text(encoding="utf-8")
        self.assertIn("app.js.before", source)
        self.assertIn("navi.json.before", source)
        self.assertIn("Assert-RemoteBaseline", source)
        self.assertIn("Assert-RemoteFinal", source)
        self.assertIn("ln -s 'k1-control' '$RemoteAlias.next'", source)
        self.assertIn("rm -f '$RemoteAlias'", source)
        self.assertNotIn("$RemoteRoot/current/www/mainsail/sw.js", source)
        self.assertIn("service_restart = $false", source)
        for forbidden in (
            "/printer/gcode/script",
            "KCTRL_MESH_CALIBRATE",
            "KCTRL_CAL_PATH_MOVE",
            "FIRMWARE_RESTART",
            "RESTART",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
