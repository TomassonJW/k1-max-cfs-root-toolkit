#!/usr/bin/env python3
"""Vérifie l'identité, les preuves locales et l'inertie du paquet R2."""

from __future__ import annotations

import json
from pathlib import Path

from run_scenarios import run


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]


def verify_fragments_in_order(source: Path, fragments: list[str]) -> None:
    text = source.read_text(encoding="utf-8", errors="replace")
    cursor = 0
    for fragment in fragments:
        position = text.find(fragment, cursor)
        if position < 0:
            raise ValueError("evidence_fragment_missing:%s:%s" % (source.name, fragment))
        cursor = position + len(fragment)


def verify() -> dict:
    contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
    calibration = json.loads((PACKAGE / "calibration-path-contract.json").read_text(encoding="utf-8"))
    stock_delta = json.loads((PACKAGE / "stock-sequence-delta.json").read_text(encoding="utf-8"))
    if any(contract[name] is not False for name in ("deployment_candidate", "printer_connection", "remote_write", "physical_action", "automatic_retry")):
        raise ValueError("contract_not_inert")
    if any(calibration[name] is not False for name in ("printer_connection", "physical_action", "deployment_candidate")):
        raise ValueError("calibration_contract_not_inert")
    if contract["hard_invariants"]["contact_or_mesh_recalculation_after_load"] != "forbidden":
        raise ValueError("post_load_contact_not_forbidden")
    if contract["hard_invariants"]["stock_BOX_effects"] != "forbidden":
        raise ValueError("stock_BOX_effect_not_forbidden")
    if contract["derivation"] != "observed_creality_stock_sequence_with_minimal_explicit_delta":
        raise ValueError("stock_derivation_missing")
    if contract["evidence_map"] != "stock-sequence-delta.json":
        raise ValueError("stock_evidence_map_missing")
    if contract["prime_line"]["path_xyz_mm"][1][1] != 180.0:
        raise ValueError("prime_reference_drift")
    if contract["prime_line"]["required_post_line_clearance_origin"] != "explicit_user_correction_not_stock_macro":
        raise ValueError("post_prime_clearance_source_confused")

    if stock_delta["coverage"]["new_discovery_print_required"] is not False:
        raise ValueError("unnecessary_discovery_print_requested")
    if stock_delta["implementation_boundary"]["opaque_stock_BOX_calls_allowed_in_final_runtime"] is not False:
        raise ValueError("opaque_stock_effect_allowed")
    actions = {item["action"] for item in stock_delta["delta"]}
    if not {
        "KEEP",
        "REPLACE",
        "ADD_EXPLICIT_CORRECTION",
        "KEEP_CHOREOGRAPHY_REIMPLEMENT_DIRECT",
        "KEEP_CAPABILITY_REIMPLEMENT_DIRECT",
    }.issubset(actions):
        raise ValueError("stock_delta_actions_incomplete")
    invariants = contract["hard_invariants"]
    if invariants["automatic_equivalent_refill_feature_preserved"] is not True:
        raise ValueError("equivalent_refill_feature_lost")
    if invariants["automatic_equivalent_refill_owner"] != "K1_Control":
        raise ValueError("equivalent_refill_owner_invalid")
    if invariants["stock_same_material_group_alone_is_sufficient"] is not False:
        raise ValueError("equivalent_refill_identity_too_weak")

    for source in stock_delta["sources"].values():
        if "required_fragments_in_order" in source:
            verify_fragments_in_order(ROOT / source["path"], source["required_fragments_in_order"])

    change_gcode = stock_delta["sources"]["single_change_gcode"]
    change_path = ROOT / change_gcode["path"]
    if change_path.stat().st_size != change_gcode["bytes"]:
        raise ValueError("single_change_gcode_size_drift")
    tool_commands = [
        line.strip()
        for line in change_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip() in {"T0", "T1"}
    ]
    if tool_commands != change_gcode["tool_commands_in_order"]:
        raise ValueError("single_change_tool_sequence_drift")

    stock_source = ROOT / contract["prime_line"]["source"]
    stock_text = stock_source.read_text(encoding="utf-8")
    stock_macro = stock_text.split("def cmd_CX_PRINT_DRAW_ONE_LINE(self, gcmd):", 1)[1].split("def cmd_CX_ROUGH_G28", 1)[0]
    stock_lines = (
        "G1 X0.1 Y20 Z0.3 F6000.0",
        "G1 X0.1 Y180.0 Z0.3 F3000.0 E10.0",
        "G1 X0.4 Y180.0 Z0.3 F3000.0",
        "G1 X0.4 Y20.0 Z0.3 F3000.0 E10.0",
        "G1 Y10.0 F3000.0",
    )
    positions = [stock_macro.find(line) for line in stock_lines]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        raise ValueError("stock_prime_source_drift")

    cutter_source = ROOT / contract["cutter_observed_geometry"]["source"]
    cutter_text = cutter_source.read_text(encoding="utf-8")
    for fragment in (
        '"pre_cut_pos_x": "38"',
        '"pre_cut_pos_y": "230.0"',
        '"cut_pos_x": "38"',
        '"cut_pos_y": "303.2"',
        '"cut_pos_offset": "1.3"',
        '"cut_velocity": "7000"',
        '"cut_run_count": "1"',
    ):
        if fragment not in cutter_text:
            raise ValueError("cutter_source_drift")

    engine_text = (PACKAGE / "engine.py").read_text(encoding="utf-8")
    for forbidden in ("import requests", "import socket", "import subprocess", "paramiko", "urllib.request"):
        if forbidden in engine_text:
            raise ValueError("transport_found_in_engine")
    matrix = run()
    if matrix["status"] != "OK" or not matrix["manifest_names_match"] or not matrix["expected_total_match"]:
        raise ValueError("scenario_matrix_failed")
    if any(item["printer_transport"] is not False or item["physical_action"] is not False for item in matrix["cases"]):
        raise ValueError("scenario_effect_detected")
    return {
        "status": "CFS_CUTTER_PURGE_INTEGRATED_R2_OFFLINE_V1_OK",
        "scenarios": "%d/%d" % (matrix["passed"], matrix["total"]),
        "stock_sequence_delta_verified": True,
        "normal_print_trace_verified": True,
        "single_change_trace_verified": True,
        "equivalent_refill_preserved": True,
        "new_discovery_print_required": False,
        "stock_prime_source_verified": True,
        "cutter_geometry_source_verified": True,
        "printer_transport": False,
        "physical_action": False,
        "deployment_candidate": False,
        "known_blockers": contract["known_blockers_before_any_install"],
    }


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, sort_keys=True))
