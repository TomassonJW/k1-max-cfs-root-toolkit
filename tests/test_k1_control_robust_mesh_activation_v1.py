from copy import deepcopy
import ast
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "robust-mesh-activation-v1"


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gate = load_module("robust_mesh_activation_v1_test", PACKAGE / "remote_gate.py")


def profile(rows, columns, digest):
    return {"rows": rows, "columns": [columns] * rows, "sha256": digest}


def safe_snapshot():
    robust = profile(6, 6, gate.ROBUST_PROFILE_SHA256)
    previous = profile(11, 11, gate.PREVIOUS_PROFILE_SHA256)
    return {
        "server": {"klippy_state": "ready", "failed_components": [], "warnings": []},
        "print": {"state": "standby", "filename_present": False},
        "heaters": {"extruder_target": 0.0, "bed_target": 0.0},
        "toolhead": {"homed_axes": "", "position": [0.0] * 4, "homing_origin": [0.0] * 4},
        "bed_mesh": {
            "profile_name": gate.PREVIOUS_PROFILE,
            "probed_matrix": previous,
            "mesh_matrix": profile(31, 31, "derived-not-authoritative"),
            "profiles": {
                gate.DEFAULT_PROFILE: profile(6, 6, gate.DEFAULT_PROFILE_SHA256),
                gate.ROBUST_PROFILE: robust,
                gate.PREVIOUS_PROFILE: previous,
            },
        },
        "box": {
            "state": "connect",
            "t_command": "",
            "T1": {"state": "connect", "filament": "None"},
            "T2": {"state": "connect", "filament": "None"},
            "T3": {"state": "None", "filament": "None"},
            "T4": {"state": "None", "filament": "None"},
        },
        "runtime": {
            "ready": 1,
            "session_active": 0,
            "accepted_z_valid": 1,
            "accepted_z_offset": -0.04,
            "low_moves_armed": 0,
        },
        "store": {"integrity": "ok"},
        "calibration_path": {"phase": "idle", "motion_armed": 0, "commit_ready": 0},
        "hashes": deepcopy(gate.EXPECTED_HASHES),
    }


