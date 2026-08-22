#!/usr/bin/env python3
"""Build and qualify one robust 6x6 mesh from two fixed batches of three."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any


ROWS = 6
COLUMNS = 6
BATCH_SIZE = 3
MEAN_ABSOLUTE_LIMIT_MM = 0.020
RMS_LIMIT_MM = 0.025
MAXIMUM_LIMIT_MM = 0.060


def _load_matrix(path: Path) -> list[list[float]]:
    document: Any = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(document, dict) and "probed_matrix" in document:
        matrix = document["probed_matrix"]
    elif isinstance(document, dict) and isinstance(document.get("bed_mesh"), dict):
        matrix = document["bed_mesh"].get("probed_matrix")
    else:
        matrix = None
    if not isinstance(matrix, list) or len(matrix) != ROWS:
        raise ValueError(f"{path}: le mesh doit contenir {ROWS} lignes")
    result: list[list[float]] = []
    for row_index, row in enumerate(matrix):
        if not isinstance(row, list) or len(row) != COLUMNS:
            raise ValueError(f"{path}: la ligne {row_index} doit contenir {COLUMNS} valeurs")
        converted = [float(value) for value in row]
        if not all(math.isfinite(value) for value in converted):
            raise ValueError(f"{path}: valeur non finie")
        result.append(converted)
    return result


def _pointwise_median(matrices: list[list[list[float]]]) -> list[list[float]]:
    return [
        [round(statistics.median(matrix[row][column] for matrix in matrices), 6)
         for column in range(COLUMNS)]
        for row in range(ROWS)
    ]


def aggregate(matrices: list[list[list[float]]]) -> dict[str, Any]:
    if len(matrices) != BATCH_SIZE * 2:
        raise ValueError("exactement six meshes sont obligatoires")
    batch_a = _pointwise_median(matrices[:BATCH_SIZE])
    batch_b = _pointwise_median(matrices[BATCH_SIZE:])
    candidate = _pointwise_median(matrices)
    deltas = [
        abs(batch_b[row][column] - batch_a[row][column])
        for row in range(ROWS)
        for column in range(COLUMNS)
    ]
    mean_absolute = sum(deltas) / len(deltas)
    rms = math.sqrt(sum(delta * delta for delta in deltas) / len(deltas))
    maximum = max(deltas)
    accepted = (
        mean_absolute <= MEAN_ABSOLUTE_LIMIT_MM
        and rms <= RMS_LIMIT_MM
        and maximum <= MAXIMUM_LIMIT_MM
    )
    return {
        "accepted": accepted,
        "method": "two_independent_pointwise_median_batches_of_three",
        "measurements": 6,
        "batch_size": BATCH_SIZE,
        "compared_points": ROWS * COLUMNS,
        "limits_mm": {
            "mean_absolute": MEAN_ABSOLUTE_LIMIT_MM,
            "rms": RMS_LIMIT_MM,
            "maximum": MAXIMUM_LIMIT_MM,
        },
        "observed_mm": {
            "mean_absolute": round(mean_absolute, 9),
            "rms": round(rms, 9),
            "maximum": round(maximum, 9),
        },
        "batch_a_median": batch_a,
        "batch_b_median": batch_b,
        "candidate_matrix": candidate,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("meshes", nargs=6, type=Path)
    args = parser.parse_args()
    result = aggregate([_load_matrix(path) for path in args.meshes])
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
