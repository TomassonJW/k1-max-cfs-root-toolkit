import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "start-sequence-owner-v1"


def load_verifier():
    spec = importlib.util.spec_from_file_location("start_sequence_owner_v1", PACKAGE / "verify_candidate.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class StartSequenceOwnerV1Tests(unittest.TestCase):
    def test_candidate_is_offline_closed_and_structurally_safe(self):
        result = load_verifier().verify()
        self.assertEqual("START_SEQUENCE_OWNER_V1_OFFLINE_OK", result["status"])
        self.assertEqual(1, result["g28_xy_only"])
        self.assertEqual(1, result["accurate_z_references"])
        self.assertEqual(0, result["automatic_brush_commands"])
        self.assertEqual(0, result["mesh_calibration_commands"])
        self.assertEqual(0, result["cfs_effect_commands"])
        self.assertFalse(result["deployment_candidate"])

    def test_contract_keeps_only_the_proven_t1a_branch(self):
        contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        self.assertEqual("KEEP_CORRECT_T1A", contract["scope"]["supported_branch"])
        self.assertEqual("T1A", contract["scope"]["required_engaged_route"])
        self.assertEqual(1, contract["exact_execution_counts"]["Z_reference_total"])
        self.assertEqual(0, contract["exact_execution_counts"]["BED_MESH_CALIBRATE"])
        self.assertFalse(contract["manual_cleaning"]["automatic_brushing"])
        self.assertFalse(contract["failure_policy"]["fallback_to_stock_start"])

    def test_orca_custom_start_contains_no_stock_or_hidden_offset_command(self):
        content = (PACKAGE / "orca-start.gcode").read_text(encoding="utf-8").strip()
        self.assertTrue(content.startswith("KCTRL_JOB_BEGIN_KEEP_CORRECT_V1 "))
        self.assertNotIn("START_PRINT ", content)
        self.assertNotIn("SET_GCODE_OFFSET", content)
        self.assertNotIn(" T0", content)
        self.assertNotIn(" G28", content)


if __name__ == "__main__":
    unittest.main()
