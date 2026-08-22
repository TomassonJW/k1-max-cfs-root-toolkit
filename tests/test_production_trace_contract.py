from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "scripts" / "start-passive-production-trace.ps1"


class ProductionTraceContractTests(unittest.TestCase):
    def test_trace_subscribes_to_cfs_transition_fields_without_private_inventory(self):
        source = TRACE.read_text(encoding="utf-8")
        self.assertIn(
            '"box": ["state", "t_command", "auto_refill", "filament_useup", "filament"]',
            source,
        )
        self.assertNotIn('"same_material"', source)
        self.assertNotIn('"T1"', source)
        self.assertNotIn('"T2"', source)

    def test_trace_remains_read_only(self):
        source = TRACE.read_text(encoding="utf-8")
        for forbidden in (
            "/printer/gcode/script",
            "KCTRL_JOB_START",
            "START_PRINT EXTRUDER_TEMP",
            "M104 S",
            "M109 S",
            "BED_MESH_CALIBRATE",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
