#!/usr/bin/env python3
"""Analyse hors imprimante un binaire box_wrapper et une trace d'incident."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


class AuditError(ValueError):
    """La preuve fournie ne permet pas le verdict contractuel."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_elf(path: Path) -> Dict[str, Any]:
    """Lit uniquement l'en-tête ELF nécessaire, sans charger le module."""

    with path.open("rb") as stream:
        header = stream.read(52)
    if len(header) < 20 or header[:4] != b"\x7fELF":
        raise AuditError("binary is not an ELF file")
    elf_class = header[4]
    data_encoding = header[5]
    if elf_class not in (1, 2):
        raise AuditError(f"unsupported ELF class: {elf_class}")
    if data_encoding not in (1, 2):
        raise AuditError(f"unsupported ELF encoding: {data_encoding}")
    endian = "<" if data_encoding == 1 else ">"
    elf_type, machine = struct.unpack_from(endian + "HH", header, 16)
    return {
        "sha256": sha256(path),
        "size": path.stat().st_size,
        "elf_class": elf_class,
        "endianness": "little" if data_encoding == 1 else "big",
        "type": elf_type,
        "machine": machine,
        "loaded_or_executed": False,
    }


def _missing_markers(text: str, markers: Iterable[str]) -> list[str]:
    return [marker for marker in markers if marker not in text]


def _first_line(lines: list[str], marker: str) -> Optional[int]:
    for index, line in enumerate(lines, start=1):
        if marker in line:
            return index
    return None


def analyze(
    contract: Dict[str, Any],
    strings_text: str,
    incident_text: str,
    binary_path: Optional[Path] = None,
) -> Dict[str, Any]:
    required = contract["required_binary_strings"]
    missing_strings = {
        group: _missing_markers(strings_text, markers)
        for group, markers in required.items()
    }
    missing_strings = {
        group: markers for group, markers in missing_strings.items() if markers
    }

    incident_lines = incident_text.splitlines()
    marker_lines = {
        name: _first_line(incident_lines, marker)
        for name, marker in contract["incident_markers"].items()
    }
    missing_incident = [name for name, line in marker_lines.items() if line is None]

    binary = None
    binary_mismatches: Dict[str, Dict[str, Any]] = {}
    if binary_path is not None:
        binary = inspect_elf(binary_path)
        for field, expected in contract["expected_binary"].items():
            actual = binary.get(field)
            if actual != expected:
                binary_mismatches[field] = {"expected": expected, "actual": actual}

    ordered_markers = (
        "request",
        "geometry_unhomed",
        "geometry_move",
        "material_temperature",
        "computed_flush_temperature",
        "observed_nozzle_target",
        "requested_flush_temperature",
        "safe_position",
        "script_finished",
        "heat_shutdown",
        "robust_profile_reloaded",
    )
    order_values = [marker_lines[name] for name in ordered_markers]
    ordered = all(
        left is not None and right is not None and left < right
        for left, right in zip(order_values, order_values[1:])
    )

    evidence_complete = (
        not missing_strings
        and not missing_incident
        and ordered
        and not binary_mismatches
    )
    primitive_verdicts = [
        {"command": command, "verdict": verdict}
        for command, verdict in contract["primitive_policy"].items()
    ]

    if evidence_complete:
        verdict = "block_stock_sequence_no_callable_primitive"
        reason = (
            "The observed load primitive owned temperature and geometry; the "
            "two following primitives were not isolated by this trace."
        )
    else:
        verdict = "inconclusive_block"
        reason = "Evidence is missing, unordered, or does not match the pinned binary."

    return {
        "contract_id": contract["contract_id"],
        "verdict": verdict,
        "reason": reason,
        "binary": binary,
        "binary_mismatches": binary_mismatches,
        "missing_binary_strings": missing_strings,
        "incident_marker_lines": marker_lines,
        "missing_incident_markers": missing_incident,
        "incident_markers_ordered": ordered,
        "primitive_verdicts": primitive_verdicts,
        "adapter": contract["adapter_policy"],
        "authorizes_printer_mutation": False,
        "authorizes_physical_test": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path)
    parser.add_argument("strings", type=Path)
    parser.add_argument("incident_log", type=Path)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    try:
        result = analyze(
            contract,
            args.strings.read_text(encoding="utf-8", errors="replace"),
            args.incident_log.read_text(encoding="utf-8", errors="replace"),
            args.binary,
        )
    except (AuditError, KeyError, OSError, json.JSONDecodeError) as exc:
        result = {
            "verdict": "inconclusive_block",
            "error": str(exc),
            "authorizes_printer_mutation": False,
            "authorizes_physical_test": False,
        }
        exit_code = 2
    else:
        exit_code = 1 if result["verdict"].startswith("block_") else 2

    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
