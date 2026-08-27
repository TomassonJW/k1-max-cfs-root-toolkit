from importlib.util import module_from_spec, spec_from_file_location
import ast
import json
import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "packages"
    / "k1-control-v1"
    / "cfs-stock-unload-guard-adapter-offline-v1"
)
GUARD_PACKAGE = (
    ROOT / "packages" / "k1-control-v1" / "cfs-stock-unload-guard-v1"
)


def _load(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


adapter = _load("cfs_stock_unload_guard_adapter", PACKAGE / "adapter.py")
runner = _load("cfs_stock_unload_guard_adapter_runner", PACKAGE / "run_scenarios.py")
guard = _load("cfs_stock_unload_guard_controller_for_adapter", GUARD_PACKAGE / "controller.py")


def fixture(name):
    return json.loads((PACKAGE / "fixtures" / name).read_text(encoding="utf-8"))


class CfsStockUnloadGuardAdapterOfflineV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(
            (PACKAGE / "contract.json").read_text(encoding="utf-8")
        )

    def test_contract_is_strictly_offline_and_not_deployable(self):
        self.assertEqual("offline_adapter_closed_green", self.contract["status"])
        self.assertEqual("offline_only", self.contract["authority_consumed"])
        for key in (
            "printer_connection",
            "gcode_surface",
            "network_transport",
            "process_execution",
            "remote_files_written",
            "service_actions",
            "physical_actions",
            "deployment_candidate",
        ):
            self.assertFalse(self.contract[key], key)

    def test_no_route_is_translated_for_fail_closed_guard_refusal(self):
        snapshot = adapter.adapt_query_response(fixture("no-route.json"))
        self.assertEqual([], snapshot["engaged_routes"])
        self.assertEqual(["T1", "T2"], snapshot["connected_cfs_units"])
        self.assertEqual(
            "expected_route_not_uniquely_engaged",
            guard.StockUnloadGuard._preflight_error(snapshot, "T1A"),
        )

    def test_unique_route_and_active_command_are_mapped_exactly(self):
        unique = adapter.adapt_query_response(fixture("unique-route.json"))
        active = adapter.adapt_query_response(fixture("active-command.json"))
        self.assertEqual(["T1A"], unique["engaged_routes"])
        self.assertEqual("", unique["active_cfs_command"])
        self.assertEqual("RETRUDE_PROCESS", active["active_cfs_command"])
        self.assertEqual(220.0, active["extruder_target_c"])

    def test_disconnected_second_cfs_is_translated_then_guard_refuses(self):
        snapshot = adapter.adapt_query_response(
            fixture("second-cfs-disconnected.json")
        )
        self.assertEqual(["T1"], snapshot["connected_cfs_units"])
        self.assertEqual(
            "two_cfs_units_not_confirmed",
            guard.StockUnloadGuard._preflight_error(snapshot, "T1A"),
        )

    def test_disabled_toolhead_sensor_becomes_unknown(self):
        snapshot = adapter.adapt_query_response(
            fixture("disabled-toolhead-sensor.json")
        )
        self.assertIsNone(snapshot["toolhead_filament_present"])

    def test_ambiguous_routes_are_rejected(self):
        with self.assertRaisesRegex(adapter.AdapterInputError, "engaged_routes_ambiguous"):
            adapter.adapt_query_response(fixture("ambiguous-routes.json"))

    def test_incomplete_response_is_rejected(self):
        with self.assertRaisesRegex(adapter.AdapterInputError, "field_missing"):
            adapter.adapt_query_response(fixture("incomplete-response.json"))

    def test_invalid_temperature_types_and_values_are_rejected(self):
        with self.assertRaisesRegex(adapter.AdapterInputError, "temperature_invalid"):
            adapter.adapt_query_response(fixture("invalid-temperature.json"))
        payload = fixture("no-route.json")
        payload["result"]["status"]["extruder"]["target"] = math.nan
        with self.assertRaisesRegex(adapter.AdapterInputError, "temperature_invalid"):
            adapter.adapt_query_response(payload)
        payload = fixture("no-route.json")
        payload["result"]["status"]["heater_bed"]["target"] = True
        with self.assertRaisesRegex(adapter.AdapterInputError, "temperature_invalid"):
            adapter.adapt_query_response(payload)

    def test_unsupported_connected_unit_is_rejected(self):
        with self.assertRaisesRegex(adapter.AdapterInputError, "connected_unit_unsupported"):
            adapter.adapt_query_response(fixture("unsupported-connected-unit.json"))
        payload = fixture("no-route.json")
        payload["result"]["status"]["box"]["T2"]["state"] = "unknown"
        with self.assertRaisesRegex(adapter.AdapterInputError, "unit_state_invalid"):
            adapter.adapt_query_response(payload)

    def test_real_unprovisioned_unit_state_is_treated_as_inactive(self):
        payload = fixture("no-route.json")
        payload["result"]["status"]["box"]["T3"]["state"] = "None"
        payload["result"]["status"]["box"]["T4"]["state"] = "None"
        snapshot = adapter.adapt_query_response(payload)
        self.assertEqual(["T1", "T2"], snapshot["connected_cfs_units"])
        self.assertEqual([], snapshot["engaged_routes"])
        payload["result"]["status"]["box"]["T1"]["state"] = "None"
        with self.assertRaisesRegex(adapter.AdapterInputError, "unit_state_invalid:T1"):
            adapter.adapt_query_response(payload)

    def test_filament_on_disconnected_unit_is_rejected(self):
        with self.assertRaisesRegex(
            adapter.AdapterInputError, "filament_on_disconnected_unit"
        ):
            adapter.adapt_query_response(
                fixture("filament-on-disconnected-unit.json")
            )

    def test_unknown_input_fields_are_not_copied(self):
        payload = fixture("unique-route.json")
        payload["result"]["status"]["box"]["private_extra"] = "not-output"
        snapshot = adapter.adapt_query_response(payload)
        self.assertEqual(
            {
                "print_state",
                "box_state",
                "connected_cfs_units",
                "active_cfs_command",
                "engaged_routes",
                "extruder_target_c",
                "bed_target_c",
                "toolhead_filament_present",
            },
            set(snapshot),
        )
        self.assertNotIn("not-output", json.dumps(snapshot))

    def test_all_snapshots_are_accepted_by_guard_schema(self):
        for name in (
            "no-route.json",
            "unique-route.json",
            "active-command.json",
            "second-cfs-disconnected.json",
            "disabled-toolhead-sensor.json",
        ):
            snapshot = adapter.adapt_query_response(fixture(name))
            self.assertEqual(snapshot, guard._snapshot(snapshot), name)

    def test_scenario_matrix_is_green(self):
        summary = runner.run(PACKAGE / "scenarios.json")
        self.assertEqual("OK", summary["verdict"])
        self.assertEqual(10, summary["passed"])
        self.assertEqual(10, summary["total"])

    def test_modules_import_no_transport_or_process_capability(self):
        forbidden = {
            "ctypes",
            "http",
            "paramiko",
            "requests",
            "serial",
            "socket",
            "subprocess",
            "urllib",
        }
        for filename in ("adapter.py", "run_scenarios.py"):
            source = (PACKAGE / filename).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=filename, feature_version=(3, 8))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertTrue(forbidden.isdisjoint(imported), filename)

    def test_versioned_fixtures_contain_no_identity_fields(self):
        forbidden = {"sn", "serial", "serial_number", "uuid", "mac", "ip"}

        def keys(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key.lower()
                    yield from keys(child)
            elif isinstance(value, list):
                for child in value:
                    yield from keys(child)

        for path in sorted((PACKAGE / "fixtures").glob("*.json")):
            self.assertTrue(forbidden.isdisjoint(set(keys(fixture(path.name)))), path.name)

    def test_next_gate_is_separate_read_only_and_has_no_effect_authority(self):
        gate = self.contract["next_gate"]
        self.assertEqual("read_only_only", gate["default_authority"])
        self.assertFalse(gate["gcode_authorized"])
        self.assertFalse(gate["physical_unload_authorized"])
        guide = (PACKAGE / "NEXT-LIVE-READ-ONLY.md").read_text(encoding="utf-8")
        self.assertIn("En langage courant", guide)
        self.assertIn("ne devra appeler ni `StockUnloadGuard.run`", guide)

    def test_lifecycle_and_documentation_publish_the_same_closed_result(self):
        lifecycle = json.loads(
            (ROOT / "design" / "job-lifecycle-contract-v1.json").read_text(
                encoding="utf-8"
            )
        )
        published = lifecycle["cfs_stock_unload_guard_adapter_offline"]
        self.assertEqual("offline_adapter_closed_green", published["status"])
        self.assertFalse(published["printer_transport"])
        self.assertFalse(published["deployment_candidate"])
        document = (
            ROOT / "docs" / "37-adaptateur-hors-ligne-garde-retrait-cfs-v1.md"
        ).read_text(encoding="utf-8")
        self.assertIn("OK hors imprimante", document)
        self.assertIn("429` tests exécutés", document)


if __name__ == "__main__":
    unittest.main()
