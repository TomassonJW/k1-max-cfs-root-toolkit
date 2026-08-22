import json
import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "calibration-ui-campaign-v1"
CONTRACT = PACKAGE / "calibration-ui-campaign-contract.json"
README = PACKAGE / "README.md"
MANIFEST = PACKAGE / "execution-manifest.json"
UI_PACKAGE = ROOT / "packages" / "k1-control-v1" / "calibration-ui-matrix-v1"
VALIDATOR = ROOT / "scripts" / "validate-k1-control-calibration-ui-campaign-v1.ps1"


class CalibrationUiCampaignContractTests(unittest.TestCase):
    def test_execution_manifest_pins_every_reviewed_artifact(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["package"],
            "G4-K1-CONTROL-CALIBRATION-UI-CAMPAIGN-V1",
        )
        self.assertEqual(manifest["operator_control"], "browser_only")
        self.assertEqual(manifest["mesh_measurements_per_level"], 6)
        self.assertEqual(manifest["physical_levels"], 4)
        self.assertEqual(manifest["total_mesh_measurements"], 24)
        for artifact in manifest["artifacts"]:
            path = ROOT / artifact["path"]
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                artifact["sha256"],
            )

    def test_campaign_is_separate_gated_and_requires_browser_only_control(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(
            contract["contract_id"],
            "G4-K1-CONTROL-CALIBRATION-UI-CAMPAIGN-V1",
        )
        self.assertFalse(contract["printer_mutation_authorized"])
        self.assertEqual(
            contract["dependency"]["required_result"],
            "deployed_validated_and_rendered_in_browser_with_6_9_11_15_presets",
        )
        self.assertFalse(
            contract["required_results"]["console_or_codex_control_during_campaign"]
        )
        self.assertEqual(contract["rerun_policy"], "no_automatic_rerun")

    def test_all_matrix_levels_require_real_physical_mesh_proof(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        capability = contract["matrix_capability"]
        self.assertEqual(
            [(item["matrix"], item["interpolation"]) for item in capability["selectable_presets"]],
            [
                ([6, 6], "lagrange"),
                ([9, 9], "bicubic"),
                ([11, 11], "bicubic"),
                ([15, 15], "bicubic"),
            ],
        )
        self.assertEqual(capability["physical_proof"], "six_real_meshes_at_every_preset")
        self.assertEqual(capability["full_z_workflow_preset"], "quick")

    def test_exact_proven_settings_and_final_guards_are_declared(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        settings = contract["common_operator_settings"]
        self.assertEqual(settings["plate"], "PEI_TEXTURED_A")
        self.assertEqual(
            (settings["bed_temperature_c"], settings["nozzle_temperature_c"]),
            (55, 140),
        )
        self.assertEqual(settings["soak_seconds"], 200)
        self.assertEqual(settings["expected_initial_seed_z_mm"], -0.04)
        sequence = contract["physical_sequence"]
        self.assertEqual([item["name"] for item in sequence], ["standard", "precise", "expert", "quick"])
        self.assertEqual([item["matrix"] for item in sequence], [[9, 9], [11, 11], [15, 15], [6, 6]])
        self.assertEqual([item["interpolation"] for item in sequence], ["bicubic", "bicubic", "bicubic", "lagrange"])
        self.assertEqual([item["replace_existing"] for item in sequence], [False, False, False, True])
        results = contract["required_results"]
        self.assertEqual(results["mesh_measurements_per_level"], 6)
        self.assertEqual(results["total_mesh_measurements"], 24)
        self.assertFalse(results["automatic_extra_measurement"])
        self.assertEqual(len(results["profiles"]), 4)
        self.assertEqual(results["runtime_store_integrity"], "ok")
        self.assertEqual(results["runtime_accepted_z_valid"], 1)
        self.assertEqual(results["runtime_session_active"], 0)
        self.assertEqual(results["path_phase"], "committed")
        self.assertEqual(results["heater_targets_c"], [0, 0])
        self.assertEqual(results["cfs_connected"], 2)

    def test_ui_contains_every_operator_action_needed_by_the_campaign(self):
        index = (UI_PACKAGE / "www" / "index.html").read_text(encoding="utf-8")
        app = (UI_PACKAGE / "www" / "app.js").read_text(encoding="utf-8")
        for control in (
            "start-mesh",
            "start-z",
            "next-z",
            "confirm-gap",
            "accept-z",
            "cancel-workflow",
            "rollback-campaign",
        ):
            self.assertIn('id="%s"' % control, index)
        self.assertIn("function hydrateForm()", app)
        self.assertIn('input:not(#plate-clear)', app)
        self.assertNotIn("/printer/gcode/script", app)

    def test_runbook_rejects_console_assistance_and_reruns(self):
        readme = README.read_text(encoding="utf-8")
        self.assertIn("sans console et sans commande Codex", readme)
        self.assertIn("Aucun septième passage", readme)
        self.assertIn("Aucun rerun automatique", readme)
        self.assertIn("vingt-quatre meshes", readme)

    def test_validator_is_read_only_and_checks_the_full_final_state(self):
        source = VALIDATOR.read_text(encoding="utf-8")
        self.assertIn("[ValidateSet('Plan', 'Preflight', 'CaptureLevel', 'Validate')]", source)
        self.assertIn("Assert-InstalledUi", source)
        self.assertIn("Assert-ExactCampaignConfig", source)
        self.assertIn("Assert-Qualification", source)
        self.assertIn("Assert-ExpectedProfiles", source)
        self.assertIn("CAPTURE_CALIBRATION_UI_LEVEL_OK", source)
        self.assertIn("@($privateState.meshes).Count -ne 6", source)
        self.assertIn("Assert-SafeAcceptedMachine", source)
        self.assertIn("VALIDATE_CALIBRATION_UI_CAMPAIGN_V1_OK", source)
        self.assertNotIn("/printer/gcode/script", source)
        self.assertNotIn("KCTRL_MESH_CALIBRATE", source)
        self.assertNotIn("KCTRL_CAL_PATH_MOVE", source)

    def test_preflight_accepts_only_fresh_cancelled_zero_or_exact_rollback(self):
        source = VALIDATOR.read_text(encoding="utf-8")
        self.assertIn("$freshIdle", source)
        self.assertIn("$cancelledBeforeFirstMesh", source)
        self.assertIn("$exactRollback", source)
        self.assertIn("[int]$api.mesh_index -eq 0", source)
        self.assertIn("[bool]$api.backup_available", source)
        self.assertIn("$api.rollback.printer_cfg_sha256", source)
        self.assertNotIn("@('cancelled', 'failed', 'mesh_rejected')", source)


if __name__ == "__main__":
    unittest.main()
