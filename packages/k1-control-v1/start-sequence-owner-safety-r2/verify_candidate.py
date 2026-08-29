"""Verify the purge geometry correction and the safe end template."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


PACKAGE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("start_owner_safety_r2_builder", PACKAGE / "build_candidate.py")
assert _SPEC and _SPEC.loader
builder = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = builder
_SPEC.loader.exec_module(builder)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify() -> dict:
    contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
    purge_contract = contract["purge_correction"]
    stock_reference = purge_contract["stock_reference"]
    stock_text = (builder.ROOT / stock_reference["path"]).read_text(encoding="utf-8")
    stock_macro = stock_text.split("def cmd_CX_PRINT_DRAW_ONE_LINE(self, gcmd):", 1)[1].split(
        "def cmd_CX_ROUGH_G28", 1
    )[0]
    stock_lines = (
        "G1 X0.1 Y20 Z0.3 F6000.0",
        "G1 X0.1 Y180.0 Z0.3 F3000.0 E10.0",
        "G1 X0.4 Y180.0 Z0.3 F3000.0",
        "G1 X0.4 Y20.0 Z0.3 F3000.0 E10.0",
        "G1 Y10.0 F3000.0",
    )
    stock_positions = [stock_macro.find(line) for line in stock_lines]
    if any(position < 0 for position in stock_positions) or stock_positions != sorted(stock_positions):
        raise ValueError("stock_purge_reference_drift")
    if stock_reference["mechanical_x_min_mm"] > purge_contract["outbound_start_mm"][0]:
        raise ValueError("stock_purge_x_outside_machine_range")
    candidate = builder.derive()
    persisted = builder.OUTPUT.read_bytes()
    expected = contract["candidate"]
    if candidate != persisted:
        raise ValueError("persisted_candidate_drift")
    if digest(candidate) != expected["sha256"] or len(candidate) != expected["bytes"]:
        raise ValueError("candidate_identity_drift")
    text = candidate.decode("utf-8")
    purge = text.split("[gcode_macro KCTRL_START_VISIBLE_PURGE_V1]", 1)[1].split("\n[", 1)[0]
    required_once = (
        "G1 X0.1 Y20 F6000",
        "G1 Y180 E10 F3000",
        "G1 X0.4 Y180 F3000",
        "G1 Y20 E10 F3000",
        "G1 Y10 F3000",
        "G1 E-1.2 F1800",
    )
    if not all(purge.count(line) == 1 for line in required_once) or purge.count("G1 Z5 F1200") != 2:
        raise ValueError("corrected_purge_line_missing")
    if any(line in purge for line in ("G1 X15 Y20 F9000", "G1 Y180 E18 F1200", "G1 E-0.8 F1800", "G1 Z2 F1200")):
        raise ValueError("old_purge_geometry_retained")
    end_lines = [line.strip() for line in (PACKAGE / "orca-end.gcode").read_text(encoding="utf-8").splitlines() if line.strip()]
    expected_end = [
        "KCTRL_START_ABORT_V1",
        "KCTRL_CLEAR_MANUAL_NOZZLE_CLEAN_V1",
        "M107 P1",
        "M107 P2",
        "TURN_OFF_HEATERS",
        "G90",
        "G1 Z50 F600",
        "G1 X203 Y273 F1200",
        "M400",
        "M84",
    ]
    if end_lines != expected_end:
        raise ValueError("safe_end_template_drift")
    if any(line.startswith("G28") for line in end_lines):
        raise ValueError("end_homing_forbidden")
    return {
        "status": "START_SEQUENCE_OWNER_SAFETY_R2_CANDIDATE_OK",
        "candidate_sha256": digest(candidate),
        "purge_outbound_start_mm": contract["purge_correction"]["outbound_start_mm"],
        "purge_outbound_end_mm": contract["purge_correction"]["outbound_end_mm"],
        "purge_return_start_mm": contract["purge_correction"]["return_start_mm"],
        "purge_return_end_mm": contract["purge_correction"]["return_end_mm"],
        "purge_feedrate_mm_min": contract["purge_correction"]["purge_feedrate_mm_min"],
        "stock_reference_verified": True,
        "safe_end": end_lines,
        "physical_qualification_required": contract["purge_correction"]["human_physical_qualification_required"],
        "deployment_authorized": contract["deployment_authorized"],
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
