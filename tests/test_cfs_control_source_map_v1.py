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

    def test_architecture_has_qualified_exact_live_restore_but_grants_no_open_authority(self):
        authority = self.source_map["authority"]
        self.assertEqual(
            "direct_CFS_owner_offline_closed_install_disabled_next",
            self.source_map["status"],
        )
        self.assertFalse(authority["printer_connection_authorized"])
        self.assertFalse(authority["printer_mutation_authorized"])
        self.assertFalse(authority["physical_action_authorized"])
        # ADR-036 : le propriétaire CFS direct est implémenté hors imprimante
        # puis posé désactivé. L'autorité d'implémentation est donc ouverte ;
        # connexion, mutation et action physique restent fermées.
        self.assertTrue(authority["implementation_authorized"])
        self.assertTrue(authority["offline_owner_core_completed"])
        self.assertTrue(authority["offline_owner_exclusion_guard_completed"])
        self.assertTrue(authority["live_owner_exclusion_read_only_completed"])
        self.assertTrue(authority["offline_owner_observability_v2_completed"])
        self.assertTrue(authority["live_owner_observability_v2_completed"])
        self.assertTrue(authority["live_owner_exclusion_effect_completed"])
        self.assertTrue(authority["start_owner_installed"])
        self.assertTrue(authority["start_owner_cold_validation_completed"])
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
            "CREALITY-OFFICIAL-HI-KLIPPER-TRANSPORT",
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

    def test_stock_effect_phases_are_historical_and_no_longer_candidates(self):
        candidates = {
            item["command"]: item
            for item in self.source_map["command_decisions"]["rejected_stock_effect_candidates_historical"]
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
            "K1_CONTROL_DIRECT_CFS_OWNER_OVER_STOCK_SERIAL_TRANSPORT",
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

    def test_observability_v2_and_exact_live_restore_are_closed(self):
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
        guard = self.source_map["owner_exclusion_guard_offline"]
        self.assertEqual(
            "OFFLINE_EXCLUSION_GUARD_CLOSED_GREEN_EFFECTS_UNQUALIFIED",
            guard["status"],
        )
        self.assertEqual("25/25", guard["scenario_matrix"])
        self.assertEqual("15/15", guard["targeted_tests"])
        self.assertTrue(guard["saved_value_restored_exactly"])
        self.assertFalse(guard["acknowledgement_is_proof"])
        self.assertFalse(guard["automatic_retry"])
        self.assertFalse(guard["reviewed_intents_dispatchable"])
        self.assertFalse(guard["printer_connection"])
        self.assertFalse(guard["physical_action"])
        self.assertFalse(guard["deployment_candidate"])
        live = self.source_map["owner_exclusion_guard_live_read_only"]
        self.assertEqual(
            "CLOSED_READ_ONLY_BLOCKED_CONNECTION_EPOCH_AND_EFFECTIVE_Z_SOURCE",
            live["status"],
        )
        self.assertEqual(2, live["live_snapshots"])
        self.assertTrue(live["live_state_stable"])
        self.assertTrue(live["configuration_hashes_unchanged"])
        self.assertFalse(live["connection_epoch_observable"])
        self.assertFalse(live["accepted_z_value_observable"])
        self.assertFalse(live["effective_z_source_qualified"])
        self.assertFalse(live["guard_effect_path_called"])
        self.assertFalse(live["rerun_authorized"])
        adapter = self.source_map["owner_observability_adapter_offline_v2"]
        self.assertEqual("12/12", adapter["scenario_matrix"])
        self.assertEqual(
            "gcode_macro KCTRL_STATE.accepted_z_offset",
            adapter["accepted_z_source"],
        )
        self.assertFalse(adapter["homing_origin_substitution_allowed"])
        self.assertFalse(adapter["silent_same_state_driver_reconnect_claimed_detectable"])
        live_v2 = self.source_map["owner_observability_live_read_only_v2"]
        self.assertEqual(
            "CLOSED_READ_ONLY_OBSERVABILITY_V2_QUALIFIED_EFFECTS_CLOSED",
            live_v2["status"],
        )
        self.assertEqual(1, live_v2["moonraker_connections"])
        self.assertEqual(2, live_v2["live_snapshots"])
        self.assertEqual(0, live_v2["reported_cfs_transitions"])
        self.assertEqual(-0.04, live_v2["accepted_z_offset_mm"])
        self.assertTrue(live_v2["all_effects_false"])
        effect = self.source_map["owner_exclusion_guard_live_effect_v1"]
        self.assertEqual(
            "CLOSED_OK_EXCLUSION_AND_EXACT_RESTORE_QUALIFIED",
            effect["status"],
        )
        self.assertEqual(1, effect["saved_value"])
        self.assertEqual(0, effect["disabled_value_proved"])
        self.assertEqual(1, effect["restored_value_proved"])
        self.assertEqual(1, effect["disable_attempts"])
        self.assertEqual(1, effect["restore_attempts"])
        self.assertTrue(effect["same_observer_connection"])
        self.assertEqual(0, effect["reported_cfs_transitions"])
        self.assertFalse(effect["rerun_authorized"])
        next_gate = self.source_map["next_gate"]
        self.assertEqual(
            "G4-K1-CONTROL-CFS-DIRECT-OWNER-INSTALL-DISABLED-V1",
            next_gate["id"],
        )
        # La gate suivante est la pose désactivée : elle n'ouvre pas de
        # connexion imprimante propre et n'envoie aucune trame CFS.
        self.assertFalse(next_gate["printer_connection"])
        self.assertFalse(next_gate["read_only"])
        self.assertFalse(next_gate["CFS_effect"])
        self.assertTrue(next_gate["implementation_authorized"])
        self.assertFalse(next_gate["preflight_completed"])
        self.assertEqual(
            "OFFLINE_PREPARED_NOT_AUTHORIZED",
            next_gate["execution_status"],
        )
        # Pose désactivée : elle écrit des fichiers et redémarre un service,
        # mais n'exécute ni G-code, ni chauffe, ni mouvement, ni extrusion.
        self.assertFalse(next_gate["gcode"])
        self.assertFalse(next_gate["heat"])
        self.assertFalse(next_gate["motion"])
        self.assertFalse(next_gate["extrusion"])
        self.assertTrue(next_gate["remote_write"])
        self.assertTrue(next_gate["service_restart"])
        self.assertFalse(next_gate["physical_trial"])
        self.assertFalse(next_gate["deployment_authorized"])
        self.assertEqual(
            "G4-K1-CONTROL-CFS-DIRECT-OWNER-PHYSICAL-LOAD-UNLOAD-V1",
            next_gate["next_gate"],
        )
        gaps = self.source_map["open_gaps_in_order"]
        self.assertEqual("read_only", gaps[0]["kind"])
        self.assertEqual("resolved", gaps[1]["kind"])
        self.assertEqual("read_only", gaps[2]["kind"])
        for gap in gaps[:3]:
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
            "docs/adr/ADR-036-proprietaire-cfs-direct-sur-transport-serie-borne.md",
            amendment["decision_record"],
        )
        architecture = lifecycle["cfs_control_architecture"]
        self.assertTrue(architecture["auto_refill_feature_preserved"])
        # Ouverte par ADR-036 ; la pose et l'action physique restent fermées.
        self.assertTrue(architecture["implementation_authorized"])
        self.assertTrue(architecture["offline_owner_core_completed"])
        self.assertEqual("21/21", architecture["offline_owner_core_scenarios"])
        self.assertTrue(architecture["offline_owner_exclusion_guard_completed"])
        self.assertEqual("25/25", architecture["offline_owner_exclusion_guard_scenarios"])
        self.assertTrue(architecture["offline_owner_observability_v2_completed"])
        self.assertTrue(architecture["live_owner_observability_v2_completed"])
        self.assertTrue(architecture["live_owner_exclusion_effect_completed"])
        self.assertEqual(
            "CLOSED_OK_EXCLUSION_AND_EXACT_RESTORE_QUALIFIED",
            architecture["live_owner_exclusion_effect_verdict"],
        )
        # Un candidat de pose désactivée existe (13/13), mais sa pose n'est
        # pas autorisée pour autant.
        self.assertTrue(architecture["deployment_candidate"])
        self.assertFalse(architecture["install_disabled_deployment_authorized"])
        self.assertTrue(architecture["start_owner_installed"])
        self.assertEqual("PASS", architecture["start_owner_cold_validation"])
        self.assertTrue(architecture["start_owner_live_read_only_preflight_completed"])
        self.assertEqual(
            "PASS_BLOCKED_NO_T1A",
            architecture["start_owner_live_read_only_preflight_verdict"],
        )
        owner = lifecycle["cfs_owner_core_offline"]
        self.assertEqual("21/21", owner["scenario_matrix"])
        self.assertFalse(owner["recorded_s12_identical_pair_present"])
        self.assertTrue(owner["full_pause_context_compared_before_resume"])
        self.assertFalse(owner["printer_connection"])
        self.assertFalse(owner["real_connector_present"])
        self.assertFalse(owner["deployment_candidate"])
        guard = lifecycle["cfs_owner_exclusion_guard_offline"]
        self.assertEqual("25/25", guard["scenario_matrix"])
        self.assertTrue(guard["stock_auto_refill_previous_value_restored_exactly"])
        self.assertFalse(guard["acknowledgement_is_proof"])
        self.assertFalse(guard["printer_connection"])
        self.assertFalse(guard["real_connector_present"])
        self.assertFalse(guard["deployment_candidate"])
        live = lifecycle["cfs_owner_exclusion_guard_live_read_only"]
        self.assertEqual(
            "closed_read_only_blocked_connection_epoch_and_effective_z_source",
            live["status"],
        )
        self.assertEqual(2, live["live_snapshots"])
        self.assertTrue(live["configuration_hashes_unchanged"])
        self.assertFalse(live["connection_epoch_observable"])
        self.assertFalse(live["accepted_z_value_observable"])
        self.assertFalse(live["effective_z_source_qualified"])
        self.assertFalse(live["guard_effect_path_called"])
        self.assertFalse(live["rerun_authorized"])
        adapter = lifecycle["cfs_owner_observability_adapter_offline_v2"]
        self.assertEqual("12/12", adapter["scenario_matrix"])
        self.assertTrue(adapter["persistent_moonraker_observer_required"])
        self.assertFalse(adapter["silent_same_state_driver_reconnect_claimed_detectable"])
        live_v2 = lifecycle["cfs_owner_observability_live_read_only_v2"]
        self.assertEqual(-0.04, live_v2["accepted_z_offset_mm"])
        self.assertEqual(0, live_v2["reported_cfs_transitions"])
        self.assertTrue(live_v2["all_effects_false"])
        effect = lifecycle["cfs_owner_exclusion_guard_live_effect_v1"]
        self.assertEqual(1, effect["saved_stock_value"])
        self.assertEqual(0, effect["disabled_value_proved"])
        self.assertEqual(1, effect["restored_value_proved"])
        self.assertEqual(1, effect["disable_attempts"])
        self.assertEqual(1, effect["restore_attempts"])
        self.assertFalse(effect["rerun_authorized"])


if __name__ == "__main__":
    unittest.main()
