import json
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run-k1-control-cfs-read-only-audit-v1.ps1"
CONTRACT = ROOT / "design" / "cfs-read-only-preflight-v1.json"
ANALYZER = (
    ROOT
    / "packages"
    / "k1-control-v1"
    / "cfs-read-only-audit-v1"
    / "analyze_capture.py"
)


def load_analyzer():
    spec = importlib.util.spec_from_file_location("cfs_read_only_analyzer", ANALYZER)
    if spec is None or spec.loader is None:
        raise RuntimeError("analyseur CFS introuvable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CfsReadOnlyAuditV1Tests(unittest.TestCase):
    def test_collector_is_read_only_on_the_printer(self) -> None:
        script = SCRIPT.read_text(encoding="utf-8")
        forbidden = (
            "/printer/gcode/script",
            '"method": "gcode/script"',
            "M104",
            "M109",
            "M140",
            "M190",
            "G28",
            "BED_MESH_CALIBRATE",
            "RESTART",
            "FIRMWARE_RESTART",
            "reboot",
            "service restart",
            "systemctl restart",
            "scp.exe",
        )
        for token in forbidden:
            self.assertNotIn(token, script)

        self.assertIn("/printer/objects/list", script)
        self.assertIn("/printer/objects/query", script)
        self.assertIn("cat /usr/data/printer_data/config/box.cfg", script)
        self.assertIn("material_box_info.json", script)
        self.assertIn("material_modify_info.json", script)
        self.assertIn("MAPPING_LOG_HISTORY_BEGIN", script)
        self.assertIn("CFS_READ_ONLY_AUDIT_OK", script)
        self.assertIn("grep -E -v", script)

    def test_contract_keeps_flow_separate_from_presence(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["status"], "read_only_audit")
        self.assertFalse(contract["printer_mutation_authorized"])
        self.assertFalse(contract["physical_action_authorized"])
        self.assertEqual(
            contract["evidence_layers"],
            ["sensor_presence", "identity", "route", "nozzle_flow"],
        )
        self.assertEqual(contract["nozzle_flow_proof"], "separate_visible_purge")
        self.assertFalse(contract["future_physical_gate"]["authorized_by_this_contract"])
        self.assertIn(
            "fresh_visible_purge_succeeds_before_print",
            contract["future_physical_gate"]["requires"],
        )
        self.assertNotIn(
            "fresh_visible_purge_succeeds_before_print",
            contract["filament_states"]["engaged_known"]["requires"],
        )

    def test_all_filament_states_are_testable_and_fail_closed(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        states = contract["filament_states"]
        self.assertEqual(
            set(states),
            {
                "absent_confirmed",
                "engaged_known",
                "engaged_unknown",
                "transitioning",
                "fault",
            },
        )
        for definition in states.values():
            self.assertTrue(definition["requires"])
            self.assertIn(
                definition["action"],
                {
                    "allow_load_only",
                    "keep_or_change_by_contract",
                    "block",
                    "continue_same_transition_only",
                    "stop_safe",
                },
            )
        self.assertEqual(states["engaged_unknown"]["action"], "block")
        self.assertEqual(states["fault"]["action"], "stop_safe")

    def test_analyzer_classification_fails_closed(self) -> None:
        analyzer = load_analyzer()
        self.assertEqual(
            analyzer.classify_filament_state(
                presence_observed=True,
                route_resolved=False,
            ),
            "engaged_unknown",
        )
        self.assertEqual(
            analyzer.classify_filament_state(
                presence_observed=True,
                route_resolved=True,
            ),
            "engaged_known",
        )
        self.assertEqual(
            analyzer.classify_filament_state(
                presence_observed=False,
                route_resolved=True,
            ),
            "fault",
        )


if __name__ == "__main__":
    unittest.main()
