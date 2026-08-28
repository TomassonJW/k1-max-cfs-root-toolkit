import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "start-sequence-t1a-route-v1"


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, PACKAGE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def snapshot(elapsed, routes, nozzle_target=0.0, xyz=None, command=""):
    return {
        "kind": "snapshot",
        "elapsed_s": elapsed,
        "print_state": "standby",
        "filename_present": False,
        "nozzle": {"temperature_c": 25.0, "target_c": nozzle_target, "can_extrude": False},
        "bed": {"temperature_c": 25.0, "target_c": 0.0},
        "motion": {
            "homed_axes": "",
            "gcode_position": xyz or [203.0, 273.0, 32.0, 0.0],
            "homing_origin": [0.0, 0.0, -0.04, 0.0],
        },
        "calibration": {
            "active_profile": "k1_p001_t055_r001_n11x11",
            "accepted_z_valid": 1,
            "accepted_z_offset": -0.04,
        },
        "start_owner": {"phase": "idle", "watchdog_armed": 0, "abort_latched": 0},
        "cfs": {
            "state": "connect",
            "active_command": command,
            "T1_state": "connect",
            "T2_state": "connect",
            "engaged_routes": routes,
        },
        "sensors": {"head": True, "after_cutter": True},
    }


def trace(final_nozzle_target=0.0):
    hashes = {"printer.cfg": "same"}
    return [
        {
            "kind": "header",
            "schema": 1,
            "mission": "G4-K1-CONTROL-START-SEQUENCE-T1A-ROUTE-V1",
            "hashes_before": hashes,
            "effects": {"gcode": False, "remote_write": False, "service_action": False},
            "operator_action": "stock_ui_load_T1A_once",
        },
        snapshot(0.0, []),
        snapshot(1.0, [], nozzle_target=220.0, command="T1A"),
        snapshot(2.0, ["T1A"], nozzle_target=220.0, command="T1A"),
        snapshot(3.0, ["T1A"], nozzle_target=final_nozzle_target),
        snapshot(4.0, ["T1A"], nozzle_target=final_nozzle_target),
        {
            "kind": "footer",
            "status": "T1A_ROUTE_OBSERVATION_OK",
            "configuration_unchanged": True,
            "hashes_after": hashes,
        },
    ]


class StartSequenceT1ARouteV1Tests(unittest.TestCase):
    def test_safe_single_transition_passes(self):
        analyzer = load_module("t1a_route_analyzer", "analyze_capture.py")
        result = analyzer.analyze_records(trace())
        self.assertEqual("START_SEQUENCE_T1A_ROUTE_V1_TECHNICAL_OK", result["status"])
        self.assertEqual([[], ["T1A"]], result["route_states"])
        self.assertEqual(1, result["route_transition_count"])
        self.assertTrue(result["xyz_unchanged"])
        self.assertFalse(result["observer_effect"])

    def test_nonzero_terminal_target_requires_safe_stop(self):
        analyzer = load_module("t1a_route_analyzer_hot", "analyze_capture.py")
        result = analyzer.analyze_records(trace(final_nozzle_target=220.0))
        self.assertEqual(
            "START_SEQUENCE_T1A_ROUTE_V1_SAFE_STOP_REQUIRED_HEATER_TARGET_NONZERO",
            result["status"],
        )

    def test_unexpected_route_is_rejected(self):
        analyzer = load_module("t1a_route_analyzer_wrong", "analyze_capture.py")
        records = trace()
        records[3]["cfs"]["engaged_routes"] = ["T2C"]
        with self.assertRaisesRegex(ValueError, "unexpected_or_ambiguous_route"):
            analyzer.analyze_records(records)

    def test_xyz_motion_is_rejected(self):
        analyzer = load_module("t1a_route_analyzer_motion", "analyze_capture.py")
        records = trace()
        records[3]["motion"]["gcode_position"] = [204.0, 273.0, 32.0, 0.0]
        with self.assertRaisesRegex(ValueError, "xyz_motion_observed"):
            analyzer.analyze_records(records)

    def test_route_replay_is_rejected(self):
        analyzer = load_module("t1a_route_analyzer_replay", "analyze_capture.py")
        records = trace()
        records.insert(-1, snapshot(3.5, []))
        with self.assertRaisesRegex(ValueError, "single_route_transition_not_proved"):
            analyzer.analyze_records(records)

    def test_candidate_has_no_automatic_effect_path(self):
        verifier = load_module("t1a_route_verifier", "verify_candidate.py")
        result = verifier.verify()
        self.assertEqual("START_SEQUENCE_T1A_ROUTE_V1_CANDIDATE_OK", result["status"])
        self.assertFalse(result["automatic_effect_connector"])
        self.assertEqual(1, result["maximum_attempts"])
        contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        self.assertFalse(contract["print_start"])
        self.assertTrue(contract["failure_policy"]["no_automatic_print_trial"])


if __name__ == "__main__":
    unittest.main()
