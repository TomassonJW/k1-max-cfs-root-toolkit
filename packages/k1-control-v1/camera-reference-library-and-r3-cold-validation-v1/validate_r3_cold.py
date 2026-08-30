#!/usr/bin/env python3
"""Pure checks for the two camera holds and the closed R3 timeout paths."""

from __future__ import annotations

import json
import re
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
R3 = ROOT / "packages" / "k1-control-v1" / "start-sequence-owner-camera-purge-r3"
CFG = R3 / "k1-control-start-sequence-owner-camera-purge-r3.cfg"
CONTRACT = PACKAGE / "contract.json"
LIBRARY = PACKAGE / "reference-library.json"


class ValidationError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValidationError(code)


def section(text: str, header: str) -> str:
    marker = f"[{header}]"
    require(text.count(marker) == 1, f"section_count:{header}")
    return text.split(marker, 1)[1].split("\n[", 1)[0]


def require_order(body: str, fragments: list[str], code: str) -> None:
    cursor = -1
    for fragment in fragments:
        position = body.find(fragment, cursor + 1)
        require(position >= 0, f"{code}:{fragment}")
        cursor = position


def active_gcode_lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and not line.startswith(("{", "[", "description:", "variable_", "gcode:")):
            lines.append(line)
    return lines


def verify() -> dict[str, object]:
    text = CFG.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    library = json.loads(LIBRARY.read_text(encoding="utf-8"))

    clean_hold = section(text, "gcode_macro KCTRL_START_BIN_PURGE_AND_RELEASE_R3")
    clean_confirm = section(text, "gcode_macro KCTRL_CONFIRM_CAMERA_CLEAN_FOR_REFERENCE_R3")
    prime = section(text, "gcode_macro KCTRL_START_VISIBLE_PURGE_V1")
    prime_confirm = section(text, "gcode_macro KCTRL_CONFIRM_CAMERA_PRIME_AND_RESUME_R3")
    watchdog = section(text, "delayed_gcode KCTRL_START_WATCHDOG_V1")

    require_order(clean_hold, ["camera_clean_check", "PAUSE_BASE"], "clean_hold_missing")
    require("ACCURATE_G28" not in clean_hold, "precise_z_reachable_before_clean_confirmation")
    require_order(
        clean_confirm,
        ["camera_clean_check", "precise_reference", "ACCURATE_G28", "KCTRL_START_AFTER_REFERENCE_V1"],
        "clean_confirmation_order",
    )
    require_order(prime, ["camera_prime_check"], "prime_hold_missing")
    require("RESUME_BASE" not in prime, "model_resumes_before_prime_confirmation")
    require_order(prime_confirm, ["camera_prime_check", "model_ready", "RESUME_BASE"], "prime_confirmation_order")

    command_lines = active_gcode_lines(text)
    require(not any(re.match(r"^(PAUSE|RESUME)(?:\s|$)", line) for line in command_lines), "stock_pause_or_resume_called")
    require(sum(line == "PAUSE_BASE" for line in command_lines) == 1, "pause_base_count_drift")
    require(sum(line == "RESUME_BASE" for line in command_lines) == 1, "resume_base_count_drift")
    for command in ("BOX_START_PRINT", "BOX_MATERIAL_FLUSH", "BOX_NOZZLE_CLEAN", "CX_NOZZLE_CLEAR"):
        require(command not in command_lines, f"forbidden_stock_command:{command}")

    for phase in ("camera_clean_check", "camera_prime_check"):
        require(phase in watchdog, f"watchdog_camera_phase_missing:{phase}")
    require_order(watchdog, ["TURN_OFF_HEATERS", "watchdog_aborted"], "watchdog_shutdown_order")
    require("KCTRL_CONFIRM_CAMERA_" not in watchdog, "watchdog_confirms_camera")
    require("camera_confirmed" not in watchdog, "watchdog_invents_camera_confirmation")

    automatic_calls = re.findall(r"^\s+KCTRL_CONFIRM_CAMERA_[A-Z0-9_]+\s*$", text, flags=re.MULTILINE)
    require(automatic_calls == [], "camera_confirmation_called_automatically")
    require(text.count("{%") == text.count("%}"), "jinja_block_delimiter_mismatch")
    action_open = len(re.findall(r"\{action_(?:respond_info|raise_error)\(", text))
    action_close = len(re.findall(r"\)\}", text))
    require(action_open <= action_close, "jinja_action_delimiter_mismatch")

    acquired = [item["id"] for item in library["references"] if item["acquired"]]
    missing = [item["id"] for item in library["references"] if not item["acquired"]]
    require(acquired == ["SAFE_IDLE_PARK"], "reference_library_invents_acquired_state")
    require(set(missing) == set(contract["reference_policy"]["missing"]), "missing_reference_policy_drift")
    require(library["automatic_semantic_decision"] is False, "camera_must_not_auto_confirm_semantics")
    require(contract["effect_connectors"] == [], "effect_connector_present")
    require(not any(contract["effects"].values()), "cold_contract_contains_effect")
    require(contract["deployment_candidate"] is False, "deployment_opened")
    require(contract["physical_run_authorized"] is False, "physical_run_opened")

    return {
        "status": "CAMERA_REFERENCE_LIBRARY_AND_R3_COLD_STATIC_OK",
        "r3_sections": len(re.findall(r"^\[(?:gcode_macro|delayed_gcode) ", text, flags=re.MULTILINE)),
        "acquired_references": acquired,
        "missing_references": missing,
        "camera_before_precise_z": True,
        "camera_before_model": True,
        "base_pause_resume_only": True,
        "watchdog_shutdown_without_confirmation": True,
        "effect_connectors": [],
    }


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2, sort_keys=True))
