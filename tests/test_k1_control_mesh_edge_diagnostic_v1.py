from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "mesh-edge-diagnostic-v1"


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, PACKAGE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MeshEdgeDiagnosticV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare = load_module("mesh_edge_prepare", "prepare_diagnostic.py")
        cls.config = load_module("mesh_edge_config", "build_candidate_config.py")

    def test_pattern_has_121_cells_and_stays_inside_bounds(self):
        strokes = self.prepare.diagnostic_strokes()
        self.assertEqual(len(strokes), 3 + 121 + 9)
        for stroke in strokes:
            for x, y in stroke:
                self.assertGreaterEqual(x, 5)
                self.assertLessEqual(x, 295)
                self.assertGreaterEqual(y, 5)
                self.assertLessEqual(y, 295)

    def test_variants_share_geometry_and_forbid_global_z(self):
        source, source_geometry, source_filament = self.prepare.render_pattern_gcode("source")
        corrected, corrected_geometry, corrected_filament = self.prepare.render_pattern_gcode("corrected")
        self.assertEqual(source_geometry, corrected_geometry)
        self.assertEqual(source_filament, corrected_filament)
        for payload in (source, corrected):
            self.assertNotIn(b"SET_GCODE_OFFSET", payload)
            self.assertEqual(payload.count(b"KCTRL_PRODUCTION_ASSERT_ARMED"), 1)
            self.assertNotIn(b"START_PRINT", payload)
            self.assertNotIn(b"END_PRINT", payload)
            self.assertNotIn(b"PAUSE", payload)
            self.assertNotIn(b"RESUME", payload)
            self.assertNotIn(b"T0", payload)
            self.assertIn(b"G1 Z5 F600\nG1 X150 Y295 F12000", payload)
            self.assertNotIn(b"G1 E-0.8 F2700\nG1 Z5", payload)
        source_commands = [line for line in source.splitlines() if line and not line.startswith(b";")]
        corrected_commands = [line for line in corrected.splitlines() if line and not line.startswith(b";")]
        self.assertEqual(source_commands, corrected_commands)

    def test_prepare_files_home_and_arm_without_heating_or_extruding(self):
        source = self.prepare.render_prepare_gcode("source")
        corrected = self.prepare.render_prepare_gcode("corrected")
        for payload in (source, corrected):
            commands = [line for line in payload.splitlines() if line and not line.startswith(b";")]
            self.assertIn(b"G28", payload)
            self.assertIn(b"X_COUNT=11 Y_COUNT=11", payload)
            self.assertFalse(any(line.startswith((b"G0 ", b"G1 ")) and b" E" in line for line in commands))
            self.assertNotIn(b"M104", payload)
            self.assertNotIn(b"M109", payload)
            self.assertNotIn(b"START_PRINT", payload)
            self.assertNotIn(b"T0", payload)
        self.assertNotIn(self.prepare.DERIVED_PROFILE.encode(), source)
        self.assertEqual(corrected.count(self.prepare.DERIVED_PROFILE.encode()), 2)

    def test_profile_changes_only_requested_cell_before_normalization(self):
        document, block = self.prepare.build_profile_artifacts()
        requested = document["matrices_mm"]["requested_delta"]
        non_zero = [
            (row, column, value)
            for row, values in enumerate(requested)
            for column, value in enumerate(values)
            if float(value) != 0.0
        ]
        self.assertEqual(non_zero, [(9, 1, "0.010000")])
        self.assertFalse(document["global_z"]["included"])
        self.assertIn("#*# [bed_mesh k1_p001_t055_r001_n11x11_tuned_v001]", block)

    def test_real_source_hash_is_pinned(self):
        contract = json.loads((PACKAGE / "diagnostic-contract.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["source_gcode"]["sha256"], self.prepare.SOURCE_GCODE_SHA256)
        self.assertEqual(contract["correction"]["x_mm"], 34)
        self.assertEqual(contract["correction"]["y_mm"], 266)
        self.assertIsNone(contract["source_gcode"]["logical_tool"])
        self.assertEqual(
            contract["source_gcode"]["tool_resolution"],
            "fresh_cfs_state_and_job_contract",
        )
        self.assertTrue(contract["source_gcode"]["hardcoded_physical_tool_forbidden"])
        self.assertTrue(contract["physical_rules"]["fresh_visible_purge_flow_required_before_each_variant"])
        self.assertTrue(contract["physical_rules"]["sensor_only_flow_proof_forbidden"])
        self.assertTrue(contract["rollback"]["completed"])
        self.assertEqual(
            contract["rollback"]["capture_id"],
            "20260826-090956-mesh-edge-diagnostic-v1",
        )
        self.assertFalse(contract["rollback"]["new_pattern_started"])

    def test_result_records_exact_rollback_and_final_validation(self):
        result = (PACKAGE / "RESULT.md").read_text(encoding="utf-8")
        self.assertIn("WAIT_COMPLETE_MESH_EDGE_DIAGNOSTIC_V1_OK", result)
        self.assertIn("ROLLBACK_MESH_EDGE_DIAGNOSTIC_V1_OK", result)
        self.assertIn("VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK", result)
        self.assertIn("Aucun homing, mouvement, chauffage, extrusion", result)
        self.assertIn("quatre G-code temporaires absents", result)

    def test_prepare_rejects_wrong_source_hash(self):
        with self.assertRaisesRegex(ValueError, "empreinte revue"):
            self.prepare._validate_source_gcode(b"not reviewed", "0" * 64)

    def test_candidate_config_is_append_only_and_rejects_unknown_base(self):
        _, block = self.prepare.build_profile_artifacts()
        base = (
            "[printer]\n"
            "#*# <---------------------- SAVE_CONFIG ---------------------->\n"
            "#*# DO NOT EDIT THIS BLOCK OR BELOW. The contents are auto-generated.\n"
            "#*# [bed_mesh k1_p001_t055_r001_n06x06]\n"
            "#*# points =\n"
            "#*# [bed_mesh k1_p001_t055_r001_n11x11]\n"
            "#*# points =\n"
        ).encode()
        digest = hashlib.sha256(base).hexdigest()
        original = set(self.config.ALLOWED_BASELINE_SHA256)
        self.config.ALLOWED_BASELINE_SHA256.add(digest)
        try:
            candidate = self.config.build_candidate(base, block.encode(), digest)
        finally:
            self.config.ALLOWED_BASELINE_SHA256 = original
        self.assertTrue(candidate.startswith(base.rstrip() + b"\n#*#\n"))
        appended = candidate[len(base.rstrip() + b"\n") :].decode().splitlines()
        self.assertTrue(all(line.startswith("#*#") for line in appended))
        self.assertEqual(candidate.count(self.prepare.DERIVED_PROFILE.encode()), 1)
        with self.assertRaisesRegex(ValueError, "empreinte de base revue"):
            self.config.build_candidate(base, block.encode(), "0" * 64)

    def test_prepare_writes_deterministic_private_artifacts(self):
        source = (
            "; total layer number: 1\n"
            "; max_z_height: 0.20\n"
            "G28\nT0\nSTART_PRINT EXTRUDER_TEMP=190 BED_TEMP=55\n"
            "; post_process = \n; z_offset = 0\n"
            "; first_layer_bed_temperature = 55\n"
            "; first_layer_temperature = 190\n"
            "; first_layer_height = 0.200\nEND_PRINT\n"
        ).encode()
        digest = hashlib.sha256(source).hexdigest()
        original = self.prepare.SOURCE_GCODE_SHA256
        self.prepare.SOURCE_GCODE_SHA256 = digest
        try:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source_path = root / "source.gcode"
                source_path.write_bytes(source)
                manifest = self.prepare.prepare_artifacts(source_path, root / "out-a")
                second = self.prepare.prepare_artifacts(source_path, root / "out-b")
                self.assertEqual(manifest["pattern"]["grid_cells"], 121)
                self.assertEqual(len(manifest["files"]), 6)
                self.assertEqual(manifest, second)
                output = root / "out-a" / manifest["files"]["source_pattern_gcode"]["name"]
                self.assertEqual(
                    manifest["files"]["source_pattern_gcode"]["sha256"],
                    hashlib.sha256(output.read_bytes()).hexdigest(),
                )
                for entry in manifest["files"].values():
                    self.assertEqual(
                        (root / "out-a" / entry["name"]).read_bytes(),
                        (root / "out-b" / entry["name"]).read_bytes(),
                    )
        finally:
            self.prepare.SOURCE_GCODE_SHA256 = original

    def test_runner_keeps_preparation_and_pattern_separate(self):
        script = (ROOT / "scripts" / "run-k1-control-mesh-edge-diagnostic-v1.ps1").read_text(encoding="utf-8")
        self.assertIn("'PrepareSource'", script)
        self.assertIn("'CheckPrepared'", script)
        self.assertIn("'PrintSource'", script)
        self.assertIn("Wait-PrintFileComplete", script)
        self.assertIn("state -ceq 'complete'", script)
        self.assertIn("AllowCompletedDiagnostic", script)
        self.assertIn("$patternNames -contains", script)
        self.assertIn("Invoke-RecoverPrepared", script)
        self.assertIn("gcode_move.homing_origin[2]", script)
        self.assertNotIn("gcode_move.homing_origin.z", script)
        self.assertIn("Assert-PhysicalFacts", script)
        self.assertIn("FilamentRouteConfirmed", script)
        self.assertIn("PurgeFlowConfirmed", script)
        self.assertIn("Assert-PhysicalFacts -RequireFilamentFlow", script)
        self.assertIn("sans supposer T0", script)
        self.assertIn("/tmp/klippy_uds", script)
        self.assertIn("'RecoverRobust'", script)
        self.assertNotIn("printer/gcode/script?script=", script)
        self.assertNotIn("'CheckPaused'", script)
        self.assertNotIn("'Resume'", script)


if __name__ == "__main__":
    unittest.main()
