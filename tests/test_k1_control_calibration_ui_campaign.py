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

    def test_all_matrix_levels_are_declared_without_overclaiming_physical_runs(self):
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
        self.assertEqual(capability["physical_campaign_preset"], "quick")
        self.assertIn("without_claiming_four_physical_campaigns", capability["physical_campaign_scope"])

    def test_exact_proven_settings_and_final_guards_are_declared(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        settings = contract["operator_settings"]
        self.assertEqual(settings["plate"], "PEI_TEXTURED_A")
        self.assertEqual(
            (settings["bed_temperature_c"], settings["nozzle_temperature_c"]),
            (55, 140),
        )
        self.assertEqual(settings["soak_seconds"], 200)
        self.assertEqual(settings["matrix"], [6, 6])
        self.assertEqual(settings["interpolation"], "lagrange")
        self.assertEqual(settings["expected_initial_seed_z_mm"], -0.04)
        self.assertTrue(settings["replace_existing"])
        results = contract["required_results"]
        self.assertEqual(results["mesh_measurements"], 6)
        self.assertFalse(results["automatic_extra_measurement"])
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

    def test_validator_is_read_only_and_checks_the_full_final_state(self):
        source = VALIDATOR.read_text(encoding="utf-8")
        self.assertIn("[ValidateSet('Plan', 'Preflight', 'Validate')]", source)
        self.assertIn("Assert-InstalledUi", source)
        self.assertIn("Assert-ExactCampaignConfig", source)
        self.assertIn("Assert-Qualification", source)
        self.assertIn("@($privateState.meshes).Count -ne 6", source)
        self.assertIn("Assert-SafeAcceptedMachine", source)
        self.assertIn("VALIDATE_CALIBRATION_UI_CAMPAIGN_V1_OK", source)
        self.assertNotIn("/printer/gcode/script", source)
        self.assertNotIn("KCTRL_MESH_CALIBRATE", source)
        self.assertNotIn("KCTRL_CAL_PATH_MOVE", source)


if __name__ == "__main__":
    unittest.main()
