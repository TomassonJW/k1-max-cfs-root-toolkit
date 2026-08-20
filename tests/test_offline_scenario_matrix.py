import json
import unittest
from pathlib import Path

from prototype.scenario_matrix import PRODUCT_CONTRACT, run_matrix


class OfflineScenarioMatrixTests(unittest.TestCase):
    def test_every_required_scenario_is_executed_and_green(self) -> None:
        contract = json.loads(PRODUCT_CONTRACT.read_text(encoding="utf-8"))
        expected = [item["id"] for item in contract["required_offline_scenarios"]]
        results = run_matrix()
        self.assertEqual([result.id for result in results], expected)
        self.assertEqual(len(results), 17)
        self.assertTrue(all(result.passed for result in results), results)

    def test_matrix_contains_real_cross_cfs_and_rollback_evidence(self) -> None:
        results = {result.id: result for result in run_matrix()}
        self.assertIn("T0 to T5", results["cfs_cross_unit_change"].detail)
        self.assertIn("SHA-256", results["deployment_slice_rollback"].detail)
        self.assertIn("early purge blocked", results["safe_start_sequence"].detail)


if __name__ == "__main__":
    unittest.main()
