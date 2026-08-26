from importlib.util import module_from_spec, spec_from_file_location
import ast
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-minimal-owner-protocol-v1"

spec = spec_from_file_location("cfs_minimal_owner_protocol_v1", PACKAGE / "emulator.py")
protocol = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = protocol
spec.loader.exec_module(protocol)


class CfsMinimalOwnerProtocolV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.evidence = json.loads(
            (PACKAGE / "evidence-map.json").read_text(encoding="utf-8")
        )
        cls.matrix = json.loads(
            (PACKAGE / "scenarios.json").read_text(encoding="utf-8")
        )
        cls.results = protocol.run_matrix(cls.contract, cls.evidence, cls.matrix)
        cls.by_id = {item["id"]: item for item in cls.results}

    def test_gate_is_a_bounded_ko_with_empty_callable_surface(self):
        self.assertEqual(
            "closed_ko_bounded_evidence_incomplete", self.contract["status"]
        )
        self.assertEqual("KO_BOUNDED", self.contract["gate_verdict"])
        self.assertEqual([], self.contract["callable_messages"])
        self.assertEqual([], self.contract["callable_operations"])
        self.assertFalse(self.contract["deployment_candidate"])
        self.assertFalse(self.contract["printer_connection_authorized"])
        self.assertFalse(self.contract["physical_test_authorized"])
        self.assertEqual("absent", self.contract["transport"])

    def test_all_25_fail_closed_scenarios_are_deterministic(self):
        self.assertEqual(25, len(self.results))
        self.assertTrue(all(item["passed"] for item in self.results), self.results)
        self.assertEqual(
            self.results,
            protocol.run_matrix(self.contract, self.evidence, self.matrix),
        )

    def test_duplicate_loss_late_response_and_reconnect_are_modelled(self):
        expected = {
            "duplicate_pending_request_is_blocked": "duplicate_pending_key",
            "lost_response_times_out_and_quarantines_key": "response_timeout",
            "late_response_after_timeout_is_never_an_ack": "late_response_quarantined",
            "response_from_before_reconnect_stays_quarantined": "late_response_quarantined",
        }
        for scenario_id, code in expected.items():
            result = self.by_id[scenario_id]["result"]
            self.assertEqual("blocked_safe", result["verdict"])
            self.assertEqual(code, result["last_code"])

    def test_unmatched_event_never_completes_another_request(self):
        result = self.by_id["unmatched_observed_response_is_event_not_ack"]["result"]
        self.assertEqual("uncorrelated_event_not_ack", result["last_code"])
        self.assertEqual(1, result["pending_count"])

    def test_two_cfs_are_observed_for_queries_but_not_for_effects(self):
        query = self.by_id["two_chained_CFS_query_keys_can_coexist_offline"]["result"]
        effect = self.by_id["effect_on_missing_second_CFS_route_is_blocked"]["result"]
        self.assertEqual(2, query["pending_count"])
        self.assertEqual("pass_offline", query["verdict"])
        self.assertIn("route_missing", effect["trace"][-1]["blockers"])
        self.assertEqual(
            [1],
            next(
                item["observed_addresses"]
                for item in self.evidence["absence_queries"]
                if item["claim"] == "no_extrude_process_request_for_address_2"
            ),
        )

    def test_only_T1A_has_an_exact_action_route_observation(self):
        self.assertEqual(
            ["T1A"],
            [item["logical_tool"] for item in self.evidence["observed_route_actions"]],
        )
        good = self.by_id["exact_T1A_route_is_observation_only"]["result"]
        second = self.by_id["T2A_effect_route_is_not_in_evidence"]["result"]
        self.assertEqual("captured_observation_only_not_production_proof", good["routes"]["T1A"]["scope"])
        self.assertEqual("route_not_tied_to_exact_evidence", second["last_code"])

    def test_every_versioned_request_has_unique_exact_proof_and_is_not_callable(self):
        items = self.evidence["observed_request_frames"]
        ids = [item["evidence_id"] for item in items]
        self.assertEqual(len(ids), len(set(ids)))
        for item in items:
            frame = item["frame"]
            self.assertEqual(len(frame) - 1, frame[1])
            self.assertEqual(255, frame[2])
            self.assertTrue(item["proof"].startswith("full_log:"))
            self.assertNotIn(item["command"], self.contract["callable_messages"])

    def test_method_names_without_frames_remain_blocked(self):
        symbols = {item["symbol"] for item in self.evidence["method_name_only"]}
        self.assertIn("communication_retrude_process", symbols)
        self.assertIn("communication_ctrl_connection_motor_action", symbols)
        for scenario_id in (
            "retrude_symbol_does_not_make_a_callable_frame",
            "connection_motor_symbol_does_not_make_a_callable_frame",
            "cut_name_does_not_make_a_callable_frame",
            "extrude2_symbol_does_not_make_a_callable_frame",
        ):
            self.assertEqual(
                "method_name_only_not_callable",
                self.by_id[scenario_id]["result"]["last_code"],
            )

    def test_private_sources_are_pinned_but_identity_payloads_are_not_versioned(self):
        expected_hashes = {
            "af630c02ccdb51b57585114e5be2be7fcf91fdb10d88872eb6a0c65f048de777",
            "a937c5348aebd083e9bd9cdc0b672c0f7fd94c9c6fe6a2f7d8a67d7e117cb79e",
            "2bf09d01dbffaf0323237a336bc69c6b21ac54e841bc246c4b8f577c55e4ea6e",
            "b02d486f7c475e47407b21c70f7bda76ff6c66baca246d71f541f3f820a4759d",
        }
        self.assertEqual(
            expected_hashes,
            {item["sha256"] for item in self.evidence["sources"].values()},
        )
        self.assertFalse(self.evidence["privacy"]["serial_numbers_or_unique_ids_versioned"])
        self.assertFalse(
            self.evidence["privacy"]["response_payloads_with_identity_data_versioned"]
        )

    def test_runtime_and_verifier_import_no_transport_or_binary_loader(self):
        forbidden = {
            "ctypes",
            "importlib",
            "paramiko",
            "requests",
            "serial",
            "socket",
            "subprocess",
        }
        for filename in ("emulator.py", "verify_private_evidence.py"):
            source = (PACKAGE / filename).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(PACKAGE / filename))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertTrue(forbidden.isdisjoint(imported), (filename, imported))
        self.assertFalse(
            any(path.suffix.lower() in {".ps1", ".sh"} for path in PACKAGE.rglob("*"))
        )

    def test_heartbeat_line_is_not_promoted_to_owner_exclusion(self):
        ownership = self.evidence["ownership"]
        self.assertEqual("not_proven", ownership["stock_owner_exclusion"])
        self.assertFalse(ownership["heartbeat_disabled_is_owner_exclusion"])
        result = self.by_id["observed_query_is_still_not_callable"]["result"]
        self.assertIn("stock_owner_exclusion_unproven", result["trace"][-1]["blockers"])

    def test_lifecycle_contract_and_docs_publish_the_bounded_ko(self):
        lifecycle = json.loads(
            (ROOT / "design" / "job-lifecycle-contract-v1.json").read_text(
                encoding="utf-8"
            )
        )
        protocol_contract = lifecycle["cfs_minimal_owner_protocol"]
        self.assertEqual("KO_BOUNDED", protocol_contract["gate_verdict"])
        self.assertEqual([], protocol_contract["callable_messages"])
        self.assertFalse(protocol_contract["printer_transport"])
        design = (ROOT / "docs" / "32-protocole-proprietaire-filament-minimal-cfs-v1.md").read_text(
            encoding="utf-8"
        )
        result = (PACKAGE / "RESULT.md").read_text(encoding="utf-8")
        self.assertIn("KO borné", design)
        self.assertIn("T1A", design)
        self.assertIn("25/25", result)
        self.assertIn("liste de messages appelables : `[]`", result)


if __name__ == "__main__":
    unittest.main()
