import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "design" / "cfs-control-source-map-v1.json"
LIFECYCLE_PATH = ROOT / "design" / "job-lifecycle-contract-v1.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class CfsControlSourceMapV1Tests(unittest.TestCase):
    def setUp(self):
        self.source_map = load_json(MAP_PATH)

    def test_architecture_has_offline_core_but_cannot_authorize_effects(self):
        authority = self.source_map["authority"]
        self.assertEqual(
            "owner_core_offline_complete_effects_and_deployment_closed",
            self.source_map["status"],
        )
        self.assertFalse(authority["printer_connection_authorized"])
        self.assertFalse(authority["printer_mutation_authorized"])
        self.assertFalse(authority["physical_action_authorized"])
        self.assertFalse(authority["implementation_authorized"])
        self.assertTrue(authority["offline_owner_core_completed"])
        self.assertFalse(authority["deployment_candidate"])

    def test_required_evidence_sources_are_pinned_and_ranked(self):
        sources = {source["id"]: source for source in self.source_map["sources"]}
        required = {
            "LOCAL-K1-CONTROL-EVIDENCE",
            "LOCAL-BOX-WRAPPER",
            "HELIXSCREEN-CFS-INTERNALS",
            "FREDERICKALT-BOX-WRAPPER",
            "CREALITY-OFFICIAL-SOURCES",
            "CFSTOOL",
            "GITSTONELABS-OPEN-DRIVER",
            "SLICK1MAX",
            "NIK-OLI-HELPER-SCRIPT",
            "ORCASLICER-ISSUE-14191",
        }
        self.assertEqual(required, set(sources))
        for source_id in (
            "HELIXSCREEN-CFS-INTERNALS",
            "FREDERICKALT-BOX-WRAPPER",
            "CREALITY-OFFICIAL-SOURCES",
            "CFSTOOL",
            "GITSTONELABS-OPEN-DRIVER",
            "SLICK1MAX",
            "NIK-OLI-HELPER-SCRIPT",
        ):
            self.assertRegex(sources[source_id]["revision"], re.compile(r"^[0-9a-f]{40}$"))
        self.assertEqual(
            "exact_local_physical_capture",
            self.source_map["evidence_precedence"][0],
        )
        self.assertIn(
            "install_HelixScreen_as_lifecycle_owner",
            sources["HELIXSCREEN-CFS-INTERNALS"]["rejected_use"],
        )
        for source in sources.values():
            for reference in source.get("references", []):
                if reference.startswith("https://"):
                    continue
                self.assertTrue((ROOT / reference).is_file(), reference)

    def test_full_stock_sequences_and_hidden_cleaning_are_forbidden(self):
        decisions = self.source_map["command_decisions"]
        forbidden_entry = set(decisions["forbidden_owned_entry_points"])
        self.assertTrue(
            {
                "START_PRINT",
                "BOX_START_PRINT",
                "BOX_START_PRINT_EXTRUDE_MATERIAL",
                "Tn",
                "CX_NOZZLE_CLEAR",
                "BED_MESH_CALIBRATE",
            }.issubset(forbidden_entry)
        )
        forbidden_cfs = set(decisions["forbidden_automatic_CFS_commands"])
        self.assertTrue(
            {
                "BOX_NOZZLE_CLEAN",
                "BOX_MATERIAL_FLUSH",
                "BOX_MATERIAL_CHANGE_FLUSH",
                "BOX_ERROR_CLEAR",
                "BOX_TNN_RETRY_PROCESS",
                "BOX_CHECK_MATERIAL_REFILL",
                "BOX_EXTRUSION_ALL_MATERIALS",
                "BOX_RESUME_EXTRUDE",
                "BOX_RETRUDE_MATERIAL_WITH_TNN",
            }.issubset(forbidden_cfs)
        )

    def test_only_bounded_stock_phases_remain_candidates(self):
        candidates = {
            item["command"]: item
            for item in self.source_map["command_decisions"]["bounded_effect_candidates_not_yet_qualified"]
        }
        self.assertEqual(
            {
                "BOX_EXTRUDE_MATERIAL",
                "BOX_EXTRUDER_EXTRUDE",
                "BOX_CUT_MATERIAL",
                "BOX_RETRUDE_MATERIAL",
                "BOX_ENABLE_AUTO_REFILL",
            },
            set(candidates),
        )
        for candidate in candidates.values():
            self.assertGreaterEqual(len(candidate["requirements"]), 4)
        self.assertIn(
            "exact_S12_motion_inventory",
            candidates["BOX_CUT_MATERIAL"]["requirements"],
        )

    def test_k1_control_is_the_only_lifecycle_owner(self):
        architecture = self.source_map["selected_architecture"]
        self.assertEqual(
            "K1_CONTROL_LIFECYCLE_OWNER_OVER_SELECTED_STOCK_BOX_PRIMITIVES",
            architecture["id"],
        )
        self.assertFalse(architecture["direct_RS485_driver_for_v1"])
        self.assertFalse(architecture["HelixScreen_as_owner"])
        owner_rule = architecture["one_owner_rule"]
        self.assertTrue(owner_rule["owner_lease_required"])
        self.assertTrue(owner_rule["stock_auto_refill_disabled_while_custom_owner_active"])
        self.assertFalse(owner_rule["stock_Tn_and_full_cycle_macros_called"])
        self.assertEqual(
            "block_without_filament_effect",
            owner_rule["ambiguous_owner_state"],
        )

    def test_owned_start_has_one_clean_reference_and_no_brush(self):
        start = self.source_map["owned_start"]
        self.assertIn("one_ACCURATE_G28_only", start["sequence"])
        self.assertIn("load_and_verify_11x11_mesh", start["sequence"])
        self.assertFalse(start["mesh_calibration_at_start"])
        self.assertFalse(start["automatic_brushing"])
        self.assertFalse(start["additional_Z_reference_after_filament_effect"])

    def test_custom_auto_refill_is_preserved_but_fails_closed(self):
        refill = self.source_map["owned_auto_refill"]
        self.assertTrue(refill["feature_preserved"])
        self.assertEqual("K1_Control_lifecycle_owner", refill["provided_by"])
        self.assertFalse(refill["stock_auto_refill_used_for_job"])
        self.assertIn(
            "same_user_approved_material_reference_id",
            refill["identical_filament_requires"],
        )
        self.assertIn(
            "replacement_slot_live_material_sensor_present",
            refill["identical_filament_requires"],
        )
        self.assertIn(
            "execute_one_qualified_bounded_tail_consume_or_retract_recipe",
            refill["sequence"],
        )
        self.assertIn("resume_without_homing_or_Z_reference", refill["sequence"])
        self.assertEqual(
            "remain_paused_heaters_follow_explicit_safe_policy_no_automatic_resume",
            refill["ambiguous_or_failed_state"],
        )

    def test_rollback_restores_exact_previous_state_and_tells_the_truth(self):
        rollback = self.source_map["rollback"]
        self.assertTrue(rollback["required"])
        self.assertFalse(rollback["stock_macro_bodies_modified"])
        self.assertFalse(rollback["direct_RS485_driver_installed"])
        self.assertIn(
            "stock_auto_refill_runtime_value",
            rollback["backup_before_enable"],
        )
        self.assertIn(
            "restore_previous_stock_auto_refill_runtime_value",
            rollback["rollback_sequence"],
        )
        self.assertIn("known_start_defects", rollback["truthful_limit"])

    def test_s12_preflight_and_owner_core_are_closed_and_next_gate_is_offline_only(self):
        preflight = self.source_map["s12_preflight"]
        self.assertEqual(
            "CLOSED_READ_ONLY_S12_SURFACE_CONFIRMED_EFFECTS_CLOSED",
            preflight["status"],
        )
        self.assertTrue(preflight["exact_binary_matches_historical_capture"])
        self.assertTrue(preflight["required_command_names_present"])
        self.assertTrue(preflight["required_callback_markers_present"])
        self.assertFalse(preflight["stock_identical_replacement_pair_present_at_capture"])
        owner = self.source_map["owner_core_offline"]
        self.assertEqual(
            "OFFLINE_OWNER_CORE_CLOSED_GREEN_EFFECTS_UNQUALIFIED",
            owner["status"],
        )
        self.assertEqual("21/21", owner["scenario_matrix"])
        self.assertTrue(owner["single_owner_lease_modeled"])
        self.assertTrue(owner["cross_cfs_identical_replacement_modeled"])
        self.assertFalse(owner["recorded_s12_identical_pair_present"])
        self.assertTrue(owner["full_pause_context_compared_before_resume"])
        self.assertFalse(owner["abstract_intents_dispatchable"])
        self.assertFalse(owner["printer_connection"])
        self.assertFalse(owner["physical_action"])
        self.assertFalse(owner["deployment_candidate"])
        next_gate = self.source_map["next_gate"]
        self.assertEqual(
            "G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-OFFLINE-V1",
            next_gate["id"],
        )
        self.assertFalse(next_gate["printer_connection"])
        self.assertFalse(next_gate["implementation_authorized"])
        for field in ("gcode", "heat", "motion", "CFS_effect", "remote_write", "service_restart"):
            self.assertFalse(next_gate[field])
        gaps = self.source_map["open_gaps_in_order"]
        for gap in gaps[:3]:
            self.assertEqual("read_only", gap["kind"])
            self.assertFalse(gap["allows_effect"])
        for gap in gaps[3:]:
            self.assertEqual("bounded_physical", gap["kind"])
            self.assertTrue(gap["allows_effect"])

    def test_lifecycle_contract_links_the_offline_core_without_promoting_it(self):
        lifecycle = load_json(LIFECYCLE_PATH)
        amendments = {item["id"]: item for item in lifecycle["amendments"]}
        amendment = amendments["CFS-CONTROL-SOURCE-MAP-V1"]
        self.assertEqual("design/cfs-control-source-map-v1.json", amendment["path"])
        self.assertEqual(
            "docs/adr/ADR-032-proprietaire-cycle-cfs-sur-primitives-stock.md",
            amendment["decision_record"],
        )
        architecture = lifecycle["cfs_control_architecture"]
        self.assertTrue(architecture["auto_refill_feature_preserved"])
        self.assertFalse(architecture["implementation_authorized"])
        self.assertTrue(architecture["offline_owner_core_completed"])
        self.assertEqual("21/21", architecture["offline_owner_core_scenarios"])
        self.assertFalse(architecture["deployment_candidate"])
        owner = lifecycle["cfs_owner_core_offline"]
        self.assertEqual("21/21", owner["scenario_matrix"])
        self.assertFalse(owner["recorded_s12_identical_pair_present"])
        self.assertTrue(owner["full_pause_context_compared_before_resume"])
        self.assertFalse(owner["printer_connection"])
        self.assertFalse(owner["real_connector_present"])
        self.assertFalse(owner["deployment_candidate"])


if __name__ == "__main__":
    unittest.main()
