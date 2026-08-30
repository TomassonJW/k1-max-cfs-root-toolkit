import importlib.util
import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "start-sequence-owner-preinsert-geometry-r4"
CONFIG = PACKAGE / "k1-control-start-sequence-owner-preinsert-geometry-r4.cfg"
DEPLOYER = ROOT / "scripts" / "deploy-k1-control-start-sequence-owner-preinsert-geometry-r4.ps1"


def load_verifier():
    path = PACKAGE / "verify_candidate.py"
    spec = importlib.util.spec_from_file_location("start_sequence_owner_preinsert_geometry_r4", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class StartSequenceOwnerPreinsertGeometryR4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier = load_verifier()
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.manifest = json.loads((PACKAGE / "deployment-manifest.json").read_text(encoding="utf-8"))
        cls.deployment_result = json.loads((PACKAGE / "deployment-result.json").read_text(encoding="utf-8"))
        cls.config = CONFIG.read_text(encoding="utf-8")
        cls.deployer = DEPLOYER.read_text(encoding="utf-8")

    def test_static_candidate_closes_contact_before_insertion(self):
        result = self.verifier.verify()
        self.assertEqual("START_SEQUENCE_OWNER_PREINSERT_GEOMETRY_R4_OFFLINE_OK", result["status"])
        self.assertTrue(result["contact_before_insertion"])
        self.assertEqual(0, result["post_insertion_probe_commands"])
        self.assertTrue(result["single_use_geometry_token"])
        self.assertTrue(result["valid_geometry_reuse_without_unload_or_probe"])
        self.assertTrue(result["mesh_rearmed_after_official_insertion"])
        self.assertTrue(result["camera_before_model"])

    def test_contract_has_the_final_order(self):
        order = self.contract["required_order"]
        self.assertLess(order.index("ACCURATE_G28"), order.index("official_T1A_insertion"))
        self.assertLess(order.index("official_T1A_insertion"), order.index("rearm_11x11_and_accepted_z_without_probe"))
        self.assertLess(order.index("camera_release_check"), order.index("outside_bed_prime"))
        self.assertLess(order.index("camera_prime_check"), order.index("resume_model"))
        reuse = self.contract["reuse_required_order"]
        self.assertLess(reuse.index("stable_T1A_already_engaged"), reuse.index("verify_existing_XYZ_11x11_and_accepted_z_without_probe"))
        self.assertNotIn("official_T1A_insertion", reuse)
        self.assertNotIn("ACCURATE_G28", reuse)

    def test_post_insertion_path_has_no_contact_command(self):
        post_insertion = self.config.split("[gcode_macro KCTRL_JOB_BEGIN_KEEP_CORRECT_V1]", 1)[1]
        for forbidden in ("ACCURATE_G28", "G28 Z", "BED_MESH_CALIBRATE", "CX_PRINT_LEVELING_CALIBRATION"):
            self.assertNotIn(forbidden, post_insertion)
        self.assertNotRegex(post_insertion, r"(?m)^\s*G28(?:\s|$)")

    def test_geometry_token_is_single_use_and_bounded(self):
        self.assertIn("variable_geometry_ready_token: 0", self.config)
        self.assertIn("VARIABLE=geometry_ready_token VALUE=1", self.config)
        self.assertIn("VARIABLE=geometry_ready_deadline VALUE={now + 600.0}", self.config)
        job = self.config.split("[gcode_macro KCTRL_JOB_BEGIN_KEEP_CORRECT_V1]", 1)[1].split("\n[", 1)[0]
        self.assertIn("VARIABLE=geometry_ready_token VALUE=0", job)

    def test_valid_geometry_reuse_keeps_t1a_without_contact_command(self):
        reuse = self.config.split("[gcode_macro KCTRL_REUSE_VALID_GEOMETRY_WITH_T1A_R4]", 1)[1].split("\n[", 1)[0]
        self.assertIn('box.T1.filament|string != "A"', reuse)
        self.assertIn("KCTRL_PRODUCTION_ARM", reuse)
        self.assertNotIn("ACCURATE_G28", reuse)
        self.assertNotIn("BED_MESH_CALIBRATE", reuse)
        self.assertNotRegex(reuse, r"(?m)^\s*G28(?:\s|$)")

    def test_camera_holds_use_only_base_pause_and_resume(self):
        active = "\n".join(line.split("#", 1)[0] for line in self.config.splitlines())
        self.assertIn("PAUSE_BASE", active)
        self.assertIn("RESUME_BASE", active)
        self.assertIsNone(re.search(r"(?m)^\s+(?:PAUSE|RESUME)\s*$", active))
        self.assertIn(
            'phase in ["camera_release_check", "first_layer_heating", "visible_purge", "camera_prime_check"]',
            self.config,
        )

    def test_deployer_is_exact_reversible_and_not_a_physical_run(self):
        self.assertIn("G4-K1-CONTROL-START-SEQUENCE-OWNER-PREINSERT-GEOMETRY-R4", self.deployer)
        self.assertIn("k1-control-start-sequence-owner-v1.cfg.before", self.deployer)
        self.assertIn("Invoke-RestartAndRestoreMesh", self.deployer)
        self.assertIn("contact_probing_after_insertion = $false", self.deployer)
        self.assertIn("physical_effect_during_deploy = $false", self.deployer)
        self.assertNotIn("__R4_CONFIG_SHA256__", self.deployer)
        self.assertNotIn("__R4_JINJA_SHA256__", self.deployer)
        self.assertIn("678582e808d74f6b720ef3d6b52dc2c443c7a0652a62c484319e2b22fba7b0bc", self.deployer)
        self.assertNotIn("25291e1534f0ba100d3171b983796089a24cd49fdfcef76817406d325e6d8e03", self.deployer)

    def test_manifest_pins_the_exact_deployment_payload(self):
        for relative_path, expected in self.manifest["payload"].items():
            actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
            self.assertEqual(expected, actual, relative_path)

    def test_physical_and_production_authority_remain_closed(self):
        self.assertFalse(self.contract["physical_run_authorized"])
        self.assertFalse(self.contract["production_authorized"])

    def test_install_is_closed_on_exact_r2_backup_and_exact_r4_payload(self):
        result = self.deployment_result
        self.assertEqual("INSTALLED_VALIDATED_COLD_ZERO_LOGICAL_ROUTE_AFTER_RESTART", result["status"])
        self.assertEqual("installed_R2_exact_not_remote_drift", result["first_preflight"]["classification"])
        self.assertEqual(
            "678582e808d74f6b720ef3d6b52dc2c443c7a0652a62c484319e2b22fba7b0bc",
            result["deployment"]["backup_sha256"],
        )
        self.assertEqual(
            "c7d7dd06ee81092d73cde9e41ba371642340e8f0270154f3cef15e0e98ef9d4e",
            result["deployment"]["installed_sha256"],
        )
        self.assertFalse(result["deployment"]["rollback_used"])

    def test_cold_install_has_no_physical_effect_and_records_route_loss(self):
        deployment = self.deployment_result["deployment"]
        for key in ("heater_action", "motion_action", "extrusion_action", "cfs_action", "print_started"):
            self.assertFalse(deployment[key])
        final = self.deployment_result["final_independent_read"]
        self.assertEqual("standby", final["print_state"])
        self.assertEqual([0.0, 0.0], final["heater_targets_c"])
        self.assertEqual("", final["homed_axes"])
        self.assertEqual("k1_p001_t055_r001_n11x11", final["active_mesh"])
        self.assertEqual([], final["logical_routes"])
        self.assertTrue(self.deployment_result["physical_interpretation"]["physical_filament_position_not_proved_by_telemetry"])


if __name__ == "__main__":
    unittest.main()
