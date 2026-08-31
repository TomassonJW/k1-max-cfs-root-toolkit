from importlib.util import module_from_spec, spec_from_file_location
import ast
import json
from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "integrated-production-cycle-v1"


def load_cycle():
    spec = spec_from_file_location("integrated_production_cycle_v1", PACKAGE / "cycle.py")
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cycle = load_cycle()


def load_verifier():
    spec = spec_from_file_location("integrated_production_cycle_v1_verifier", PACKAGE / "verify_candidate.py")
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verifier = load_verifier()


def load_orchestrator():
    sys.path.insert(0, str(PACKAGE))
    try:
        spec = spec_from_file_location("integrated_production_cycle_v1_orchestrator", PACKAGE / "orchestrator.py")
        module = module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(PACKAGE))


orchestrator = load_orchestrator()


def load_job_contract():
    spec = spec_from_file_location("integrated_production_cycle_v1_job_contract", PACKAGE / "job_contract.py")
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


job_contract = load_job_contract()


class FakeBackend:
    def __init__(self, routes=None, camera="PASS"):
        self.camera = camera
        self.commands = []
        self.started = []
        self.status = {
            "printer_state": "standby",
            "klippy_ready": True,
            "nozzle_target_c": 0,
            "bed_target_c": 0,
            "cfs_command": "",
            "routes": [] if routes is None else routes,
            "cycle_phase": "idle",
            "mesh_profile": "k1_p001_t055_r001_n11x11",
            "accepted_z_mm": -0.04,
            "accepted_z_valid": True,
            "hidden_z_offset_present": False,
            "head_sensor": bool(routes),
            "after_cutter_sensor": bool(routes),
            "last_cfs_effect_target_c": 190,
            "cfs_temperature_command": False,
        }

    async def selected_job(self):
        return job()

    async def query_status(self):
        return dict(self.status)

    async def run_gcode(self, script):
        self.commands.append(script)
        if script.startswith("KCTRL_CYCLE_PREPARE_V1"):
            if self.status["routes"]:
                self.status["cycle_phase"] = "unload_before_clean"
            elif self.status["head_sensor"] and self.status["after_cutter_sensor"]:
                self.status["cycle_phase"] = "reconcile_before_clean"
            else:
                self.status["cycle_phase"] = "await_manual_clean"
        elif script == "KCTRL_CYCLE_RECONCILE_SLOT_A_BEFORE_CLEAN_V1":
            self.status.update({
                "routes": ["T1A"],
                "cycle_phase": "unload_before_clean",
                "head_sensor": True,
                "after_cutter_sensor": True,
                "last_cfs_effect_target_c": 190,
            })
        elif script == "KCTRL_CYCLE_UNLOAD_BEFORE_CLEAN_V1":
            self.status.update({
                "routes": [],
                "cycle_phase": "await_manual_clean",
                "after_cutter_sensor": False,
                "last_cfs_effect_target_c": 190,
            })
        elif script == "KCTRL_CYCLE_CONFIRM_CLEAN_AND_REFERENCE_V1":
            self.status.update({
                "cycle_phase": "await_t1a_load",
                "bed_temperature_c": 55,
                "reference_nozzle_temperature_c": 140,
                "mesh_profile": "k1_p001_t055_r001_n11x11",
                "accepted_z_mm": -0.04,
                "accepted_z_valid": True,
                "hidden_z_offset_present": False,
            })
        elif script == "KCTRL_CYCLE_LOAD_SLOT_A_V1":
            self.status.update({
                "cycle_phase": "await_purge_proof",
                "routes": ["T1A"],
                "head_sensor": True,
                "after_cutter_sensor": True,
                "last_cfs_effect_target_c": 190,
                "cfs_temperature_command": False,
            })
        elif script == "KCTRL_CYCLE_SINGLE_PURGE_V1":
            self.status.update({
                "cycle_phase": "camera_purge_check",
                "purge_effect_observed": True,
                "last_cfs_effect_target_c": 190,
            })
        elif script == "KCTRL_CYCLE_CONFIRM_PURGE_CAMERA_V1":
            self.status["cycle_phase"] = "ready_to_print"
        elif script == "KCTRL_CYCLE_ABORT_V1":
            self.status.update({
                "cycle_phase": "failed_safe",
                "nozzle_target_c": 0,
                "bed_target_c": 0,
            })

    async def camera_verdict(self, reference):
        self.commands.append("CAMERA:%s" % reference)
        return self.camera

    async def start_print(self, filename):
        self.started.append(filename)
        self.status.update({"printer_state": "printing", "cycle_phase": "printing"})

    def complete_end(self):
        self.status.update({
            "printer_state": "standby",
            "cycle_phase": "closed_safe",
            "routes": [],
            "after_cutter_sensor": False,
            "last_cfs_effect_target_c": 190,
            "cfs_temperature_command": False,
            "park_verified": True,
            "bed_lowered_verified": True,
            "heater_targets_zero": True,
            "fans_zero": True,
            "motors_released": True,
        })


