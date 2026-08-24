#!/usr/bin/env python3
"""Deterministic Klipper export for MESH-EDITOR-OFFLINE-V1; never installs it."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List

from mesh_editor_core import (
    DERIVED_PROFILE_ID,
    GRID_SIZE,
    MeshEditorError,
    PINNED_SOURCE_MATRIX_SHA256,
    SOURCE_ID,
    decimal_matrix,
    load_source_matrix,
    validate_derived_document,
    weighted_surface_mean,
)


PROFILE_HEADER = "#*# [bed_mesh " + DERIVED_PROFILE_ID + "]"
PROFILE_NAME_PATTERN = re.compile(r"^[a-z0-9_]+$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
EXPORTED_MEAN_TOLERANCE = Decimal("0.000001")


def _format_number(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    if rounded == 0:
        rounded = abs(rounded)
    return format(rounded, ".6f")


def render_klipper_profile(document: Dict[str, Any], eol: str = "\n") -> str:
    validate_derived_document(document)
    if eol not in ("\n", "\r\n"):
        raise MeshEditorError("la fin de ligne Klipper est invalide")
    if not PROFILE_NAME_PATTERN.fullmatch(DERIVED_PROFILE_ID):
        raise MeshEditorError("le nom du profil Klipper est invalide")
    final = decimal_matrix(document["matrices_mm"]["final"], "la matrice finale")
    fingerprint = document["fingerprint"]["canonical_json"]
    lines = [
        "# MESH-EDITOR-OFFLINE-V1",
        "# source_profile = " + document["source"]["profile_id"],
        "# source_matrix_sha256 = " + document["source"]["matrix_sha256"],
        "# derived_profile_sha256 = " + fingerprint,
        "# global_z_included = false",
        PROFILE_HEADER,
        "#*# version = 1",
        "#*# points =",
    ]
    lines.extend(
        "#*# \t" + ", ".join(_format_number(item) for item in row)
        for row in final
    )
    lines.extend(
        [
            "#*# x_count = 11",
            "#*# y_count = 11",
            "#*# mesh_x_pps = 2",
            "#*# mesh_y_pps = 2",
            "#*# algo = bicubic",
            "#*# tension = 0.2",
            "#*# min_x = 5.0",
            "#*# max_x = 295.0",
            "#*# min_y = 5.0",
            "#*# max_y = 295.0",
        ]
    )
    rendered = eol.join(lines) + eol
    parsed = parse_klipper_profile(rendered)
    source = load_source_matrix()
    exported_delta = tuple(
        tuple(parsed["matrix"][row][column] - source[row][column] for column in range(GRID_SIZE))
        for row in range(GRID_SIZE)
    )
    if abs(weighted_surface_mean(exported_delta)) > EXPORTED_MEAN_TOLERANCE:
        raise MeshEditorError(
            "l'arrondi Klipper dépasse la tolérance de moyenne nulle"
        )
    return rendered


def parse_klipper_profile(block: str) -> Dict[str, Any]:
    if not isinstance(block, str) or "\x00" in block:
        raise MeshEditorError("le bloc Klipper est invalide")
    lines = block.splitlines()
    if lines.count(PROFILE_HEADER) != 1:
        raise MeshEditorError("l'en-tête du profil dérivé doit être unique")
    header_index = lines.index(PROFILE_HEADER)
    if header_index != 5:
        raise MeshEditorError("les métadonnées du profil Klipper sont incomplètes")
    expected_prefixes = [
        "# MESH-EDITOR-OFFLINE-V1",
        "# source_profile = " + SOURCE_ID,
        "# source_matrix_sha256 = ",
        "# derived_profile_sha256 = ",
        "# global_z_included = false",
    ]
    if lines[0] != expected_prefixes[0] or lines[1] != expected_prefixes[1]:
        raise MeshEditorError("la référence source du bloc Klipper a changé")
    if lines[2] != expected_prefixes[2] + PINNED_SOURCE_MATRIX_SHA256:
        raise MeshEditorError("l'empreinte source du bloc Klipper est invalide")
    if not lines[3].startswith(expected_prefixes[3]) or not SHA256_PATTERN.fullmatch(
        lines[3][len(expected_prefixes[3]) :]
    ):
        raise MeshEditorError("l'empreinte dérivée du bloc Klipper est invalide")
    if lines[4] != expected_prefixes[4]:
        raise MeshEditorError("le bloc Klipper ne sépare pas le Z global")
    required_tail = [
        "#*# version = 1",
        "#*# points =",
    ]
    if lines[header_index + 1 : header_index + 3] != required_tail:
        raise MeshEditorError("le début du bloc Klipper est incomplet")
    point_lines = lines[header_index + 3 : header_index + 3 + GRID_SIZE]
    if len(point_lines) != GRID_SIZE:
        raise MeshEditorError("le bloc Klipper doit contenir onze lignes")
    rows: List[List[Decimal]] = []
    for line in point_lines:
        if not line.startswith("#*# \t"):
            raise MeshEditorError("une ligne de points Klipper est invalide")
        values = [item.strip() for item in line[len("#*# \t") :].split(",")]
        if len(values) != GRID_SIZE:
            raise MeshEditorError("une ligne Klipper doit contenir onze colonnes")
        try:
            rows.append([Decimal(value) for value in values])
        except (InvalidOperation, ValueError):
            raise MeshEditorError("une valeur de point Klipper est invalide")
    parameters = lines[header_index + 3 + GRID_SIZE :]
    expected_parameters = [
        "#*# x_count = 11",
        "#*# y_count = 11",
        "#*# mesh_x_pps = 2",
        "#*# mesh_y_pps = 2",
        "#*# algo = bicubic",
        "#*# tension = 0.2",
        "#*# min_x = 5.0",
        "#*# max_x = 295.0",
        "#*# min_y = 5.0",
        "#*# max_y = 295.0",
    ]
    if parameters != expected_parameters:
        raise MeshEditorError("les paramètres Klipper du profil ont changé")
    return {
        "profile_id": DERIVED_PROFILE_ID,
        "metadata": {
            "source_profile": lines[1].split(" = ", 1)[1],
            "source_matrix_sha256": lines[2].split(" = ", 1)[1],
            "derived_profile_sha256": lines[3].split(" = ", 1)[1],
            "global_z_included": False,
        },
        "matrix": decimal_matrix(rows),
        "parameters": {
            "x_count": 11,
            "y_count": 11,
            "mesh_x_pps": 2,
            "mesh_y_pps": 2,
            "algo": "bicubic",
            "tension": "0.2",
            "min_x": "5.0",
            "max_x": "295.0",
            "min_y": "5.0",
            "max_y": "295.0",
        },
    }


def canonical_round_trip(block: str) -> str:
    parse_klipper_profile(block)
    eol = "\r\n" if "\r\n" in block else "\n"
    return eol.join(block.splitlines()) + eol
