import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "calibration-ui-v1"
CORE = PACKAGE / "k1_control_calibration_core.py"
COMPONENT = PACKAGE / "k1_control.py"
DEPLOYER = ROOT / "scripts" / "deploy-k1-control-calibration-ui-v1.ps1"
MANIFEST = PACKAGE / "deployment-manifest.json"
CONTRACT = PACKAGE / "calibration-ui-contract.json"
BASE_MOONRAKER = ROOT / "packages" / "k1-control-v1" / "paths-v1" / "moonraker.conf"
CANDIDATE_MOONRAKER = PACKAGE / "moonraker.conf"
INDEX = PACKAGE / "www" / "index.html"
APP = PACKAGE / "www" / "app.js"


def load_core():
    spec = importlib.util.spec_from_file_location("k1_control_calibration_core", CORE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeBackend:
    def __init__(self, matrices):
        self.matrices = list(matrices)
        self.commands = []
        self.update_calls = []
        self.wait_calls = []
        self.status = {
            "print_stats": {"state": "standby", "filename": ""},
            "extruder": {"target": 0, "temperature": 25},
            "heater_bed": {"target": 0, "temperature": 25},
            "toolhead": {"homed_axes": "", "position": [0, 0, 5, 0]},
            "gcode_move": {"homing_origin": [0, 0, 0, 0]},
            "bed_mesh": {"profile_name": "", "probed_matrix": [[]], "profiles": {}},
            "gcode_macro KCTRL_STATE": {
                "ready": 1,
                "session_active": 0,
                "low_moves_armed": 0,
                "accepted_z_valid": 0,
                "previous_z_valid": 0,
            },
            "gcode_macro KCTRL_CAL_PATH_STATE": {"phase": "idle", "motion_armed": 0},
        }

    async def query_status(self):
        return self.status

    async def run_gcode(self, script, disconnect_ok=False):
        self.commands.append(script)
        if script.startswith("M140 S"):
            target = float(script.removeprefix("M140 S"))
            self.status["heater_bed"]["target"] = target
            self.status["heater_bed"]["temperature"] = target
        elif script.startswith("M104 S"):
            target = float(script.removeprefix("M104 S"))
            self.status["extruder"]["target"] = target
            self.status["extruder"]["temperature"] = target
        elif script == "KCTRL_CALIBRATION_HOME":
            self.status["toolhead"]["homed_axes"] = "xyz"
        elif script.startswith("KCTRL_MESH_CALIBRATE"):
            matrix = self.matrices.pop(0)
            self.status["bed_mesh"].update({
                "profile_name": "K1_TRANSIENT",
                "probed_matrix": matrix,
            })
        elif script == "BED_MESH_PROFILE LOAD=K1_TRANSIENT":
            self.status["bed_mesh"]["profile_name"] = "K1_TRANSIENT"
        elif script.startswith("KCTRL_MESH_COMMIT"):
            args = dict(item.split("=", 1) for item in script.split()[1:])
            profile = "k1_p%03d_t%03d_r%03d_n%02dx%02d" % (
                int(args["PLATE"]), int(args["TEMP_BAND"]), int(args["PROBE_REV"]),
                int(args["X_COUNT"]), int(args["Y_COUNT"]),
            )
            self.status["bed_mesh"]["profiles"][profile] = {
                "points": self.status["bed_mesh"]["probed_matrix"]
            }
            self.status["bed_mesh"]["profiles"].pop("K1_TRANSIENT", None)
            self.status["toolhead"]["homed_axes"] = ""
            self.status["heater_bed"]["target"] = 0
            self.status["extruder"]["target"] = 0
        elif script.startswith("KCTRL_CAL_PATH_BEGIN"):
            self.status["gcode_macro KCTRL_CAL_PATH_STATE"].update({
                "phase": "testing", "motion_armed": 1
            })
            self.status["gcode_macro KCTRL_STATE"]["session_active"] = 1
        elif script.startswith("KCTRL_CAL_PATH_CONFIRM_GAP"):
            self.status["gcode_macro KCTRL_CAL_PATH_STATE"]["phase"] = "gap_confirmed"
        elif script == "KCTRL_CAL_PATH_PARK":
            self.status["gcode_macro KCTRL_CAL_PATH_STATE"].update({
                "phase": "parked_confirmed", "motion_armed": 0
            })
        elif script.startswith("KCTRL_CAL_PATH_COMMIT_Z"):
            self.status["gcode_macro KCTRL_STATE"].update({
                "accepted_z_valid": 1, "session_active": 0
            })
            self.status["gcode_macro KCTRL_CAL_PATH_STATE"]["phase"] = "committed"
        elif script == "KCTRL_CAL_PATH_CANCEL_Z":
            self.status["gcode_macro KCTRL_STATE"]["session_active"] = 0
        elif script == "TURN_OFF_HEATERS":
            self.status["heater_bed"]["target"] = 0
            self.status["extruder"]["target"] = 0
        return "ok"

    async def update_mesh(self, matrix):
        self.update_calls.append(matrix)
        self.status["bed_mesh"].update({
            "profile_name": "K1_TRANSIENT",
            "probed_matrix": matrix,
        })
        self.status["bed_mesh"]["profiles"]["K1_TRANSIENT"] = {"points": matrix}
        self.status["toolhead"]["homed_axes"] = ""

    async def wait_klippy_ready(self, timeout):
        self.wait_calls.append(timeout)


class MemoryStore:
    def __init__(self, initial):
        self.value = dict(initial)

    def load(self):
        return dict(self.value)

    def save(self, state):
        self.value = json.loads(json.dumps(state))


class FakeBackups:
    def __init__(self):
        self.calls = []
        self.restore_calls = []

    def create(self, campaign_id):
        self.calls.append(campaign_id)
        return {"root": "memory://" + campaign_id, "printer_cfg_sha256": "a" * 64}

    def restore(self, campaign_id, evidence):
        self.restore_calls.append((campaign_id, evidence))
        return {"printer_cfg_sha256": evidence["printer_cfg_sha256"], "z_state_present": False}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.now += max(0.001, float(seconds))


class CalibrationUiCoreTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = load_core()

    @staticmethod
    def matrix(delta=0.0, size=6):
        return [[row * 0.01 + column * 0.001 + delta for column in range(size)] for row in range(size)]

    @staticmethod
    def config(**overrides):
        value = {
            "plate_id": 1,
            "plate_label": "PEI_TEXTURED_A",
            "bed_temp_c": 55,
            "nozzle_temp_c": 140,
            "soak_seconds": 200,
            "probe_revision": 1,
            "nozzle_id": 1,
            "config_id": 1,
            "x_count": 6,
            "y_count": 6,
            "algorithm": "lagrange",
            "seed_offset_mm": 0.0,
        }
        value.update(overrides)
        return value

    def test_start_state_accepts_only_closed_path_phases(self):
        backend = FakeBackend([])
        target = "k1_p001_t055_r001_n06x06"
        for phase in ("idle", "committed", "cancelled"):
            backend.status["gcode_macro KCTRL_CAL_PATH_STATE"]["phase"] = phase
            self.core.CalibrationOrchestrator._assert_start_state(backend.status, target, False)
        for phase in ("mesh_ready", "testing", "parked_confirmed"):
            backend.status["gcode_macro KCTRL_CAL_PATH_STATE"]["phase"] = phase
            with self.assertRaisesRegex(self.core.CalibrationError, "n'est pas fermé"):
                self.core.CalibrationOrchestrator._assert_start_state(backend.status, target, False)

    def make_orchestrator(self, backend):
        backups = FakeBackups()
        clock = FakeClock()
        orchestrator = self.core.CalibrationOrchestrator(
            backend, MemoryStore(self.core.default_state()), backups,
            clock=clock, sleep=clock.sleep,
        )
        return orchestrator, backups

    async def test_stable_six_mesh_campaign_commits_one_robust_profile(self):
        matrices = [self.matrix(delta) for delta in (-0.004, 0, 0.004, 0.010, 0.014, 0.018)]
        backend = FakeBackend(matrices)
        orchestrator, backups = self.make_orchestrator(backend)
        state = await orchestrator.run_mesh_campaign(self.config(), plate_clear=True)
        self.assertEqual(state["phase"], "mesh_ready")
        self.assertFalse(state["busy"])
        self.assertEqual(sum(command.startswith("KCTRL_MESH_CALIBRATE") for command in backend.commands), 6)
        self.assertEqual(len(backend.update_calls), 1)
        self.assertIn("k1_p001_t055_r001_n06x06", backend.status["bed_mesh"]["profiles"])
        self.assertNotIn("K1_TRANSIENT", backend.status["bed_mesh"]["profiles"])
        self.assertEqual(len(backups.calls), 1)

    async def test_divergent_batches_stop_without_update_or_seventh_mesh(self):
        matrices = [self.matrix() for _ in range(3)] + [self.matrix(0.061) for _ in range(3)]
        backend = FakeBackend(matrices)
        orchestrator, _ = self.make_orchestrator(backend)
        state = await orchestrator.run_mesh_campaign(self.config(), plate_clear=True)
        self.assertEqual(state["phase"], "mesh_rejected")
        self.assertEqual(len(backend.update_calls), 0)
        self.assertEqual(sum(command.startswith("KCTRL_MESH_CALIBRATE") for command in backend.commands), 6)
        self.assertEqual(backend.commands[-2:], ["BED_MESH_CLEAR", "TURN_OFF_HEATERS"])
        self.assertEqual(backend.status["heater_bed"]["target"], 0)

    async def test_z_path_cannot_skip_and_requires_observed_gap(self):
        backend = FakeBackend([self.matrix() for _ in range(6)])
        orchestrator, _ = self.make_orchestrator(backend)
        await orchestrator.run_mesh_campaign(self.config(), plate_clear=True)
        await orchestrator.begin_z(plate_clear=True, nozzle_clean=True)
        with self.assertRaisesRegex(self.core.CalibrationError, "dernier palier"):
            await orchestrator.confirm_gap(True)
        for _ in range(7):
            await orchestrator.step_z()
        with self.assertRaisesRegex(self.core.CalibrationError, "réellement observé"):
            await orchestrator.confirm_gap(False)
        await orchestrator.adjust_z(0.005)
        await orchestrator.confirm_gap(True)
        state = await orchestrator.accept_z()
        self.assertEqual(state["phase"], "accepted")
        self.assertEqual(backend.status["gcode_macro KCTRL_STATE"]["accepted_z_valid"], 1)

    async def test_parameters_are_selectable_but_bounded(self):
        selected = self.core.validate_config(self.config(soak_seconds=600, algorithm="bicubic"))
        self.assertEqual(selected["soak_seconds"], 600)
        self.assertEqual(selected["algorithm"], "bicubic")
        with self.assertRaisesRegex(self.core.CalibrationError, "60-1200"):
            self.core.validate_config(self.config(soak_seconds=20))
        selected_matrix = self.core.validate_config(self.config(x_count=5, y_count=5))
        self.assertEqual((selected_matrix["x_count"], selected_matrix["y_count"]), (5, 5))
        with self.assertRaisesRegex(self.core.CalibrationError, "3x3-6x6"):
            self.core.validate_config(self.config(x_count=7, y_count=7))

    async def test_five_by_five_campaign_uses_selected_matrix(self):
        matrices = [self.matrix(delta, size=5) for delta in (-0.004, 0, 0.004, 0.010, 0.014, 0.018)]
        backend = FakeBackend(matrices)
        orchestrator, _ = self.make_orchestrator(backend)
        state = await orchestrator.run_mesh_campaign(
            self.config(x_count=5, y_count=5), plate_clear=True
        )
        self.assertEqual(state["phase"], "mesh_ready")
        self.assertIn("k1_p001_t055_r001_n05x05", backend.status["bed_mesh"]["profiles"])
        self.assertTrue(all(
            "X_COUNT=5 Y_COUNT=5" in command
            for command in backend.commands if command.startswith("KCTRL_MESH_CALIBRATE")
        ))

    async def test_cancel_interrupts_soak_before_homing_and_turns_heaters_off(self):
        backend = FakeBackend([self.matrix() for _ in range(6)])
        orchestrator, _ = self.make_orchestrator(backend)
        original_sleep = orchestrator._sleep
        cancelled = False

        async def cancel_during_soak(seconds):
            nonlocal cancelled
            await original_sleep(seconds)
            if not cancelled:
                cancelled = True
                orchestrator.request_cancel()

        orchestrator._sleep = cancel_during_soak
        with self.assertRaises(asyncio.CancelledError):
            await orchestrator.run_mesh_campaign(self.config(), plate_clear=True)
        self.assertEqual(orchestrator.public_state()["phase"], "cancelled")
        self.assertNotIn("KCTRL_CALIBRATION_HOME", backend.commands)
        self.assertIn("BED_MESH_CLEAR", backend.commands)
        self.assertEqual(backend.status["heater_bed"]["target"], 0)
        self.assertEqual(backend.status["extruder"]["target"], 0)

    async def test_full_rollback_uses_only_current_campaign_backup(self):
        backend = FakeBackend([self.matrix() for _ in range(6)])
        orchestrator, backups = self.make_orchestrator(backend)
        await orchestrator.run_mesh_campaign(self.config(), plate_clear=True)
        state = await orchestrator.rollback_campaign()
        self.assertEqual(state["phase"], "rolled_back")
        self.assertEqual(len(backups.restore_calls), 1)
        self.assertIn("RESTART", backend.commands)
        self.assertTrue(state["backup_available"])
        self.assertNotIn("backup", state)

    async def test_previous_z_restore_requires_a_real_record_and_homed_xyz(self):
        backend = FakeBackend([])
        orchestrator, _ = self.make_orchestrator(backend)
        with self.assertRaisesRegex(self.core.CalibrationError, "enregistrement disponible"):
            await orchestrator.restore_previous_z()
        backend.status["gcode_macro KCTRL_STATE"]["previous_z_valid"] = 1
        backend.status["toolhead"]["homed_axes"] = "xyz"
        state = await orchestrator.restore_previous_z()
        self.assertEqual(state["phase"], "restored")
        self.assertIn("KCTRL_Z_RESTORE_PREVIOUS", backend.commands)

    def test_component_exposes_only_domain_endpoints(self):
        source = COMPONENT.read_text(encoding="utf-8")
        for endpoint in (
            "/machine/k1_control/status",
            "/machine/k1_control/calibration/start",
            "/machine/k1_control/calibration/cancel",
            "/machine/k1_control/calibration/rollback",
            "/machine/k1_control/z/start",
            "/machine/k1_control/z/step",
            "/machine/k1_control/z/adjust",
            "/machine/k1_control/z/confirm",
            "/machine/k1_control/z/accept",
            "/machine/k1_control/z/restore",
        ):
            self.assertIn(endpoint, source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("os.system", source)

    def test_backup_manager_restores_exact_config_and_z_absence(self):
        root = ROOT / ".codex-work" / "test-calibration-ui-backup"
        if root.exists():
            shutil.rmtree(root)
        try:
            root.mkdir(parents=True)
        except PermissionError:
            self.skipTest("Le sandbox Windows interdit les écritures Python dans le workspace.")
        try:
            printer = root / "printer.cfg"
            z_state = root / "z-state.json"
            backups = root / "backups"
            printer.write_text("baseline\n", encoding="utf-8")
            manager = self.core.BackupManager(printer, z_state, backups)
            evidence = manager.create("campaign-a")
            printer.write_text("mutated\n", encoding="utf-8")
            z_state.write_text('{"accepted": true}\n', encoding="utf-8")
            result = manager.restore("campaign-a", evidence)
            self.assertEqual(printer.read_text(encoding="utf-8"), "baseline\n")
            self.assertFalse(z_state.exists())
            self.assertFalse(result["z_state_present"])
        finally:
            if root.exists():
                shutil.rmtree(root)


class CalibrationUiPackageTests(unittest.TestCase):
    def test_manifest_pins_every_payload_hash(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["contract_id"], "G4-K1-CONTROL-CALIBRATION-UI-V1")
        deployer = ROOT / manifest["deployer"]["path"]
        self.assertEqual(hashlib.sha256(deployer.read_bytes()).hexdigest(), manifest["deployer"]["sha256"])
        for item in manifest["files"]:
            payload = PACKAGE / item["source"]
            self.assertEqual(hashlib.sha256(payload.read_bytes()).hexdigest(), item["sha256"])

    def test_moonraker_candidate_only_appends_the_reviewed_component(self):
        baseline = BASE_MOONRAKER.read_text(encoding="utf-8")
        candidate = CANDIDATE_MOONRAKER.read_text(encoding="utf-8")
        self.assertTrue(candidate.startswith(baseline.rstrip("\n") + "\n\n[k1_control]\n"))
        self.assertEqual(candidate.count("[k1_control]"), 1)

    def test_deployer_is_exactly_gated_and_has_automatic_rollback(self):
        source = DEPLOYER.read_text(encoding="utf-8")
        self.assertIn("$RequiredGate = 'G4-K1-CONTROL-CALIBRATION-UI-V1'", source)
        self.assertIn("Get-LocalSha256 $PSCommandPath", source)
        self.assertIn("[string]$Action = 'Plan'", source)
        copy_to_remote = source[
            source.index("function Copy-ToRemote"):source.index("function Get-RemoteSha256")
        ]
        self.assertIn("'-O'", copy_to_remote)
        backup = source.index("cp '$RemoteConfig' '$RemoteBackup/moonraker.conf.before'")
        mutation = source.index("$MutationStarted = $true", backup)
        transfer = source.index("Copy-ToRemote", mutation)
        install = source.index("'$destination.next'", transfer)
        self.assertLess(backup, mutation)
        self.assertLess(mutation, transfer)
        self.assertLess(transfer, install)
        self.assertIn("if ($MutationStarted)", source)
        self.assertIn("Invoke-ExactRollback", source)
        self.assertIn("rmdir '$RemoteStaging'", source)
        self.assertIn("k1-control-calibration-workflow.json", source)
        self.assertIn("$closedPhases = @('idle', 'committed', 'cancelled')", source)
        self.assertIn("$closedPhases -notcontains [string]$path.phase", source)
        self.assertIn("gcode_macro+KCTRL_STATE&gcode_macro+KCTRL_CAL_PATH_STATE", source)
        self.assertNotIn("curl -fsS", source)
        self.assertIn("Assert-RemotePythonCompatibility", source)
        self.assertIn("REMOTE_CALIBRATION_UI_IMPORT_OK", source)
        preflight = source[source.index("function Assert-BasePreflight"):]
        self.assertLess(preflight.index("Assert-RemotePythonCompatibility"), preflight.index("[void](Assert-PrinterIdle)"))
        self.assertNotIn("KCTRL_CALIBRATION_PREHEAT", source)
        self.assertNotIn("KCTRL_CALIBRATION_HOME", source)
        self.assertNotIn("KCTRL_MESH_CALIBRATE", source)

    def test_contract_declares_generated_cache_and_full_restore(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertTrue(contract["safety"]["exact_campaign_backup_restore"])
        self.assertTrue(contract["safety"]["cancellable_heat_and_soak"])
        self.assertTrue(contract["safety"]["exact_remote_python_import_before_mutation"])
        self.assertEqual(contract["safety"]["closed_path_phases"], ["idle", "committed", "cancelled"])
        self.assertEqual(sum(path.endswith(".pyc") for path in contract["write_set"]), 2)

    def test_real_ui_has_operator_choices_and_no_free_gcode(self):
        index = INDEX.read_text(encoding="utf-8")
        app = APP.read_text(encoding="utf-8")
        for expected in ('value="55"', 'value="140"', 'value="200"', 'value="6" selected'):
            self.assertIn(expected, index)
        for control in ("start-mesh", "cancel-workflow", "rollback-campaign", "restore-z", "accept-z"):
            self.assertIn('id="%s"' % control, index)
        self.assertIn('/calibration/rollback', app)
        self.assertIn('previous_z_restorable', app)
        self.assertNotIn('/printer/gcode/script', app)
        self.assertNotIn('gcode/script', app)


if __name__ == "__main__":
    unittest.main()
