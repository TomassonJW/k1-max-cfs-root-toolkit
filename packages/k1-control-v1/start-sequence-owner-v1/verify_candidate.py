from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parent


def _macro_body(text: str, name: str) -> str:
    return _section_body(text, "gcode_macro %s" % name)


def _section_body(text: str, section: str) -> str:
    marker = "[%s]" % section
    start = text.find(marker)
    if start < 0:
        raise ValueError("missing_section:%s" % section)
    body_start = text.find("\n", start) + 1
    end = text.find("\n[", body_start)
    if end < 0:
        end = len(text)
    return text[body_start:end]


def _ordered(body: str, tokens: list[str], label: str) -> None:
    cursor = -1
    for token in tokens:
        cursor = body.find(token, cursor + 1)
        if cursor < 0:
            raise ValueError("%s_missing_or_out_of_order:%s" % (label, token))


def _active_gcode_lines(text: str) -> list[str]:
    result = []
    in_gcode = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("["):
            in_gcode = False
        elif stripped == "gcode:":
            in_gcode = True
            continue
        if in_gcode and stripped and not stripped.startswith(("#", "{%", "{action_", "{%")):
            if not stripped.startswith(("{%", "{%", "{%")):
                result.append(stripped)
    return result


def verify() -> dict[str, object]:
    contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
    cfg = (PACKAGE / "k1-control-start-sequence-owner-v1.cfg").read_text(encoding="utf-8")
    orca_lines = [
        line.strip()
        for line in (PACKAGE / "orca-start.gcode").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    if contract["status"] not in {
        "OFFLINE_HARDENED_LIVE_PREFLIGHT_PENDING",
        "PREFLIGHT_QUALIFIED_DEPLOYMENT_CANDIDATE_NOT_AUTHORIZED",
        "INSTALLED_VALIDATED_COLD_PHYSICAL_TRIAL_BLOCKED_NO_T1A",
    }:
        raise ValueError("candidate_status_opened")
    installed = contract["status"] == "INSTALLED_VALIDATED_COLD_PHYSICAL_TRIAL_BLOCKED_NO_T1A"
    if contract["deployment_authorized"] or contract["printer_connection_authorized"]:
        raise ValueError("candidate_authority_too_broad")
    if installed:
        if contract["deployment_candidate"]:
            raise ValueError("installed_payload_still_marked_candidate")
        if contract["deployment_result"]["status"] != "INSTALLED_VALIDATED_COLD":
            raise ValueError("installed_payload_has_no_closed_result")
    elif not contract["deployment_candidate"]:
        raise ValueError("candidate_not_marked_deployable")
    if contract["live_read_only_preflight"]["status"] != "PASS_BLOCKED_NO_T1A":
        raise ValueError("live_preflight_not_closed")
    if contract["physical_trial"]["blocker"] != "BLOCKED_NO_ENGAGED_T1A":
        raise ValueError("physical_trial_not_fail_closed")
    if len(orca_lines) != 1 or not orca_lines[0].startswith("KCTRL_JOB_BEGIN_KEEP_CORRECT_V1 "):
        raise ValueError("orca_entrypoint_not_single_owned_macro")

    begin = _macro_body(cfg, "KCTRL_JOB_BEGIN_KEEP_CORRECT_V1")
    after_reference = _macro_body(cfg, "KCTRL_START_AFTER_REFERENCE_V1")
    after_arm = _macro_body(cfg, "KCTRL_START_AFTER_ARM_V1")
    purge = _macro_body(cfg, "KCTRL_START_VISIBLE_PURGE_V1")
    watchdog = _section_body(cfg, "delayed_gcode KCTRL_START_WATCHDOG_V1")
    confirm = _macro_body(cfg, "KCTRL_CONFIRM_MANUAL_NOZZLE_CLEAN_V1")

    _ordered(
        begin,
        [
            "manual_clean_token VALUE=0",
            "M140 S{bed}",
            "M104 S{probe_nozzle}",
            "G28 X Y",
            "M190 S{bed}",
            "M109 S{probe_nozzle}",
            "ACCURATE_G28",
            "KCTRL_START_AFTER_REFERENCE_V1",
        ],
        "begin",
    )
    _ordered(
        begin,
        [
            "watchdog_armed VALUE=1",
            "watchdog_deadline VALUE={now + 600.0}",
            "UPDATE_DELAYED_GCODE ID=KCTRL_START_WATCHDOG_V1 DURATION=5",
            "M140 S{bed}",
        ],
        "watchdog_before_heat",
    )
    _ordered(
        after_reference,
        ["KCTRL_PRODUCTION_ARM", "KCTRL_START_AFTER_ARM_V1"],
        "after_reference",
    )
    _ordered(
        after_arm,
        ["KCTRL_PRODUCTION_ASSERT_ARMED", "M104 S{first_nozzle}", "M109 S{first_nozzle}", "KCTRL_START_VISIBLE_PURGE_V1"],
        "after_arm",
    )
    _ordered(
        purge,
        [
            "KCTRL_PRODUCTION_ASSERT_ARMED",
            "watchdog_deadline VALUE={now + 60.0}",
            "G1 Z5",
            "G1 X15 Y20",
            "G1 Z0.30",
            "G1 Y180 E18",
            "watchdog_armed VALUE=0",
            "phase VALUE='\"model_ready\"'",
        ],
        "purge",
    )
    _ordered(
        watchdog,
        [
            'printer.print_stats.state|string != "printing"',
            "TURN_OFF_HEATERS",
            "watchdog_armed VALUE=0",
            "phase VALUE='\"watchdog_aborted\"'",
        ],
        "watchdog_abort",
    )
    if "manual_clean_deadline VALUE={now + 300.0}" not in confirm:
        raise ValueError("manual_clean_confirmation_has_no_deadline")
    if "now > owner.manual_clean_deadline|float" not in begin:
        raise ValueError("expired_manual_clean_confirmation_not_rejected")

    active = _active_gcode_lines(cfg)
    all_g28 = [line for line in active if re.match(r"^G28(?:\s|$)", line)]
    g28_xy = [line for line in active if line == "G28 X Y"]
    accurate = [line for line in active if line == "ACCURATE_G28"]
    if all_g28 != ["G28 X Y"] or len(g28_xy) != 1 or len(accurate) != 1:
        raise ValueError("reference_execution_count_changed")

    forbidden_prefixes = (
        "START_PRINT",
        "BOX_START_PRINT",
        "BOX_START_PRINT_EXTRUDE_MATERIAL",
        "CX_ROUGH_G28",
        "CX_NOZZLE_CLEAR",
        "NOZZLE_CLEAR",
        "G29",
        "BED_MESH_CALIBRATE",
        "CX_PRINT_LEVELING_CALIBRATION",
        "CHECK_BED_MESH",
        "T0",
        "T1 ",
        "T2 ",
        "T3 ",
        "SAVE_CONFIG",
    )
    forbidden_hits = [line for line in active if line.upper().startswith(forbidden_prefixes)]
    if forbidden_hits:
        raise ValueError("forbidden_active_command:%s" % forbidden_hits)
    if any("S220" in line.upper() or "Z_ADJUST=0.27" in line.upper() for line in active):
        raise ValueError("hidden_temperature_or_offset")

    return {
        "status": "START_SEQUENCE_OWNER_V1_INSTALLED_PAYLOAD_OK" if installed else "START_SEQUENCE_OWNER_V1_PREFLIGHT_QUALIFIED_OK",
        "owned_orca_lines": len(orca_lines),
        "g28_xy_only": len(g28_xy),
        "accurate_z_references": len(accurate),
        "automatic_brush_commands": 0,
        "mesh_calibration_commands": 0,
        "cfs_effect_commands": 0,
        "explicit_temperatures_c": [55, 140, 190],
        "supported_branch": contract["scope"]["supported_branch"],
        "deployment_candidate": contract["deployment_candidate"],
        "watchdog_scenarios": contract["thermal_watchdog"]["scenario_matrix"],
        "manual_clean_token_validity_s": contract["manual_cleaning"]["token_validity_s"],
        "exact_Jinja_parser": "13_sections_passed_in_live_read_only_preflight",
        "physical_trial": contract["physical_trial"]["blocker"],
    }


def main() -> int:
    print(json.dumps(verify(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
