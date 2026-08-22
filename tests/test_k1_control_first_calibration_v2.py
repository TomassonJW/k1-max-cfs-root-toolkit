import importlib.util
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "first-calibration-v2"
AGGREGATOR = PACKAGE / "aggregate_meshes.py"
CONTRACT = PACKAGE / "first-calibration-contract.json"
RUNNER = ROOT / "scripts" / "run-k1-control-first-calibration-v2.ps1"
MANIFEST = PACKAGE / "execution-manifest.json"


def load_aggregator():
    spec = importlib.util.spec_from_file_location("first_calibration_v2_aggregate", AGGREGATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FirstCalibrationV2AggregationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_aggregator()
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    @staticmethod
    def matrix(delta=0.0):
        return [
            [row * 0.01 + column * 0.001 + delta for column in range(6)]
            for row in range(6)
        ]

    def test_contract_fixes_six_measurements_without_extra_rerun(self):
        mesh = self.contract["mesh"]
        self.assertEqual(mesh["measurements"], 6)
        self.assertEqual(mesh["batches"], [[1, 2, 3], [4, 5, 6]])
        self.assertEqual(mesh["estimator"], "pointwise_median")
        self.assertFalse(mesh["qualification"]["automatic_extra_measurement"])
        self.assertIn("automatic_seventh_mesh", self.contract["forbidden"])

    def test_two_stable_median_batches_are_accepted(self):
        matrices = [
            self.matrix(-0.004),
            self.matrix(0.000),
            self.matrix(0.004),
            self.matrix(0.010),
            self.matrix(0.014),
            self.matrix(0.018),
        ]
        result = self.module.aggregate(matrices)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["measurements"], 6)
        self.assertAlmostEqual(result["observed_mm"]["maximum"], 0.014)
        self.assertAlmostEqual(result["candidate_matrix"][0][0], 0.007)

    def test_one_isolated_raw_outlier_does_not_move_a_batch_median(self):
        matrices = [self.matrix() for _ in range(6)]
        matrices[0][2][3] = 3.0
        result = self.module.aggregate(matrices)
        self.assertTrue(result["accepted"])
        self.assertAlmostEqual(result["candidate_matrix"][2][3], 0.023)

    def test_repeatable_batch_shift_is_rejected(self):
        matrices = [self.matrix() for _ in range(3)] + [self.matrix(0.061) for _ in range(3)]
        result = self.module.aggregate(matrices)
        self.assertFalse(result["accepted"])
        self.assertGreater(result["observed_mm"]["maximum"], 0.060)

    def test_exactly_six_finite_6x6_matrices_are_required(self):
        with self.assertRaisesRegex(ValueError, "exactement six"):
            self.module.aggregate([self.matrix()])

    def test_runner_uses_the_fixed_v2_gate_and_six_named_checkpoints(self):
        self.assertIn("$RequiredGate = 'G4-K1-CONTROL-FIRST-CALIBRATION-V2'", self.runner)
        self.assertIn("Mesh6AndQualify", self.runner)
        self.assertNotIn("Mesh7", self.runner)
        self.assertIn("1..6 | ForEach-Object", self.runner)
        self.assertIn("aucun septieme mesh", self.runner)

    def test_candidate_is_loaded_only_after_qualification_then_read_back(self):
        commit_start = self.runner.index("if ($Action -eq 'CommitRobustMesh')")
        commit_block = self.runner[commit_start:]
        self.assertLess(commit_block.index("Assert-QualifiedEvidence"), commit_block.index("Invoke-KlipperMeshUpdate"))
        self.assertIn('"method": "update_mesh"', self.runner)
        self.assertIn("function Wait-TransientMeshUpdate", self.runner)
        self.assertIn("$snapshot.toolhead.homed_axes -eq 'xyz'", self.runner)
        self.assertIn("$snapshot.bed_mesh.profile_name -eq 'K1_TRANSIENT'", self.runner)
        self.assertNotIn("function Wait-TransientMeshRestart", self.runner)
        self.assertIn("Assert-CandidateMatrix -Actual $loaded.bed_mesh.probed_matrix", commit_block)
        self.assertIn("KCTRL_MESH_COMMIT PLATE=1 TEMP_BAND=55", commit_block)

    def test_runner_keeps_backup_rollback_and_no_production_actions(self):
        self.assertIn("first-calibration-v2", self.runner)
        self.assertIn("sha256sum -c checksums.sha256", self.runner)
        self.assertIn("ROLLBACK_FIRST_CALIBRATION_V2_OK", self.runner)
        for token in ("START_PRINT", "BOX_", "G92 E", "G1 E", "EXTRUDE"):
            self.assertNotIn(token, self.runner)

    def test_runner_checks_the_klipper_generated_mesh_header(self):
        generated_header = 'Get-ExactRemoteLineCount -Path $PrinterConfig -Line "#*# [bed_mesh $MeshProfile]"'
        self.assertEqual(self.runner.count(generated_header), 2)
        self.assertNotIn(
            'Get-ExactRemoteLineCount -Path $PrinterConfig -Line "[bed_mesh $MeshProfile]"',
            self.runner,
        )

    def test_manifest_pins_every_executable_artifact(self):
        for artifact in self.manifest["artifacts"]:
            path = ROOT / artifact["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact["sha256"])


if __name__ == "__main__":
    unittest.main()
