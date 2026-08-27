#!/usr/bin/env python3
"""Verify that the future deployment blueprint is exact and still inert."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Dict, Mapping


PACKAGE = Path(__file__).resolve().parent
BLUEPRINT = PACKAGE / "future-deployment-blueprint.json"
DESTINATION_ROOT = (
    "/usr/data/k1-control-v1/current/moonraker/moonraker/"
    "moonraker/components/"
)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def verify(path: Path = BLUEPRINT) -> Mapping[str, Any]:
    blueprint = json.loads(path.read_text(encoding="utf-8"))
    if blueprint["status"] != "offline_blueprint_not_deployable":
        raise ValueError("blueprint_status_invalid")
    for field in ("deployment_candidate", "execute", "printer_connection"):
        if blueprint[field] is not False:
            raise ValueError("blueprint_must_remain_inert:%s" % field)
    for field in ("remote_commands", "service_actions", "gcode_commands"):
        if blueprint[field] != []:
            raise ValueError("blueprint_command_surface_not_empty:%s" % field)

    source_hashes: Dict[str, str] = {}
    destinations = []
    for item in blueprint["files"]:
        source = (PACKAGE / item["source"]).resolve()
        if not source.is_file():
            raise ValueError("blueprint_source_missing:%s" % item["source"])
        actual = file_sha256(source)
        if item["sha256"] != actual:
            raise ValueError("blueprint_source_hash_mismatch:%s" % item["role"])
        destination = item["future_destination"]
        if not destination.startswith(DESTINATION_ROOT):
            raise ValueError("blueprint_destination_outside_component_root")
        source_hashes[item["role"]] = actual
        destinations.append(destination)
    if len(destinations) != len(set(destinations)):
        raise ValueError("blueprint_destination_duplicate")
    if destinations != blueprint["future_write_set"]:
        raise ValueError("blueprint_write_set_mismatch")
    rollback = blueprint["rollback_requirements"]
    if rollback["same_write_set_as_candidate"] is not True:
        raise ValueError("rollback_write_set_not_pinned")
    if not all(
        rollback[field] is True
        for field in (
            "remove_only_confirmed_new_paths",
            "restore_existing_files_from_exact_backup",
            "verify_hashes_after_restore",
            "validate_stock_ui_calibration_z_mesh_and_two_cfs",
        )
    ):
        raise ValueError("rollback_requirements_incomplete")
    expected_slices = [
        "CLEAN-MOTION-V1",
        "CLEAN-AND-REFERENCE-V1",
        "CFS-TEMP-OWNER-V1",
        "TOOL-CHANGE-AND-RUNOUT-V1",
        "PAUSE-RESUME-SEMANTICS-V1",
        "END-SEQUENCE-V1",
        "ORCA-CUTOVER-V1",
    ]
    if [item["id"] for item in blueprint["future_slices"]] != expected_slices:
        raise ValueError("future_slice_order_invalid")
    if not all(item["human_presence"] is True for item in blueprint["future_slices"]):
        raise ValueError("future_human_gate_missing")
    return {
        "status": "OK",
        "files_pinned": len(source_hashes),
        "future_write_set_count": len(destinations),
        "future_slices": len(expected_slices),
        "remote_commands": 0,
        "service_actions": 0,
        "gcode_commands": 0,
        "deployment_candidate": False,
        "printer_connection": False,
    }


def main() -> int:
    print(json.dumps(verify(), indent=2, sort_keys=True))
    print("VERIFY_JOB_LIFECYCLE_FUTURE_BLUEPRINT_V1_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
