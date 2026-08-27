import ast
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "clean-motion-v1"


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


collector = load_module(
    "clean_motion_geometry_read_only_test",
    PACKAGE / "remote_geometry_read_only.py",
)
checkpoint = load_module(
    "clean_motion_checkpoint_c_test",
    PACKAGE / "remote_checkpoint_c.py",
)


class CleanMotionV1ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.form = json.loads((PACKAGE / "human-observation-form.json").read_text(encoding="utf-8"))

    def test_gate_is_not_deployable_and_contains_only_checkpoint_c_commands(self):
        self.assertEqual(
            "checkpoint_c_technical_ok_awaiting_human_verdict",
            self.contract["status"],
        )
        self.assertFalse(self.contract["deployment_candidate"])
        self.assertTrue(self.contract["read_only_connection_qualified"])
        self.assertTrue(self.contract["printer_effect_connection"])
        self.assertEqual([], self.contract["remote_commands"])
        self.assertEqual(checkpoint.CHECKPOINT_SCRIPT.split("\n"), self.contract["gcode_commands"])
        self.assertEqual([], self.contract["service_actions"])

    def test_read_only_evidence_is_pinned_and_keeps_software_geometry_distinct(self):
        evidence = json.loads((PACKAGE / "evidence-map.json").read_text(encoding="utf-8"))
        private_capture = ROOT / evidence["private_source"]["path"]
        self.assertTrue(private_capture.is_file())
        import hashlib

        self.assertEqual(
            evidence["private_source"]["sha256"],
            hashlib.sha256(private_capture.read_bytes()).hexdigest(),
        )
        collector_path = ROOT / evidence["collector"]["path"]
        self.assertEqual(
            evidence["collector"]["sha256"],
            hashlib.sha256(collector_path.read_bytes()).hexdigest(),
        )
        geometry = self.contract["read_only_facts"]["stock_declared_cleaning_zone_mm"]
        self.assertEqual(68.0, geometry["x_start"])
        self.assertEqual(94.0, geometry["x_end"])
        self.assertIn(
            "brush_left_right_front_back_bounds_observed_by_human",
            self.contract["physical_facts_required_before_approach_commands"],
        )

    def test_best_current_11x11_is_the_hard_prerequisite(self):
        prerequisites = self.contract["prerequisites"]
        self.assertEqual(
            "G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-V1",
            prerequisites["best_current_mesh_restore_gate"],
        )
        self.assertEqual("RESTORE_OK", prerequisites["best_current_mesh_restore_required_status"])
        self.assertTrue(prerequisites["best_current_mesh_restore_satisfied"])
        self.assertEqual("k1_p001_t055_r001_n11x11", prerequisites["required_active_profile"])
        self.assertFalse("robust_mesh_activation_gate" in prerequisites)

    def test_physical_geometry_is_explicitly_missing(self):
        required = set(self.contract["physical_facts_required_before_approach_commands"])
        self.assertIn("brush_left_right_front_back_bounds_observed_by_human", required)
        self.assertIn("checkpoint_c_safe_clearance_human_positive", required)
        self.assertIn("first_contact_z_observed_at_cold_slow_speed", required)
        self.assertTrue(all(value is None for value in self.form["observed_geometry_mm"].values()))
        self.assertEqual("CHECKPOINT_C_TECHNICAL_OK_AWAITING_HUMAN_VERDICT", self.form["status"])
        self.assertTrue(self.form["operator_present"])
        self.assertTrue(self.form["plate_clear"])
        self.assertTrue(self.form["brush_installed_and_visible"])
        self.assertTrue(self.form["immediate_stop_available"])

    def test_every_effect_phase_requires_or_follows_human_checkpoints(self):
        phases = self.contract["phases"]
        self.assertEqual(
            [
                "A_READ_ONLY_BASELINE",
                "B_HUMAN_STATIC_OBSERVATION",
                "C_COLD_REFERENCE_AND_HIGH_CLEARANCE",
                "D_SLOW_APPROACH_CHECKPOINTS",
                "E_COLD_DRY_TRAJECTORY",
                "F_SAFE_RETURN_AND_FINAL_READ",
            ],
            [phase["id"] for phase in phases],
        )
        self.assertFalse(phases[0]["effect"])
        self.assertFalse(phases[1]["effect"])
        self.assertTrue(phases[2]["human_confirmation_before_effect"])
        self.assertTrue(phases[3]["human_confirmation_before_each_checkpoint"])
        self.assertTrue(phases[4]["human_confirmation_before_effect"])

    def test_forbidden_effects_and_terminal_stop_conditions_are_explicit(self):
        forbidden = self.contract["forbidden"]
        for name in (
            "heating",
            "extrusion",
            "cfs_action",
            "probing_brush_with_prtouch",
            "mesh_measurement",
            "z_offset_write",
            "configuration_write",
            "service_restart",
            "automatic_retry",
            "unobserved_motion",
        ):
            self.assertTrue(forbidden[name])
        self.assertIn("state_or_position_becomes_ambiguous", self.contract["stop_conditions"])

    def test_read_only_collector_exports_summaries_not_full_macro_source(self):
        source = (PACKAGE / "remote_geometry_read_only.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="remote_geometry_read_only.py", feature_version=(3, 8))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertNotIn("socket", imported)
        self.assertNotIn("subprocess", imported)
        self.assertIn('Request(BASE_URL + path, method="GET")', source)
        self.assertNotIn("gcode/script", source)
        builtin_open_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "open"
        ]
        self.assertEqual([], builtin_open_calls)

    def test_motion_summary_keeps_literals_and_hash_but_not_source_line(self):
        source = "G1 X10.5 Y-2 F600\nG1 X{brush_x} Z3\nM104 S0"
        summary = collector.motion_line_summaries(source)
        self.assertEqual(2, len(summary))
        self.assertEqual({"X": 10.5, "Y": -2.0, "F": 600.0}, summary[0]["literal_values"])
        self.assertFalse(summary[0]["contains_template"])
        self.assertTrue(summary[1]["contains_template"])
        self.assertNotIn("source", summary[0])
        self.assertNotIn("line", summary[0])

    def test_discovery_filter_is_bounded_to_cleaning_and_reference_names(self):
        selected = [
            name
            for name in (
                "gcode_macro nozzle_clear",
                "gcode_macro accurate_g28",
                "prtouch_v2",
                "gcode_macro unrelated_secret",
            )
            if collector.DISCOVERY_PATTERN.search(name)
        ]
        self.assertEqual(
            ["gcode_macro nozzle_clear", "gcode_macro accurate_g28", "prtouch_v2"],
            selected,
        )

    def test_cleaning_settings_keep_only_reviewed_geometry_and_speed_fields(self):
        settings = {
            "prtouch_v2": {
                "clr_noz_start_x": 10.0,
                "clr_noz_len_x": 30.0,
                "g29_speed": 5.0,
                "private_unrelated_value": "excluded",
            },
            "other": {"private_unrelated_value": "excluded"},
        }
        selected = collector.selected_cleaning_settings(settings)
        self.assertEqual(
            {
                "prtouch_v2": {
                    "clr_noz_start_x": 10.0,
                    "clr_noz_len_x": 30.0,
                    "g29_speed": 5.0,
                }
            },
            selected,
        )

    def test_powershell_runner_streams_stdin_and_has_no_effect_route(self):
        source = (PACKAGE / "capture_geometry_sources_read_only.ps1").read_text(encoding="utf-8")
        self.assertIn("$RemoteProgram | & ssh.exe", source)
        self.assertIn("http_methods = @('GET')", source)
        self.assertNotIn("scp.exe", source)
        self.assertNotIn("-Execute", source)
        self.assertNotIn("-Gate", source)

    def test_checkpoint_c_is_one_bounded_cold_script(self):
        self.assertEqual(
            [
                "G28",
                "BED_MESH_PROFILE LOAD=k1_p001_t055_r001_n11x11",
                "G90",
                "G1 Z50 F600",
                "M400",
            ],
            checkpoint.CHECKPOINT_SCRIPT.split("\n"),
        )
        upper = checkpoint.CHECKPOINT_SCRIPT.upper()
        for forbidden in ("M104", "M109", "M140", "M190", " E", "BOX_", "BED_MESH_CALIBRATE"):
            self.assertNotIn(forbidden, upper)

    def test_checkpoint_c_compensates_for_stock_g28_mesh_replacement(self):
        lines = checkpoint.CHECKPOINT_SCRIPT.split("\n")
        self.assertLess(lines.index("G28"), lines.index("BED_MESH_PROFILE LOAD=k1_p001_t055_r001_n11x11"))
        self.assertLess(lines.index("BED_MESH_PROFILE LOAD=k1_p001_t055_r001_n11x11"), lines.index("G1 Z50 F600"))

    def test_checkpoint_c_safe_projection_excludes_cfs_identity(self):
        source = (PACKAGE / "remote_checkpoint_c.py").read_text(encoding="utf-8")
        self.assertNotIn('get("sn")', source)
        self.assertNotIn('get("uuid")', source)
        self.assertNotIn("T3,T4", checkpoint.QUERY_PATH)

    def test_checkpoint_c_runner_requires_exact_gate_and_reviewed_hash(self):
        source = (PACKAGE / "run_checkpoint_c.ps1").read_text(encoding="utf-8")
        self.assertIn("G4-K1-CONTROL-CLEAN-MOTION-V1", source)
        self.assertIn("-Execute", source)
        self.assertIn("ExpectedProgramSha256", source)
        self.assertNotIn("scp.exe", source)

    def test_checkpoint_c_validation_separates_commanded_and_mesh_compensated_z(self):
        snapshot = {
            "server": {"klippy_state": "ready", "failed_components": [], "warnings": []},
            "print": {"state": "standby", "filename_present": False},
            "heaters": {"extruder_target": 0.0, "bed_target": 0.0},
            "toolhead": {
                "homed_axes": "xyz",
                "position": [156.657, 142.271, 50.23, 0.0],
                "gcode_position": [156.657, 142.271, 50.0, 0.0],
            },
            "bed_mesh": {
                "profile_name": checkpoint.BEST_CURRENT_PROFILE,
                "probed_matrix": {"rows": 11, "columns": [11] * 11, "sha256": checkpoint.BEST_CURRENT_SHA256},
                "best_current_profile": {"rows": 11, "columns": [11] * 11, "sha256": checkpoint.BEST_CURRENT_SHA256},
            },
            "box": {
                "state": "connect",
                "t_command": "",
                "T1": {"state": "connect", "filament": "None"},
                "T2": {"state": "connect", "filament": "None"},
            },
            "runtime": {
                "ready": 1,
                "session_active": 0,
                "accepted_z_valid": 1,
                "accepted_z_offset": -0.04,
                "low_moves_armed": 0,
            },
            "store": {"integrity": "ok"},
            "calibration_path": {"phase": "idle", "motion_armed": 0, "commit_ready": 0},
            "hashes": checkpoint.EXPECTED_HASHES,
        }
        checkpoint.validate_after(snapshot)

    def test_checkpoint_c_evidence_pins_false_ko_and_corrected_validation(self):
        evidence = json.loads((PACKAGE / "evidence-map.json").read_text(encoding="utf-8"))
        checkpoint_evidence = evidence["checkpoint_c"]
        self.assertEqual(
            "false_ko_validator_used_mesh_compensated_physical_z",
            checkpoint_evidence["run"]["interpretation"],
        )
        self.assertEqual(
            "CHECKPOINT_C_TECHNICAL_OK_AWAITING_HUMAN_VERDICT",
            checkpoint_evidence["corrected_read_only_validation"]["status"],
        )
        self.assertIsNone(checkpoint_evidence["human_verdict"])


if __name__ == "__main__":
    unittest.main()
