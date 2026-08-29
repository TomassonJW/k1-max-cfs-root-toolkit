from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "z-thermal-stabilization-diagnostic-v1"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ZThermalStabilizationDiagnosticV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
        cls.verifier = load_module("z_thermal_candidate", PACKAGE / "verify_candidate.py")
        cls.analyzer = load_module("z_thermal_analyzer", PACKAGE / "analyze_capture.py")

    def test_candidate_adds_only_the_exact_soak_and_reviewed_safe_end(self):
        result = self.verifier.verify()
        self.assertEqual("Z_THERMAL_STABILIZATION_DIAGNOSTIC_CANDIDATE_OK", result["status"])
        self.assertEqual(200, result["soak_seconds"])
        self.assertEqual(["M140 S55", "M190 S55", "G4 P200000"], result["inserted_commands"])
        candidate = self.verifier.builder.OUTPUT.read_text(encoding="utf-8")
        safe_end = (ROOT / self.contract["safe_end_template"]).read_text(encoding="utf-8").strip()
        self.assertIn(safe_end, candidate)

    def test_contract_keeps_recalibration_and_retry_closed(self):
        self.assertFalse(self.contract["automatic_retry"])
        self.assertFalse(self.contract["thermal_comparison"]["manual_live_Z_adjustment_before_verdict"])
        self.assertIn("persistent_Z_write", self.contract["out_of_scope"])
        self.assertIn("mesh_measurement_or_persistence", self.contract["out_of_scope"])

    def test_live_preflight_and_upload_evidence_keep_the_run_blocked(self):
        evidence = json.loads((PACKAGE / "preflight-evidence.json").read_text(encoding="utf-8"))
        self.assertEqual("Z_THERMAL_STABILIZATION_DIAGNOSTIC_PREFLIGHT_OK", evidence["corrected_preflight"]["status"])
        self.assertTrue(evidence["corrected_preflight"]["heater_targets_zero"])
        self.assertTrue(evidence["corrected_preflight"]["axes_released"])
        self.assertEqual("T1A", evidence["corrected_preflight"]["unique_engaged_route"])
        self.assertEqual(evidence["upload"]["sha256"], evidence["upload"]["removed_sha256"])
        self.assertNotEqual(self.contract["candidate"]["sha256"], evidence["upload"]["sha256"])
        self.assertTrue(evidence["upload"]["remote_file_removed"])
        self.assertFalse(evidence["upload"]["print_started"])
        self.assertIn("plate_clear", evidence["next_effect_blocked_until"])

    def test_runner_requires_all_human_physical_guards(self):
        runner = (PACKAGE / "run_trial.ps1").read_text(encoding="utf-8")
        for guard in ("HumanPresent", "PlateClear", "ManualNozzleCleanConfirmed", "ImmediateStopAvailable"):
            self.assertIn(guard, runner)
        self.assertIn("if (-not $Execute -or $Gate -cne $Mission)", runner)
        self.assertIn("automatic_retry = $false", runner)

    def test_derived_preflight_accepts_only_safe_terminal_print_states(self):
        trial, _ = self.verifier.builder.derive_programs()
        source = trial.decode("utf-8")
        self.assertIn('print_state not in ("standby", "complete")', source)
        self.assertIn('print_state == "standby" and print_filename', source)
        self.assertIn('print_state == "complete" and not print_filename', source)
        self.assertNotIn('printer_not_standby', source)

    def test_derived_trial_pins_r2_and_proves_the_safe_terminal_position(self):
        trial, _ = self.verifier.builder.derive_programs()
        source = trial.decode("utf-8")
        self.assertIn(self.contract["installed_start_owner"]["sha256"], source)
        self.assertNotIn(self.verifier.builder.OLD_START_OWNER_SHA256, source)
        self.assertIn('"physical_position": child(status, "toolhead").get("position")', source)
        self.assertIn('G1 Z50 F600\\nG1 X203 Y273 F1200\\nM400\\nM84', source)
        self.assertIn('raise GateError("final_park_x_invalid")', source)
        self.assertIn('raise GateError("final_park_y_invalid")', source)
        self.assertIn('raise GateError("final_bed_clearance_invalid")', source)

    def test_analyzer_accepts_a_complete_soak_trace(self):
        records = [
            {"kind": "snapshot", "elapsed_s": 0.0, "print": {"state": "standby"}, "owner": {"phase": "idle"}, "bed": {"target": 0.0, "temperature": 30.0}, "nozzle": {"target": 0.0}, "cfs": {"engaged_routes": ["T1A"], "active_command": ""}},
            {"kind": "snapshot", "elapsed_s": 10.0, "print": {"state": "printing"}, "owner": {"phase": "idle"}, "bed": {"target": 55.0, "temperature": 54.8}, "nozzle": {"target": 0.0}, "cfs": {"engaged_routes": ["T1A"], "active_command": ""}},
            {"kind": "snapshot", "elapsed_s": 208.0, "print": {"state": "printing"}, "owner": {"phase": "idle"}, "bed": {"target": 55.0, "temperature": 55.0}, "nozzle": {"target": 0.0}, "cfs": {"engaged_routes": ["T1A"], "active_command": ""}},
            {"kind": "snapshot", "elapsed_s": 208.5, "print": {"state": "printing"}, "owner": {"phase": "manual_clean_confirmed"}, "bed": {"target": 55.0}, "nozzle": {"target": 0.0}, "cfs": {"engaged_routes": ["T1A"], "active_command": ""}},
            {"kind": "snapshot", "elapsed_s": 209.0, "print": {"state": "printing"}, "owner": {"phase": "reference_heating"}, "bed": {"target": 55.0}, "nozzle": {"target": 140.0}, "cfs": {"engaged_routes": ["T1A"], "active_command": ""}},
            {"kind": "snapshot", "elapsed_s": 220.0, "print": {"state": "printing"}, "owner": {"phase": "visible_purge"}, "bed": {"target": 55.0}, "nozzle": {"target": 190.0}, "cfs": {"engaged_routes": ["T1A"], "active_command": ""}},
            {"kind": "snapshot", "elapsed_s": 230.0, "print": {"state": "printing"}, "owner": {"phase": "model_ready"}, "bed": {"target": 55.0}, "nozzle": {"target": 190.0}, "cfs": {"engaged_routes": ["T1A"], "active_command": ""}},
            {"kind": "snapshot", "elapsed_s": 240.0, "print": {"state": "complete"}, "owner": {"phase": "idle"}, "bed": {"target": 0.0}, "nozzle": {"target": 0.0}, "cfs": {"engaged_routes": ["T1A"], "active_command": ""}},
            {"kind": "footer", "status": "Z_THERMAL_STABILIZATION_DIAGNOSTIC_AUTOMATION_OK"},
        ]
        result = self.analyzer.analyze_records(records)
        self.assertEqual("Z_THERMAL_STABILIZATION_DIAGNOSTIC_AUTOMATIC_OK", result["status"])
        self.assertGreaterEqual(result["soak_observed_seconds"], 195.0)


if __name__ == "__main__":
    unittest.main()
