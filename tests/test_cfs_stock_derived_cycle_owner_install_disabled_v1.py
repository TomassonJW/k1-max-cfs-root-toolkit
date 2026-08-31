from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-stock-derived-cycle-owner-install-disabled-v1"


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "stock_cycle_install_disabled_runner",
        PACKAGE / "run_scenarios.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CfsStockDerivedCycleOwnerInstallDisabledV1Tests(unittest.TestCase):
    def test_all_scenarios_are_green(self):
        result = load_runner().run()
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["passed"], result["total"])
        self.assertEqual(result["total"], 17)
        self.assertFalse(result["printer_transport"])
        self.assertFalse(result["physical_action"])

    def test_disabled_entries_read_no_arguments_and_send_no_commands(self):
        runner = load_runner()
        owner, printer = runner.make_owner(enabled=False)
        entries = (
            owner.cmd_CUT_UNLOAD,
            owner.cmd_LOAD_PURGE,
            owner.cmd_PRIME,
            owner.cmd_REFILL_GUARD,
            owner.cmd_END,
        )
        for entry in entries:
            gcmd = runner.FakeGcmd(forbid_reads=True)
            runner.expect_error(
                lambda entry=entry, gcmd=gcmd: entry(gcmd),
                "stock_derived_cycle_disabled",
            )
            self.assertEqual(gcmd.read_count, 0)
        self.assertEqual(printer.gcode.scripts, [])

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
            "CFS_STOCK_DERIVED_CYCLE_OWNER_INSTALL_DISABLED_V1_OK",
        )
        self.assertEqual(result["scenarios"], "17/17")
        self.assertTrue(result["uncertain_effect_retry_blocked"])
        self.assertTrue(result["equivalent_refill_preserved"])
        self.assertFalse(result["printer_connection"])
        self.assertFalse(result["physical_action"])


if __name__ == "__main__":
    unittest.main()
