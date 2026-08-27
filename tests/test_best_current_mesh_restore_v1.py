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
PACKAGE = ROOT / "packages" / "k1-control-v1" / "best-current-mesh-restore-v1"


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gate = load_module("best_current_mesh_restore_v1_test", PACKAGE / "remote_gate.py")


def profile(rows, digest):
    return {"rows": rows, "columns": [rows] * rows, "sha256": digest}


def safe_snapshot():
    daily = profile(6, gate.DAILY_6X6_SHA256)
    best = profile(11, gate.BEST_CURRENT_SHA256)
    return {
        "server": {"klippy_state": "ready", "failed_components": [], "warnings": []},
        "print": {"state": "standby", "filename_present": False},
        "heaters": {"extruder_target": 0.0, "bed_target": 0.0},
        "toolhead": {"homed_axes": "", "position": [0.0] * 4, "homing_origin": [0.0] * 4},
        "bed_mesh": {
            "profile_name": gate.DAILY_6X6_PROFILE,
            "probed_matrix": daily,
            "profiles": {
                gate.DEFAULT_PROFILE: profile(6, gate.DEFAULT_SHA256),
                gate.DAILY_6X6_PROFILE: daily,
                gate.BEST_CURRENT_PROFILE: best,
            },
        },
        "box": {
            "state": "connect",
            "t_command": "",
            "T1": {"state": "connect", "filament": "None"},
            "T2": {"state": "connect", "filament": "None"},
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


class BestCurrentMeshRestoreV1Tests(unittest.TestCase):
    def test_contract_corrects_the_nomenclature(self):
        contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        names = contract["nomenclature"]
        self.assertTrue(names["all_current_profiles_have_edge_defects"])
        self.assertEqual(gate.DAILY_6X6_PROFILE, names["daily_6x6_profile"])
        self.assertEqual(gate.BEST_CURRENT_PROFILE, names["best_current_observed_profile"])
        self.assertFalse(names["robust_profile_currently_exists"])
        self.assertEqual(
            contract["remote_program_sha256"],
            hashlib.sha256((PACKAGE / "remote_gate.py").read_bytes()).hexdigest(),
        )

    def test_live_evidence_is_pinned_sanitized_and_confirms_11x11(self):
        evidence = json.loads((PACKAGE / "evidence-map.json").read_text(encoding="utf-8"))
        for source in evidence["private_sources"].values():
            capture = ROOT / source["path"]
            self.assertTrue(capture.is_file())
            self.assertEqual(source["sha256"], hashlib.sha256(capture.read_bytes()).hexdigest())
            self.assertFalse(source["versioned"])
            self.assertFalse(source["identity_values_exported"])

        restore_lines = (
            ROOT / evidence["private_sources"]["restore"]["path"]
        ).read_text(encoding="utf-8-sig").splitlines()
        validation_lines = (
            ROOT / evidence["private_sources"]["independent_validation"]["path"]
        ).read_text(encoding="utf-8-sig").splitlines()
        self.assertEqual("BEST_CURRENT_MESH_RESTORE_V1_RESTORE_OK", restore_lines[1])
        self.assertEqual("K1_READ_ONLY_QUALIFICATION_CAPTURE_V1_OK", validation_lines[1])

        restored = json.loads(restore_lines[0])
        self.assertEqual("RESTORE_OK", restored["status"])
        self.assertEqual(gate.DAILY_6X6_PROFILE, restored["before"]["bed_mesh"]["profile_name"])
        self.assertEqual(gate.BEST_CURRENT_PROFILE, restored["after"]["bed_mesh"]["profile_name"])
        self.assertEqual(gate.BEST_CURRENT_SHA256, restored["after"]["bed_mesh"]["probed_matrix"]["sha256"])
        self.assertIsNone(restored["rollback"])

        independent = json.loads(validation_lines[0])
        self.assertTrue(independent["response_schema_stable"])
        self.assertEqual(independent["hashes_before"], independent["hashes_after"])
        for snapshot in independent["snapshots"]:
            self.assertEqual(gate.BEST_CURRENT_PROFILE, snapshot["bed_mesh"]["profile_name"])
            self.assertEqual(gate.BEST_CURRENT_SHA256, snapshot["bed_mesh"]["probed_matrix"]["sha256"])

    def test_preflight_requires_the_current_6x6_state(self):
        gate.validate_active(safe_snapshot(), gate.DAILY_6X6_PROFILE)
        with self.assertRaisesRegex(gate.GateError, "active_profile_drift"):
            gate.validate_active(safe_snapshot(), gate.BEST_CURRENT_PROFILE)

    def test_success_restores_11x11_once_without_rollback(self):
        before = safe_snapshot()
        after = safe_snapshot()
        after["bed_mesh"]["profile_name"] = gate.BEST_CURRENT_PROFILE
        after["bed_mesh"]["probed_matrix"] = deepcopy(
            after["bed_mesh"]["profiles"][gate.BEST_CURRENT_PROFILE]
        )
        with patch.object(gate, "capture_snapshot", side_effect=[before, after]), patch.object(
            gate, "send_gcode"
        ) as sender:
            result = gate.run_restore()
        self.assertEqual("RESTORE_OK", result["status"])
        self.assertIsNone(result["rollback"])
        sender.assert_called_once_with(
            "BED_MESH_PROFILE LOAD=%s" % gate.BEST_CURRENT_PROFILE
        )

    def test_ambiguous_result_rolls_back_once_and_never_retries_11x11(self):
        before = safe_snapshot()
        ambiguous = safe_snapshot()
        ambiguous["bed_mesh"]["profile_name"] = gate.BEST_CURRENT_PROFILE
        with patch.object(
            gate, "capture_snapshot", side_effect=[before, ambiguous, safe_snapshot()]
        ), patch.object(gate, "send_gcode") as sender:
            result = gate.run_restore()
        self.assertEqual("RESTORE_KO_ROLLED_BACK", result["status"])
        self.assertEqual(
            [
                "BED_MESH_PROFILE LOAD=%s" % gate.BEST_CURRENT_PROFILE,
                "BED_MESH_PROFILE LOAD=%s" % gate.DAILY_6X6_PROFILE,
            ],
            [call.args[0] for call in sender.call_args_list],
        )

    def test_hot_busy_homed_or_active_cfs_states_fail_closed(self):
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
                    gate.validate_active(snapshot, gate.DAILY_6X6_PROFILE)

    def test_runner_requires_exact_gate_and_streams_without_remote_file(self):
        source = (PACKAGE / "run_live.ps1").read_text(encoding="utf-8")
        self.assertIn("G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-V1", source)
        self.assertIn("-not $Execute", source)
        self.assertIn("$RemoteProgram | & ssh.exe", source)
        self.assertNotIn("scp.exe", source)

    def test_safe_projection_does_not_export_cfs_identity_fields(self):
        source = (PACKAGE / "remote_gate.py").read_text(encoding="utf-8")
        self.assertNotIn('"T1": child(box, "T1")', source)
        self.assertNotIn('"T2": child(box, "T2")', source)
        self.assertNotIn('.get("sn")', source)
        self.assertNotIn('.get("uuid")', source)

    def test_remote_program_parses_as_printer_python_3_8(self):
        source = (PACKAGE / "remote_gate.py").read_text(encoding="utf-8")
        ast.parse(source, filename="remote_gate.py", feature_version=(3, 8))


if __name__ == "__main__":
    unittest.main()
