#!/usr/bin/env python3
"""Vérifie l'orchestrateur stock-derived hors imprimante V1."""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "stock_derived_orchestrator_verifier_runner",
        HERE / "run_scenarios.py",
    )
    if spec is None or spec.loader is None:
        raise ValueError("runner_import_spec_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify():
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    source_path = HERE / "orchestrator.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path), feature_version=(3, 8))

    if contract["status"] != "OFFLINE_PERSISTABLE_ORCHESTRATOR_NO_CONNECTOR":
        raise ValueError("contract_status_invalid")
    if any(value is not False for value in contract["authority"].values()):
        raise ValueError("authority_not_closed")
    boundary = contract["current_runtime_boundary"]
    for field in (
        "geometry_handoff_adapter_installed",
        "moonraker_connector_present",
        "state_file_writer_present",
        "effect_dispatcher_present",
    ):
        if boundary[field] is not False:
            raise ValueError("runtime_boundary_open:%s" % field)

    forbidden_imports = {
        "aiohttp", "http", "os", "paramiko", "requests", "serial",
        "socket", "subprocess", "urllib",
    }
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    if imported & forbidden_imports:
        raise ValueError("runtime_or_transport_import_found")

    required_commands = (
        "KCTRL_PREPARE_GEOMETRY_BEFORE_INSERTION_R4",
        "KCTRL_STOCK_CYCLE_CUT_UNLOAD_V1",
        "KCTRL_STOCK_CYCLE_LOAD_PURGE_V1",
        "KCTRL_STOCK_CYCLE_PRIME_V1",
        "KCTRL_STOCK_CYCLE_REFILL_GUARD_V1",
        "KCTRL_STOCK_CYCLE_END_V1",
    )
    if any(command not in source for command in required_commands):
        raise ValueError("required_command_mapping_missing")
    for forbidden in ("BOX_", "BED_MESH_CALIBRATE", "CX_PRINT_LEVELING_CALIBRATION"):
        command_literals = [
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and node.value.strip().startswith(forbidden)
            and node.value.strip() != forbidden
        ]
        if command_literals:
            raise ValueError("forbidden_command_literal:%s" % forbidden)

    required_ticket_fragments = (
        '"status": "claimed"',
        '"attempt_count": 1',
        '"automatic_retry_count": 0',
        '"command_sha256": _command_digest(command)',
        '"proof_sha256": None',
        '"claimed_ticket_recovered_without_outcome"',
        '"effect_outcome_unknown_no_retry"',
    )
    if any(fragment not in source for fragment in required_ticket_fragments):
        raise ValueError("persistent_ticket_contract_missing")

    sources = contract["sources"]
    source_text = {
        name: (ROOT / path).read_text(encoding="utf-8", errors="replace")
        for name, path in sources.items()
    }
    if "equivalent_spool_runout_refill" not in source_text["lifecycle"]:
        raise ValueError("lifecycle_refill_source_missing")
    owner_contract = json.loads(source_text["owner_and_refill"])
    owner_identity = owner_contract["material_identity"]
    for field in contract["equivalent_refill"]["required_exact_fields"]:
        if field == "user_approved":
            if owner_identity.get("user_approval_required") is not True:
                raise ValueError("owner_refill_user_approval_missing")
            continue
        if field not in owner_identity["required_exact_fields"]:
            raise ValueError("owner_refill_field_missing:%s" % field)
    if "KCTRL_STOCK_CYCLE_REFILL_GUARD_V1" not in source_text["effect_primitives"]:
        raise ValueError("effect_refill_primitive_missing")
    if "geometry_ready_for_insertion" not in source_text["geometry_source"]:
        raise ValueError("R4_geometry_source_missing")

    matrix = load_runner().run()
    if matrix["status"] != "OK" or matrix["passed"] != 19 or matrix["total"] != 19:
        raise ValueError("scenario_matrix_failed")
    if matrix["printer_transport"] or matrix["physical_action"] or matrix["deployment_candidate"]:
        raise ValueError("offline_boundary_broken")

    return {
        "status": "CFS_STOCK_DERIVED_ORCHESTRATOR_OFFLINE_V1_OK",
        "scenarios": "19/19",
        "persistent_ticket_before_effect": True,
        "unknown_effect_never_replayed": True,
        "tool_change_encoded": True,
        "equivalent_refill_encoded": True,
        "strict_identical_spare_required": True,
        "post_filament_contact_forbidden": True,
        "current_profile_only": True,
        "printer_transport": False,
        "physical_action": False,
        "deployment_candidate": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, sort_keys=True))
