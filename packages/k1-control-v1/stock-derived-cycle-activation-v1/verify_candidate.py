#!/usr/bin/env python3
"""Vérifie hors imprimante le candidat d'activation au repos."""

import ast
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def source(name):
    return (HERE / name).read_text(encoding="utf-8")


python_files = (
    "k1_control_cfs_startup_exclusion.py",
    "k1_control_cfs_runout_owner.py",
    "active_core.py",
    "job_contract.py",
    "moonraker_component.py",
    "remote_source_validate.py",
    "remote_validate_active_idle.py",
    "remote_prospective_hash.py",
    "remote_restore_accepted_z.py",
    "run_scenarios.py",
)
for name in python_files:
    ast.parse(source(name), filename=name)

direct_cfg = source("k1-control-cfs-direct-owner-active-v1.cfg")
cycle_cfg = source("k1-control-stock-cycle-active-v1.cfg")
geometry_cfg = source("k1-control-stock-geometry-handoff-active-v1.cfg")
moon_cfg = source("moonraker-section.conf")

if not (
    direct_cfg.index("[k1_control_cfs_startup_exclusion]")
    < direct_cfg.index("[k1_control_cfs_direct_owner]")
    < direct_cfg.index("[k1_control_cfs_runout_owner]")
):
    raise RuntimeError("klipper_owner_load_order_invalid")
for name, text in (
    ("direct", direct_cfg),
    ("cycle", cycle_cfg),
    ("geometry", geometry_cfg),
    ("moonraker", moon_cfg),
):
    if "enabled: true" not in text or "enabled: false" in text:
        raise RuntimeError("active_config_invalid:%s" % name)

combined = "\n".join(
    source(name) for name in (
        "active_core.py",
        "moonraker_component.py",
        "k1_control_cfs_runout_owner.py",
    )
)
for forbidden in (
    "BOX_EXTRUDE_MATERIAL",
    "BOX_RETRUDE_MATERIAL",
    "BOX_START_PRINT",
    "BED_MESH_CALIBRATE",
    "CX_PRINT_LEVELING_CALIBRATION",
):
    if forbidden in combined:
        raise RuntimeError("forbidden_runtime_route:%s" % forbidden)
for required in (
    "KCTRL_CFS_RUNOUT_DISARM_V1",
    "KCTRL_CFS_RUNOUT_RELEASE_V1",
    "KCTRL_STOCK_CYCLE_EMPTY_END_V1",
    "KCTRL_STOCK_RESUME_OWNED_V1",
):
    if required not in combined and required not in cycle_cfg:
        raise RuntimeError("required_runtime_marker_missing:%s" % required)
if "premature_owner_shutdown_command" not in source("job_contract.py"):
    raise RuntimeError("job_shutdown_guard_missing")

spec = importlib.util.spec_from_file_location(
    "activation_scenarios", HERE / "run_scenarios.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("scenario_module_missing")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
result = module.run()
if result.get("status") != "OK" or result.get("passed") != result.get("total"):
    raise RuntimeError("activation_scenarios_failed:%s" % json.dumps(result))
if result.get("printer_transport") is not False or result.get("physical_action") is not False:
    raise RuntimeError("offline_scenario_boundary_invalid")

print(json.dumps({
    "status": "OK",
    "scenarios": result["total"],
    "printer_transport": False,
    "physical_action": False,
    "stock_BOX_effect": False,
    "post_filament_probe": False,
    "mesh_recalculation": False,
}, sort_keys=True, separators=(",", ":")))
print("VERIFY_STOCK_DERIVED_CYCLE_ACTIVATION_V1_OK")
