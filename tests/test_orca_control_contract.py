import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORCA = ROOT / "orca" / "k1-control-v1"
FIXTURES = ROOT / "tests" / "fixtures" / "k1-control-v1"


class OrcaControlContractTests(unittest.TestCase):
    def test_expanded_contract_commands_survive_the_exact_creality_parser(self) -> None:
        parser = re.compile(r"([A-Z_]+|[A-Z*/])")
        names = []
        for fixture in FIXTURES.glob("orca-*-expanded.gcode"):
            text = fixture.read_text(encoding="utf-8")
            names.extend(re.findall(r"^(KCTRL_[A-Z_]+)\b", text, re.MULTILINE))
        self.assertGreaterEqual(len(names), 5)
        for name in names:
            parts = parser.split(name.upper())
            parsed = parts[1] + parts[2].strip() if len(parts) >= 3 else ""
            self.assertEqual(parsed, name, f"Creality parser truncates {name} to {parsed}")

    def test_three_fields_and_printer_contract_are_an_atomic_cutover(self) -> None:
        contract = json.loads((ORCA / "contract.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["status"], "offline_candidate_never_import")
        self.assertFalse(contract["printer_mutation_authorized"])
        self.assertFalse(contract["current_profile_changed"])
        self.assertTrue(contract["legacy_z_postprocessor_still_active"])
        self.assertEqual(
            set(contract["atomic_cutover"]),
            {
                "machine_start_gcode",
                "machine_end_gcode",
                "change_filament_gcode",
                "printer_side_contract",
                "legacy_z_postprocessor_removal",
            },
        )

    def test_start_has_no_direct_homing_tool_or_temperature_command(self) -> None:
        start = (ORCA / "machine-start.gcode").read_text(encoding="utf-8")
        executable = [line for line in start.splitlines() if line and not line.startswith(";")]
        self.assertTrue(executable[-1].endswith("KCTRL_JOB_START CONTRACT=1"))
        for forbidden in (r"^G28\b", r"^T\d+\b", r"^M10[49]\b", r"START_PRINT"):
            self.assertFalse(any(re.search(forbidden, line) for line in executable), forbidden)
        self.assertEqual(start.count("KCTRL_JOB_TOOL_TARGET"), 8)
        self.assertIn("first_layer_print_min", start)
        self.assertIn("first_layer_print_max", start)

    def test_tool_change_wraps_the_stock_cfs_boundary_with_dynamic_targets(self) -> None:
        change = (ORCA / "change-filament.gcode").read_text(encoding="utf-8")
        self.assertLess(change.index("KCTRL_TOOL_CHANGE_BEGIN"), change.index("T{next_extruder}"))
        self.assertLess(change.index("T{next_extruder}"), change.index("KCTRL_TOOL_CHANGE_END"))
        self.assertIn("NEXT_TARGET={new_filament_temp}", change)
        fixture = (FIXTURES / "orca-toolchange-expanded.gcode").read_text(encoding="utf-8")
        self.assertIn("PREVIOUS=0 NEXT=5", fixture)
        self.assertIn("NEXT_TARGET=235", fixture)

    def test_end_never_commits_or_resets_z(self) -> None:
        end = (ORCA / "machine-end.gcode").read_text(encoding="utf-8")
        self.assertIn("KCTRL_JOB_END CONTRACT=1", end)
        self.assertNotIn("SAVE_CONFIG", end)
        self.assertNotIn("Z_OFFSET_APPLY_PROBE", end)
        self.assertNotIn("SET_GCODE_OFFSET", end)


if __name__ == "__main__":
    unittest.main()
