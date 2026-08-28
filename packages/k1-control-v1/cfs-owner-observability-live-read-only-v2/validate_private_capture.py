#!/usr/bin/env python3
"""Validate the V2 read-only capture and project it through the pure adapter."""

from __future__ import annotations

import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence, Set


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
OFFLINE_PACKAGE = PACKAGE.parent / "cfs-owner-observability-adapter-offline-v2"
GUARD_PACKAGE = PACKAGE.parent / "cfs-owner-exclusion-guard-offline-v1"
CONTRACT = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
OFFLINE_CONTRACT = json.loads((OFFLINE_PACKAGE / "contract.json").read_text(encoding="utf-8"))
GUARD_CONTRACT = json.loads((GUARD_PACKAGE / "contract.json").read_text(encoding="utf-8"))
TERMINAL_MARKER = "CFS_OWNER_OBSERVABILITY_LIVE_READ_ONLY_V2_CAPTURE_OK"
CAPTURE_FIELDS = {
    "schema", "mission", "authority", "capture_mode", "identity_values_exported",
    "identity_fields_stripped", "rpc_methods", "state_read_count", "observation_window_s",
    "observer_connection_id", "reported_cfs_transition_count", "reported_cfs_transitions",
    "observations", "configuration_hashes_before", "configuration_hashes_after", "effects",
}


def _load_adapter():
    spec = spec_from_file_location("cfs_owner_observability_live_adapter_v2", OFFLINE_PACKAGE / "adapter_v2.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("adapter_import_failed")
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


adapter = _load_adapter()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("%s_invalid" % label)
    return value


def _exact_fields(value: Mapping[str, Any], expected: Set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError("%s_fields_invalid" % label)


def load_capture(path: Path) -> Mapping[str, Any]:
    lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    if len(lines) != 2 or lines[1] != TERMINAL_MARKER:
        raise ValueError("capture_terminal_invalid")
    return _mapping(json.loads(lines[0]), "capture")


def verify_payload(raw_capture: Mapping[str, Any]) -> Mapping[str, Any]:
    capture = _mapping(raw_capture, "capture")
    _exact_fields(capture, CAPTURE_FIELDS, "capture")
    if capture["schema"] != 2 or capture["mission"] != CONTRACT["mission"]:
        raise ValueError("capture_identity_invalid")
    if capture["authority"] != "strict_read_only":
        raise ValueError("capture_authority_invalid")
    if capture["capture_mode"] != "single_ssh_persistent_moonraker_websocket_subscription":
        raise ValueError("capture_mode_invalid")
    if capture["identity_values_exported"] is not False:
        raise ValueError("identity_values_exported")
    if capture["identity_fields_stripped"] != ["sn", "uuid"]:
        raise ValueError("identity_strip_contract_invalid")
    if capture["rpc_methods"] != CONTRACT["capture"]["rpc_methods"]:
        raise ValueError("rpc_surface_invalid")
    if capture["state_read_count"] != 2:
        raise ValueError("state_read_count_invalid")
    if capture["observation_window_s"] != CONTRACT["capture"]["observation_window_s"]:
        raise ValueError("observation_window_invalid")
    if capture["reported_cfs_transition_count"] != 0 or capture["reported_cfs_transitions"] != []:
        raise ValueError("cfs_transition_observed")
    effects = _mapping(capture["effects"], "effects")
    if not effects or not all(value is False for value in effects.values()):
        raise ValueError("effect_boundary_invalid")
    before = _mapping(capture["configuration_hashes_before"], "hashes_before")
    after = _mapping(capture["configuration_hashes_after"], "hashes_after")
    if before != after or len(before) != 3 or any(not isinstance(value, str) for value in before.values()):
        raise ValueError("configuration_hashes_changed_or_incomplete")
    observations = capture["observations"]
    if not isinstance(observations, list) or len(observations) != 2:
        raise ValueError("observation_count_invalid")
    if any(item.get("observer_connection_id") != capture["observer_connection_id"] for item in observations):
        raise ValueError("observer_connection_id_mismatch")
    try:
        projection = adapter.adapt_observation_pair(OFFLINE_CONTRACT, GUARD_CONTRACT, observations)
    except adapter.ObservationError as exc:
        raise ValueError("offline_adapter_rejected:%s:%s" % (exc.code, exc.detail))
    snapshot = projection["guard_snapshot"]
    return {
        "status": "OK",
        "verdict": "CLOSED_READ_ONLY_OBSERVABILITY_V2_QUALIFIED_EFFECTS_CLOSED",
        "live_observations": 2,
        "observer_connection_id_observed": True,
        "observer_connection_stable": True,
        "reported_cfs_transition_count": 0,
        "accepted_z_offset_mm": projection["accepted_z_offset_mm"],
        "accepted_z_value_stable": projection["accepted_z_value_stable"],
        "accepted_z_store_integrity_qualified": projection["accepted_z_store_integrity_qualified"],
        "connection_epoch": projection["connection_epoch"],
        "stock_auto_refill": snapshot["stock_auto_refill"],
        "stock_cfs_print_enable": snapshot["stock_cfs_print_enable"],
        "connected_units": snapshot["connected_units"],
        "engaged_routes": snapshot["engaged_routes"],
        "active_mesh_profile": snapshot["protected"]["mesh_profile"],
        "configuration_hashes_unchanged": True,
        "offline_adapter_accepted": True,
        "silent_same_state_driver_reconnect_detectable": False,
        "guard_imported_or_called": False,
        "gcode_sent": False,
        "remote_write": False,
        "physical_action": False,
    }


def verify_capture(path: Path) -> Mapping[str, Any]:
    return verify_payload(load_capture(path))


def verify_evidence(repo_root: Path = ROOT) -> Mapping[str, Any]:
    evidence = json.loads((PACKAGE / "evidence-map.json").read_text(encoding="utf-8"))
    private = evidence["private_source"]
    path = repo_root / private["path"]
    if sha256_file(path) != private["sha256"]:
        raise ValueError("private_capture_hash_mismatch")
    result = verify_capture(path)
    if result != evidence["safe_result"]:
        raise ValueError("safe_result_mismatch")
    return result


def main(arguments: Sequence[str]) -> int:
    result = verify_capture(Path(arguments[0])) if arguments else verify_evidence()
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    print("VALIDATE_CFS_OWNER_OBSERVABILITY_LIVE_READ_ONLY_V2_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
