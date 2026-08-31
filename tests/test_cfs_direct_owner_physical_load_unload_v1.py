import ast
from contextlib import redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
import io
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-direct-owner-physical-load-unload-v1"


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CfsDirectOwnerPhysicalLoadUnloadV1Tests(unittest.TestCase):
    def test_contract_keeps_the_scope_narrow(self):
        contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        self.assertEqual("CLOSED_KO_BEFORE_FILAMENT_EFFECT", contract["status"])
        authority = contract["authority"]
        self.assertTrue(authority["T1A_load_once"])
        self.assertTrue(authority["T1A_final_unload_once"])
        self.assertFalse(authority["automatic_retry"])
        self.assertFalse(authority["printing"])
        self.assertFalse(authority["probe"])
        self.assertFalse(authority["mesh_calibration"])
        self.assertFalse(authority["axis_motion"])
        correction = contract["product_contract_correction"]
        self.assertTrue(correction["cutter_position_and_cut_before_any_unload"])
        self.assertTrue(correction["purge_in_bin_after_every_load"])
        self.assertEqual("3_to_4", correction["purge_release_round_trips"])

    def test_historical_active_configuration_is_now_a_safe_tombstone(self):
        text = (PACKAGE / "k1-control-cfs-direct-owner-active-physical-v1.cfg").read_text(encoding="utf-8")
        self.assertNotIn("enabled: true", text)
        self.assertEqual(1, text.count("enabled: false"))
        self.assertIn("connected_boxes: 1, 2", text)

    def test_remote_program_parses_as_python_38(self):
        text = (PACKAGE / "remote_phase.py").read_text(encoding="utf-8")
        ast.parse(text, filename="remote_phase.py", feature_version=(3, 8))
        self.assertIn("V1_CLOSED_KO = True", text)
        self.assertIn("v1_closed_cutter_and_bin_purge_required", text)

    def test_remote_program_refuses_before_argument_or_socket_use(self):
        module = load_module("closed_direct_physical_v1", PACKAGE / "remote_phase.py")
        output = io.StringIO()
        with redirect_stdout(output):
            code = module.main(["remote_phase.py"])
        self.assertEqual(2, code)
        self.assertIn("v1_closed_cutter_and_bin_purge_required", output.getvalue())

    def test_remote_program_has_only_the_reviewed_effect_surface(self):
        text = (PACKAGE / "remote_phase.py").read_text(encoding="utf-8")
        for required in (
            '"M104 S220"',
            '"TURN_OFF_HEATERS"',
            '"KCTRL_CFS_DIRECT_LOAD ROUTE=T1A EFFECT_ID="',
            '"KCTRL_CFS_DIRECT_UNLOAD ROUTE=T1A EFFECT_ID="',
            '"BOX_ENABLE_AUTO_REFILL ENABLE=0"',
            '"BOX_ENABLE_AUTO_REFILL ENABLE=1"',
        ):
            self.assertIn(required, text)
        for forbidden in ("G28", "BED_MESH_CALIBRATE", "START_PRINT", "RESUME_BASE", "M109"):
            self.assertNotIn(forbidden, text)

    def test_runner_is_hard_closed_and_keeps_historical_rollback(self):
        text = (PACKAGE / "run_gate.ps1").read_text(encoding="utf-8")
        self.assertIn("Assert-Authority", text)
        self.assertIn("Invoke-DeactivateInternal", text)
        self.assertIn("Restart-And-RestoreMesh", text)
        self.assertIn("scp.exe '-O'", text)
        self.assertIn("V1 close KO et rendue non executable", text)
        self.assertIn("cutter avant retrait", text)
        self.assertIn("purge bac", text)

    def test_offline_matrix_is_green(self):
        namespace = {}
        exec((PACKAGE / "run_scenarios.py").read_text(encoding="utf-8"), namespace)
        results = namespace["run"]()
        self.assertEqual(15, len(results))
        self.assertTrue(all(item["status"] == "OK" for item in results))


if __name__ == "__main__":
    unittest.main()
