#!/usr/bin/env python3
"""Vérification hors imprimante du candidat combiné install-disabled."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MANIFEST = HERE / "deployment-manifest.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("module_spec_missing:%s" % name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
baseline = json.loads((HERE / "baseline-read-only.json").read_text(encoding="utf-8"))

if manifest["gate"] != contract["gate"]:
    raise RuntimeError("gate_mismatch")
if manifest["status"] != "offline_review_candidate_not_installed":
    raise RuntimeError("manifest_status_invalid")
if contract["authority"]["activation_authorized"] is not False:
    raise RuntimeError("activation_must_remain_closed")
if contract["authority"]["physical_trial_authorized"] is not False:
    raise RuntimeError("physical_trial_must_remain_closed")

checked = 0
for group in ("files", "support_files", "preparation_evidence"):
    for entry in manifest[group]:
        path = ROOT / entry["source"]
        if not path.is_file() or digest(path) != entry["sha256"]:
            raise RuntimeError("manifest_hash_mismatch:%s" % entry["source"])
        checked += 1
deployer = ROOT / manifest["deployer"]["source"]
if digest(deployer) != manifest["deployer"]["sha256"]:
    raise RuntimeError("deployer_hash_mismatch")
checked += 1

if baseline["printer_cfg"]["baseline_sha256"] != manifest["baseline"]["printer_cfg_sha256"]:
    raise RuntimeError("printer_baseline_mismatch")
if baseline["printer_cfg"]["prospective_sha256"] != manifest["installed"]["printer_cfg_sha256"]:
    raise RuntimeError("printer_prospective_mismatch")
if baseline["moonraker_conf"]["baseline_sha256"] != manifest["baseline"]["moonraker_conf_sha256"]:
    raise RuntimeError("moonraker_baseline_mismatch")
if baseline["moonraker_conf"]["prospective_sha256"] != manifest["installed"]["moonraker_conf_sha256"]:
    raise RuntimeError("moonraker_prospective_mismatch")
if not all(baseline["new_paths_absent"].values()):
    raise RuntimeError("preparation_path_was_not_absent")
for name, expected in baseline["required"].items():
    if manifest["baseline"]["required_files"][name]["sha256"] != expected:
        raise RuntimeError("required_baseline_mismatch:%s" % name)

geometry_text = (HERE / "k1_control_stock_geometry_handoff.py").read_text(encoding="utf-8")
moonraker_text = (HERE / "moonraker_component.py").read_text(encoding="utf-8")
core_text = (
    ROOT
    / "packages/k1-control-v1/cfs-stock-derived-orchestrator-offline-v1/orchestrator.py"
).read_text(encoding="utf-8")
for name, text in (
    ("geometry", geometry_text),
    ("moonraker", moonraker_text),
    ("core", core_text),
):
    ast.parse(text, filename=name + ".py")
    for forbidden in ("import requests", "import subprocess", "import serial"):
        if forbidden in text:
            raise RuntimeError("forbidden_transport_import:%s" % name)

for forbidden in (
    " G28",
    '"G28',
    "BED_MESH_CALIBRATE",
    "PROBE",
    '"M104',
    '"M109',
    '"M140',
    '"M190',
    '"G0 ',
    '"G1 ',
    '"BOX_',
    '"KCTRL_CFS_DIRECT_',
):
    if forbidden in geometry_text:
        raise RuntimeError("geometry_contains_physical_command:%s" % forbidden)
for required in (
    "geometry_ready_for_insertion",
    "k1_p001_t055_r001_n11x11",
    "accepted_Z_changed",
    "filament_or_stock_owner_present_before_handoff",
    "effect_id_already_claimed_no_retry",
    "command_failed_uncertain_no_retry",
):
    if required not in geometry_text:
        raise RuntimeError("geometry_guard_missing:%s" % required)

for required in (
    "install-disabled-v1 cannot be enabled",
    "stock_cycle_disabled",
    "state_file_read_count\": 0",
    "state_file_write_count\": 0",
    "gcode_dispatch_count\": 0",
    "camera_request_count\": 0",
    "stock_BOX_effect_count\": 0",
    "k1_control_stock_cycle_core",
):
    if required not in moonraker_text:
        raise RuntimeError("moonraker_disabled_guard_missing:%s" % required)

for required in (
    "IDENTITY_FIELDS",
    "material_digest",
    "identical_replacement_missing",
    "identical_replacement_ambiguous",
    "await_refill_camera",
    "resume_context",
):
    if required not in core_text:
        raise RuntimeError("equivalent_refill_invariant_missing:%s" % required)

for config_name in (
    "k1-control-stock-geometry-handoff-disabled-v1.cfg",
    "moonraker-section.conf",
):
    config_text = (HERE / config_name).read_text(encoding="utf-8")
    if "enabled: false" not in config_text or "enabled: true" in config_text:
        raise RuntimeError("config_not_immutable_disabled:%s" % config_name)

runner = load_module("stock_handoff_scenarios", HERE / "run_scenarios.py")
scenario_result = runner.run()
if scenario_result["status"] != "OK" or scenario_result["passed"] != 12:
    raise RuntimeError("scenario_matrix_failed:%s" % scenario_result)

print(
    json.dumps(
        {
            "status": "OK",
            "manifest_files_checked": checked,
            "scenarios_passed": scenario_result["passed"],
            "scenarios_total": scenario_result["total"],
            "enabled": False,
            "printer_transport": False,
            "physical_action": False,
            "equivalent_spool_refill_preserved": True,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
)
print("VERIFY_STOCK_DERIVED_HANDOFF_MOONRAKER_INSTALL_DISABLED_V1_OK")
