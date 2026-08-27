from importlib.util import module_from_spec, spec_from_file_location
import ast
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "job-lifecycle-offline-v1"


def _load(name, filename):
    spec = spec_from_file_location(name, PACKAGE / filename)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load("test_job_lifecycle_offline_runner", "run_scenarios.py")
blueprint = _load("test_job_lifecycle_offline_blueprint", "verify_blueprint.py")


class JobLifecycleOfflineV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(
            (PACKAGE / "contract.json").read_text(encoding="utf-8")
        )

    def test_contract_is_complete_offline_and_not_deployable(self):
        self.assertEqual("offline_only", self.contract["authority"])
        self.assertFalse(self.contract["printer_connection"])
        self.assertFalse(self.contract["printer_action"])
        self.assertFalse(self.contract["gcode_sent"])
        self.assertFalse(self.contract["real_connector_present"])
        self.assertFalse(self.contract["deployment_candidate"])

    def test_all_canonical_scenarios_are_implemented_once(self):
        canonical = json.loads(
            (ROOT / "design" / "job-lifecycle-contract-v1.json").read_text(
                encoding="utf-8"
            )
        )
        canonical_ids = [
            item["id"] for item in canonical["required_offline_scenarios"]
        ]
        self.assertEqual(canonical_ids, self.contract["required_scenarios"])
        self.assertEqual(27, len(set(canonical_ids)))

    def test_all_twenty_seven_scenarios_are_deterministic_and_green(self):
        first = runner.run()
        second = runner.run()
        self.assertEqual(first, second)
        self.assertEqual("OK", first["verdict"])
        self.assertEqual(27, first["passed"])
        self.assertEqual(27, first["total"])
        self.assertFalse(first["printer_connection"])
        self.assertFalse(first["gcode_sent"])
        self.assertFalse(first["physical_action"])

    def test_start_keeps_the_correct_filament_and_always_proves_flow(self):
        result = runner.run_one("start_correct_filament_engaged")
        self.assertEqual("printing", result["phase"])
        self.assertEqual(0, result["cut_count"])
        self.assertEqual(0, result["unload_count"])
        self.assertEqual(1, result["purge_count"])
        self.assertTrue(result["flow_proven"])
        operations = [
            item["operation"]
            for item in result["trace"]
            if item.get("kind") == "cfs_boundary"
        ]
        self.assertEqual(["purge"], operations)

    def test_wrong_and_absent_filament_paths_are_distinct(self):
        wrong = runner.run_one("start_wrong_filament_engaged")
        absent = runner.run_one("start_no_filament")
        self.assertEqual((1, 1, 1), (wrong["cut_count"], wrong["unload_count"], wrong["load_count"]))
        self.assertEqual((0, 0, 1), (absent["cut_count"], absent["unload_count"], absent["load_count"]))
        self.assertEqual("T0", wrong["engaged_tool"])
        self.assertEqual("T0", absent["engaged_tool"])

    def test_unknown_filament_and_sensor_disagreement_block_before_heat_or_motion(self):
        for scenario_id, reason in (
            ("start_unknown_filament_identity", "filament_identity_unknown"),
            ("sensor_disagreement", "sensor_disagreement"),
        ):
            with self.subTest(scenario_id=scenario_id):
                result = runner.run_one(scenario_id)
                self.assertEqual(reason, result["reason_code"])
                self.assertEqual(0, result["cfs_effects"])
                self.assertEqual(0, result["nozzle_target_c"])
                self.assertEqual(0, result["bed_target_c"])
                self.assertFalse(any(item.get("kind") == "rough_reference" for item in result["trace"]))

    def test_cleaning_uses_human_brush_plane_without_probe_extrusion_or_filament_change(self):
        result = runner.run_one("clean_brush_z_not_probed")
        cleaning = next(item for item in result["trace"] if item["kind"] == "clean_nozzle")
        self.assertFalse(cleaning["brush_z_probed"])
        self.assertEqual(180, cleaning["cleaning_target_c"])
        self.assertEqual(140, cleaning["probe_target_c"])

    def test_mesh_and_z_are_armed_only_after_the_final_reference(self):
        result = runner.run_one("mesh_reference_match")
        kinds = [item["kind"] for item in result["trace"]]
        self.assertLess(kinds.index("final_reference"), kinds.index("arm_mesh_z"))
        self.assertTrue(result["low_moves_armed"])
        mismatch = runner.run_one("mesh_reference_mismatch")
        self.assertEqual("mesh_profile_mismatch", mismatch["reason_code"])
        self.assertFalse(mismatch["low_moves_armed"])

    def test_pause_has_no_cfs_effect_and_resume_keeps_latest_z(self):
        paused = runner.run_one("pause_normal")
        resumed = runner.run_one("resume_with_optional_reprime")
        self.assertEqual(1, paused["cfs_effects"])
        self.assertEqual("paused_normal", paused["phase"])
        self.assertEqual(-0.05, resumed["effective_z_offset_mm"])
        self.assertEqual("z-r2", resumed["accepted_z_revision"])
        resume_trace = next(
            item for item in resumed["trace"] if item["kind"] == "resume_normal"
        )
        self.assertTrue(resume_trace["reprime"])
        self.assertEqual(-0.05, resume_trace["effective_z_offset_mm"])

    def test_tool_change_refuses_a_blocked_rear_path_before_new_cfs_effect(self):
        result = runner.run_one("tall_part_blocks_rear_path")
        self.assertEqual("rear_path_blocked", result["reason_code"])
        self.assertEqual(1, result["cfs_effects"])
        self.assertEqual(0, result["cut_count"])

    def test_cross_material_change_keeps_every_temperature_explicit(self):
        result = runner.run_one("intentional_cross_material_change")
        boundaries = [
            item for item in result["trace"] if item.get("kind") == "cfs_boundary"
        ][-3:]
        self.assertEqual(
            [("intentional_unload", 210), ("intentional_load", 235), ("purge", 230)],
            [(item["operation"], item["target_c"]) for item in boundaries],
        )
        self.assertEqual(240, result["nozzle_target_c"])

    def test_late_temperature_rewrite_fails_before_cut_or_resume(self):
        result = runner.run_one("cfs_late_220_rewrite")
        self.assertEqual("late_temperature_rewrite", result["reason_code"])
        self.assertEqual(0, result["cut_count"])
        self.assertFalse(result["resume_armed"])
        self.assertEqual(0, result["nozzle_target_c"])
        self.assertEqual(0, result["bed_target_c"])

    def test_end_keeps_filament_engaged_and_closes_resume(self):
        result = runner.run_one("end_keep_engaged")
        self.assertEqual("closed_safe", result["phase"])
        self.assertEqual("T0", result["engaged_tool"])
        self.assertEqual(0, result["cut_count"])
        self.assertEqual(0, result["unload_count"])
        self.assertFalse(result["resume_armed"])
        self.assertEqual("engaged", result["persisted_filament_record"]["engagement_state"])

    def test_manual_disengage_uses_the_real_offline_guard_composition(self):
        result = runner.run_one("manual_disengage_and_clean")
        self.assertTrue(result["disengage_guard_used"])
        self.assertEqual("engaged_unknown", result["filament_state"])
        self.assertIsNone(result["engaged_tool"])
        trace = next(
            item for item in result["trace"] if item["kind"] == "disengage_and_clean"
        )
        self.assertEqual("stock_unload_guard_transport_offline_v1", trace["guard"])

    def test_boundary_timeout_is_safe_and_has_no_retry_or_counted_effect(self):
        job = runner.job_payload()
        machine = runner._absent_machine()
        events = runner.start_to_arm(job, machine)
        events.append(
            {
                "kind": "resolve_initial_filament",
                "branch": "load_absent",
                "boundaries": [
                    runner.boundary(
                        job,
                        "initial_load",
                        "T0",
                        205,
                        "slow-load",
                        "slow-load-proof",
                        elapsed_s=150.001,
                    )
                ],
            }
        )
        result = runner.simulate(job, machine, events)
        self.assertEqual("phase_timeout:cfs_boundary", result["reason_code"])
        self.assertEqual(0, result["cfs_effects"])
        self.assertEqual([], result["effect_ids"])

    def test_duplicate_effect_id_is_refused_before_a_second_effect(self):
        job = runner.job_payload()
        machine = runner.machine_payload()
        events = runner.happy_start_events(job, machine, prefix="duplicate-effect")
        events.extend(
            [
                {"kind": "pause_normal", "cfs_effect": False, "purge": False},
                {
                    "kind": "resume_normal",
                    "homing": False,
                    "reprime": True,
                    "purge_volume_mm3": 3,
                    "boundary": runner.boundary(
                        job,
                        "purge",
                        "T0",
                        205,
                        "duplicate-effect-purge",
                        "fresh-duplicate-effect-proof",
                        purge_volume_mm3=3,
                        flow_proven=True,
                    ),
                },
            ]
        )
        result = runner.simulate(job, machine, events)
        self.assertEqual("duplicate_effect_rejected", result["reason_code"])
        self.assertEqual(1, result["cfs_effects"])

    def test_cancel_reboot_and_route_freshness_matrices_are_closed(self):
        cancel = runner.run_one("cancel_and_reboot_each_phase")
        routes = runner.run_one("cfs_route_freshness")
        self.assertEqual(3, cancel["safe_subcases"])
        self.assertEqual(0, cancel["implicit_replays"])
        self.assertTrue(routes["stale_blocked"])
        self.assertTrue(routes["reused_blocked"])
        self.assertTrue(routes["reconnect_blocked"])
        self.assertEqual(
            "cfs_reconnect_requires_explicit_recovery",
            routes["reconnect_reason_code"],
        )

    def test_runtime_sources_parse_as_python_38_and_import_no_transport(self):
        forbidden = {
            "asyncio",
            "ctypes",
            "http",
            "paramiko",
            "pathlib",
            "requests",
            "serial",
            "socket",
            "subprocess",
            "time",
            "urllib",
        }
        for filename in ("contract_model.py", "engine.py"):
            source = (PACKAGE / filename).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=filename, feature_version=(3, 8))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertTrue(forbidden.isdisjoint(imported), filename)

    def test_future_blueprint_pins_sources_but_has_no_executable_surface(self):
        result = blueprint.verify()
        self.assertEqual("OK", result["status"])
        self.assertEqual(3, result["files_pinned"])
        self.assertEqual(3, result["future_write_set_count"])
        self.assertEqual(7, result["future_slices"])
        self.assertEqual(0, result["remote_commands"])
        self.assertEqual(0, result["service_actions"])
        self.assertEqual(0, result["gcode_commands"])
        self.assertFalse(result["deployment_candidate"])

    def test_future_blueprint_records_goal_2_and_keeps_effect_paths_missing(self):
        candidate = json.loads(
            (PACKAGE / "future-deployment-blueprint.json").read_text(
                encoding="utf-8"
            )
        )
        qualification = candidate["goal_2_read_only_qualification"]
        self.assertEqual(
            "closed_read_only_blocked_mesh_drift", qualification["status"]
        )
        self.assertEqual(["GET"], qualification["qualified_http_methods"])
        self.assertFalse(qualification["deployment_authorized"])
        missing = set(candidate["intentionally_missing_after_goal_2"])
        self.assertNotIn("real_query_connector", missing)
        self.assertNotIn("live_deadline_qualification", missing)
        self.assertIn("real_command_connector", missing)
        self.assertIn("connection_epoch_notification_wiring", missing)
        self.assertIn("deployment_script", missing)
        self.assertIn("remote_command_encoding", missing)
        self.assertIn("orca_profile_mutation", missing)
        self.assertEqual([], candidate["remote_commands"])


if __name__ == "__main__":
    unittest.main()
