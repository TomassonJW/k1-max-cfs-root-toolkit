from importlib.util import module_from_spec, spec_from_file_location
import ast
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-stock-unload-guard-v1"


def _load(name, filename):
    spec = spec_from_file_location(name, PACKAGE / filename)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


controller = _load("cfs_stock_unload_guard_controller", "controller.py")
fake_api = _load("cfs_stock_unload_guard_fake_api", "fake_api.py")
scenario_runner = _load("cfs_stock_unload_guard_scenarios", "run_scenarios.py")


BASE = {
    "print_state": "standby",
    "box_state": "connect",
    "connected_cfs_units": ["T1", "T2"],
    "active_cfs_command": "",
    "engaged_routes": ["T1A"],
    "stock_unload_state": "idle",
    "extruder_target_c": 0,
    "bed_target_c": 0,
    "toolhead_filament_present": True,
}


def state(**changes):
    value = deepcopy(BASE)
    value.update(changes)
    return value


def successful_scenario():
    return {
        "initial": state(),
        "after_stock": [
            state(
                active_cfs_command="RETRUDE_PROCESS",
                stock_unload_state="running",
                extruder_target_c=220,
            ),
            state(
                engaged_routes=[],
                stock_unload_state="completed",
                extruder_target_c=220,
            ),
        ],
        "after_cleanup": [
            state(engaged_routes=[], stock_unload_state="completed")
        ],
    }


