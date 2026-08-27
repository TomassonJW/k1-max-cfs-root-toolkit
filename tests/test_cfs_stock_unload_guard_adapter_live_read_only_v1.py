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
    / "cfs-stock-unload-guard-adapter-live-read-only-v1"
)
HISTORICAL_CAPTURE = (
    ROOT
    / "inventory"
    / "raw"
    / "20260827-020930-g4-k1-control-cfs-stock-unload-guard-live-preflight-v1"
    / "guard-live-preflight.private.txt"
)


spec = spec_from_file_location(
    "cfs_stock_unload_guard_adapter_live_read_only_validator",
    PACKAGE / "validate_private_capture.py",
)
validator = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = validator
spec.loader.exec_module(validator)


def historical_payload():
    lines = HISTORICAL_CAPTURE.read_text(
        encoding="utf-8-sig", errors="strict"
    ).splitlines()
    return json.loads(validator.marked_block(lines, "STATE_1"))


class CfsStockUnloadGuardAdapterLiveReadOnlyV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(
            (PACKAGE / "contract.json").read_text(encoding="utf-8")
        )
        cls.evidence = json.loads(
            (PACKAGE / "evidence-map.json").read_text(encoding="utf-8")
        )
        cls.live_result = validator.verify_evidence(ROOT)

    def test_historical_private_capture_dry_run_is_green(self):
        result = validator.verify_capture(
            HISTORICAL_CAPTURE, "LIVE_PREFLIGHT_READ_ONLY_OK"
        )
        self.assertEqual("OK", result["status"])
        self.assertEqual(2, result["live_snapshots"])
        self.assertEqual(
            "BLOCKED_NO_ENGAGED_ROUTE",
            result["current_guard_readiness_without_guard_call"],
        )
        self.assertFalse(result["guard_run_called"])

    def test_identity_is_removed_before_adapter_projection(self):
        payload = historical_payload()
        payload["result"]["status"]["box"]["T1"]["sn"] = "PRIVATE-SERIAL-SENTINEL"
        payload["result"]["status"]["box"]["T1"]["uuid"] = "PRIVATE-UUID-SENTINEL"
        safe = validator.sanitize_query_response(payload)
        rendered = json.dumps(safe, sort_keys=True)
        self.assertNotIn("PRIVATE-SERIAL-SENTINEL", rendered)
        self.assertNotIn("PRIVATE-UUID-SENTINEL", rendered)
        self.assertNotIn('"sn"', rendered)
        self.assertNotIn('"uuid"', rendered)

    def test_unknown_status_box_and_unit_fields_stop_validation(self):
        cases = []
        status_extra = historical_payload()
        status_extra["result"]["status"]["new_status"] = 1
        cases.append(status_extra)
        box_extra = historical_payload()
        box_extra["result"]["status"]["box"]["new_box"] = 1
        cases.append(box_extra)
        unit_extra = historical_payload()
        unit_extra["result"]["status"]["box"]["T1"]["new_unit"] = 1
        cases.append(unit_extra)
        for payload in cases:
            with self.subTest(keys=sorted(payload["result"]["status"])):
                with self.assertRaisesRegex(ValueError, "schema_drift"):
                    validator.sanitize_query_response(payload)

    def test_missing_field_stops_validation(self):
        payload = historical_payload()
        del payload["result"]["status"]["box"]["T2"]["filament"]
        with self.assertRaisesRegex(ValueError, "schema_drift"):
            validator.sanitize_query_response(payload)

    def test_ambiguous_routes_still_fail_in_adapter(self):
        payload = historical_payload()
        payload["result"]["status"]["box"]["T1"]["filament"] = "A"
        payload["result"]["status"]["box"]["T2"]["filament"] = "B"
        safe = validator.sanitize_query_response(payload)
        with self.assertRaisesRegex(
            validator.adapter.AdapterInputError, "engaged_routes_ambiguous"
        ):
            validator.adapter.adapt_query_response(safe)

    def test_remote_script_is_strictly_read_only(self):
        source = (PACKAGE / "capture_live_read_only.ps1").read_text(encoding="utf-8")
        match = re.search(r"\$remoteScript = @'\n(.*?)\n'@", source, re.DOTALL)
        self.assertIsNotNone(match)
        remote = match.group(1)
        self.assertEqual(2, remote.count("/printer/objects/query"))
        self.assertIn("sha256sum", remote)
        for token in (
            "/printer/gcode",
            "BOX_QUIT_MATERIAL",
            "TURN_OFF_HEATERS",
            "RESTART",
            "SAVE_CONFIG",
            "chmod ",
            "rm -",
            "mv ",
            "cp ",
            "curl -sS",
        ):
            self.assertNotIn(token, remote)

    def test_validator_has_no_transport_process_or_guard_import(self):
        source = (PACKAGE / "validate_private_capture.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="validate_private_capture.py", feature_version=(3, 8))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(
            {"paramiko", "requests", "serial", "socket", "subprocess", "urllib"}.isdisjoint(imported)
        )
        self.assertNotIn("StockUnloadGuard", source)
        self.assertNotIn("controller.py", source)

    def test_sanitized_shape_is_exact_adapter_input(self):
        safe = validator.sanitize_query_response(historical_payload())
        snapshot = validator.adapter.adapt_query_response(safe)
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

    def test_fresh_private_evidence_is_green_and_not_versioned(self):
        self.assertEqual("OK", self.live_result["status"])
        self.assertFalse(self.evidence["private_source"]["versioned"])
        self.assertTrue(self.live_result["configuration_hashes_unchanged"])
        self.assertEqual([], self.live_result["adapted_snapshot"]["engaged_routes"])

    def test_contract_keeps_every_effect_closed(self):
        self.assertEqual(
            "closed_live_read_only_adapter_ok", self.contract["status"]
        )
        self.assertTrue(self.contract["printer_connected"])
        for key in (
            "guard_run_called",
            "gcode_sent",
            "remote_files_written",
            "service_actions",
            "physical_actions",
            "transport_candidate",
            "deployment_candidate",
        ):
            self.assertFalse(self.contract[key], key)

    def test_real_none_state_is_documented_without_relaxing_unknown_states(self):
        correction = self.contract["adapter_correction"]
        self.assertEqual("None", correction["real_unprovisioned_unit_state"])
        self.assertEqual("inactive_unit", correction["meaning"])
        self.assertTrue(correction["other_unknown_unit_states_rejected"])

    def test_next_gate_is_offline_transport_only(self):
        gate = self.contract["next_gate"]
        self.assertEqual(
            "G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-TRANSPORT-OFFLINE-V1",
            gate["candidate"],
        )
        self.assertEqual("offline_only", gate["default_authority"])
        self.assertFalse(gate["printer_connection_authorized"])
        self.assertFalse(gate["gcode_authorized"])
        guide = (PACKAGE / "NEXT-TRANSPORT-OFFLINE.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("En langage courant", guide)
        self.assertIn("ne se connectera pas à la K1", guide)

    def test_lifecycle_and_documentation_publish_closed_result(self):
        lifecycle = json.loads(
            (ROOT / "design" / "job-lifecycle-contract-v1.json").read_text(
                encoding="utf-8"
            )
        )
        published = lifecycle["cfs_stock_unload_guard_adapter_live_read_only"]
        self.assertEqual("closed_live_read_only_adapter_ok", published["status"])
        self.assertFalse(published["guard_run_called"])
        self.assertFalse(published["deployment_candidate"])
        document = (
            ROOT / "docs" / "38-validation-live-adaptateur-garde-retrait-cfs-v1.md"
        ).read_text(encoding="utf-8")
        self.assertIn("OK en lecture seule", document)
        self.assertIn("BLOCKED_NO_ENGAGED_ROUTE", document)
        self.assertIn("`443` tests", document)


if __name__ == "__main__":
    unittest.main()
