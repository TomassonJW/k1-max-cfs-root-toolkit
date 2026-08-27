from copy import deepcopy
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
    / "k1-read-only-qualification-v1"
)


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


analyzer = load_module("k1_read_only_qualification_analyzer_test", PACKAGE / "analyze_capture.py")
connector = analyzer.connector


class K1ReadOnlyQualificationV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(
            (PACKAGE / "contract.json").read_text(encoding="utf-8")
        )
        cls.evidence = json.loads(
            (PACKAGE / "evidence-map.json").read_text(encoding="utf-8")
        )
        cls.capture_path = ROOT / cls.evidence["private_source"]["path"]
        cls.capture = analyzer.load_capture(cls.capture_path)
        cls.snapshots = cls.capture["snapshots"]
        cls.result = analyzer.verify_evidence(ROOT)

    def test_private_capture_is_pinned_and_valid(self):
        self.assertFalse(self.evidence["private_source"]["versioned"])
        self.assertFalse(self.evidence["private_source"]["identity_values_exported"])
        self.assertEqual(
            self.evidence["private_source"]["sha256"],
            analyzer.sha256_file(self.capture_path),
        )
        self.assertEqual(self.evidence["safe_result"], self.result)

    def test_gate_closes_on_real_mesh_drift(self):
        self.assertEqual(
            "CLOSED_READ_ONLY_BLOCKED_MESH_DRIFT", self.result["status"]
        )
        self.assertEqual("default", self.result["active_mesh_profile"])
        self.assertEqual(
            "k1_p001_t055_r001_n06x06",
            self.result["required_mesh_profile"],
        )
        self.assertFalse(self.result["active_mesh_matches_required"])
        self.assertFalse(self.result["offline_contract_ready"])

    def test_two_live_reads_are_stable_except_allowed_temperature_drift(self):
        first, second = self.snapshots
        self.assertLess(float(first["eventtime"]), float(second["eventtime"]))
        self.assertEqual(
            connector.control_projection(first),
            connector.control_projection(second),
        )
        self.assertEqual(
            connector.adapt_snapshot(first), connector.adapt_snapshot(second)
        )

    def test_live_read_deadline_is_bounded(self):
        self.assertTrue(self.result["query_deadline_qualified"])
        self.assertLessEqual(self.result["maximum_observed_query_ms"], 5000.0)
        self.assertEqual(5.0, self.contract["capture"]["per_request_timeout_s"])

    def test_configuration_and_component_hashes_are_exact_and_unchanged(self):
        self.assertEqual(self.capture["hashes_before"], self.capture["hashes_after"])
        self.assertEqual(
            self.contract["expected_hashes"], self.capture["hashes_before"]
        )
        self.assertTrue(self.result["configuration_hashes_unchanged"])

    def test_mapping_cache_invalidates_on_observable_change_or_epoch(self):
        first = self.snapshots[0]
        same = deepcopy(first)
        changed = deepcopy(first)
        changed["box"]["T2"]["state"] = "disconnect"
        self.assertTrue(
            connector.mapping_cache_valid(
                first, same, connection_epoch_changed=False
            )
        )
        self.assertFalse(
            connector.mapping_cache_valid(
                first, changed, connection_epoch_changed=False
            )
        )
        self.assertFalse(
            connector.mapping_cache_valid(
                first, same, connection_epoch_changed=True
            )
        )

    def test_same_state_reconnect_gap_is_explicit(self):
        mapping = self.contract["mapping_cache"]
        self.assertFalse(mapping["same_state_reconnect_between_polls_detectable"])
        self.assertTrue(mapping["future_moonraker_notification_epoch_required"])
        self.assertFalse(mapping["physical_reconnect_triggered"])

    def test_connector_rejects_new_or_ambiguous_data(self):
        extra = deepcopy(self.snapshots[0])
        extra["new_live_field"] = True
        with self.assertRaisesRegex(connector.ReadOnlyInputError, "schema_drift"):
            connector.adapt_snapshot(extra)

        ambiguous = deepcopy(self.snapshots[0])
        ambiguous["box"]["T1"]["filament"] = "A"
        ambiguous["box"]["T2"]["filament"] = "B"
        with self.assertRaisesRegex(
            connector.ReadOnlyInputError, "engaged_routes_ambiguous"
        ):
            connector.adapt_snapshot(ambiguous)

    def test_connector_has_no_network_process_file_or_effect_surface(self):
        source = (PACKAGE / "read_only_connector.py").read_text(encoding="utf-8")
        tree = ast.parse(
            source, filename="read_only_connector.py", feature_version=(3, 8)
        )
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        forbidden = {
            "asyncio",
            "os",
            "pathlib",
            "requests",
            "serial",
            "socket",
            "subprocess",
            "urllib",
        }
        self.assertTrue(forbidden.isdisjoint(imported))
        for token in ("BOX_QUIT_MATERIAL", "TURN_OFF_HEATERS", "/printer/gcode"):
            self.assertNotIn(token, source)

    def test_live_collector_contains_get_only_and_no_remote_write_route(self):
        source = (PACKAGE / "capture_live_read_only.ps1").read_text(encoding="utf-8")
        match = re.search(r"\$remotePython = @'\n(.*?)\n'@", source, re.DOTALL)
        self.assertIsNotNone(match)
        remote = match.group(1)
        self.assertIn('Request(BASE_URL + path, method="GET")', remote)
        self.assertIn("time.monotonic()", remote)
        self.assertIn("hash_file", remote)
        for token in (
            "BOX_QUIT_MATERIAL",
            "TURN_OFF_HEATERS",
            "/printer/gcode",
            "SAVE_CONFIG",
            "RESTART",
            "subprocess",
            "os.remove",
            "os.rename",
            "open(path, \"w",
            "requests.post",
            "urlopen(Request(BASE_URL + path, method=\"POST\")",
        ):
            self.assertNotIn(token, remote)
        self.assertIn("$remoteProgram | & ssh.exe", source)
        self.assertNotIn("scp.exe", source)

    def test_every_effect_and_deployment_boundary_remains_closed(self):
        self.assertEqual(["GET"], self.capture["http_methods"])
        self.assertFalse(self.capture["identity_values_exported"])
        self.assertEqual(
            {
                "gcode_sent": False,
                "guard_called": False,
                "physical_action": False,
                "remote_files_written": False,
                "service_action": False,
            },
            self.capture["effects"],
        )
        self.assertFalse(self.contract["integration"]["component_activated"])
        self.assertFalse(self.contract["integration"]["deployment_candidate"])

    def test_documentation_states_the_bounded_ko_and_next_human_gate(self):
        result = (PACKAGE / "RESULT.md").read_text(encoding="utf-8")
        guide = (
            ROOT / "docs" / "41-qualification-k1-lecture-seule-goal-2.md"
        ).read_text(encoding="utf-8")
        options = (PACKAGE / "INTEGRATION-OPTIONS.md").read_text(encoding="utf-8")
        self.assertIn("CLOSED_READ_ONLY_BLOCKED_MESH_DRIFT", result)
        self.assertIn("profil robuste", guide)
        self.assertIn("Thomas devra", guide)
        self.assertIn("être devant la K1", guide)
        self.assertIn("composant Moonraker séparé", options)


if __name__ == "__main__":
    unittest.main()