def job():
    return {
        "contract_version": 1,
        "job_id": "daily-pla",
        "filename": "K1-Control/daily-pla.gcode",
        "material_id": "PLA-GEEETECH-BLACK",
        "route": "T1A",
        "mesh_profile": "k1_p001_t055_r001_n11x11",
        "legacy_z_offset_removed": True,
        "bed_first_c": 55,
        "probe_nozzle_c": 140,
        "nozzle_first_c": 190,
        "nozzle_normal_c": 195,
        "load_c": 190,
        "unload_c": 190,
        "purge_c": 190,
        "purge_mm": 8,
        "material_min_c": 180,
        "material_max_c": 220,
    }


def prepare(routes=None):
    present = bool(routes)
    return {
        "kind": "prepare",
        "printer_state": "standby",
        "klippy_ready": True,
        "nozzle_target_c": 0,
        "bed_target_c": 0,
        "cfs_command": "",
        "routes": [] if routes is None else routes,
        "head_sensor": present,
        "after_cutter_sensor": present,
    }


def effect(kind, operation, effect_id, target, commands, **extra):
    value = {
        "kind": kind,
        "operation": operation,
        "effect_id": effect_id,
        "effect_observed": True,
        "target_before_c": target,
        "target_during_c": target,
        "cfs_temperature_command": False,
        "commands": commands,
        "automatic_retry": False,
    }
    value.update(extra)
    return value


def geometry():
    return {
        "kind": "geometry_complete",
        "commands": ["G28 X Y", "ACCURATE_G28", "KCTRL_PRODUCTION_ARM"],
        "mesh_calibrated": False,
        "xy_reference_count": 1,
        "precise_z_reference_count": 1,
        "bed_c": 55,
        "nozzle_c": 140,
        "mesh_profile": "k1_p001_t055_r001_n11x11",
        "mesh_verified": True,
        "accepted_z_mm": -0.04,
        "accepted_z_verified": True,
        "hidden_z_offset_present": False,
    }


def events_to_print(routes=None):
    values = [prepare(routes)]
    if routes:
        values.append(effect(
            "unload_before_clean_complete",
            "preclean-unload",
            "preclean-1",
            190,
            ["BOX_CUT_MATERIAL", "local_tip_retract", "BOX_RETRUDE_MATERIAL"],
            route_after=None,
            after_cutter_sensor_after=False,
        ))
    values.extend([
        {
            "kind": "manual_clean_confirmed",
            "operator_confirmed": True,
            "nozzle_visibly_clean": True,
            "confirmation_fresh": True,
        },
        geometry(),
        effect(
            "t1a_load_complete",
            "T1A-load",
            "load-1",
            190,
            ["BOX_EXTRUDE_MATERIAL TNN=T1A", "BOX_EXTRUDER_EXTRUDE TNN=T1A"],
            route_after="T1A",
            head_sensor_after=True,
            after_cutter_sensor_after=True,
        ),
        effect(
            "purge_complete",
            "single-purge",
            "purge-1",
            190,
            [],
            route="T1A",
            zone="origin_edge_outside_model",
            purge_mm=8,
            flow_visible=True,
            camera_verdict="PASS",
        ),
        {
            "kind": "print_started",
            "filename": "K1-Control/daily-pla.gcode",
            "virtual_sd_state": "printing",
            "mesh_profile": "k1_p001_t055_r001_n11x11",
            "route": "T1A",
            "hidden_z_offset_present": False,
        },
    ])
    return values


