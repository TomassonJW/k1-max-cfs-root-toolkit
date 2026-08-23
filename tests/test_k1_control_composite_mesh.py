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
    layouts = (
        (list(range(0, 11, 2)), list(range(0, 11, 2))),
        (list(range(1, 11, 2)), list(range(0, 11, 2))),
        (list(range(0, 11, 2)), list(range(1, 11, 2))),
        (list(range(1, 11, 2)), list(range(1, 11, 2))),
    )
    return {
        "target": {
            "x_count": 11,
            "y_count": 11,
            "mesh_min": [5, 5],
            "mesh_max": [295, 295],
        },
        "passes": [
            {
                "context": _context(),
                "x_indices": xs,
                "y_indices": ys,
                "matrix": [[_value(y, x) for x in xs] for y in ys],
            }
            for xs, ys in layouts
        ],
    }


class CompositeMeshTests(unittest.TestCase):
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
        result = MODULE.compose(_document())
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


if __name__ == "__main__":
    unittest.main()
