#!/usr/bin/env python3
"""Build the bounded MESH-EDGE-DIAGNOSTIC-V1 offline artifacts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, List, Sequence, Tuple


PACKAGE_DIR = Path(__file__).resolve().parent
EDITOR_DIR = PACKAGE_DIR.parent / "mesh-editor-offline-v1"
SOURCE_GCODE_SHA256 = "b93fff2eec8354376be7de55210ad592ea4feffb546abfa92f016cc7c6fde2d3"
SOURCE_PROFILE = "k1_p001_t055_r001_n11x11"
DERIVED_PROFILE = SOURCE_PROFILE + "_tuned_v001"
ROBUST_PROFILE = "k1_p001_t055_r001_n06x06"
GRID = tuple(5 + 29 * index for index in range(11))
TARGET_ROW = 9
TARGET_COLUMN = 1
TARGET_X_MM = GRID[TARGET_COLUMN]
TARGET_Y_MM = GRID[TARGET_ROW]
LAYER_Z_MM = 0.2
EXTRUSION_PER_MM = 0.03770
FILAMENT_GRAMS_PER_MM = 16.75 / 5570.0


class DiagnosticPreparationError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise DiagnosticPreparationError("Impossible de charger le moteur d'édition figé.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_editor_modules():
    editor_path = str(EDITOR_DIR)
    if editor_path not in sys.path:
        sys.path.insert(0, editor_path)
    core = _load_module("mesh_edge_editor_core", EDITOR_DIR / "mesh_editor_core.py")
    sys.modules["mesh_editor_core"] = core
    klipper = _load_module("mesh_edge_klipper_profile", EDITOR_DIR / "klipper_profile.py")
    return core, klipper


def _validate_source_gcode(source: bytes, expected_sha256: str) -> None:
    if sha256_bytes(source) != expected_sha256:
        raise DiagnosticPreparationError("Le G-code source n'a pas l'empreinte revue.")
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DiagnosticPreparationError("Le G-code source n'est pas en UTF-8.") from exc
    required = (
        "; total layer number: 1",
        "; max_z_height: 0.20",
        "G28",
        "START_PRINT EXTRUDER_TEMP=190 BED_TEMP=55",
        "; post_process = ",
        "; z_offset = 0",
        "; first_layer_bed_temperature = 55",
        "; first_layer_temperature = 190",
        "; first_layer_height = 0.200",
        "END_PRINT",
    )
    lines = text.splitlines()
    for line in required:
        if lines.count(line) != 1:
            raise DiagnosticPreparationError(
                "Le G-code source doit contenir exactement une ligne : " + line
            )
    for line in lines:
        executable = line.strip()
        if not executable or executable.startswith(";"):
            continue
        upper = executable.upper()
        if any(token in upper for token in ("SET_GCODE_OFFSET", "G92 Z", "M206", "M851", "KCTRL_")):
            raise DiagnosticPreparationError("Commande interdite dans la source : " + executable)


Point = Tuple[float, float]


def _rectangle(x0: float, y0: float, x1: float, y1: float) -> Tuple[Point, ...]:
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))


def diagnostic_strokes() -> Tuple[Tuple[Point, ...], ...]:
    strokes: List[Tuple[Point, ...]] = []
    for inset in (0.0, 0.6, 1.2):
        strokes.append(_rectangle(5.0 + inset, 5.0 + inset, 295.0 - inset, 295.0 - inset))
    half = 1.5
    for y in GRID:
        for x in GRID:
            strokes.append(
                _rectangle(
                    max(5.0, x - half),
                    max(5.0, y - half),
                    min(295.0, x + half),
                    min(295.0, y + half),
                )
            )
    strokes.extend(
        (
            ((140.0, 150.0), (160.0, 150.0)),
            ((150.0, 140.0), (150.0, 160.0)),
            ((10.0, 10.0), (18.0, 10.0), (10.0, 18.0), (10.0, 10.0)),
            ((282.0, 10.0), (290.0, 10.0)),
            ((282.0, 13.0), (290.0, 13.0)),
            ((10.0, 282.0), (18.0, 282.0)),
            ((10.0, 286.0), (18.0, 286.0)),
            ((10.0, 290.0), (18.0, 290.0)),
            ((282.0, 282.0), (290.0, 282.0), (290.0, 290.0), (282.0, 290.0), (282.0, 282.0)),
        )
    )
    return tuple(strokes)


def _path_length(stroke: Sequence[Point]) -> float:
    return sum(math.hypot(x1 - x0, y1 - y0) for (x0, y0), (x1, y1) in zip(stroke, stroke[1:]))


def _format_number(value: float, places: int = 5) -> str:
    rendered = f"{value:.{places}f}".rstrip("0").rstrip(".")
    return "0" if rendered in ("", "-0") else rendered


def render_geometry() -> Tuple[List[str], float]:
    lines: List[str] = [
        "; MESH_EDGE_DIAGNOSTIC_GEOMETRY_START",
        "SET_VELOCITY_LIMIT ACCEL=5000 ACCEL_TO_DECEL=5000 SQUARE_CORNER_VELOCITY=6",
        "G90",
        "M83",
        "G92 E0",
    ]
    total_length = 0.0
    for index, stroke in enumerate(diagnostic_strokes(), start=1):
        if len(stroke) < 2:
            raise DiagnosticPreparationError("Un tracé diagnostic est vide.")
        for x, y in stroke:
            if not (5.0 <= x <= 295.0 and 5.0 <= y <= 295.0):
                raise DiagnosticPreparationError("Le motif sort de la zone X/Y 5..295 mm.")
        x0, y0 = stroke[0]
        lines.extend(
            (
                f"; diagnostic_stroke={index}",
                "G1 E-0.8 F2700",
                f"G1 X{_format_number(x0)} Y{_format_number(y0)} Z0.5 F18000",
                f"G1 Z{_format_number(LAYER_Z_MM)} F600",
                "G1 E0.8 F2700",
                "G1 F3600",
            )
        )
        previous = stroke[0]
        for x, y in stroke[1:]:
            distance = math.hypot(x - previous[0], y - previous[1])
            extrusion = distance * EXTRUSION_PER_MM
            lines.append(f"G1 X{_format_number(x)} Y{_format_number(y)} E{_format_number(extrusion)}")
            total_length += distance
            previous = (x, y)
    lines.extend(
        (
            "G1 Z5 F600",
            "G1 X150 Y295 F12000",
            "; MESH_EDGE_DIAGNOSTIC_GEOMETRY_END",
        )
    )
    return lines, total_length


def _arm_lines(variant: str) -> List[str]:
    common = [
        "KCTRL_PRODUCTION_ARM PLATE=1 TEMP_BAND=55 PROBE_REV=1 NOZZLE_ID=1 CONFIG_ID=1 X_COUNT=11 Y_COUNT=11"
    ]
    if variant == "source":
        return common
    if variant == "corrected":
        return common + [
            "BED_MESH_PROFILE LOAD=" + DERIVED_PROFILE,
            "KCTRL_PRODUCTION_VERIFY PROFILE=" + DERIVED_PROFILE,
        ]
    raise DiagnosticPreparationError("Variante inconnue.")


def render_prepare_gcode(variant: str) -> bytes:
    lines = [
        "; MESH-EDGE-DIAGNOSTIC-V1 PREPARE — NO EXTRUSION",
        f"; variant: {variant}",
        "; explicit_gcode_z_offset: none",
        "G28",
    ]
    lines.extend(_arm_lines(variant))
    lines.extend(("M400", "; PREPARE_MESH_EDGE_DIAGNOSTIC_V1_COMPLETE", ""))
    payload = "\n".join(lines).encode("utf-8")
    for raw_line in payload.splitlines():
        executable = raw_line.strip().upper()
        if not executable or executable.startswith(b";"):
            continue
        if executable.startswith((b"M104", b"M109", b"M140", b"M190", b"START_PRINT")) or re.fullmatch(rb"T\d+", executable):
            raise DiagnosticPreparationError("Le fichier de préparation contient une chauffe ou une sélection d'outil.")
        if executable.startswith((b"G0 ", b"G1 ")) and b" E" in executable:
            raise DiagnosticPreparationError("Le fichier de préparation contient une extrusion.")
    return payload


def render_pattern_gcode(variant: str) -> Tuple[bytes, str, float]:
    geometry, path_length = render_geometry()
    geometry_payload = ("\n".join(geometry) + "\n").encode("utf-8")
    filament_mm = path_length * EXTRUSION_PER_MM
    lines = [
        "; MESH-EDGE-DIAGNOSTIC-V1 PATTERN",
        "; total layer number: 1",
        "; max_z_height: 0.20",
        "; generated from reviewed Orca process metadata; geometry is deterministic",
        f"; variant: {variant}",
        "; no physical tool is selected; runner requires a confirmed route and visible purge",
        f"; geometry_sha256: {sha256_bytes(geometry_payload)}",
        f"; target_cell: row={TARGET_ROW} column={TARGET_COLUMN} X={TARGET_X_MM} Y={TARGET_Y_MM}",
        "; explicit_gcode_z_offset: none",
        "; EXECUTABLE_BLOCK_START",
        "EXCLUDE_OBJECT_DEFINE NAME=MESH_EDGE_DIAGNOSTIC_V1 CENTER=150,150 POLYGON=[[5,5],[295,5],[295,295],[5,295],[5,5]]",
        "M73 P0 R8",
        "M106 S0",
        "M106 P2 S0",
        ";TYPE:Custom",
        "KCTRL_PRODUCTION_ASSERT_ARMED",
        "M140 S55",
        "M104 S190",
        "M190 S55",
        "M109 S190",
    ]
    lines.extend(
        (
            "M204 S2000",
            "G1 Z3 F600",
            "M83",
            "G92 E0",
            "G1 Z1 F600",
            "G90",
            "G21",
            "M83",
            "SET_PRESSURE_ADVANCE ADVANCE=0.03",
            "M106 S0",
            "M106 P2 S0",
            ";LAYER_CHANGE",
            ";Z:0.2",
            ";HEIGHT:0.2",
            "EXCLUDE_OBJECT_START NAME=MESH_EDGE_DIAGNOSTIC_V1",
        )
    )
    lines.extend(geometry)
    lines.extend(
        (
            "EXCLUDE_OBJECT_END NAME=MESH_EDGE_DIAGNOSTIC_V1",
            "M106 S0",
            "M106 P2 S0",
            ";TYPE:Custom",
            "BED_MESH_PROFILE LOAD=" + ROBUST_PROFILE,
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=low_moves_armed VALUE=0",
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=armed_mesh_profile VALUE='\"none\"'",
            "TURN_OFF_HEATERS",
            "M84",
            "M73 P100 R0",
            "; EXECUTABLE_BLOCK_END",
            f"; filament used [mm] = {filament_mm:.2f}",
            f"; filament used [g] = {filament_mm * FILAMENT_GRAMS_PER_MM:.2f}",
            "; total layers count = 1",
            "",
        )
    )
    payload = "\n".join(lines).encode("utf-8")
    forbidden = (b"SET_GCODE_OFFSET", b"G92 Z", b"BED_MESH_CALIBRATE", b"START_PRINT", b"END_PRINT", b"PAUSE", b"RESUME")
    if any(token in payload for token in forbidden):
        raise DiagnosticPreparationError("Une commande interdite existe dans le G-code produit.")
    if payload.count(b"KCTRL_PRODUCTION_ASSERT_ARMED") != 1:
        raise DiagnosticPreparationError("La garde avant extrusion n'est pas unique.")
    return payload, sha256_bytes(geometry_payload), filament_mm


def build_profile_artifacts() -> Tuple[dict[str, Any], str]:
    core, klipper = _load_editor_modules()
    editor = core.MeshEditor()
    editor.apply_correction(
        {"mode": "point", "row": TARGET_ROW, "column": TARGET_COLUMN},
        "farther",
        "0.010",
    )
    document = editor.export_document()
    block = klipper.render_klipper_profile(document)
    parsed = klipper.parse_klipper_profile(block)
    if parsed["profile_id"] != DERIVED_PROFILE:
        raise DiagnosticPreparationError("Le profil Klipper dérivé n'est pas canonique.")
    return document, block


def prepare_artifacts(source_path: Path, output_directory: Path) -> dict[str, Any]:
    source = source_path.read_bytes()
    _validate_source_gcode(source, SOURCE_GCODE_SHA256)
    document, profile_block = build_profile_artifacts()
    source_prepare = render_prepare_gcode("source")
    corrected_prepare = render_prepare_gcode("corrected")
    source_gcode, geometry_hash, filament_mm = render_pattern_gcode("source")
    corrected_gcode, corrected_geometry_hash, corrected_filament_mm = render_pattern_gcode("corrected")
    if geometry_hash != corrected_geometry_hash or abs(filament_mm - corrected_filament_mm) > 1e-12:
        raise DiagnosticPreparationError("La géométrie ou la matière diffère entre variantes.")
    output_directory.mkdir(parents=True, exist_ok=False)
    files = {
        "derived_document": ("mesh-edge-derived-profile-v001.json", (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")),
        "derived_klipper": ("mesh-edge-derived-profile-v001.cfg", profile_block.encode("utf-8")),
        "source_prepare_gcode": ("K1-MESH-EDGE-V1-01A-SOURCE-PREPARE.gcode", source_prepare),
        "source_pattern_gcode": ("K1-MESH-EDGE-V1-01B-SOURCE-PATTERN.gcode", source_gcode),
        "corrected_prepare_gcode": ("K1-MESH-EDGE-V1-02A-CORRECTED-PREPARE.gcode", corrected_prepare),
        "corrected_pattern_gcode": ("K1-MESH-EDGE-V1-02B-FARTHER-X034-Y266-PATTERN.gcode", corrected_gcode),
    }
    manifest: dict[str, Any] = {
        "schema": 1,
        "gate": "MESH-EDGE-DIAGNOSTIC-V1",
        "source_gcode_sha256": sha256_bytes(source),
        "source_profile": SOURCE_PROFILE,
        "derived_profile": DERIVED_PROFILE,
        "fallback_profile": ROBUST_PROFILE,
        "correction": {
            "row": TARGET_ROW,
            "column": TARGET_COLUMN,
            "x_mm": TARGET_X_MM,
            "y_mm": TARGET_Y_MM,
            "direction": "farther",
            "requested_delta_mm": "0.010",
            "global_z_included": False,
        },
        "pattern": {
            "geometry_sha256": geometry_hash,
            "strokes": len(diagnostic_strokes()),
            "grid_cells": 121,
            "bounds_mm": [5, 5, 295, 295],
            "extrusion_path_mm": f"{sum(_path_length(stroke) for stroke in diagnostic_strokes()):.3f}",
            "estimated_filament_mm": f"{filament_mm:.3f}",
            "estimated_filament_g": f"{filament_mm * FILAMENT_GRAMS_PER_MM:.3f}",
        },
        "files": {},
    }
    for key, (name, payload) in files.items():
        (output_directory / name).write_bytes(payload)
        manifest["files"][key] = {"name": name, "sha256": sha256_bytes(payload)}
    (output_directory / "diagnostic-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_gcode", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    manifest = prepare_artifacts(args.source_gcode, args.output_directory)
    print(json.dumps(manifest, sort_keys=True, ensure_ascii=False))
    print("PREPARE_MESH_EDGE_DIAGNOSTIC_V1_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
