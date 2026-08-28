from importlib.util import module_from_spec, spec_from_file_location
import ast
import json
from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-s12-owner-preflight-v1"


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


analyzer = load_module("cfs_s12_owner_preflight_analyzer_test", PACKAGE / "analyze_capture.py")


class CfsS12OwnerPreflightV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.evidence = json.loads((PACKAGE / "evidence-map.json").read_text(encoding="utf-8"))
        cls.capture_path = ROOT / cls.evidence["private_source"]["path"]
        cls.capture = analyzer.load_capture(cls.capture_path)
        cls.result = analyzer.verify_evidence(ROOT)

    def test_authority_is_strictly_read_only(self):
        authority = self.contract["authority"]
        self.assertTrue(authority["printer_connection"])
        self.assertEqual(["GET"], authority["http_methods"])
        for key in (
            "gcode",
            "heat",
            "motion",
            "cfs_effect",
            "remote_write",
            "service_restart",
            "deployment",
            "physical_phase",
        ):
            self.assertFalse(authority[key])

    def test_live_collector_uses_get_and_remote_sanitization_only(self):
        source = (PACKAGE / "capture_live_read_only.ps1").read_text(encoding="utf-8")
        match = re.search(r"\$remotePython = @'\n(.*?)\n'@", source, re.DOTALL)
        self.assertIsNotNone(match)
        remote = match.group(1)
        self.assertIn('Request(BASE_URL + path, method="GET")', remote)
        self.assertIn('"identity_fields_stripped": ["sn", "uuid"]', remote)
        self.assertIn("safe_unit", remote)
        self.assertIn("binary_inventory", remote)
        self.assertIn("config_inventory", remote)
        for token in (
            "/printer/gcode/script",
            'method="POST"',
            "requests.post",
            "subprocess",
            "os.remove",
            "os.rename",
            'open(path, "w',
            "systemctl",
            "service restart",
        ):
            self.assertNotIn(token, remote)
        self.assertIn("$remoteProgram | & ssh.exe", source)
        self.assertNotIn("scp.exe", source)

    def test_remote_python_is_python_38_compatible(self):
        source = (PACKAGE / "capture_live_read_only.ps1").read_text(encoding="utf-8")
        match = re.search(r"\$remotePython = @'\n(.*?)\n'@", source, re.DOTALL)
        self.assertIsNotNone(match)
        ast.parse(match.group(1), filename="remote_s12_capture.py", feature_version=(3, 8))

    def test_private_capture_is_pinned_but_not_versioned(self):
        private_source = self.evidence["private_source"]
        self.assertFalse(private_source["versioned"])
        self.assertFalse(private_source["identity_values_exported"])
        self.assertEqual(private_source["sha256"], analyzer.sha256_file(self.capture_path))

    def test_real_capture_kept_every_effect_closed(self):
        self.assertEqual(["GET"], self.capture["http_methods"])
        self.assertFalse(self.capture["identity_values_exported"])
        self.assertTrue(all(value is False for value in self.capture["effects"].values()))
        self.assertEqual(
            "CLOSED_READ_ONLY_S12_SURFACE_CONFIRMED_EFFECTS_CLOSED",
            self.result["status"],
        )

    def test_exact_binary_and_loaders_match_historical_evidence(self):
        self.assertTrue(all(self.result["historical_hashes_match"].values()))
        self.assertTrue(self.result["checks"]["files_unchanged"])

    def test_safe_observations_are_derived_from_the_pinned_capture(self):
        observed = self.evidence["safe_observations"]
        first = self.capture["snapshots"][0]
        self.assertEqual(observed["printer_state"], first["print_state"])
        self.assertEqual(observed["hotend_target_c"], first["extruder"]["target"])
        self.assertEqual(observed["bed_target_c"], first["heater_bed"]["target"])
        self.assertEqual(observed["active_mesh"], first["active_mesh"])
        self.assertEqual(observed["stock_auto_refill_value"], first["box"]["auto_refill"])
        self.assertEqual(observed["stock_cfs_print_enable_value"], first["box"]["enable"])
        self.assertEqual(
            observed["same_material_groups_without_identity"],
            first["box"]["same_material_groups"],
        )
        self.assertEqual(
            observed["exact_binary_command_name_count"],
            len(self.capture["binary_inventory"]["command_names"]),
        )
        callbacks = self.capture["binary_inventory"]["callback_markers"]
        self.assertEqual("17/17", observed["reviewed_callback_markers_present"])
        self.assertEqual(17, sum(value is True for value in callbacks.values()))
        self.assertEqual(
            observed["active_config_box_call_count"],
            len(self.capture["config_inventory"]["box_calls"]),
        )
        self.assertEqual(
            observed["active_box_option_count"],
            len(self.capture["config_inventory"]["box_options"]),
        )
        self.assertTrue(
            self.capture["config_inventory"]["box_options"]["Tn_extrude_temp"].startswith("220")
        )
        self.assertEqual(
            observed["objects_query_timings_ms"],
            self.capture["timings_ms"]["objects_query"],
        )

    def test_required_commands_and_callbacks_are_bound_to_exact_s12(self):
        for evidence in self.result["required_command_presence"].values():
            self.assertTrue(evidence["name_in_exact_binary"])
            self.assertIn("not_authoritative", evidence["registration_note"])
        self.assertTrue(all(self.result["required_callback_presence"].values()))

    def test_auto_refill_is_preserved_as_custom_feature_not_stock_owner(self):
        refill = self.result["auto_refill"]
        self.assertTrue(refill["custom_feature_remains_possible_to_implement"])
        self.assertFalse(refill["stock_auto_refill_selected_as_job_owner"])
        self.assertFalse(refill["physical_runout_behavior_qualified"])

    def test_no_effect_or_deployment_is_authorized(self):
        next_scope = self.result["next_scope"]
        self.assertFalse(next_scope["deployment_authorized"])
        self.assertFalse(next_scope["gcode_or_cfs_effect_authorized"])
        self.assertFalse(next_scope["physical_phase_authorized"])
        self.assertTrue(next_scope["separate_human_present_gate_required_per_primitive"])


if __name__ == "__main__":
    unittest.main()
