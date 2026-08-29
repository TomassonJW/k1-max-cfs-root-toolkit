import ast
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "long-checkpoint-job-v1"


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = load_module("long_checkpoint_job_v1_builder_test", PACKAGE / "build_candidate.py")


class LongCheckpointJobV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = builder.SOURCE.read_bytes()
        cls.candidate = builder.derive(cls.source)
        cls.text = cls.candidate.decode("utf-8")
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))

    def test_contract_pins_source_and_candidate(self):
        self.assertEqual(builder.SOURCE_SHA256, self.contract["source"]["sha256"])
        self.assertEqual(builder.digest(self.candidate), self.contract["candidate"]["sha256"])
        self.assertEqual(len(self.candidate), self.contract["candidate"]["bytes"])
        self.assertFalse(self.contract["deployment_candidate"])
        self.assertFalse(any(self.contract["effects_of_this_package"].values()))

    def test_eight_monotonic_layers_and_two_distinct_windows(self):
        self.assertEqual(8, self.text.count(";LAYER_CHANGE"))
        self.assertEqual(
            ["0.2", "0.4", "0.6", "0.8", "1", "1.2", "1.4", "1.6"],
            [line.split(":", 1)[1] for line in self.text.splitlines() if line.startswith(";Z:")],
        )
        tool = self.text.index(";KCTRL_CHECKPOINT_WINDOW TOOL_CHANGE_T1A_TO_T2C")
        runout = self.text.index(";KCTRL_CHECKPOINT_WINDOW RUNOUT_T2_EQUIVALENT")
        self.assertLess(tool, runout)

    def test_no_automatic_tool_or_stock_lifecycle_command_is_executable(self):
        executable = builder.executable_lines(self.candidate)
        self.assertFalse(any(re.fullmatch(r"T\d+", line) for line in executable))
        for forbidden in ("START_PRINT", "END_PRINT", "G28", "BOX_"):
            self.assertFalse(any(forbidden in line for line in executable))
        self.assertFalse(any(line.startswith("M73 ") for line in executable))

    def test_owned_start_and_safe_end_are_unique_and_ordered(self):
        result = builder.validate(self.candidate)
        self.assertEqual("LONG_CHECKPOINT_JOB_V1_CANDIDATE_OK", result["status"])
        executable = builder.executable_lines(self.candidate)
        self.assertEqual(1, executable.count(builder.START_MACRO))
        self.assertLess(executable.index("TURN_OFF_HEATERS"), executable.index("G1 Z50 F600"))
        self.assertLess(executable.index("G1 Z50 F600"), executable.index("G1 X203 Y273 F1200"))
        self.assertLess(executable.index("G1 X203 Y273 F1200"), executable.index("M84"))

    def test_source_or_candidate_drift_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "source_gcode_hash_drift"):
            builder.derive(self.source + b"\n")
        damaged = self.candidate.replace(b";KCTRL_CHECKPOINT_WINDOW RUNOUT_T2_EQUIVALENT", b";missing", 1)
        with self.assertRaisesRegex(ValueError, "runout_marker_missing_or_duplicate"):
            builder.validate(damaged)

    def test_builder_parses_as_python_3_8(self):
        ast.parse(
            (PACKAGE / "build_candidate.py").read_text(encoding="utf-8"),
            filename="build_candidate.py",
            feature_version=(3, 8),
        )


if __name__ == "__main__":
    unittest.main()
