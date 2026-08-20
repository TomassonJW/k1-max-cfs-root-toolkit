import configparser
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "overrides" / "g4-zsafe-start"
MACROS = PACKAGE / "zsafe_g4.cfg"
CONTRACT = PACKAGE / "sequence-contract.json"


def macro_body(text: str, name: str) -> str:
    pattern = re.compile(rf"^\[gcode_macro {re.escape(name)}\]\s*$\n(.*?)(?=^\[|\Z)", re.MULTILINE | re.DOTALL)
    match = pattern.search(text)
    if not match:
        raise AssertionError(f"macro not found: {name}")
    return match.group(1)


def assert_in_order(testcase: unittest.TestCase, text: str, tokens: list[str]) -> None:
    positions = [text.index(token) for token in tokens]
    testcase.assertEqual(positions, sorted(positions), tokens)


def simulate(stages: list[dict]) -> set[str]:
    state: set[str] = set()
    for stage in stages:
        missing = set(stage.get("requires", [])) - state
        if missing:
            raise ValueError(f"{stage['id']} missing {sorted(missing)}")
        if stage.get("hazard") and "armed" not in state:
            raise ValueError(f"{stage['id']} reached with closed safety gate")
        state.update(stage.get("sets", []))
    return state


class ZSafeOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = MACROS.read_text(encoding="utf-8")
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_duplicate_section_overlay_replaces_stock_gcode(self) -> None:
        parser = configparser.RawConfigParser(strict=False)
        parser.read_string("[gcode_macro START_PRINT]\nvariable_prepare: 0\ngcode:\n  STOCK\n[gcode_macro START_PRINT]\ngcode:\n  ZSAFE\n")
        self.assertIn("ZSAFE", parser.get("gcode_macro START_PRINT", "gcode"))
        self.assertEqual(parser.get("gcode_macro START_PRINT", "variable_prepare"), "0")

    def test_overlay_is_valid_ini_for_captured_config_parser_mode(self) -> None:
        parser = configparser.RawConfigParser(strict=False, inline_comment_prefixes=(";", "#"))
        parser.read_string(self.text)
        self.assertTrue(parser.has_section("gcode_macro START_PRINT"))
        self.assertTrue(parser.has_section("gcode_macro ZSAFE_END_PRINT"))
        self.assertEqual(
            parser.get("save_variables", "filename"),
            "/usr/data/printer_data/config/zsafe_g4_variables.cfg",
        )

    def test_start_sequence_closes_gate_before_purge(self) -> None:
        body = macro_body(self.text, "START_PRINT")
        assert_in_order(self, body, ["CX_ROUGH_G28", "ZSAFE_FINAL_REFERENCE", "ZSAFE_LOAD_MESH", "ZSAFE_APPLY_CORRECTION", "ZSAFE_ARM_LOW_MOVES", "ZSAFE_SAFE_CFS_AND_PURGE"])

    def test_unsafe_stock_paths_are_absent_from_start_override(self) -> None:
        body = macro_body(self.text, "START_PRINT")
        for token in ("CX_NOZZLE_CLEAR", "CX_PRINT_LEVELING_CALIBRATION", "CHECK_BED_MESH", "BED_MESH_CALIBRATE", "CXSAVE_CONFIG", "Z_OFFSET_APPLY_PROBE"):
            self.assertNotIn(token, body)

    def test_cfs_and_line_purge_each_have_a_runtime_guard(self) -> None:
        cfs = macro_body(self.text, "ZSAFE_SAFE_CFS_AND_PURGE")
        assert_in_order(self, cfs, ["ZSAFE_ASSERT_ARMED", "BOX_START_PRINT", "T{initial_tool}", "BOX_START_PRINT_EXTRUDE_MATERIAL"])
        line = macro_body(self.text, "ZSAFE_DRAW_LINE")
        assert_in_order(self, line, ["ZSAFE_ASSERT_ARMED", "CX_PRINT_DRAW_ONE_LINE"])

    def test_no_cfs_command_runs_before_start_gate(self) -> None:
        body = macro_body(self.text, "START_PRINT")
        prefix = body[: body.index("ZSAFE_ARM_LOW_MOVES")]
        self.assertNotIn("BOX_", prefix)
        self.assertNotRegex(prefix, r"(?m)^\s*T\d+")

    def test_orca_start_has_no_preliminary_homing_or_tool_command(self) -> None:
        lines = [
            line.strip()
            for line in (PACKAGE / "orca-machine-start.gcode").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith(";")
        ]
        self.assertTrue(lines[0].startswith("START_PRINT "))
        self.assertFalse(any(re.fullmatch(r"G28(?:\s.*)?", line) for line in lines))
        self.assertFalse(any(re.fullmatch(r"T\d+", line) for line in lines))
        self.assertIn("Z_CORRECTION=0.27", lines[0])

    def test_rejected_package_fails_closed_if_loaded_by_mistake(self) -> None:
        body = macro_body(self.text, "START_PRINT")
        self.assertIn("was rejected and must never be deployed", body)
        self.assertEqual(self.contract["status"], "rejected_never_deploy")
        self.assertFalse(self.contract["deployment_authorized"])

    def test_end_captures_candidate_before_stock_end(self) -> None:
        body = macro_body(self.text, "ZSAFE_END_PRINT")
        assert_in_order(self, body, ["ZSAFE_CAPTURE_CORRECTION_CANDIDATE", "ZSAFE_DISARM", "END_PRINT"])
        self.assertIn("SAVE_VARIABLE", macro_body(self.text, "ZSAFE_CAPTURE_CORRECTION_CANDIDATE"))

    def test_declared_sequence_simulates_without_open_gate(self) -> None:
        self.assertIn("candidate_saved", simulate(self.contract["stages"]))

    def test_simulator_rejects_purge_before_correction(self) -> None:
        stages = list(self.contract["stages"])
        purge = next(stage for stage in stages if stage["id"] == "stock_line_purge")
        correction_index = next(i for i, stage in enumerate(stages) if stage["id"] == "effective_correction")
        stages.remove(purge)
        stages.insert(correction_index, purge)
        with self.assertRaises(ValueError):
            simulate(stages)

    def test_validation_path_contains_no_extrusion_or_tool_selection(self) -> None:
        body = macro_body(self.text, "ZSAFE_VALIDATE_HIGH")
        self.assertIn("G1 Z30", body)
        self.assertNotRegex(body, r"(?m)^\s*G1\s+E")
        self.assertNotRegex(body, r"(?m)^\s*T\d+")
        self.assertNotIn("BOX_START_PRINT_EXTRUDE_MATERIAL", body)


if __name__ == "__main__":
    unittest.main()
