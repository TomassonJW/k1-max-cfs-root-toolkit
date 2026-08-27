#!/usr/bin/env python3
"""Validate the sanitized Goal 2 capture and publish only bounded facts."""

from __future__ import annotations

import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
from typing import Any, Dict, Mapping


PACKAGE = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE.parents[2]
CAPTURE_MARKER = "K1_READ_ONLY_QUALIFICATION_CAPTURE_V1_OK"


def _load_connector():
    path = PACKAGE / "read_only_connector.py"
    spec = spec_from_file_location("k1_read_only_connector_v1", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("connector_import_failed")
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


connector = _load_connector()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("object_required:%s" % path)
    return value


def load_capture(path: Path) -> Mapping[str, Any]:
    lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    if len(lines) != 2 or lines[1] != CAPTURE_MARKER:
        raise ValueError("capture_marker_or_line_count_invalid")
    payload = json.loads(lines[0])
    return _mapping(payload, "capture")


def _validate_server(capture: Mapping[str, Any]) -> None:
    server = _mapping(capture.get("server"), "capture.server")
    if set(server) != {"first", "second"}:
        raise ValueError("server_schema_drift")
    for label in ("first", "second"):
        state = _mapping(server[label], "capture.server.%s" % label)
        if state.get("klippy_state") != "ready":
            raise ValueError("klippy_not_ready:%s" % label)
        if state.get("failed_components") not in ([], None):
            raise ValueError("moonraker_failed_components:%s" % label)
        if state.get("warnings") not in ([], None):
            raise ValueError("moonraker_warnings:%s" % label)


def _validate_timings(capture: Mapping[str, Any], contract: Mapping[str, Any]) -> float:
    timings = _mapping(capture.get("timings_ms"), "capture.timings_ms")
    expected_counts = {"server_info": 2, "objects_list": 1, "objects_query": 2}
    maximum = 0.0
    deadline_ms = float(contract["capture"]["per_request_timeout_s"]) * 1000.0
    for key, expected_count in expected_counts.items():
        values = timings.get(key)
        if not isinstance(values, list) or len(values) != expected_count:
            raise ValueError("timing_count_invalid:%s" % key)
        for value in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("timing_invalid:%s" % key)
            number = float(value)
            if number <= 0.0 or number > deadline_ms:
                raise ValueError("timing_deadline_failed:%s" % key)
            maximum = max(maximum, number)
    return maximum


def _validate_hashes(capture: Mapping[str, Any], contract: Mapping[str, Any]) -> None:
    before = _mapping(capture.get("hashes_before"), "capture.hashes_before")
    after = _mapping(capture.get("hashes_after"), "capture.hashes_after")
    expected = _mapping(contract.get("expected_hashes"), "contract.expected_hashes")
    if dict(before) != dict(after):
        raise ValueError("remote_hashes_changed_during_capture")
    if dict(before) != dict(expected):
        raise ValueError("remote_hashes_drifted_from_reviewed_baseline")


def _validate_no_effects(capture: Mapping[str, Any]) -> None:
    if capture.get("authority") != "strict_read_only":
        raise ValueError("authority_invalid")
    if capture.get("http_methods") != ["GET"]:
        raise ValueError("http_method_not_read_only")
    if capture.get("identity_values_exported") is not False:
        raise ValueError("identity_values_exported")
    effects = _mapping(capture.get("effects"), "capture.effects")
    expected = {
        "gcode_sent": False,
        "guard_called": False,
        "physical_action": False,
        "remote_files_written": False,
        "service_action": False,
    }
    if dict(effects) != expected:
        raise ValueError("effect_boundary_broken")


def analyze_capture(path: Path, contract: Mapping[str, Any]) -> Dict[str, Any]:
    capture = load_capture(path)
    if capture.get("mission") != contract.get("contract_id"):
        raise ValueError("mission_mismatch")
    if capture.get("capture_mode") != "remote_sanitization_before_local_processing":
        raise ValueError("sanitization_boundary_invalid")
    if float(capture.get("query_timeout_s")) != float(
        contract["capture"]["per_request_timeout_s"]
    ):
        raise ValueError("query_timeout_drift")
    if float(capture.get("query_interval_s")) != float(
        contract["capture"]["query_interval_s"]
    ):
        raise ValueError("query_interval_drift")

    _validate_no_effects(capture)
    _validate_server(capture)
    maximum_timing = _validate_timings(capture, contract)
    _validate_hashes(capture, contract)

    required_objects = _mapping(
        capture.get("required_objects_present"), "capture.required_objects_present"
    )
    if not required_objects or any(value is not True for value in required_objects.values()):
        raise ValueError("required_live_object_missing")
    if capture.get("response_schema_stable") is not True:
        raise ValueError("response_schema_changed_between_reads")
    schema_hash = canonical_sha256(capture.get("response_schema"))
    if schema_hash != contract["response_schema"]["canonical_sha256"]:
        raise ValueError("response_schema_drift")

    if capture.get("moonraker_sections") != contract["required_moonraker_sections"]:
        raise ValueError("moonraker_integration_sections_drift")

    snapshots = capture.get("snapshots")
    if not isinstance(snapshots, list) or len(snapshots) != 2:
        raise ValueError("live_snapshot_count_invalid")
    first = connector.adapt_snapshot(snapshots[0])
    second = connector.adapt_snapshot(snapshots[1])
    if connector.control_projection(snapshots[0]) != connector.control_projection(
        snapshots[1]
    ):
        raise ValueError("control_state_not_stable")
    if float(snapshots[1]["eventtime"]) <= float(snapshots[0]["eventtime"]):
        raise ValueError("eventtime_not_advancing")
    mapping_valid = connector.mapping_cache_valid(
        snapshots[0], snapshots[1], connection_epoch_changed=False
    )
    if not mapping_valid:
        raise ValueError("mapping_changed_between_reads")
    if first != second:
        raise ValueError("adapted_snapshot_not_stable")

    store = _mapping(snapshots[1].get("store"), "snapshot.store")
    if store.get("integrity") != "ok":
        raise ValueError("z_store_integrity_invalid")
    if any(
        store.get(key) is not None
        for key in (
            "ready",
            "accepted_z_valid",
            "accepted_z_offset",
            "session_active",
            "low_moves_armed",
        )
    ):
        raise ValueError("z_store_shape_drift")
    toolhead = _mapping(snapshots[1].get("toolhead"), "snapshot.toolhead")
    if toolhead.get("homed_axes") not in ("", []):
        raise ValueError("axes_not_released")
    if toolhead.get("position") != snapshots[0]["toolhead"]["position"]:
        raise ValueError("toolhead_position_changed")
    if snapshots[1]["gcode_move"].get("homing_origin") != snapshots[0][
        "gcode_move"
    ].get("homing_origin"):
        raise ValueError("homing_origin_changed")

    expected_live = contract["expected_live_state"]
    comparisons = {
        "print_state": first["print_state"],
        "connected_cfs_units": first["connected_cfs_units"],
        "engaged_routes": first["engaged_routes"],
        "filament_state": first["filament_state"],
        "extruder_target_c": first["extruder_target_c"],
        "bed_target_c": first["bed_target_c"],
        "accepted_z_valid": first["accepted_z_valid"],
        "accepted_z_offset_mm": first["accepted_z_offset_mm"],
        "low_moves_armed": first["low_moves_armed"],
        "active_mesh_profile": first["active_mesh_profile"],
        "active_mesh_sha256": first["active_mesh_sha256"],
        "safe_idle": first["safe_idle"],
        "offline_contract_ready": first["offline_contract_ready"],
    }
    for key, value in comparisons.items():
        if value != expected_live[key]:
            raise ValueError("live_fact_drift:%s" % key)
    if first["robust_mesh_sha256"] != expected_live["required_mesh_sha256"]:
        raise ValueError("robust_profile_matrix_drift")
    if first["robust_mesh_active"] is not False:
        raise ValueError("mesh_drift_expected_but_not_observed")

    return {
        "status": "CLOSED_READ_ONLY_BLOCKED_MESH_DRIFT",
        "live_snapshots": 2,
        "schema_stable": True,
        "configuration_hashes_unchanged": True,
        "query_deadline_qualified": True,
        "maximum_observed_query_ms": maximum_timing,
        "connected_cfs_units": first["connected_cfs_units"],
        "engaged_routes": first["engaged_routes"],
        "filament_state": first["filament_state"],
        "accepted_z_offset_mm": first["accepted_z_offset_mm"],
        "active_mesh_profile": first["active_mesh_profile"],
        "required_mesh_profile": expected_live["required_mesh_profile"],
        "active_mesh_matches_required": False,
        "offline_contract_ready": False,
        "mapping_cache_valid_between_reads": mapping_valid,
        "same_state_reconnect_between_polls_detectable": False,
        "gcode_sent": False,
        "remote_files_written": False,
        "service_action": False,
        "physical_action": False,
        "deployment_candidate": False,
    }


def verify_evidence(repo_root: Path = REPO_ROOT) -> Mapping[str, Any]:
    contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
    evidence = json.loads((PACKAGE / "evidence-map.json").read_text(encoding="utf-8"))
    source = evidence["private_source"]
    capture_path = repo_root / source["path"]
    if not capture_path.is_file():
        raise FileNotFoundError("private_capture_missing")
    if sha256_file(capture_path) != source["sha256"]:
        raise ValueError("private_capture_hash_mismatch")
    result = analyze_capture(capture_path, contract)
    if result != evidence["safe_result"]:
        raise ValueError("safe_result_mismatch")
    return result


def main() -> int:
    print(json.dumps(verify_evidence(), indent=2, sort_keys=True, ensure_ascii=False))
    print("VALIDATE_GOAL_P4_K1_READ_ONLY_QUALIFICATION_V1_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
