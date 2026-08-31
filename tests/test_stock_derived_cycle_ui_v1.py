from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "packages/k1-control-v1/stock-derived-cycle-ui-v1/verify_candidate.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location("stock_derived_cycle_ui_v1_verify", VERIFY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class StockDerivedCycleUiV1Tests(unittest.TestCase):
    def test_stock_derived_cycle_ui_candidate(self) -> None:
        self.assertEqual(load_verifier().verify(), [
            "contract_static_only",
            "backend_only_effect_routes",
            "strict_unique_spare_ux",
            "human_and_camera_boundaries",
            "calibration_preserved",
            "manifest_hashes",
        ])
