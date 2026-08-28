import ast
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-owner-observability-adapter-offline-v2"


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = load_module("cfs_owner_observability_adapter_offline_v2_runner_test", PACKAGE / "run_scenarios.py")


class CfsOwnerObservabilityAdapterOfflineV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.scenarios = json.loads((PACKAGE / "scenarios.json").read_text(encoding="utf-8"))

    def test_contract_is_offline_only_and_pins_the_closed_guard(self):
        self.assertEqual("offline_only", self.contract["authority"])
        self.assertTrue(all(value is False for value in self.contract["boundaries"].values()))
        source = ROOT / self.contract["source_pins"]["guard_contract"]
        self.assertEqual(
            self.contract["source_pins"]["guard_contract_sha256"],
            hashlib.sha256(source.read_bytes()).hexdigest(),
        )

    def test_all_declared_scenarios_are_deterministic(self):
        result = runner.run()
        self.assertEqual(12, result["total"])
        self.assertEqual(12, result["passed"])
        self.assertEqual(0, result["failed"])
        self.assertEqual(
            self.contract["required_scenarios"],
            [item["id"] for item in self.scenarios["scenarios"]],
        )
        self.assertFalse(result["printer_connection"])
        self.assertFalse(result["gcode_sent"])
        self.assertFalse(result["physical_action"])

    def test_stable_pair_projects_observed_epoch_and_real_accepted_z(self):
        result = runner.run()
        projection = result["results"][0]["projection"]
        self.assertEqual(-0.04, projection["accepted_z_offset_mm"])
        self.assertTrue(projection["accepted_z_value_stable"])
        self.assertTrue(projection["accepted_z_store_integrity_qualified"])
        self.assertTrue(projection["reported_transition_free"])
        self.assertEqual(-0.04, projection["guard_snapshot"]["protected"]["effective_z_offset_mm"])
        self.assertTrue(projection["connection_epoch"].startswith("moonraker-ws-424242:cfs-0:"))

    def test_reconnect_transition_and_store_shape_drift_fail_closed(self):
        results = {item["id"]: item for item in runner.run()["results"]}
        self.assertEqual("observer_connection_changed", results["observer_connection_change_rejected"]["actual"])
        self.assertEqual("cfs_connection_transition_observed", results["reported_cfs_transition_rejected"]["actual"])
        self.assertEqual("accepted_z_store_shape_invalid", results["store_shape_drift_rejected"]["actual"])

    def test_homing_origin_can_never_substitute_for_accepted_z(self):
        result = {item["id"]: item for item in runner.run()["results"]}
        self.assertEqual("protected_fields_invalid", result["homing_origin_substitution_rejected"]["actual"])
        source = (PACKAGE / "adapter_v2.py").read_text(encoding="utf-8")
        self.assertNotIn("homing_origin", source)

    def test_runtime_sources_parse_as_python_38_and_have_no_transport(self):
        imported = set()
        for name in ("adapter_v2.py", "run_scenarios.py"):
            source = (PACKAGE / name).read_text(encoding="utf-8")
            tree = ast.parse(source, feature_version=(3, 8))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
        self.assertFalse(imported & {"socket", "urllib", "requests", "subprocess", "paramiko", "websocket"})


if __name__ == "__main__":
    unittest.main()
