from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "packages"
    / "k1-control-v1"
    / "cfs-stock-derived-orchestrator-offline-v1"
)


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "stock_derived_orchestrator_offline_test_runner",
        PACKAGE / "run_scenarios.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CfsStockDerivedOrchestratorOfflineV1Tests(unittest.TestCase):
    def test_all_scenarios_are_green(self):
        result = load_runner().run()
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["passed"], 19)
        self.assertEqual(result["total"], 19)
        self.assertFalse(result["printer_transport"])
        self.assertFalse(result["physical_action"])
        self.assertFalse(result["deployment_candidate"])

    def test_equivalent_refill_uses_exactly_one_strict_match(self):
        runner = load_runner()
        owner = runner.prepare_printing()
        context = runner.pause_context()
        ticket = owner.plan_equivalent_refill(context)
        self.assertIn("FROM=T1A TO=T2D", ticket["command"])
        self.assertIn("CANDIDATES=1 PAUSE_LATCHED=1", ticket["command"])
        self.assertNotIn("BOX_", ticket["command"])

    def test_claimed_effect_is_persisted_and_not_replayed(self):
        runner = load_runner()
        owner = runner.prepare_printing()
        ticket = owner.plan_tool_change("T1B")
        persisted = owner.snapshot()
        with self.assertRaisesRegex(
            runner.MODULE.OrchestratorError,
            "claimed_ticket_recovered_without_outcome",
        ):
            runner.MODULE.StockDerivedOrchestrator(
                runner.job(), runner.inventory(), persisted
            )
        self.assertEqual(ticket["attempt_count"], 1)
        self.assertEqual(ticket["automatic_retry_count"], 0)

    def test_candidate_verifier(self):
        completed = subprocess.run(
            [sys.executable, str(PACKAGE / "verify_candidate.py")],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(
            result["status"],
            "CFS_STOCK_DERIVED_ORCHESTRATOR_OFFLINE_V1_OK",
        )
        self.assertEqual(result["scenarios"], "19/19")
        self.assertTrue(result["strict_identical_spare_required"])
        self.assertFalse(result["deployment_candidate"])


if __name__ == "__main__":
    unittest.main()
