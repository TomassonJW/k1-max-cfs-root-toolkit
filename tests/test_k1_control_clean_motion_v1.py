import ast
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
import tempfile
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
checkpoint_d = load_module(
    "clean_motion_checkpoint_d_test",
    PACKAGE / "remote_checkpoint_d.py",
)
brush_trial = load_module(
    "clean_motion_brush_trial_test",
    PACKAGE / "remote_brush_trial.py",
)
manual_capture = load_module(
    "clean_motion_manual_geometry_capture_test",
    PACKAGE / "remote_manual_geometry_capture.py",
)
manual_analysis = load_module(
    "clean_motion_manual_geometry_analysis_test",
    PACKAGE / "analyze_manual_geometry_capture.py",
)


class CleanMotionV1ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.form = json.loads((PACKAGE / "human-observation-form.json").read_text(encoding="utf-8"))

    def test_gate_is_not_deployable_and_records_only_executed_commands(self):
        self.assertEqual(
            "closed_ok_human_qualified_two_brush_cold_motion",
            self.contract["status"],
        )
        self.assertFalse(self.contract["deployment_candidate"])
        self.assertTrue(self.contract["read_only_connection_qualified"])
        self.assertTrue(self.contract["printer_effect_connection"])
        self.assertEqual([], self.contract["remote_commands"])
        self.assertEqual(
            checkpoint.CHECKPOINT_SCRIPT.split("\n")
            + checkpoint_d.CHECKPOINTS["d1"]["script"].split("\n")
            + checkpoint_d.CHECKPOINTS["d2"]["script"].split("\n")
            + checkpoint_d.CHECKPOINTS["d3"]["script"].split("\n")
            + brush_trial.TRIALS["e1"]["script"].split("\n")
            + brush_trial.TRIALS["e2"]["script"].split("\n")
            + [
                "G90",
                "G1 X203 Y273 Z32 F1200",
                "G1 Y303 F600",
                "G1 Y304 F180",
                "G1 X206 F180",
                "G1 Y303 F180",
                "G1 X203 F180",
                "G1 Y273 F600",
                "M400",
            ]
            + brush_trial.TRIALS["e3"]["script"].split("\n")
            + brush_trial.TRIALS["e4"]["script"].split("\n"),
            self.contract["gcode_commands"],
        )
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

    def test_physical_geometry_is_human_qualified_for_both_brushes(self):
        required = set(self.contract["physical_facts_required_before_approach_commands"])
        self.assertIn("brush_left_right_front_back_bounds_observed_by_human", required)
        self.assertIn("checkpoint_c_safe_clearance_human_positive", required)
        self.assertIn("first_contact_z_observed_at_cold_slow_speed", required)
        geometry = self.form["observed_geometry_mm"]
        self.assertEqual(66.0, geometry["brush_x_min"])
        self.assertEqual(99.0, geometry["brush_x_max"])
        self.assertEqual(303.0, geometry["brush_y_min"])
        self.assertEqual(307.0, geometry["brush_y_max"])
        self.assertEqual(2.0, geometry["first_contact_z"])
        self.assertEqual(30.0, geometry["secondary_brush_minimum_safe_z"])
        self.assertEqual(50.0, geometry["safe_clearance_z"])
        self.assertEqual("CLOSED_OK_HUMAN_QUALIFIED_TWO_BRUSH_COLD_MOTION", self.form["status"])
        self.assertEqual("CLEAN_MOTION_V1_OK", self.form["verdict"])
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
        self.assertEqual("CHECKPOINT_C_OK", checkpoint_evidence["human_verdict"])
        self.assertEqual("OK", self.contract["checkpoint_c"]["human_verdict"])
        self.assertFalse(self.contract["checkpoint_c"]["next_motion_blocked_until_human_positive"])

    def test_checkpoint_d_stages_three_high_clearance_positions_without_contact(self):
        self.assertEqual(["d1", "d2", "d3"], sorted(checkpoint_d.CHECKPOINTS))
        self.assertEqual([81.0, 280.0, 50.0], checkpoint_d.CHECKPOINTS["d1"]["after"])
        self.assertEqual([81.0, 300.0, 50.0], checkpoint_d.CHECKPOINTS["d2"]["after"])
        self.assertEqual([81.0, 303.0, 50.0], checkpoint_d.CHECKPOINTS["d3"]["after"])
        self.assertEqual(checkpoint_d.CHECKPOINTS["d1"]["after"], checkpoint_d.CHECKPOINTS["d2"]["before"])
        self.assertEqual(checkpoint_d.CHECKPOINTS["d2"]["after"], checkpoint_d.CHECKPOINTS["d3"]["before"])

    def test_checkpoint_d_scripts_are_cold_xy_only_and_slow_down(self):
        scripts = [checkpoint_d.CHECKPOINTS[name]["script"] for name in ("d1", "d2", "d3")]
        self.assertIn("F1200", scripts[0])
        self.assertIn("F600", scripts[1])
        self.assertIn("F300", scripts[2])
        for source in scripts:
            upper = source.upper()
            self.assertIn("Z50", upper)
            for forbidden in (
                "M104",
                "M109",
                "M140",
                "M190",
                "BOX_",
                "G28",
                "BED_MESH_CALIBRATE",
                " E",
            ):
                self.assertNotIn(forbidden, upper)

    def test_checkpoint_d_projection_excludes_cfs_identity_and_remote_writes(self):
        source = (PACKAGE / "remote_checkpoint_d.py").read_text(encoding="utf-8")
        self.assertNotIn('get("sn")', source)
        self.assertNotIn('get("uuid")', source)
        self.assertNotIn("T3,T4", checkpoint_d.QUERY_PATH)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("scp", source.lower())

    def test_checkpoint_d_runner_requires_exact_gate_and_pinned_source(self):
        source = (PACKAGE / "run_checkpoint_d.ps1").read_text(encoding="utf-8")
        self.assertIn("G4-K1-CONTROL-CLEAN-MOTION-V1", source)
        self.assertIn("-Execute", source)
        self.assertIn("ExpectedProgramSha256", source)
        self.assertIn("D1_OK", source)
        self.assertIn("D2_OK", source)
        self.assertIn("PreviousHumanVerdict", source)
        self.assertNotIn("__PIN_AFTER_REVIEW__", source)

    def test_checkpoint_d_evidence_pins_program_runner_and_private_captures(self):
        import hashlib

        evidence = json.loads((PACKAGE / "evidence-map.json").read_text(encoding="utf-8"))
        checkpoint_evidence = evidence["checkpoint_d"]
        for key in (
            "remote_program",
            "runner",
            "preflight_d1",
            "run_d1",
            "preflight_d2",
            "run_d2",
            "preflight_d3",
            "run_d3",
        ):
            artifact = checkpoint_evidence[key]
            path = ROOT / artifact["path"]
            self.assertTrue(path.is_file(), key)
            self.assertEqual(artifact["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual("D1_OK", checkpoint_evidence["run_d1"]["human_verdict"])
        self.assertFalse(checkpoint_evidence["d2_blocked_until_d1_human_positive"])
        self.assertTrue(checkpoint_evidence["d2_executed"])
        self.assertEqual("D2_OK", checkpoint_evidence["run_d2"]["human_verdict"])
        self.assertFalse(checkpoint_evidence["d3_blocked_until_d2_human_positive"])
        self.assertTrue(checkpoint_evidence["d3_executed"])
        self.assertEqual("D3_OK", checkpoint_evidence["run_d3"]["human_verdict"])
        self.assertFalse(
            checkpoint_evidence["next_entry_or_vertical_approach_blocked_until_d3_human_positive"]
        )

    def test_manual_geometry_capture_is_get_only_and_sanitized(self):
        source = (PACKAGE / "remote_manual_geometry_capture.py").read_text(encoding="utf-8")
        self.assertIn('method="GET"', source)
        self.assertNotIn("gcode/script", source)
        self.assertNotIn("socket.socket", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn('get("sn")', source)
        self.assertNotIn('get("uuid")', source)
        self.assertEqual("k1_p001_t055_r001_n11x11", manual_capture.BEST_PROFILE)

    def test_manual_geometry_capture_runner_requires_operator_and_pins_source(self):
        source = (PACKAGE / "capture_manual_geometry.ps1").read_text(encoding="utf-8")
        self.assertIn("OperatorPresent", source)
        self.assertIn("PlateClear", source)
        self.assertIn("ExpectedProgramSha256", source)
        self.assertIn("codex_motion = $false", source)
        self.assertIn("gcode_sent = $false", source)

    def test_manual_geometry_analysis_detects_long_stable_dwells(self):
        samples = []
        for index in range(10):
            samples.append(
                {
                    "elapsed_s": float(index),
                    "gcode_xyz": [70.0, 304.5, 2.0],
                    "physical_xyz": [70.0, 304.5, 2.2],
                }
            )
        samples.append(
            {
                "elapsed_s": 10.0,
                "gcode_xyz": [94.0, 304.5, 4.0],
                "physical_xyz": [94.0, 304.5, 4.2],
            }
        )
        dwells = manual_analysis.stable_dwells(samples)
        self.assertEqual(1, len(dwells))
        self.assertEqual([70.0, 304.5, 2.0], dwells[0]["gcode_xyz_median"])
        self.assertEqual(9.0, dwells[0]["duration_s"])

    def test_manual_geometry_analysis_reports_short_dwells_and_extrema(self):
        samples = [
            {"elapsed_s": 0.0, "gcode_xyz": [81.0, 303.0, 50.0], "physical_xyz": [81.0, 303.0, 50.2]},
            {"elapsed_s": 1.0, "gcode_xyz": [81.0, 303.0, 50.0], "physical_xyz": [81.0, 303.0, 50.2]},
            {"elapsed_s": 2.0, "gcode_xyz": [66.0, 303.0, 3.0], "physical_xyz": [66.0, 303.0, 2.9]},
            {"elapsed_s": 5.0, "gcode_xyz": [66.0, 303.0, 3.0], "physical_xyz": [66.0, 303.0, 2.9]},
        ]
        records = [
            {"record": "control", "event": "ready"},
            *[{"record": "sample", **sample} for sample in samples],
            {"record": "control", "event": "complete"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.jsonl"
            path.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )
            result = manual_analysis.analyze(path)
        self.assertEqual(2.0, result["first_movement_s"])
        self.assertEqual([66.0, 303.0, 3.0], result["gcode_extrema"]["minimum_xyz"])
        self.assertEqual([81.0, 303.0, 50.0], result["gcode_extrema"]["maximum_xyz"])
        self.assertEqual(1, result["short_dwell_count"])

    def test_manual_geometry_protocol_has_four_ordered_corners_and_safe_lifts(self):
        source = (PACKAGE / "MANUAL-GEOMETRY-PROTOCOL.md").read_text(encoding="utf-8")
        for marker in ("X− / Y−", "X+ / Y−", "X+ / Y+", "X− / Y+"):
            self.assertIn(marker, source)
        self.assertIn("10 secondes", source)
        self.assertIn("2 mm", source)
        self.assertIn("0,1 mm", source)

    def test_qualified_manual_captures_and_brush_candidate_are_hash_pinned(self):
        import hashlib

        evidence = json.loads((PACKAGE / "evidence-map.json").read_text(encoding="utf-8"))
        for section in (
            "manual_geometry_capture_v2_primary_brush",
            "manual_geometry_capture_v1_secondary_purge_brush",
        ):
            artifact = evidence[section]["capture"]
            path = ROOT / artifact["path"]
            self.assertTrue(path.is_file(), section)
            self.assertEqual(artifact["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        for artifact in evidence["brush_trial_candidate"].values():
            if not isinstance(artifact, dict) or "path" not in artifact:
                continue
            path = ROOT / artifact["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(artifact["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_brush_trials_use_only_the_human_observed_geometry(self):
        self.assertEqual(["e1", "e2", "e3", "e4"], sorted(brush_trial.TRIALS))
        self.assertEqual([203.0, 273.0, 32.0], brush_trial.TRIALS["e1"]["before"])
        self.assertEqual([203.0, 273.0, 32.0], brush_trial.TRIALS["e1"]["after"])
        self.assertEqual([81.0, 280.0, 32.0], brush_trial.TRIALS["e2"]["after"])
        self.assertEqual([203.0, 273.0, 32.0], brush_trial.TRIALS["e3"]["before"])
        self.assertEqual([203.0, 273.0, 32.0], brush_trial.TRIALS["e3"]["after"])
        self.assertEqual([203.0, 273.0, 32.0], brush_trial.TRIALS["e4"]["before"])
        self.assertEqual([203.0, 273.0, 32.0], brush_trial.TRIALS["e4"]["after"])

    def test_e1_is_contact_free_and_stops_before_the_secondary_brush(self):
        trial = brush_trial.TRIALS["e1"]
        self.assertEqual("none", trial["brush_contact"])
        self.assertEqual(5.0, trial["minimum_commanded_z_mm"])
        self.assertIn("G1 X66 F300", trial["script"])
        self.assertIn("G1 Y300 F600", trial["script"])
        self.assertNotIn("G1 Y303 F600", trial["script"])

    def test_e2_is_one_primary_contact_and_lifts_before_leaving(self):
        lines = brush_trial.TRIALS["e2"]["script"].split("\n")
        self.assertEqual("primary_bed_brush_once", brush_trial.TRIALS["e2"]["brush_contact"])
        self.assertEqual(2.0, brush_trial.TRIALS["e2"]["minimum_commanded_z_mm"])
        self.assertLess(lines.index("G1 Z2 F120"), lines.index("G1 X66 F300"))
        self.assertLess(lines.index("G1 X66 F300"), lines.index("G1 Z12 F300"))
        self.assertLess(lines.index("G1 Z12 F300"), lines.index("G1 X81 Y280 F600"))

    def test_e3_never_descends_below_secondary_brush_clearance(self):
        trial = brush_trial.TRIALS["e3"]
        self.assertEqual("secondary_purge_bin_brush_out_and_back", trial["brush_contact"])
        self.assertEqual(32.0, trial["minimum_commanded_z_mm"])
        self.assertIn("G1 Y304.5 F600", trial["script"])
        self.assertIn("G1 X206 F180", trial["script"])
        self.assertNotIn("G1 Y303", trial["script"])
        self.assertNotIn(" Z2", trial["script"])
        self.assertNotIn(" Z5", trial["script"])

    def test_brush_trial_source_and_runner_keep_effects_bounded(self):
        source = (PACKAGE / "remote_brush_trial.py").read_text(encoding="utf-8")
        runner = (PACKAGE / "run_brush_trial.ps1").read_text(encoding="utf-8")
        for forbidden in ("M104", "M109", "M140", "M190", "BOX_", "BED_MESH_CALIBRATE", "G28"):
            self.assertNotIn(forbidden, "\n".join(item["script"] for item in brush_trial.TRIALS.values()).upper())
        self.assertNotIn('get("sn")', source)
        self.assertNotIn('get("uuid")', source)
        self.assertNotIn("T3,T4", brush_trial.QUERY_PATH)
        self.assertIn("GEOMETRY_OK", runner)
        self.assertIn("CONTACT_COORDINATES_OK", runner)
        self.assertIn("E2_OK", runner)
        self.assertIn("SQUARE_CYCLE_COORDINATES_OK", runner)
        self.assertIn("OperatorPresent", runner)
        self.assertIn("ImmediateStopAvailable", runner)
        self.assertNotIn("__PIN_AFTER_REVIEW__", runner)

    def test_e4_is_exactly_one_two_lane_square_observation_cycle(self):
        trial = brush_trial.TRIALS["e4"]
        self.assertEqual("secondary_purge_bin_brush_square_cycle_once", trial["brush_contact"])
        self.assertEqual(32.0, trial["minimum_commanded_z_mm"])
        self.assertEqual(
            [
                "G90",
                "G1 X203 Y273 Z32 F1200",
                "G1 Y305 F600",
                "G1 X206 F180",
                "G1 X203 F180",
                "G1 Y304 F180",
                "G1 X206 F180",
                "G1 X203 F180",
                "G1 Y273 F600",
                "M400",
            ],
            trial["script"].split("\n"),
        )


if __name__ == "__main__":
    unittest.main()
