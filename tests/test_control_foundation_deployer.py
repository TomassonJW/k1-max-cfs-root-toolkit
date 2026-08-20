from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deploy-control-foundation.ps1"


class ControlFoundationDeployerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SCRIPT.read_text(encoding="utf-8")

    def test_every_remote_action_is_behind_the_exact_v2_gate(self) -> None:
        self.assertIn("$RequiredGate = 'G4-K1-CONTROL-FOUNDATION-V2'", self.text)
        guard = self.text.index("Assert-ExactGate\n\nif ($Action -eq 'InstallBootstrap')")
        self.assertGreater(guard, self.text.index("if ($Action -eq 'Plan')"))
        self.assertNotIn("G4-K1-CONTROL-FOUNDATION-V1", self.text)

    def test_install_is_bootstrap_only_and_rolls_back_on_failure(self) -> None:
        self.assertIn("127.0.0.1:7125", self.text)
        self.assertIn("127.0.0.1:4409", self.text)
        self.assertIn("Invoke-FoundationRollback -BestEffort", self.text)
        self.assertIn("ActivateLan exige -AccountVerified", self.text)
        self.assertNotIn("printer.gcode.script", self.text)
        self.assertNotIn("/usr/data/printer_data/config/printer.cfg", self.text)

    def test_preflight_requires_idle_two_cfs_and_stock_syslog(self) -> None:
        self.assertIn("$klipper.print_state -ne 'standby'", self.text)
        self.assertIn("foreach ($name in @('T1', 'T2'))", self.text)
        self.assertIn("test -S /dev/log", self.text)
        self.assertIn("default 200KB", self.text)
        self.assertIn("@('base64', 'tar', 'unzip', 'sha256sum', 'du', 'df', 'netstat')", self.text)
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
        self.assertIn(" -t -c '$nextConfig'", self.text)
        self.assertIn("Invoke-FoundationValidation -LanExpected", self.text)
        self.assertIn("mv '$previousConfig' '$activeConfig'", self.text)


if __name__ == "__main__":
    unittest.main()
