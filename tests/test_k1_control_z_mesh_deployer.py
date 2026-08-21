import hashlib
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deploy-k1-control-z-mesh-runtime-v1.ps1"
PACKAGE = ROOT / "packages" / "k1-control-v1" / "z-mesh-runtime-v1"
MANIFEST = PACKAGE / "deployment-manifest.json"


class K1ControlZMeshDeployerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8-sig")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_every_remote_action_requires_the_exact_gate_and_execute(self):
        self.assertIn("G4-K1-CONTROL-Z-MESH-RUNTIME-V1", self.script)
        self.assertIn("-not $Execute", self.script)
        self.assertLess(self.script.index("Assert-ExactGate\n"), self.script.index("if ($Action -eq 'Preflight')"))

    def test_manifest_hashes_match_the_reviewed_public_files(self):
        records = {record["source"]: record for record in self.manifest["files"]}
        for filename in ("k1-control-z-mesh.cfg", "k1_control_store.py"):
            digest = hashlib.sha256((PACKAGE / filename).read_bytes()).hexdigest()
            self.assertEqual(records[filename]["sha256"], digest)
            self.assertIn(digest, self.script)

    def test_backup_is_verified_before_the_first_runtime_mutation(self):
        deploy = self.script[self.script.index("if ($Action -eq 'Deploy')") :]
        backup = deploy.index("sha256sum -c checksums.sha256")
        mutation = deploy.index("$MutationStarted = $true")
        self.assertLess(backup, mutation)
        self.assertIn("printer.cfg.before", deploy[:mutation])

    def test_deploy_adds_only_two_files_and_one_include(self):
        self.assertEqual(len(self.manifest["files"]), 2)
        self.assertEqual(
            {record["destination"] for record in self.manifest["files"]},
            {
                "/usr/data/printer_data/config/k1-control-z-mesh.cfg",
                "/usr/share/klipper/klippy/extras/k1_control_store.py",
            },
        )
        self.assertEqual(
            self.manifest["printer_cfg"]["change"],
            "insert one [include k1-control-z-mesh.cfg] after [include box.cfg]",
        )
        self.assertFalse(self.manifest["runtime_effect"]["orca_profile_change"])

    def test_deploy_uses_host_restart_and_a_no_motion_fail_closed_check(self):
        deploy = self.script[self.script.index("if ($Action -eq 'Deploy')") : self.script.index("if ($Action -eq 'Validate')")]
        self.assertIn("Invoke-KlipperScript 'RESTART' -NoResponse", deploy)
        self.assertNotIn("FIRMWARE_RESTART", deploy)
        self.assertIn("Assert-FailClosedWithoutMotion", deploy)
        self.assertIn("KCTRL_PRODUCTION_ASSERT_ARMED", self.script)
        for token in (" G28", " G1 ", "M104", "M109", "M140", "M190", "BOX_START_PRINT"):
            self.assertNotIn(token, deploy)

    def test_remote_python_reads_stdin_before_receiving_arguments(self):
        self.assertIn("/usr/share/klippy-env/bin/python - '$include'", self.script)
        self.assertIn("/usr/share/klippy-env/bin/python - '$Script' '$wait'", self.script)

    def test_rollback_archives_state_before_removing_it(self):
        rollback = self.script[
            self.script.index("function Invoke-RuntimeRollback") : self.script.index("if ($Action -eq 'Plan')")
        ]
        archive = rollback.index("state-at-rollback")
        remove = rollback.index("rm -f '$RuntimeConfig'")
        self.assertLess(archive, remove)
        self.assertIn("printer.cfg.before", rollback)
        self.assertIn("sha256sum -c checksums.sha256", rollback)
        self.assertIn("Wait-IdleSnapshot -RequireUnhomed -Attempts 60", rollback)
        self.assertIn("$PrinterConfig.rollback-final", rollback)
        self.assertLess(
            rollback.index("$runtimeUnloaded = $true"),
            rollback.index("Wait-IdleSnapshot -RequireUnhomed -Attempts 60"),
        )
        self.assertLess(
            rollback.index("Wait-IdleSnapshot -RequireUnhomed -Attempts 60"),
            rollback.index("cp '$remoteBackup/printer.cfg.before' '$PrinterConfig.rollback-final'"),
        )
        self.assertLess(
            rollback.index("Start-Sleep -Seconds 3"),
            rollback.index("$restoredHash"),
        )

    def test_deploy_waits_for_runtime_and_both_cfs_to_stabilize(self):
        installed = self.script[
            self.script.index("function Assert-RuntimeInstalled") : self.script.index("function Assert-FailClosedWithoutMotion")
        ]
        self.assertIn("$runtimeReady = $true", installed)
        self.assertIn("validation-runtime-not-ready.json", installed)
        self.assertLess(
            installed.index("validation-runtime-not-ready.json"),
            installed.index("Runtime K1 Control non pret apres le delai."),
        )
        self.assertIn("Wait-IdleSnapshot -IncludeRuntime -RequireUnhomed -Attempts 60", installed)


if __name__ == "__main__":
    unittest.main()
