#!/usr/bin/env python3
"""Strict pure adapter for synthetic owner-boundary snapshots."""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Dict, Iterable, Mapping, Sequence, Set


class AdapterError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


def _exact_fields(value: Mapping[str, Any], required: Iterable[str], label: str) -> None:
    expected = set(required)
    actual = set(value.keys())
    if expected - actual:
        raise AdapterError("%s_incomplete" % label)
    if actual - expected:
        raise AdapterError("%s_unknown_field" % label)


def _integer(value: Any, field: str, allowed: Sequence[int]) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in allowed:
        raise AdapterError("%s_invalid" % field)
    return value


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AdapterError("%s_invalid" % field)
    result = float(value)
    if not math.isfinite(result):
        raise AdapterError("%s_invalid" % field)
    return result


def _text(value: Any, field: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not value and not allow_empty) or len(value) > 128:
        raise AdapterError("%s_invalid" % field)
    if any(ord(character) < 32 for character in value):
        raise AdapterError("%s_invalid" % field)
    return value


def adapt_snapshot(contract: Mapping[str, Any], raw: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise AdapterError("snapshot_invalid")
    spec = contract["snapshot"]
    _exact_fields(raw, spec["required_fields"], "snapshot")
    if raw["schema"] != 1:
        raise AdapterError("snapshot_schema_invalid")
    sample_seq = _integer(raw["sample_seq"], "sample_seq", range(1, 2 ** 31))
    mapping_revision = _text(raw["mapping_revision"], "mapping_revision")
    connection_epoch = _text(raw["connection_epoch"], "connection_epoch")
    if raw["printer_state"] != spec["required_printer_state"]:
        raise AdapterError("printer_not_idle")
    if raw["connected_units"] != spec["required_connected_units"]:
        raise AdapterError("connected_units_invalid")
    if raw["active_command"] != "":
        raise AdapterError("stock_command_active")
    auto_refill = _integer(raw["stock_auto_refill"], "stock_auto_refill", (0, 1))
    print_enable = _integer(raw["stock_cfs_print_enable"], "stock_cfs_print_enable", (0, 1))
    routes = raw["engaged_routes"]
    if not isinstance(routes, list) or any(not isinstance(route, str) for route in routes):
        raise AdapterError("engaged_routes_invalid")
    if len(routes) != len(set(routes)):
        raise AdapterError("engaged_routes_invalid")
    if len(routes) > spec["maximum_engaged_routes"]:
        raise AdapterError("multiple_engaged_routes")
    if any(route not in {"T1A", "T1B", "T1C", "T1D", "T2A", "T2B", "T2C", "T2D"} for route in routes):
        raise AdapterError("engaged_routes_invalid")
    protected = raw["protected"]
    if not isinstance(protected, Mapping):
        raise AdapterError("protected_invalid")
    _exact_fields(protected, spec["protected_fields"], "protected")
    result = deepcopy(dict(raw))
    result["sample_seq"] = sample_seq
    result["mapping_revision"] = mapping_revision
    result["connection_epoch"] = connection_epoch
    result["stock_auto_refill"] = auto_refill
    result["stock_cfs_print_enable"] = print_enable
    result["protected"]["mesh_profile"] = _text(protected["mesh_profile"], "mesh_profile")
    result["protected"]["accepted_z_revision"] = _text(
        protected["accepted_z_revision"], "accepted_z_revision"
    )
    homed_axes = _text(protected["homed_axes"], "homed_axes", allow_empty=True)
    if any(axis not in "xyz" for axis in homed_axes) or len(set(homed_axes)) != len(homed_axes):
        raise AdapterError("homed_axes_invalid")
    result["protected"]["homed_axes"] = homed_axes
    result["protected"]["effective_z_offset_mm"] = _finite(
        protected["effective_z_offset_mm"], "effective_z_offset_mm"
    )
    result["protected"]["nozzle_target_c"] = _finite(protected["nozzle_target_c"], "nozzle_target_c")
    result["protected"]["bed_target_c"] = _finite(protected["bed_target_c"], "bed_target_c")
    if result["protected"]["nozzle_target_c"] != 0 or result["protected"]["bed_target_c"] != 0:
        raise AdapterError("heater_target_not_zero")
    return result


def adapt_stable_pair(contract: Mapping[str, Any], reads: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(reads, (list, tuple)) or len(reads) != contract["snapshot"]["stable_reads"]:
        raise AdapterError("stable_pair_count_invalid")
    first = adapt_snapshot(contract, reads[0])
    second = adapt_snapshot(contract, reads[1])
    if second["sample_seq"] <= first["sample_seq"]:
        raise AdapterError("sample_sequence_not_increasing")
    left = deepcopy(first)
    right = deepcopy(second)
    left.pop("sample_seq")
    right.pop("sample_seq")
    if left != right:
        raise AdapterError("stable_pair_changed")
    return second


def transition_drift(before: Mapping[str, Any], after: Mapping[str, Any]) -> Set[str]:
    ignored = {"sample_seq", "stock_auto_refill"}
    return {key for key in before if key not in ignored and before.get(key) != after.get(key)}


def owner_identity_drift(before: Mapping[str, Any], after: Mapping[str, Any]) -> Set[str]:
    fields = {"mapping_revision", "connection_epoch", "stock_cfs_print_enable"}
    return {field for field in fields if before.get(field) != after.get(field)}
