#!/usr/bin/env python3
"""Vérifie le candidat installable désactivé sans contacter la K1."""

import ast
import base64
from contextlib import redirect_stdout
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MANIFEST = HERE / "deployment-manifest.json"
CONTRACT = HERE / "contract.json"
OFFLINE = HERE.parent / "cfs-direct-owner-offline-v1"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def load(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def payload_sources(manifest):
    result = {}
    mapping = {
        "init": "/usr/share/klipper/klippy/extras/k1_control_cfs_direct/__init__.py",
        "protocol": "/usr/share/klipper/klippy/extras/k1_control_cfs_direct/protocol.py",
        "owner": "/usr/share/klipper/klippy/extras/k1_control_cfs_direct/owner.py",
        "runtime_adapter": "/usr/share/klipper/klippy/extras/k1_control_cfs_direct/runtime_adapter.py",
        "component": "/usr/share/klipper/klippy/extras/k1_control_cfs_direct_owner.py",
    }
    by_destination = {item["destination"]: item for item in manifest["files"]}
    for key, destination in mapping.items():
        item = by_destination[destination]
        result[key] = ROOT / item["source"]
    return result


def verify_remote_import_validator(manifest):
    payload = {
        name: base64.b64encode(path.read_bytes()).decode("ascii")
        for name, path in payload_sources(manifest).items()
    }
    encoded = base64.b64encode(
        json.dumps(payload, separators=(",", ":")).encode("ascii")
    ).decode("ascii")
    program = (HERE / "remote_import_validate.py").read_text(encoding="utf-8")
    program = program.replace("__PAYLOAD_JSON_B64__", encoded)
    output = StringIO()
    with redirect_stdout(output):
        exec(compile(program, "remote_import_validate.py", "exec"), {})
    if output.getvalue().strip() != (
        "REMOTE_CFS_DIRECT_OWNER_IMPORT_OK files=5 stock_entries=19"
    ):
        raise AssertionError("remote_import_validator_invalid")


def verify():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if manifest["status"] != "installed_validated_disabled":
        raise AssertionError("manifest_status_invalid")
    if contract["status"] != "INSTALLED_VALIDATED_DISABLED_ZERO_CFS_FRAME":
        raise AssertionError("contract_status_invalid")
    if contract["authority"]["printer_connection"] is not False:
        raise AssertionError("printer_connection_authority_open")
    if contract["authority"]["deployment_authorized"] is not False:
        raise AssertionError("deployment_authority_open")
    if contract["live_qualification"] != {
        "capture_id": "20260831-123137-g4-k1-control-cfs-direct-owner-install-disabled-v1",
        "deployment_completed": True,
        "embedded_validation": True,
        "independent_validation_count": 2,
        "printer_connection_used": True,
        "remote_write_used": True,
        "klipper_restart_count": 1,
        "mesh_restore": "k1_p001_t055_r001_n11x11",
        "heater_command": False,
        "axis_motion": False,
        "filament_command": False,
        "cfs_frame": False,
        "first_attempt_rollback_exact": True,
        "evidence_map": "packages/k1-control-v1/cfs-direct-owner-install-disabled-v1/evidence-map.json",
    }:
        raise AssertionError("live_qualification_invalid")
    if contract["installed_configuration"] != {
        "section": "k1_control_cfs_direct_owner",
        "enabled": False,
        "transport_bound": False,
        "stock_commands_replaced": False,
        "direct_effect_entries_refuse_before_argument_parsing": True,
        "disabled_selftest_has_no_serial_frame": True,
    }:
        raise AssertionError("disabled_contract_invalid")

    for item in manifest["files"] + manifest["support_files"]:
        path = ROOT / item["source"]
        if digest(path) != item["sha256"]:
            raise AssertionError("manifest_hash_mismatch:%s" % item["source"])
    evidence_map = HERE / "evidence-map.json"
    if digest(evidence_map) != manifest["evidence_map"]["sha256"]:
        raise AssertionError("evidence_map_hash_mismatch")
    if len(manifest["files"]) != 6:
        raise AssertionError("payload_file_count_invalid")
    if any(item["before"] != "absent" for item in manifest["files"]):
        raise AssertionError("payload_before_state_invalid")
    if manifest["planned_effects"]["cfs_frame"] is not False:
        raise AssertionError("deployment_CFS_effect_open")
    if manifest["planned_effects"]["stock_command_replacement_while_disabled"] is not False:
        raise AssertionError("disabled_stock_replacement_open")

    config = (
        HERE / "k1-control-cfs-direct-owner-disabled-v1.cfg"
    ).read_text(encoding="utf-8")
    if config.count("enabled: false") != 1 or "enabled: true" in config:
        raise AssertionError("disabled_config_invalid")

    python_files = [
        HERE / "k1_control_cfs_direct_owner.py",
        HERE / "payload_init.py",
        HERE / "remote_import_validate.py",
        HERE / "remote_validate_disabled.py",
        HERE / "run_scenarios.py",
        OFFLINE / "protocol.py",
        OFFLINE / "owner.py",
        OFFLINE / "runtime_adapter.py",
    ]
    for path in python_files:
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
            feature_version=(3, 8),
        )

    component = (HERE / "k1_control_cfs_direct_owner.py").read_text(
        encoding="utf-8"
    )
    for command in (
        "KCTRL_CFS_DIRECT_RECONCILE",
        "KCTRL_CFS_DIRECT_LOAD",
        "KCTRL_CFS_DIRECT_UNLOAD",
        "KCTRL_CFS_DIRECT_DISABLED_SELFTEST",
    ):
        if command not in component:
            raise AssertionError("direct_command_missing:%s" % command)
    for forbidden in ("M104", "M109", "G28", "BED_MESH_CALIBRATE"):
        if forbidden in component:
            raise AssertionError("hidden_command_present:%s" % forbidden)
    if component.count("G1 E-20 F8400") != 1 or component.count("M400") != 1:
        raise AssertionError("tip_pull_sequence_invalid")
    prepare_effect = component[
        component.index("def _prepare_effect") : component.index(
            "def _ensure_runtime"
        )
    ]
    if prepare_effect.index("self._require_enabled()") > prepare_effect.index(
        "self._ensure_runtime()"
    ):
        raise AssertionError("disabled_guard_order_invalid")

    deployer = ROOT / "scripts/deploy-k1-control-cfs-direct-owner-install-disabled-v1.ps1"
    deployer_text = deployer.read_text(encoding="utf-8")
    for token in (
        "Assert-Preflight",
        "Invoke-ExactRollback",
        "Wait-KlipperTransition",
        "REMOTE_CFS_DIRECT_OWNER_DISABLED_VALIDATE_OK",
        "$Snapshot.runtime.accepted_z_offset",
        "& scp.exe '-O' @SshOptions",
        "enabled=false",
        "aucun effet filament",
    ):
        if token not in deployer_text:
            raise AssertionError("deployer_guard_missing:%s" % token)
    if "$Snapshot.runtime.accepted_z_offset_mm" in deployer_text:
        raise AssertionError("deployer_uses_nonexistent_z_field")

    verify_remote_import_validator(manifest)
    scenarios = load(
        "cfs_direct_owner_install_disabled_scenarios",
        HERE / "run_scenarios.py",
    )
    results = scenarios.run()
    if len(results) != 16 or any(item["status"] != "OK" for item in results):
        raise AssertionError("offline_scenarios_invalid")

    return {
        "status": "OK",
        "offline_scenarios": len(results),
        "payload_files": len(manifest["files"]),
        "installed_enabled": False,
        "printer_connection": False,
        "deployment_authorized": False,
        "direct_owner_installed": True,
        "cfs_frame": False,
    }


if __name__ == "__main__":
    result = verify()
    print(
        "VERIFY_CFS_DIRECT_OWNER_INSTALL_DISABLED_V1_OK %d/%d"
        % (result["offline_scenarios"], result["offline_scenarios"])
    )
