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
STOCK_INITIAL_PURGE_MM = 140.0
VALID_EXTENSIONS = {".gcode", ".g", ".gco"}
MAX_SCAN_BYTES = 256 * 1024 * 1024
ASSERT_MARKER = "KCTRL_STOCK_JOB_ASSERT_V1"
END_MARKER = "KCTRL_STOCK_JOB_END_V1"
COMMAND = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\b")
ORCA_FLUSH_LINE = re.compile(
    r"^\s*;\s*(filament_diameter|flush_multiplier|flush_volumes_matrix|"
    r"flush_volumes_vector|purge_in_prime_tower)\s*=\s*(.*?)\s*$",
    re.IGNORECASE,
)
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


def _csv_numbers(value: str, name: str):
    result = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            raise JobContractError("gcode_%s_invalid" % name)
        result.append(_number(item, "gcode_%s" % name))
    return result


def _orca_flush_profile(values: Mapping[str, str]):
    if not values:
        return None
    required = {
        "filament_diameter",
        "flush_multiplier",
        "flush_volumes_matrix",
        "flush_volumes_vector",
        "purge_in_prime_tower",
    }
    if set(values) != required:
        raise JobContractError("gcode_flush_profile_incomplete")
    diameters = _csv_numbers(values["filament_diameter"], "filament_diameter")
    matrix = _csv_numbers(values["flush_volumes_matrix"], "flush_volumes_matrix")
    vector = _csv_numbers(values["flush_volumes_vector"], "flush_volumes_vector")
    multiplier = _number(values["flush_multiplier"], "gcode_flush_multiplier")
    purge_in_prime_tower = _number(
        values["purge_in_prime_tower"], "gcode_purge_in_prime_tower"
    )
    count = len(diameters)
    if (
        count < 1
        or len(matrix) != count * count
        or len(vector) < count
        or not 0.1 <= multiplier <= 3.0
        or purge_in_prime_tower not in (0.0, 1.0)
    ):
        raise JobContractError("gcode_flush_profile_invalid")
    for diameter in diameters:
        if not 1.0 <= diameter <= 3.0:
            raise JobContractError("gcode_filament_diameter_invalid")
    initial = vector[:count]
    if any(not 80.0 <= length <= 400.0 for length in initial):
        raise JobContractError("gcode_initial_purge_out_of_bounds")
    transitions = {}
    for source in range(count):
        for target in range(count):
            volume = matrix[source * count + target] * multiplier
            area = math.pi * (diameters[target] / 2.0) ** 2
            length = volume / area
            if source != target and not 0.1 <= length <= 400.0:
                raise JobContractError("gcode_transition_purge_out_of_bounds")
            transitions["%d>%d" % (source, target)] = length
    return {
        "filament_diameter_mm": diameters,
        "initial_purge_mm_by_tool": initial,
        "transition_purge_mm_by_pair": transitions,
        "flush_multiplier": multiplier,
        "purge_in_prime_tower": int(purge_in_prime_tower),
    }


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
    flush_values = {}
    try:
        with path.open("rb") as stream:
            for raw_line in stream:
                digest.update(raw_line)
                line = raw_line.decode("utf-8", errors="replace")
                flush_match = ORCA_FLUSH_LINE.match(line)
                if flush_match is not None:
                    flush_values[flush_match.group(1).lower()] = flush_match.group(2)
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
        "orca_flush_profile": _orca_flush_profile(flush_values),
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
    flush_profile = inspection["orca_flush_profile"]
    initial_purge_mm = STOCK_INITIAL_PURGE_MM
    purge_contract = "stock_initial_load_140mm_fallback"
    if flush_profile is not None:
        initial_purge_mm = flush_profile["initial_purge_mm_by_tool"][0]
        purge_contract = "orca_flush_vector_tool_0"
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
        # La trace stock qualifie 140 mm lorsque le premier filament est
        # charge (last_tnn=None). Ce n'est pas la purge variable d'un
        # changement de couleur, qui doit rester issue de la matrice Orca.
        "purge_mm": initial_purge_mm,
        "purge_contract": purge_contract,
        "orca_flush_profile": flush_profile,
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
