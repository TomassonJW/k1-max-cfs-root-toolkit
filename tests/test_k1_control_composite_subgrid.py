import asyncio
import ast
import hashlib
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "composite-subgrid-v1"
MODULE_PATH = PACKAGE / "k1_control_composite_subgrid_core.py"
SPEC = importlib.util.spec_from_file_location("composite_subgrid_core", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _matrix():
    return [[round(0.01 * y + 0.001 * x, 6) for x in range(5)] for y in range(5)]


def _status():
    return {
        "print_stats": {"state": "standby", "filename": ""},
        "extruder": {"target": 0.0, "temperature": 25.0},
        "heater_bed": {"target": 0.0, "temperature": 25.0},
        "toolhead": {"homed_axes": ""},
        "gcode_macro KCTRL_STATE": {
            "ready": 1,
            "accepted_z_valid": 1,
            "session_active": 0,
            "low_moves_armed": 0,
            "expected_nozzle_c": 0,
            "temperature_owner": "none",
        },
        "gcode_macro KCTRL_CAL_PATH_STATE": {
            "phase": "committed",
            "motion_armed": 0,
        },
        "bed_mesh": {
            "profile_name": MODULE.ROBUST_PROFILE,
            "probed_matrix": [[0.0] * 6 for _ in range(6)],
            "profiles": {MODULE.ROBUST_PROFILE: {"points": [[0.0] * 6] * 6}},
        },
        "box": {
            "T1": {"state": "connect"},
            "T2": {"state": "connect"},
        },
    }


class Store:
    def __init__(self):
        self.value = MODULE.default_state()

    def load(self):
        return dict(self.value)

    def save(self, value):
        self.value = json.loads(json.dumps(value))


class Backups:
    def __init__(self):
        self.ids = []

    def create(self, campaign_id):
        self.ids.append(campaign_id)
        return {
            "printer_cfg_sha256": "a" * 64,
            "z_state_present": True,
            "z_state_sha256": "b" * 64,
        }


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    async def sleep(self, seconds):
        self.value += seconds
        await asyncio.sleep(0)


class Backend:
    def __init__(
        self,
        fail_mesh=False,
        fail_command=None,
        final_delay_queries=0,
        post_restart_not_ready_attempts=0,
    ):
        self.status = _status()
        self.commands = []
        self.waits = []
        self.fail_mesh = fail_mesh
        self.fail_command = fail_command
        self.final_delay_queries = final_delay_queries
        self.remaining_final_delay = 0
        self.restarted = False
        self.post_restart_not_ready_attempts = post_restart_not_ready_attempts

    async def query_status(self):
        if self.remaining_final_delay > 0:
            self.status["box"]["T2"]["state"] = "disconnect"
            self.remaining_final_delay -= 1
        elif self.restarted and self.status["print_stats"]["state"] == "standby":
            self.status["box"]["T2"]["state"] = "connect"
        return self.status

    async def wait_klippy_ready(self, timeout):
        self.waits.append(timeout)

    async def run_gcode(self, command, disconnect_ok=False):
        self.commands.append((command, disconnect_ok))
        if self.restarted and self.post_restart_not_ready_attempts > 0:
            self.post_restart_not_ready_attempts -= 1
            raise RuntimeError("Printer is not ready")
        if command == self.fail_command:
            raise RuntimeError("synthetic command failure")
        if command == "M140 S55":
            self.status["heater_bed"].update(target=55.0, temperature=55.0)
        elif command == "M104 S140":
            self.status["extruder"].update(target=140.0, temperature=140.0)
        elif command == "KCTRL_CALIBRATION_HOME":
            self.status["toolhead"]["homed_axes"] = "xyz"
        elif command == MODULE.MESH_COMMAND:
            if self.fail_mesh:
                raise RuntimeError("synthetic probe failure")
            self.status["bed_mesh"]["probed_matrix"] = _matrix()
            self.status["bed_mesh"]["profile_name"] = MODULE.TEMP_PROFILE
            self.status["bed_mesh"]["profiles"][MODULE.TEMP_PROFILE] = {
                "points": _matrix()
            }
        elif command == "TURN_OFF_HEATERS":
            self.status["heater_bed"]["target"] = 0.0
            self.status["extruder"]["target"] = 0.0
        elif command == "BED_MESH_PROFILE LOAD=%s" % MODULE.ROBUST_PROFILE:
            self.status["bed_mesh"]["profile_name"] = MODULE.ROBUST_PROFILE
            self.status["bed_mesh"]["probed_matrix"] = [[0.0] * 6 for _ in range(6)]
        elif command == "BED_MESH_PROFILE REMOVE=%s" % MODULE.TEMP_PROFILE:
            self.status["bed_mesh"]["profiles"].pop(MODULE.TEMP_PROFILE, None)
        elif command == "RESTART":
            self.status["toolhead"]["homed_axes"] = ""
            self.remaining_final_delay = self.final_delay_queries
            self.restarted = True
        elif "VARIABLE=expected_nozzle_c VALUE=" in command:
            self.status["gcode_macro KCTRL_STATE"]["expected_nozzle_c"] = int(
                command.rsplit("=", 1)[1]
            )
        elif "VARIABLE=temperature_owner VALUE=" in command:
            self.status["gcode_macro KCTRL_STATE"]["temperature_owner"] = (
                "calibration" if "calibration" in command else "none"
            )
        return "ok"


class CompositeSubgridTests(unittest.IsolatedAsyncioTestCase):
    def build(
        self,
        fail_mesh=False,
        fail_command=None,
        final_delay_queries=0,
        post_restart_not_ready_attempts=0,
    ):
        backend = Backend(
            fail_mesh=fail_mesh,
            fail_command=fail_command,
            final_delay_queries=final_delay_queries,
            post_restart_not_ready_attempts=post_restart_not_ready_attempts,
        )
        store = Store()
        backups = Backups()
        clock = Clock()
        orchestrator = MODULE.CompositeSubgridOrchestrator(
            backend, store, backups, clock=clock, sleep=clock.sleep
        )
        return orchestrator, backend, store, backups

    async def test_fixed_25_contact_subgrid_is_captured_then_cleaned(self):
        orchestrator, backend, store, backups = self.build()
        result = await orchestrator.run(MODULE.GATE_ID, True)
        self.assertEqual(result["phase"], "qualified")
        self.assertFalse(result["busy"])
        self.assertEqual(result["physical_contacts"], 25)
        self.assertEqual(result["matrix"], _matrix())
        self.assertEqual(result["context"]["x_indices"], [1, 3, 5, 7, 9])
        self.assertEqual(result["context"]["klipper_restart_count"], 0)
        self.assertEqual(len(backups.ids), 1)
        commands = [item[0] for item in backend.commands]
        self.assertIn(MODULE.MESH_COMMAND, commands)
        self.assertLess(commands.index(MODULE.MESH_COMMAND), commands.index("RESTART"))
        self.assertEqual(backend.waits, [120])
        self.assertEqual(backend.status["extruder"]["target"], 0.0)
        self.assertEqual(backend.status["heater_bed"]["target"], 0.0)
        self.assertEqual(
            backend.status["bed_mesh"]["profile_name"], MODULE.ROBUST_PROFILE
        )
        self.assertNotIn(MODULE.TEMP_PROFILE, backend.status["bed_mesh"]["profiles"])
        self.assertEqual(
            backend.status["gcode_macro KCTRL_STATE"]["temperature_owner"], "none"
        )
        self.assertEqual(
            backend.status["gcode_macro KCTRL_STATE"]["expected_nozzle_c"], 0
        )
        self.assertEqual(store.value["phase"], "qualified")

    async def test_final_validation_waits_for_second_cfs_reconnection(self):
        orchestrator, backend, _, _ = self.build(final_delay_queries=3)
        result = await orchestrator.run(MODULE.GATE_ID, True)
        self.assertEqual(result["phase"], "qualified")
        self.assertEqual(backend.remaining_final_delay, 0)
        self.assertEqual(backend.status["box"]["T2"]["state"], "connect")

    async def test_post_restart_command_race_is_retried(self):
        orchestrator, backend, _, _ = self.build(post_restart_not_ready_attempts=2)
        result = await orchestrator.run(MODULE.GATE_ID, True)
        self.assertEqual(result["phase"], "qualified")
        robust_loads = [
            command
            for command, _ in backend.commands
            if command == "BED_MESH_PROFILE LOAD=%s" % MODULE.ROBUST_PROFILE
        ]
        self.assertGreaterEqual(len(robust_loads), 4)
        self.assertEqual(
            backend.status["bed_mesh"]["profile_name"], MODULE.ROBUST_PROFILE
        )

    async def test_failed_complete_capture_is_qualified_after_bounded_recovery(self):
        orchestrator, backend, store, _ = self.build()
        orchestrator.state.update(
            phase="failed",
            busy=False,
            matrix=_matrix(),
            context={
                "session_id": "physical-capture",
                "plate_id": MODULE.PLATE_ID,
                "bed_target_c": MODULE.BED_TARGET_C,
                "nozzle_target_c": MODULE.NOZZLE_TARGET_C,
                "homing_epoch": "physical-capture",
                "klipper_restart_count": 0,
                "x_indices": [1, 3, 5, 7, 9],
                "y_indices": [1, 3, 5, 7, 9],
            },
            backup={
                "printer_cfg_sha256": "a" * 64,
                "z_state_present": True,
                "z_state_sha256": "b" * 64,
            },
        )
        backend.status["bed_mesh"]["profile_name"] = "default"
        store.save(orchestrator.state)
        result = await orchestrator.recover_interrupted()
        self.assertEqual(result["phase"], "qualified")
        self.assertFalse(result["busy"])
        self.assertEqual(result["matrix"], _matrix())
        self.assertEqual(
            backend.status["bed_mesh"]["profile_name"], MODULE.ROBUST_PROFILE
        )
        self.assertNotIn("RESTART", [item[0] for item in backend.commands])

    def test_default_state_uses_shared_store_version_marker(self):
        state = MODULE.default_state()
        self.assertEqual(state["version"], 1)
        self.assertNotIn("schema", state)

    def test_legacy_state_marker_is_migrated_without_changing_capture(self):
        migration_path = PACKAGE / "migrate_composite_state.py"
        spec = importlib.util.spec_from_file_location(
            "migrate_composite_state", migration_path
        )
        migration = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(migration)
        legacy = {
            "schema": 1,
            "phase": "failed",
            "matrix": _matrix(),
            "context": {"x_indices": [1, 3, 5, 7, 9]},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(json.dumps(legacy), encoding="utf-8")
            migrated = migration.migrate(path)
            persisted = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(migrated["version"], 1)
        self.assertNotIn("schema", migrated)
        self.assertEqual(persisted["matrix"], legacy["matrix"])
        self.assertEqual(persisted["context"], legacy["context"])

    async def test_exact_gate_is_required(self):
        orchestrator, backend, _, _ = self.build()
        with self.assertRaisesRegex(MODULE.CompositeSubgridError, "gate composite"):
            await orchestrator.run("GO", True)
        self.assertEqual(backend.commands, [])

    async def test_fresh_plate_confirmation_is_required(self):
        orchestrator, backend, _, _ = self.build()
        with self.assertRaisesRegex(MODULE.CompositeSubgridError, "plateau libre"):
            await orchestrator.run(MODULE.GATE_ID, False)
        self.assertEqual(backend.commands, [])

    async def test_existing_heater_target_is_rejected_before_backup(self):
        orchestrator, backend, store, backups = self.build()
        backend.status["heater_bed"]["target"] = 55.0
        with self.assertRaisesRegex(MODULE.CompositeSubgridError, "plateau possède déjà"):
            await orchestrator.run(MODULE.GATE_ID, True)
        self.assertEqual(backups.ids, [])
        self.assertEqual(backend.commands, [])
        self.assertEqual(store.value["phase"], "failed")

    async def test_disconnected_second_cfs_is_rejected(self):
        orchestrator, backend, _, backups = self.build()
        backend.status["box"]["T2"]["state"] = "disconnect"
        with self.assertRaisesRegex(MODULE.CompositeSubgridError, "CFS T2"):
            await orchestrator.run(MODULE.GATE_ID, True)
        self.assertEqual(backups.ids, [])
        self.assertEqual(backend.commands, [])

    async def test_probe_failure_still_cuts_heaters_and_reloads_robust_profile(self):
        orchestrator, backend, store, _ = self.build(fail_mesh=True)
        with self.assertRaisesRegex(MODULE.CompositeSubgridError, "synthetic probe failure"):
            await orchestrator.run(MODULE.GATE_ID, True)
        self.assertEqual(store.value["phase"], "failed")
        self.assertEqual(backend.status["extruder"]["target"], 0.0)
        self.assertEqual(backend.status["heater_bed"]["target"], 0.0)
        self.assertEqual(
            backend.status["bed_mesh"]["profile_name"], MODULE.ROBUST_PROFILE
        )

    async def test_failure_before_mesh_cuts_heaters_without_restart(self):
        clean = "NOZZLE_CLEAR HOT_MIN_TEMP=140 HOT_MAX_TEMP=180 BED_MAX_TEMP=55"
        orchestrator, backend, store, _ = self.build(fail_command=clean)
        with self.assertRaisesRegex(MODULE.CompositeSubgridError, "synthetic command"):
            await orchestrator.run(MODULE.GATE_ID, True)
        commands = [item[0] for item in backend.commands]
        self.assertNotIn("RESTART", commands)
        self.assertEqual(backend.waits, [])
        self.assertEqual(backend.status["extruder"]["target"], 0.0)
        self.assertEqual(backend.status["heater_bed"]["target"], 0.0)
        self.assertEqual(store.value["phase"], "failed")

    async def test_recovery_before_physical_action_sends_no_gcode(self):
        orchestrator, backend, store, _ = self.build()
        orchestrator.state.update(phase="preflight", busy=True)
        store.save(orchestrator.state)
        result = await orchestrator.recover_interrupted()
        self.assertEqual(result["phase"], "interrupted")
        self.assertEqual(backend.commands, [])

    async def test_recovery_during_print_sends_no_gcode(self):
        orchestrator, backend, store, _ = self.build()
        orchestrator.state.update(phase="measuring", busy=True)
        store.save(orchestrator.state)
        backend.status["print_stats"].update(state="printing", filename="job.gcode")
        result = await orchestrator.recover_interrupted()
        self.assertEqual(result["phase"], "failed")
        self.assertIn("impression est active", result["last_error"])
        self.assertEqual(backend.commands, [])

    def test_non_finite_matrix_is_rejected(self):
        value = _matrix()
        value[2][3] = math.nan
        with self.assertRaisesRegex(MODULE.CompositeSubgridError, "non finie"):
            MODULE.validate_matrix(value)

    def test_contract_keeps_full_composite_and_production_out_of_scope(self):
        contract = json.loads(
            (PACKAGE / "composite-subgrid-contract.json").read_text(encoding="utf-8")
        )
        self.assertEqual(contract["status"], "offline_review_candidate")
        self.assertEqual(contract["fixed_settings"]["physical_contacts"], 25)
        self.assertFalse(contract["hard_guards"]["prtouch_version_change"])
        self.assertFalse(contract["hard_guards"]["printer_config_change"])
        self.assertIn("four-subgrid campaign", contract["not_in_scope"])

    def test_sources_parse_with_python_38_grammar(self):
        for name in (
            "k1_control_composite_subgrid_core.py",
            "k1_control_composite_subgrid.py",
            "migrate_composite_state.py",
        ):
            source = (PACKAGE / name).read_text(encoding="utf-8")
            ast.parse(source, filename=name, feature_version=(3, 8))

    def test_deployment_manifest_pins_exact_reviewed_files(self):
        manifest = json.loads(
            (PACKAGE / "deployment-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["contract_id"], MODULE.GATE_ID)
        self.assertEqual(manifest["status"], "offline_review_candidate")
        deployer = ROOT / manifest["deployer"]["path"]
        self.assertEqual(
            hashlib.sha256(deployer.read_bytes()).hexdigest(),
            manifest["deployer"]["sha256"],
        )
        runner = ROOT / manifest["runner"]["path"]
        self.assertEqual(
            hashlib.sha256(runner.read_bytes()).hexdigest(),
            manifest["runner"]["sha256"],
        )
        contract = PACKAGE / manifest["contract"]["path"]
        self.assertEqual(
            hashlib.sha256(contract.read_bytes()).hexdigest(),
            manifest["contract"]["sha256"],
        )
        for item in manifest["files"]:
            source = PACKAGE / item["source"]
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), item["sha256"])
        self.assertEqual(manifest["baseline"]["loaded_probe_count"], [6, 6])
        self.assertEqual(manifest["baseline"]["loaded_algorithm"], "lagrange")
        self.assertEqual(
            manifest["baseline"]["printer_cfg_sha256"],
            "e1f6cd6dc92c9eea1e105f8c669f6d246753243535f09c7f9d92e2dfafebac14",
        )
        unchanged = {
            item["destination"]: item["sha256"]
            for item in manifest["unchanged"]["files"]
        }
        self.assertEqual(
            unchanged[
                "/usr/data/k1-control-v1/current/www/mainsail/k1-control/app.js"
            ],
            "001a31fe7357b0031bfbfa5f6856f8436315cf9640f5a61b2f6121766c985554",
        )
        self.assertEqual(
            unchanged["/usr/data/printer_data/config/.theme/navi.json"],
            "f1775f28967ef73baf205e1574c8ddc7e57e0d021e4b1778cb6ef8e06e9e9774",
        )
        self.assertEqual(
            manifest["required_static_alias"],
            {
                "destination": "/usr/data/k1-control-v1/current/www/mainsail/access-k1-control",
                "target": "k1-control",
            },
        )
        deployer_source = deployer.read_text(encoding="utf-8")
        self.assertIn("test -L '$RemoteNavigationAlias'", deployer_source)
        self.assertFalse(manifest["full_composite_campaign"])

    def test_recovery_manifest_pins_exact_previous_and_repaired_revisions(self):
        manifest = json.loads(
            (PACKAGE / "recovery-deployment-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        deployer = ROOT / manifest["deployer"]["path"]
        self.assertEqual(
            hashlib.sha256(deployer.read_bytes()).hexdigest(),
            manifest["deployer"]["sha256"],
        )
        self.assertEqual(
            manifest["baseline"]["core_sha256"],
            "4f6e281b8cea57a19a76fcb47f936427ff786d4acb1d14e51d1656635fc0ebde",
        )
        self.assertEqual(
            manifest["baseline"]["component_sha256"],
            "f8951b755e8c2d65d3a8f750e05d99431ed430b7310067358915817e19cfe6bd",
        )
        for item in manifest["files"]:
            source = PACKAGE / item["source"]
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), item["sha256"])
        migration = PACKAGE / manifest["state_migration"]["source"]
        self.assertEqual(
            hashlib.sha256(migration.read_bytes()).hexdigest(),
            manifest["state_migration"]["sha256"],
        )
        self.assertFalse(manifest["physical_action"])
        self.assertTrue(manifest["state_preserved"])


if __name__ == "__main__":
    unittest.main()
