#!/usr/bin/env python3
"""Evaluate a recorded CFS boundary without contacting the printer."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


THERMAL_TOLERANCE_C = 0.1
Z_TOLERANCE_MM = 0.000001

Z_MUTATING_COMMANDS = (
    re.compile(r"^G28(?:\s|$)", re.IGNORECASE),
    re.compile(r"^SET_GCODE_OFFSET(?:\s|$)", re.IGNORECASE),
    re.compile(r"^Z_OFFSET_APPLY_PROBE(?:\s|$)", re.IGNORECASE),
    re.compile(r"^BED_MESH_CLEAR(?:\s|$)", re.IGNORECASE),
    re.compile(r"^BED_MESH_PROFILE(?:\s|$)", re.IGNORECASE),
)
BED_COMMANDS = (
    re.compile(r"^M140(?:\s|$)", re.IGNORECASE),
    re.compile(r"^M190(?:\s|$)", re.IGNORECASE),
)
NOZZLE_COMMANDS = (
    re.compile(r"^M104(?:\s|$)", re.IGNORECASE),
    re.compile(r"^M109(?:\s|$)", re.IGNORECASE),
)


class TraceError(ValueError):
    """Raised when a trace cannot support a deterministic verdict."""


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TraceError(f"{field} must be a finite number")
    converted = float(value)
    if not math.isfinite(converted):
        raise TraceError(f"{field} must be a finite number")
    return converted


def _same_number(left: Any, right: Any, tolerance: float, field: str) -> bool:
    return abs(_number(left, field) - _number(right, field)) <= tolerance


def _require_keys(mapping: Dict[str, Any], keys: Iterable[str], prefix: str) -> None:
    missing = [key for key in keys if key not in mapping]
    if missing:
        raise TraceError(f"{prefix} missing: {', '.join(missing)}")


def _violation(
    code: str,
    event_index: int,
    expected: Any,
    actual: Any,
    action: str,
) -> Dict[str, Any]:
    return {
        "code": code,
        "event_index": event_index,
        "expected": expected,
        "actual": actual,
        "action": action,
    }


def evaluate_trace(contract: Dict[str, Any], trace: Dict[str, Any]) -> Dict[str, Any]:
    """Return a fail-closed verdict for one bounded CFS phase."""

    _require_keys(contract, ("contract_id", "allowed_phases"), "contract")
    _require_keys(trace, ("trace_id", "phase", "expected", "events"), "trace")
    if trace["phase"] not in contract["allowed_phases"]:
        raise TraceError(f"unsupported phase: {trace['phase']}")
    if not isinstance(trace["events"], list) or not trace["events"]:
        raise TraceError("trace.events must be a non-empty list")

    expected = trace["expected"]
    required_state = (
        "nozzle_target_c",
        "bed_target_c",
        "accepted_z_offset_mm",
        "homing_origin_z_mm",
        "mesh_profile",
        "homed_axes",
    )
    _require_keys(expected, required_state, "trace.expected")

    violations: List[Dict[str, Any]] = []
    evidence_gaps: List[Dict[str, Any]] = []
    snapshots = 0
    for index, event in enumerate(trace["events"]):
        if not isinstance(event, dict) or "kind" not in event:
            raise TraceError(f"event {index} has no kind")

        if event["kind"] == "snapshot":
            snapshots += 1
            _require_keys(event, required_state, f"event {index}")

            comparisons: Tuple[Tuple[str, float, str, str], ...] = (
                (
                    "nozzle_target_c",
                    THERMAL_TOLERANCE_C,
                    "nozzle_target_override",
                    "abort_cfs_and_set_heater_targets_zero",
                ),
                (
                    "bed_target_c",
                    THERMAL_TOLERANCE_C,
                    "bed_target_override",
                    "abort_cfs_and_set_heater_targets_zero",
                ),
                (
                    "accepted_z_offset_mm",
                    Z_TOLERANCE_MM,
                    "accepted_z_offset_changed",
                    "stop_without_blind_z_restore",
                ),
                (
                    "homing_origin_z_mm",
                    Z_TOLERANCE_MM,
                    "homing_origin_z_changed",
                    "stop_without_blind_z_restore",
                ),
            )
            for field, tolerance, code, action in comparisons:
                if event[field] is None:
                    evidence_gaps.append({"event_index": index, "field": field})
                    continue
                if not _same_number(event[field], expected[field], tolerance, field):
                    violations.append(
                        _violation(code, index, expected[field], event[field], action)
                    )

            for field, code in (
                ("mesh_profile", "mesh_profile_changed"),
                ("homed_axes", "homed_axes_changed"),
            ):
                if event[field] is None:
                    evidence_gaps.append({"event_index": index, "field": field})
                    continue
                if event[field] != expected[field]:
                    violations.append(
                        _violation(
                            code,
                            index,
                            expected[field],
                            event[field],
                            "stop_without_blind_z_restore",
                        )
                    )

        elif event["kind"] == "gcode":
            command = str(event.get("command", "")).strip()
            if not command:
                raise TraceError(f"event {index} has an empty command")
            if any(pattern.search(command) for pattern in BED_COMMANDS):
                violations.append(
                    _violation(
                        "cfs_bed_command",
                        index,
                        "no bed command from CFS",
                        command,
                        "abort_cfs_and_set_heater_targets_zero",
                    )
                )
            if any(pattern.search(command) for pattern in NOZZLE_COMMANDS):
                violations.append(
                    _violation(
                        "cfs_nozzle_command",
                        index,
                        "no nozzle command inside a CFS boundary",
                        command,
                        "abort_cfs_and_set_heater_targets_zero",
                    )
                )
            if any(pattern.search(command) for pattern in Z_MUTATING_COMMANDS):
                violations.append(
                    _violation(
                        "forbidden_geometry_command",
                        index,
                        "no homing, Z or mesh mutation inside a CFS boundary",
                        command,
                        "stop_without_blind_z_restore",
                    )
                )
        else:
            raise TraceError(f"event {index} has unsupported kind: {event['kind']}")

    if snapshots < 2:
        raise TraceError("at least two snapshots are required")

    unique_violations = []
    seen = set()
    for item in violations:
        marker = (
            item["code"],
            item["event_index"],
            json.dumps(item["actual"], sort_keys=True),
        )
        if marker not in seen:
            seen.add(marker)
            unique_violations.append(item)

    if unique_violations:
        thermal = any(
            "target" in item["code"]
            or item["code"] in {"cfs_bed_command", "cfs_nozzle_command"}
            for item in unique_violations
        )
        geometry = any(
            item["code"]
            in {
                "accepted_z_offset_changed",
                "homing_origin_z_changed",
                "mesh_profile_changed",
                "homed_axes_changed",
                "forbidden_geometry_command",
            }
            for item in unique_violations
        )
        safe_actions = []
        if thermal:
            safe_actions.append("set_nozzle_and_bed_targets_zero")
        if geometry:
            safe_actions.append("do_not_restore_z_automatically")
        safe_actions.append("block_print_resume")
        verdict = "block_driver_primitive"
    elif evidence_gaps:
        safe_actions = ["block_until_complete_evidence"]
        verdict = "inconclusive"
    else:
        safe_actions = ["allow_next_guarded_phase_only"]
        verdict = "pass_offline_trace_only"

    return {
        "contract_id": contract["contract_id"],
        "trace_id": trace["trace_id"],
        "phase": trace["phase"],
        "verdict": verdict,
        "violations": unique_violations,
        "evidence_gaps": evidence_gaps,
        "safe_actions": safe_actions,
        "authorizes_printer_mutation": False,
        "authorizes_print_resume": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path)
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    trace = json.loads(args.trace.read_text(encoding="utf-8"))
    try:
        result = evaluate_trace(contract, trace)
    except TraceError as exc:
        print(json.dumps({"verdict": "inconclusive", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["verdict"] == "pass_offline_trace_only":
        return 0
    if result["verdict"] == "inconclusive":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
