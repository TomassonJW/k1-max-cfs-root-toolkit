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
PACKAGE = (
    ROOT
    / "packages"
    / "k1-control-v1"
    / "best-current-mesh-restore-after-power-cycle-v1"
)


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gate = load_module(
    "best_current_mesh_restore_after_power_cycle_v1_test",
    PACKAGE / "remote_gate.py",
)


def profile(rows, digest):
    return {"rows": rows, "columns": [rows] * rows, "sha256": digest}


def safe_snapshot(active_profile=gate.DEFAULT_PROFILE):
    default = profile(6, gate.DEFAULT_SHA256)
    daily = profile(6, gate.DAILY_6X6_SHA256)
    best = profile(11, gate.BEST_CURRENT_SHA256)
    profiles = {
        gate.DEFAULT_PROFILE: default,
        gate.DAILY_6X6_PROFILE: daily,
        gate.BEST_CURRENT_PROFILE: best,
    }
    return {
        "server": {"klippy_state": "ready", "failed_components": [], "warnings": []},
        "print": {"state": "standby", "filename_present": False},
        "heaters": {"extruder_target": 0.0, "bed_target": 0.0},
        "toolhead": {"homed_axes": "", "position": [0.0] * 4, "homing_origin": [0.0] * 4},
        "bed_mesh": {
            "profile_name": active_profile,
            "probed_matrix": deepcopy(profiles[active_profile]),
            "profiles": profiles,
        },
        "cfs": {
            "state": "connect",
            "active_command": "",
            "T1_state": "connect",
            "T2_state": "connect",
            "engaged_routes": ["T1A"],
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
        "start_owner": {"phase": "idle", "watchdog_armed": 0, "manual_clean_token": 0},
        "hashes": deepcopy(gate.EXPECTED_HASHES),
    }


class BestCurrentMeshRestoreAfterPowerCycleV1Tests(unittest.TestCase):
    def test_contract_pins_program_and_post_power_cycle_boundary(self):
        contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        self.assertEqual(gate.MISSION, contract["contract_id"])
        self.assertEqual(list(gate.ALLOWED_PRIOR_PROFILES), contract["preflight"]["accepted_initial_profiles"])
        self.assertEqual("T1A", contract["preflight"]["required_unique_route"])
        self.assertEqual(
            contract["remote_program_sha256"],
            hashlib.sha256((PACKAGE / "remote_gate.py").read_bytes()).hexdigest(),
        )

    def test_default_and_daily_6x6_are_the_only_allowed_prior_profiles(self):
        self.assertEqual(gate.DEFAULT_PROFILE, gate.validate_prior(safe_snapshot()))
        self.assertEqual(
            gate.DAILY_6X6_PROFILE,
            gate.validate_prior(safe_snapshot(gate.DAILY_6X6_PROFILE)),
        )
        with self.assertRaisesRegex(gate.GateError, "prior_profile_not_allowed"):
            gate.validate_prior(safe_snapshot(gate.BEST_CURRENT_PROFILE))

    def test_success_from_default_loads_11x11_once_without_rollback(self):
        before = safe_snapshot(gate.DEFAULT_PROFILE)
        after = safe_snapshot(gate.BEST_CURRENT_PROFILE)
        with patch.object(gate, "capture_snapshot", side_effect=[before, after]), patch.object(
            gate, "send_gcode"
        ) as sender:
            result = gate.run_restore()
        self.assertEqual("RESTORE_OK", result["status"])
        self.assertEqual(gate.DEFAULT_PROFILE, result["prior_profile"])
        self.assertIsNone(result["rollback"])
        sender.assert_called_once_with("BED_MESH_PROFILE LOAD=%s" % gate.BEST_CURRENT_PROFILE)

    def test_success_from_daily_6x6_loads_11x11_once(self):
        before = safe_snapshot(gate.DAILY_6X6_PROFILE)
        after = safe_snapshot(gate.BEST_CURRENT_PROFILE)
        with patch.object(gate, "capture_snapshot", side_effect=[before, after]), patch.object(
            gate, "send_gcode"
        ) as sender:
            result = gate.run_restore()
        self.assertEqual("RESTORE_OK", result["status"])
        self.assertEqual(gate.DAILY_6X6_PROFILE, result["prior_profile"])
        self.assertEqual(1, sender.call_count)

    def test_ambiguous_result_rolls_back_once_to_exact_default(self):
        before = safe_snapshot(gate.DEFAULT_PROFILE)
        ambiguous = safe_snapshot(gate.BEST_CURRENT_PROFILE)
        ambiguous["bed_mesh"]["probed_matrix"] = deepcopy(
            ambiguous["bed_mesh"]["profiles"][gate.DEFAULT_PROFILE]
        )
        rollback = safe_snapshot(gate.DEFAULT_PROFILE)
        with patch.object(
            gate, "capture_snapshot", side_effect=[before, ambiguous, rollback]
        ), patch.object(gate, "send_gcode") as sender:
            result = gate.run_restore()
        self.assertEqual("RESTORE_KO_ROLLED_BACK", result["status"])
        self.assertEqual(
            [
                "BED_MESH_PROFILE LOAD=%s" % gate.BEST_CURRENT_PROFILE,
                "BED_MESH_PROFILE LOAD=%s" % gate.DEFAULT_PROFILE,
            ],
            [call.args[0] for call in sender.call_args_list],
        )

    def test_ambiguous_result_rolls_back_once_to_exact_daily_6x6(self):
        before = safe_snapshot(gate.DAILY_6X6_PROFILE)
        ambiguous = safe_snapshot(gate.BEST_CURRENT_PROFILE)
        ambiguous["bed_mesh"]["probed_matrix"] = deepcopy(
            ambiguous["bed_mesh"]["profiles"][gate.DAILY_6X6_PROFILE]
        )
        rollback = safe_snapshot(gate.DAILY_6X6_PROFILE)
        with patch.object(
            gate, "capture_snapshot", side_effect=[before, ambiguous, rollback]
        ), patch.object(gate, "send_gcode") as sender:
            result = gate.run_restore()
        self.assertEqual("RESTORE_KO_ROLLED_BACK", result["status"])
        self.assertEqual(
            "BED_MESH_PROFILE LOAD=%s" % gate.DAILY_6X6_PROFILE,
            sender.call_args_list[1].args[0],
        )

    def test_no_route_wrong_route_or_multiple_routes_fail_closed(self):
        for routes in ([], ["T2A"], ["T1A", "T2A"]):
            with self.subTest(routes=routes):
                snapshot = safe_snapshot()
                snapshot["cfs"]["engaged_routes"] = routes
                with self.assertRaisesRegex(gate.GateError, "t1a_route_not_unique"):
                    gate.validate_prior(snapshot)

    def test_hot_busy_cfs_active_or_owner_active_fail_closed(self):
        cases = (
            ("print", "state", "printing", "printer_not_standby"),
            ("heaters", "extruder_target", 220.0, "extruder_target_nonzero"),
            ("cfs", "active_command", "T1A", "cfs_command_active"),
            ("start_owner", "phase", "model_ready", "start_owner_not_idle"),
            ("start_owner", "watchdog_armed", 1, "start_watchdog_armed"),
        )
        for section, key, value, error in cases:
            with self.subTest(error=error):
                snapshot = safe_snapshot()
                snapshot[section][key] = value
                with self.assertRaisesRegex(gate.GateError, error):
                    gate.validate_prior(snapshot)

    def test_safe_high_park_is_accepted_but_other_homed_positions_fail(self):
        snapshot = safe_snapshot()
        snapshot["toolhead"]["homed_axes"] = "xyz"
        snapshot["toolhead"]["position"] = [210.0, 291.5, 66.89154721095261, 60.0]
        self.assertEqual(gate.DEFAULT_PROFILE, gate.validate_prior(snapshot))
        snapshot["toolhead"]["position"] = [210.0, 291.5, 10.0, 60.0]
        with self.assertRaisesRegex(gate.GateError, "homed_position_not_safe_park"):
            gate.validate_prior(snapshot)

    def test_preflight_KO_keeps_the_safe_snapshot_without_effect(self):
        snapshot = safe_snapshot()
        snapshot["toolhead"]["homed_axes"] = "xyz"
        with patch.object(gate, "capture_snapshot", return_value=snapshot):
            result = gate.run_preflight()
        self.assertEqual("PREFLIGHT_KO", result["status"])
        self.assertEqual("GateError:homed_position_not_safe_park", result["error"])
        self.assertEqual(snapshot, result["before"])
        self.assertEqual([], result["effects"]["gcode_commands_attempted"])

    def test_hash_drift_fails_before_any_gcode(self):
        snapshot = safe_snapshot()
        snapshot["hashes"]["/usr/data/printer_data/config/printer.cfg"] = "drift"
        with patch.object(gate, "capture_snapshot", return_value=snapshot), patch.object(
            gate, "send_gcode"
        ) as sender:
            with self.assertRaisesRegex(gate.GateError, "configuration_hash_drift"):
                gate.run_restore()
        sender.assert_not_called()

    def test_only_three_exact_mesh_load_commands_are_callable(self):
        source = (PACKAGE / "remote_gate.py").read_text(encoding="utf-8")
        self.assertNotIn("BOX_", source)
        self.assertNotIn("M104", source)
        self.assertNotIn("M109", source)
        self.assertNotIn("M140", source)
        self.assertNotIn("M190", source)
        self.assertNotIn("G28", source)
        self.assertNotIn("RESTART", source)

    def test_runner_has_offline_plan_exact_restore_gate_and_no_remote_write(self):
        source = (PACKAGE / "run_live.ps1").read_text(encoding="utf-8")
        self.assertIn(gate.MISSION, source)
        self.assertIn("$Action -ceq 'Plan'", source)
        self.assertIn("printer_connection = $false", source)
        self.assertIn("-not $Execute", source)
        self.assertIn("$RemoteProgram | & ssh.exe", source)
        self.assertNotIn("scp.exe", source)

    def test_safe_projection_does_not_export_cfs_identity_fields(self):
        source = (PACKAGE / "remote_gate.py").read_text(encoding="utf-8")
        self.assertNotIn('.get("sn")', source)
        self.assertNotIn('.get("uuid")', source)

    def test_remote_program_parses_as_printer_python_3_8(self):
        source = (PACKAGE / "remote_gate.py").read_text(encoding="utf-8")
        ast.parse(source, filename="remote_gate.py", feature_version=(3, 8))


if __name__ == "__main__":
    unittest.main()
