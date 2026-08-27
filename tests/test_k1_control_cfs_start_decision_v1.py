from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-temp-owner-v1"


def load_module():
    spec = importlib.util.spec_from_file_location("cfs_start_decision", PACKAGE / "start_decision.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CfsStartDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def snapshot(self, routes=None, head=False, after=False, command=""):
        return {
            "kind": "snapshot",
            "cfs": {
                "state": "connect",
                "T1_state": "connect",
                "T2_state": "connect",
                "active_command": command,
                "engaged_routes": routes or [],
            },
            "sensors": {"head": head, "after_cutter": after},
        }

    def test_segment_without_route_blocks(self):
        result = self.module.classify(self.snapshot(head=True), "T1A", False)
        self.assertEqual("BLOCK", result["decision"])
        self.assertEqual("SEGMENT_PRESENT_WITHOUT_UNIQUE_ROUTE", result["reason"])
        self.assertFalse(any(result["effects"].values()))

    def test_empty_path_loads_only_when_both_sensors_are_clear(self):
        result = self.module.classify(self.snapshot(), "T1A", False)
        self.assertEqual("LOAD", result["decision"])
        self.assertEqual("PATH_CONFIRMED_EMPTY", result["reason"])

    def test_confirmed_residual_same_route_allows_load(self):
        result = self.module.classify(self.snapshot(head=True), "T1A", False, "T1A")
        self.assertEqual("LOAD", result["decision"])
        self.assertEqual("CONFIRMED_RESIDUAL_SEGMENT_SAME_ROUTE", result["reason"])
        self.assertEqual("T1A", result["confirmed_residual_route"])

    def test_confirmed_residual_other_route_still_blocks(self):
        result = self.module.classify(self.snapshot(head=True), "T2C", False, "T1A")
        self.assertEqual("BLOCK", result["decision"])
        self.assertEqual("CONFIRMED_RESIDUAL_ROUTE_DIFFERS", result["reason"])

    def test_invalid_confirmed_residual_route_is_rejected(self):
        with self.assertRaises(self.module.DecisionError):
            self.module.classify(self.snapshot(head=True), "T1A", False, "unknown")

    def test_route_without_material_identity_still_blocks(self):
        result = self.module.classify(self.snapshot(["T1A"], head=True), "T1A", False)
        self.assertEqual("BLOCK", result["decision"])
        self.assertEqual("MATERIAL_IDENTITY_UNPROVEN", result["reason"])

    def test_confirmed_match_keeps_and_confirmed_difference_changes(self):
        keep = self.module.classify(self.snapshot(["T1A"], head=True), "T1A", True)
        change = self.module.classify(self.snapshot(["T1A"], head=True), "T2C", True)
        self.assertEqual("KEEP", keep["decision"])
        self.assertEqual("CHANGE", change["decision"])

    def test_multiple_routes_and_active_command_fail_closed(self):
        multiple = self.module.classify(self.snapshot(["T1A", "T2C"], head=True), "T1A", True)
        self.assertEqual("BLOCK", multiple["decision"])
        self.assertEqual("MULTIPLE_ENGAGED_ROUTES", multiple["reason"])
        with self.assertRaises(self.module.DecisionError):
            self.module.classify(self.snapshot(command="EXTRUDE_PROCESS"), "T1A", False)

    def test_capture_requires_effect_free_unchanged_evidence(self):
        records = [
            {"kind": "header", "effects": {"gcode": False, "remote_write": False, "service_action": False}},
            self.snapshot(head=True),
            {"kind": "footer", "configuration_unchanged": True},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.jsonl"
            path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
            result = self.module.classify_capture(path, "T1A", False)
        self.assertEqual("BLOCK", result["decision"])
        self.assertTrue(result["human_physical_verdict_required"])

    def test_live_ambiguous_evidence_is_technical_only_and_pinned(self):
        contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        evidence = json.loads((PACKAGE / "ambiguous-start-read-only-evidence.json").read_text(encoding="utf-8"))
        digest = hashlib.sha256((PACKAGE / "start_decision.py").read_bytes()).hexdigest()
        self.assertEqual(digest, contract["start_decision_adapter"]["program_sha256"])
        self.assertEqual("BLOCK", evidence["decision"]["result"])
        self.assertEqual("SEGMENT_PRESENT_WITHOUT_UNIQUE_ROUTE", evidence["decision"]["reason"])
        self.assertFalse(any(evidence["effects"].values()))
        self.assertIsNone(evidence["human_physical_verdict"])
        self.assertEqual("AWAITING_HUMAN_CONFIRMATION_NO_EFFECT_OBSERVED", evidence["qualification_status"])


if __name__ == "__main__":
    unittest.main()
