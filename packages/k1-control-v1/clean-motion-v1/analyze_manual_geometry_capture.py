from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path


MISSION = "G4-K1-CONTROL-CLEAN-MOTION-V1-MANUAL-GEOMETRY-ANALYSIS"


class AnalysisError(RuntimeError):
    pass


def load_samples(path: Path) -> tuple[list[dict], list[dict]]:
    samples = []
    controls = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AnalysisError(f"invalid_json_line:{line_number}:{exc}") from exc
        if value.get("record") == "sample":
            samples.append(value)
        elif value.get("record") == "control":
            controls.append(value)
    if not samples:
        raise AnalysisError("no_samples")
    return samples, controls


def within(first: list[float], second: list[float], xy_tolerance: float, z_tolerance: float) -> bool:
    return (
        abs(first[0] - second[0]) <= xy_tolerance
        and abs(first[1] - second[1]) <= xy_tolerance
        and abs(first[2] - second[2]) <= z_tolerance
    )


def stable_dwells(
    samples: list[dict],
    minimum_seconds: float = 6.0,
    xy_tolerance: float = 0.03,
    z_tolerance: float = 0.02,
) -> list[dict]:
    groups = []
    current = [samples[0]]
    anchor = samples[0]["gcode_xyz"]
    for sample in samples[1:]:
        if within(sample["gcode_xyz"], anchor, xy_tolerance, z_tolerance):
            current.append(sample)
            continue
        groups.append(current)
        current = [sample]
        anchor = sample["gcode_xyz"]
    groups.append(current)

    dwells = []
    for group in groups:
        duration = float(group[-1]["elapsed_s"]) - float(group[0]["elapsed_s"])
        if duration < minimum_seconds:
            continue
        axes = list(zip(*(sample["gcode_xyz"] for sample in group)))
        physical_axes = list(zip(*(sample["physical_xyz"] for sample in group)))
        dwells.append(
            {
                "order": len(dwells) + 1,
                "start_s": round(float(group[0]["elapsed_s"]), 3),
                "end_s": round(float(group[-1]["elapsed_s"]), 3),
                "duration_s": round(duration, 3),
                "sample_count": len(group),
                "gcode_xyz_median": [round(statistics.median(axis), 5) for axis in axes],
                "physical_xyz_median": [round(statistics.median(axis), 5) for axis in physical_axes],
            }
        )
    return dwells


def analyze(path: Path) -> dict:
    samples, controls = load_samples(path)
    events = [item.get("event") for item in controls]
    if "ready" not in events:
        raise AnalysisError("ready_record_missing")
    if "aborted" in events:
        raise AnalysisError("capture_aborted")
    if "complete" not in events:
        raise AnalysisError("complete_record_missing")
    dwells = stable_dwells(samples)
    short_dwells = stable_dwells(samples, minimum_seconds=2.0)
    initial_xyz = samples[0]["gcode_xyz"]
    first_movement_s = None
    for sample in samples[1:]:
        if not within(sample["gcode_xyz"], initial_xyz, 0.03, 0.02):
            first_movement_s = round(float(sample["elapsed_s"]), 3)
            break
    axes = list(zip(*(sample["gcode_xyz"] for sample in samples)))
    return {
        "schema": 1,
        "mission": MISSION,
        "status": "MANUAL_GEOMETRY_ANALYSIS_OK",
        "source": str(path),
        "sample_count": len(samples),
        "first_movement_s": first_movement_s,
        "gcode_extrema": {
            "minimum_xyz": [round(min(axis), 5) for axis in axes],
            "maximum_xyz": [round(max(axis), 5) for axis in axes],
        },
        "stable_dwell_count": len(dwells),
        "stable_dwells": dwells,
        "short_dwell_count": len(short_dwells),
        "short_dwells": short_dwells,
        "interpretation": {
            "automatic_corner_labels_assigned": False,
            "expected_operator_order": ["Xminus_Yminus", "Xplus_Yminus", "Xplus_Yplus", "Xminus_Yplus"],
            "human_review_required": True,
        },
        "effects": {"printer_connection": False, "gcode": False, "remote_write": False},
    }


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        print(json.dumps({"status": "MANUAL_GEOMETRY_ANALYSIS_KO", "error": "capture_path_required"}))
        return 2
    try:
        result = analyze(Path(arguments[0]))
    except Exception as exc:
        print(json.dumps({"status": "MANUAL_GEOMETRY_ANALYSIS_KO", "error": f"{type(exc).__name__}:{exc}"}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
