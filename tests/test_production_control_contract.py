import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "design" / "job-lifecycle-contract-v1.json"
LEGACY_CONTRACT_PATH = ROOT / "design" / "production-control-contract.json"
REJECTED_ZSAFE_PATH = ROOT / "overrides" / "g4-zsafe-start" / "sequence-contract.json"


class ProductionControlContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        cls.sequence = cls.contract["start_sequence"]

    def stage(self, stage_id: str) -> dict:
        return next(stage for stage in self.sequence if stage["id"] == stage_id)

    def position(self, stage_id: str) -> int:
        return next(index for index, stage in enumerate(self.sequence) if stage["id"] == stage_id)

    def test_contract_is_complete_offline_and_never_authorizes_printer_mutation(self) -> None:
        self.assertEqual(
            self.contract["status"],
            "direct_CFS_physical_v1_closed_before_effect_integrated_cutter_purge_successor_offline",
        )
        self.assertFalse(self.contract["printer_mutation_authorized"])
        self.assertFalse(
            self.contract["job_lifecycle_offline"]["real_connector_present"]
        )
        self.assertFalse(
            self.contract["cfs_stock_unload_guard_transport_offline"]["deployment_candidate"]
        )
        self.assertIn("production_cutover", self.contract["deployment"])
        self.assertIn("not implemented", self.contract["deployment"]["production_cutover"])

    def test_legacy_contract_points_to_the_frozen_contract(self) -> None:
        legacy = json.loads(LEGACY_CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            legacy["status"],
            "superseded_by_job_lifecycle_v1_frozen_offline",
        )
        self.assertEqual(legacy["superseded_by"], "design/job-lifecycle-contract-v1.json")

    def test_z_has_no_hidden_numeric_default_or_implicit_commit(self) -> None:
        z = self.contract["z"]
        self.assertIsNone(z["numeric_default_mm"])
        self.assertEqual(z["source"], "accepted_calibration_record")
        self.assertFalse(z["implicit_commit_on_print_end"])
        self.assertTrue(z["legacy_hidden_offset_forbidden"])
        self.assertEqual(self.sequence[-1]["id"], "end_without_calibration_commit")

    def test_mesh_key_includes_plate_temperature_probe_and_nozzle(self) -> None:
        self.assertEqual(
            self.contract["mesh"]["profile_key"],
            [
                "plate_id",
                "bed_temperature_band_c",
                "probe_reference_revision",
                "nozzle_id",
                "nozzle_diameter_mm",
            ],
        )
        self.assertEqual(self.contract["mesh"]["daily_measurement_probe_count"], [6, 6])
        self.assertEqual(
            self.contract["mesh"]["best_current_profile"],
            "k1_p001_t055_r001_n11x11",
        )
        self.assertIsNone(self.contract["mesh"]["current_robust_profile"])
        self.assertTrue(self.contract["mesh"]["all_current_profiles_have_edge_defects"])
        self.assertEqual(self.contract["mesh"]["daily_measurement_algorithm"], "lagrange")
        self.assertTrue(self.contract["mesh"]["precision"]["ui_hidden"])
        self.assertIn("silent_nearest_profile_selection", self.contract["mesh"]["forbidden"])

    def test_filament_state_is_not_reduced_to_a_switch(self) -> None:
        state = self.contract["filament_state"]
        self.assertEqual(
            set(state["states"]),
            {"absent_confirmed", "engaged_known", "engaged_unknown", "transitioning", "fault"},
        )
        self.assertIn("nozzle_flow", state["presence_sensor_does_not_prove"])
        self.assertIn("nozzle_not_clogged", state["presence_sensor_does_not_prove"])
        self.assertTrue(state["hardcoded_physical_tool_forbidden"])
        self.assertEqual(state["exact_machine_observation"]["mapping_status"], "unqualified")

    def test_temperature_owner_is_explicit_for_every_phase(self) -> None:
        temperature = self.contract["temperature"]
        self.assertEqual(temperature["print_owner"], "gcode_or_explicit_operator_change")
        self.assertEqual(temperature["equivalent_refill"], "preserve_active_target")
        change = temperature["intentional_tool_change"]
        self.assertEqual(change["outgoing_unload"], "previous_accepted_material_temperature")
        self.assertIn("explicit_job_contract", change["transition_purge"])
        self.assertEqual(change["incoming_print"], "next_tool_gcode_target")
        self.assertIn("hidden_220_celsius_fallback", temperature["forbidden"])
        self.assertIn("universal_plus_10_or_plus_20_cleaning_delta", temperature["forbidden"])

    def test_cleaning_uses_coarse_reference_and_never_probes_brush_z(self) -> None:
        cleaning = self.contract["standalone_nozzle_cleaning"]
        self.assertIn("home_xy_and_coarse_z_only_if_needed", cleaning["sequence"])
        self.assertIn("park_safely_over_waste_chute", cleaning["sequence"])
        self.assertIn("descend_to_versioned_human_calibrated_brush_plane", cleaning["sequence"])
        self.assertEqual(
            cleaning["brush_z_probe"],
            "forbidden_until_a_real_sensor_path_is_proven",
        )
        self.assertEqual(cleaning["cooling_wipe"], "absent_from_v1_until_material_specific_physical_qualification")
        self.assertEqual(cleaning["extrusion"], "forbidden")

    def test_final_reference_mesh_and_z_precede_production_arm(self) -> None:
        arm = self.position("arm_production_low_moves")
        for stage_id in ("final_z_reference", "resolve_mesh_policy", "resolve_effective_z"):
            self.assertLess(self.position(stage_id), arm)

    def test_owned_start_has_manual_clean_and_one_z_reference_without_rough_reference(self) -> None:
        self.assertLess(self.position("confirm_manual_nozzle_clean"), self.position("final_z_reference"))
        self.assertLess(self.position("final_z_reference"), self.position("resolve_initial_filament"))
        self.assertEqual(1, self.stage("final_z_reference")["maximum_execution_count"])
        self.assertFalse(any(stage["id"] == "rough_reference" for stage in self.sequence))
        self.assertFalse(any(stage["id"] == "controlled_nozzle_clean" for stage in self.sequence))

    def test_no_production_hazard_occurs_before_arm_and_flow_proof_precedes_print(self) -> None:
        arm = self.position("arm_production_low_moves")
        hazards = [stage for stage in self.sequence if stage.get("hazard")]
        self.assertGreaterEqual(len(hazards), 4)
        for stage in hazards:
            self.assertIn("production_low_moves_armed", stage.get("requires", []), stage["id"])
            self.assertGreater(self.position(stage["id"]), arm)
        self.assertLess(self.position("purge_and_verify_flow"), self.position("prime_line"))
        self.assertLess(self.position("prime_line"), self.position("print_model"))

    def test_initial_filament_branches_keep_change_load_or_block(self) -> None:
        branches = self.contract["initial_filament_branches"]
        self.assertEqual(
            branches["keep_correct"][:2],
            ["reconcile_route_without_motor_if_needed", "direct_unload_before_clean"],
        )
        self.assertIn("visible_purge", branches["load_absent"])
        self.assertIn("explicit_transition_purge", branches["change_wrong"])
        self.assertIn("block", branches["unknown"])
        self.assertIn("unknown", self.stage("resolve_initial_filament")["branches"])
        self.assertIn("initial_filament_ready", self.stage("purge_and_verify_flow")["requires"])

    def test_mid_print_change_preserves_full_state_and_forbids_homing(self) -> None:
        change = self.contract["mid_print_change"]
        self.assertTrue(change["no_homing"])
        self.assertIn("mesh_and_effective_z", change["snapshot"])
        self.assertIn("pressure_advance", change["snapshot"])
        self.assertIn("collision_free_route", change["safe_path"])
        self.assertEqual(change["rear_purge_role"], "remove_previous_material")
        self.assertIn("stabilize_pressure", change["slicer_prime_tower_role"])

    def test_end_requires_full_unload_and_rewind(self) -> None:
        end = self.contract["end_policy"]
        self.assertEqual(end["default_candidate"], "full_unload_and_rewind")
        self.assertTrue(end["default_requires_physical_qualification"])
        self.assertFalse(end["automatic_cut_and_unload_by_habit"])
        self.assertTrue(end["normal_end_direct_full_unload_required"])
        self.assertFalse(end["normal_end_cut_and_unload_required"])
        self.assertTrue(end["explicit_material_unload_temperature_required"])
        self.assertTrue(end["single_attempt_no_retry"])
        self.assertTrue(end["safe_park_before_motor_release"])
        self.assertEqual(end["manual_action"], "Clean nozzle only before a future contact reference")
        self.assertFalse(end["unattended_delayed_reheat"])
        self.assertIn("filament_state_known_empty_and_rewound", end["final_state"])

    def test_calibration_policy_distinguishes_contact_and_extrusion_work(self) -> None:
        policy = self.contract["calibration_policy"]
        self.assertIn("manual_clean_default", policy["contact_z_or_mesh"])
        self.assertIn("direct_unload", policy["contact_z_or_mesh_filament"])
        self.assertEqual(policy["flow_temperature_retraction_pressure_advance"], "resolved_filament_required")
        self.assertIn("cold_no_extrusion", policy["brush"])

    def test_job_contract_is_atomic_and_never_assumes_a_physical_tool(self) -> None:
        job = self.contract["job_contract"]
        self.assertEqual(job["entry_point"], "KCTRL_JOB_BEGIN")
        self.assertTrue(job["logical_tool_only"])
        self.assertIn("transition_purge_targets_c", job["required_fields"])
        self.assertIn("standalone_Tn", job["forbidden_entry_points"])
        self.assertEqual(
            set(job["changed_atomically"]),
            {"machine_start_gcode", "machine_end_gcode", "tool_change_gcode", "printer_side_contract"},
        )

    def test_offline_matrix_covers_every_new_failure_boundary(self) -> None:
        scenario_ids = {scenario["id"] for scenario in self.contract["required_offline_scenarios"]}
        required = {
            "clean_brush_z_not_probed",
            "start_correct_filament_engaged",
            "start_wrong_filament_engaged",
            "start_no_filament",
            "start_unknown_filament_identity",
            "sensor_present_no_nozzle_flow",
            "intentional_cross_material_change",
            "cross_cfs_change",
            "pause_normal",
            "tall_part_blocks_rear_path",
            "end_full_unload",
            "manual_disengage_and_clean",
            "cfs_late_220_rewrite",
            "cancel_and_reboot_each_phase",
            "deployment_slice_rollback",
        }
        self.assertTrue(required.issubset(scenario_ids))
        self.assertGreaterEqual(len(scenario_ids), 20)

    def test_old_fixed_z_package_is_explicitly_rejected(self) -> None:
        rejected = json.loads(REJECTED_ZSAFE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(rejected["status"], "rejected_never_deploy")
        self.assertFalse(rejected["deployment_authorized"])


if __name__ == "__main__":
    unittest.main()
