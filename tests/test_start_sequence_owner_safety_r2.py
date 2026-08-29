from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "start-sequence-owner-safety-r2"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class StartSequenceOwnerSafetyR2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.verifier = load_module("start_owner_safety_r2_verifier", PACKAGE / "verify_candidate.py")

    def test_candidate_uses_the_normal_stock_edge_out_and_back_geometry(self):
        result = self.verifier.verify()
        self.assertEqual("START_SEQUENCE_OWNER_SAFETY_R2_CANDIDATE_OK", result["status"])
        self.assertEqual([0.1, 20.0, 0.3], result["purge_outbound_start_mm"])
        self.assertEqual([0.1, 180.0, 0.3], result["purge_outbound_end_mm"])
        self.assertEqual([0.4, 180.0, 0.3], result["purge_return_start_mm"])
        self.assertEqual([0.4, 20.0, 0.3], result["purge_return_end_mm"])
        self.assertEqual(3000, result["purge_feedrate_mm_min"])
        self.assertTrue(result["stock_reference_verified"])
        self.assertEqual(0.3, self.contract["purge_correction"]["x_offset_mm"])
        self.assertEqual(20.0, self.contract["purge_correction"]["extrusion_total_mm"])

    def test_safe_end_lowers_and_parks_before_releasing_axes(self):
        lines = self.verifier.verify()["safe_end"]
        self.assertLess(lines.index("G1 Z50 F600"), lines.index("G1 X203 Y273 F1200"))
        self.assertLess(lines.index("G1 X203 Y273 F1200"), lines.index("M400"))
        self.assertEqual("M84", lines[-1])
        self.assertFalse(any(line.startswith("G28") for line in lines))

    def test_completed_cold_install_does_not_authorize_a_human_run(self):
        manifest = json.loads((PACKAGE / "deployment-manifest.json").read_text(encoding="utf-8"))
        deployer = ROOT / "scripts" / "deploy-k1-control-start-sequence-owner-safety-r2.ps1"
        self.assertFalse(self.contract["deployment_authorized"])
        self.assertFalse(self.contract["printer_connection_authorized"])
        self.assertFalse(self.contract["physical_run_authorized"])
        self.assertTrue(self.contract["purge_correction"]["human_physical_qualification_required"])
        self.assertFalse(self.contract["automatic_retry"])
        self.assertEqual("INSTALLED_VALIDATED_COLD_ZERO_ROUTE", manifest["status"])
        self.assertTrue(manifest["deployment_completed"])
        self.assertTrue(manifest["authorization_consumed"])
        self.assertFalse(manifest["deployment_authorized"])
        self.assertFalse(manifest["physical_trial_authorized"])
        self.assertFalse(manifest["planned_change"]["printer_cfg_change"])
        self.assertEqual(
            manifest["payload"]["scripts/deploy-k1-control-start-sequence-owner-safety-r2.ps1"],
            hashlib.sha256(deployer.read_bytes()).hexdigest(),
        )

    def test_recovery_finished_but_uncertain_effect_was_never_retried(self):
        evidence = json.loads((PACKAGE / "recovery-evidence.json").read_text(encoding="utf-8"))
        recovery = evidence["recovery"]
        self.assertIn("NO_RETRY", recovery["http_result"])
        self.assertEqual("BLOCKED_BEFORE_EFFECT", recovery["continuation"]["status"])
        self.assertTrue(recovery["final_two_read_only_snapshots"]["stable"])
        self.assertEqual([203.0, 273.0, 50.23], recovery["final_two_read_only_snapshots"]["physical_position_mm"])
        self.assertTrue(evidence["unsafe_thermal_gcode"]["removed_after_exact_hash_check"])
        self.assertFalse(evidence["automatic_retry"])

    def test_first_deploy_attempt_is_truthfully_rolled_back_and_requires_new_go(self):
        attempt = json.loads((PACKAGE / "deployment-attempt.json").read_text(encoding="utf-8"))
        self.assertEqual("ROLLED_BACK_SAFE_BLOCKED_NO_LOGICAL_ROUTE", attempt["status"])
        self.assertTrue(attempt["rollback"]["v1_file_restored"])
        self.assertTrue(attempt["final_two_read_only_snapshots"]["stable"])
        self.assertEqual("NONE", attempt["final_two_read_only_snapshots"]["logical_route"])
        self.assertFalse(attempt["final_two_read_only_snapshots"]["physical_filament_position_inferred"])
        self.assertFalse(attempt["effects"]["heating"])
        self.assertFalse(attempt["effects"]["motion"])
        self.assertFalse(attempt["effects"]["extrusion"])
        self.assertFalse(attempt["effects"]["cfs_command"])
        self.assertTrue(attempt["deployer_correction"]["renewed_exact_go_required"])

    def test_second_deploy_is_installed_cold_without_claiming_a_physical_purge(self):
        result = json.loads((PACKAGE / "deployment-result.json").read_text(encoding="utf-8"))
        manifest = json.loads((PACKAGE / "deployment-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("INSTALLED_VALIDATED_COLD_ZERO_ROUTE", result["status"])
        self.assertEqual("8abbed2", result["authorized_commit"])
        self.assertTrue(result["deployment"]["backup_verified"])
        self.assertTrue(result["deployment"]["restart_transition_observed"])
        self.assertEqual(1, result["deployment"]["mesh_restore_command_count"])
        self.assertEqual("PASS", result["validation"]["deployment_validation"])
        self.assertEqual("PASS", result["validation"]["independent_validation"])
        self.assertEqual("NONE", result["validation"]["final_logical_route"])
        self.assertFalse(result["effects"]["heating"])
        self.assertFalse(result["effects"]["motion"])
        self.assertFalse(result["effects"]["extrusion"])
        self.assertFalse(result["effects"]["cfs_command"])
        self.assertFalse(result["effects"]["physical_purge"])
        self.assertTrue(manifest["deployment_completed"])
        self.assertTrue(manifest["authorization_consumed"])
        self.assertFalse(manifest["deployment_candidate"])
        self.assertFalse(manifest["physical_trial_authorized"])


if __name__ == "__main__":
    unittest.main()
