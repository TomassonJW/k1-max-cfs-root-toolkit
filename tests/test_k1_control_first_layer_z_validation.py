from __future__ import annotations

import hashlib
import importlib.util
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "packages" / "k1-control-v1" / "first-layer-z-validation-v1" / "prepare_gcode.py"


def load_module():
    spec = importlib.util.spec_from_file_location("first_layer_z_prepare", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def source_payload(newline="\n", extra_executable=""):
    lines = [
        "; total layer number: 1",
        "; max_z_height: 0.20",
        "EXCLUDE_OBJECT_DEFINE NAME=Cube_id_0_copy_0 CENTER=150,150 POLYGON=[[20,20],[280,20],[280,280],[20,280],[20,20]]",
        "G28",
        "T0",
        "START_PRINT EXTRUDER_TEMP=190 BED_TEMP=55",
        "M104 S190",
        "G1 Z.2",
    ]
    if extra_executable:
        lines.append(extra_executable)
    lines.extend(
        [
            "; post_process = ",
            "; z_offset = 0",
            "; first_layer_bed_temperature = 55",
            "; first_layer_temperature = 190",
            "; first_layer_height = 0.200",
        ]
    )
    return (newline.join(lines) + newline).encode()


class FirstLayerZValidationTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_adds_only_guard_without_explicit_z_offset(self):
        source = source_payload("\r\n")
        payload = self.module.prepare_payload(source, hashlib.sha256(source).hexdigest())
        self.assertEqual(payload.count(b"KCTRL_PRODUCTION_ARM"), 1)
        self.assertIn(b"X_COUNT=6 Y_COUNT=6", payload)
        self.assertNotIn(b"SET_GCODE_OFFSET", payload)
        self.assertIn(b"START_PRINT EXTRUDER_TEMP=190 BED_TEMP=55\r\n; K1_CONTROL", payload)

    def test_rejects_any_executable_z_offset(self):
        source = source_payload(extra_executable="SET_GCODE_OFFSET Z=0.27")
        digest = hashlib.sha256(source).hexdigest()
        with self.assertRaisesRegex(ValueError, "commande interdite"):
            self.module.prepare_payload(source, digest)

    def test_allows_inert_offset_notes(self):
        source = source_payload() + b"; notes = old z-offset 0.27\n"
        digest = hashlib.sha256(source).hexdigest()
        payload = self.module.prepare_payload(source, digest)
        self.assertIn(b"old z-offset 0.27", payload)

    def test_rejects_changed_source_hash(self):
        with self.assertRaisesRegex(ValueError, "empreinte revue"):
            self.module.prepare_payload(source_payload(), "0" * 64)

    def test_writes_manifest_for_large_robust_sheet(self):
        source = source_payload()
        digest = hashlib.sha256(source).hexdigest()
        original = self.module.SOURCE_SHA256
        self.module.SOURCE_SHA256 = digest
        try:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source_path = root / "source.gcode"
                source_path.write_bytes(source)
                manifest = self.module.write_validation(source_path, root / "output")
                self.assertEqual(manifest["geometry_mm"], [260, 260, 0.2])
                self.assertEqual(manifest["expected_initial_z_mm"], -0.04)
                self.assertIsNone(manifest["explicit_gcode_z_offset"])
        finally:
            self.module.SOURCE_SHA256 = original


if __name__ == "__main__":
    unittest.main()
