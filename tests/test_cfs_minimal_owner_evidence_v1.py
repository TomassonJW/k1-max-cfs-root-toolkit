from importlib.util import module_from_spec, spec_from_file_location
import ast
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-minimal-owner-evidence-v1"

spec = spec_from_file_location(
    "cfs_minimal_owner_evidence_v1", PACKAGE / "verify_private_evidence.py"
)
evidence_verifier = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = evidence_verifier
spec.loader.exec_module(evidence_verifier)


class CfsMinimalOwnerEvidenceV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(
            (PACKAGE / "contract.json").read_text(encoding="utf-8")
        )
        cls.evidence = json.loads(
            (PACKAGE / "evidence-map.json").read_text(encoding="utf-8")
        )

    def test_gate_remains_bounded_ko_without_callable_surface(self):
        self.assertEqual(
            "closed_ko_bounded_retract_evidence_added", self.contract["status"]
        )
        self.assertEqual("KO_BOUNDED", self.contract["gate_verdict"])
        self.assertEqual([], self.contract["callable_messages"])
        self.assertEqual([], self.contract["callable_operations"])
        self.assertEqual("absent", self.contract["transport"])
        self.assertFalse(self.contract["deployment_candidate"])
        self.assertFalse(self.contract["printer_connection_authorized"])
        self.assertFalse(self.contract["physical_test_authorized"])

    def test_exact_retract_requests_and_response_are_versioned(self):
        observation = self.contract["newly_qualified_observation"]
        self.assertEqual(
            [[1, 5, 255, 17, 1, 0], [1, 5, 255, 17, 1, 1]],
            observation["application_requests"],
        )
        self.assertEqual([247, 1, 3, 0, 17, 202], observation["matched_response"])
        self.assertEqual(150, observation["host_timeout_seconds"])
        self.assertEqual("present_to_clear", observation["local_sensor_transition"])
        self.assertFalse(observation["callable"])

    def test_historical_snapshots_are_not_double_counted(self):
        independence = self.evidence["source_independence"]
        self.assertTrue(independence["historical_log_prefix_is_exact_prefix_of_superset"])
        self.assertEqual(1, independence["independent_retract_runs"])
        self.assertFalse(
            self.contract["evidence_policy"][
                "historical_duplicate_snapshots_count_as_independent_runs"
            ]
        )

    def test_crc_candidate_matches_captured_response_but_request_wire_is_missing(self):
        response = self.contract["newly_qualified_observation"]["matched_response"]
        self.assertEqual(response[-1], evidence_verifier.crc8(response[2:-1]))
        self.assertTrue(self.evidence["integrity"]["captured_response_matches_candidate_rule"])
        self.assertFalse(
            self.evidence["integrity"]["request_side_full_wire_bytes_present_in_local_log"]
        )

    def test_public_references_are_supporting_only(self):
        references = {item["name"]: item for item in self.evidence["public_references"]}
        retrude = references["K1_retrude_before_cut_reverse_engineering"]
        self.assertFalse(retrude["exact_command_table_match"])
        self.assertGreaterEqual(len(retrude["mismatch_examples"]), 4)
        self.assertIn("supporting_only", references["CFSTool_protocol"]["classification"])
        self.assertIn("not_exact", references["CrealityOfficial_K1_Series_Klipper_PR_13"]["classification"])

    def test_owner_exclusion_and_other_routes_remain_missing(self):
        missing = set(self.contract["remaining_required_proofs"])
        self.assertIn("stock_owner_exclusion_acknowledgement_and_restore", missing)
        self.assertIn("fresh_routes_for_slots_B_C_D_on_first_CFS", missing)
        self.assertIn("fresh_effect_routes_for_second_CFS", missing)
        self.assertIn("isolated_cut_contract", missing)
        self.assertIn("isolated_purge_contract", missing)

    def test_verifier_has_no_transport_or_binary_loader(self):
        source = (PACKAGE / "verify_private_evidence.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(PACKAGE / "verify_private_evidence.py"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        forbidden = {
            "ctypes",
            "paramiko",
            "requests",
            "serial",
            "socket",
            "subprocess",
        }
        self.assertTrue(forbidden.isdisjoint(imported), imported)
        self.assertFalse(any(path.suffix.lower() in {".ps1", ".sh"} for path in PACKAGE.rglob("*")))

    def test_passive_capture_is_a_separate_unarmed_gate(self):
        next_gate = self.contract["next_gate"]
        self.assertEqual(
            "G4-K1-CONTROL-CFS-MINIMAL-OWNER-PASSIVE-CAPTURE-V1",
            next_gate["candidate"],
        )
        self.assertTrue(next_gate["printer_connection_requires_fresh_explicit_authority"])
        self.assertTrue(next_gate["physical_action_requires_separate_reviewed_gate"])
        self.assertFalse(next_gate["automatic_start"])
        protocol = (PACKAGE / "PASSIVE-CAPTURE-PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("aucune connexion ni action physique", protocol)
        self.assertIn("Aucun outil ne doit écrire sur le bus série", protocol)

    def test_docs_and_lifecycle_publish_the_same_verdict(self):
        lifecycle = json.loads(
            (ROOT / "design" / "job-lifecycle-contract-v1.json").read_text(
                encoding="utf-8"
            )
        )
        gate = lifecycle["cfs_minimal_owner_evidence"]
        self.assertEqual("KO_BOUNDED", gate["gate_verdict"])
        self.assertEqual([], gate["callable_messages"])
        design = (ROOT / "docs" / "33-preuves-proprietaire-filament-minimal-cfs-v1.md").read_text(
            encoding="utf-8"
        )
        result = (PACKAGE / "RESULT.md").read_text(encoding="utf-8")
        self.assertIn("preuve de retrait ajoutée", design)
        self.assertIn("liste de messages appelables : `[]`", result)


if __name__ == "__main__":
    unittest.main()
