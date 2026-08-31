#!/usr/bin/env python3
"""Vérifie le candidat de pose désactivée du cycle dérivé du stock."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Dict


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "stock_cycle_install_disabled_verifier_runner",
        HERE / "run_scenarios.py",
    )
    if spec is None or spec.loader is None:
        raise ValueError("runner_import_spec_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ordered(text: str, fragments) -> bool:
    cursor = 0
    for fragment in fragments:
        position = text.find(fragment, cursor)
        if position < 0:
            return False
        cursor = position + len(fragment)
    return True


def verify() -> Dict[str, Any]:
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    evidence = json.loads((HERE / "evidence-map.json").read_text(encoding="utf-8"))
    manifest = json.loads((HERE / "deployment-manifest.json").read_text(encoding="utf-8"))
    config_text = (HERE / "k1-control-stock-derived-cycle-owner-disabled-v1.cfg").read_text(encoding="utf-8")
    component_path = HERE / "k1_control_stock_cycle_owner.py"
    component_text = component_path.read_text(encoding="utf-8")

    if contract["status"] != "OFFLINE_INSTALL_CANDIDATE_DISABLED":
        raise ValueError("contract_status_invalid")
    if any(contract["authority"][name] is not False for name in (
        "printer_connection", "remote_write", "service_restart", "heat",
        "axis_motion", "extrusion", "cfs_frame", "deployment_authorized",
        "activation_authorized", "production_authorized",
    )):
        raise ValueError("authority_not_closed")
    if "[k1_control_stock_cycle_owner]" not in config_text or "enabled: false" not in config_text:
        raise ValueError("disabled_config_invalid")
    if "SET_GCODE_VARIABLE" in config_text:
        raise ValueError("enabled_must_not_be_gcode_mutable")

    tree = ast.parse(component_text, filename=str(component_path))
    forbidden_imports = {"requests", "socket", "subprocess", "urllib", "paramiko", "serial"}
    imported = set()
    strings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            strings.append(node.value)
    if imported & forbidden_imports:
        raise ValueError("transport_import_found")
    if any(value.strip().upper().startswith("BOX_") for value in strings):
        raise ValueError("stock_BOX_command_found")

    effect_methods = (
        "cmd_CUT_UNLOAD", "cmd_LOAD_PURGE", "cmd_PRIME",
        "cmd_REFILL_GUARD", "cmd_END",
    )
    class_node = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "K1ControlStockCycleOwner"
    )
    methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}
    for method_name in effect_methods:
        method = methods[method_name]
        first = method.body[0]
        if not isinstance(first, ast.Try):
            raise ValueError("effect_guard_try_missing:%s" % method_name)
        first_try = first.body[0]
        if not (
            isinstance(first_try, ast.Expr)
            and isinstance(first_try.value, ast.Call)
            and isinstance(first_try.value.func, ast.Attribute)
            and first_try.value.func.attr == "_require_enabled"
        ):
            raise ValueError("effect_guard_not_first:%s" % method_name)

    required_motion = (
        "G1 X38 Y230 F7000",
        "G1 X38 Y304.5 F7000",
        "G1 X185.5 Y305 F1200",
        "G1 Z30 F600",
        "G1 X203 Y273 F1200",
        "G1 X206 F180",
        "G1 X203 F180",
        "G1 X0.1 Y20 Z0.3 F6000",
        "G1 X0.1 Y180 Z0.3 F3000 E10",
        "G1 X0.4 Y180 Z0.3 F3000",
        "G1 X0.4 Y20 Z0.3 F3000 E10",
        "G1 Y10 F3000",
        "G1 Z5 F1200",
    )
    if any(fragment not in component_text for fragment in required_motion):
        raise ValueError("required_motion_missing")
    cutter_runtime_order = (
        '"G1 X38 Y304.5 F7000"',
        '"G4 P1500"',
        "self._require_cut_sensor(True)",
        '"KCTRL_CFS_DIRECT_UNLOAD ROUTE=%s EFFECT_ID=%s "',
        '"G1 X38 Y230 F7000"',
        '"G4 P1000"',
        "self._require_cut_sensor(False)",
    )
    if not ordered(component_text, cutter_runtime_order):
        raise ValueError("cutter_hold_during_unload_order_missing")
    for forbidden in ("G28", "BED_MESH_CALIBRATE", "CX_PRINT_LEVELING_CALIBRATION"):
        if ('"%s' % forbidden) in component_text:
            raise ValueError("forbidden_contact_command_found:%s" % forbidden)

    cutter_cfg = ROOT / evidence["cutter_configuration"]["path"]
    cutter_cfg_text = cutter_cfg.read_text(encoding="utf-8", errors="replace")
    for fragment in evidence["cutter_configuration"]["required_fragments"]:
        if fragment not in cutter_cfg_text:
            raise ValueError("cutter_config_fragment_missing:%s" % fragment)
    cutter_run = ROOT / evidence["cutter_observed_run"]["path"]
    cutter_run_text = cutter_run.read_text(encoding="utf-8", errors="replace")
    if not ordered(cutter_run_text, evidence["cutter_observed_run"]["required_fragments_in_order"]):
        raise ValueError("cutter_observed_order_missing")

    refill_contract = json.loads(
        (ROOT / evidence["equivalent_refill"]["contract_path"]).read_text(encoding="utf-8")
    )
    refill_text = json.dumps(refill_contract, ensure_ascii=False, sort_keys=True)
    for scenario in evidence["equivalent_refill"]["required_scenarios"]:
        if scenario not in refill_text:
            raise ValueError("equivalent_refill_scenario_missing:%s" % scenario)

    for item in manifest["files"] + manifest["support_files"]:
        if sha256(HERE / item["source"]) != item["sha256"]:
            raise ValueError("manifest_hash_mismatch:%s" % item["source"])
    deployer = manifest["deployer"]
    if sha256(ROOT / deployer["source"]) != deployer["sha256"]:
        raise ValueError("deployer_hash_mismatch")
    preparation = manifest["preparation_evidence"]
    if sha256(HERE / preparation["source"]) != preparation["sha256"]:
        raise ValueError("preparation_evidence_hash_mismatch")
    preparation_value = json.loads((HERE / preparation["source"]).read_text(encoding="utf-8"))
    if preparation_value["prospective_sha256"] != manifest["printer_cfg"]["installed_sha256"]:
        raise ValueError("prospective_printer_cfg_hash_mismatch")
    if any(preparation_value[name] is not False for name in (
        "remote_write", "gcode", "service_action", "heat", "motion",
        "extrusion", "cfs_frame",
    )):
        raise ValueError("preparation_read_only_boundary_broken")
    if manifest["status"] != "offline_review_candidate_not_installed":
        raise ValueError("manifest_status_invalid")
    if manifest["required_disabled_validation"]["expected_refused_entries"] != 5:
        raise ValueError("disabled_refusal_count_invalid")
    if '"claimed_effect_count": len(self.claimed_effect_ids)' not in component_text:
        raise ValueError("claimed_effect_status_missing")

    matrix = load_runner().run()
    if matrix["status"] != "OK" or matrix["passed"] != matrix["total"] or matrix["total"] != 17:
        raise ValueError("scenario_matrix_failed")
    return {
        "status": "CFS_STOCK_DERIVED_CYCLE_OWNER_INSTALL_DISABLED_V1_OK",
        "scenarios": "17/17",
        "uncertain_effect_retry_blocked": True,
        "effect_entries_refuse_before_arguments": True,
        "cutter_stock_evidence_verified": True,
        "cutter_held_through_direct_unload": True,
        "cutter_sensor_required_before_and_after_unload": True,
        "purge_bin_and_release_prepared": True,
        "stock_prime_line_prepared": True,
        "equivalent_refill_preserved": True,
        "new_discovery_print_required": False,
        "deployment_candidate": True,
        "installed": False,
        "enabled": False,
        "printer_connection": False,
        "physical_action": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, sort_keys=True))
