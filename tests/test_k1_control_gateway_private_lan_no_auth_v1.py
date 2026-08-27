import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "gateway-private-lan-no-auth-v1"


class GatewayPrivateLanNoAuthV1Tests(unittest.TestCase):
    def test_gateway_has_no_authentication_and_keeps_private_network_boundary(self) -> None:
        nginx = (PACKAGE / "nginx.conf").read_text(encoding="utf-8")
        self.assertNotIn("auth_basic", nginx)
        self.assertIn("listen 0.0.0.0:4409", nginx)
        self.assertIn("server 127.0.0.1:7125", nginx)
        for source in ("127.0.0.1", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"):
            self.assertIn(f"allow {source};", nginx)
        self.assertIn("deny all;", nginx)
        self.assertEqual(nginx.count("proxy_set_header Authorization \"\";"), 2)
        self.assertEqual(nginx.count("proxy_set_header X-Real-IP 127.0.0.1;"), 2)
        self.assertNotIn("proxy_set_header X-Real-IP $remote_addr;", nginx)

    def test_manifest_limits_the_write_set_and_preserves_rollback(self) -> None:
        manifest = json.loads((PACKAGE / "deployment-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["contract_id"],
            "G4-K1-CONTROL-GATEWAY-PRIVATE-LAN-NO-AUTH-V1",
        )
        self.assertEqual(
            manifest["candidate"]["destination"],
            "/usr/data/k1-control-v1/state/nginx-active.conf",
        )
        self.assertEqual(
            manifest["service_action"],
            "reload /etc/init.d/S57k1_control_gateway only",
        )
        self.assertIn("password file deletion", manifest["forbidden"])
        self.assertEqual(len(manifest["allowed_before_sha256"]), 2)
        for digest in manifest["allowed_before_sha256"]:
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertRegex(manifest["candidate"]["sha256"], r"^[0-9a-f]{64}$")

    def test_deployer_is_bounded_and_has_automatic_rollback(self) -> None:
        deployer = (ROOT / "scripts" / "deploy-k1-control-gateway-private-lan-no-auth-v1.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("S57k1_control_gateway", deployer)
        self.assertNotIn("S56k1_control_moonraker", deployer)
        self.assertNotIn("printer/gcode/script", deployer)
        self.assertIn("PREFLIGHT_GATEWAY_PRIVATE_LAN_NO_AUTH_V1_OK", deployer)
        self.assertIn("VALIDATE_GATEWAY_PRIVATE_LAN_NO_AUTH_V1_OK", deployer)
        self.assertIn("ROLLBACK_GATEWAY_PRIVATE_LAN_NO_AUTH_V1_OK", deployer)
        self.assertIn("cp '$RemoteBackupConfig' '$RemoteActive'", deployer)
        self.assertIn("-g 'error_log stderr;' -t", deployer)


if __name__ == "__main__":
    unittest.main()
