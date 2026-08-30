#!/usr/bin/env python3
"""Static safety checks for the pre-insertion geometry R4 candidate."""

from __future__ import annotations

import json
import re
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
CFG = PACKAGE / "k1-control-start-sequence-owner-preinsert-geometry-r4.cfg"
CONTRACT = PACKAGE / "contract.json"


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


def active_lines(text: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def verify() -> dict[str, object]:
    text = CFG.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    prepare = macro_body(text, "KCTRL_PREPARE_GEOMETRY_BEFORE_INSERTION_R4")
    after_geometry = macro_body(text, "KCTRL_AFTER_GEOMETRY_BEFORE_INSERTION_R4")
    mark_ready = macro_body(text, "KCTRL_MARK_GEOMETRY_READY_FOR_INSERTION_R4")
    reuse = macro_body(text, "KCTRL_REUSE_VALID_GEOMETRY_WITH_T1A_R4")
    mark_reuse = macro_body(text, "KCTRL_MARK_REUSED_GEOMETRY_READY_R4")
    job = macro_body(text, "KCTRL_JOB_BEGIN_KEEP_CORRECT_V1")
    after_rearm = macro_body(text, "KCTRL_START_AFTER_REARM_R4")
    bin_release = macro_body(text, "KCTRL_START_BIN_PURGE_AND_RELEASE_R4")
    camera_release = macro_body(text, "KCTRL_CONFIRM_CAMERA_RELEASE_AND_PRIME_R4")
    prime = macro_body(text, "KCTRL_START_VISIBLE_PRIME_R4")
    camera_prime = macro_body(text, "KCTRL_CONFIRM_CAMERA_PRIME_AND_RESUME_R4")

    ordered(
        prepare,
        [
            'box.T1.filament|string not in ["None", "none", ""]',
            "M140 S{bed}",
            "G28 X Y",
            "M190 S{bed}",
            "M109 S{probe_nozzle}",
            "ACCURATE_G28",
            "KCTRL_AFTER_GEOMETRY_BEFORE_INSERTION_R4",
        ],
        "preinsert_contact_order",
    )
    if re.search(r"\bG1\s+E", prepare):
        raise ValueError("extrusion_before_insertion")

    ordered(
        after_geometry,
        [
            'box.T1.filament|string not in ["None", "none", ""]',
            "KCTRL_PRODUCTION_ARM",
            "KCTRL_MARK_GEOMETRY_READY_FOR_INSERTION_R4",
        ],
        "arm_before_insertion_token",
    )
    ordered(
        mark_ready,
        [
            "KCTRL_START_FAIL_AFTER_HEAT_V1 CODE=route_engaged_before_geometry_ready",
            "TURN_OFF_HEATERS",
            "VARIABLE=geometry_ready_token VALUE=1",
            "geometry_ready_for_insertion",
        ],
        "token_after_geometry",
    )

    ordered(
        reuse,
        [
            '"xyz" not in printer.toolhead.homed_axes',
            'box.T1.filament|string != "A"',
            "KCTRL_PRODUCTION_ARM",
            "KCTRL_MARK_REUSED_GEOMETRY_READY_R4",
        ],
        "reuse_without_unload_or_probe",
    )
    for forbidden in ("G28", "ACCURATE_G28", "BED_MESH_CALIBRATE", "G29"):
        if re.search(rf"(?m)^\s*{re.escape(forbidden)}(?:\s|$)", reuse):
            raise ValueError(f"reuse_probe_or_home:{forbidden}")
    ordered(
        mark_reuse,
        [
            "geometry_reuse_arming",
            "reused_geometry_verification_failed",
            "VARIABLE=geometry_ready_token VALUE=1",
            "geometry_ready_with_engaged_t1a",
        ],
        "verified_reuse_token",
    )

    ordered(
        job,
        [
            "geometry_ready_token|int != 1",
            'box.T1.filament|string != "A"',
            "VARIABLE=geometry_ready_token VALUE=0",
            "KCTRL_PRODUCTION_ARM",
            "KCTRL_START_AFTER_REARM_R4",
        ],
        "single_use_token_and_rearm",
    )
    for forbidden in ("G28", "ACCURATE_G28", "BED_MESH_CALIBRATE", "G29"):
        if re.search(rf"(?m)^\s*{re.escape(forbidden)}(?:\s|$)", job):
            raise ValueError(f"post_insertion_probe_or_home:{forbidden}")

    ordered(
        after_rearm,
        [
            "KCTRL_PRODUCTION_ASSERT_ARMED",
            "M140 S{owner.job_bed}",
            "M109 S{first_nozzle}",
            "KCTRL_START_BIN_PURGE_AND_RELEASE_R4",
        ],
        "rearm_before_heat_and_purge",
    )
    ordered(
        bin_release,
        [
            "KCTRL_PRODUCTION_ASSERT_ARMED",
            "G1 X185.5 Y305 F1200",
            "G1 E20 F360",
            "M104 S{release_nozzle}",
            "G1 X203 Y273 F1200",
            "G1 Y305 F600",
            "G1 X206 F180",
            "G1 X203 F180",
            "G1 Y304 F180",
            "G1 X206 F180",
            "G1 X203 F180",
            "camera_release_check",
            "PAUSE_BASE",
        ],
        "post_probe_bin_release_order",
    )
    if "ACCURATE_G28" in bin_release or "G28 Z" in bin_release:
        raise ValueError("probe_after_purge")

    ordered(
        camera_release,
        [
            "camera_release_check",
            "KCTRL_PRODUCTION_ASSERT_ARMED",
            "M109 S{owner.job_first_nozzle}",
            "KCTRL_START_VISIBLE_PRIME_R4",
        ],
        "camera_before_prime",
    )
    ordered(
        prime,
        [
            "KCTRL_PRODUCTION_ASSERT_ARMED",
            "G1 X-1.7 Y20 F6000",
            "G1 Y150 E10 F3000",
            "G1 X-1.3 Y150 F3000",
            "G1 Y20 E10 F3000",
            "camera_prime_check",
        ],
        "outside_bed_prime_order",
    )
    ordered(camera_prime, ["camera_prime_check", "model_ready", "RESUME_BASE"], "camera_before_model")

    post_insertion = text.split("[gcode_macro KCTRL_JOB_BEGIN_KEEP_CORRECT_V1]", 1)[1]
    for forbidden in ("ACCURATE_G28", "G28 Z", "BED_MESH_CALIBRATE", "CX_PRINT_LEVELING_CALIBRATION"):
        if forbidden in active_lines(post_insertion):
            raise ValueError(f"post_insertion_contact_command:{forbidden}")

    active = active_lines(text)
    for forbidden in ("START_PRINT", "BOX_START_PRINT", "BOX_MATERIAL_FLUSH", "BOX_NOZZLE_CLEAN", "CX_NOZZLE_CLEAR"):
        if re.search(rf"(?m)^\s*{re.escape(forbidden)}(?:\s|$)", active):
            raise ValueError(f"forbidden_stock_call:{forbidden}")
    if re.search(r"(?m)^\s+(?:PAUSE|RESUME)\s*$", active):
        raise ValueError("stock_pause_resume_call")

    watchdog = text.split("[delayed_gcode KCTRL_START_WATCHDOG_V1]", 1)[1].split("\n[", 1)[0]
    for phase in (
        "geometry_heating",
        "geometry_arming",
        "geometry_ready_for_insertion",
        "geometry_reuse_arming",
        "geometry_ready_with_engaged_t1a",
        "camera_release_check",
        "first_layer_heating",
        "visible_purge",
        "camera_prime_check",
    ):
        if phase not in watchdog:
            raise ValueError(f"watchdog_phase_missing:{phase}")
    if 'phase in ["camera_release_check", "first_layer_heating", "visible_purge", "camera_prime_check"]' not in watchdog:
        raise ValueError("watchdog_paused_subphases_not_allowed")
    if 'phase in ["geometry_heating", "geometry_arming", "geometry_ready_for_insertion", "geometry_reuse_arming", "geometry_ready_with_engaged_t1a", "selftest_active"]' not in watchdog:
        raise ValueError("watchdog_standby_subphases_not_allowed")
    for fragment in ("TURN_OFF_HEATERS", "VARIABLE=geometry_ready_token VALUE=0", "VARIABLE=low_moves_armed VALUE=0"):
        if fragment not in watchdog:
            raise ValueError(f"watchdog_cleanup_missing:{fragment}")

    if contract["hard_invariants"]["all_contact_probing_before_insertion"] is not True:
        raise ValueError("contract_contact_order_open")
    if contract["hard_invariants"]["valid_geometry_reuse_keeps_T1A_and_never_probes"] is not True:
        raise ValueError("contract_reuse_path_open")
    if contract["physical_run_authorized"] or contract["production_authorized"]:
        raise ValueError("physical_or_production_authority_open")

    return {
        "status": "START_SEQUENCE_OWNER_PREINSERT_GEOMETRY_R4_OFFLINE_OK",
        "contact_before_insertion": True,
        "post_insertion_probe_commands": 0,
        "single_use_geometry_token": True,
        "valid_geometry_reuse_without_unload_or_probe": True,
        "mesh_rearmed_after_official_insertion": True,
        "camera_before_model": True,
        "physical_run_authorized": False,
        "production_authorized": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2, sort_keys=True))