class RobustMeshActivationV1Tests(unittest.TestCase):
    def test_contract_distinguishes_robust_and_composite_profiles(self):
        contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        self.assertEqual(gate.ROBUST_PROFILE, contract["profiles"]["target"]["id"])
        self.assertEqual(6, contract["profiles"]["target"]["rows"])
        self.assertEqual(gate.PREVIOUS_PROFILE, contract["profiles"]["expected_previous"]["id"])
        self.assertEqual(11, contract["profiles"]["expected_previous"]["rows"])
        self.assertFalse(contract["authority"]["goal_3_started_by_success"])
        self.assertEqual(
            contract["remote_program_sha256"],
            hashlib.sha256((PACKAGE / "remote_gate.py").read_bytes()).hexdigest(),
        )

    def test_live_preflight_evidence_is_pinned_and_read_only(self):
        evidence = json.loads((PACKAGE / "evidence-map.json").read_text(encoding="utf-8"))
        capture = ROOT / evidence["private_source"]["path"]
        self.assertTrue(capture.is_file())
        self.assertEqual(
            evidence["private_source"]["sha256"],
            hashlib.sha256(capture.read_bytes()).hexdigest(),
        )
        self.assertEqual("PREFLIGHT_OK", evidence["safe_result"]["preflight"])
        self.assertEqual([], evidence["safe_result"]["gcode_commands_attempted"])
        self.assertFalse(evidence["safe_result"]["remote_files_written"])

    def test_safe_preflight_accepts_only_the_expected_previous_profile(self):
        snapshot = safe_snapshot()
        gate.validate_active(snapshot, gate.PREVIOUS_PROFILE)
        with self.assertRaisesRegex(gate.GateError, "active_profile_drift"):
            gate.validate_active(snapshot, gate.ROBUST_PROFILE)

    def test_post_activation_requires_target_matrix_as_active_matrix(self):
        snapshot = safe_snapshot()
        snapshot["bed_mesh"]["profile_name"] = gate.ROBUST_PROFILE
        snapshot["bed_mesh"]["probed_matrix"] = deepcopy(
            snapshot["bed_mesh"]["profiles"][gate.ROBUST_PROFILE]
        )
        gate.validate_active(snapshot, gate.ROBUST_PROFILE)
        snapshot["bed_mesh"]["probed_matrix"]["sha256"] = "wrong"
        with self.assertRaisesRegex(gate.GateError, "active_probed_matrix_drift"):
            gate.validate_active(snapshot, gate.ROBUST_PROFILE)

    def test_busy_hot_homed_or_active_cfs_states_fail_closed(self):
        cases = (
            ("print", "state", "printing", "printer_not_standby"),
            ("heaters", "extruder_target", 220.0, "extruder_target_nonzero"),
            ("toolhead", "homed_axes", "xyz", "axes_still_homed"),
            ("box", "t_command", "T1A", "cfs_command_active"),
        )
        for section, key, value, error in cases:
            with self.subTest(error=error):
                snapshot = safe_snapshot()
                snapshot[section][key] = value
                with self.assertRaisesRegex(gate.GateError, error):
                    gate.validate_active(snapshot, gate.PREVIOUS_PROFILE)

    def test_matrix_profile_set_and_configuration_drift_fail_closed(self):
        mutations = []
        changed_matrix = safe_snapshot()
        changed_matrix["bed_mesh"]["profiles"][gate.ROBUST_PROFILE]["sha256"] = "wrong"
        mutations.append((changed_matrix, "robust_matrix_drift"))
        extra_profile = safe_snapshot()
        extra_profile["bed_mesh"]["profiles"]["unexpected"] = profile(1, 1, "x")
        mutations.append((extra_profile, "profile_set_drift"))
        changed_hash = safe_snapshot()
        first_path = next(iter(changed_hash["hashes"]))
        changed_hash["hashes"][first_path] = "wrong"
        mutations.append((changed_hash, "configuration_hash_drift"))
        for snapshot, error in mutations:
            with self.subTest(error=error):
                with self.assertRaisesRegex(gate.GateError, error):
                    gate.validate_active(snapshot, gate.PREVIOUS_PROFILE)

    def test_only_two_reviewed_runtime_commands_exist(self):
        source = (PACKAGE / "remote_gate.py").read_text(encoding="utf-8")
        self.assertIn('"BED_MESH_PROFILE LOAD=%s" % ROBUST_PROFILE', source)
        self.assertIn('"BED_MESH_PROFILE LOAD=%s" % PREVIOUS_PROFILE', source)
        for forbidden in ("TURN_OFF_HEATERS", "RESTART", "SAVE_CONFIG", "G28", "G29", "BOX_QUIT_MATERIAL"):
            self.assertNotIn(forbidden, source)

    def test_success_sends_the_primary_command_once_without_rollback(self):
        before = safe_snapshot()
        after = safe_snapshot()
        after["bed_mesh"]["profile_name"] = gate.ROBUST_PROFILE
        after["bed_mesh"]["probed_matrix"] = deepcopy(
            after["bed_mesh"]["profiles"][gate.ROBUST_PROFILE]
        )
        with patch.object(gate, "capture_snapshot", side_effect=[before, after]), patch.object(
            gate, "send_gcode", return_value={"response_received": True, "error": False}
        ) as sender:
            result = gate.run_activation()
        self.assertEqual("ACTIVATION_OK", result["status"])
        sender.assert_called_once_with(
            "BED_MESH_PROFILE LOAD=%s" % gate.ROBUST_PROFILE
        )

    def test_ambiguous_result_rolls_back_once_and_never_retries_primary(self):
        before = safe_snapshot()
        ambiguous = safe_snapshot()
        ambiguous["bed_mesh"]["profile_name"] = gate.ROBUST_PROFILE
        rollback = safe_snapshot()
        with patch.object(
            gate, "capture_snapshot", side_effect=[before, ambiguous, rollback]
        ), patch.object(
            gate, "send_gcode", return_value={"response_received": True, "error": False}
        ) as sender:
            result = gate.run_activation()
        self.assertEqual("ACTIVATION_KO_ROLLED_BACK", result["status"])
        self.assertEqual(
            [
                "BED_MESH_PROFILE LOAD=%s" % gate.ROBUST_PROFILE,
                "BED_MESH_PROFILE LOAD=%s" % gate.PREVIOUS_PROFILE,
            ],
            [call.args[0] for call in sender.call_args_list],
        )

    def test_runner_requires_exact_gate_and_does_not_copy_remote_files(self):
        source = (PACKAGE / "run_live.ps1").read_text(encoding="utf-8")
        self.assertIn("G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1", source)
        self.assertIn("-not $Execute", source)
        self.assertIn("$RemoteProgram | & ssh.exe", source)
        self.assertNotIn("scp.exe", source)
        self.assertNotIn("Invoke-WebRequest", source)

    def test_remote_program_parses_as_printer_python_3_8(self):
        source = (PACKAGE / "remote_gate.py").read_text(encoding="utf-8")
        ast.parse(source, filename="remote_gate.py", feature_version=(3, 8))


if __name__ == "__main__":
    unittest.main()
