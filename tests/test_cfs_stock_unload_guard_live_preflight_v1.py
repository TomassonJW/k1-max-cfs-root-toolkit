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
    / "cfs-stock-unload-guard-live-preflight-v1"
)
GUARD_PACKAGE = (
    ROOT / "packages" / "k1-control-v1" / "cfs-stock-unload-guard-v1"
)

spec = spec_from_file_location(
    "cfs_stock_unload_guard_live_preflight_verifier",
    PACKAGE / "verify_private_capture.py",
)
verifier = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = verifier
spec.loader.exec_module(verifier)


class CfsStockUnloadGuardLivePreflightV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(
            (PACKAGE / "contract.json").read_text(encoding="utf-8")
        )
        cls.evidence = json.loads(
            (PACKAGE / "evidence-map.json").read_text(encoding="utf-8")
        )
        cls.result = verifier.verify(ROOT)

    def test_live_mapping_is_ok_but_current_route_is_empty(self):
        self.assertEqual("OK_WITH_GUARD_CORRECTION", self.result["status"])
        self.assertEqual(["T1", "T2"], self.result["connected_cfs_units"])
        self.assertEqual([], self.result["engaged_routes"])
        self.assertEqual("BLOCKED_NO_ENGAGED_ROUTE", self.result["current_guard_readiness"])

    def test_live_connection_was_strictly_read_only(self):
        self.assertTrue(self.contract["printer_connected"])
        self.assertFalse(self.contract["gcode_sent"])
        self.assertFalse(self.contract["remote_files_written"])
        self.assertFalse(self.contract["service_actions"])
        self.assertFalse(self.contract["physical_actions"])
        self.assertFalse(self.contract["deployment_candidate"])

    def test_two_snapshots_are_safe_and_configuration_is_unchanged(self):
        self.assertEqual(2, self.result["live_snapshots"])
        self.assertEqual("ready", self.result["klippy_state"])
        self.assertEqual("standby", self.result["print_state"])
        self.assertEqual(0, self.result["extruder_target_c"])
        self.assertEqual(0, self.result["bed_target_c"])
        self.assertTrue(self.result["configuration_hashes_unchanged"])

    def test_real_field_mapping_is_explicit(self):
        mapping = self.evidence["direct_live_mapping"]
        self.assertEqual("print_stats.state", mapping["print_state"])
        self.assertEqual("box.t_command", mapping["active_cfs_command"])
        self.assertIn("box.T1..T4", mapping["connected_cfs_units"])
        self.assertIn("filament", mapping["engaged_routes"])

    def test_nonexistent_stock_completion_field_was_removed_from_guard(self):
        self.assertFalse(self.result["direct_stock_unload_state_field"])
        guard_source = (GUARD_PACKAGE / "controller.py").read_text(encoding="utf-8")
        self.assertNotIn("stock_unload_state", guard_source)
        guard_contract = json.loads(
            (GUARD_PACKAGE / "contract.json").read_text(encoding="utf-8")
        )
        self.assertFalse(
            guard_contract["safety_policy"]["direct_stock_unload_state_field_required"]
        )

    def test_completion_rule_uses_real_effect_not_http_alone(self):
        correction = self.contract["guard_correction"]
        self.assertEqual(
            [
                "stock_request_returned_without_transport_exception",
                "expected_route_cleared",
                "box_t_command_empty",
            ],
            correction["new_completion_evidence"],
        )
        self.assertFalse(correction["http_ok_alone_is_success"])

    def test_historical_capture_proves_route_change_but_not_t_command_lifecycle(self):
        self.assertEqual("T1A_to_none", self.result["historical_route_transition"])
        self.assertEqual([""], self.result["historical_t_command_distinct_values"])

    def test_remote_script_contains_only_read_operations(self):
        source = (PACKAGE / "capture_live_preflight.ps1").read_text(encoding="utf-8")
        match = re.search(r"\$remoteScript = @'\n(.*?)\n'@", source, re.DOTALL)
        self.assertIsNotNone(match)
        remote = match.group(1)
        self.assertIn("/printer/objects/query", remote)
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
        ):
            self.assertNotIn(token, remote)
        self.assertNotIn("curl -sS", remote)

    def test_verifier_has_no_transport_and_emits_no_identity(self):
        source = (PACKAGE / "verify_private_capture.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="verify_private_capture.py")
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(
            {"paramiko", "requests", "serial", "socket", "subprocess"}.isdisjoint(
                imported
            )
        )
        rendered = json.dumps(self.result, sort_keys=True)
        self.assertNotIn('"sn"', rendered)
        self.assertNotIn('"uuid"', rendered)

    def test_private_identity_fields_are_not_versioned(self):
        privacy = self.evidence["privacy"]
        self.assertFalse(privacy["raw_capture_versioned"])
        self.assertFalse(privacy["CFS_serial_numbers_versioned"])
        self.assertFalse(privacy["CFS_UUIDs_versioned"])

    def test_rejected_first_capture_is_not_the_live_authority(self):
        rejected = self.evidence["private_sources"]["rejected_curl_option_capture"]
        self.assertIn("not_accepted", rejected["reason"])
        self.assertNotEqual(
            rejected["sha256"],
            self.evidence["private_sources"]["valid_live_capture"]["sha256"],
        )

    def test_next_gate_is_offline_adapter_in_plain_language(self):
        gate = self.contract["next_gate"]
        self.assertEqual(
            "G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-OFFLINE-V1",
            gate["candidate"],
        )
        self.assertEqual("offline_only", gate["default_authority"])
        self.assertFalse(gate["physical_unload_authorized"])
        guide = (PACKAGE / "NEXT-ADAPTER-OFFLINE.md").read_text(encoding="utf-8")
        self.assertIn("En langage courant", guide)
        self.assertIn("petit traducteur", guide)


if __name__ == "__main__":
    unittest.main()
