import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "calibration-ui-prtouch-bed-mesh-v2"
MANIFEST = PACKAGE / "deployment-manifest.json"
CONTRACT = PACKAGE / "calibration-ui-prtouch-bed-mesh-v2-contract.json"
COMPONENT = PACKAGE / "k1_control_probe_count.py"
DEPLOYER = ROOT / "scripts" / "deploy-k1-control-calibration-ui-prtouch-bed-mesh-v2.ps1"


class PrtouchBedMeshV2Tests(unittest.TestCase):
    def test_contract_records_xs3002_and_the_exact_atomic_pair(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(
            contract["contract_id"],
            "G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-BED-MESH-V2",
        )
        self.assertEqual(contract["observed_failure"]["screen_code"], "XS3002")
        self.assertEqual(contract["observed_failure"]["mesh_measurements"], 0)
        self.assertEqual(
            contract["runtime"]["atomic_fields"],
            ["bed_mesh.probe_count", "bed_mesh.algorithm"],
        )
        self.assertIn(
            {"probe_count": [9, 9], "algorithm": "bicubic"},
            contract["runtime"]["supported_pairs"],
        )
        self.assertIn(
            {"probe_count": [9, 9], "algorithm": "lagrange"},
            contract["runtime"]["forbidden_pairs"],
        )

    def test_manifest_pins_exact_upgrade_baseline_and_payload(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["baseline"]["component_sha256"],
            "6b97095f1cb4f62d7207d8e63186c9a93b6f53603b15bc5e4354de4aa767254e",
        )
        self.assertEqual(manifest["baseline"]["loaded_probe_count"], [6, 6])
        self.assertEqual(manifest["baseline"]["loaded_algorithm"], "lagrange")
        self.assertEqual(len(manifest["files"]), 1)
        self.assertEqual(
            hashlib.sha256(COMPONENT.read_bytes()).hexdigest(),
            manifest["files"][0]["sha256"],
        )
        self.assertEqual(
            hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
            manifest["contract"]["sha256"],
        )
        self.assertEqual(
            hashlib.sha256(DEPLOYER.read_bytes()).hexdigest(),
            manifest["deployer"]["sha256"],
        )

    def test_deployer_replaces_only_the_component_and_rolls_it_back_exactly(self):
        source = DEPLOYER.read_text(encoding="utf-8")
        self.assertIn("component_sha256", source)
        self.assertIn("k1_control_probe_count.py.before", source)
        self.assertIn("Invoke-ExactRollback", source)
        self.assertIn("S56k1_control_moonraker", source)
        self.assertIn("algorithm: bicubic", source)
        self.assertNotIn("moonraker.conf.before", source)
        for forbidden in ("KCTRL_MESH_CALIBRATE", "M104", "M140", "G28"):
            self.assertNotIn(forbidden, source)

    def test_component_verifies_loaded_count_and_algorithm(self):
        source = COMPONENT.read_text(encoding="utf-8")
        self.assertIn('algorithm = str(bed_mesh.get("algorithm", "")).lower()', source)
        self.assertIn('target_algorithm != "bicubic"', source)
        self.assertIn("self.config.write(previous)", source)
        self.assertIn("await self._restart_and_verify(previous)", source)


if __name__ == "__main__":
    unittest.main()
