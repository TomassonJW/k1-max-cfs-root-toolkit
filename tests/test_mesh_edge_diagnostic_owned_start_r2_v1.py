import ast
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "mesh-edge-diagnostic-owned-start-r2-v1"


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = load_module("mesh_edge_diagnostic_owned_start_r2_v1", PACKAGE / "build_owned_patterns.py")


class MeshEdgeDiagnosticOwnedStartR2V1Tests(unittest.TestCase):
    def test_contract_is_offline_and_pins_installed_r2(self):
        contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        self.assertEqual(builder.MISSION, contract["mission"])
        self.assertEqual(builder.INSTALLED_START_OWNER_SHA256, contract["installed_start_owner"]["sha256"])
        self.assertFalse(any(contract["effects_of_this_offline_package"].values()))
        self.assertFalse(contract["production_authorized"])

    def test_source_pattern_uses_owned_start_visible_purge_and_safe_end(self):
        payload, record = builder.build_pattern("source")
        text = payload.decode("utf-8")
        lines = list(builder.executable_lines(payload))
        self.assertEqual(1, lines.count(builder.START_CALL))
        self.assertEqual(1, lines.count(builder.ASSERT_LINE))
        self.assertNotIn("START_PRINT", text)
        self.assertNotIn("END_PRINT", text)
        self.assertNotIn("k1_p001_t055_r001_n06x06", text)
        self.assertNotIn(builder.DERIVED_PROFILE, text)
        self.assertEqual(record["owned_sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(builder.OWNED_PATTERN_SHA256["source"], record["owned_sha256"])

    def test_corrected_pattern_loads_and_verifies_only_the_derived_profile(self):
        payload, _ = builder.build_pattern("corrected")
        lines = list(builder.executable_lines(payload))
        self.assertEqual(1, lines.count("BED_MESH_PROFILE LOAD=" + builder.DERIVED_PROFILE))
        self.assertEqual(1, lines.count("KCTRL_PRODUCTION_VERIFY PROFILE=" + builder.DERIVED_PROFILE))
        self.assertEqual(1, lines.count("BED_MESH_PROFILE LOAD=" + builder.SOURCE_PROFILE))

    def test_variants_keep_identical_geometry_and_material_budget(self):
        _, source = builder.build_pattern("source")
        _, corrected = builder.build_pattern("corrected")
        self.assertEqual(source["geometry_sha256"], corrected["geometry_sha256"])
        self.assertEqual(source["estimated_filament_mm"], corrected["estimated_filament_mm"])

    def test_cli_builder_writes_only_new_local_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "owned"
            manifest = builder.build_all(output)
            self.assertTrue((output / "manifest.json").is_file())
            self.assertEqual({"source", "corrected"}, set(manifest["files"]))
            with self.assertRaisesRegex(builder.OwnedPatternError, "output_directory_already_exists"):
                builder.build_all(output)

    def test_builder_parses_as_python_3_8(self):
        source = (PACKAGE / "build_owned_patterns.py").read_text(encoding="utf-8")
        ast.parse(source, filename="build_owned_patterns.py", feature_version=(3, 8))


if __name__ == "__main__":
    unittest.main()
