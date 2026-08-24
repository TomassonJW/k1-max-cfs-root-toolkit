#!/usr/bin/env python3
"""Prepare the two exact first-layer G-codes used to compare 6x6 and 11x11."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Optional


SOURCE_SHA256 = "50b54577a4b8a76a0bb5fb2b48e915d1dc6ea9e5bb87aa1f32404c559a54f856"
START_COMMAND = "START_PRINT EXTRUDER_TEMP=190 BED_TEMP=55"
LEGACY_Z_COMMAND = (
    "SET_GCODE_OFFSET Z=0.27 MOVE=1 MOVE_SPEED=5 ; POSTPROC global start Z offset "
    "after START_PRINT"
)
MARKER = "; K1_CONTROL_COMPOSITE_FIRST_LAYER_COMPARISON_V1"
BLOCKED_REASON = (
    "COMPOSITE-FIRST-LAYER-COMPARISON-V1 est close KO: l'ancien offset Orca "
    "+0,27 mm rend la première couche physiquement invalide."
)
PROFILES = {
    "robust_6x6": "k1_p001_t055_r001_n06x06",
    "composite_11x11": "k1_p001_t055_r001_n11x11",
}
OUTPUT_NAMES = {
    "robust_6x6": "K1-COMPARE-01-ROBUST-6X6.gcode",
    "composite_11x11": "K1-COMPARE-02-COMPOSITE-11X11.gcode",
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
        "G28",
        "T0",
        START_COMMAND,
        LEGACY_Z_COMMAND,
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
        LEGACY_Z_COMMAND,
    ]:
        raise ComparisonPreparationError("La séquence G28/T0/START_PRINT/Z a changé.")
    if any(line.lstrip().startswith("BED_MESH_") for line in lines):
        raise ComparisonPreparationError("Le G-code source contient déjà une commande Bed Mesh.")
    return text, newline


def prepare_payloads(source: bytes, expected_sha256: Optional[str] = None) -> dict[str, bytes]:
    if expected_sha256 is None:
        expected_sha256 = SOURCE_SHA256
    text, newline = _validate_source(source, expected_sha256)
    raise ComparisonPreparationError(BLOCKED_REASON)


def _prepare_historical_payloads(text: str, newline: str) -> dict[str, bytes]:
    """Retained only to make the rejected V1 transformation reviewable in tests."""
    anchor = START_COMMAND + newline
    outputs: dict[str, bytes] = {}
    for key, profile in PROFILES.items():
        insertion = (
            anchor
            + MARKER
            + newline
            + f'BED_MESH_PROFILE LOAD="{profile}"'
            + newline
        )
        outputs[key] = text.replace(anchor, insertion, 1).encode("utf-8")

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
        f'BED_MESH_PROFILE LOAD="{PROFILES["robust_6x6"]}"'.encode(),
        f'BED_MESH_PROFILE LOAD="{PROFILES["composite_11x11"]}"'.encode(),
    }
    if {robust_lines[difference], composite_lines[difference]} != expected_lines:
        raise ComparisonPreparationError("La différence entre sorties n'est pas le profil Bed Mesh.")
    return outputs


def write_comparison(source_path: Path, output_directory: Path) -> dict:
    source = source_path.read_bytes()
    outputs = prepare_payloads(source)
    output_directory.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema": 1,
        "source_sha256": sha256_bytes(source),
        "source_name": source_path.name,
        "shared_contract": {
            "layers": 1,
            "geometry_mm": [200, 200, 0.2],
            "filament": "PLA Geeetech",
            "tool": "T0",
            "bed_temperature_c": 55,
            "nozzle_temperature_c": 190,
            "legacy_z_offset_mm": 0.27,
            "estimated_duration": "18m44s",
            "estimated_filament_g": 9.91,
        },
        "files": {},
    }
    for key, payload in outputs.items():
        name = OUTPUT_NAMES[key]
        (output_directory / name).write_bytes(payload)
        manifest["files"][key] = {
            "name": name,
            "profile": PROFILES[key],
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
    print("PREPARE_COMPOSITE_FIRST_LAYER_COMPARISON_V1_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
