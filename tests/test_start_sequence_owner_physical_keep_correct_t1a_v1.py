import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "start-sequence-owner-physical-keep-correct-t1a-v1"


def load(name):
    spec = importlib.util.spec_from_file_location(name, PACKAGE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PhysicalKeepCorrectT1ATests(unittest.TestCase):
    def terminal_snapshot(self):
        return {
            "print": {"state": "complete"},
            "nozzle": {"target": 0.0},
            "bed": {"target": 0.0},
            "calibration": {
                "active_profile": "k1_p001_t055_r001_n11x11",
                "accepted_z_valid": 1,
                "accepted_z_offset": -0.04,
                "low_moves_armed": 0,
                "armed_mesh_profile": "none",
            },
            "owner": {"phase": "idle", "watchdog_armed": 0, "manual_clean_token": 0},
            "motion": {"homed_axes": ""},
            "cfs": {
                "state": "connect", "T1_state": "connect", "T2_state": "connect",
                "active_command": "", "engaged_routes": ["T1A"],
            },
        }

    def test_candidate_is_frozen(self):
        result = load("verify_candidate").verify()
        self.assertEqual(result["status"], "KEEP_CORRECT_T1A_PHYSICAL_CANDIDATE_OK")
        self.assertFalse(result["automatic_retry"])
        self.assertTrue(result["human_verdict_required"])

    def test_analyzer_accepts_complete_bounded_trace(self):
        entries = []
        for phase in load("analyze_capture").EXPECTED_PHASES:
            entries.append({
                "kind": "snapshot", "owner": {"phase": phase},
                "nozzle": {"target": 190}, "bed": {"target": 55},
                "cfs": {"engaged_routes": ["T1A"], "active_command": ""},
                "print": {"state": "printing"},
                "calibration": {
                    "active_profile": "k1_p001_t055_r001_n11x11",
                    "low_moves_armed": 1,
                    "armed_mesh_profile": "k1_p001_t055_r001_n11x11",
                },
                "motion": {"homed_axes": "xyz"},
            })
        entries[0]["nozzle"]["target"] = 0
        entries[0]["bed"]["target"] = 0
        entries.append({
            "kind": "snapshot",
            "owner": {"phase": "idle", "watchdog_armed": 0, "manual_clean_token": 0},
            "nozzle": {"target": 0}, "bed": {"target": 0},
            "cfs": {"engaged_routes": ["T1A"], "active_command": ""},
            "print": {"state": "complete"},
            "calibration": {
                "active_profile": "k1_p001_t055_r001_n11x11",
                "low_moves_armed": 0,
                "armed_mesh_profile": "none",
            },
            "motion": {"homed_axes": ""},
        })
        entries.extend([
            {"kind": "effect", "effect": "manual_clean_token_once"},
            {"kind": "effect", "effect": "print_start_once"},
            {"kind": "footer", "status": "KEEP_CORRECT_T1A_PHYSICAL_AUTOMATION_OK"},
        ])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "capture.jsonl"
            path.write_text("\n".join(json.dumps(item) for item in entries), encoding="utf-8")
            result = load("analyze_capture").analyze(path)
        self.assertEqual(result["status"], "KEEP_CORRECT_T1A_PHYSICAL_AUTOMATIC_OK")

    def test_analyzer_refuses_route_change(self):
        entry = {
            "kind": "snapshot", "owner": {"phase": "manual_clean_confirmed"},
            "nozzle": {"target": 0}, "bed": {"target": 0},
            "cfs": {"engaged_routes": [], "active_command": ""},
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "capture.jsonl"
            path.write_text(json.dumps(entry), encoding="utf-8")
            result = load("analyze_capture").analyze(path)
        self.assertEqual(result["status"], "KEEP_CORRECT_T1A_PHYSICAL_AUTOMATIC_KO")

    def test_remote_trial_has_only_bounded_effects(self):
        source = (PACKAGE / "remote_trial.py").read_text(encoding="utf-8")
        self.assertEqual(source.count('"effect": "print_start_once"'), 1)
        self.assertEqual(source.count('"effect": "manual_clean_token_once"'), 1)
        self.assertNotIn("BOX_EXTRUDE", source)
        self.assertNotIn("BED_MESH_CALIBRATE", source)

    def test_terminal_validator_requires_complete_safe_return(self):
        remote = load("remote_trial")
        remote.validate_terminal(self.terminal_snapshot())

    def test_terminal_validator_rejects_axes_still_homed(self):
        remote = load("remote_trial")
        snapshot = self.terminal_snapshot()
        snapshot["motion"]["homed_axes"] = "xyz"
        with self.assertRaisesRegex(remote.GateError, "axes_not_released_after_run"):
            remote.validate_terminal(snapshot)


if __name__ == "__main__":
    unittest.main()
