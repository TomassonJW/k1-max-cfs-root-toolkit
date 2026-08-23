#!/usr/bin/env python3
"""Compose one real dense bed mesh from bounded physical sub-grids."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


MAX_CONTACTS_PER_PASS = 36
REQUIRED_CONTEXT_FIELDS = (
    "session_id",
    "plate_id",
    "bed_target_c",
    "nozzle_target_c",
    "homing_epoch",
)


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label}: entier positif obligatoire")
    try:
        converted = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label}: entier positif obligatoire") from error
    if converted != value or converted < 1:
        raise ValueError(f"{label}: entier positif obligatoire")
    return converted


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label}: entier positif ou nul obligatoire")
    try:
        converted = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label}: entier positif ou nul obligatoire") from error
    if converted != value or converted < 0:
        raise ValueError(f"{label}: entier positif ou nul obligatoire")
    return converted


def _finite_float(value: Any, label: str) -> float:
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{label}: valeur finie obligatoire")
    return converted


def _indices(value: Any, limit: int, label: str) -> list[int]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label}: liste non vide obligatoire")
    result = [_nonnegative_int(item, label) for item in value]
    if result != sorted(set(result)):
        raise ValueError(f"{label}: indices uniques et croissants obligatoires")
    if result[0] < 0 or result[-1] >= limit:
        raise ValueError(f"{label}: indice hors matrice cible")
    return result


def compose(document: dict[str, Any]) -> dict[str, Any]:
    target = document.get("target")
    passes = document.get("passes")
    if not isinstance(target, dict) or not isinstance(passes, list) or not passes:
        raise ValueError("target et passes sont obligatoires")

    x_count = _positive_int(target.get("x_count"), "target.x_count")
    y_count = _positive_int(target.get("y_count"), "target.y_count")
    if x_count < 3 or y_count < 3:
        raise ValueError("la matrice cible doit avoir au moins 3 points par axe")

    mesh_min = target.get("mesh_min")
    mesh_max = target.get("mesh_max")
    if not isinstance(mesh_min, list) or not isinstance(mesh_max, list):
        raise ValueError("mesh_min et mesh_max sont obligatoires")
    if len(mesh_min) != 2 or len(mesh_max) != 2:
        raise ValueError("mesh_min et mesh_max doivent contenir X et Y")
    min_x, min_y = (_finite_float(value, "mesh_min") for value in mesh_min)
    max_x, max_y = (_finite_float(value, "mesh_max") for value in mesh_max)
    if min_x >= max_x or min_y >= max_y:
        raise ValueError("les bornes de mesh sont invalides")

    expected_context: dict[str, Any] | None = None
    cells: dict[tuple[int, int], float] = {}
    pass_summaries: list[dict[str, Any]] = []

    for pass_number, item in enumerate(passes, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"passage {pass_number}: objet obligatoire")
        context = item.get("context")
        if not isinstance(context, dict):
            raise ValueError(f"passage {pass_number}: contexte obligatoire")
        current_context = {field: context.get(field) for field in REQUIRED_CONTEXT_FIELDS}
        if any(value is None for value in current_context.values()):
            raise ValueError(f"passage {pass_number}: contexte incomplet")
        if int(context.get("klipper_restart_count", 0)) != 0:
            raise ValueError("aucun redémarrage Klipper n'est permis entre les sous-grilles")
        if expected_context is None:
            expected_context = current_context
        elif current_context != expected_context:
            raise ValueError("toutes les sous-grilles doivent partager la même session physique")

        x_indices = _indices(item.get("x_indices"), x_count, "x_indices")
        y_indices = _indices(item.get("y_indices"), y_count, "y_indices")
        contacts = len(x_indices) * len(y_indices)
        if contacts > MAX_CONTACTS_PER_PASS:
            raise ValueError(
                f"passage {pass_number}: {contacts} contacts dépassent la limite de 36"
            )

        matrix = item.get("matrix")
        if not isinstance(matrix, list) or len(matrix) != len(y_indices):
            raise ValueError(f"passage {pass_number}: nombre de lignes incorrect")
        for local_y, row in enumerate(matrix):
            if not isinstance(row, list) or len(row) != len(x_indices):
                raise ValueError(f"passage {pass_number}: largeur de ligne incorrecte")
            for local_x, value in enumerate(row):
                key = (y_indices[local_y], x_indices[local_x])
                if key in cells:
                    raise ValueError(f"position physique dupliquée: {key}")
                cells[key] = _finite_float(value, f"passage {pass_number} position {key}")

        pass_summaries.append(
            {
                "pass": pass_number,
                "contacts": contacts,
                "x_indices": x_indices,
                "y_indices": y_indices,
            }
        )

    expected_cells = {(y, x) for y in range(y_count) for x in range(x_count)}
    missing = sorted(expected_cells - set(cells))
    extra = sorted(set(cells) - expected_cells)
    if missing or extra:
        raise ValueError(
            f"couverture incomplète: {len(missing)} absente(s), {len(extra)} en trop"
        )

    matrix = [[cells[(y, x)] for x in range(x_count)] for y in range(y_count)]
    values = [value for row in matrix for value in row]
    algorithm = "bicubic" if x_count >= 4 and y_count >= 4 else "lagrange"
    return {
        "accepted": True,
        "method": "bounded_physical_subgrid_interlace",
        "context": expected_context,
        "pass_count": len(passes),
        "physical_points": len(values),
        "maximum_contacts_per_pass": max(summary["contacts"] for summary in pass_summaries),
        "passes": pass_summaries,
        "mesh_params": {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "x_count": x_count,
            "y_count": y_count,
            "mesh_x_pps": 2,
            "mesh_y_pps": 2,
            "algo": algorithm,
            "tension": 0.2,
        },
        "observed_mm": {
            "minimum": min(values),
            "maximum": max(values),
            "range": max(values) - min(values),
        },
        "candidate_matrix": matrix,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    document = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    result = compose(document)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
