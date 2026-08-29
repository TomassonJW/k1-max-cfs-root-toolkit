from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "job-lifecycle-observer-v1"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class JobLifecycleObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observer = load_module("job_lifecycle_observer", PACKAGE / "observer.py")
        cls.analyzer = load_module("job_lifecycle_analyzer", PACKAGE / "analyze_observation.py")
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))

    def snapshot(self, elapsed=0.0, state="standby", paused=False, active=False, routes=None, command="", nozzle=0.0, bed=0.0):
        return {
            "kind": "snapshot",
            "elapsed_s": elapsed,
            "job": {
                "print_state": state,
                "total_duration_s": elapsed,
                "print_duration_s": elapsed,
                "filament_used_mm": elapsed,
                "power_loss": 0,
                "reported_z_mm": 1.0,
                "is_paused": paused,
                "virtual_sd_active": active,
                "progress": 0.5 if active else 0.0,
                "file_position": 50 if active else 0,
                "file_size": 100 if active else 0,
                "first_layer_stop": False,
                "layer": 1 if active else 0,
                "layer_count": 2 if active else 0,
                "run_distance_mm": 1.0 if active else 0.0,
                "idle_state": "Printing" if active else "Ready",
                "idle_printing_time_s": elapsed,
            },
            "heaters": {"nozzle_temperature_c": 30.0, "nozzle_target_c": nozzle, "nozzle_can_extrude": nozzle >= 170, "bed_temperature_c": 30.0, "bed_target_c": bed},
            "motion": {"homed_axes": "xyz", "toolhead_position": [1, 2, 3, 0], "gcode_position": [1, 2, 3, 0], "homing_origin": [0, 0, 0, 0]},
            "calibration": {"active_profile": "k1_p001_t055_r001_n11x11", "accepted_z_valid": 1, "accepted_z_offset": -0.04},
            "cfs": {"state": "connect", "active_command": command, "T1_state": "connect", "T2_state": "connect", "engaged_routes": routes or []},
            "sensors": {"head": bool(routes), "after_cutter": bool(routes)},
        }

    def records(self):
        hashes = {"config": "hash"}
        snapshots = [
            self.snapshot(0.0),
            self.snapshot(0.25, "printing", False, True, ["T1A"], "", 220.0, 55.0),
            self.snapshot(0.5, "paused", True, True, ["T1A"]),
            self.snapshot(0.75, "printing", False, True, ["T2C"], "EXTRUDE_PROCESS", 230.0, 55.0),
            self.snapshot(1.0),
        ]
        return [
            {"kind": "header", "schema": 1, "mission": "G4-K1-CONTROL-JOB-LIFECYCLE-OBSERVER-V1", "checkpoint": "FULL_CYCLE", "duration_s": 5.0, "poll_interval_s": 0.25, "hashes_before": hashes, "effects": {"gcode": False, "remote_write": False, "service_action": False}},
            *snapshots,
            {"kind": "footer", "status": "JOB_LIFECYCLE_OBSERVATION_OK", "snapshot_count": len(snapshots), "hashes_after": hashes, "configuration_unchanged": True},
        ]

    def analyze(self, records):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.jsonl"
            path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
            return self.analyzer.analyze(path)

    def test_observer_has_only_get_and_no_command_transport(self):
        source = (PACKAGE / "observer.py").read_text(encoding="utf-8")
        self.assertIn('method="GET"', source)
        for forbidden in ("gcode/script", "socket.socket", "subprocess", "urlencode", "open(path, \"w\""):
            self.assertNotIn(forbidden, source)

    def test_safe_snapshot_drops_filename_and_identity(self):
        payload = {"result": {"status": {
            "print_stats": {"state": "printing", "filename": "private.gcode", "total_duration": 1.0, "print_duration": 1.0, "filament_used": 1.0, "power_loss": 0, "z_pos": 1.0},
            "pause_resume": {"is_paused": False},
            "virtual_sdcard": {"file_path": "/secret/private.gcode", "progress": 0.1, "is_active": True, "file_position": 1, "file_size": 10, "first_layer_stop": False, "layer": 1, "layer_count": 2, "run_dis": 1.0},
            "idle_timeout": {"state": "Printing", "printing_time": 1.0},
            "extruder": {"temperature": 220.0, "target": 220.0, "can_extrude": True},
            "heater_bed": {"temperature": 55.0, "target": 55.0},
            "toolhead": {"homed_axes": "xyz", "position": [1, 2, 3, 0]},
            "gcode_move": {"gcode_position": [1, 2, 3, 0], "homing_origin": [0, 0, 0, 0]},
            "bed_mesh": {"profile_name": "k1_p001_t055_r001_n11x11"},
            "gcode_macro KCTRL_STATE": {"accepted_z_valid": 1, "accepted_z_offset": -0.04},
            "box": {"state": "connect", "t_command": "", "uuid": "secret", "T1": {"state": "connect", "filament": "A"}, "T2": {"state": "connect", "filament": "None"}},
            "filament_switch_sensor filament_sensor": {"filament_detected": True},
            "filament_switch_sensor filament_sensor_2": {"filament_detected": True},
        }}}
        snapshot = self.observer.safe_snapshot(0.0, payload)
        rendered = json.dumps(snapshot, sort_keys=True)
        self.assertNotIn("private.gcode", rendered)
        self.assertNotIn('"filename"', rendered)
        self.assertNotIn('"uuid"', rendered)
        self.assertEqual(["T1A"], snapshot["cfs"]["engaged_routes"])

    def test_analyzer_reports_pause_route_heat_and_terminal_sequences(self):
        result = self.analyze(self.records())
        self.assertEqual(["standby", "printing", "paused", "printing", "standby"], result["print_state_sequence"])
        self.assertEqual([False, True, False], result["pause_state_sequence"])
        self.assertEqual([[], ["T1A"], ["T2C"], []], result["route_states"])
        self.assertEqual(230.0, result["maximum_nozzle_target_c"])
        self.assertTrue(result["terminal_heater_targets_zero"])
        self.assertTrue(result["mesh_and_z_stable"])
        self.assertFalse(result["observer_effect"])

    def test_analyzer_does_not_turn_telemetry_into_human_verdict(self):
        result = self.analyze(self.records())
        self.assertTrue(result["human_physical_verdict_required"])
        self.assertNotIn("physical_verdict", result)

    def test_analyzer_rejects_identity_configuration_count_and_time_drift(self):
        variants = []
        identity = self.records()
        identity[1]["filename"] = "secret"
        variants.append(identity)
        drift = self.records()
        drift[-1]["hashes_after"] = {"config": "changed"}
        variants.append(drift)
        count = self.records()
        count[-1]["snapshot_count"] = 99
        variants.append(count)
        elapsed = self.records()
        elapsed[2]["elapsed_s"] = 9.0
        variants.append(elapsed)
        for records in variants:
            with self.assertRaises(self.analyzer.AnalysisError):
                self.analyze(records)

    def test_ambiguous_routes_are_reported_not_hidden(self):
        records = self.records()
        records[2]["cfs"]["engaged_routes"] = ["T1A", "T2C"]
        self.assertTrue(self.analyze(records)["ambiguous_route_observed"])

    def test_checkpoint_set_is_identical_in_code_contract_and_runner(self):
        runner = (PACKAGE / "capture_observation.ps1").read_text(encoding="utf-8")
        self.assertEqual(set(self.contract["checkpoints"]), set(self.observer.ALLOWED_CHECKPOINTS))
        for checkpoint in self.contract["checkpoints"]:
            self.assertIn(checkpoint, runner)

    def test_r2_hash_and_checkpoint_specific_entries_are_pinned(self):
        source = (PACKAGE / "observer.py").read_text(encoding="utf-8")
        runner = (PACKAGE / "capture_observation.ps1").read_text(encoding="utf-8")
        self.assertIn(self.contract["installed_start_owner"]["sha256"], source)
        self.assertIn('checkpoint == "FULL_CYCLE"', source)
        self.assertIn('checkpoint == "DISENGAGE"', source)
        self.assertIn('state not in ("printing", "paused")', source)
        for guard in ("-not $Execute", "$Gate -cne $Mission", "-not $HumanPresent", "-not $ImmediateStopAvailable"):
            self.assertIn(guard, runner)

    def test_contract_and_runner_are_pinned(self):
        observer = self.contract["observer"]
        self.assertEqual(sha256(PACKAGE / "observer.py"), observer["program_sha256"])
        self.assertEqual(sha256(PACKAGE / "analyze_observation.py"), observer["analyzer_sha256"])
        self.assertEqual(sha256(PACKAGE / "capture_observation.ps1"), observer["runner_sha256"])
        runner = (PACKAGE / "capture_observation.ps1").read_text(encoding="utf-8")
        self.assertIn(observer["program_sha256"], runner)

    def test_live_baseline_is_effect_free(self):
        baseline = self.contract["live_read_only_baseline"]
        self.assertEqual(11, baseline["snapshot_count"])
        self.assertTrue(baseline["configuration_unchanged"])
        self.assertFalse(baseline["observer_effect"])
        physical = dict(self.contract["effects"])
        physical.pop("printer_connection")
        self.assertFalse(any(physical.values()))


if __name__ == "__main__":
    unittest.main()
