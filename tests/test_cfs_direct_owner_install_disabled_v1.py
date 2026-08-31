from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "packages"
    / "k1-control-v1"
    / "cfs-direct-owner-install-disabled-v1"
)


def load(name, filename):
    spec = spec_from_file_location(name, PACKAGE / filename)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CfsDirectOwnerInstallDisabledV1Tests(unittest.TestCase):
    def test_candidate_verifier_closes_all_offline_scenarios(self):
        result = load("cfs_direct_install_verifier", "verify_candidate.py").verify()
        self.assertEqual("OK", result["status"])
        self.assertEqual(13, result["offline_scenarios"])
        self.assertFalse(result["installed_enabled"])
        self.assertFalse(result["printer_connection"])
        self.assertFalse(result["deployment_authorized"])
        self.assertFalse(result["cfs_frame"])

    def test_installed_configuration_is_strictly_disabled(self):
        config = (PACKAGE / "k1-control-cfs-direct-owner-disabled-v1.cfg").read_text(
            encoding="utf-8"
        )
        self.assertEqual(1, config.count("enabled: false"))
        self.assertNotIn("enabled: true", config)

    def test_contract_keeps_printer_and_physical_authority_closed(self):
        contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        self.assertFalse(contract["authority"]["printer_connection"])
        self.assertFalse(contract["authority"]["remote_write"])
        self.assertFalse(contract["authority"]["service_restart"])
        self.assertFalse(contract["authority"]["filament_frame"])
        self.assertFalse(contract["authority"]["physical_action"])
        self.assertFalse(contract["authority"]["deployment_authorized"])

    def test_manifest_has_six_absent_before_files_and_exact_rollback(self):
        manifest = json.loads(
            (PACKAGE / "deployment-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(6, len(manifest["files"]))
        self.assertEqual({"absent"}, {item["before"] for item in manifest["files"]})
        self.assertEqual(
            manifest["baseline"]["printer_cfg_sha256"],
            manifest["rollback"]["expected_printer_cfg_sha256"],
        )
        self.assertFalse(manifest["planned_effects"]["cfs_frame"])
        self.assertFalse(
            manifest["planned_effects"]["stock_command_replacement_while_disabled"]
        )

    def test_future_activation_requires_stock_exclusion_before_transport(self):
        contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        boundary = contract["future_enabled_boundary"]
        self.assertTrue(boundary["requires_new_gate"])
        self.assertEqual(19, boundary["stock_effect_entry_count"])
        self.assertEqual(0, boundary["stock_auto_refill_must_already_equal"])
        self.assertEqual("", boundary["stock_t_command_must_equal"])
        self.assertEqual([1, 2], boundary["connected_boxes_required"])
        self.assertFalse(boundary["automatic_retry"])


if __name__ == "__main__":
    unittest.main()
