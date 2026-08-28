#!/usr/bin/env python3
"""Pure V2 projection from continuous Moonraker observations to the V1 guard."""

from __future__ import annotations

from copy import deepcopy
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Dict, Iterable, Mapping, Sequence


PACKAGE = Path(__file__).resolve().parent
OFFLINE_GUARD_PACKAGE = PACKAGE.parent / "cfs-owner-exclusion-guard-offline-v1"
GUARD_ADAPTER_PATH = OFFLINE_GUARD_PACKAGE / "adapter.py"


class ObservationError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


def _load_guard_adapter():
    spec = spec_from_file_location("cfs_owner_observability_guard_adapter", GUARD_ADAPTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("guard_adapter_import_failed")
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


guard_adapter = _load_guard_adapter()

OBSERVATION_FIELDS = {
    "schema", "sample_seq", "observer_connection_id", "observer_connection_live",
    "observer_eventtime", "cfs_transition_seq", "cfs_transition_digest",
    "mapping_revision", "printer_state", "connected_units", "active_command",
    "stock_auto_refill", "stock_cfs_print_enable", "engaged_routes", "protected",
}
PROTECTED_FIELDS = {
    "mesh_profile", "runtime_accepted_z_valid", "runtime_accepted_z_offset_mm",
    "store_ready", "store_integrity", "store_accepted_z_valid",
    "store_accepted_z_offset_mm", "homed_axes", "nozzle_target_c", "bed_target_c",
}
SHA256_MARKER = re.compile(r"^[a-z][a-z0-9-]{0,31}:[0-9a-f]{64}$")


def _exact_fields(value: Mapping[str, Any], expected: Iterable[str], label: str) -> None:
    actual = set(value)
    wanted = set(expected)
    if actual != wanted:
        raise ObservationError(
            "%s_fields_invalid" % label,
            "missing=%s extra=%s" % (sorted(wanted - actual), sorted(actual - wanted)),
        )


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ObservationError("%s_invalid" % label)
    return value


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ObservationError("%s_invalid" % label)
    return value


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ObservationError("%s_invalid" % label)
    result = float(value)
    if not math.isfinite(result):
        raise ObservationError("%s_invalid" % label)
    return result


def _text(value: Any, label: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value) or len(value) > 128:
        raise ObservationError("%s_invalid" % label)
    if any(ord(character) < 32 for character in value):
        raise ObservationError("%s_invalid" % label)
    return value


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_single(contract: Mapping[str, Any], raw: Mapping[str, Any]) -> Dict[str, Any]:
    observation = _mapping(raw, "observation")
    _exact_fields(observation, OBSERVATION_FIELDS, "observation")
    if observation["schema"] != 2:
        raise ObservationError("observation_schema_invalid")
    protected = _mapping(observation["protected"], "protected")
    _exact_fields(protected, PROTECTED_FIELDS, "protected")
    result = deepcopy(dict(observation))
    result["sample_seq"] = _integer(observation["sample_seq"], "sample_seq", 1)
    result["observer_connection_id"] = _integer(
        observation["observer_connection_id"], "observer_connection_id", 1
    )
    if observation["observer_connection_live"] is not True:
        raise ObservationError("observer_connection_not_live")
    result["observer_eventtime"] = _finite(observation["observer_eventtime"], "observer_eventtime")
    result["cfs_transition_seq"] = _integer(observation["cfs_transition_seq"], "cfs_transition_seq")
    transition_digest = _text(observation["cfs_transition_digest"], "cfs_transition_digest")
    if not SHA256_MARKER.fullmatch(transition_digest):
        raise ObservationError("cfs_transition_digest_invalid")
    result["cfs_transition_digest"] = transition_digest
    result["mapping_revision"] = _text(observation["mapping_revision"], "mapping_revision")
    return result


def _accepted_z(contract: Mapping[str, Any], protected: Mapping[str, Any]) -> Dict[str, Any]:
    if protected["runtime_accepted_z_valid"] != 1:
        raise ObservationError("runtime_accepted_z_invalid")
    if protected["store_integrity"] != "ok":
        raise ObservationError("accepted_z_store_integrity_invalid")
    if any(protected[field] is not None for field in (
        "store_ready", "store_accepted_z_valid", "store_accepted_z_offset_mm"
    )):
        raise ObservationError("accepted_z_store_shape_invalid")
    runtime_z = _finite(protected["runtime_accepted_z_offset_mm"], "runtime_accepted_z_offset_mm")
    spec = contract["observation"]
    if not spec["accepted_z_min_mm"] <= runtime_z <= spec["accepted_z_max_mm"]:
        raise ObservationError("accepted_z_out_of_range")
    material = {
        "runtime_valid": 1,
        "runtime_offset_mm": runtime_z,
        "store_integrity": "ok",
        "store_runtime_shape": "null",
    }
    return {
        "value_mm": runtime_z,
        "revision": "accepted-z:" + _canonical_hash(material),
    }


def adapt_observation_pair(
    contract: Mapping[str, Any],
    guard_contract: Mapping[str, Any],
    reads: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    if contract.get("contract_id") != "cfs-owner-observability-adapter-offline-v2":
        raise ObservationError("contract_invalid")
    if contract.get("authority") != "offline_only":
        raise ObservationError("contract_authority_invalid")
    if not isinstance(reads, (list, tuple)) or len(reads) != contract["observation"]["stable_reads"]:
        raise ObservationError("observation_pair_count_invalid")
    first = _validate_single(contract, reads[0])
    second = _validate_single(contract, reads[1])
    if second["sample_seq"] <= first["sample_seq"]:
        raise ObservationError("sample_sequence_not_increasing")
    if second["observer_connection_id"] != first["observer_connection_id"]:
        raise ObservationError("observer_connection_changed")
    interval = second["observer_eventtime"] - first["observer_eventtime"]
    if interval <= 0:
        raise ObservationError("observer_eventtime_not_increasing")
    if interval > contract["observation"]["maximum_interval_s"]:
        raise ObservationError("observation_interval_too_long")
    if second["cfs_transition_seq"] != first["cfs_transition_seq"]:
        raise ObservationError("cfs_connection_transition_observed")
    if second["cfs_transition_digest"] != first["cfs_transition_digest"]:
        raise ObservationError("connection_witness_inconsistent")

    guard_reads = []
    accepted_values = []
    connection_epoch = "moonraker-ws-%d:cfs-%d:%s" % (
        first["observer_connection_id"],
        first["cfs_transition_seq"],
        first["cfs_transition_digest"].split(":", 1)[1],
    )
    for observation in (first, second):
        protected = observation["protected"]
        accepted = _accepted_z(contract, protected)
        accepted_values.append(accepted["value_mm"])
        guard_reads.append({
            "schema": 1,
            "sample_seq": observation["sample_seq"],
            "mapping_revision": observation["mapping_revision"],
            "connection_epoch": connection_epoch,
            "printer_state": observation["printer_state"],
            "connected_units": observation["connected_units"],
            "active_command": observation["active_command"],
            "stock_auto_refill": observation["stock_auto_refill"],
            "stock_cfs_print_enable": observation["stock_cfs_print_enable"],
            "engaged_routes": observation["engaged_routes"],
            "protected": {
                "mesh_profile": protected["mesh_profile"],
                "accepted_z_revision": accepted["revision"],
                "effective_z_offset_mm": accepted["value_mm"],
                "homed_axes": protected["homed_axes"],
                "nozzle_target_c": protected["nozzle_target_c"],
                "bed_target_c": protected["bed_target_c"],
            },
        })
    try:
        stable = guard_adapter.adapt_stable_pair(guard_contract, guard_reads)
    except guard_adapter.AdapterError as exc:
        raise ObservationError("guard_adapter_rejected", exc.code)
    return {
        "guard_snapshot": stable,
        "guard_reads": guard_reads,
        "connection_epoch": connection_epoch,
        "observer_connection_id": first["observer_connection_id"],
        "cfs_transition_seq": first["cfs_transition_seq"],
        "accepted_z_offset_mm": accepted_values[0],
        "accepted_z_value_stable": accepted_values[0] == accepted_values[1],
        "accepted_z_store_integrity_qualified": True,
        "reported_transition_free": True,
    }
