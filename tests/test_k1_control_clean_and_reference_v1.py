from __future__ import annotations

import importlib.util
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "clean-and-reference-v1"


def load_recipe_module():
    spec = importlib.util.spec_from_file_location("clean_and_reference_recipe", PACKAGE / "recipe.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_inventory_module():
    spec = importlib.util.spec_from_file_location("clean_and_reference_inventory", PACKAGE / "analyze_material_inventory.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_history_module():
    spec = importlib.util.spec_from_file_location("clean_and_reference_history", PACKAGE / "analyze_recent_cfs_history.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CleanAndReferenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.recipe = load_recipe_module()
        cls.inventory = load_inventory_module()
        cls.history = load_history_module()

    def test_live_preflight_has_connection_but_no_physical_effect(self) -> None:
        self.assertEqual("LIVE_PREFLIGHT_OK_BLOCKED_PREVIOUS_MATERIAL_IDENTITY", self.contract["status"])
        self.assertTrue(self.contract["effects"]["printer_connection"])
        physical = dict(self.contract["effects"])
        physical.pop("printer_connection")
        self.assertFalse(any(physical.values()))
        self.assertFalse(self.contract["live_read_only_evidence"]["preflight_capture"]["material_identity_accepted_for_effect"])

    def test_geometry_is_exactly_the_human_qualified_secondary_square(self) -> None:
        geometry = self.contract["source_geometry"]
        self.assertEqual([203.0, 206.0], geometry["x_bounds_mm"])
        self.assertEqual([304.0, 305.0], geometry["y_bounds_mm"])
        self.assertEqual(32.0, geometry["qualified_z_mm"])
        self.assertEqual([203.0, 273.0, 32.0], geometry["safe_approach_and_exit_mm"])

    def test_material_is_mandatory(self) -> None:
        for material in ("", "unknown", "none"):
            with self.assertRaises(self.recipe.RecipeError):
                self.recipe.build_checkpoints(self.recipe.MaterialRecipe(material, 180.0))

    def test_cleaning_target_is_bounded(self) -> None:
        for target in (139.9, 300.1):
            with self.assertRaises(self.recipe.RecipeError):
                self.recipe.build_checkpoints(self.recipe.MaterialRecipe("TEST", target))

    def test_reviewed_candidate_has_no_tool_cfs_or_extrusion(self) -> None:
        scripts = self.recipe.build_checkpoints(self.recipe.MaterialRecipe("TEST", 200.0))
        joined = "\n".join(scripts.values())
        self.assertNotIn("T0", joined)
        self.assertNotIn("BOX_", joined)
        self.assertNotIn("NOZZLE_CLEAR", joined)
        self.assertNotRegex(joined, r"(?m)^G[01].*\bE[-+0-9]")

    def test_exactly_one_final_reference_is_built(self) -> None:
        scripts = self.recipe.build_checkpoints(self.recipe.MaterialRecipe("TEST", 200.0))
        joined = "\n".join(scripts.values())
        self.assertEqual(1, joined.count("ACCURATE_G28"))
        self.assertIn("BED_MESH_PROFILE LOAD=k1_p001_t055_r001_n11x11", scripts["final_reference_once"])
        self.assertIn("TURN_OFF_HEATERS", scripts["final_reference_once"])

    def test_no_wipe_occurs_during_cooling_checkpoint(self) -> None:
        scripts = self.recipe.build_checkpoints(self.recipe.MaterialRecipe("TEST", 200.0))
        cooling = scripts["cool_without_wipe"]
        self.assertNotIn("Y305", cooling)
        self.assertNotIn("X206", cooling)
        self.assertIn("X203 Y273 Z35", cooling)

    def test_two_cleaning_cycles_are_explicit_and_bounded(self) -> None:
        scripts = self.recipe.build_checkpoints(self.recipe.MaterialRecipe("TEST", 200.0))
        self.assertEqual(scripts["hot_clean_once"], scripts["stable_140c_clean_once"])
        self.assertIn("G1 X203 Y273 Z35 F600\nG1 Z32 F300", scripts["hot_clean_once"])
        self.assertEqual(2, scripts["hot_clean_once"].count("G1 X206 F180"))
        self.assertEqual(2, scripts["hot_clean_once"].count("G1 X203 F180"))

    def test_material_capture_exports_only_safe_slot_labels(self) -> None:
        unit = {
            "state": "connect",
            "filament": "None",
            "material_type": ["PLA", "PETG", None, "ABS"],
            "sn": "must-not-leak",
            "uuid": "must-not-leak",
        }
        payload = {"result": {"status": {"box": {"state": "connect", "t_command": "", "T1": unit, "T2": unit}}}}
        block = json.dumps(payload)
        capture = "\n".join(("=== STATE_1_BEGIN ===", block, "=== STATE_1_END ===", "=== STATE_2_BEGIN ===", block, "=== STATE_2_END ==="))
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "capture.txt"
            path.write_text(capture, encoding="utf-8")
            result = self.inventory.analyze_capture(path)
        rendered = json.dumps(result, sort_keys=True)
        self.assertNotIn("must-not-leak", rendered)
        self.assertEqual("PLA", result["inventory"]["units"]["T1"]["materials"]["A"])
        self.assertEqual("EMPTY_OR_UNKNOWN", result["inventory"]["units"]["T1"]["materials"]["C"])
        self.assertFalse(result["previous_nozzle_material_proven"])

    def test_physical_runner_is_human_gated_and_has_no_remote_write(self) -> None:
        runner = (PACKAGE / "run_clean_reference.ps1").read_text(encoding="utf-8")
        for token in (
            "MATERIAL_RECIPE_CONFIRMED",
            "FLOW_FALLS_IN_WASTE_RECEPTACLE_OK",
            "HOT_CLEAN_VISIBLE_OK",
            "COOLING_COMPLETE_NO_WIPE_OK",
            "FINAL_NOZZLE_CLEAN_OK",
            "THERMAL_STOP_REQUIRED",
        ):
            self.assertIn(token, runner)
        self.assertIn("$RemoteProgram | & ssh.exe", runner)
        self.assertIn("remote_file_write = $false", runner)
        self.assertIn("extrusion = $false", runner)
        self.assertIn("cfs_action = $false", runner)
        physical = self.contract["physical_runner"]
        self.assertEqual(sha256(PACKAGE / "remote_clean_reference.py"), physical["remote_program_sha256"])
        self.assertEqual(sha256(PACKAGE / "run_clean_reference.ps1"), physical["runner_sha256"])
        self.assertIn(physical["remote_program_sha256"], runner)

    def test_remote_runner_keeps_exact_bounded_sequence(self) -> None:
        remote = (PACKAGE / "remote_clean_reference.py").read_text(encoding="utf-8")
        self.assertEqual(1, remote.count('"ACCURATE_G28",'))
        self.assertNotIn('"NOZZLE_CLEAR', remote)
        self.assertNotRegex(remote, r'(?m)^\s*"G[01].*\bE[-+0-9]')
        self.assertIn('"G1 X204.5 Y304.5 F600"', remote)
        self.assertIn('"G1 X203 Y273 Z35 F600"', remote)
        self.assertIn('"G1 Z32 F300"', remote)
        self.assertIn('"TURN_OFF_HEATERS"', remote)

    def test_history_analyzer_reports_only_safe_markers(self) -> None:
        digest_lines = "\n".join(
            (
                "a" * 64 + " /config/printer.cfg",
                "b" * 64 + " /config/box.cfg",
                "c" * 64 + " /config/gcode_macro.cfg",
            )
        )
        history = "\n".join(
            (
                "2026-08-27 00:19:43.489 webhooks gcode/script request BOX_QUIT_MATERIAL T1A",
                "2026-08-27 09:38:41.838 EXTRUDE_PROCESS stage T2C",
            )
        )
        capture = "\n".join(
            (
                "=== HASHES_BEFORE_BEGIN ===",
                digest_lines,
                "=== HASHES_BEFORE_END ===",
                "=== CURRENT_STATE_BEGIN ===",
                "{}",
                "=== CURRENT_STATE_END ===",
                "=== CFS_HISTORY_BEGIN ===",
                history,
                "=== CFS_HISTORY_END ===",
                "=== HASHES_AFTER_BEGIN ===",
                digest_lines,
                "=== HASHES_AFTER_END ===",
                "CFS_HISTORY_READ_ONLY_OK",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "history.txt"
            path.write_text(capture, encoding="utf-8")
            result = self.history.analyze(path)
        self.assertEqual(1, result["event_counts_at_or_after_cutoff"]["stock_load"])
        self.assertEqual(1, result["event_counts_at_or_after_cutoff"]["stock_unload"])
        self.assertEqual(["T2C"], result["safe_event_records"][1]["routes_on_line"])
        self.assertFalse(result["identity_fields_exported"])

    def test_live_preflight_is_provisional_and_effect_free(self) -> None:
        preflight = self.contract["live_read_only_evidence"]["preflight_capture"]
        self.assertEqual("PREFLIGHT_OK", preflight["status"])
        self.assertEqual("CFS_TYPE_000001_PROVISIONAL", preflight["material_id"])
        self.assertFalse(preflight["material_identity_accepted_for_effect"])
        self.assertFalse(preflight["gcode"])
        self.assertFalse(preflight["motion"])
        self.assertFalse(preflight["heating"])

    def test_material_history_blocks_inference_from_old_t1a(self) -> None:
        evidence = self.contract["live_read_only_evidence"]
        self.assertFalse(evidence["material_inventory_capture"]["previous_nozzle_material_proven"])
        self.assertTrue(evidence["cfs_history_capture"]["stock_load_marker_after_original_T1A_unload"])
        self.assertFalse(evidence["cfs_history_capture"]["route_for_latest_stock_load_proven"])
        self.assertEqual("HUMAN_CONFIRMATION_REQUIRED", self.contract["only_remaining_pre_effect_fact"]["status"])


if __name__ == "__main__":
    unittest.main()
