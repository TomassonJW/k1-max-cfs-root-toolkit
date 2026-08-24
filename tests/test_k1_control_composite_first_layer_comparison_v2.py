from __future__ import annotations

import hashlib
import importlib.util
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "packages" / "k1-control-v1" / "composite-first-layer-comparison-v2" / "prepare_gcodes.py"


def load_module():
    spec = importlib.util.spec_from_file_location("comparison_prepare_v2", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def source_payload(newline="\n"):
    lines = [
        "; total layer number: 1",
        "; max_z_height: 0.20",
        "EXCLUDE_OBJECT_DEFINE NAME=Cube_id_0_copy_0 CENTER=150,150 POLYGON=[[20,20],[280,20],[280,280],[20,280],[20,20]]",
        "G28",
        "T0",
        "START_PRINT EXTRUDER_TEMP=190 BED_TEMP=55",
        "M104 S190",
        "G1 X10 Y10 Z0.2",
        "; post_process = ",
        "; z_offset = 0",
        "; first_layer_bed_temperature = 55",
        "; first_layer_temperature = 190",
        "; first_layer_height = 0.200",
    ]
    return (newline.join(lines) + newline).encode()


class CompositeFirstLayerComparisonV2Tests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_adds_guarded_profiles_without_explicit_z(self):
        source = source_payload("\r\n")
        outputs = self.module.prepare_payloads(source, hashlib.sha256(source).hexdigest())
        for payload in outputs.values():
            self.assertNotIn(b"SET_GCODE_OFFSET", payload)
            self.assertEqual(payload.count(b"KCTRL_PRODUCTION_ARM"), 1)
            self.assertEqual(payload.count(b"PAUSE"), 1)
            self.assertIn(b"K1_CONTROL_COMPOSITE_FIRST_LAYER_COMPARISON_V2", payload)
        self.assertIn(b"X_COUNT=6 Y_COUNT=6", outputs["robust_6x6"])
        self.assertIn(b"X_COUNT=11 Y_COUNT=11", outputs["composite_11x11"])

    def test_outputs_differ_on_exactly_one_guard_line(self):
        source = source_payload()
        outputs = self.module.prepare_payloads(source, hashlib.sha256(source).hexdigest())
        robust = outputs["robust_6x6"].splitlines()
        composite = outputs["composite_11x11"].splitlines()
        differences = [i for i, pair in enumerate(zip(robust, composite)) if pair[0] != pair[1]]
        self.assertEqual(len(robust), len(composite))
        self.assertEqual(len(differences), 1)
        self.assertIn(b"KCTRL_PRODUCTION_ARM", robust[differences[0]])
        self.assertIn(b"KCTRL_PRODUCTION_ARM", composite[differences[0]])

    def test_rejects_changed_source_hash(self):
        with self.assertRaisesRegex(ValueError, "empreinte revue"):
            self.module.prepare_payloads(source_payload(), "0" * 64)

    def test_rejects_source_already_containing_a_guard(self):
        source = source_payload() + b"KCTRL_PRODUCTION_ARM X_COUNT=6 Y_COUNT=6\n"
        digest = hashlib.sha256(source).hexdigest()
        with self.assertRaisesRegex(ValueError, "commande interdite"):
            self.module.prepare_payloads(source, digest)

    def test_rejects_explicit_z_offset(self):
        source = source_payload() + b"SET_GCODE_OFFSET Z=-0.24\n"
        digest = hashlib.sha256(source).hexdigest()
        with self.assertRaisesRegex(ValueError, "commande interdite"):
            self.module.prepare_payloads(source, digest)

    def test_writes_manifest_with_guard_contract(self):
        source = source_payload()
        digest = hashlib.sha256(source).hexdigest()
        original = self.module.SOURCE_SHA256
        self.module.SOURCE_SHA256 = digest
        try:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source_path = root / "source.gcode"
                source_path.write_bytes(source)
                manifest = self.module.write_comparison(source_path, root / "output")
                self.assertEqual(manifest["schema"], 3)
                self.assertEqual(manifest["accepted_z_source"], "KCTRL_STATE.accepted_z_offset")
                self.assertIsNone(manifest["explicit_gcode_z_offset"])
                self.assertEqual(manifest["shared_contract"]["geometry_mm"], [260, 260, 0.2])
                self.assertEqual(len(manifest["files"]), 2)
        finally:
            self.module.SOURCE_SHA256 = original


if __name__ == "__main__":
    unittest.main()
