from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-boundary-guard-v1"

spec = spec_from_file_location("cfs_boundary_guard_v1", PACKAGE / "evaluate_trace.py")
guard = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(guard)


class CfsBoundaryGuardV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))

    def fixture(self, name):
        return json.loads((PACKAGE / "fixtures" / name).read_text(encoding="utf-8"))

    def test_safe_trace_passes_offline_only(self):
        result = guard.evaluate_trace(self.contract, self.fixture("safe-phase.json"))
        self.assertEqual("pass_offline_trace_only", result["verdict"])
        self.assertFalse(result["authorizes_printer_mutation"])
        self.assertFalse(result["authorizes_print_resume"])

    def test_real_incident_blocks_stock_primitive(self):
        result = guard.evaluate_trace(
            self.contract, self.fixture("incident-20260826.json")
        )
        self.assertEqual("block_driver_primitive", result["verdict"])
        self.assertEqual(
            {
                "nozzle_target_override",
                "forbidden_geometry_command",
                "homed_axes_changed",
            },
            {item["code"] for item in result["violations"]},
        )
        self.assertEqual(
            {"accepted_z_offset_mm", "homing_origin_z_mm", "mesh_profile"},
            {item["field"] for item in result["evidence_gaps"]},
        )
        self.assertIn("set_nozzle_and_bed_targets_zero", result["safe_actions"])
        self.assertIn("do_not_restore_z_automatically", result["safe_actions"])

    def test_bed_change_is_a_hard_failure(self):
        trace = self.fixture("safe-phase.json")
        trace["events"][-1]["bed_target_c"] = 0
        result = guard.evaluate_trace(self.contract, trace)
        self.assertIn(
            "bed_target_override", {item["code"] for item in result["violations"]}
        )

    def test_cfs_bed_command_is_forbidden_even_if_target_would_match(self):
        trace = self.fixture("safe-phase.json")
        trace["events"].insert(
            1, {"kind": "gcode", "owner": "unknown", "command": "M140 S60"}
        )
        trace["events"].insert(
            2, {"kind": "gcode", "owner": "unknown", "command": "M104 S205"}
        )
        result = guard.evaluate_trace(self.contract, trace)
        codes = {item["code"] for item in result["violations"]}
        self.assertIn("cfs_bed_command", codes)
        self.assertIn("cfs_nozzle_command", codes)

    def test_z_offset_change_stops_without_blind_restore(self):
        trace = self.fixture("safe-phase.json")
        trace["events"][-1]["accepted_z_offset_mm"] = 0
        result = guard.evaluate_trace(self.contract, trace)
        self.assertIn(
            "accepted_z_offset_changed",
            {item["code"] for item in result["violations"]},
        )
        self.assertIn("do_not_restore_z_automatically", result["safe_actions"])

    def test_mesh_or_homing_change_is_a_hard_failure(self):
        trace = self.fixture("safe-phase.json")
        trace["events"][-1]["mesh_profile"] = ""
        trace["events"][-1]["homed_axes"] = "xy"
        result = guard.evaluate_trace(self.contract, trace)
        codes = {item["code"] for item in result["violations"]}
        self.assertIn("mesh_profile_changed", codes)
        self.assertIn("homed_axes_changed", codes)

    def test_missing_snapshot_is_inconclusive(self):
        trace = self.fixture("safe-phase.json")
        trace["events"] = trace["events"][:1]
        with self.assertRaisesRegex(guard.TraceError, "at least two snapshots"):
            guard.evaluate_trace(self.contract, trace)

    def test_unknown_protected_value_is_inconclusive_without_a_violation(self):
        trace = self.fixture("safe-phase.json")
        trace["events"][-1]["homing_origin_z_mm"] = None
        result = guard.evaluate_trace(self.contract, trace)
        self.assertEqual("inconclusive", result["verdict"])
        self.assertEqual("homing_origin_z_mm", result["evidence_gaps"][0]["field"])

    def test_documents_freeze_bed_and_z_as_cfs_invariants(self):
        requirements = (ROOT / "docs" / "07-dynamic-cfs-temperature-requirements.md").read_text(
            encoding="utf-8"
        )
        adr = (
            ROOT / "docs" / "adr" / "ADR-017-frontiere-cfs-buse-plateau-z.md"
        ).read_text(encoding="utf-8")
        incident = (
            ROOT / "docs" / "27-incident-cfs-temperature-geometrie-v1.md"
        ).read_text(encoding="utf-8")
        result_document = (PACKAGE / "RESULT.md").read_text(encoding="utf-8")
        lifecycle = json.loads(
            (ROOT / "design" / "job-lifecycle-contract-v1.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertIn("cible plateau explicite", requirements)
        self.assertIn("Z accepté, origine Z courante, profil mesh", requirements)
        self.assertIn("six invariants", adr)
        self.assertIn("ne pas rejouer la séquence brute", incident)
        self.assertIn("verdict=block_driver_primitive", result_document)
        self.assertIn("324 tests Python", result_document)
        self.assertEqual(
            "offline_candidate_production_closed",
            lifecycle["cfs_boundary_guard"]["status"],
        )


if __name__ == "__main__":
    unittest.main()
