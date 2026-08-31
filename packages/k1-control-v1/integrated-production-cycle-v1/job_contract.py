#!/usr/bin/env python3
"""Build one strict K1 Control job contract from Moonraker metadata and G-code.

The file is read locally on the printer.  No file is selected implicitly and
no temperature is taken from a CFS macro.  V1 deliberately accepts only the
qualified T1A/PLA/55 C setup.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path, PurePosixPath
import re
from typing import Any, Dict, Mapping


PROFILE = "k1_p001_t055_r001_n11x11"
VALID_EXTENSIONS = {".gcode", ".g", ".gco"}
PLA_MIN_C = 180.0
PLA_MAX_C = 240.0
BED_FIRST_C = 55.0
PROBE_NOZZLE_C = 140.0
PURGE_MM = 8.0
MAX_SCAN_BYTES = 256 * 1024 * 1024

COMMAND = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\b")
FORBIDDEN_COMMANDS = {
    "T0",
    "START_PRINT",
    "END_PRINT",
    "BOX_START_PRINT",
    "BOX_END_PRINT",
    "BOX_MATERIAL_FLUSH",
    "BOX_NOZZLE_CLEAN",
    "BED_MESH_CALIBRATE",
    "G29",
    "G28",
    "SET_GCODE_OFFSET",
}


class JobContractError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise JobContractError("metadata_%s_invalid" % name)
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise JobContractError("metadata_%s_invalid" % name)
    if not math.isfinite(result):
        raise JobContractError("metadata_%s_invalid" % name)
    return result


def _filename(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise JobContractError("filename_invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.suffix.lower() not in VALID_EXTENSIONS:
        raise JobContractError("filename_invalid")
    return str(path)


def _single_material(value: Any) -> str:
    if not isinstance(value, str):
        raise JobContractError("metadata_filament_type_invalid")
    materials = [part.strip().upper() for part in re.split(r"[,;]", value) if part.strip()]
    if not materials or set(materials) != {"PLA"}:
        raise JobContractError("only_single_PLA_T1A_supported")
    return "PLA"


def _normal_temperature(metadata: Mapping[str, Any], first: float) -> float:
    values = metadata.get("filament_temps")
    if values is None:
        return first
    if not isinstance(values, list) or len(values) != 1:
        raise JobContractError("metadata_filament_temps_invalid")
    return _number(values[0], "filament_temps")


def inspect_gcode(path: Path) -> Dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError as error:
        raise JobContractError("gcode_file_unreadable") from error
    if size <= 0 or size > MAX_SCAN_BYTES:
        raise JobContractError("gcode_file_size_invalid")
    digest = hashlib.sha256()
    commands = []
    try:
        with path.open("rb") as stream:
            for raw_line in stream:
                digest.update(raw_line)
                line = raw_line.decode("utf-8", errors="replace")
                match = COMMAND.match(line)
                if match is not None:
                    commands.append(match.group(1).upper())
    except OSError as error:
        raise JobContractError("gcode_file_unreadable") from error
    forbidden = sorted(set(commands) & FORBIDDEN_COMMANDS)
    if forbidden:
        raise JobContractError("forbidden_gcode_command:%s" % forbidden[0])
    if commands.count("KCTRL_CYCLE_JOB_ASSERT_V1") != 1:
        raise JobContractError("atomic_start_missing_or_duplicated")
    if commands.count("KCTRL_CYCLE_END_V1") != 1:
        raise JobContractError("atomic_end_missing_or_duplicated")
    if commands.index("KCTRL_CYCLE_JOB_ASSERT_V1") >= commands.index("KCTRL_CYCLE_END_V1"):
        raise JobContractError("atomic_start_end_order_invalid")
    return {"sha256": digest.hexdigest(), "size": size, "command_count": len(commands)}


def build_job_contract(filename: Any, metadata: Mapping[str, Any], full_path: Path) -> Dict[str, Any]:
    safe_filename = _filename(filename)
    if not isinstance(metadata, Mapping):
        raise JobContractError("metadata_invalid")
    if "ORCASLICER" not in str(metadata.get("slicer", "")).upper():
        raise JobContractError("only_OrcaSlicer_supported")
    material = _single_material(metadata.get("filament_type"))
    first = _number(metadata.get("first_layer_extr_temp"), "first_layer_extr_temp")
    bed = _number(metadata.get("first_layer_bed_temp"), "first_layer_bed_temp")
    normal = _normal_temperature(metadata, first)
    if abs(bed - BED_FIRST_C) > 0.001:
        raise JobContractError("first_layer_bed_must_be_55C")
    for name, value in (("first", first), ("normal", normal)):
        if not PLA_MIN_C <= value <= PLA_MAX_C:
            raise JobContractError("PLA_%s_temperature_out_of_bounds" % name)
    referenced = metadata.get("referenced_tools", [0])
    if referenced not in ([0], [], None):
        raise JobContractError("multi_tool_job_forbidden")
    if metadata.get("mmu_print") not in (None, 0, False):
        raise JobContractError("slicer_MMU_job_forbidden")
    inspection = inspect_gcode(full_path)
    marker = str(metadata.get("uuid") or inspection["sha256"][:24])
    job_id = re.sub(r"[^A-Za-z0-9._-]", "-", marker).strip("-.")[:96]
    if not job_id:
        raise JobContractError("job_id_invalid")
    return {
        "contract_version": 1,
        "job_id": job_id,
        "filename": safe_filename,
        "material_id": material,
        "route": "T1A",
        "mesh_profile": PROFILE,
        "legacy_z_offset_removed": True,
        "bed_first_c": BED_FIRST_C,
        "probe_nozzle_c": PROBE_NOZZLE_C,
        "nozzle_first_c": first,
        "nozzle_normal_c": normal,
        "load_c": first,
        "unload_c": first,
        "purge_c": first,
        "purge_mm": PURGE_MM,
        "material_min_c": PLA_MIN_C,
        "material_max_c": PLA_MAX_C,
        "source": {
            "metadata_uuid": metadata.get("uuid"),
            "gcode_sha256": inspection["sha256"],
            "gcode_size": inspection["size"],
            "slicer": metadata.get("slicer"),
            "slicer_version": metadata.get("slicer_version"),
        },
    }