class CfsStockUnloadGuardV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))

    def test_contract_is_offline_and_not_deployable(self):
        self.assertEqual("offline_guard_closed_green", self.contract["status"])
        self.assertEqual("offline_only", self.contract["authority"])
        self.assertFalse(self.contract["printer_connection"])
        self.assertFalse(self.contract["printer_action"])
        self.assertFalse(self.contract["deployment_candidate"])
        self.assertFalse(self.contract["transport_candidate"])

    def test_success_requires_effects_not_http_ack(self):
        api = fake_api.FakePrinterApi(successful_scenario())
        result = controller.StockUnloadGuard(api).run("T1A")
        self.assertEqual("OK", result.verdict)
        self.assertTrue(result.stock_completion_observed)
        self.assertTrue(result.route_clear_observed)
        self.assertTrue(result.heater_shutdown_verified)
        self.assertEqual(
            ["BOX_QUIT_MATERIAL", "TURN_OFF_HEATERS"], api.commands
        )

    def test_toolhead_segment_is_explained_not_required_clear(self):
        api = fake_api.FakePrinterApi(successful_scenario())
        result = controller.StockUnloadGuard(api).run("T1A")
        self.assertTrue(result.toolhead_filament_present_after)
        self.assertIn("après le cutter", result.operator_message)

    def test_http_ok_without_unload_effect_is_ko_without_retry(self):
        scenario = successful_scenario()
        scenario["after_stock"] = [
            state(
                active_cfs_command="RETRUDE_PROCESS",
                stock_unload_state="running",
                extruder_target_c=220,
            )
        ]
        scenario["after_cleanup"] = [state(stock_unload_state="running")]
        api = fake_api.FakePrinterApi(scenario)
        result = controller.StockUnloadGuard(api, max_polls=2).run("T1A")
        self.assertEqual("stock_unload_timeout", result.code)
        self.assertEqual(1, result.stock_command_count)
        self.assertEqual(1, result.heater_shutdown_count)

    def test_http_ok_without_heater_effect_is_ko(self):
        scenario = successful_scenario()
        scenario["after_cleanup"] = [
            state(
                engaged_routes=[],
                stock_unload_state="completed",
                extruder_target_c=220,
            )
        ]
        api = fake_api.FakePrinterApi(scenario)
        result = controller.StockUnloadGuard(api, cleanup_polls=2).run("T1A")
        self.assertEqual("KO", result.verdict)
        self.assertEqual("heater_shutdown_effect_unproven", result.code)
        self.assertTrue(result.heater_shutdown_acknowledged)
        self.assertFalse(result.heater_shutdown_verified)

    def test_transport_error_after_stock_attempt_still_requests_cleanup(self):
        scenario = successful_scenario()
        scenario["stock_error"] = "lost"
        api = fake_api.FakePrinterApi(scenario)
        result = controller.StockUnloadGuard(api).run("T1A")
        self.assertEqual("KO", result.verdict)
        self.assertTrue(result.primary_error.startswith("stock_unload_transport_error"))
        self.assertEqual(
            ["BOX_QUIT_MATERIAL", "TURN_OFF_HEATERS"], api.commands
        )

    def test_cleanup_transport_error_has_priority(self):
        scenario = successful_scenario()
        scenario["cleanup_error"] = "lost"
        api = fake_api.FakePrinterApi(scenario)
        result = controller.StockUnloadGuard(api).run("T1A")
        self.assertEqual("KO", result.verdict)
        self.assertTrue(result.code.startswith("heater_shutdown_error"))

    def test_busy_printer_refuses_without_any_command(self):
        scenario = successful_scenario()
        scenario["initial"] = state(print_state="printing")
        api = fake_api.FakePrinterApi(scenario)
        result = controller.StockUnloadGuard(api).run("T1A")
        self.assertEqual("printer_not_standby", result.code)
        self.assertEqual([], api.commands)
        self.assertFalse(result.heater_shutdown_attempted)

    def test_ambiguous_route_refuses_without_any_command(self):
        scenario = successful_scenario()
        scenario["initial"] = state(engaged_routes=["T1A", "T2B"])
        api = fake_api.FakePrinterApi(scenario)
        result = controller.StockUnloadGuard(api).run("T1A")
        self.assertEqual("expected_route_not_uniquely_engaged", result.code)
        self.assertEqual([], api.commands)

    def test_wrong_route_refuses_without_any_command(self):
        scenario = successful_scenario()
        scenario["initial"] = state(engaged_routes=["T1B"])
        api = fake_api.FakePrinterApi(scenario)
        result = controller.StockUnloadGuard(api).run("T1A")
        self.assertEqual("expected_route_not_uniquely_engaged", result.code)
        self.assertEqual([], api.commands)

    def test_active_cfs_command_refuses_without_cleanup(self):
        scenario = successful_scenario()
        scenario["initial"] = state(active_cfs_command="LOAD")
        api = fake_api.FakePrinterApi(scenario)
        result = controller.StockUnloadGuard(api).run("T1A")
        self.assertEqual("cfs_command_already_active", result.code)
        self.assertEqual([], api.commands)

    def test_missing_second_cfs_refuses(self):
        scenario = successful_scenario()
        scenario["initial"] = state(connected_cfs_units=["T1"])
        api = fake_api.FakePrinterApi(scenario)
        result = controller.StockUnloadGuard(api).run("T1A")
        self.assertEqual("two_cfs_units_not_confirmed", result.code)
        self.assertEqual([], api.commands)

    def test_unexpected_route_after_effect_fails_and_cleans_up(self):
        scenario = successful_scenario()
        scenario["after_stock"] = [
            state(
                engaged_routes=["T1B"],
                stock_unload_state="completed",
                extruder_target_c=220,
            )
        ]
        scenario["after_cleanup"] = [
            state(engaged_routes=["T1B"], stock_unload_state="completed")
        ]
        api = fake_api.FakePrinterApi(scenario)
        result = controller.StockUnloadGuard(api).run("T1A")
        self.assertEqual("engaged_route_changed_unexpectedly", result.code)
        self.assertTrue(result.heater_shutdown_verified)

    def test_invalid_route_token_is_rejected_before_snapshot(self):
        api = fake_api.FakePrinterApi(successful_scenario())
        with self.assertRaises(controller.GuardInputError):
            controller.StockUnloadGuard(api).run("T3A")
        self.assertEqual([], api.commands)

    def test_offline_scenario_matrix_is_green(self):
        summary = scenario_runner.run(PACKAGE / "scenarios.json")
        self.assertEqual("OK", summary["verdict"])
        self.assertEqual(9, summary["passed"])
        self.assertEqual(9, summary["total"])

    def test_modules_have_no_real_transport_or_process_import(self):
        forbidden = {"ctypes", "paramiko", "requests", "serial", "socket", "subprocess"}
        for filename in ("controller.py", "fake_api.py", "run_scenarios.py"):
            tree = ast.parse((PACKAGE / filename).read_text(encoding="utf-8"), filename=filename)
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertTrue(forbidden.isdisjoint(imported), filename)

    def test_next_gate_is_read_only_and_plain_language(self):
        gate = self.contract["next_gate"]
        self.assertEqual("read_only_only", gate["default_authority"])
        self.assertTrue(gate["printer_connection_requires_fresh_exact_GO"])
        self.assertFalse(gate["physical_unload_authorized"])
        guide = (PACKAGE / "NEXT-LIVE-PREFLIGHT.md").read_text(encoding="utf-8")
        self.assertIn("En langage courant", guide)
        self.assertIn("sans couper, chauffer ni", guide)

    def test_lifecycle_and_documentation_publish_same_closed_result(self):
        lifecycle = json.loads(
            (ROOT / "design" / "job-lifecycle-contract-v1.json").read_text(
                encoding="utf-8"
            )
        )
        gate = lifecycle["cfs_stock_unload_guard"]
        self.assertEqual("offline_guard_closed_green", gate["status"])
        self.assertFalse(gate["http_ok_is_effect_proof"])
        self.assertFalse(gate["automatic_stock_retry"])
        self.assertTrue(gate["success_requires_targets_zero"])
        document = (ROOT / "docs" / "35-garde-retrait-officiel-cfs-v1.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("aucun second essai automatique", document)
        self.assertIn("les deux consignes réellement à zéro", document)


if __name__ == "__main__":
    unittest.main()
