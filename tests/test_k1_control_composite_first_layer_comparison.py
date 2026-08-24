from __future__ import annotations

import hashlib
import importlib.util
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "packages" / "k1-control-v1" / "composite-first-layer-comparison-v1" / "prepare_gcodes.py"


def load_module():
    spec = importlib.util.spec_from_file_location("comparison_prepare", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def source_payload(newline="\n"):
    lines = [
        "; total layer number: 1",
        "; max_z_height: 0.20",
        "G28",
        "T0",
        "START_PRINT EXTRUDER_TEMP=190 BED_TEMP=55",
        "SET_GCODE_OFFSET Z=0.27 MOVE=1 MOVE_SPEED=5 ; POSTPROC global start Z offset after START_PRINT",
        "G1 X10 Y10 Z0.2",
    ]
    return (newline.join(lines) + newline).encode()


class CompositeFirstLayerComparisonTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_v1_is_blocked_before_generating_outputs(self):
        source = source_payload("\r\n")
        digest = hashlib.sha256(source).hexdigest()
        with self.assertRaisesRegex(ValueError, "close KO"):
            self.module.prepare_payloads(source, digest)

    def test_historical_transformation_differed_only_by_profile_load(self):
        source = source_payload("\r\n")
        text, newline = self.module._validate_source(source, hashlib.sha256(source).hexdigest())
        outputs = self.module._prepare_historical_payloads(text, newline)
        robust = outputs["robust_6x6"].splitlines()
        composite = outputs["composite_11x11"].splitlines()
        differences = [i for i, pair in enumerate(zip(robust, composite)) if pair[0] != pair[1]]
        self.assertEqual(differences, [6])
        self.assertIn(b'n06x06"', robust[6])
        self.assertIn(b'n11x11"', composite[6])
        self.assertIn(b"SET_GCODE_OFFSET Z=0.27", outputs["robust_6x6"])

    def test_rejects_changed_source_hash(self):
        with self.assertRaisesRegex(ValueError, "empreinte revue"):
            self.module.prepare_payloads(source_payload(), "0" * 64)

    def test_rejects_preexisting_bed_mesh_command(self):
        source = source_payload() + b'BED_MESH_PROFILE LOAD="default"\n'
        digest = hashlib.sha256(source).hexdigest()
        with self.assertRaisesRegex(ValueError, "déjà une commande Bed Mesh"):
            self.module.prepare_payloads(source, digest)

    def test_refuses_to_write_a_new_pair(self):
        source = source_payload()
        digest = hashlib.sha256(source).hexdigest()
        original = self.module.SOURCE_SHA256
        self.module.SOURCE_SHA256 = digest
        try:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source_path = root / "source.gcode"
                source_path.write_bytes(source)
                with self.assertRaisesRegex(ValueError, "close KO"):
                    self.module.write_comparison(source_path, root / "output")
                self.assertFalse((root / "output").exists())
        finally:
            self.module.SOURCE_SHA256 = original


if __name__ == "__main__":
    unittest.main()
