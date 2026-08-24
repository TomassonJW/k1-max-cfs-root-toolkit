#!/usr/bin/env python3
"""Prepare one guarded large first-layer job for live Z validation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Optional


SOURCE_SHA256 = "b93fff2eec8354376be7de55210ad592ea4feffb546abfa92f016cc7c6fde2d3"
START_COMMAND = "START_PRINT EXTRUDER_TEMP=190 BED_TEMP=55"
MARKER = "; K1_CONTROL_FIRST_LAYER_Z_VALIDATION_V1"
ARM_COMMAND = (
    "KCTRL_PRODUCTION_ARM PLATE=1 TEMP_BAND=55 PROBE_REV=1 NOZZLE_ID=1 "
    "CONFIG_ID=1 X_COUNT=6 Y_COUNT=6"
)
PROFILE = "k1_p001_t055_r001_n06x06"
OUTPUT_NAME = "K1-Z-VALIDATION-V1-ROBUST-6X6.gcode"


class ZValidationPreparationError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_source(source: bytes, expected_sha256: str) -> tuple[str, str]:
    if sha256_bytes(source) != expected_sha256:
        raise ZValidationPreparationError("Le G-code source n'a pas l'empreinte revue.")
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ZValidationPreparationError("Le G-code source n'est pas en UTF-8.") from exc
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    required_once = (
        "; total layer number: 1",
        "; max_z_height: 0.20",
        "EXCLUDE_OBJECT_DEFINE NAME=Cube_id_0_copy_0 CENTER=150,150 POLYGON=[[20,20],[280,20],[280,280],[20,280],[20,20]]",
        "G28",
        "T0",
        START_COMMAND,
        "; post_process = ",
        "; z_offset = 0",
        "; first_layer_bed_temperature = 55",
        "; first_layer_temperature = 190",
        "; first_layer_height = 0.200",
    )
    for required in required_once:
        if lines.count(required) != 1:
            raise ZValidationPreparationError(
                f"Le G-code source doit contenir exactement une ligne: {required}"
            )
    start_index = lines.index(START_COMMAND)
    if lines[start_index - 2 : start_index + 2] != [
        "G28",
        "T0",
        START_COMMAND,
        "M104 S190",
    ]:
        raise ZValidationPreparationError("La séquence G28/T0/START_PRINT/M104 a changé.")

    forbidden = (
        "SET_GCODE_OFFSET",
        "G92 Z",
        "M206",
        "M851",
        "BED_MESH_",
        "KCTRL_",
    )
    for line in lines:
        executable = line.strip()
        if not executable or executable.startswith(";"):
            continue
        upper = executable.upper()
        if any(token in upper for token in forbidden):
            raise ZValidationPreparationError(
                f"Le G-code source contient une commande interdite: {executable}"
            )
    return text, newline


def prepare_payload(source: bytes, expected_sha256: Optional[str] = None) -> bytes:
    if expected_sha256 is None:
        expected_sha256 = SOURCE_SHA256
    text, newline = _validate_source(source, expected_sha256)
    anchor = START_COMMAND + newline
    guarded = anchor + MARKER + newline + ARM_COMMAND + newline
    output = text.replace(anchor, guarded, 1)
    payload = output.encode("utf-8")
    if payload.count(b"KCTRL_PRODUCTION_ARM") != 1:
        raise ZValidationPreparationError("La garde K1 Control n'est pas unique.")
    if b"SET_GCODE_OFFSET" in payload:
        raise ZValidationPreparationError("Une correction Z explicite est présente.")
    return payload


def write_validation(source_path: Path, output_directory: Path) -> dict:
    source = source_path.read_bytes()
    payload = prepare_payload(source)
    output_directory.mkdir(parents=True, exist_ok=False)
    (output_directory / OUTPUT_NAME).write_bytes(payload)
    manifest = {
        "schema": 1,
        "source_name": source_path.name,
        "source_sha256": sha256_bytes(source),
        "output_name": OUTPUT_NAME,
        "output_sha256": sha256_bytes(payload),
        "profile": PROFILE,
        "accepted_z_source": "KCTRL_STATE.accepted_z_offset",
        "expected_initial_z_mm": -0.04,
        "explicit_gcode_z_offset": None,
        "geometry_mm": [260, 260, 0.2],
        "bed_temperature_c": 55,
        "nozzle_temperature_c": 190,
    }
    (output_directory / "validation-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    manifest = write_validation(args.source, args.output_directory)
    print(json.dumps(manifest, sort_keys=True, ensure_ascii=False))
    print("PREPARE_FIRST_LAYER_Z_VALIDATION_V1_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
