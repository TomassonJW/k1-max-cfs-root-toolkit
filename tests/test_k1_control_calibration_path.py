import ast
import hashlib
import json
import pathlib
import re
import shlex
import unittest

try:
    import jinja2
except ModuleNotFoundError:
    jinja2 = None


ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "calibration-path-v1"
CFG = PACKAGE / "k1-control-calibration-path.cfg"
MANIFEST = PACKAGE / "deployment-manifest.json"
CONTRACT = PACKAGE / "calibration-path-contract.json"
DEPLOYER = ROOT / "scripts" / "deploy-k1-control-calibration-path-v1.ps1"


def macro_body(text: str, name: str) -> str:
    match = re.search(
        rf"^\[gcode_macro {re.escape(name)}\]\n(?P<body>.*?)(?=^\[|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise AssertionError(f"macro absent: {name}")
    return match.group("body")


class CalibrationPathRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = CFG.read_text(encoding="utf-8")

    def test_package_is_fail_closed_and_has_no_production_or_heat_path(self) -> None:
        self.assertIn("OFFLINE CANDIDATE - DO NOT DEPLOY", self.text)
        for forbidden in (
            "[gcode_macro START_PRINT]",
            "M104",
            "M109",
            "M140",
            "M190",
            "BOX_",
            "G1 E",
            "SAVE_CONFIG",
            "Z_OFFSET_APPLY_PROBE",
            "0.27",
        ):
            self.assertNotIn(forbidden, self.text)

    def test_only_four_macros_contain_xyz_motion(self) -> None:
        names = re.findall(r"^\[gcode_macro ([A-Z_]+)\]$", self.text, re.MULTILINE)
        moving = {name for name in names if re.search(r"^  G1 (?:X|Y|Z)", macro_body(self.text, name), re.MULTILINE)}
        self.assertEqual(
            moving,
            {
                "KCTRL_CAL_PATH_BEGIN",
                "KCTRL_CAL_PATH_MOVE",
                "KCTRL_CAL_PATH_ADJUST",
                "KCTRL_CAL_PATH_PARK",
            },
        )
        self.assertNotIn("G1", macro_body(self.text, "KCTRL_CAL_PATH_ASSERT_ARMED"))

    def test_every_command_name_survives_the_exact_creality_parser(self) -> None:
        parser = re.compile(r"([A-Z_]+|[A-Z*/])")
        names = re.findall(r"^\[gcode_macro ([A-Z0-9_]+)\]$", self.text, re.MULTILINE)
        self.assertGreaterEqual(len(names), 10)
        for name in names:
            parts = parser.split(name.upper())
            parsed = parts[1] + parts[2].strip() if len(parts) >= 3 else ""
            self.assertEqual(parsed, name, f"Creality parser truncates {name} to {parsed}")

    def test_text_variables_survive_creality_shlex_and_literal_eval(self) -> None:
        assignments = re.findall(r"^  +SET_GCODE_VARIABLE (?P<args>.+)$", self.text, re.MULTILINE)
        checked = 0
        for args in assignments:
            if " VARIABLE=phase " not in f" {args} " and " VARIABLE=mesh_profile " not in f" {args} ":
                continue
            rendered = args.replace("{profile}", "k1_p001_t060_r001_n11x11")
            params = dict(token.split("=", 1) for token in shlex.split(rendered))
            value = ast.literal_eval(params["VALUE"])
            self.assertIsInstance(value, str, rendered)
            checked += 1
        self.assertGreaterEqual(checked, 10)

    @unittest.skipUnless(jinja2, "Jinja2 absent du Python local; validation exacte requise avant GO")
    def test_every_template_parses_with_creality_delimiters(self) -> None:
        environment = jinja2.Environment("{%", "%}", "{", "}")
        bodies = re.findall(r"^gcode:\n((?:^  .*\n?)*)", self.text, flags=re.MULTILINE)
        self.assertGreaterEqual(len(bodies), 10)
        for body in bodies:
            environment.parse(body)

    def test_descent_is_bounded_and_cannot_skip_a_reviewed_step(self) -> None:
        body = macro_body(self.text, "KCTRL_CAL_PATH_MOVE")
        self.assertIn("[5.0,2.0,1.0,0.5,0.3,0.2,0.15,0.1]", body)
        for current, minimum in (
            ("5.0", "2.0"),
            ("2.0", "1.0"),
            ("1.0", "0.5"),
            ("0.5", "0.3"),
            ("0.3", "0.2"),
            ("0.2", "0.15"),
            ("0.15", "0.1"),
        ):
            self.assertIn(f"current == {current} and height < {minimum}", body)
        self.assertIn("G1 Z{height} F120", body)

    def test_z_adjust_confirm_commit_and_cancel_require_the_safe_path(self) -> None:
        begin = macro_body(self.text, "KCTRL_CAL_PATH_BEGIN")
        adjust = macro_body(self.text, "KCTRL_CAL_PATH_ADJUST")
        confirm = macro_body(self.text, "KCTRL_CAL_PATH_CONFIRM_GAP")
        park = macro_body(self.text, "KCTRL_CAL_PATH_PARK")
        commit = macro_body(self.text, "KCTRL_CAL_PATH_COMMIT_Z")
        cancel = macro_body(self.text, "KCTRL_CAL_PATH_CANCEL_Z")
        self.assertIn("CLEAR_PLATE", begin)
        self.assertIn("CLEAN_NOZZLE", begin)
        self.assertIn("current_height_mm|float != 0.1", adjust)
        self.assertIn("KCTRL_Z_ADJUST", adjust)
        self.assertIn("G1 Z0.1 F60", adjust)
        self.assertIn('printer.print_stats.state|string != "standby"', adjust)
        self.assertIn("printer.bed_mesh.profile_name", adjust)
        self.assertIn("expected_bed_c", adjust)
        self.assertIn("expected_nozzle_c", adjust)
        self.assertIn("CONFIRMED", confirm)
        self.assertIn("commit_ready VALUE=1", confirm)
        self.assertIn("G1 Z5.0 F600", park)
        self.assertIn('phase|string != "parked_confirmed"', commit)
        self.assertIn("KCTRL_Z_COMMIT", commit)
        self.assertIn("park before cancelling", cancel)
        self.assertIn("KCTRL_Z_CANCEL", cancel)

    def test_z_session_identity_is_bound_to_the_qualified_mesh(self) -> None:
        load = macro_body(self.text, "KCTRL_CAL_PATH_LOAD_MESH")
        verify = macro_body(self.text, "KCTRL_CAL_PATH_VERIFY_MESH")
        start = macro_body(self.text, "KCTRL_CAL_PATH_START_Z")
        for parameter in ("PLATE", "TEMP_BAND", "PROBE_REV", "X_COUNT", "Y_COUNT"):
            self.assertIn(f"{parameter}=", load)
        self.assertIn("profile != expected_profile", verify)
        for variable in ("plate_id", "temperature_band_c", "probe_revision", "x_count", "y_count"):
            self.assertIn(f"VARIABLE={variable}", verify)
        self.assertIn("plate != path.plate_id|int", start)
        self.assertIn("temp != path.temperature_band_c|int", start)
        self.assertIn("probe != path.probe_revision|int", start)


class CalibrationPathPackageTests(unittest.TestCase):
    def test_manifest_pins_exact_source_and_current_runtime(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        source_hash = hashlib.sha256(CFG.read_bytes()).hexdigest()
        self.assertEqual(manifest["package"], "G4-K1-CONTROL-CALIBRATION-PATH-V1")
        self.assertFalse(manifest["printer_mutation_authorized"])
        self.assertEqual(manifest["files"][0]["sha256"], source_hash)
        self.assertEqual(
            manifest["baseline"]["printer_cfg_sha256"],
            "a484e8d802d0ba1a1331ea2060ecc339bd2d1a607e3a0f9bbcca976c66709c6a",
        )
        self.assertEqual(
            manifest["baseline"]["z_mesh_runtime_config_sha256"],
            "dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113",
        )
        self.assertEqual(
            manifest["printer_cfg"]["after_sha256"],
            "0d59dd656844c3198ee43a81056b06830dbe60779d558b71aaa8c28fa708d9ee",
        )

    def test_contract_has_no_hidden_z_and_defines_console_free_ui(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertFalse(contract["printer_mutation_authorized"])
        self.assertIsNone(contract["z_adjustment"]["numeric_default_mm"])
        self.assertFalse(contract["daily_ui"]["console_required"])
        self.assertEqual(contract["approach"]["height_ladder_mm"][-1], 0.1)
        self.assertIn("commit_or_cancel_before_park", contract["forbidden"])

    def test_deployer_is_exactly_gated_and_never_starts_calibration(self) -> None:
        text = DEPLOYER.read_text(encoding="utf-8")
        self.assertIn("$RequiredGate = 'G4-K1-CONTROL-CALIBRATION-PATH-V1'", text)
        self.assertIn("if (-not $Execute -or $Gate -cne $RequiredGate)", text)
        self.assertIn("[string]$Action = 'Plan'", text)
        self.assertIn("KCTRL_CAL_PATH_ASSERT_ARMED", text)
        self.assertIn("function Assert-ExactRemoteJinjaSyntax", text)
        self.assertIn("environment.parse(body)", text)
        for forbidden in (
            "KCTRL_CALIBRATION_PREHEAT'",
            "KCTRL_CALIBRATION_HOME'",
            "KCTRL_MESH_CALIBRATE'",
            "KCTRL_CAL_PATH_LOAD_MESH'",
            "KCTRL_CAL_PATH_START_Z'",
            "KCTRL_CAL_PATH_BEGIN'",
            "KCTRL_CAL_PATH_MOVE'",
            "KCTRL_CAL_PATH_ADJUST'",
            "KCTRL_CAL_PATH_CONFIRM_GAP'",
            "KCTRL_CAL_PATH_PARK'",
            "KCTRL_CAL_PATH_COMMIT_Z'",
        ):
            self.assertNotIn(forbidden, text)

    def test_deployer_pins_manifest_hashes(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        text = DEPLOYER.read_text(encoding="utf-8")
        self.assertIn(manifest["baseline"]["printer_cfg_sha256"], text)
        self.assertIn(manifest["printer_cfg"]["after_sha256"], text)
        self.assertIn(manifest["files"][0]["sha256"], text)
        self.assertIn(manifest["baseline"]["z_mesh_runtime_config_sha256"], text)
        self.assertIn(manifest["baseline"]["z_mesh_runtime_module_sha256"], text)

    def test_backup_precedes_the_first_remote_runtime_mutation(self) -> None:
        text = DEPLOYER.read_text(encoding="utf-8")
        backup = text.index("cp '$PrinterConfig' '$remoteBackup/printer.cfg.before'")
        checksum = text.index("sha256sum -c checksums.sha256", backup)
        mutation_flag = text.index("$MutationStarted = $true", checksum)
        install = text.index("'$CalibrationConfig.next'", mutation_flag)
        self.assertLess(backup, checksum)
        self.assertLess(checksum, mutation_flag)
        self.assertLess(mutation_flag, install)

    def test_remote_jinja_parse_uses_stdin_and_runs_before_mutation(self) -> None:
        text = DEPLOYER.read_text(encoding="utf-8")
        self.assertIn(
            "/usr/share/klippy-env/bin/python - '$configPayload'",
            text,
        )
        preflight = text.index("Assert-ExactRemoteJinjaSyntax")
        mutation_flag = text.index("$MutationStarted = $true")
        self.assertLess(preflight, mutation_flag)

    def test_validation_proves_fail_closed_without_physical_change(self) -> None:
        text = DEPLOYER.read_text(encoding="utf-8")
        self.assertIn("$response = Invoke-KlipperScript 'KCTRL_CAL_PATH_ASSERT_ARMED'", text)
        for field in (
            "extruder.target",
            "heater_bed.target",
            "toolhead.position",
            "gcode_move.homing_origin",
        ):
            self.assertIn(field, text)
        self.assertIn("Assert-NoPhysicalChange -Before $before -After $after", text)

    def test_rollback_removes_only_the_new_overlay_and_preserves_runtime(self) -> None:
        text = DEPLOYER.read_text(encoding="utf-8")
        rollback = text[text.index("function Invoke-CalibrationPathRollback") :]
        self.assertIn("rm -f '$CalibrationConfig'", rollback)
        for preserved in ("$RuntimeConfig", "$RuntimeModule", "$RuntimeState"):
            self.assertNotIn(f"rm -f '{preserved}'", rollback)
        self.assertIn("Assert-RuntimeBaseline $snapshot", rollback)


if __name__ == "__main__":
    unittest.main()
