from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deploy-control-foundation.ps1"


class ControlFoundationDeployerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SCRIPT.read_text(encoding="utf-8")

    def test_every_remote_action_is_behind_the_exact_v3_gate(self) -> None:
        self.assertIn("$RequiredGate = 'G4-K1-CONTROL-FOUNDATION-V3'", self.text)
        guard = self.text.index("Assert-ExactGate\n\nif ($Action -eq 'InstallBootstrap')")
        self.assertGreater(guard, self.text.index("if ($Action -eq 'Plan')"))
        self.assertNotIn("G4-K1-CONTROL-FOUNDATION-V1", self.text)
        self.assertNotIn("G4-K1-CONTROL-FOUNDATION-V2", self.text)

    def test_install_is_bootstrap_only_and_rolls_back_on_failure(self) -> None:
        self.assertIn("127.0.0.1:7125", self.text)
        self.assertIn("127.0.0.1:4409", self.text)
        self.assertIn("scp.exe -O -q", self.text)
        self.assertIn("chmod 0711 '$RemoteRoot' '$RemoteRoot/releases' '$RemoteRelease'", self.text)
        self.assertIn("find '$RemoteRelease/www' -type d -exec chmod 0755", self.text)
        self.assertIn("find '$RemoteRelease/www' -type f -exec chmod 0644", self.text)
        self.assertIn("Invoke-FoundationRollback -BestEffort", self.text)
        self.assertIn("restauration complete de l absence V3", self.text)
        self.assertIn("root.before' 2>/dev/null", self.text)
        self.assertIn("$script:RemoteRootWasProvenAbsent = $true", self.text)
        self.assertIn("rm -rf '$RemoteRoot'", self.text)
        self.assertLess(
            self.text.index("$MutationStarted = $true", self.text.index("if ($Action -eq 'InstallBootstrap')")),
            self.text.index("mkdir -p '$remoteBackup' '$remoteStaging'"),
        )
        self.assertIn("ActivateLan exige -CaptureId, -EvidenceDirectory et -AccountVerified", self.text)
        self.assertIn("nginx-bootstrap-auth.conf", self.text)
        self.assertIn("SetGatewayAccount", self.text)
        self.assertNotIn("printer.gcode.script", self.text)
        self.assertNotIn("/usr/data/printer_data/config/printer.cfg", self.text)

    def test_preflight_requires_idle_two_cfs_and_stock_syslog(self) -> None:
        self.assertIn("$klipper.print_state -ne 'standby'", self.text)
        self.assertIn("foreach ($name in @('T1', 'T2'))", self.text)
        self.assertIn("test -S /dev/log", self.text)
        self.assertIn("default 200KB", self.text)
        self.assertIn("'netstat', 'chown', 'stat', 'su'", self.text)
        self.assertIn("id -u www-data", self.text)
        self.assertIn("minimum_usr_data_free_before_install_mib", self.text)
        self.assertNotIn("logrotate", self.text)

    def test_stock_stack_and_resource_limits_are_checked_after_start(self) -> None:
        self.assertIn("function Assert-StockProcesses", self.text)
        self.assertIn("'[m]aster-server'", self.text)
        self.assertIn("'[d]isplay-server'", self.text)
        self.assertIn("kill -0", self.text)
        self.assertIn("maximum_release_disk_mib", self.text)

    def test_lan_activation_is_tested_atomic_and_reversible(self) -> None:
        self.assertIn("nginx-active.conf.previous", self.text)
        self.assertIn("nginx-active.conf.next", self.text)
        self.assertIn("-g 'error_log stderr;' -t -c '$gatewayNextConfig'", self.text)
        self.assertIn("Invoke-FoundationValidation -LanExpected", self.text)
        self.assertIn("Compte nginx absent ou invalide", self.text)
        self.assertIn("Get-GatewayAnonymousStatus", self.text)
        self.assertIn("mv '$gatewayPreviousConfig' '$gatewayActiveConfig'", self.text)
        self.assertIn("'$GatewayService' restart", self.text)
        self.assertLess(
            self.text.index("La protection nginx locale ne refuse pas"),
            self.text.index("ouverture Mainsail authentifie au LAN"),
        )

    def test_gateway_account_uses_secure_input_ssha_and_loopback_verification(self) -> None:
        self.assertIn("$PSVersionTable.PSVersion.Major -lt 7", self.text)
        self.assertIn("[Security.SecureString]$GatewayPassword", self.text)
        self.assertIn("function New-SshaPasswordRecord", self.text)
        self.assertIn("RandomNumberGenerator]::Fill", self.text)
        self.assertIn("{SSHA}", self.text)
        self.assertIn("chown root:www-data '$passwordNext'", self.text)
        self.assertIn("chmod 0640 '$passwordNext'", self.text)
        self.assertIn("chmod 0710 '$RemoteRoot/state'", self.text)
        self.assertIn(".nginx-read-probe", self.text)
        self.assertIn("su -s /bin/sh www-data", self.text)
        self.assertIn("gateway-authentication-failure.txt", self.text)
        self.assertIn("stat -c '%u:%g:%a'", self.text)
        self.assertIn("Invoke-RemoteWithInput", self.text)
        self.assertIn("StandardInputEncoding = [Text.UTF8Encoding]::new($false)", self.text)
        self.assertIn('$process.StandardInput.Write("`n")', self.text)
        credential_function = self.text[
            self.text.index("function Test-GatewayCredential"):
            self.text.index("function New-SshaPasswordRecord")
        ]
        self.assertIn("-c 'import base64;exec(base64.b64decode", credential_function)
        self.assertNotIn("echo $scriptPayload | base64 -d", credential_function)
        self.assertIn("anonymous_status -ne 401", self.text)
        self.assertIn("authenticated_status -ne 200", self.text)
        self.assertIn("proxy", (ROOT / "packages" / "k1-control-v1" / "config" / "nginx.conf").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
