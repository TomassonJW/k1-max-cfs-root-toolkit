import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "design" / "production-control-contract.json"
REJECTED_ZSAFE_PATH = ROOT / "overrides" / "g4-zsafe-start" / "sequence-contract.json"


class ProductionControlContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        cls.sequence = cls.contract["sequence"]

    def stage(self, stage_id: str) -> dict:
        return next(stage for stage in self.sequence if stage["id"] == stage_id)

    def position(self, stage_id: str) -> int:
        return next(index for index, stage in enumerate(self.sequence) if stage["id"] == stage_id)

    def test_contract_never_authorizes_printer_mutation(self) -> None:
        self.assertEqual(self.contract["status"], "offline_runtime_candidate")
        self.assertFalse(self.contract["printer_mutation_authorized"])
        self.assertEqual(
            self.contract["deployment"]["active_g4_candidate"],
            "G4-K1-CONTROL-Z-MESH-RUNTIME-V1",
        )

    def test_z_has_no_hidden_numeric_default(self) -> None:
        z = self.contract["z_calibration"]
        self.assertIsNone(z["numeric_default_mm"])
        self.assertEqual(z["production_source"], "accepted_calibration_record")
        self.assertIn("universal_fixed_offset", z["forbidden"])

    def test_z_commit_is_explicit_and_not_print_end(self) -> None:
        z = self.contract["z_calibration"]
        self.assertEqual(z["commit"]["mode"], "explicit_user_action")
        self.assertEqual(z["commit"]["command"], "KCTRL_Z_COMMIT")
        self.assertIn("implicit_commit_on_print_end", z["forbidden"])
        self.assertEqual(self.sequence[-1]["id"], "end_without_calibration_commit")

    def test_z_survives_restart_but_calibration_invalidates_it(self) -> None:
        z = self.contract["z_calibration"]
        self.assertIn("printer_restart", z["survives"])
        self.assertIn("power_cycle", z["survives"])
        self.assertIn("probe_reference_calibration", z["invalidated_by"])
        self.assertIn("system_calibration_affecting_z", z["invalidated_by"])
        self.assertNotIn("printer_restart", z["invalidated_by"])

    def test_mesh_is_keyed_by_plate_temperature_and_reference(self) -> None:
        key = self.contract["mesh"]["reference_profile_key"]
        self.assertEqual(
            key,
            ["plate_id", "bed_temperature_band_c", "probe_reference_revision"],
        )
        self.assertFalse(self.contract["mesh"]["adaptive"]["persist_after_job"])
        self.assertFalse(self.contract["mesh"]["adaptive"]["reuse_for_other_job"])

    def test_final_reference_mesh_and_z_precede_production_arm(self) -> None:
        arm = self.position("arm_production_low_moves")
        for stage_id in ("final_z_reference", "resolve_mesh_policy", "resolve_effective_z"):
            self.assertLess(self.position(stage_id), arm)

    def test_every_production_hazard_requires_the_closed_gate_output(self) -> None:
        hazards = [stage for stage in self.sequence if stage.get("hazard")]
        self.assertGreaterEqual(len(hazards), 3)
        for stage in hazards:
            self.assertIn("production_low_moves_armed", stage.get("requires", []), stage["id"])

    def test_only_controlled_probe_or_cleaning_paths_exist_before_arm(self) -> None:
        arm = self.position("arm_production_low_moves")
        allowed_low_kinds = {"controlled_probe_path", "controlled_cleaning_path"}
        pre_arm_low_paths = [
            stage for stage in self.sequence[:arm]
            if stage["kind"] in allowed_low_kinds
        ]
        self.assertEqual(
            [stage["id"] for stage in pre_arm_low_paths],
            ["rough_reference", "controlled_nozzle_clean", "final_z_reference"],
        )
        self.assertNotIn(
            "hazard",
            self.stage("controlled_nozzle_clean"),
            "the cleaning path is controlled, not a production purge",
        )

    def test_temperature_owner_is_dynamic_across_cfs_paths(self) -> None:
        temperature = self.contract["temperature"]
        self.assertEqual(temperature["print_owner"], "gcode_or_explicit_operator_change")
        self.assertEqual(temperature["equivalent_refill"], "preserve_active_target")
        self.assertEqual(temperature["intentional_tool_change"], "next_tool_gcode_target")
        self.assertIn("fixed_material_temperature", temperature["forbidden"])

    def test_orca_and_printer_contract_change_together(self) -> None:
        orca = self.contract["orca_contract"]
        self.assertTrue(orca["versioned"])
        self.assertEqual(
            set(orca["changed_atomically"]),
            {
                "machine_start_gcode",
                "machine_end_gcode",
                "tool_change_gcode",
                "printer_side_contract",
            },
        )
        self.assertFalse(orca["legacy_z_postprocessor_removed_before_replacement_proven"])

    def test_daily_and_expert_interfaces_are_both_present(self) -> None:
        interfaces = self.contract["interfaces"]
        self.assertEqual(interfaces["daily"], "K1 Control")
        self.assertEqual(interfaces["expert_candidate"], "Mainsail")
        self.assertTrue(interfaces["creality_interfaces_retained"])

    def test_required_offline_matrix_covers_z_mesh_two_cfs_orca_and_rollback(self) -> None:
        scenario_ids = {
            scenario["id"] for scenario in self.contract["required_offline_scenarios"]
        }
        self.assertEqual(
            scenario_ids,
            {
                "z_live_adjust_then_commit",
                "z_cancel_calibration",
                "z_print_end_and_restart",
                "z_new_reference_calibration",
                "mesh_reference_plate_temperature_match",
                "mesh_reference_mismatch",
                "mesh_adaptive_job",
                "safe_start_sequence",
                "cfs_initial_load",
                "cfs_equivalent_refill",
                "cfs_intentional_tool_change",
                "cfs_cross_unit_change",
                "pause_resume",
                "cancel_and_end",
                "explicit_operator_temperature_change",
                "orca_contract_version_mismatch",
                "deployment_slice_rollback",
            },
        )
        cross_cfs = next(
            scenario
            for scenario in self.contract["required_offline_scenarios"]
            if scenario["id"] == "cfs_cross_unit_change"
        )
        self.assertIn("two_cfs", cross_cfs["expected"])

    def test_old_fixed_z_package_is_explicitly_rejected(self) -> None:
        rejected = json.loads(REJECTED_ZSAFE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(rejected["status"], "rejected_never_deploy")
        self.assertFalse(rejected["deployment_authorized"])


if __name__ == "__main__":
    unittest.main()
