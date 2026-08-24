#!/usr/bin/env python3
"""Compose one real dense bed mesh from bounded physical sub-grids."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


MAX_CONTACTS_PER_PASS = 36
MAX_OVERLAP_SPREAD_MM = 0.05
REQUIRED_CONTEXT_FIELDS = (
    "session_id",
    "plate_id",
    "bed_target_c",
    "nozzle_target_c",
    "homing_epoch",
)

EXPECTED_11X11_LAYOUTS = (
    {
        "name": "north_west",
        "x_indices": tuple(range(0, 6)),
        "y_indices": tuple(range(0, 6)),
        "mesh_min": (5.0, 5.0),
        "mesh_max": (150.0, 150.0),
        "probe_count": (6, 6),
        "algorithm": "lagrange",
    },
    {
        "name": "north_east",
        "x_indices": tuple(range(5, 11)),
        "y_indices": tuple(range(0, 6)),
        "mesh_min": (150.0, 5.0),
        "mesh_max": (295.0, 150.0),
        "probe_count": (6, 6),
        "algorithm": "lagrange",
    },
    {
        "name": "south_west",
        "x_indices": tuple(range(0, 6)),
        "y_indices": tuple(range(5, 11)),
        "mesh_min": (5.0, 150.0),
        "mesh_max": (150.0, 295.0),
        "probe_count": (6, 6),
        "algorithm": "lagrange",
    },
    {
        "name": "south_east",
        "x_indices": tuple(range(5, 11)),
        "y_indices": tuple(range(5, 11)),
        "mesh_min": (150.0, 150.0),
        "mesh_max": (295.0, 295.0),
        "probe_count": (6, 6),
        "algorithm": "lagrange",
    },
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


def _solve_overlap_offsets(
    pass_names: list[str],
    pass_contacts: dict[str, int],
    cells: dict[tuple[int, int], list[tuple[str, float]]],
) -> dict[str, float]:
    """Fit one additive bias per pass from shared physical positions."""

    if not pass_names:
        raise ValueError("au moins un passage est obligatoire")
    anchor = pass_names[0]
    unknowns = pass_names[1:]
    if not unknowns:
        return {anchor: 0.0}
    normal = [[0.0 for _ in unknowns] for _ in unknowns]
    vector = [0.0 for _ in unknowns]
    equations = 0
    for samples in cells.values():
        if len(samples) < 2:
            continue
        reference_name, reference_value = samples[0]
        for current_name, current_value in samples[1:]:
            row = [0.0 for _ in unknowns]
            if current_name != anchor:
                row[unknowns.index(current_name)] += 1.0
            if reference_name != anchor:
                row[unknowns.index(reference_name)] -= 1.0
            target = reference_value - current_value
            for left in range(len(unknowns)):
                vector[left] += row[left] * target
                for right in range(len(unknowns)):
                    normal[left][right] += row[left] * row[right]
            equations += 1
    if equations < len(unknowns):
        raise ValueError("les recouvrements ne relient pas toutes les sous-grilles")

    for pivot in range(len(unknowns)):
        candidate = max(
            range(pivot, len(unknowns)),
            key=lambda row_index: abs(normal[row_index][pivot]),
        )
        if abs(normal[candidate][pivot]) < 1e-12:
            raise ValueError("les recouvrements ne déterminent pas les biais de passage")
        if candidate != pivot:
            normal[pivot], normal[candidate] = normal[candidate], normal[pivot]
            vector[pivot], vector[candidate] = vector[candidate], vector[pivot]
        scale = normal[pivot][pivot]
        for column in range(pivot, len(unknowns)):
            normal[pivot][column] /= scale
        vector[pivot] /= scale
        for row_index in range(len(unknowns)):
            if row_index == pivot:
                continue
            factor = normal[row_index][pivot]
            for column in range(pivot, len(unknowns)):
                normal[row_index][column] -= factor * normal[pivot][column]
            vector[row_index] -= factor * vector[pivot]

    offsets = {anchor: 0.0, **dict(zip(unknowns, vector))}
    total_contacts = sum(pass_contacts.values())
    weighted_mean = sum(
        offsets[name] * pass_contacts[name] for name in pass_names
    ) / total_contacts
    return {name: offsets[name] - weighted_mean for name in pass_names}


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
    cells: dict[tuple[int, int], list[tuple[str, float]]] = {}
    pass_summaries: list[dict[str, Any]] = []
    pass_names: list[str] = []
    pass_contacts: dict[str, int] = {}

    for pass_number, item in enumerate(passes, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"passage {pass_number}: objet obligatoire")
        pass_name = str(item.get("name", ""))
        if not pass_name or pass_name in pass_names:
            raise ValueError(f"passage {pass_number}: nom unique obligatoire")
        pass_names.append(pass_name)
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
        pass_contacts[pass_name] = contacts

        matrix = item.get("matrix")
        if not isinstance(matrix, list) or len(matrix) != len(y_indices):
            raise ValueError(f"passage {pass_number}: nombre de lignes incorrect")
        for local_y, row in enumerate(matrix):
            if not isinstance(row, list) or len(row) != len(x_indices):
                raise ValueError(f"passage {pass_number}: largeur de ligne incorrecte")
            for local_x, value in enumerate(row):
                key = (y_indices[local_y], x_indices[local_x])
                cells.setdefault(key, []).append(
                    (
                        pass_name,
                        _finite_float(value, f"passage {pass_number} position {key}"),
                    )
                )

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

    offsets = _solve_overlap_offsets(pass_names, pass_contacts, cells)
    aligned_cells = {
        key: [value + offsets[name] for name, value in samples]
        for key, samples in cells.items()
    }
    matrix = [
        [sum(aligned_cells[(y, x)]) / len(aligned_cells[(y, x)]) for x in range(x_count)]
        for y in range(y_count)
    ]
    values = [value for row in matrix for value in row]
    physical_contacts = sum(summary["contacts"] for summary in pass_summaries)
    raw_overlap_spreads = [
        max(value for _, value in samples) - min(value for _, value in samples)
        for samples in cells.values()
        if len(samples) > 1
    ]
    overlap_spreads = [
        max(samples) - min(samples)
        for samples in aligned_cells.values()
        if len(samples) > 1
    ]
    algorithm = "bicubic" if x_count >= 4 and y_count >= 4 else "lagrange"
    return {
        "accepted": True,
        "method": "bounded_physical_square_subgrid_overlap_stitch",
        "context": expected_context,
        "pass_count": len(passes),
        "physical_points": len(values),
        "physical_contacts": physical_contacts,
        "unique_physical_points": len(cells),
        "duplicate_contacts": physical_contacts - len(cells),
        "overlap_positions": len(overlap_spreads),
        "pass_offsets_mm": offsets,
        "raw_overlap_mm": {
            "maximum_spread": max(raw_overlap_spreads) if raw_overlap_spreads else 0.0,
            "mean_spread": (
                sum(raw_overlap_spreads) / len(raw_overlap_spreads)
                if raw_overlap_spreads else 0.0
            ),
        },
        "overlap_mm": {
            "maximum_spread": max(overlap_spreads) if overlap_spreads else 0.0,
            "mean_spread": (
                sum(overlap_spreads) / len(overlap_spreads) if overlap_spreads else 0.0
            ),
        },
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


def _float_pair(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label}: paire X/Y obligatoire")
    return (
        _finite_float(value[0], label),
        _finite_float(value[1], label),
    )


def _int_pair(value: Any, label: str) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label}: paire X/Y obligatoire")
    return (
        _positive_int(value[0], label),
        _positive_int(value[1], label),
    )


def compose_11x11(document: dict[str, Any]) -> dict[str, Any]:
    """Validate the one reviewed physical recipe, then interlace its values."""

    target = document.get("target")
    passes = document.get("passes")
    if not isinstance(target, dict) or not isinstance(passes, list):
        raise ValueError("target et passes sont obligatoires")
    if (
        target.get("x_count") != 11
        or target.get("y_count") != 11
        or _float_pair(target.get("mesh_min"), "target.mesh_min") != (5.0, 5.0)
        or _float_pair(target.get("mesh_max"), "target.mesh_max") != (295.0, 295.0)
    ):
        raise ValueError("la cible composite revue doit être exactement 11x11 de 5 à 295 mm")
    if len(passes) != len(EXPECTED_11X11_LAYOUTS):
        raise ValueError("exactement quatre sous-grilles revues sont obligatoires")

    for pass_number, (item, expected) in enumerate(
        zip(passes, EXPECTED_11X11_LAYOUTS), start=1
    ):
        if not isinstance(item, dict):
            raise ValueError(f"passage {pass_number}: objet obligatoire")
        actual = {
            "name": item.get("name"),
            "x_indices": tuple(_indices(item.get("x_indices"), 11, "x_indices")),
            "y_indices": tuple(_indices(item.get("y_indices"), 11, "y_indices")),
            "mesh_min": _float_pair(item.get("mesh_min"), "mesh_min"),
            "mesh_max": _float_pair(item.get("mesh_max"), "mesh_max"),
            "probe_count": _int_pair(item.get("probe_count"), "probe_count"),
            "algorithm": str(item.get("algorithm", "")).lower(),
        }
        if actual != expected:
            raise ValueError(
                f"passage {pass_number}: recette physique {expected['name']} obligatoire"
            )

    result = compose(document)
    if (
        result["pass_count"] != 4
        or result["physical_contacts"] != 144
        or result["unique_physical_points"] != 121
        or result["duplicate_contacts"] != 23
    ):
        raise ValueError(
            "la preuve composite doit contenir quatre passages, 144 contacts et 121 positions uniques"
        )
    if result["overlap_mm"]["maximum_spread"] > MAX_OVERLAP_SPREAD_MM:
        raise ValueError("la divergence des recouvrements dépasse 0,05 mm")
    if result["mesh_params"]["algo"] != "bicubic":
        raise ValueError("le profil composite final doit être bicubique")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    document = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    result = compose_11x11(document)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
