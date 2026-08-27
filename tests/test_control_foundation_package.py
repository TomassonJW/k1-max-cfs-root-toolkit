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
        self.assertEqual(manifest["package_version"], 3)
        self.assertEqual(manifest["active_g4_candidate"], "G4-K1-CONTROL-FOUNDATION-V3")
        self.assertFalse(manifest["network"]["daily_ui_exposed_in_this_slice"])
        self.assertEqual(manifest["network"]["moonraker_bind"], "127.0.0.1:7125")
        self.assertFalse(manifest["network"]["force_logins"])
        self.assertFalse(manifest["network"]["api_key_enabled"])
        self.assertEqual(manifest["network"]["trusted_clients"], ["127.0.0.1"])
        self.assertEqual(manifest["network"]["authentication_owner"], "nginx")
        self.assertEqual(manifest["network"]["gateway_authentication"], "http_basic")
        self.assertEqual(manifest["network"]["password_minimum_characters"], 16)
        self.assertEqual(manifest["network"]["password_maximum_characters"], 128)
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
        nginx_auth = (PACKAGE / "config" / "nginx-bootstrap-auth.conf").read_text(
            encoding="utf-8"
        )
        self.assertIn("host: 127.0.0.1", moonraker)
        self.assertIn("force_logins: False", moonraker)
        self.assertIn("enable_api_key: False", moonraker)
        self.assertIn("provider: none", moonraker)
        self.assertIn("validate_service: False", moonraker)
        self.assertIn("validate_config: False", moonraker)
        self.assertIn("trusted_clients:", moonraker)
        self.assertIn("127.0.0.1", moonraker)
        self.assertFalse((PACKAGE / "config" / "moonraker-bootstrap.conf").exists())
        self.assertNotIn("update_manager", moonraker)
        self.assertIn("listen 0.0.0.0:4409", nginx)
        self.assertNotIn("listen 80", nginx)
        bootstrap = (PACKAGE / "config" / "nginx-bootstrap.conf").read_text(encoding="utf-8")
        self.assertIn("listen 127.0.0.1:4409", bootstrap)
        self.assertIn("listen 127.0.0.1:4409", nginx_auth)
        self.assertNotIn("auth_basic ", bootstrap)
        for protected in (nginx_auth, nginx):
            self.assertIn('auth_basic "K1 Max Control"', protected)
            self.assertIn("auth_basic_user_file /usr/data/k1-control-v1/state/nginx.htpasswd", protected)
        moonraker_service = (PACKAGE / "services" / "S56k1_control_moonraker").read_text(
            encoding="utf-8"
        )
        self.assertIn('-l "$LOGS/moonraker.log"', moonraker_service)
        self.assertIn('touch "$STATE/misc/usb.ids"', moonraker_service)
        self.assertIn('CONFIG="$ROOT/config/moonraker.conf"', moonraker_service)
        self.assertFalse((PACKAGE / "config" / "logrotate-k1-control").exists())
        self.assertIn("error_log syslog:server=unix:/dev/log", nginx)
        self.assertIn("error_log syslog:server=unix:/dev/log", bootstrap)
        self.assertIn("error_log syslog:server=unix:/dev/log", nginx_auth)
        self.assertIn("tag=k1_control", nginx)
        self.assertIn("tag=k1_control", bootstrap)
        self.assertIn("tag=k1_control", nginx_auth)
        self.assertNotIn("tag=k1-control", nginx)
        self.assertNotIn("tag=k1-control", bootstrap)
        self.assertNotIn("tag=k1-control", nginx_auth)
        for gateway_config in (bootstrap, nginx_auth, nginx):
            self.assertEqual(gateway_config.count("proxy_set_header Host $http_host;"), 2)
            self.assertEqual(gateway_config.count('proxy_set_header Authorization "";'), 2)
            self.assertNotIn("proxy_set_header Host $host;", gateway_config)
        for temp_kind in ("client-body", "proxy", "fastcgi", "uwsgi", "scgi"):
            expected = f"/usr/data/k1-control-v1/tmp/nginx-{temp_kind}"
            self.assertIn(expected, nginx)
            self.assertIn(expected, bootstrap)
            self.assertIn(expected, nginx_auth)
        for private_source in ("127.0.0.1", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"):
            self.assertIn(f"allow {private_source};", nginx)
        gateway_service = (PACKAGE / "services" / "S57k1_control_gateway").read_text(
            encoding="utf-8"
        )
        self.assertIn("/usr/data/k1-control-v1/tmp", gateway_service)
        self.assertNotIn("/var/tmp/nginx", gateway_service)
        self.assertIn('-g "error_log stderr;"', gateway_service)
        self.assertIn('-s quit', gateway_service)
        self.assertIn('-s KILL', gateway_service)
        manifest = json.loads((PACKAGE / "foundation-manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["logging"]["extra_logging_package_required"])
        self.assertEqual(manifest["logging"]["observed_syslog_default_max_kib"], 200)
        self.assertEqual(manifest["resource_gates"]["minimum_usr_data_free_before_install_mib"], 512)

    def test_deployment_plan_is_observation_only_and_not_authorized(self) -> None:
        plan = json.loads((PACKAGE / "deployment-plan.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["g4_id"], "G4-K1-CONTROL-FOUNDATION-V3")
        self.assertEqual(plan["status"], "prepared_not_authorized")
        self.assertFalse(plan["printer_mutation_authorized"])
        unchanged = set(plan["does_not_change"])
        self.assertIn("START_PRINT", unchanged)
        self.assertIn("CFS macros or firmware", unchanged)
        self.assertIn("Orca profiles or post-processing", unchanged)
        validation = set(plan["validation_without_machine_motion"])
        self.assertIn("no printer.gcode.script request is sent", validation)
        self.assertIn("resource gates from foundation-manifest.json pass", validation)
        self.assertNotIn("/etc/logrotate.d/k1-control-v1", plan["new_remote_paths"])
        self.assertTrue(any("/dev/log" in item for item in plan["pre_change_backup"]))
        self.assertIn("moonraker_trusted_client", plan["bootstrap"])
        self.assertTrue(any("anonymous Mainsail" in item for item in validation))
        self.assertTrue(any("HTTP Basic credentials" in item for item in validation))

    def test_account_wrapper_prompts_securely_and_never_accepts_plaintext_cli_password(self) -> None:
        wrapper = (ROOT / "scripts" / "set-control-foundation-account.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("Read-Host 'Mot de passe (16 a 128 caracteres ASCII, sans espace)' -AsSecureString", wrapper)
        self.assertIn("Read-Host 'Confirme le mot de passe' -AsSecureString", wrapper)
        self.assertIn("-GatewayPassword $password", wrapper)
        self.assertIn("$PSVersionTable.PSVersion.Major -lt 7", wrapper)
        self.assertNotIn("[string]$Password", wrapper)

    def test_double_click_launcher_uses_the_secure_tunnel_without_secrets(self) -> None:
        launcher = (ROOT / "Ouvrir-Mainsail-K1-Max.cmd").read_text(encoding="utf-8")
        calibration_launcher = (ROOT / "Ouvrir-Calibration-K1-Max.cmd").read_text(
            encoding="utf-8"
        )
        helper = (ROOT / "scripts" / "launch-control-dashboard.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("launch-control-dashboard.ps1", launcher)
        self.assertIn("-WindowStyle Hidden", launcher)
        self.assertIn("launch-control-dashboard.ps1", calibration_launcher)
        self.assertIn("-View Calibration", calibration_launcher)
        self.assertIn("http://localhost:4409/k1-control/", helper)
        self.assertIn("[ValidateSet('Mainsail', 'Calibration')]", helper)
        self.assertIn("127.0.0.1:4409:127.0.0.1:4409", helper)
        self.assertIn("ExitOnForwardFailure=yes", helper)
        self.assertIn("ServerAliveInterval=30", helper)
        self.assertIn("BatchMode=yes", helper)
        self.assertIn("'k1max-root'", helper)
        self.assertIn("return $Status -in @(200, 401)", helper)
        self.assertIn("Start-Process $DashboardUrl", helper)
        self.assertNotRegex(helper, r"192\.168\.|10\.\d+\.\d+\.\d+")

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
