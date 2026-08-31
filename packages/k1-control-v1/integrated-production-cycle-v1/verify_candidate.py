#!/usr/bin/env python3
"""Static, deterministic checks for the integrated cycle candidate."""

from __future__ import annotations

import json
import ast
from pathlib import Path
import re


PACKAGE = Path(__file__).resolve().parent
CFG = PACKAGE / "k1-control-integrated-production-cycle-v1.cfg"
CONTRACT = PACKAGE / "contract.json"
INDEX = PACKAGE / "www" / "index.html"
APP = PACKAGE / "www" / "app.js"
DIRECT_OWNER_CONTRACT = PACKAGE.parent / "cfs-direct-owner-offline-v1" / "contract.json"


def block(text: str, macro: str) -> str:
    marker = "[gcode_macro %s]" % macro
    if marker not in text:
        raise AssertionError("macro_missing:%s" % macro)
    tail = text.split(marker, 1)[1]
    match = re.search(r"\n\[(?:gcode_macro|delayed_gcode) ", tail)
    return tail[: match.start()] if match else tail


def ordered(text: str, values: list[str], label: str) -> None:
    cursor = -1
    for value in values:
        position = text.find(value, cursor + 1)
        if position < 0:
            raise AssertionError("%s_missing:%s" % (label, value))
        cursor = position


