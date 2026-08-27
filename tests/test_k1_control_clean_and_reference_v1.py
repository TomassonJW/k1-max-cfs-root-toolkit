from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
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


class CleanAndReferenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.recipe = load_recipe_module()

    def test_candidate_has_no_printer_effect(self) -> None:
        self.assertEqual("OFFLINE_CANDIDATE_BLOCKED_MATERIAL_RECIPE", self.contract["status"])
        self.assertFalse(any(self.contract["effects"].values()))

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


if __name__ == "__main__":
    unittest.main()
