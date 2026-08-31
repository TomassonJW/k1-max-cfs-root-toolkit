#!/usr/bin/env python3
"""Contrat strict d'un G-code possédé par le cycle stock-derived."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path, PurePosixPath
import re
from typing import Any, Dict, Mapping


PROFILE = "k1_p001_t055_r001_n11x11"
ACCEPTED_Z_MM = -0.04
BED_C = 55.0
PROBE_C = 140.0
FIRST_C = 190.0
PLA_MIN_C = 180.0
PLA_MAX_C = 230.0
VALID_EXTENSIONS = {".gcode", ".g", ".gco"}
MAX_SCAN_BYTES = 256 * 1024 * 1024
ASSERT_MARKER = "KCTRL_STOCK_JOB_ASSERT_V1"
END_MARKER = "KCTRL_STOCK_JOB_END_V1"
COMMAND = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\b")
FORBIDDEN_EXACT = {
    "T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7",
    "START_PRINT", "END_PRINT", "BOX_START_PRINT", "BOX_END_PRINT",
    "BOX_MATERIAL_FLUSH", "BOX_NOZZLE_CLEAN", "BOX_CUT_MATERIAL",
    "BOX_EXTRUDE_MATERIAL", "BOX_RETRUDE_MATERIAL",
    "BED_MESH_CALIBRATE", "BED_MESH_PROFILE", "G29", "G28",
    "SET_GCODE_OFFSET", "SAVE_CONFIG", "M84", "TURN_OFF_HEATERS", "M107",
}
ZERO_TARGET = re.compile(r"(?:^|\s)S\s*0(?:\.0+)?(?:\s|$)", re.IGNORECASE)
ZERO_HEATER_TARGET = re.compile(
    r"(?:^|\s)TARGET\s*=\s*0(?:\.0+)?(?:\s|$)", re.IGNORECASE
)


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


def _single_pla(value: Any) -> str:
    if not isinstance(value, str):
        raise JobContractError("metadata_filament_type_invalid")
    materials = [part.strip().upper() for part in re.split(r"[,;]", value) if part.strip()]
    if not materials or set(materials) != {"PLA"}:
        raise JobContractError("only_single_PLA_profile_is_qualified")
    return "PLA"


def inspect_gcode(path: Path) -> Dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError as error:
        raise JobContractError("gcode_file_unreadable") from error
    if size <= 0 or size > MAX_SCAN_BYTES:
        raise JobContractError("gcode_file_size_invalid")
    digest = hashlib.sha256()
    commands = []
    forbidden_shutdown = None
    try:
        with path.open("rb") as stream:
            for raw_line in stream:
                digest.update(raw_line)
                line = raw_line.decode("utf-8", errors="replace")
                match = COMMAND.match(line)
                if match is not None:
                    command = match.group(1).upper()
                    commands.append(command)
                    if command in {"M104", "M109", "M140", "M190"} and ZERO_TARGET.search(line):
                        forbidden_shutdown = command
                    if command == "SET_HEATER_TEMPERATURE" and ZERO_HEATER_TARGET.search(line):
                        forbidden_shutdown = command
    except OSError as error:
        raise JobContractError("gcode_file_unreadable") from error
    forbidden = sorted(set(commands) & FORBIDDEN_EXACT)
    if forbidden:
        raise JobContractError("forbidden_gcode_command:%s" % forbidden[0])
    if forbidden_shutdown is not None:
        raise JobContractError(
            "premature_owner_shutdown_command:%s" % forbidden_shutdown
        )
    forbidden_prefix = sorted(
        command for command in set(commands)
        if command.startswith("BOX_") or (
            command.startswith("KCTRL_") and command not in {ASSERT_MARKER, END_MARKER}
        )
    )
    if forbidden_prefix:
        raise JobContractError("foreign_owner_gcode_command:%s" % forbidden_prefix[0])
    if commands.count(ASSERT_MARKER) != 1 or commands.count(END_MARKER) != 1:
        raise JobContractError("stock_owner_markers_missing_or_duplicated")
    if commands[0] != ASSERT_MARKER or commands[-1] != END_MARKER:
        raise JobContractError("stock_owner_markers_not_at_boundaries")
    return {
        "sha256": digest.hexdigest(),
        "size": size,
        "command_count": len(commands),
    }


def build_job_contract(
    filename: Any,
    metadata: Mapping[str, Any],
    full_path: Path,
    initial_route: str,
) -> Dict[str, Any]:
    safe_filename = _filename(filename)
    if not re.fullmatch(r"T[12][ABCD]", str(initial_route)):
        raise JobContractError("initial_route_invalid")
    if not isinstance(metadata, Mapping):
        raise JobContractError("metadata_invalid")
    if "ORCASLICER" not in str(metadata.get("slicer", "")).upper():
        raise JobContractError("only_OrcaSlicer_supported")
    material = _single_pla(metadata.get("filament_type"))
    first = _number(metadata.get("first_layer_extr_temp"), "first_layer_extr_temp")
    bed = _number(metadata.get("first_layer_bed_temp"), "first_layer_bed_temp")
    if abs(first - FIRST_C) > 0.001 or abs(bed - BED_C) > 0.001:
        raise JobContractError("only_55C_190C_profile_is_qualified")
    referenced = metadata.get("referenced_tools", [0])
    if referenced not in ([0], [], None) or metadata.get("mmu_print") not in (None, 0, False):
        raise JobContractError("multi_tool_gcode_not_yet_qualified")
    inspection = inspect_gcode(full_path)
    marker = str(metadata.get("uuid") or inspection["sha256"][:24])
    job_id = re.sub(r"[^A-Za-z0-9._-]", "-", marker).strip("-.")[:48]
    if not job_id:
        raise JobContractError("job_id_invalid")
    return {
        "job_id": job_id,
        "filename": safe_filename,
        "initial_route": str(initial_route),
        "mesh_profile": PROFILE,
        "accepted_z_mm": ACCEPTED_Z_MM,
        "bed_c": BED_C,
        "probe_nozzle_c": PROBE_C,
        "first_nozzle_c": FIRST_C,
        "load_c": FIRST_C,
        "unload_c": FIRST_C,
        "purge_c": FIRST_C,
        "purge_mm": 20.0,
        "material_min_c": PLA_MIN_C,
        "material_max_c": PLA_MAX_C,
        "release_trips": 4,
        "material_type": material,
        "source": {
            "gcode_sha256": inspection["sha256"],
            "gcode_size": inspection["size"],
            "slicer": metadata.get("slicer"),
            "slicer_version": metadata.get("slicer_version"),
        },
    }
