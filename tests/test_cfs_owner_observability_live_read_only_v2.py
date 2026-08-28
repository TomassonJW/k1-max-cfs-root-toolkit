import ast
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-owner-observability-live-read-only-v2"
OFFLINE = ROOT / "packages" / "k1-control-v1" / "cfs-owner-observability-adapter-offline-v2"


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = load_module("cfs_owner_observability_live_validator_v2_test", PACKAGE / "validate_private_capture.py")
offline_runner = load_module("cfs_owner_observability_live_offline_runner_v2_test", OFFLINE / "run_scenarios.py")


def capture():
    observations = offline_runner.pair()
    hashes = {
        "/usr/data/printer_data/config/printer.cfg": "a" * 64,
        "/usr/data/printer_data/config/box.cfg": "b" * 64,
        "/usr/data/printer_data/config/gcode_macro.cfg": "c" * 64,
    }
    return {
        "schema": 2,
        "mission": "G4-K1-CONTROL-CFS-OWNER-OBSERVABILITY-LIVE-READ-ONLY-V2",
        "authority": "strict_read_only",
        "capture_mode": "single_ssh_persistent_moonraker_websocket_subscription",
        "identity_values_exported": False,
        "identity_fields_stripped": ["sn", "uuid"],
        "rpc_methods": [
            "server.websocket.id", "printer.objects.subscribe", "printer.objects.query"
        ],
        "state_read_count": 2,
        "observation_window_s": 2.0,
        "observer_connection_id": 424242,
        "reported_cfs_transition_count": 0,
        "reported_cfs_transitions": [],
        "observations": observations,
        "configuration_hashes_before": hashes,
        "configuration_hashes_after": dict(hashes),
        "effects": {
            "remote_files_written": False,
            "gcode_sent": False,
            "heater_action": False,
            "motion_action": False,
            "cfs_action": False,
            "service_action": False,
            "guard_imported_or_called": False,
        },
    }


class CfsOwnerObservabilityLiveReadOnlyV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.evidence = json.loads((PACKAGE / "evidence-map.json").read_text(encoding="utf-8"))

    def test_contract_authorizes_only_one_persistent_read_only_connection(self):
        self.assertEqual("strict_read_only", self.contract["authority"])
        self.assertEqual(1, self.contract["capture"]["moonraker_connections"])
        self.assertEqual(2, self.contract["capture"]["state_reads"])
        for field, value in self.contract["boundaries"].items():
            if field not in {"printer_connection", "network_read_only"}:
                self.assertFalse(value, field)

    def test_synthetic_capture_qualifies_projection_without_effect(self):
        result = validator.verify_payload(capture())
        self.assertEqual("OK", result["status"])
        self.assertTrue(result["offline_adapter_accepted"])
        self.assertEqual(-0.04, result["accepted_z_offset_mm"])
        self.assertTrue(result["accepted_z_value_stable"])
        self.assertTrue(result["accepted_z_store_integrity_qualified"])
        self.assertFalse(result["guard_imported_or_called"])
        self.assertFalse(result["gcode_sent"])

    def test_transition_connection_and_effect_drift_are_rejected(self):
        transitioned = capture()
        transitioned["reported_cfs_transition_count"] = 1
        transitioned["reported_cfs_transitions"] = [{"seq": 1}]
        with self.assertRaisesRegex(ValueError, "cfs_transition_observed"):
            validator.verify_payload(transitioned)
        changed = capture()
        changed["observations"][1]["observer_connection_id"] += 1
        with self.assertRaisesRegex(ValueError, "observer_connection_id_mismatch"):
            validator.verify_payload(changed)
        effect = capture()
        effect["effects"]["gcode_sent"] = True
        with self.assertRaisesRegex(ValueError, "effect_boundary_invalid"):
            validator.verify_payload(effect)

    def test_remote_observer_exposes_only_read_methods_and_sanitized_fields(self):
        source = (PACKAGE / "remote_observer.py").read_text(encoding="utf-8")
        for method in self.contract["capture"]["rpc_methods"]:
            self.assertIn('"%s"' % method, source)
        for forbidden in (
            "gcode/script", "printer.gcode.script", "BOX_ENABLE_AUTO_REFILL",
            "SAVE_CONFIG", "RESTART", "scp", "from guard import",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn('"identity_values_exported": False', source)
        self.assertIn('"runtime_accepted_z_offset_mm"', source)
        self.assertIn('"store_accepted_z_offset_mm"', source)

    def test_python_sources_parse_as_python_38(self):
        for name in ("remote_observer.py", "validate_private_capture.py"):
            ast.parse((PACKAGE / name).read_text(encoding="utf-8"), feature_version=(3, 8))

    def test_private_capture_and_executed_artifacts_are_pinned(self):
        self.assertEqual(self.evidence["safe_result"], validator.verify_evidence(ROOT))
        for name, expected in self.evidence["executed_artifacts"].items():
            self.assertEqual(expected, hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest(), name)
        self.assertFalse(self.contract["rerun_authorized"])
        self.assertEqual(
            "CLOSED_READ_ONLY_OBSERVABILITY_V2_QUALIFIED_EFFECTS_CLOSED",
            self.contract["verdict"],
        )


if __name__ == "__main__":
    unittest.main()
