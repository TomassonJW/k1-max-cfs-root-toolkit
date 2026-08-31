#!/usr/bin/env python3
"""Vérifie hors imprimante la gate physique directe T1A."""

import ast
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def load(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def verify():
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (HERE / "deployment-manifest.json").read_text(encoding="utf-8")
    )
    if contract["mission"] != manifest["mission"]:
        raise AssertionError("mission_mismatch")
    if contract["status"] != "CLOSED_KO_BEFORE_FILAMENT_EFFECT":
        raise AssertionError("contract_status_invalid")
    if manifest["status"] != "closed_ko_before_filament_effect":
        raise AssertionError("manifest_status_invalid")
    if contract["authority"]["automatic_retry"] is not False:
        raise AssertionError("automatic_retry_open")
    for key in ("printing", "purge", "probe", "mesh_calibration", "axis_motion"):
        if contract["authority"][key] is not False:
            raise AssertionError("forbidden_authority_open:%s" % key)
    correction = contract["product_contract_correction"]
    if not correction["cutter_position_and_cut_before_any_unload"]:
        raise AssertionError("cutter_not_required")
    if not correction["purge_in_bin_after_every_load"]:
        raise AssertionError("purge_not_required")
    if correction["purge_release_round_trips"] != "3_to_4":
        raise AssertionError("purge_release_count_invalid")

    for item in manifest["local_files"]:
        path = ROOT / item["path"]
        if digest(path) != item["sha256"]:
            raise AssertionError("local_hash_mismatch:%s" % item["path"])

    active = (HERE / "k1-control-cfs-direct-owner-active-physical-v1.cfg").read_text(
        encoding="utf-8"
    )
    if "enabled: true" in active or active.count("enabled: false") != 1:
        raise AssertionError("active_config_invalid")

    remote = (HERE / "remote_phase.py").read_text(encoding="utf-8")
    ast.parse(remote, filename="remote_phase.py", feature_version=(3, 8))
    if "V1_CLOSED_KO = True" not in remote:
        raise AssertionError("remote_program_not_closed")
    for required in (
        '"M104 S220"',
        '"TURN_OFF_HEATERS"',
        '"KCTRL_CFS_DIRECT_LOAD ROUTE=T1A EFFECT_ID="',
        '"KCTRL_CFS_DIRECT_UNLOAD ROUTE=T1A EFFECT_ID="',
        '"BOX_ENABLE_AUTO_REFILL ENABLE=0"',
        '"BOX_ENABLE_AUTO_REFILL ENABLE=1"',
        '"automatic_retry_count": 0',
    ):
        if required not in remote:
            raise AssertionError("remote_guard_missing:%s" % required)
    for forbidden in ("G28", "BED_MESH_CALIBRATE", "START_PRINT", "RESUME_BASE", "M109"):
        if forbidden in remote:
            raise AssertionError("remote_forbidden_command:%s" % forbidden)

    runner = (HERE / "run_gate.ps1").read_text(encoding="utf-8")
    for required in (
        "Assert-Authority",
        "Invoke-DeactivateInternal",
        "Restart-And-RestoreMesh",
        "scp.exe '-O'",
        "PrepareClear",
        "Deactivate",
        "Validate",
        "V1 close KO et rendue non executable",
    ):
        if required not in runner:
            raise AssertionError("runner_guard_missing:%s" % required)

    scenarios = load("cfs_direct_physical_scenarios", HERE / "run_scenarios.py")
    results = scenarios.run()
    if len(results) != 15 or any(item["status"] != "OK" for item in results):
        raise AssertionError("offline_scenarios_invalid")
    return {
        "status": "OK",
        "scenario_count": len(results),
        "printer_connection": False,
        "physical_action": False,
        "authorized_gate": contract["mission"],
    }


if __name__ == "__main__":
    result = verify()
    print(
        "VERIFY_CFS_DIRECT_OWNER_PHYSICAL_LOAD_UNLOAD_V1_CLOSED_KO_BEFORE_EFFECT %d/%d"
        % (result["scenario_count"], result["scenario_count"])
    )
