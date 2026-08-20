import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1"
SCRIPT = ROOT / "scripts" / "prepare-control-foundation.py"

spec = importlib.util.spec_from_file_location("prepare_control_foundation", SCRIPT)
prepare = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(prepare)


class ControlFoundationPackageTests(unittest.TestCase):
    def test_manifest_is_pinned_fail_closed_and_does_not_touch_vendor_configs(self) -> None:
        manifest = json.loads((PACKAGE / "foundation-manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["printer_mutation_authorized"])
        self.assertEqual(manifest["active_g4_candidate"], "G4-K1-CONTROL-FOUNDATION-V1")
        self.assertFalse(manifest["network"]["daily_ui_exposed_in_this_slice"])
        self.assertEqual(manifest["network"]["moonraker_bind"], "127.0.0.1:7125")
        self.assertTrue(manifest["network"]["force_logins"])
        self.assertEqual(manifest["network"]["trusted_clients"], [])
        self.assertFalse(manifest["network"]["automatic_updates"])
        self.assertEqual(manifest["resource_gates"]["maximum_logs_disk_mib"], 16)
        components = {item["id"]: item for item in manifest["components"]}
        self.assertEqual(components["mainsail"]["version"], "v2.18.2")
        self.assertRegex(components["mainsail"]["sha256"], r"^[0-9a-f]{64}$")
        forbidden = set(manifest["forbidden_future_writes"])
        self.assertIn("/usr/data/printer_data/config/printer.cfg", forbidden)
        self.assertIn("/usr/data/printer_data/config/box.cfg", forbidden)

    def test_security_configs_have_no_open_trust_or_update_manager(self) -> None:
        moonraker = (PACKAGE / "config" / "moonraker.conf").read_text(encoding="utf-8")
        nginx = (PACKAGE / "config" / "nginx.conf").read_text(encoding="utf-8")
        self.assertIn("host: 127.0.0.1", moonraker)
        self.assertIn("force_logins: True", moonraker)
        self.assertNotIn("trusted_clients", moonraker)
        self.assertNotIn("update_manager", moonraker)
        self.assertIn("listen 4409", nginx)
        self.assertNotIn("listen 80", nginx)
        bootstrap = (PACKAGE / "config" / "nginx-bootstrap.conf").read_text(encoding="utf-8")
        self.assertIn("listen 127.0.0.1:4409", bootstrap)
        moonraker_service = (PACKAGE / "services" / "S56k1_control_moonraker").read_text(
            encoding="utf-8"
        )
        self.assertIn('-l "$LOGS/moonraker.log"', moonraker_service)
        logrotate = (PACKAGE / "config" / "logrotate-k1-control").read_text(encoding="utf-8")
        self.assertIn("size 1M", logrotate)
        self.assertIn("rotate 5", logrotate)
        self.assertIn("/var/run/k1-control-nginx.pid", logrotate)

    def test_deployment_plan_is_observation_only_and_not_authorized(self) -> None:
        plan = json.loads((PACKAGE / "deployment-plan.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["g4_id"], "G4-K1-CONTROL-FOUNDATION-V1")
        self.assertEqual(plan["status"], "prepared_not_authorized")
        self.assertFalse(plan["printer_mutation_authorized"])
        unchanged = set(plan["does_not_change"])
        self.assertIn("START_PRINT", unchanged)
        self.assertIn("CFS macros or firmware", unchanged)
        self.assertIn("Orca profiles or post-processing", unchanged)
        validation = set(plan["validation_without_machine_motion"])
        self.assertIn("no printer.gcode.script request is sent", validation)
        self.assertIn("resource gates from foundation-manifest.json pass", validation)
        self.assertIn("/etc/logrotate.d/k1-control-v1", plan["new_remote_paths"])

    def test_preparer_verifies_size_and_hash_and_rejects_workspace_root(self) -> None:
        artifact = ROOT / "tests" / "fixtures" / "k1-control-v1" / "orca-end-expanded.gcode"
        component = {
            "id": "sample",
            "size_bytes": artifact.stat().st_size,
            "sha256": prepare.file_sha256(artifact),
        }
        prepare.verify_artifact(artifact, component)
        component["sha256"] = "0" * 64
        with self.assertRaises(prepare.PreparationError):
            prepare.verify_artifact(artifact, component)
        with self.assertRaises(prepare.PreparationError):
            prepare.ensure_local_output(ROOT)


if __name__ == "__main__":
    unittest.main()
