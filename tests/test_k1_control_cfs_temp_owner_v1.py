from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-temp-owner-v1"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CfsTempOwnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.observer = load_module("cfs_temp_owner_observer", PACKAGE / "observer.py")
        cls.analyzer = load_module("cfs_temp_owner_analyzer", PACKAGE / "analyze_observation.py")
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))

    def snapshot(self, elapsed: float = 0.0, routes=None, command="", nozzle_target=0.0):
        return {
            "kind": "snapshot",
            "elapsed_s": elapsed,
            "print_state": "standby",
            "filename_present": False,
            "nozzle": {"temperature_c": 30.0, "target_c": nozzle_target, "can_extrude": False},
            "bed": {"temperature_c": 30.0, "target_c": 0.0},
            "motion": {"homed_axes": "xyz", "gcode_position": [203.0, 273.0, 35.0, 0.0], "homing_origin": [0, 0, 0, 0]},
            "calibration": {"active_profile": "k1_p001_t055_r001_n11x11", "accepted_z_valid": 1, "accepted_z_offset": -0.04},
            "cfs": {"state": "connect", "active_command": command, "T1_state": "connect", "T2_state": "connect", "engaged_routes": routes or []},
            "sensors": {"head": False, "after_cutter": False},
        }

    def capture_records(self):
        hashes = {"a": "b"}
        snapshots = [
            self.snapshot(0.0),
            self.snapshot(0.5, ["T2C"], "EXTRUDE_PROCESS", 220.0),
            self.snapshot(1.0, [], "", 0.0),
        ]
        return [
            {"kind": "header", "schema": 1, "mission": "G4-K1-CONTROL-CFS-TEMP-OWNER-V1", "checkpoint": "CLEANING_PREP", "duration_s": 5.0, "poll_interval_s": 0.5, "hashes_before": hashes, "effects": {"gcode": False, "remote_write": False, "service_action": False}},
            *snapshots,
            {"kind": "footer", "status": "CFS_TEMP_OWNER_OBSERVATION_OK", "snapshot_count": len(snapshots), "hashes_after": hashes, "configuration_unchanged": True},
        ]

    def analyze_records(self, records):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.jsonl"
            path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
            return self.analyzer.analyze(path)

    def test_observer_has_only_get_and_no_command_transport(self):
        source = (PACKAGE / "observer.py").read_text(encoding="utf-8")
        self.assertIn('method="GET"', source)
        for forbidden in ("gcode/script", "urllib.parse.urlencode", "socket.socket", "subprocess", "open(path, \"w\""):
            self.assertNotIn(forbidden, source)

    def test_safe_snapshot_exports_routes_but_not_identity(self):
        payload = {"result": {"status": {
            "print_stats": {"state": "standby", "filename": ""},
            "extruder": {"temperature": 30.0, "target": 0.0, "can_extrude": False},
            "heater_bed": {"temperature": 30.0, "target": 0.0},
            "toolhead": {"homed_axes": "xyz"},
            "gcode_move": {"gcode_position": [1, 2, 3, 0], "homing_origin": [0, 0, 0, 0]},
            "bed_mesh": {"profile_name": "k1_p001_t055_r001_n11x11"},
            "gcode_macro KCTRL_STATE": {"accepted_z_valid": 1, "accepted_z_offset": -0.04},
            "box": {"state": "connect", "t_command": "", "sn": "secret", "T1": {"state": "connect", "filament": "A", "uuid": "secret"}, "T2": {"state": "connect", "filament": "None"}},
            "filament_switch_sensor filament_sensor": {"filament_detected": True},
            "filament_switch_sensor filament_sensor_2": {"filament_detected": False},
        }}}
        snapshot = self.observer.safe_snapshot(0.0, payload)
        rendered = json.dumps(snapshot, sort_keys=True)
        self.assertEqual(["T1A"], snapshot["cfs"]["engaged_routes"])
        self.assertNotIn("secret", rendered)
        self.assertNotIn('"uuid"', rendered)
        self.assertNotIn('"sn"', rendered)

    def test_analyzer_reports_real_transitions_and_terminal_state(self):
        result = self.analyze_records(self.capture_records())
        self.assertEqual("CFS_TEMP_OWNER_ANALYSIS_OK", result["status"])
        self.assertEqual([[], ["T2C"], []], result["route_states"])
        self.assertEqual(["", "EXTRUDE_PROCESS", ""], result["active_command_states"])
        self.assertEqual(220.0, result["maximum_nozzle_target_c"])
        self.assertTrue(result["terminal_heater_targets_zero"])
        self.assertFalse(result["observer_effect"])

    def test_analyzer_rejects_identity_configuration_drift_count_and_time(self):
        variants = []
        identity = self.capture_records()
        identity[1]["uuid"] = "secret"
        variants.append(identity)
        drift = self.capture_records()
        drift[-1]["hashes_after"] = {"a": "changed"}
        drift[-1]["configuration_unchanged"] = False
        variants.append(drift)
        count = self.capture_records()
        count[-1]["snapshot_count"] = 99
        variants.append(count)
        elapsed = self.capture_records()
        elapsed[2]["elapsed_s"] = 2.0
        variants.append(elapsed)
        for records in variants:
            with self.assertRaises(self.analyzer.AnalysisError):
                self.analyze_records(records)

    def test_contract_and_runner_are_pinned_and_effect_free(self):
        observer = self.contract["observer"]
        self.assertEqual(sha256(PACKAGE / "observer.py"), observer["program_sha256"])
        self.assertEqual(sha256(PACKAGE / "analyze_observation.py"), observer["analyzer_sha256"])
        self.assertEqual(sha256(PACKAGE / "capture_observation.ps1"), observer["runner_sha256"])
        runner = (PACKAGE / "capture_observation.ps1").read_text(encoding="utf-8")
        self.assertIn(observer["program_sha256"], runner)
        self.assertIn("cfs_action_by_observer = $false", runner)
        self.assertNotIn("-Execute", runner)

    def test_checkpoint_set_in_code_runner_and_contract_is_identical(self):
        runner = (PACKAGE / "capture_observation.ps1").read_text(encoding="utf-8")
        self.assertEqual(set(self.contract["checkpoints"]), set(self.observer.ALLOWED_CHECKPOINTS))
        for checkpoint in self.contract["checkpoints"]:
            self.assertIn(checkpoint, runner)

    def test_live_baseline_is_read_only_and_not_a_physical_verdict(self):
        baseline = self.contract["live_read_only_baseline"]
        self.assertEqual("CFS_TEMP_OWNER_ANALYSIS_OK", baseline["status"])
        self.assertEqual(8, baseline["snapshot_count"])
        self.assertIsNone(baseline["human_physical_verdict"])
        self.assertFalse(any(baseline["effects"].values()))
        effects = dict(self.contract["effects"])
        self.assertTrue(effects.pop("printer_connection"))
        self.assertFalse(any(effects.values()))

    def test_analyzer_marks_two_simultaneous_routes_as_ambiguous(self):
        records = self.capture_records()
        records[2]["cfs"]["engaged_routes"] = ["T1A", "T2C"]
        result = self.analyze_records(records)
        self.assertTrue(result["ambiguous_route_observed"])


if __name__ == "__main__":
    unittest.main()
