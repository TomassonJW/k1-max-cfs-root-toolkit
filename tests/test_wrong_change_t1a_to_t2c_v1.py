import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "wrong-change-t1a-to-t2c-v1"


def load(name):
    spec = importlib.util.spec_from_file_location(name, PACKAGE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snap(route, nozzle_target, command=""):
    return {
        "kind": "snapshot",
        "cfs": {"engaged_routes": route, "active_command": command},
        "nozzle": {"target": nozzle_target},
        "bed": {"target": 0.0},
        "calibration": {"active_profile": "k1_p001_t055_r001_n11x11", "accepted_z_offset": -0.04},
    }


class WrongChangeT1AToT2CTests(unittest.TestCase):
    def test_candidate_is_passive_and_bounded(self):
        result = load("verify_candidate").verify()
        self.assertEqual(result["status"], "WRONG_CHANGE_T1A_TO_T2C_CANDIDATE_OK")
        self.assertFalse(result["observer_effect"])
        self.assertFalse(result["automatic_retry"])

    def test_observer_pins_r2_and_accepts_only_real_terminal_state_pairs(self):
        observer = (PACKAGE / "remote_observer.py").read_text(encoding="utf-8")
        contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        self.assertIn(contract["installed_start_owner"]["sha256"], observer)
        self.assertIn('item["print_state"] not in ("standby", "complete")', observer)
        self.assertIn('item["print_state"] == "standby" and item["filename_present"]', observer)
        self.assertIn('item["print_state"] == "complete" and not item["filename_present"]', observer)
        self.assertEqual("OFFLINE_READY_BLOCKED_BY_PRIOR_R2_PHYSICAL_TRIAL", contract["status"])

    def test_complete_unique_change_is_automatically_green(self):
        entries = [
            snap(["T1A"], 0.0),
            snap(["T1A"], 220.0, "change"),
            snap([], 220.0, "change"),
            snap(["T2C"], 220.0, "change"),
            snap(["T2C"], 0.0),
            {"kind": "footer", "status": "WRONG_CHANGE_OBSERVATION_OK"},
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "capture.jsonl"
            path.write_text("\n".join(json.dumps(item) for item in entries), encoding="utf-8")
            result = load("analyze_capture").analyze(path)
        self.assertEqual(result["status"], "WRONG_CHANGE_T1A_TO_T2C_AUTOMATIC_OK")
        self.assertTrue(result["human_visible_purge_verdict_required"])

    def test_other_route_is_rejected(self):
        entries = [
            snap(["T1A"], 220.0), snap([], 220.0), snap(["T2B"], 220.0), snap(["T2C"], 0.0),
            {"kind": "footer", "status": "WRONG_CHANGE_OBSERVATION_OK"},
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "capture.jsonl"
            path.write_text("\n".join(json.dumps(item) for item in entries), encoding="utf-8")
            result = load("analyze_capture").analyze(path)
        self.assertEqual(result["status"], "WRONG_CHANGE_T1A_TO_T2C_AUTOMATIC_KO")

    def test_duplicate_t2c_transition_is_rejected(self):
        entries = [
            snap(["T1A"], 220.0), snap([], 220.0), snap(["T2C"], 220.0),
            snap([], 220.0), snap(["T2C"], 0.0),
            {"kind": "footer", "status": "WRONG_CHANGE_OBSERVATION_OK"},
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "capture.jsonl"
            path.write_text("\n".join(json.dumps(item) for item in entries), encoding="utf-8")
            result = load("analyze_capture").analyze(path)
        self.assertEqual(result["status"], "WRONG_CHANGE_T1A_TO_T2C_AUTOMATIC_KO")


if __name__ == "__main__":
    unittest.main()
