#!/usr/bin/env python3
"""Validate the remotely sanitized capture without importing the guard."""

from __future__ import annotations

from copy import deepcopy
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, Mapping, Sequence, Set


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
OFFLINE_PACKAGE = PACKAGE.parent / "cfs-owner-exclusion-guard-offline-v1"
OFFLINE_CONTRACT_PATH = OFFLINE_PACKAGE / "contract.json"
OFFLINE_ADAPTER_PATH = OFFLINE_PACKAGE / "adapter.py"
TERMINAL_MARKER = "CFS_OWNER_EXCLUSION_GUARD_LIVE_READ_ONLY_V1_CAPTURE_OK"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _load_adapter():
    spec = spec_from_file_location("cfs_owner_exclusion_guard_live_adapter", OFFLINE_ADAPTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("adapter_import_failed")
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


adapter = _load_adapter()
OFFLINE_CONTRACT = json.loads(OFFLINE_CONTRACT_PATH.read_text(encoding="utf-8"))
SNAPSHOT_KEYS = set(OFFLINE_CONTRACT["snapshot"]["required_fields"])
PROTECTED_KEYS = set(OFFLINE_CONTRACT["snapshot"]["protected_fields"])
CAPTURE_KEYS = {
    "schema", "mission", "authority", "capture_mode", "identity_values_exported",
    "identity_fields_stripped", "http_methods", "query_count", "query_timeout_s",
    "connection_epoch_observable", "connection_epoch_source", "snapshots",
    "configuration_hashes_before", "configuration_hashes_after", "effects"
}


def _exact_keys(value: Mapping[str, Any], expected: Set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError("%s_keys_invalid:missing=%s:extra=%s" % (
            label, sorted(expected - actual), sorted(actual - expected)
        ))


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("%s_invalid" % label)
    return value


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("%s_invalid" % label)
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("%s_invalid" % label)
    return result


def load_capture(path: Path) -> Mapping[str, Any]:
    lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    if len(lines) != 2 or lines[1] != TERMINAL_MARKER:
        raise ValueError("capture_terminal_invalid")
    return _mapping(json.loads(lines[0]), "capture")


def _stable_except_sequence(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    left = deepcopy(dict(first))
    right = deepcopy(dict(second))
    left.pop("sample_seq", None)
    right.pop("sample_seq", None)
    return left == right


def verify_payload(raw_capture: Mapping[str, Any]) -> Mapping[str, Any]:
    capture = _mapping(raw_capture, "capture")
    _exact_keys(capture, CAPTURE_KEYS, "capture")
    if capture["schema"] != 1 or capture["authority"] != "strict_read_only":
        raise ValueError("capture_authority_invalid")
    if capture["http_methods"] != ["GET"] or capture["query_count"] != 2:
        raise ValueError("capture_query_contract_invalid")
    if _finite(capture["query_timeout_s"], "query_timeout_s") > 5.0:
        raise ValueError("query_timeout_too_large")
    if capture["identity_values_exported"] is not False:
        raise ValueError("identity_values_exported")
    if capture["identity_fields_stripped"] != ["sn", "uuid"]:
        raise ValueError("identity_strip_contract_invalid")
    if capture["connection_epoch_observable"] is not False:
        raise ValueError("unexpected_connection_epoch_claim")
    if capture["connection_epoch_source"] != "unavailable_no_notification_epoch":
        raise ValueError("connection_epoch_source_invalid")
    effects = _mapping(capture["effects"], "effects")
    if not effects or not all(value is False for value in effects.values()):
        raise ValueError("effect_boundary_invalid")
    before = _mapping(capture["configuration_hashes_before"], "hashes_before")
    after = _mapping(capture["configuration_hashes_after"], "hashes_after")
    if before != after or len(before) != 3 or any(not isinstance(value, str) for value in before.values()):
        raise ValueError("configuration_hashes_changed_or_incomplete")

    snapshots = capture["snapshots"]
    if not isinstance(snapshots, list) or len(snapshots) != 2:
        raise ValueError("snapshot_count_invalid")
    for index, raw in enumerate(snapshots, 1):
        snapshot = _mapping(raw, "snapshot_%d" % index)
        _exact_keys(snapshot, SNAPSHOT_KEYS, "snapshot_%d" % index)
        protected = _mapping(snapshot["protected"], "snapshot_%d.protected" % index)
        _exact_keys(protected, PROTECTED_KEYS, "snapshot_%d.protected" % index)
        if snapshot["sample_seq"] != index:
            raise ValueError("sample_sequence_invalid")
        if snapshot["connection_epoch"] is not None:
            raise ValueError("invented_connection_epoch")
    if not _stable_except_sequence(snapshots[0], snapshots[1]):
        raise ValueError("live_state_not_stable")

    adapter_error = None
    try:
        adapter.adapt_stable_pair(OFFLINE_CONTRACT, snapshots)
    except adapter.AdapterError as exc:
        adapter_error = exc.code
    if adapter_error != "connection_epoch_invalid":
        raise ValueError("adapter_did_not_fail_on_missing_connection_epoch:%s" % adapter_error)

    first = snapshots[0]
    safe_idle = (
        first["printer_state"] == "standby"
        and first["connected_units"] == ["T1", "T2"]
        and first["active_command"] == ""
        and len(first["engaged_routes"]) <= 1
        and first["protected"]["nozzle_target_c"] == 0
        and first["protected"]["bed_target_c"] == 0
    )
    return {
        "status": "OK",
        "verdict": "CLOSED_READ_ONLY_BLOCKED_CONNECTION_EPOCH_AND_EFFECTIVE_Z_SOURCE",
        "live_snapshots": 2,
        "live_state_stable": True,
        "safe_idle_observed": safe_idle,
        "connected_units": first["connected_units"],
        "engaged_routes": first["engaged_routes"],
        "stock_auto_refill": first["stock_auto_refill"],
        "stock_cfs_print_enable": first["stock_cfs_print_enable"],
        "active_mesh_profile": first["protected"]["mesh_profile"],
        "observed_homing_origin_z_mm": first["protected"]["effective_z_offset_mm"],
        "accepted_z_revision_stable": True,
        "accepted_z_value_observable": False,
        "effective_z_source_qualified": False,
        "configuration_hashes_unchanged": True,
        "adapter_called": True,
        "adapter_blockers": [adapter_error, "effective_z_source_unqualified"],
        "guard_adapter_ready": False,
        "connection_epoch_observable": False,
        "same_state_reconnect_between_queries_detectable": False,
        "guard_imported_or_called": False,
        "gcode_sent": False,
        "remote_write": False,
        "physical_action": False,
    }


def verify_capture(path: Path) -> Mapping[str, Any]:
    return verify_payload(load_capture(path))


def verify_evidence(repo_root: Path = ROOT) -> Mapping[str, Any]:
    evidence_path = PACKAGE / "evidence-map.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    private = evidence["private_source"]
    capture_path = repo_root / private["path"]
    if sha256_file(capture_path) != private["sha256"]:
        raise ValueError("private_capture_hash_mismatch")
    result = verify_capture(capture_path)
    if result != evidence["safe_result"]:
        raise ValueError("safe_result_mismatch")
    return result


def main(arguments: Sequence[str]) -> int:
    result = verify_capture(Path(arguments[0])) if arguments else verify_evidence()
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    print("VALIDATE_CFS_OWNER_EXCLUSION_GUARD_LIVE_READ_ONLY_V1_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
