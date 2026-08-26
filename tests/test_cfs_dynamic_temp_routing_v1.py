from importlib.util import module_from_spec, spec_from_file_location
import ast
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-dynamic-temp-routing-v1"

spec = spec_from_file_location("cfs_dynamic_temp_routing_v1", PACKAGE / "simulator.py")
routing = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = routing
spec.loader.exec_module(routing)


class CfsDynamicTempRoutingV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.options = json.loads(
            (PACKAGE / "architecture-options.json").read_text(encoding="utf-8")
        )
        cls.matrix = json.loads((PACKAGE / "scenarios.json").read_text(encoding="utf-8"))
        cls.results = routing.run_matrix(cls.contract, cls.matrix)
        cls.by_id = {item["id"]: item for item in cls.results}

    def test_package_is_offline_closed_and_has_no_transport(self):
        self.assertEqual("offline_complete_production_closed", self.contract["status"])
        self.assertFalse(self.contract["printer_mutation_authorized"])
        self.assertFalse(self.contract["deployment_candidate"])
        self.assertEqual("absent", self.contract["transport"])
        self.assertTrue(all(value is False for value in self.contract["offline_isolation"].values()))

    def test_architecture_comparison_selects_one_design_without_claiming_deployment(self):
        result = routing.select_architecture(self.options)
        self.assertEqual("minimal_separate_filament_owner", result["selected"])
        self.assertEqual([result["selected"]], result["capable_options"])
        self.assertFalse(result["deployment_candidate"])
        self.assertFalse(result["authorizes_printer_mutation"])

    def test_every_declared_scenario_is_deterministic_and_green(self):
        self.assertEqual(25, len(self.results))
        self.assertTrue(all(item["passed"] for item in self.results), self.results)
        second = routing.run_matrix(self.contract, self.matrix)
        self.assertEqual(self.results, second)

    def test_first_layer_and_normal_targets_remain_distinct_for_nozzle_and_bed(self):
        result = self.by_id["first_layer_then_normal_targets"]["result"]
        boundary = next(item for item in result["trace"] if item["kind"] == "cfs_boundary")
        self.assertEqual(205, boundary["nozzle_target_c"])
        self.assertEqual(60, boundary["bed_target_c"])
        self.assertEqual(200, result["final_state"]["nozzle_target_c"])
        self.assertEqual(55, result["final_state"]["bed_target_c"])

    def test_initial_load_and_cross_material_change_cover_both_cfs(self):
        cfs1 = self.by_id["initial_load_on_cfs1"]["result"]
        cfs2 = self.by_id["initial_load_on_cfs2"]["result"]
        change = self.by_id["cross_material_cfs1_to_cfs2"]["result"]
        self.assertEqual("T3", cfs1["final_state"]["engaged_tool"])
        self.assertEqual("T6", cfs2["final_state"]["engaged_tool"])
        targets = [
            item["nozzle_target_c"]
            for item in change["trace"]
            if item["kind"] == "cfs_boundary"
        ]
        self.assertEqual([200, 235, 225], targets)
        self.assertEqual(1, change["cut_count"])
        self.assertEqual(1, change["unload_count"])
        self.assertEqual("T6", change["final_state"]["engaged_tool"])
        self.assertEqual(235, change["final_state"]["nozzle_target_c"])

    def test_equivalent_refill_and_runout_preserve_the_active_explicit_target(self):
        refill = self.by_id["equivalent_refill_preserves_operator_target"]["result"]
        runout = self.by_id["runout_cross_cfs_preserves_active_target"]["result"]
        self.assertEqual(198, refill["final_state"]["nozzle_target_c"])
        self.assertEqual(200, runout["final_state"]["nozzle_target_c"])
        self.assertIn("p-runout-cfs2", runout["route_proofs_used"])

    def test_normal_pause_has_no_hidden_cfs_cycle_and_reprime_is_explicit(self):
        normal = self.by_id["normal_pause_resume_has_no_cfs_effect"]["result"]
        reprime = self.by_id["resume_reprime_is_explicit"]["result"]
        self.assertEqual(0, normal["effects"])
        self.assertEqual(["pause", "resume"], [item["kind"] for item in normal["trace"]])
        self.assertEqual(1, reprime["effects"])
        self.assertEqual("resume_reprime", reprime["trace"][-1]["operation"])

    def test_target_mismatch_blocks_before_the_first_effect_and_cuts_both_targets(self):
        for scenario_id in (
            "hidden_target_before_effect_blocks",
            "post_tool_reassertion_cannot_repair_purge",
        ):
            result = self.by_id[scenario_id]["result"]
            self.assertEqual("blocked_safe", result["verdict"])
            self.assertEqual("nozzle_target_before_effect_mismatch", result["reason_code"])
            self.assertEqual(0, result["effects"])
            self.assertEqual(0, result["final_state"]["nozzle_target_c"])
            self.assertEqual(0, result["final_state"]["bed_target_c"])
            self.assertFalse(result["resume_armed"])

    def test_cfs_thermal_or_geometry_ownership_is_always_refused(self):
        expected = {
            "cfs_bed_write_blocks": "cfs_bed_command",
            "cfs_nozzle_command_is_forbidden_even_if_equal": "cfs_nozzle_command",
            "geometry_change_blocks_without_blind_z_restore": "forbidden_geometry_command",
        }
        for scenario_id, reason in expected.items():
            result = self.by_id[scenario_id]["result"]
            self.assertEqual(reason, result["reason_code"])
            self.assertFalse(result["blind_z_restore"])
            self.assertFalse(result["resume_armed"])

    def test_unknown_stale_reused_or_inconsistent_routes_fail_closed(self):
        expected = {
            "unknown_route_blocks_before_effect": "route_missing",
            "route_is_stale_after_cfs_reconnect": "route_stale",
            "route_proof_cannot_be_reused": "route_proof_reused",
            "route_material_mismatch_blocks": "route_material_mismatch",
        }
        for scenario_id, reason in expected.items():
            result = self.by_id[scenario_id]["result"]
            self.assertEqual("blocked_safe", result["verdict"])
            self.assertEqual(reason, result["reason_code"])
            self.assertEqual(0, result["final_state"]["nozzle_target_c"])
            self.assertEqual(0, result["final_state"]["bed_target_c"])

    def test_missing_or_incompatible_transition_temperatures_fail_before_effect(self):
        missing = self.by_id["missing_load_temperature_blocks_contract"]["result"]
        incompatible = self.by_id[
            "incompatible_transition_temperature_blocks_contract"
        ]["result"]
        self.assertEqual("job_contract_invalid", missing["reason_code"])
        self.assertEqual("transition_target_out_of_bounds", incompatible["reason_code"])
        self.assertEqual(0, missing["effects"])
        self.assertEqual(0, incompatible["effects"])

    def test_material_database_value_is_not_consumed_as_the_dynamic_target(self):
        result = self.by_id["material_database_value_is_not_dynamic_owner"]["result"]
        self.assertEqual("pass_offline", result["verdict"])
        self.assertEqual(205, result["final_state"]["nozzle_target_c"])
        self.assertEqual(
            "static_safety_net_and_inventory_only",
            self.contract["temperature_authority"]["material_database"],
        )

    def test_runtime_source_imports_no_network_serial_or_process_transport(self):
        source = (PACKAGE / "simulator.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(PACKAGE / "simulator.py"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(
            {"socket", "subprocess", "serial", "paramiko", "requests"}.isdisjoint(imported)
        )
        self.assertFalse(any(path.suffix.lower() in {".ps1", ".sh"} for path in PACKAGE.rglob("*")))

    def test_runtime_and_contract_contain_no_material_setpoint_constant(self):
        source = (PACKAGE / "simulator.py").read_text(encoding="utf-8")
        contract_text = (PACKAGE / "contract.json").read_text(encoding="utf-8")
        for token in ("190", "195", "205", "220", "235", "240"):
            self.assertNotIn(token, source)
            self.assertNotIn(token, contract_text)

    def test_canonical_lifecycle_contract_exposes_load_target_and_closed_router(self):
        lifecycle = json.loads(
            (ROOT / "design" / "job-lifecycle-contract-v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn("transition_load_targets_c", lifecycle["job_contract"]["required_fields"])
        router = lifecycle["cfs_dynamic_temperature_routing"]
        self.assertEqual("minimal_separate_filament_owner", router["selected_architecture"])
        self.assertFalse(router["printer_transport"])
        self.assertFalse(router["deployment_candidate"])
        self.assertFalse(router["physical_test_authorized"])

    def test_documentation_maps_the_exact_resolver_and_keeps_physical_validation_open(self):
        design = (ROOT / "docs" / "31-routage-dynamique-temperatures-cfs-v1.md").read_text(
            encoding="utf-8"
        )
        result = (PACKAGE / "RESULT.md").read_text(encoding="utf-8")
        self.assertIn("get_material_target_temp", design)
        self.assertIn("minimal_separate_filament_owner", design)
        self.assertIn("aucun transport K1", design)
        self.assertIn("25/25", result)
        self.assertIn("validation physique : non exécutée", result)


if __name__ == "__main__":
    unittest.main()
