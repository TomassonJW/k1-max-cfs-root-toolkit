import ast
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "return-t2c-to-t1a-v1"


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


observer = load_module("return_t2c_to_t1a_observer_v1", PACKAGE / "remote_observer.py")
analyzer = load_module("return_t2c_to_t1a_analyzer_v1", PACKAGE / "analyze_capture.py")


def snap(route, nozzle_target, command=""):
    return {
        "kind": "snapshot",
        "cfs": {"engaged_routes": route, "active_command": command},
        "nozzle": {"target": nozzle_target},
        "bed": {"target": 0.0},
        "calibration": {
            "active_profile": "k1_p001_t055_r001_n11x11",
            "accepted_z_offset": -0.04,
            "low_moves_armed": 0,
        },
        "owner": {"phase": "idle"},
    }


def analyze(entries):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "capture.jsonl"
        path.write_text("\n".join(json.dumps(item) for item in entries), encoding="utf-8")
        return analyzer.analyze(path)


class ReturnT2CToT1AV1Tests(unittest.TestCase):
    def test_contract_pins_passive_observer_and_routes(self):
        contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        self.assertEqual(observer.MISSION, contract["mission"])
        self.assertEqual("T2C", contract["starting_route"])
        self.assertEqual("T1A", contract["target_route"])
        self.assertEqual(
            hashlib.sha256((PACKAGE / "remote_observer.py").read_bytes()).hexdigest(),
            contract["observer"]["sha256"],
        )
        self.assertFalse(contract["production_authorized"])

    def test_observer_has_get_only_and_no_effect_surface(self):
        source = (PACKAGE / "remote_observer.py").read_text(encoding="utf-8")
        self.assertIn('method="GET"', source)
        for forbidden in ('method="POST"', "/printer/gcode/script", "socket.socket", "subprocess", "os.system"):
            self.assertNotIn(forbidden, source)

    def test_complete_reverse_transition_is_automatically_green(self):
        entries = [
            snap(["T2C"], 0.0),
            snap(["T2C"], 220.0, "change"),
            snap([], 220.0, "change"),
            snap(["T1A"], 220.0, "change"),
            snap(["T1A"], 0.0),
            {"kind": "footer", "status": "RETURN_T2C_TO_T1A_OBSERVATION_OK", "stable_terminal_target_reads": 4},
        ]
        result = analyze(entries)
        self.assertEqual("RETURN_T2C_TO_T1A_AUTOMATIC_OK", result["status"])
        self.assertTrue(result["human_visible_purge_verdict_required"])

    def test_wrong_route_duplicate_target_or_hot_terminal_is_rejected(self):
        variants = [
            [snap(["T2C"], 220.0), snap(["T1A"], 220.0), snap(["T1A"], 0.0)],
            [snap(["T2C"], 220.0), snap([], 220.0), snap(["T2B"], 220.0), snap(["T1A"], 0.0)],
            [snap(["T2C"], 220.0), snap([], 220.0), snap(["T1A"], 220.0), snap([], 220.0), snap(["T1A"], 0.0)],
            [snap(["T2C"], 220.0), snap([], 220.0), snap(["T1A"], 220.0)],
        ]
        footer = {"kind": "footer", "status": "RETURN_T2C_TO_T1A_OBSERVATION_OK", "stable_terminal_target_reads": 4}
        for entries in variants:
            with self.subTest(entries=entries):
                self.assertEqual("RETURN_T2C_TO_T1A_AUTOMATIC_KO", analyze(entries + [footer])["status"])

    def test_runner_reserves_exact_gate_for_observation_and_confirms_both_identities(self):
        runner = (PACKAGE / "capture_gate.ps1").read_text(encoding="utf-8")
        self.assertIn("$Action -eq 'Observe' -and (-not $Execute", runner)
        self.assertIn("HumanConfirmedT2CIdentity", runner)
        self.assertIn("HumanConfirmedT1AIdentity", runner)
        self.assertIn("$Program | & ssh.exe", runner)
        self.assertNotIn("scp.exe", runner)

    def test_python_sources_parse_as_3_8(self):
        for name in ("remote_observer.py", "analyze_capture.py"):
            ast.parse((PACKAGE / name).read_text(encoding="utf-8"), filename=name, feature_version=(3, 8))


if __name__ == "__main__":
    unittest.main()
