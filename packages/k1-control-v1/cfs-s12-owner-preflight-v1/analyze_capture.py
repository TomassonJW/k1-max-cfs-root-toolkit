from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CAPTURE_MARKER = "CFS_S12_OWNER_PREFLIGHT_V1_CAPTURE_OK"
IDENTITY_KEYS = {"sn", "uuid"}


class CaptureError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_capture(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if len(lines) != 2 or lines[1].strip() != CAPTURE_MARKER:
        raise CaptureError("capture_marker_or_line_count_invalid")
    value = json.loads(lines[0])
    if not isinstance(value, dict):
        raise CaptureError("capture_root_not_object")
    return value


def _contains_identity_key(value: Any) -> bool:
    if isinstance(value, dict):
        if IDENTITY_KEYS.intersection(value):
            return True
        return any(_contains_identity_key(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_identity_key(item) for item in value)
    return False


def _file_by_path(capture: dict[str, Any], phase: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for value in capture.get(phase, {}).values():
        if isinstance(value, dict) and isinstance(value.get("path"), str):
            result[value["path"]] = value
    return result


def _connected_units(snapshot: dict[str, Any]) -> list[str]:
    box = snapshot.get("box", {})
    connected = []
    for unit_name in ("T1", "T2", "T3", "T4"):
        state = str(box.get(unit_name, {}).get("state", "")).lower()
        if state == "connect":
            connected.append(unit_name)
    return connected


def _effect_boundary_ok(capture: dict[str, Any]) -> bool:
    effects = capture.get("effects")
    return (
        isinstance(effects, dict)
        and effects
        and all(value is False for value in effects.values())
        and capture.get("http_methods") == ["GET"]
        and capture.get("authority") == "strict_read_only"
    )


def analyze(capture: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    registered = set(capture.get("registered_commands", {}))
    binary = capture.get("binary_inventory", {})
    binary_commands = set(binary.get("command_names", []))
    callbacks = binary.get("callback_markers", {})
    arguments = binary.get("argument_tokens", {})

    required_commands = contract["required_command_names"]
    required_callbacks = contract["required_binary_callbacks"]
    command_presence = {
        command: {
            "listed_by_gcode_help": command in registered,
            "name_in_exact_binary": command in binary_commands,
            "registration_note": (
                "gcode_help_only_lists_commands_with_help_text_and_is_not_authoritative_for_this_compiled_module"
            ),
        }
        for command in required_commands
    }
    callback_presence = {
        marker: callbacks.get(marker) is True for marker in required_callbacks
    }

    before = _file_by_path(capture, "files_before")
    after = _file_by_path(capture, "files_after")
    files_unchanged = before == after and bool(before)
    historical_hashes = contract["historical_exact_hashes"]
    historical_matches = {
        path: (
            path in before
            and before[path].get("exists") is True
            and before[path].get("sha256") == expected
        )
        for path, expected in historical_hashes.items()
    }

    signatures = {}
    config_calls = capture.get("config_inventory", {}).get("box_calls", [])
    for command, signature in contract["public_cross_map"]["candidate_signatures"].items():
        observed_argument_names = sorted(
            {
                argument
                for call in config_calls
                if call.get("command") == command
                for argument in call.get("argument_names", [])
            }
        )
        public_arguments = signature["required"] + signature["optional"]
        signatures[command] = {
            "public_signature": signature,
            "listed_by_gcode_help": command in registered,
            "name_in_exact_binary": command in binary_commands,
            "argument_tokens_exist_in_exact_binary": {
                argument: arguments.get(argument) is True
                for argument in public_arguments
            },
            "arguments_seen_in_active_config_calls": observed_argument_names,
            "qualification": "surface_correlated_effect_behavior_not_qualified",
        }

    snapshots = capture.get("snapshots", [])
    snapshots_valid = len(snapshots) == 2 and all(isinstance(item, dict) for item in snapshots)
    first = snapshots[0] if snapshots_valid else {}
    second = snapshots[1] if snapshots_valid else {}
    connected_first = _connected_units(first)
    connected_second = _connected_units(second)
    runtime_box_fields = first.get("box", {}) if snapshots_valid else {}
    same_material_groups = runtime_box_fields.get("same_material_groups", [])
    auto_refill_surface_present = (
        "auto_refill" in runtime_box_fields
        and "enable" in runtime_box_fields
        and isinstance(same_material_groups, list)
        and all(
            command in binary_commands
            for command in (
                "BOX_ENABLE_AUTO_REFILL",
                "BOX_UPDATE_SAME_MATERIAL_LIST",
                "BOX_CHECK_MATERIAL_REFILL",
                "BOX_EXTRUSION_ALL_MATERIALS",
            )
        )
        and callback_presence.get("material_auto_refill") is True
        and callback_presence.get("update_Tnn_map") is True
    )

    identity_boundary_ok = (
        capture.get("identity_values_exported") is False
        and not _contains_identity_key(capture)
    )
    box_object_active = capture.get("required_objects_present", {}).get("box") is True
    command_surface_ok = box_object_active and all(
        item["name_in_exact_binary"] for item in command_presence.values()
    )
    callbacks_ok = all(callback_presence.values())
    server_ready = capture.get("server", {}).get("klippy_state") == "ready"
    schema_stable = capture.get("safe_response_schema_stable") is True
    read_only_boundary_ok = _effect_boundary_ok(capture)
    required_objects_ok = all(capture.get("required_objects_present", {}).values())

    blockers = []
    checks = {
        "read_only_boundary": read_only_boundary_ok,
        "identity_boundary": identity_boundary_ok,
        "files_unchanged": files_unchanged,
        "historical_binary_and_loaders_match": all(historical_matches.values()),
        "server_ready": server_ready,
        "required_objects_present": required_objects_ok,
        "safe_schema_stable": schema_stable,
        "box_object_active": box_object_active,
        "required_command_names_in_exact_loaded_binary": command_surface_ok,
        "required_callbacks_in_binary": callbacks_ok,
        "two_classic_cfs_units_connected": connected_first == ["T1", "T2"] and connected_second == ["T1", "T2"],
        "auto_refill_control_surface_present": auto_refill_surface_present,
    }
    for name, ok in checks.items():
        if not ok:
            blockers.append(name)

    if not read_only_boundary_ok or not identity_boundary_ok:
        status = "INVALID_READ_ONLY_CAPTURE"
    elif not files_unchanged:
        status = "CLOSED_READ_ONLY_BLOCKED_FILE_DRIFT_DURING_CAPTURE"
    elif not all(historical_matches.values()):
        status = "CLOSED_READ_ONLY_BLOCKED_S12_BINARY_DRIFT"
    elif not command_surface_ok or not callbacks_ok:
        status = "CLOSED_READ_ONLY_BLOCKED_S12_SURFACE_MISMATCH"
    elif blockers:
        status = "CLOSED_READ_ONLY_S12_SURFACE_FOUND_RUNTIME_GAPS"
    else:
        status = "CLOSED_READ_ONLY_S12_SURFACE_CONFIRMED_EFFECTS_CLOSED"

    return {
        "status": status,
        "checks": checks,
        "blockers": blockers,
        "historical_hashes_match": historical_matches,
        "required_command_presence": command_presence,
        "required_callback_presence": callback_presence,
        "candidate_signature_cross_map": signatures,
        "connected_units": {
            "first": connected_first,
            "second": connected_second,
        },
        "runtime": {
            "print_state_first": first.get("print_state"),
            "print_state_second": second.get("print_state"),
            "hotend_target_first": first.get("extruder", {}).get("target"),
            "bed_target_first": first.get("heater_bed", {}).get("target"),
            "active_mesh_first": first.get("active_mesh"),
            "box_state_first": first.get("box", {}).get("state"),
            "t_command_present_first": first.get("box", {}).get("t_command", {}).get("present"),
            "stock_auto_refill_value_first": first.get("box", {}).get("auto_refill"),
            "stock_cfs_print_enable_first": first.get("box", {}).get("enable"),
            "same_material_groups_without_identity": same_material_groups,
        },
        "auto_refill": {
            "custom_feature_remains_possible_to_implement": auto_refill_surface_present,
            "stock_auto_refill_selected_as_job_owner": False,
            "physical_runout_behavior_qualified": False,
        },
        "next_scope": {
            "offline_owner_gate_ready_for_separate_GO": status == "CLOSED_READ_ONLY_S12_SURFACE_CONFIRMED_EFFECTS_CLOSED",
            "deployment_authorized": False,
            "gcode_or_cfs_effect_authorized": False,
            "physical_phase_authorized": False,
            "separate_human_present_gate_required_per_primitive": True,
        },
        "truthful_limit": (
            "The exact S12 command names, callbacks, runtime fields and file hashes are mapped. "
            "Klipper gcode_help is non-authoritative for compiled commands without help text. "
            "Public argument signatures are correlated with the exact binary surface, but no effect, "
            "hidden side effect, retry path or physical auto-refill sequence is qualified."
        ),
    }


def verify_evidence(root: Path) -> dict[str, Any]:
    package = root / "packages" / "k1-control-v1" / "cfs-s12-owner-preflight-v1"
    contract = json.loads((package / "contract.json").read_text(encoding="utf-8"))
    evidence = json.loads((package / "evidence-map.json").read_text(encoding="utf-8"))
    capture_path = root / evidence["private_source"]["path"]
    if sha256_file(capture_path) != evidence["private_source"]["sha256"]:
        raise CaptureError("private_capture_hash_mismatch")
    result = analyze(load_capture(capture_path), contract)
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    result_sha256 = hashlib.sha256(canonical).hexdigest()
    if result_sha256 != evidence["safe_result_sha256"]:
        raise CaptureError("safe_result_hash_mismatch")
    if result["status"] != evidence["expected_status"]:
        raise CaptureError("safe_result_status_mismatch")
    if result["checks"] != evidence["expected_checks"]:
        raise CaptureError("safe_result_checks_mismatch")
    return result


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[3]
    print(json.dumps(verify_evidence(project_root), indent=2, sort_keys=True))
