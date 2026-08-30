#!/usr/bin/env python3
"""Offline tombstone checks for the superseded R3 start sequence."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CFG = ROOT / "k1-control-start-sequence-owner-camera-purge-r3.cfg"
CONTRACT = ROOT / "contract.json"


def macro_body(text: str, name: str) -> str:
    marker = f"[gcode_macro {name}]"
    if text.count(marker) != 1:
        raise ValueError(f"macro_count:{name}")
    return text.split(marker, 1)[1].split("\n[", 1)[0]


def ordered(body: str, fragments: list[str], code: str) -> None:
    cursor = -1
    for fragment in fragments:
        position = body.find(fragment, cursor + 1)
        if position < 0:
            raise ValueError(f"{code}:{fragment}")
        cursor = position


def verify() -> dict[str, object]:
    text = CFG.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    begin = macro_body(text, "KCTRL_JOB_BEGIN_KEEP_CORRECT_V1")
    bin_purge = macro_body(text, "KCTRL_START_BIN_PURGE_AND_RELEASE_R3")
    camera_clean = macro_body(text, "KCTRL_CONFIRM_CAMERA_CLEAN_FOR_REFERENCE_R3")
    prime = macro_body(text, "KCTRL_START_VISIBLE_PURGE_V1")
    camera_prime = macro_body(text, "KCTRL_CONFIRM_CAMERA_PRIME_AND_RESUME_R3")

    if contract["status"] != "SUPERSEDED_NEVER_DEPLOY_OR_RUN_PROBING_AFTER_INSERTION":
        raise ValueError("r3_must_remain_superseded")
    if contract.get("superseded_by") != "ADR-034":
        raise ValueError("r3_superseding_adr_missing")

    ordered(
        begin,
        [
            "G28 X Y",
            "M109 S{probe_nozzle}",
            "G28 Z",
            "M109 S{first_nozzle}",
            "KCTRL_START_BIN_PURGE_AND_RELEASE_R3",
        ],
        "rough_then_bin_order",
    )
    if "ACCURATE_G28" in begin:
        raise ValueError("historical_r3_shape_changed")

    ordered(
        bin_purge,
        [
            "G1 Z32 F600",
            "G1 X185.5 Y305 F1200",
            "G1 Z30 F600",
            "G1 E20 F360",
            "M104 S{probe_nozzle}",
            "M109 S{probe_nozzle}",
            "G1 X203 Y273 F1200",
            "G1 Y305 F600",
            "G1 X206 F180",
            "G1 X203 F180",
            "G1 Y304 F180",
            "G1 X206 F180",
            "G1 X203 F180",
            "camera_clean_check",
            "PAUSE_BASE",
        ],
        "bin_release_order",
    )
    ordered(camera_clean, ["camera_clean_check", "ACCURATE_G28", "KCTRL_START_AFTER_REFERENCE_V1"], "camera_before_precise_z")

    # This order is deliberately preserved as evidence of why R3 is closed:
    # T1A is required, extrusion happens, and only then ACCURATE_G28 runs.
    if 'box.T1.filament|string != "A"' not in begin:
        raise ValueError("historical_engaged_route_guard_missing")
    if "G1 E20 F360" not in bin_purge or "ACCURATE_G28" not in camera_clean:
        raise ValueError("historical_contamination_before_probe_not_proven")

    ordered(
        prime,
        [
            "G1 X-1.7 Y20 F6000",
            "G1 Y150 E10 F3000",
            "G1 X-1.3 Y150 F3000",
            "G1 Y20 E10 F3000",
            "camera_prime_check",
        ],
        "outside_bed_prime_order",
    )
    if any(fragment in prime for fragment in ("G1 X0.1", "G1 X0.4", "RESUME_BASE")):
        raise ValueError("printable_area_or_early_resume_retained")
    ordered(camera_prime, ["camera_prime_check", "model_ready", "RESUME_BASE"], "camera_before_model_resume")

    watchdog = text.split("[delayed_gcode KCTRL_START_WATCHDOG_V1]", 1)[1].split("\n[", 1)[0]
    for phase in ("camera_clean_check", "camera_prime_check"):
        if phase not in watchdog:
            raise ValueError(f"watchdog_pause_phase_missing:{phase}")

    forbidden_calls = ["BOX_MATERIAL_FLUSH", "BOX_NOZZLE_CLEAN", "CX_NOZZLE_CLEAR"]
    active = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    for command in forbidden_calls:
        if command in active:
            raise ValueError(f"forbidden_stock_call:{command}")

    if contract["deployment_candidate"] or contract["physical_run_authorized"]:
        raise ValueError("offline_candidate_must_remain_closed")
    if contract["machine_facts"]["mechanical_x_min_mm"] > contract["machine_facts"]["outside_bed_prime_first_x_mm"]:
        raise ValueError("outside_bed_prime_beyond_mechanical_min")

    return {
        "status": "START_SEQUENCE_OWNER_CAMERA_PURGE_R3_SUPERSEDED_OK",
        "historical_cold_shape_preserved": True,
        "engaged_filament_before_extrusion": True,
        "extrusion_before_accurate_z_reference": True,
        "camera_before_model": True,
        "deployment_candidate": False,
        "physical_run_authorized": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2, sort_keys=True))
