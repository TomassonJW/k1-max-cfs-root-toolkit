from importlib.util import module_from_spec, spec_from_file_location
import ast
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "packages"
    / "k1-control-v1"
    / "cfs-minimal-owner-passive-capture-v1"
)

spec = spec_from_file_location(
    "cfs_minimal_owner_passive_capture_v1",
    PACKAGE / "verify_private_capture.py",
)
capture_verifier = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = capture_verifier
spec.loader.exec_module(capture_verifier)


class CfsMinimalOwnerPassiveCaptureV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(
            (PACKAGE / "contract.json").read_text(encoding="utf-8")
        )
        cls.evidence = json.loads(
            (PACKAGE / "evidence-map.json").read_text(encoding="utf-8")
        )

    def test_capture_is_ok_but_protocol_promotion_stays_bounded_ko(self):
        self.assertEqual("OK", self.contract["capture_verdict"])
        self.assertEqual("KO_BOUNDED", self.contract["protocol_gate_verdict"])
        self.assertEqual([], self.contract["callable_messages"])
        self.assertFalse(self.contract["deployment_candidate"])
        self.assertFalse(self.contract["transport_candidate"])

    def test_only_the_authorized_stock_macro_was_used(self):
        self.assertEqual(
            "one_explicitly_authorized_stock_BOX_QUIT_MATERIAL",
            self.contract["printer_action"],
        )
        self.assertFalse(self.contract["raw_serial_frames_sent_by_codex"])
        self.assertEqual("BOX_QUIT_MATERIAL", self.evidence["official_action"]["macro"])
        self.assertEqual(1, len({self.evidence["official_action"]["macro_received_line"]}))

    def test_fresh_T1A_route_was_cleared(self):
        self.assertEqual("A", self.evidence["route"]["before"]["T1_filament"])
        self.assertEqual("None", self.evidence["route"]["after"]["T1_filament"])
        self.assertEqual("T1A", self.evidence["route"]["qualified"])

    def test_two_retract_phases_have_success_responses(self):
        self.assertEqual(
            [1, 5, 255, 17, 1, 0],
            self.evidence["retract"]["buffer_request"]["frame"],
        )
        self.assertEqual(
            [1, 5, 255, 17, 1, 1],
            self.evidence["retract"]["material_request"]["frame"],
        )
        self.assertEqual(
            [247, 1, 3, 0, 17, 202],
            self.evidence["retract"]["buffer_response"]["frame"],
        )
        self.assertEqual(
            self.evidence["retract"]["buffer_response"]["frame"],
            self.evidence["retract"]["material_response"]["frame"],
        )

    def test_stock_macro_left_heat_on_and_cleanup_is_mandatory(self):
        thermal = self.contract["thermal_observation"]
        self.assertEqual(220, thermal["stock_cycle_target_celsius"])
        self.assertFalse(thermal["stock_cycle_cleared_target_at_finish"])
        self.assertEqual("TURN_OFF_HEATERS", thermal["required_cleanup"])
        self.assertEqual(0, thermal["final_extruder_target_celsius"])
        self.assertEqual(0, thermal["final_bed_target_celsius"])

    def test_http_ok_is_not_treated_as_effect_proof(self):
        transport = self.contract["transport_observation"]
        self.assertEqual(
            "rejected_as_unknown_command",
            transport["percent_encoded_space_attempt"],
        )
        self.assertFalse(transport["http_result_alone_is_success_proof"])
        self.assertEqual(
            "confirmed_effective", transport["single_token_TURN_OFF_HEATERS"]
        )

    def test_toolhead_segment_and_cutter_limit_are_explicit(self):
        observation = self.contract["qualified_observation"]
        self.assertTrue(observation["toolhead_filament_sensor_after"])
        self.assertTrue(observation["cutter_command_in_stock_sequence"])
        self.assertFalse(observation["physical_cut_sensor_or_human_confirmation"])

    def test_private_identity_fields_are_not_versioned(self):
        privacy = self.evidence["privacy"]
        self.assertFalse(privacy["raw_capture_versioned"])
        self.assertFalse(privacy["CFS_serial_numbers_versioned"])
        self.assertFalse(privacy["CFS_UUIDs_versioned"])
        source = (PACKAGE / "evidence-map.json").read_text(encoding="utf-8")
        self.assertNotIn('"sn":', source)
        self.assertNotIn('"uuid":', source)

    def test_verifier_has_no_transport_or_process_execution(self):
        source = (PACKAGE / "verify_private_capture.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(PACKAGE / "verify_private_capture.py"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(
            {"ctypes", "paramiko", "requests", "serial", "socket", "subprocess"}.isdisjoint(imported)
        )

    def test_next_gate_is_offline_stock_guard_in_plain_language(self):
        next_gate = self.contract["next_gate"]
        self.assertEqual(
            "G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-V1",
            next_gate["candidate"],
        )
        self.assertEqual("offline_only", next_gate["default_authority"])
        self.assertTrue(next_gate["printer_connection_requires_fresh_exact_GO"])
        guide = (PACKAGE / "NEXT-STOCK-UNLOAD-GUARD.md").read_text(encoding="utf-8")
        self.assertIn("En langage courant", guide)
        self.assertIn("couper les chauffes même si le retrait échoue", guide)

    def test_lifecycle_and_documentation_publish_same_result(self):
        lifecycle = json.loads(
            (ROOT / "design" / "job-lifecycle-contract-v1.json").read_text(
                encoding="utf-8"
            )
        )
        gate = lifecycle["cfs_minimal_owner_passive_capture"]
        self.assertEqual("OK", gate["capture_verdict"])
        self.assertEqual("KO_BOUNDED", gate["protocol_gate_verdict"])
        document = (ROOT / "docs" / "34-capture-retrait-officiel-cfs-v1.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("La K1 sait bien couper puis retirer", document)
        self.assertIn("arrêt global des chauffes", document)


if __name__ == "__main__":
    unittest.main()
