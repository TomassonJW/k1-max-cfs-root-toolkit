from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import struct
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-box-wrapper-audit-v1"

spec = spec_from_file_location(
    "cfs_box_wrapper_audit_v1", PACKAGE / "analyze_evidence.py"
)
audit = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit)


class CfsBoxWrapperAuditV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.strings = (PACKAGE / "fixtures" / "box-wrapper.strings.redacted.txt").read_text(
            encoding="utf-8"
        )
        cls.incident = (PACKAGE / "fixtures" / "incident.redacted.txt").read_text(
            encoding="utf-8"
        )

    def test_real_redacted_evidence_blocks_all_stock_primitives(self):
        result = audit.analyze(self.contract, self.strings, self.incident)
        self.assertEqual("block_stock_sequence_no_callable_primitive", result["verdict"])
        self.assertEqual([], result["adapter"]["callable_stock_primitives"])
        self.assertFalse(result["adapter"]["deployment_candidate"])
        self.assertFalse(result["authorizes_printer_mutation"])
        self.assertFalse(result["authorizes_physical_test"])

    def test_each_primitive_has_an_explicit_fail_closed_verdict(self):
        result = audit.analyze(self.contract, self.strings, self.incident)
        verdicts = {item["command"]: item["verdict"] for item in result["primitive_verdicts"]}
        self.assertEqual(
            "blocked_observed_temperature_and_geometry_owner",
            verdicts["BOX_EXTRUDE_MATERIAL"],
        )
        self.assertEqual("unqualified_not_isolated", verdicts["BOX_EXTRUDER_EXTRUDE"])
        self.assertEqual("unqualified_not_isolated", verdicts["BOX_MATERIAL_FLUSH"])

    def test_requested_190_does_not_hide_observed_220(self):
        result = audit.analyze(self.contract, self.strings, self.incident)
        lines = result["incident_marker_lines"]
        self.assertLess(lines["material_temperature"], lines["requested_flush_temperature"])
        self.assertLess(lines["observed_nozzle_target"], lines["requested_flush_temperature"])

    def test_missing_temperature_evidence_is_inconclusive(self):
        incident = self.incident.replace("get next material temp: 220", "temperature hidden")
        result = audit.analyze(self.contract, self.strings, incident)
        self.assertEqual("inconclusive_block", result["verdict"])
        self.assertIn("material_temperature", result["missing_incident_markers"])

    def test_unordered_evidence_is_inconclusive(self):
        lines = self.incident.splitlines()
        lines[0], lines[-1] = lines[-1], lines[0]
        result = audit.analyze(self.contract, self.strings, "\n".join(lines))
        self.assertEqual("inconclusive_block", result["verdict"])
        self.assertFalse(result["incident_markers_ordered"])

    def test_missing_binary_string_is_inconclusive(self):
        strings = self.strings.replace("BED_MESH_CLEAR", "BED_MESH_HIDDEN")
        result = audit.analyze(self.contract, strings, self.incident)
        self.assertEqual("inconclusive_block", result["verdict"])
        self.assertEqual(["BED_MESH_CLEAR"], result["missing_binary_strings"]["geometry_ownership"])

    def test_elf_header_is_read_without_loading_module(self):
        header = bytearray(52)
        header[:6] = b"\x7fELF\x01\x01"
        struct.pack_into("<HH", header, 16, 3, 8)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "module.so"
            path.write_bytes(header)
            info = audit.inspect_elf(path)
        self.assertEqual(1, info["elf_class"])
        self.assertEqual("little", info["endianness"])
        self.assertEqual(3, info["type"])
        self.assertEqual(8, info["machine"])
        self.assertFalse(info["loaded_or_executed"])

    def test_wrong_binary_identity_is_inconclusive(self):
        header = bytearray(52)
        header[:6] = b"\x7fELF\x01\x01"
        struct.pack_into("<HH", header, 16, 3, 8)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "module.so"
            path.write_bytes(header)
            result = audit.analyze(self.contract, self.strings, self.incident, path)
        self.assertEqual("inconclusive_block", result["verdict"])
        self.assertIn("sha256", result["binary_mismatches"])

    def test_result_document_keeps_deployment_closed(self):
        result = (PACKAGE / "RESULT.md").read_text(encoding="utf-8")
        self.assertIn("aucune primitive stock qualifiée", result)
        self.assertIn("adapter.deployment_candidate=false", result)
        self.assertIn("n'autorise ni pose ni essai physique", result)

    def test_narrow_adapter_contract_is_fail_closed(self):
        adapter = json.loads(
            (PACKAGE / "adapter-contract.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            "offline_fail_closed_no_primitive_selected", adapter["status"]
        )
        self.assertEqual([], adapter["callable_stock_primitives"])
        self.assertEqual(6, len(adapter["protected_state"]))
        self.assertFalse(adapter["deployment_candidate"])
        self.assertFalse(adapter["physical_test_authorized"])
        self.assertEqual(
            "stop_without_blind_z_restore_and_block_resume",
            adapter["failure_policy"]["geometry_change"],
        )


if __name__ == "__main__":
    unittest.main()