def normal_end():
    return effect(
        "normal_end_complete",
        "normal-end-unload",
        "end-unload-1",
        190,
        [
            "safe_lift",
            "lower_bed",
            "set_unload_temperature",
            "BOX_CUT_MATERIAL",
            "local_tip_retract",
            "BOX_RETRUDE_MATERIAL",
            "park_head",
            "TURN_OFF_HEATERS",
            "FANS_ZERO",
            "M84",
        ],
        route_after=None,
        after_cutter_sensor_after=False,
        park_verified=True,
        bed_lowered_verified=True,
        heater_targets_zero=True,
        fans_zero=True,
        motors_released=True,
    )


class IntegratedProductionCycleV1Tests(unittest.TestCase):
    def test_all_macro_names_follow_the_creality_command_parser_rule(self):
        config = (PACKAGE / "k1-control-integrated-production-cycle-v1.cfg").read_text(encoding="utf-8")
        names = re.findall(r"^\[gcode_macro ([A-Z0-9_]+)\]$", config, re.MULTILINE)
        self.assertTrue(names)
        for name in names:
            self.assertRegex(name, r"^[A-Z_]+[0-9]*$")

    def test_macro_ui_and_orca_candidate_is_coherent(self):
        result = verifier.verify()
        self.assertEqual("OK", result["status"])
        self.assertTrue(result["single_purge"])
        self.assertFalse(result["full_unload_end"])
        self.assertTrue(result["cfs_effects_blocked"])
        self.assertFalse(result["printer_transport"])

    def test_contract_targets_the_full_daily_cycle_but_remains_offline(self):
        contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        self.assertEqual("K1 Control opened from Mainsail", contract["target_ui"])
        self.assertIn("cut_unload_and_rewind_at_explicit_temperature", contract["workflow"])
        self.assertFalse(contract["deployment_candidate"])
        self.assertFalse(contract["printer_connection"])
        self.assertFalse(contract["physical_action"])

    def test_complete_empty_start_and_normal_end_close_safe(self):
        result = cycle.simulate(job(), events_to_print() + [normal_end()])
        self.assertEqual("closed_safe", result["phase"])
        self.assertIsNone(result["route"])
        self.assertEqual(1, result["load_count"])
        self.assertEqual(1, result["unload_count"])
        self.assertEqual(1, result["purge_count"])
        self.assertEqual({"nozzle": 0.0, "bed": 0.0}, result["targets"])

    def test_existing_route_is_removed_before_clean_and_removed_again_at_end(self):
        result = cycle.simulate(job(), events_to_print(["T1A"]) + [normal_end()])
        self.assertEqual("closed_safe", result["phase"])
        self.assertEqual(2, result["unload_count"])
        kinds = [item["kind"] for item in result["trace"]]
        self.assertLess(kinds.index("unload_before_clean_complete"), kinds.index("manual_clean_confirmed"))
        self.assertLess(kinds.index("geometry_complete"), kinds.index("t1a_load_complete"))

    def test_geometry_never_calibrates_a_mesh(self):
        bad = geometry()
        bad["mesh_calibrated"] = True
        result = cycle.simulate(job(), [prepare(), {
            "kind": "manual_clean_confirmed",
            "operator_confirmed": True,
            "nozzle_visibly_clean": True,
            "confirmation_fresh": True,
        }, bad])
        self.assertEqual("mesh_calibration_forbidden", result["failure_code"])
        self.assertEqual("failed_safe", result["phase"])

    def test_clean_confirmation_before_route_clear_fails(self):
        result = cycle.simulate(job(), [prepare(["T1A"]), {
            "kind": "manual_clean_confirmed",
            "operator_confirmed": True,
            "nozzle_visibly_clean": True,
            "confirmation_fresh": True,
        }])
        self.assertEqual("phase_order_invalid", result["failure_code"])

    def test_hidden_220_rewrite_blocks_without_retry(self):
        values = events_to_print()[:3]
        bad_load = effect(
            "t1a_load_complete",
            "T1A-load",
            "load-hidden-220",
            190,
            ["BOX_EXTRUDE_MATERIAL TNN=T1A", "BOX_EXTRUDER_EXTRUDE TNN=T1A"],
            route_after="T1A",
            head_sensor_after=True,
            after_cutter_sensor_after=True,
        )
        bad_load["target_during_c"] = 220
        result = cycle.simulate(job(), values + [bad_load])
        self.assertEqual("phase_temperature_mismatch", result["failure_code"])
        self.assertEqual({"nozzle": 0.0, "bed": 0.0}, result["targets"])

    def test_duplicate_effect_is_rejected(self):
        values = events_to_print()
        values[3]["effect_id"] = "same-effect"
        values[4]["effect_id"] = "same-effect"
        result = cycle.simulate(job(), values)
        self.assertEqual("duplicate_effect_rejected", result["failure_code"])

    def test_end_refuses_motor_release_before_park_and_unload(self):
        bad = normal_end()
        bad["commands"] = ["M84"] + bad["commands"][:-1]
        result = cycle.simulate(job(), events_to_print() + [bad])
        self.assertEqual("normal_end_order_invalid", result["failure_code"])

    def test_runtime_core_has_no_transport_import(self):
        source = (PACKAGE / "cycle.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="cycle.py", feature_version=(3, 8))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue({"asyncio", "http", "requests", "socket", "subprocess", "urllib"}.isdisjoint(imported))

    def test_job_contract_comes_from_orca_metadata_and_exact_file(self):
        metadata = {
            "uuid": "job-pla-001",
            "filament_type": "PLA",
            "first_layer_extr_temp": 210,
            "first_layer_bed_temp": 55,
            "filament_temps": [205],
            "referenced_tools": [0],
            "mmu_print": 0,
            "slicer": "OrcaSlicer",
            "slicer_version": "2.4.2",
        }
        result = job_contract.build_job_contract(
            "K1-Control/compatible-pla.gcode",
            metadata,
            PACKAGE / "fixture-compatible-pla.gcode",
        )
        self.assertEqual(210, result["load_c"])
        self.assertEqual(210, result["unload_c"])
        self.assertEqual(205, result["nozzle_normal_c"])
        self.assertEqual("T1A", result["route"])
        self.assertEqual(55, result["bed_first_c"])

    def test_repeated_PLA_metadata_is_still_one_supported_material(self):
        metadata = {
            "uuid": "job-pla-duplicate-metadata",
            "filament_type": "PLA;PLA",
            "first_layer_extr_temp": 190,
            "first_layer_bed_temp": 55,
            "slicer": "OrcaSlicer",
        }
        result = job_contract.build_job_contract(
            "compatible-pla.gcode", metadata, PACKAGE / "fixture-compatible-pla.gcode"
        )
        self.assertEqual("PLA", result["material_id"])

    def test_real_two_layer_gate_body_has_only_integrated_entry_and_end(self):
        metadata = {
            "uuid": "05f62f0e-d213-4f0d-90c7-337a9d3768e1",
            "filament_type": "PLA;PLA",
            "first_layer_extr_temp": 190,
            "first_layer_bed_temp": 55,
            "slicer": "OrcaSlicer",
            "slicer_version": "2.4.2",
        }
        result = job_contract.build_job_contract(
            "K1-INTEGRATED-T1A-2LAYER.gcode",
            metadata,
            PACKAGE / "K1-INTEGRATED-T1A-2LAYER.gcode",
        )
        self.assertEqual(190, result["load_c"])
        self.assertEqual(190, result["unload_c"])
        self.assertEqual(90422, result["source"]["gcode_size"])

    def test_job_contract_refuses_legacy_start_even_with_valid_metadata(self):
        metadata = {
            "filament_type": "PLA",
            "first_layer_extr_temp": 210,
            "first_layer_bed_temp": 55,
            "filament_temps": [205],
            "slicer": "OrcaSlicer",
        }
        with self.assertRaises(job_contract.JobContractError) as raised:
            job_contract.build_job_contract(
                "forbidden.gcode",
                metadata,
                PACKAGE / "fixture-forbidden-legacy-start.gcode",
            )
        self.assertEqual("forbidden_gcode_command:START_PRINT", raised.exception.code)

    def test_moonraker_component_exposes_selection_camera_and_cycle_endpoints(self):
        source = (PACKAGE / "moonraker_component.py").read_text(encoding="utf-8")
        ast.parse(source, filename="moonraker_component.py", feature_version=(3, 8))
        for endpoint in (
            "/cycle/files", "/cycle/select", "/cycle/prepare",
            "/cycle/clean-confirm", "/cycle/camera-verdict", "/cycle/abort",
        ):
            self.assertIn(endpoint, source)
        self.assertIn('authority_mode in {"qualification", "production"}', source)
        self.assertIn('get_directory("gcodes")', source)
        self.assertNotIn('get_full_path("gcodes"', source)

    def test_ui_never_implicitly_selects_the_latest_file(self):
        app = (PACKAGE / "www" / "app.js").read_text(encoding="utf-8")
        page = (PACKAGE / "www" / "index.html").read_text(encoding="utf-8")
        self.assertIn('new Option("Choisir un fichier…", "")', app)
        self.assertIn('post("/select", {filename})', app)
        self.assertIn('id="file-select"', page)


class IntegratedProductionCycleOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_after_one_clean_confirmation_the_remaining_start_is_automatic(self):
        backend = FakeBackend()
        service = orchestrator.CycleOrchestrator(backend, effects_enabled=True, poll_s=0)
        prepared = await service.prepare(job())
        self.assertEqual("await_manual_clean", prepared["phase"])
        printing = await service.confirm_clean_and_start()
        self.assertEqual("printing", printing["phase"])
        self.assertEqual(["K1-Control/daily-pla.gcode"], backend.started)
        self.assertIn("KCTRL_CYCLE_LOAD_SLOT_A_V1", backend.commands)
        self.assertIn("CAMERA:ORIGIN_EDGE_PURGE", backend.commands)

    async def test_existing_T1A_is_retracted_before_the_clean_prompt(self):
        backend = FakeBackend(["T1A"])
        service = orchestrator.CycleOrchestrator(backend, effects_enabled=True, poll_s=0)
        prepared = await service.prepare(job())
        self.assertEqual("await_manual_clean", prepared["phase"])
        self.assertIsNone(prepared["route"])
        self.assertEqual(1, service.cycle.unload_count)

    async def test_residual_T1A_without_logical_route_is_reconciled_then_unloaded(self):
        backend = FakeBackend()
        backend.status.update({"head_sensor": True, "after_cutter_sensor": True})
        service = orchestrator.CycleOrchestrator(backend, effects_enabled=True, poll_s=0)
        prepared = await service.prepare(job())
        self.assertEqual("await_manual_clean", prepared["phase"])
        self.assertEqual(1, service.cycle.load_count)
        self.assertEqual(1, service.cycle.unload_count)
        self.assertIn("KCTRL_CYCLE_RECONCILE_SLOT_A_BEFORE_CLEAN_V1", backend.commands)
        self.assertIn("KCTRL_CYCLE_UNLOAD_BEFORE_CLEAN_V1", backend.commands)

    async def test_camera_ko_stops_before_print_start(self):
        backend = FakeBackend(camera="KO")
        service = orchestrator.CycleOrchestrator(backend, effects_enabled=True, poll_s=0)
        await service.prepare(job())
        with self.assertRaises(orchestrator.OrchestrationError):
            await service.confirm_clean_and_start()
        self.assertEqual([], backend.started)
        self.assertEqual("failed_safe", service.cycle.phase)

    async def test_unqualified_effect_connector_fails_closed(self):
        backend = FakeBackend()
        service = orchestrator.CycleOrchestrator(backend, effects_enabled=False, poll_s=0)
        with self.assertRaises(orchestrator.OrchestrationError) as raised:
            await service.prepare(job())
        self.assertEqual("CFS_primitives_not_physically_qualified", raised.exception.code)
        self.assertEqual("failed_safe", service.cycle.phase)

    async def test_normal_end_is_verified_as_full_unload_and_safe_terminal_state(self):
        backend = FakeBackend()
        service = orchestrator.CycleOrchestrator(backend, effects_enabled=True, poll_s=0)
        await service.prepare(job())
        await service.confirm_clean_and_start()
        backend.complete_end()
        terminal = await service.observe_normal_end()
        self.assertEqual("closed_safe", terminal["phase"])
        self.assertEqual(1, terminal["unload_count"])
        self.assertIsNone(terminal["route"])


if __name__ == "__main__":
    unittest.main()
