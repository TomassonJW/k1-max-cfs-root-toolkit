import ast
import pathlib
import re
import shlex
import unittest

try:
    import jinja2
except ModuleNotFoundError:
    jinja2 = None


ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = ROOT / "packages" / "k1-control-v1" / "z-mesh-runtime-v1" / "k1-control-z-mesh.cfg"


def macro_body(text: str, name: str) -> str:
    match = re.search(
        rf"^\[gcode_macro {re.escape(name)}\]\n(?P<body>.*?)(?=^\[|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise AssertionError(f"macro absent: {name}")
    return match.group("body")


class K1ControlZMeshRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CFG.read_text(encoding="utf-8")

    def test_candidate_is_fail_closed_and_does_not_replace_start_print(self):
        self.assertIn("OFFLINE CANDIDATE - DO NOT DEPLOY", self.text)
        self.assertNotIn("[gcode_macro START_PRINT]", self.text)
        self.assertNotIn("Z_OFFSET_APPLY_PROBE", self.text)
        self.assertNotIn("CXSAVE_CONFIG", self.text)
        self.assertNotIn("0.27", self.text)

    @unittest.skipUnless(jinja2, "Jinja2 absent du Python local; validation exacte séparée sur l'environnement capturé")
    def test_every_gcode_template_parses_with_the_exact_creality_jinja_delimiters(self):
        environment = jinja2.Environment("{%", "%}", "{", "}")
        bodies = re.findall(r"^gcode:\n((?:^  .*\n?)*)", self.text, flags=re.MULTILINE)
        self.assertGreaterEqual(len(bodies), 15)
        for body in bodies:
            environment.parse(body)

    def test_every_custom_command_name_survives_the_exact_creality_parser(self):
        parser = re.compile(r"([A-Z_]+|[A-Z*/])")
        names = re.findall(r"^\[(?:gcode_macro|delayed_gcode) ([A-Z0-9_]+)\]$", self.text, re.MULTILINE)
        names.append("KCTRL_STATE_SAVE")
        self.assertGreaterEqual(len(names), 15)
        for name in names:
            parts = parser.split(name.upper())
            parsed = parts[1] + parts[2].strip() if len(parts) >= 3 else ""
            self.assertEqual(parsed, name, f"Creality parser truncates {name} to {parsed}")

    def test_every_text_variable_survives_creality_shlex_and_literal_eval(self):
        text_variables = {
            "armed_mesh_profile",
            "block_reason",
            "mesh_mode",
            "store_integrity",
            "temperature_owner",
        }
        assignments = re.findall(r"^  +SET_GCODE_VARIABLE (?P<args>.+)$", self.text, re.MULTILINE)
        checked = 0
        for args in assignments:
            rendered = args.replace("{store.integrity}", "empty").replace("{profile}", "reference_plate")
            params = dict(token.split("=", 1) for token in shlex.split(rendered))
            if params.get("VARIABLE") not in text_variables:
                continue
            value = ast.literal_eval(params["VALUE"])
            self.assertIsInstance(value, str, rendered)
            checked += 1
        self.assertEqual(24, checked)

    def test_persistence_uses_one_atomic_composite_record(self):
        self.assertEqual(self.text.count("KCTRL_STATE_SAVE RECORD="), 3)
        self.assertIn("[k1_control_store]", self.text)
        self.assertNotIn("[save_variables]", self.text)
        self.assertNotIn("SAVE_VARIABLE", self.text)
        commit = macro_body(self.text, "KCTRL_Z_COMMIT")
        self.assertLess(commit.index("KCTRL_STATE_SAVE"), commit.index("KCTRL_LOAD_STATE"))
        self.assertIn("old|length != 17", commit)

    def test_empty_store_is_ready_for_calibration_but_remains_fail_closed(self):
        load = macro_body(self.text, "KCTRL_LOAD_STATE")
        empty = load.index('store.integrity|string == "empty"')
        invalid = load.index('store.integrity|string == "invalid"')
        self.assertLess(empty, invalid)
        empty_branch = load[empty:invalid]
        self.assertIn("VARIABLE=ready VALUE=1", empty_branch)
        self.assertIn("VARIABLE=block_reason VALUE='\"no_accepted_z\"'", empty_branch)
        self.assertIn("VARIABLE=accepted_z_valid VALUE=0", empty_branch)
        self.assertIn("VARIABLE=low_moves_armed VALUE=0", empty_branch)

    def test_z_commit_cancel_restore_and_invalidate_are_explicit(self):
        for name in (
            "KCTRL_Z_SESSION_START",
            "KCTRL_Z_ADJUST",
            "KCTRL_Z_COMMIT",
            "KCTRL_Z_CANCEL",
            "KCTRL_Z_RESTORE_PREVIOUS",
            "KCTRL_Z_INVALIDATE",
        ):
            self.assertIn(f"[gcode_macro {name}]", self.text)
        self.assertNotIn("KCTRL_STATE_SAVE", macro_body(self.text, "KCTRL_Z_ADJUST"))
        self.assertNotIn("KCTRL_STATE_SAVE", macro_body(self.text, "KCTRL_Z_CANCEL"))

    def test_mesh_matrix_and_interpolation_are_bounded(self):
        body = macro_body(self.text, "KCTRL_MESH_CALIBRATE")
        self.assertIn("x < 3 or x > 25", body)
        self.assertIn('algorithm == "lagrange" and (x > 6 or y > 6)', body)
        self.assertIn("MESH_MIN=5,5 MESH_MAX=295,295", body)
        self.assertIn("PROBE_COUNT={x},{y}", body)
        self.assertIn("ALGORITHM={algorithm}", body)

    def test_mesh_measurement_and_persistence_are_separate(self):
        calibrate = macro_body(self.text, "KCTRL_MESH_CALIBRATE")
        commit = macro_body(self.text, "KCTRL_MESH_COMMIT")
        self.assertNotIn("SAVE_CONFIG", calibrate)
        self.assertNotIn("BED_MESH_PROFILE SAVE=", calibrate)
        self.assertIn("BED_MESH_PROFILE SAVE=", commit)
        self.assertIn("BED_MESH_PROFILE REMOVE=K1_TRANSIENT", commit)
        self.assertIn("SAVE_CONFIG", commit)
        self.assertLess(commit.index("BED_MESH_PROFILE SAVE="), commit.index("SAVE_CONFIG"))
        self.assertLess(commit.index("BED_MESH_PROFILE REMOVE=K1_TRANSIENT"), commit.index("SAVE_CONFIG"))

    def test_mesh_calibration_refuses_missing_homing(self):
        body = macro_body(self.text, "KCTRL_MESH_CALIBRATE")
        self.assertIn('"xyz" not in printer.toolhead.homed_axes', body)
        self.assertNotIn("G28", body)
        self.assertIn("[gcode_macro KCTRL_CALIBRATION_HOME]", self.text)

    def test_low_move_gate_is_applied_only_after_verification(self):
        arm = macro_body(self.text, "KCTRL_PRODUCTION_ARM")
        verify = macro_body(self.text, "KCTRL_PRODUCTION_VERIFY")
        self.assertIn("VALUE=0", arm)
        self.assertIn("BED_MESH_PROFILE LOAD=", arm)
        self.assertIn("SET_GCODE_OFFSET Z=", arm)
        self.assertIn("KCTRL_PRODUCTION_VERIFY", arm)
        self.assertNotIn("VALUE=1", arm)
        self.assertIn("VARIABLE=low_moves_armed VALUE=1", verify)
        self.assertIn("VARIABLE=armed_mesh_profile", verify)
        final_guard = macro_body(self.text, "KCTRL_PRODUCTION_ASSERT_ARMED")
        self.assertIn("state.armed_mesh_profile", final_guard)

    def test_restore_and_invalidate_are_blocked_during_printing(self):
        restore = macro_body(self.text, "KCTRL_Z_RESTORE_PREVIOUS")
        invalidate = macro_body(self.text, "KCTRL_Z_INVALIDATE")
        self.assertIn('printer.print_stats.state|string != "standby"', restore)
        self.assertIn('"xyz" not in printer.toolhead.homed_axes', restore)
        self.assertIn('printer.print_stats.state|string != "standby"', invalidate)

    def test_no_cfs_extrusion_or_low_motion_exists_in_this_slice(self):
        for forbidden in (
            "BOX_START_PRINT",
            "BOX_START_PRINT_EXTRUDE_MATERIAL",
            "CX_PRINT_DRAW_ONE_LINE",
            "G1 Z",
            "G1 X",
            "G1 Y",
            "G1 E",
        ):
            self.assertNotIn(forbidden, self.text)


if __name__ == "__main__":
    unittest.main()
