from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deploy-control-foundation-paths-v1.ps1"
BASE_CONFIG = ROOT / "packages" / "k1-control-v1" / "config" / "moonraker.conf"
PATHS_CONFIG = ROOT / "packages" / "k1-control-v1" / "paths-v1" / "moonraker.conf"


class ControlFoundationPathsDeployerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SCRIPT.read_text(encoding="utf-8")

    def test_every_remote_action_requires_the_exact_paths_gate(self) -> None:
        self.assertIn(
            "$RequiredGate = 'G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1'",
            self.text,
        )
        self.assertIn("Assert-ExactGate\nif ($EvidenceDirectory)", self.text)
        self.assertIn("-Execute et -Gate", self.text)
        self.assertNotIn("G4-K1-CONTROL-FOUNDATION-V2", self.text)

    def test_preflight_requires_the_exact_v3_baseline_and_empty_roots(self) -> None:
        self.assertIn("CR4CU220812S12", self.text)
        self.assertIn("ota_version=2.3.5.34", self.text)
        self.assertIn("$PreviousConfigSha256", self.text)
        self.assertIn("test -z", self.text)
        self.assertIn("find '$root' -mindepth 1 -maxdepth 1", self.text)
        self.assertIn("$klipper.print_state -ne 'standby'", self.text)
        self.assertIn("foreach ($name in @('T1', 'T2'))", self.text)
        self.assertIn("Axes encore homes", self.text)
        self.assertIn("Permission config initiale inattendue", self.text)
        self.assertIn("Avertissement initial absent ou duplique", self.text)

    def test_deploy_changes_only_config_roots_and_moonraker_config(self) -> None:
        self.assertIn("rmdir '$MoonrakerConfigRoot'", self.text)
        self.assertIn("rmdir '$MoonrakerGcodeRoot'", self.text)
        self.assertIn("ln -s '$CrealityConfigRoot' '$MoonrakerConfigRoot'", self.text)
        self.assertIn("ln -s '$CrealityGcodeRoot' '$MoonrakerGcodeRoot'", self.text)
        self.assertIn("mv '$RemoteConfig.paths-next' '$RemoteConfig'", self.text)
        self.assertIn("'$MoonrakerService' stop", self.text)
        self.assertIn("'$MoonrakerService' start", self.text)
        self.assertNotIn("'$GatewayService' restart", self.text)
        self.assertNotIn("'$GatewayService' stop", self.text)
        self.assertNotIn("printer.cfg' >", self.text)
        self.assertNotIn("virtual_sdcard", self.text)

    def test_backup_is_verified_before_the_first_runtime_change(self) -> None:
        backup_config = self.text.index("moonraker.conf.before'\" | Out-Null")
        backup_tar = self.text.index("empty-roots.before.tar' -C")
        stop_service = self.text.index(
            "Invoke-Remote \"'$MoonrakerService' stop\"",
            self.text.index("if ($Action -eq 'Deploy')"),
        )
        self.assertLess(backup_config, stop_service)
        self.assertLess(backup_tar, stop_service)
        self.assertIn("backupConfigHash -ne $PreviousConfigSha256", self.text)
        self.assertIn("remote-backup-sha256.txt", self.text)

    def test_validation_is_read_only_and_reports_api_permissions(self) -> None:
        self.assertIn("Get-MoonrakerJson '/server/files/roots'", self.text)
        self.assertIn("permissions -ne 'r'", self.text)
        self.assertIn("permissions -ne 'rw'", self.text)
        self.assertIn("Get-MoonrakerJson '/server/info'", self.text)
        self.assertIn("Les avertissements de chemins Moonraker", self.text)
        self.assertIn("gcode-api-risk.txt", self.text)
        self.assertNotIn("/server/files/upload", self.text)
        self.assertNotIn("/server/files/delete", self.text)
        self.assertNotIn("printer/print/start", self.text)
        self.assertNotIn("printer.gcode.script", self.text)

    def test_failure_rolls_back_and_restores_original_directories(self) -> None:
        self.assertIn("try { Invoke-PathsRollback }", self.text)
        self.assertIn("Deploiement KO et rollback KO", self.text)
        self.assertIn("active_hash=", self.text)
        self.assertIn("$active_hash", self.text)
        self.assertIn("tar -xpf '$remoteBackup/empty-roots.before.tar'", self.text)
        self.assertIn("$RemoteConfig.rollback-next", self.text)
        self.assertIn("Assert-RollbackState", self.text)
        self.assertIn("Rollback de racine incomplet", self.text)

    def test_package_disables_config_write_access(self) -> None:
        base_config = BASE_CONFIG.read_text(encoding="utf-8")
        paths_config = PATHS_CONFIG.read_text(encoding="utf-8")
        self.assertNotIn("enable_config_write_access", base_config)
        self.assertIn("enable_config_write_access: False", paths_config)
        self.assertIn("queue_gcode_uploads: False", paths_config)
        self.assertIn("paths-v1\\moonraker.conf", self.text)


if __name__ == "__main__":
    unittest.main()
