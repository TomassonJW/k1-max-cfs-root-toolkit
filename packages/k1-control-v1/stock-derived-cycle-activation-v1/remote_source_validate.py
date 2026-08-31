#!/usr/bin/env python3
"""Valide sur les Python K1 et Moonraker les sources actives avant pose."""

import ast
import base64


SOURCES = {
    "startup": "__STARTUP_B64__",
    "runout": "__RUNOUT_B64__",
    "active_core": "__ACTIVE_CORE_B64__",
    "job_contract": "__JOB_CONTRACT_B64__",
    "moonraker": "__MOONRAKER_B64__",
}

decoded = {}
for name, encoded in SOURCES.items():
    text = base64.b64decode(encoded).decode("utf-8")
    ast.parse(text, filename=name + ".py")
    decoded[name] = text

required = {
    "startup": (
        "class K1ControlCfsStartupExclusion",
        "BOX_ENABLE_AUTO_REFILL",
        "ready_verified",
    ),
    "runout": (
        "class K1ControlCfsRunoutOwner",
        "BOX_CHECK_MATERIAL_REFILL",
        "KCTRL_CFS_RUNOUT_RELEASE_V1",
        "KCTRL_CFS_RUNOUT_DISARM_V1",
        "exhausted_route_released_without_motor",
    ),
    "active_core": (
        "class ActiveStockDerivedOrchestrator",
        "KCTRL_CFS_RUNOUT_RELEASE_V1",
        "KCTRL_STOCK_CYCLE_EMPTY_END_V1",
        "KCTRL_CFS_RUNOUT_DISARM_V1",
    ),
    "job_contract": (
        "premature_owner_shutdown_command",
        "TURN_OFF_HEATERS",
        "KCTRL_STOCK_JOB_ASSERT_V1",
    ),
    "moonraker": (
        "class K1ControlStockCycle",
        "fresh_runout_signal_missing",
        "KCTRL_STOCK_RESUME_OWNED_V1",
        "expected_empty_effect_id",
    ),
}
for name, markers in required.items():
    if any(marker not in decoded[name] for marker in markers):
        raise RuntimeError("required_source_marker_missing:%s" % name)

if "BOX_EXTRUDE_MATERIAL" in "\n".join(
    decoded[name] for name in ("runout", "active_core", "moonraker")
):
    raise RuntimeError("forbidden_stock_effect_present")
if "BED_MESH_CALIBRATE" in decoded["moonraker"]:
    raise RuntimeError("moonraker_mesh_recalculation_present")

print("REMOTE_STOCK_DERIVED_CYCLE_ACTIVATION_SOURCE_VALIDATE_OK")
