#!/usr/bin/env python3
"""Render, but never install, the reviewed Klipper 11x11 profile block."""

from __future__ import annotations

import math
from typing import Any


PROFILE_NAME = "k1_p001_t055_r001_n11x11"
ROBUST_PROFILE_NAME = "k1_p001_t055_r001_n06x06"
SAVE_CONFIG_MARKER = b"#*# <---------------------- SAVE_CONFIG ---------------------->"


def _matrix_11x11(value: Any) -> list[list[float]]:
    if not isinstance(value, (list, tuple)) or len(value) != 11:
        raise ValueError("le profil composite doit contenir onze lignes")
    matrix = []
    for row in value:
        if not isinstance(row, (list, tuple)) or len(row) != 11:
            raise ValueError("le profil composite doit contenir onze colonnes")
        converted = []
        for item in row:
            number = float(item)
            if not math.isfinite(number):
                raise ValueError("le profil composite contient une valeur non finie")
            converted.append(number)
        matrix.append(converted)
    return matrix


def _format_number(value: float) -> str:
    if abs(value) < 0.0000005:
        value = 0.0
    return f"{value:.6f}"


def render_profile_block(matrix: Any, eol: bytes = b"\n") -> bytes:
    checked = _matrix_11x11(matrix)
    if eol not in (b"\n", b"\r\n"):
        raise ValueError("fin de ligne non prise en charge")
    lines = [
        f"#*# [bed_mesh {PROFILE_NAME}]",
        "#*# version = 1",
        "#*# points =",
    ]
    lines.extend(
        "#*# \t" + ", ".join(_format_number(item) for item in row)
        for row in checked
    )
    lines.extend(
        (
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
        )
    )
    return eol.join(line.encode("ascii") for line in lines) + eol


def append_profile(document: bytes, matrix: Any) -> bytes:
    """Return the only reviewed printer.cfg candidate; perform no filesystem write."""

    lines = document.splitlines()
    if lines.count(SAVE_CONFIG_MARKER) != 1:
        raise ValueError("le bloc SAVE_CONFIG exact doit être unique")
    robust_header = f"#*# [bed_mesh {ROBUST_PROFILE_NAME}]".encode("ascii")
    target_header = f"#*# [bed_mesh {PROFILE_NAME}]".encode("ascii")
    if lines.count(robust_header) != 1:
        raise ValueError("le profil robuste 6x6 exact doit être unique")
    if target_header in lines:
        raise ValueError("un profil composite 11x11 existe déjà")
    eol = b"\r\n" if b"\r\n" in document else b"\n"
    prefix = document
    if prefix and not prefix.endswith((b"\n", b"\r")):
        prefix += eol
    return prefix + b"#*#" + eol + render_profile_block(matrix, eol)