def verify() -> dict:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    direct_owner = json.loads(DIRECT_OWNER_CONTRACT.read_text(encoding="utf-8"))
    cfg = CFG.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    macros = re.findall(r"^\[gcode_macro ([A-Z0-9_]+)\]$", cfg, re.MULTILINE)
    if len(macros) != len(set(macros)):
        raise AssertionError("duplicate_macro")
    for name in macros:
        if re.fullmatch(r"[A-Z_]+[0-9]*", name) is None:
            raise AssertionError("creality_macro_name_invalid:%s" % name)
    required = {
        "KCTRL_CYCLE_PREPARE_V1",
        "KCTRL_CYCLE_UNLOAD_BEFORE_CLEAN_V1",
        "KCTRL_CYCLE_RECONCILE_SLOT_A_BEFORE_CLEAN_V1",
        "KCTRL_CYCLE_CONFIRM_CLEAN_AND_REFERENCE_V1",
        "KCTRL_CYCLE_LOAD_SLOT_A_V1",
        "KCTRL_CYCLE_SINGLE_PURGE_V1",
        "KCTRL_CYCLE_CONFIRM_PURGE_CAMERA_V1",
        "KCTRL_CYCLE_JOB_ASSERT_V1",
        "KCTRL_CYCLE_END_V1",
        "KCTRL_CYCLE_ABORT_V1",
        "KCTRL_CYCLE_RESET_V1",
    }
    if not required.issubset(macros):
        raise AssertionError("required_macros_missing")
    executable = "\n".join(
        line.strip() for line in cfg.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    for forbidden in (
        "BED_MESH_CALIBRATE", "CX_PRINT_LEVELING_CALIBRATION", "G29",
        "BOX_START_PRINT", "BOX_END_PRINT", "BOX_MATERIAL_FLUSH",
        "BOX_NOZZLE_CLEAN", "BOX_TNN_RETRY_PROCESS",
        "BOX_EXTRUDE_MATERIAL", "BOX_EXTRUDER_EXTRUDE",
        "BOX_CUT_MATERIAL", "BOX_RETRUDE_MATERIAL",
    ):
        if forbidden in executable:
            raise AssertionError("forbidden_command:%s" % forbidden)
    if re.search(r"(^|\n)\s*(START_PRINT|END_PRINT)(?:\s|$)", executable):
        raise AssertionError("stock_job_entry_present")
    if "220" in executable:
        raise AssertionError("hidden_220_present")

    for macro in (
        "KCTRL_CYCLE_UNLOAD_BEFORE_CLEAN_V1",
        "KCTRL_CYCLE_RECONCILE_SLOT_A_BEFORE_CLEAN_V1",
        "KCTRL_CYCLE_LOAD_SLOT_A_V1",
        "KCTRL_CYCLE_END_V1",
    ):
        guarded = block(cfg, macro)
        if "action_raise_error" not in guarded:
            raise AssertionError("unsafe_cfs_entry_not_blocked:%s" % macro)
    reference = block(cfg, "KCTRL_CYCLE_CONFIRM_CLEAN_AND_REFERENCE_V1")
    ordered(reference, ["KCTRL_CONFIRM_MANUAL_NOZZLE_CLEAN_V1", "KCTRL_PREPARE_GEOMETRY_BEFORE_INSERTION_R4", "KCTRL_CYCLE_VERIFY_REFERENCE_V1"], "reference")
    purge = block(cfg, "KCTRL_CYCLE_SINGLE_PURGE_V1")
    if purge.count(" E{cycle.purge_mm}") != 1:
        raise AssertionError("purge_not_unique")
    if "X-1.7 Y20" not in purge or "Y60 E{cycle.purge_mm}" not in purge:
        raise AssertionError("origin_edge_purge_missing")
    if "M104 S{cycle.purge_nozzle}" not in purge or "M109 S{cycle.purge_nozzle}" not in purge:
        raise AssertionError("explicit_purge_temperature_missing")
    camera = block(cfg, "KCTRL_CYCLE_CONFIRM_PURGE_CAMERA_V1")
    ordered(camera, ["M104 S{cycle.first_nozzle}", "M109 S{cycle.first_nozzle}", "ready_to_print"], "camera_to_first_layer")
    if "KCTRL_CYCLE_JOB_ASSERT_V1" != (PACKAGE / "orca-start.gcode").read_text(encoding="utf-8").strip():
        raise AssertionError("orca_start_not_atomic")
    if "KCTRL_CYCLE_END_V1" != (PACKAGE / "orca-end.gcode").read_text(encoding="utf-8").strip():
        raise AssertionError("orca_end_not_atomic")
    for token in ("Préparer l’impression", "Buse propre — Continuer", "Arrêter en sécurité"):
        if token not in index:
            raise AssertionError("ui_action_missing:%s" % token)
    for endpoint in ("/status", "/files", "/select", "/prepare", "/clean-confirm", "/abort"):
        if endpoint not in app:
            raise AssertionError("ui_endpoint_missing:%s" % endpoint)
    for filename in ("cycle.py", "orchestrator.py", "job_contract.py", "moonraker_component.py"):
        ast.parse((PACKAGE / filename).read_text(encoding="utf-8"), filename=filename, feature_version=(3, 8))
    if "filament_switch_sensor filament_sensor_2" not in cfg:
        raise AssertionError("after_cutter_sensor_guard_missing")
    component = (PACKAGE / "moonraker_component.py").read_text(encoding="utf-8")
    for endpoint in ("/cycle/files", "/cycle/select", "/cycle/camera-verdict"):
        if endpoint not in component:
            raise AssertionError("moonraker_endpoint_missing:%s" % endpoint)
    if contract["normal_end"]["unload_count"] != 1 or contract["single_purge"]["count"] != 1:
        raise AssertionError("contract_effect_count_invalid")
    if direct_owner["status"] != "CLOSED_OK_OFFLINE_24_OF_24":
        raise AssertionError("direct_owner_offline_gate_not_closed")
    if contract["direct_cfs_owner"]["installed"] is not False:
        raise AssertionError("direct_owner_install_state_invalid")
    for filename in ("cycle.py", "orchestrator.py"):
        source = (PACKAGE / filename).read_text(encoding="utf-8")
        if "BOX_" in source:
            raise AssertionError("stock_effect_owner_in_core:%s" % filename)
        for command in (
            "KCTRL_CFS_DIRECT_RECONCILE ROUTE=T1A",
            "KCTRL_CFS_DIRECT_LOAD ROUTE=T1A",
            "KCTRL_CFS_DIRECT_UNLOAD ROUTE=T1A",
        ):
            if command not in source:
                raise AssertionError("direct_owner_command_missing:%s" % command)
    return {
        "status": "OK",
        "macros": len(macros),
        "single_purge": True,
        "full_unload_end": True,
        "cfs_effects_blocked": True,
        "direct_owner_offline": True,
        "ui_actions": 3,
        "printer_transport": False,
        "deployment_candidate": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
