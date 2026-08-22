"""Qualifie deux matrices de mesh capturees, sans acces a l'imprimante."""

from __future__ import print_function

import argparse
import json
import math
import sys


EXPECTED_ROWS = 6
EXPECTED_COLUMNS = 6
DEFAULT_TOLERANCE_MM = 0.025


def _matrix_from_document(document):
    if isinstance(document, list):
        return document
    if not isinstance(document, dict):
        raise ValueError("document JSON inattendu")
    if "probed_matrix" in document:
        return document["probed_matrix"]
    bed_mesh = document.get("bed_mesh")
    if isinstance(bed_mesh, dict) and "probed_matrix" in bed_mesh:
        return bed_mesh["probed_matrix"]
    raise ValueError("probed_matrix absente")


def _normalise(matrix):
    if not isinstance(matrix, list) or len(matrix) != EXPECTED_ROWS:
        raise ValueError("la matrice doit contenir 6 lignes")
    result = []
    for row in matrix:
        if not isinstance(row, list) or len(row) != EXPECTED_COLUMNS:
            raise ValueError("chaque ligne doit contenir 6 points")
        values = [float(value) for value in row]
        if not all(math.isfinite(value) for value in values):
            raise ValueError("la matrice contient une valeur non finie")
        result.append(values)
    return result


def compare(first, second, tolerance_mm=DEFAULT_TOLERANCE_MM):
    if tolerance_mm <= 0:
        raise ValueError("la tolerance doit etre positive")
    left = _normalise(_matrix_from_document(first))
    right = _normalise(_matrix_from_document(second))
    deltas = [
        abs(left[row][column] - right[row][column])
        for row in range(EXPECTED_ROWS)
        for column in range(EXPECTED_COLUMNS)
    ]
    maximum = max(deltas)
    return {
        "accepted": maximum <= tolerance_mm,
        "columns": EXPECTED_COLUMNS,
        "compared_points": len(deltas),
        "maximum_delta_mm": round(maximum, 6),
        "mean_delta_mm": round(sum(deltas) / len(deltas), 6),
        "method": "absolute_pointwise_delta",
        "rows": EXPECTED_ROWS,
        "tolerance_mm": tolerance_mm,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("first")
    parser.add_argument("second")
    parser.add_argument("--tolerance-mm", type=float, default=DEFAULT_TOLERANCE_MM)
    arguments = parser.parse_args(argv)
    with open(arguments.first, "r", encoding="utf-8-sig") as handle:
        first = json.load(handle)
    with open(arguments.second, "r", encoding="utf-8-sig") as handle:
        second = json.load(handle)
    result = compare(first, second, tolerance_mm=arguments.tolerance_mm)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["accepted"] else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("MESH_COMPARISON_ERROR: %s" % exc, file=sys.stderr)
        sys.exit(3)
