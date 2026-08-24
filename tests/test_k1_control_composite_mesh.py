import ast
import importlib.util
import json
import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "packages" / "k1-control-v1" / "composite-mesh-v1" / "compose_mesh.py"
)
SPEC = importlib.util.spec_from_file_location("compose_mesh", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

PROFILE_MODULE_PATH = MODULE_PATH.with_name("render_profile.py")
PROFILE_SPEC = importlib.util.spec_from_file_location("render_profile", PROFILE_MODULE_PATH)
PROFILE_MODULE = importlib.util.module_from_spec(PROFILE_SPEC)
assert PROFILE_SPEC.loader is not None
PROFILE_SPEC.loader.exec_module(PROFILE_MODULE)


def _context():
    return {
        "session_id": "synthetic-session",
        "plate_id": "PEI_TEXTURED_A",
        "bed_target_c": 55,
        "nozzle_target_c": 140,
        "homing_epoch": "home-1",
        "klipper_restart_count": 0,
    }


def _value(y, x):
    return round(0.003 * x * x - 0.002 * y + 0.0005 * x * y, 6)


def _document():
    return {
        "target": {
            "x_count": 11,
            "y_count": 11,
            "mesh_min": [5, 5],
            "mesh_max": [295, 295],
        },
        "passes": [
            {
                "name": layout["name"],
                "context": _context(),
                "x_indices": list(layout["x_indices"]),
                "y_indices": list(layout["y_indices"]),
                "mesh_min": list(layout["mesh_min"]),
                "mesh_max": list(layout["mesh_max"]),
                "probe_count": list(layout["probe_count"]),
                "algorithm": layout["algorithm"],
                "matrix": [
                    [_value(y, x) for x in layout["x_indices"]]
                    for y in layout["y_indices"]
                ],
            }
            for layout in MODULE.EXPECTED_11X11_LAYOUTS
        ],
    }


def _printer_config():
    return (
        b"[include helper.cfg]\n"
        b"[bed_mesh]\n"
        b"probe_count: 6,6\n\n"
        b"#*# <---------------------- SAVE_CONFIG ---------------------->\n"
        b"#*# DO NOT EDIT THIS BLOCK OR BELOW. The contents are auto-generated.\n"
        b"#*#\n"
        b"#*# [bed_mesh k1_p001_t055_r001_n06x06]\n"
        b"#*# version = 1\n"
        b"#*# points =\n"
        b"#*# \t0, 0, 0, 0, 0, 0\n"
        b"#*# \t0, 0, 0, 0, 0, 0\n"
        b"#*# \t0, 0, 0, 0, 0, 0\n"
        b"#*# \t0, 0, 0, 0, 0, 0\n"
        b"#*# \t0, 0, 0, 0, 0, 0\n"
        b"#*# \t0, 0, 0, 0, 0, 0\n"
    )


class CompositeMeshTests(unittest.TestCase):
    def test_sources_parse_with_python_38_grammar(self):
        for path in (MODULE_PATH, PROFILE_MODULE_PATH):
            ast.parse(
                path.read_text(encoding="utf-8"),
                filename=path.name,
                feature_version=(3, 8),
            )

    def test_contract_keeps_the_composite_path_offline_and_bounded(self):
        contract_path = MODULE_PATH.with_name("composite-mesh-contract.json")
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(contract["status"], "offline_prototype_only")
        self.assertFalse(contract["printer_mutation_authorized"])
        self.assertEqual(contract["target"]["physical_points"], 121)
        self.assertEqual(
            max(item["physical_points"] for item in contract["bounded_passes"]),
            36,
        )
        self.assertFalse(contract["hard_guards"]["prtouch_version_change"])
        self.assertFalse(contract["hard_guards"]["remove_factory_hold_tables"])

    def test_four_bounded_passes_rebuild_exact_11_by_11_surface(self):
        result = MODULE.compose_11x11(_document())
        self.assertTrue(result["accepted"])
        self.assertEqual(result["pass_count"], 4)
        self.assertEqual(result["physical_points"], 121)
        self.assertEqual(result["maximum_contacts_per_pass"], 36)
        self.assertEqual(result["mesh_params"]["algo"], "bicubic")
        expected = [[_value(y, x) for x in range(11)] for y in range(11)]
        self.assertEqual(result["candidate_matrix"], expected)

    def test_rejects_more_than_36_contacts_in_one_pass(self):
        document = _document()
        document["passes"][0]["x_indices"] = list(range(7))
        document["passes"][0]["matrix"] = [
            [_value(y, x) for x in range(7)]
            for y in document["passes"][0]["y_indices"]
        ]
        with self.assertRaisesRegex(ValueError, "dépassent la limite de 36"):
            MODULE.compose(document)

    def test_rejects_different_physical_session(self):
        document = _document()
        document["passes"][2]["context"]["homing_epoch"] = "home-2"
        with self.assertRaisesRegex(ValueError, "même session physique"):
            MODULE.compose(document)

    def test_rejects_klipper_restart_between_subgrids(self):
        document = _document()
        document["passes"][1]["context"]["klipper_restart_count"] = 1
        with self.assertRaisesRegex(ValueError, "aucun redémarrage Klipper"):
            MODULE.compose(document)

    def test_rejects_duplicate_and_therefore_missing_position(self):
        document = _document()
        document["passes"][3]["x_indices"][0] = 0
        with self.assertRaisesRegex(ValueError, "indices uniques|dupliquée"):
            MODULE.compose(document)

    def test_rejects_non_finite_measurement(self):
        document = _document()
        document["passes"][3]["matrix"][0][0] = math.nan
        with self.assertRaisesRegex(ValueError, "valeur finie"):
            MODULE.compose(document)

    def test_strict_recipe_rejects_reordered_or_shifted_partition(self):
        reordered = _document()
        reordered["passes"][0], reordered["passes"][1] = (
            reordered["passes"][1], reordered["passes"][0]
        )
        with self.assertRaisesRegex(ValueError, "recette physique even_even"):
            MODULE.compose_11x11(reordered)

        shifted = _document()
        shifted["passes"][3]["mesh_min"] = [35, 34]
        with self.assertRaisesRegex(ValueError, "recette physique odd_odd"):
            MODULE.compose_11x11(shifted)

    def test_profile_renderer_appends_exact_11x11_block_without_touching_robust(self):
        matrix = MODULE.compose_11x11(_document())["candidate_matrix"]
        source = _printer_config()
        rendered = PROFILE_MODULE.append_profile(source, matrix)
        self.assertTrue(rendered.startswith(source))
        self.assertEqual(
            rendered.count(b"#*# [bed_mesh k1_p001_t055_r001_n06x06]"), 1
        )
        self.assertEqual(
            rendered.count(b"#*# [bed_mesh k1_p001_t055_r001_n11x11]"), 1
        )
        self.assertIn(b"#*# x_count = 11\n#*# y_count = 11", rendered)
        self.assertIn(b"#*# algo = bicubic", rendered)
        block = rendered.split(b"#*# [bed_mesh k1_p001_t055_r001_n11x11]", 1)[1]
        point_rows = [line for line in block.splitlines() if line.startswith(b"#*# \t")]
        self.assertEqual(len(point_rows), 11)
        self.assertTrue(all(len(row.split(b",")) == 11 for row in point_rows))

    def test_profile_renderer_refuses_missing_baseline_existing_target_and_nonfinite(self):
        matrix = MODULE.compose_11x11(_document())["candidate_matrix"]
        with self.assertRaisesRegex(ValueError, "SAVE_CONFIG exact doit être unique"):
            PROFILE_MODULE.append_profile(b"[bed_mesh]\n", matrix)
        existing = PROFILE_MODULE.append_profile(_printer_config(), matrix)
        with self.assertRaisesRegex(ValueError, "existe déjà"):
            PROFILE_MODULE.append_profile(existing, matrix)
        matrix[0][0] = math.inf
        with self.assertRaisesRegex(ValueError, "valeur non finie"):
            PROFILE_MODULE.append_profile(_printer_config(), matrix)


if __name__ == "__main__":
    unittest.main()
