from importlib.util import module_from_spec, spec_from_file_location
import ast
import json
from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "packages"
    / "k1-control-v1"
    / "cfs-stock-unload-guard-transport-offline-v1"
)


def _load(name, filename):
    spec = spec_from_file_location(name, PACKAGE / filename)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


transport = _load("test_cfs_guard_offline_transport", "transport.py")
fake_endpoint = _load("test_cfs_guard_offline_endpoint", "fake_endpoint.py")
runner = _load("test_cfs_guard_offline_runner", "run_scenarios.py")


class CfsStockUnloadGuardTransportOfflineV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(
            (PACKAGE / "contract.json").read_text(encoding="utf-8")
        )

    def test_contract_keeps_every_real_effect_closed(self):
        self.assertEqual("offline_only", self.contract["authority"])
        self.assertFalse(self.contract["printer_connection"])
        self.assertFalse(self.contract["printer_action"])
        self.assertFalse(self.contract["gcode_sent"])
        self.assertFalse(self.contract["deployment_candidate"])
        self.assertFalse(self.contract["real_connector_present"])

    def test_only_the_two_guard_commands_are_allowlisted(self):
        self.assertEqual(
            ["BOX_QUIT_MATERIAL", "TURN_OFF_HEATERS"],
            self.contract["interfaces"]["allowed_commands"],
        )
        self.assertEqual(
            tuple(self.contract["interfaces"]["allowed_commands"]),
            transport.ALLOWED_COMMANDS,
        )

    def test_all_thirteen_scenarios_are_deterministic_and_green(self):
        first = runner.run()
        second = runner.run()
        self.assertEqual(first, second)
        self.assertEqual("OK", first["verdict"])
        self.assertEqual(13, first["passed"])
        self.assertEqual(13, first["total"])
        self.assertFalse(first["printer_connection"])
        self.assertFalse(first["gcode_sent"])

    def test_success_runs_exactly_one_stock_and_one_cleanup_command(self):
        result = runner.run_one("success_route_clear_and_targets_zero")
        self.assertEqual("OK", result["verdict"])
        self.assertEqual(
            ["BOX_QUIT_MATERIAL", "TURN_OFF_HEATERS"],
            result["attempted_commands"],
        )
        command_entries = [
            item for item in result["journal"] if item["operation"] == "command"
        ]
        self.assertEqual(2, len(command_entries))
        self.assertTrue(
            all(item["effect_certainty"] == "unproven_request_return" for item in command_entries)
        )

    def test_stock_timeout_never_resends_and_still_attempts_cleanup_once(self):
        result = runner.run_one("stock_timeout_no_retry_cleanup_once")
        self.assertEqual("KO", result["verdict"])
        self.assertEqual(1, result["stock_count"])
        self.assertEqual(1, result["cleanup_count"])
        self.assertEqual(
            ["BOX_QUIT_MATERIAL", "TURN_OFF_HEATERS"],
            result["attempted_commands"],
        )
        timeout = next(item for item in result["journal"] if item["outcome"] == "timeout")
        self.assertEqual("BOX_QUIT_MATERIAL", timeout["command"])
        self.assertEqual("unknown", timeout["effect_certainty"])

    def test_false_http_successes_need_observed_effects(self):
        unload = runner.run_one("http_ok_without_unload_effect")
        cleanup = runner.run_one("http_ok_without_cleanup_effect")
        self.assertEqual("stock_unload_timeout", unload["code"])
        self.assertEqual("heater_shutdown_effect_unproven", cleanup["code"])

    def test_duplicate_and_unknown_commands_stop_before_endpoint(self):
        for scenario_id, expected_calls in (
            ("duplicate_stock_rejected", 1),
            ("duplicate_cleanup_rejected", 2),
            ("unsupported_command_rejected", 0),
            ("cleanup_before_stock_rejected", 0),
        ):
            with self.subTest(scenario_id=scenario_id):
                result = runner.run_one(scenario_id)
                self.assertEqual(expected_calls, result["endpoint_commands"])
                self.assertEqual("rejected_before_endpoint", result["journal"][-1]["outcome"])

    def test_exact_deadlines_pass_and_one_millisecond_over_fails(self):
        boundary = runner.run_one("exact_deadlines_are_accepted")
        timeout = runner.run_one("stock_timeout_no_retry_cleanup_once")
        self.assertEqual("OK", boundary["verdict"])
        self.assertEqual("KO", timeout["verdict"])
        self.assertTrue(timeout["primary_error"].startswith("stock_unload_transport_error"))

    def test_schema_drift_blocks_before_any_command(self):
        result = runner.run_one("schema_drift_refused_before_command")
        self.assertEqual("KO", result["verdict"])
        self.assertEqual([], result["attempted_commands"])
        self.assertEqual(0, result["endpoint_commands"])
        self.assertTrue(result["primary_error"].startswith("preflight_snapshot_invalid"))

    def test_endpoint_script_is_strict_and_does_not_repeat_events(self):
        endpoint = fake_endpoint.ScriptedEndpoint(
            [runner.command(transport.STOCK_UNLOAD_COMMAND)]
        )
        event = endpoint.exchange("command", transport.STOCK_UNLOAD_COMMAND)
        self.assertEqual({"result": "ok"}, event["payload"])
        with self.assertRaises(fake_endpoint.EndpointScriptError):
            endpoint.exchange("command", transport.STOCK_UNLOAD_COMMAND)

        malformed = fake_endpoint.ScriptedEndpoint(
            [
                {
                    "operation": "command",
                    "command": transport.STOCK_UNLOAD_COMMAND,
                    "elapsed_s": "invalid",
                    "payload": {"result": "ok"},
                }
            ]
        )
        seam = transport.OfflineGuardTransport(malformed, lambda payload: payload)
        with self.assertRaises(transport.TransportFailure):
            seam.run_gcode(transport.STOCK_UNLOAD_COMMAND)
        self.assertEqual((transport.STOCK_UNLOAD_COMMAND,), seam.attempted_commands)
        self.assertEqual("endpoint_error", seam.journal[-1].outcome)
        self.assertEqual("unknown", seam.journal[-1].effect_certainty)

    def test_runtime_imports_no_real_transport_clock_or_process_capability(self):
        forbidden = {
            "asyncio",
            "ctypes",
            "http",
            "paramiko",
            "requests",
            "serial",
            "socket",
            "subprocess",
            "time",
            "urllib",
        }
        for filename in ("transport.py", "fake_endpoint.py", "run_scenarios.py"):
            tree = ast.parse((PACKAGE / filename).read_text(encoding="utf-8"))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertTrue(forbidden.isdisjoint(imported), filename)

    def test_public_package_contains_no_host_or_identity_value(self):
        rendered = "\n".join(
            path.read_text(encoding="utf-8")
            for path in PACKAGE.iterdir()
            if path.is_file()
        )
        self.assertNotIn("PRINTER_HOST", rendered)
        self.assertNotIn('"sn"', rendered)
        self.assertNotIn('"uuid"', rendered)
        self.assertIsNone(re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", rendered))

    def test_readme_explains_unknown_effect_and_no_retry_in_plain_language(self):
        readme = (PACKAGE / "README.md").read_text(encoding="utf-8")
        self.assertIn("rend l'effet inconnu", readme)
        self.assertIn("interdit toute nouvelle", readme)
        self.assertIn("aucune connexion K1", readme)


if __name__ == "__main__":
    unittest.main()
