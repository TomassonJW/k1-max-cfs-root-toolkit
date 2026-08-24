#!/usr/bin/env python3
"""Prepare the guarded 6x6/11x11 large first-layer comparison pair."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Optional


SOURCE_SHA256 = "b93fff2eec8354376be7de55210ad592ea4feffb546abfa92f016cc7c6fde2d3"
START_COMMAND = "START_PRINT EXTRUDER_TEMP=190 BED_TEMP=55"
MARKER = "; K1_CONTROL_COMPOSITE_FIRST_LAYER_COMPARISON_V2"
PAUSE_COMMAND = "PAUSE"
ARM_TEMPLATE = (
    "KCTRL_PRODUCTION_ARM PLATE=1 TEMP_BAND=55 PROBE_REV=1 NOZZLE_ID=1 "
    "CONFIG_ID=1 X_COUNT={count} Y_COUNT={count}"
)
PROFILES = {
    "robust_6x6": "k1_p001_t055_r001_n06x06",
    "composite_11x11": "k1_p001_t055_r001_n11x11",
}
COUNTS = {"robust_6x6": 6, "composite_11x11": 11}
OUTPUT_NAMES = {
    "robust_6x6": "K1-COMPARE-V2-01-ROBUST-6X6-260MM.gcode",
    "composite_11x11": "K1-COMPARE-V2-02-COMPOSITE-11X11-260MM.gcode",
}


class ComparisonPreparationError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_source(source: bytes, expected_sha256: str) -> tuple[str, str]:
    if sha256_bytes(source) != expected_sha256:
        raise ComparisonPreparationError("Le G-code source n'a pas l'empreinte revue.")
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ComparisonPreparationError("Le G-code source n'est pas en UTF-8.") from exc
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
            raise ComparisonPreparationError(
                f"Le G-code source doit contenir exactement une ligne: {required}"
            )
    start_index = lines.index(START_COMMAND)
    if lines[start_index - 2 : start_index + 2] != [
        "G28",
        "T0",
        START_COMMAND,
        "M104 S190",
    ]:
        raise ComparisonPreparationError("La séquence G28/T0/START_PRINT/M104 a changé.")

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
            raise ComparisonPreparationError(
                f"Le G-code source contient une commande interdite: {executable}"
            )
    return text, newline


def prepare_payloads(source: bytes, expected_sha256: Optional[str] = None) -> dict[str, bytes]:
    if expected_sha256 is None:
        expected_sha256 = SOURCE_SHA256
    text, newline = _validate_source(source, expected_sha256)
    outputs: dict[str, bytes] = {}
    anchor = START_COMMAND + newline
    for key, count in COUNTS.items():
        guarded = (
            anchor
            + MARKER
            + newline
            + ARM_TEMPLATE.format(count=count)
            + newline
            + PAUSE_COMMAND
            + newline
        )
        output = text.replace(anchor, guarded, 1)
        payload = output.encode("utf-8")
        if payload.count(b"KCTRL_PRODUCTION_ARM") != 1:
            raise ComparisonPreparationError("La garde K1 Control n'est pas unique.")
        if payload.count(b"\nPAUSE\n") != 1 and payload.count(b"\r\nPAUSE\r\n") != 1:
            raise ComparisonPreparationError("La pause humaine avant extrusion n'est pas unique.")
        if b"SET_GCODE_OFFSET" in payload:
            raise ComparisonPreparationError("Une correction Z explicite est présente.")
        outputs[key] = payload

    robust_lines = outputs["robust_6x6"].splitlines()
    composite_lines = outputs["composite_11x11"].splitlines()
    differences = [
        index
        for index, pair in enumerate(zip(robust_lines, composite_lines))
        if pair[0] != pair[1]
    ]
    if len(robust_lines) != len(composite_lines) or len(differences) != 1:
        raise ComparisonPreparationError("Les deux sorties ne diffèrent pas d'une seule ligne.")
    difference = differences[0]
    expected_lines = {
        ARM_TEMPLATE.format(count=COUNTS["robust_6x6"]).encode(),
        ARM_TEMPLATE.format(count=COUNTS["composite_11x11"]).encode(),
    }
    if {robust_lines[difference], composite_lines[difference]} != expected_lines:
        raise ComparisonPreparationError("La différence entre sorties n'est pas la garde de profil.")
    return outputs


def write_comparison(source_path: Path, output_directory: Path) -> dict:
    source = source_path.read_bytes()
    outputs = prepare_payloads(source)
    output_directory.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema": 3,
        "source_sha256": sha256_bytes(source),
        "source_name": source_path.name,
        "accepted_z_source": "KCTRL_STATE.accepted_z_offset",
        "explicit_gcode_z_offset": None,
        "shared_contract": {
            "layers": 1,
            "geometry_mm": [260, 260, 0.2],
            "filament": "PLA Geeetech",
            "tool": "T0",
            "bed_temperature_c": 55,
            "nozzle_temperature_c": 190,
            "estimated_duration": "30m3s",
            "estimated_filament_g": 16.75,
        },
        "files": {},
    }
    for key, payload in outputs.items():
        name = OUTPUT_NAMES[key]
        (output_directory / name).write_bytes(payload)
        manifest["files"][key] = {
            "name": name,
            "profile": PROFILES[key],
            "arm_command": ARM_TEMPLATE.format(count=COUNTS[key]),
            "sha256": sha256_bytes(payload),
        }
    (output_directory / "comparison-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    manifest = write_comparison(args.source, args.output_directory)
    print(json.dumps(manifest, sort_keys=True, ensure_ascii=False))
    print("PREPARE_COMPOSITE_FIRST_LAYER_COMPARISON_V2_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
