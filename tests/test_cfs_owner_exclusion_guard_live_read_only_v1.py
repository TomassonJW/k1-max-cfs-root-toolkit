import ast
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-owner-exclusion-guard-live-read-only-v1"


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = load_module("cfs_owner_exclusion_guard_live_validator_test", PACKAGE / "validate_private_capture.py")


def snapshot(sequence=1):
    return {
        "schema": 1,
        "sample_seq": sequence,
        "mapping_revision": "mapping:stable",
        "connection_epoch": None,
        "printer_state": "standby",
        "connected_units": ["T1", "T2"],
        "active_command": "",
        "stock_auto_refill": 1,
        "stock_cfs_print_enable": 1,
        "engaged_routes": [],
        "protected": {
            "mesh_profile": "k1_p001_t055_r001_n11x11",
            "accepted_z_revision": "accepted-z:stable",
            "effective_z_offset_mm": -0.04,
            "homed_axes": "",
            "nozzle_target_c": 0,
            "bed_target_c": 0,
        },
    }


def capture():
    hashes = {"printer.cfg": "a" * 64, "box.cfg": "b" * 64, "gcode_macro.cfg": "c" * 64}
    return {
        "schema": 1,
        "mission": "G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-LIVE-READ-ONLY-V1",
        "authority": "strict_read_only",
        "capture_mode": "single_ssh_two_get_remote_sanitization",
        "identity_values_exported": False,
        "identity_fields_stripped": ["sn", "uuid"],
        "http_methods": ["GET"],
        "query_count": 2,
        "query_timeout_s": 5.0,
        "connection_epoch_observable": False,
        "connection_epoch_source": "unavailable_no_notification_epoch",
        "snapshots": [snapshot(1), snapshot(2)],
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


class CfsOwnerExclusionGuardLiveReadOnlyV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.evidence = json.loads((PACKAGE / "evidence-map.json").read_text(encoding="utf-8"))

    def test_contract_authorizes_only_two_remote_sanitized_get_reads(self):
        self.assertEqual("strict_read_only", self.contract["authority"])
        self.assertEqual(2, self.contract["capture"]["object_queries"])
        self.assertEqual(["GET"], self.contract["capture"]["http_methods"])
        self.assertTrue(self.contract["capture"]["remote_sanitization_before_local_return"])
        self.assertFalse(self.contract["capture"]["identity_values_exported"])
        for field, value in self.contract["boundaries"].items():
            if field not in {"printer_connection", "network_get_only"}:
                self.assertFalse(value, field)

    def test_offline_guard_source_is_pinned(self):
        source = ROOT / self.contract["source_pins"]["offline_guard_contract"]
        self.assertEqual(
            self.contract["source_pins"]["offline_guard_contract_sha256"],
            hashlib.sha256(source.read_bytes()).hexdigest(),
        )

    def test_closed_contract_forbids_replay_and_records_bounded_verdict(self):
        self.assertFalse(self.contract["rerun_authorized"])
        self.assertEqual(
            "closed_read_only_blocked_connection_epoch_and_effective_z_source",
            self.contract["status"],
        )
        self.assertEqual(
            "CLOSED_READ_ONLY_BLOCKED_CONNECTION_EPOCH_AND_EFFECTIVE_Z_SOURCE",
            self.contract["verdict"],
        )

    def test_private_evidence_and_reviewed_artifacts_are_pinned(self):
        self.assertEqual(self.evidence["safe_result"], validator.verify_evidence(ROOT))
        for relative_name, expected in self.evidence["reviewed_artifacts"].items():
            self.assertEqual(
                expected,
                hashlib.sha256((PACKAGE / relative_name).read_bytes()).hexdigest(),
                relative_name,
            )

    def test_synthetic_capture_closes_on_missing_connection_epoch(self):
        result = validator.verify_payload(capture())
        self.assertEqual("OK", result["status"])
        self.assertEqual(
            "CLOSED_READ_ONLY_BLOCKED_CONNECTION_EPOCH_AND_EFFECTIVE_Z_SOURCE",
            result["verdict"],
        )
        self.assertEqual(
            ["connection_epoch_invalid", "effective_z_source_unqualified"],
            result["adapter_blockers"],
        )
        self.assertFalse(result["accepted_z_value_observable"])
        self.assertFalse(result["effective_z_source_qualified"])
        self.assertFalse(result["guard_adapter_ready"])
        self.assertTrue(result["adapter_called"])
        self.assertFalse(result["guard_imported_or_called"])
        self.assertFalse(result["gcode_sent"])
        self.assertFalse(result["remote_write"])

    def test_invented_epoch_or_state_drift_is_rejected(self):
        invented = capture()
        for item in invented["snapshots"]:
            item["connection_epoch"] = "invented"
        with self.assertRaisesRegex(ValueError, "invented_connection_epoch"):
            validator.verify_payload(invented)

        drifted = capture()
        drifted["snapshots"][1]["stock_auto_refill"] = 0
        with self.assertRaisesRegex(ValueError, "live_state_not_stable"):
            validator.verify_payload(drifted)

    def test_configuration_or_effect_drift_is_rejected(self):
        changed = capture()
        changed["configuration_hashes_after"]["box.cfg"] = "d" * 64
        with self.assertRaisesRegex(ValueError, "configuration_hashes_changed"):
            validator.verify_payload(changed)

        effect = capture()
        effect["effects"]["gcode_sent"] = True
        with self.assertRaisesRegex(ValueError, "effect_boundary_invalid"):
            validator.verify_payload(effect)

    def test_collector_has_no_effect_endpoint_and_sanitizes_remotely(self):
        source = (PACKAGE / "capture_live_read_only.ps1").read_text(encoding="utf-8")
        self.assertIn('Request(BASE_URL + QUERY_PATH, method="GET")', source)
        self.assertEqual(2, source.count("safe_snapshot(fetch_state()"))
        self.assertIn('"identity_values_exported": False', source)
        self.assertIn('"connection_epoch": None', source)
        for forbidden in (
            "/printer/gcode/script", "BOX_ENABLE_AUTO_REFILL ENABLE=", "SAVE_CONFIG",
            "RESTART", "scp.exe", "guard.py", "from guard import"
        ):
            self.assertNotIn(forbidden, source)

    def test_validator_parses_as_python_38_and_imports_no_transport(self):
        source = (PACKAGE / "validate_private_capture.py").read_text(encoding="utf-8")
        tree = ast.parse(source, feature_version=(3, 8))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(imported & {"requests", "urllib", "socket", "subprocess", "paramiko"})


if __name__ == "__main__":
    unittest.main()
