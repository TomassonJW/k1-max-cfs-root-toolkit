#!/usr/bin/env python3
"""Pure offline domain engine for a versioned, derived K1 bed-mesh profile."""

from __future__ import annotations

import copy
import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple


BASE_DIR = Path(__file__).resolve().parent
SOURCE_PROFILE_PATH = BASE_DIR / "source-profile.json"

GRID_SIZE = 11
INTERPOLATION_MULTIPLIER = 3
INTERPOLATED_SIZE = 31
TENSION = Decimal("0.2")
ALLOWED_STEPS = (Decimal("0.005"), Decimal("0.010"))
WARNING_ABSOLUTE_DELTA = Decimal("0.050")
MAX_ABSOLUTE_DELTA = Decimal("0.100")
MAX_NEIGHBOR_JUMP = Decimal("0.080")
ZERO_MEAN_TOLERANCE = Decimal("0.000000000001")

SOURCE_ID = "k1_p001_t055_r001_n11x11"
DERIVED_PROFILE_ID = SOURCE_ID + "_tuned_v001"
DERIVED_SCHEMA = "k1-control.mesh-editor.derived-profile.v1"
PINNED_SOURCE_MATRIX_SHA256 = (
    "bee530fb9738773d1f2ccb63d47743e15776690f1bcdf92a3daac7661f0f50bf"
)

DecimalRow = Tuple[Decimal, ...]
DecimalMatrix = Tuple[DecimalRow, ...]
Cell = Tuple[int, int]


class MeshEditorError(ValueError):
    """A bounded, user-facing domain refusal."""


def _decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool):
        raise MeshEditorError(label + " doit être un nombre")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise MeshEditorError(label + " doit être un nombre fini")
    if not number.is_finite():
        raise MeshEditorError(label + " doit être un nombre fini")
    return number


def decimal_matrix(value: Any, label: str = "la matrice") -> DecimalMatrix:
    if not isinstance(value, (list, tuple)) or len(value) != GRID_SIZE:
        raise MeshEditorError(label + " doit contenir onze lignes")
    rows = []
    for row in value:
        if not isinstance(row, (list, tuple)) or len(row) != GRID_SIZE:
            raise MeshEditorError(label + " doit contenir onze colonnes")
        rows.append(tuple(_decimal(item, label) for item in row))
    return tuple(rows)


def zero_matrix() -> DecimalMatrix:
    return tuple(
        tuple(Decimal("0") for _column in range(GRID_SIZE))
        for _row in range(GRID_SIZE)
    )


def _fixed(value: Decimal, places: int) -> str:
    quantum = Decimal("1").scaleb(-places)
    rounded = value.quantize(quantum, rounding=ROUND_HALF_UP)
    if rounded == 0:
        rounded = abs(rounded)
    return format(rounded, "." + str(places) + "f")


def matrix_strings(matrix: DecimalMatrix, places: int = 12) -> List[List[str]]:
    return [[_fixed(value, places) for value in row] for row in matrix]


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def source_matrix_sha256(matrix: DecimalMatrix) -> str:
    return canonical_sha256(matrix_strings(matrix, places=6))


def load_source_document(path: Path = SOURCE_PROFILE_PATH) -> Dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema") != "k1-control.mesh-editor.source-profile.v1":
        raise MeshEditorError("le schéma de la source physique est inconnu")
    if document.get("source_id") != SOURCE_ID or document.get("immutable") is not True:
        raise MeshEditorError("la source physique immuable attendue est absente")
    matrix = decimal_matrix(document.get("points_mm"), "la source physique")
    geometry = document.get("geometry", {})
    expected_geometry = {
        "rows": GRID_SIZE,
        "columns": GRID_SIZE,
        "row_order": "min_y_to_max_y",
        "mesh_x_pps": 2,
        "mesh_y_pps": 2,
        "algorithm": "bicubic",
        "tension": "0.2",
    }
    for key, expected in expected_geometry.items():
        if geometry.get(key) != expected:
            raise MeshEditorError("la géométrie source n'est pas celle qui a été qualifiée")
    if (
        document.get("matrix_sha256") != PINNED_SOURCE_MATRIX_SHA256
        or source_matrix_sha256(matrix) != PINNED_SOURCE_MATRIX_SHA256
    ):
        raise MeshEditorError("l'empreinte de la matrice source est invalide")
    return document


def load_source_matrix(path: Path = SOURCE_PROFILE_PATH) -> DecimalMatrix:
    return decimal_matrix(load_source_document(path)["points_mm"], "la source physique")


def _cardinal_value(
    p0: Decimal,
    p1: Decimal,
    p2: Decimal,
    p3: Decimal,
    position: Decimal,
) -> Decimal:
    """Evaluate the same cardinal-Hermite form used by the reviewed Klipper mesh."""

    position_2 = position * position
    position_3 = position_2 * position
    tangent_1 = TENSION * (p2 - p0)
    tangent_2 = TENSION * (p3 - p1)
    return (
        (Decimal("2") * position_3 - Decimal("3") * position_2 + Decimal("1")) * p1
        + (position_3 - Decimal("2") * position_2 + position) * tangent_1
        + (-Decimal("2") * position_3 + Decimal("3") * position_2) * p2
        + (position_3 - position_2) * tangent_2
    )


def _interpolate_line(values: Sequence[Decimal]) -> DecimalRow:
    if len(values) != GRID_SIZE:
        raise MeshEditorError("la ligne bicubique doit contenir onze valeurs")
    result = []
    last_segment = GRID_SIZE - 2
    for generated_index in range(INTERPOLATED_SIZE):
        if generated_index == INTERPOLATED_SIZE - 1:
            segment = last_segment
            position = Decimal("1")
        else:
            segment = generated_index // INTERPOLATION_MULTIPLIER
            remainder = generated_index % INTERPOLATION_MULTIPLIER
            position = Decimal(remainder) / Decimal(INTERPOLATION_MULTIPLIER)
        p0 = values[max(0, segment - 1)]
        p1 = values[segment]
        p2 = values[segment + 1]
        p3 = values[min(GRID_SIZE - 1, segment + 2)]
        result.append(_cardinal_value(p0, p1, p2, p3, position))
    return tuple(result)


def bicubic_surface(matrix: Any) -> DecimalMatrix:
    """Return the exact 31 x 31 separable cardinal surface for this profile."""

    checked = decimal_matrix(matrix)
    with localcontext() as context:
        context.prec = 50
        horizontal = tuple(_interpolate_line(row) for row in checked)
        columns = []
        for column in range(INTERPOLATED_SIZE):
            columns.append(
                _interpolate_line(tuple(row[column] for row in horizontal))
            )
        return tuple(
            tuple(columns[column][row] for column in range(INTERPOLATED_SIZE))
            for row in range(INTERPOLATED_SIZE)
        )


def weighted_surface_mean(matrix: Any) -> Decimal:
    surface = bicubic_surface(matrix)
    with localcontext() as context:
        context.prec = 50
        total = sum((value for row in surface for value in row), Decimal("0"))
        return total / Decimal(INTERPOLATED_SIZE * INTERPOLATED_SIZE)


def normalize_requested_delta(requested_delta: Any) -> DecimalMatrix:
    requested = decimal_matrix(requested_delta, "la correction demandée")
    offset = weighted_surface_mean(requested)
    normalized = tuple(
        tuple(value - offset for value in row)
        for row in requested
    )
    residual = weighted_surface_mean(normalized)
    if abs(residual) > ZERO_MEAN_TOLERANCE:
        raise MeshEditorError("la correction n'a pas pu être normalisée à moyenne nulle")
    return normalized


def add_matrices(left: Any, right: Any) -> DecimalMatrix:
    first = decimal_matrix(left)
    second = decimal_matrix(right)
    return tuple(
        tuple(first[row][column] + second[row][column] for column in range(GRID_SIZE))
        for row in range(GRID_SIZE)
    )


def _checked_index(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MeshEditorError(label + " doit être un entier")
    if not 0 <= value < GRID_SIZE:
        raise MeshEditorError(label + " doit être compris entre 0 et 10")
    return value


def selected_cells(selection: Mapping[str, Any]) -> Tuple[Cell, ...]:
    if not isinstance(selection, Mapping):
        raise MeshEditorError("la sélection est absente")
    mode = selection.get("mode")
    if mode == "point":
        cells = (
            (
                _checked_index(selection.get("row"), "la ligne"),
                _checked_index(selection.get("column"), "la colonne"),
            ),
        )
    elif mode == "row":
        row = _checked_index(selection.get("row"), "la ligne")
        cells = tuple((row, column) for column in range(GRID_SIZE))
    elif mode == "column":
        column = _checked_index(selection.get("column"), "la colonne")
        cells = tuple((row, column) for row in range(GRID_SIZE))
    elif mode == "region":
        row_start = _checked_index(selection.get("row_start"), "la première ligne")
        row_end = _checked_index(selection.get("row_end"), "la dernière ligne")
        column_start = _checked_index(
            selection.get("column_start"), "la première colonne"
        )
        column_end = _checked_index(
            selection.get("column_end"), "la dernière colonne"
        )
        low_row, high_row = sorted((row_start, row_end))
        low_column, high_column = sorted((column_start, column_end))
        if high_row - low_row + 1 > 3 or high_column - low_column + 1 > 3:
            raise MeshEditorError("une petite zone ne peut pas dépasser 3 x 3 points")
        cells = tuple(
            (row, column)
            for row in range(low_row, high_row + 1)
            for column in range(low_column, high_column + 1)
        )
    else:
        raise MeshEditorError("le mode de sélection est inconnu")
    return tuple(sorted(cells))


def canonical_selection(selection: Mapping[str, Any]) -> Dict[str, Any]:
    cells = selected_cells(selection)
    return {
        "mode": selection["mode"],
        "cells": [{"row": row, "column": column} for row, column in cells],
    }


def correction_warnings(normalized_delta: Any) -> List[str]:
    matrix = decimal_matrix(normalized_delta, "la correction normalisée")
    warnings = []
    for row in range(GRID_SIZE):
        for column in range(GRID_SIZE):
            value = matrix[row][column]
            if abs(value) > WARNING_ABSOLUTE_DELTA:
                warnings.append(
                    "Correction élevée à X {0} / Y {1}: {2} mm".format(
                        5 + 29 * column,
                        5 + 29 * row,
                        _fixed(value, 6),
                    )
                )
    return warnings


def validate_normalized_delta(normalized_delta: Any) -> List[str]:
    matrix = decimal_matrix(normalized_delta, "la correction normalisée")
    for row in range(GRID_SIZE):
        for column in range(GRID_SIZE):
            value = matrix[row][column]
            if abs(value) > MAX_ABSOLUTE_DELTA:
                raise MeshEditorError(
                    "correction refusée à X {0} / Y {1}: delta {2} mm, "
                    "|delta| dépasse 0,100 mm".format(
                        5 + 29 * column,
                        5 + 29 * row,
                        _fixed(value, 6),
                    )
                )
            if column + 1 < GRID_SIZE:
                jump = abs(value - matrix[row][column + 1])
                if jump > MAX_NEIGHBOR_JUMP:
                    raise MeshEditorError(
                        "correction refusée entre X {0} et X {1}, Y {2}: "
                        "saut voisin {3} mm supérieur à 0,080 mm".format(
                            5 + 29 * column,
                            5 + 29 * (column + 1),
                            5 + 29 * row,
                            _fixed(jump, 6),
                        )
                    )
            if row + 1 < GRID_SIZE:
                jump = abs(value - matrix[row + 1][column])
                if jump > MAX_NEIGHBOR_JUMP:
                    raise MeshEditorError(
                        "correction refusée à X {0}, entre Y {1} et Y {2}: "
                        "saut voisin {3} mm supérieur à 0,080 mm".format(
                            5 + 29 * column,
                            5 + 29 * row,
                            5 + 29 * (row + 1),
                            _fixed(jump, 6),
                        )
                    )
    return correction_warnings(matrix)


def _non_zero_count(matrix: DecimalMatrix) -> int:
    return sum(1 for row in matrix for value in row if value != 0)


def _max_absolute(matrix: DecimalMatrix) -> Decimal:
    return max((abs(value) for row in matrix for value in row), default=Decimal("0"))


class MeshEditor:
    """In-memory editor. It never reads or writes printer state."""

    def __init__(self, source_document: Mapping[str, Any] = None) -> None:
        loaded = dict(source_document) if source_document is not None else load_source_document()
        if loaded.get("source_id") != SOURCE_ID or loaded.get("immutable") is not True:
            raise MeshEditorError("la source physique immuable attendue est absente")
        self.source_document = copy.deepcopy(loaded)
        self.source_matrix = decimal_matrix(loaded.get("points_mm"), "la source physique")
        self.source_fingerprint = source_matrix_sha256(self.source_matrix)
        if (
            loaded.get("matrix_sha256") != PINNED_SOURCE_MATRIX_SHA256
            or self.source_fingerprint != PINNED_SOURCE_MATRIX_SHA256
        ):
            raise MeshEditorError("la matrice source ne correspond pas à la fixture figée")
        self._snapshots = [zero_matrix()]
        self._events = []
        self._cursor = 0
        self._audit = []
        self._event_sequence = 0
        self._audit_sequence = 0

    @property
    def requested_delta(self) -> DecimalMatrix:
        return self._snapshots[self._cursor]

    @property
    def normalized_delta(self) -> DecimalMatrix:
        return normalize_requested_delta(self.requested_delta)

    @property
    def final_matrix(self) -> DecimalMatrix:
        return add_matrices(self.source_matrix, self.normalized_delta)

    @property
    def can_undo(self) -> bool:
        return self._cursor > 0

    @property
    def can_redo(self) -> bool:
        return self._cursor < len(self._snapshots) - 1

    def _append_audit(self, kind: str) -> None:
        self._audit_sequence += 1
        self._audit.append(
            {
                "sequence": self._audit_sequence,
                "kind": kind,
                "cursor": self._cursor,
            }
        )

    def _commit_snapshot(self, matrix: DecimalMatrix, event: Dict[str, Any]) -> None:
        if self.can_redo:
            self._snapshots = self._snapshots[: self._cursor + 1]
            self._events = self._events[: self._cursor]
        self._event_sequence += 1
        event["sequence"] = self._event_sequence
        self._events.append(event)
        self._snapshots.append(matrix)
        self._cursor += 1
        self._append_audit(event["kind"])

    def apply_correction(
        self,
        selection: Mapping[str, Any],
        direction: str,
        step_mm: Any,
    ) -> Dict[str, Any]:
        step = _decimal(step_mm, "le pas")
        if step not in ALLOWED_STEPS:
            raise MeshEditorError("le pas doit être 0,005 mm ou 0,010 mm")
        if direction == "closer":
            signed_step = -step
        elif direction == "farther":
            signed_step = step
        else:
            raise MeshEditorError("la direction doit être closer ou farther")
        cells = selected_cells(selection)
        candidate = [list(row) for row in self.requested_delta]
        for row, column in cells:
            candidate[row][column] += signed_step
        checked = decimal_matrix(candidate, "la correction demandée")
        normalized = normalize_requested_delta(checked)
        warnings = validate_normalized_delta(normalized)
        self._commit_snapshot(
            checked,
            {
                "kind": "correction",
                "direction": direction,
                "step_mm": _fixed(step, 3),
                "selection": canonical_selection(selection),
            },
        )
        return {"state": self.state(), "warnings": warnings}

    def restore_source(self) -> Dict[str, Any]:
        candidate = zero_matrix()
        self._commit_snapshot(
            candidate,
            {
                "kind": "restore_source",
                "previous_non_zero_requested_points": _non_zero_count(self.requested_delta),
            },
        )
        return self.state()

    def undo(self) -> Dict[str, Any]:
        if not self.can_undo:
            raise MeshEditorError("aucune correction à annuler")
        self._cursor -= 1
        self._append_audit("undo")
        return self.state()

    def redo(self) -> Dict[str, Any]:
        if not self.can_redo:
            raise MeshEditorError("aucune correction à rétablir")
        self._cursor += 1
        self._append_audit("redo")
        return self.state()

    def _history(self) -> List[Dict[str, Any]]:
        history = []
        for index, event in enumerate(self._events, start=1):
            item = copy.deepcopy(event)
            item["state"] = "applied" if index <= self._cursor else "redo_available"
            history.append(item)
        return history

    def state(self) -> Dict[str, Any]:
        requested = self.requested_delta
        normalized = self.normalized_delta
        final = self.final_matrix
        weighted_mean = weighted_surface_mean(normalized)
        warnings = validate_normalized_delta(normalized)
        return {
            "schema": "k1-control.mesh-editor.state.v1",
            "profile_id": DERIVED_PROFILE_ID,
            "source_id": SOURCE_ID,
            "source_fingerprint": self.source_fingerprint,
            "source_immutable": True,
            "global_z_included": False,
            "source_matrix": matrix_strings(self.source_matrix, 6),
            "requested_delta": matrix_strings(requested, 6),
            "normalized_delta": matrix_strings(normalized, 12),
            "final_matrix": matrix_strings(final, 12),
            "statistics": {
                "weighted_surface_mean_mm": _fixed(weighted_mean, 12),
                "max_absolute_normalized_delta_mm": _fixed(
                    _max_absolute(normalized), 12
                ),
                "requested_non_zero_points": _non_zero_count(requested),
                "interpolated_rows": INTERPOLATED_SIZE,
                "interpolated_columns": INTERPOLATED_SIZE,
            },
            "warnings": warnings,
            "history": self._history(),
            "audit": copy.deepcopy(self._audit),
            "cursor": self._cursor,
            "can_undo": self.can_undo,
            "can_redo": self.can_redo,
            "qualification": {
                "offline_contract": "valid",
                "physical_test": "not_run",
                "precision_ui_promotion": "blocked",
                "production": "blocked",
            },
        }

    def export_document(self) -> Dict[str, Any]:
        state = self.state()
        document = {
            "schema": DERIVED_SCHEMA,
            "profile_id": DERIVED_PROFILE_ID,
            "version": 1,
            "source": {
                "profile_id": SOURCE_ID,
                "matrix_sha256": self.source_fingerprint,
                "immutable": True,
                "capture_id": self.source_document.get("capture_id"),
                "provenance": copy.deepcopy(self.source_document.get("provenance", {})),
            },
            "geometry": {
                "rows": GRID_SIZE,
                "columns": GRID_SIZE,
                "row_order": "min_y_to_max_y",
                "min_x_mm": "5.0",
                "max_x_mm": "295.0",
                "min_y_mm": "5.0",
                "max_y_mm": "295.0",
                "mesh_x_pps": 2,
                "mesh_y_pps": 2,
                "algorithm": "bicubic",
                "tension": "0.2",
            },
            "global_z": {
                "included": False,
                "reason": "les corrections du mesh ne remplacent jamais le Z global",
            },
            "matrices_mm": {
                "source": state["source_matrix"],
                "requested_delta": state["requested_delta"],
                "normalized_delta": state["normalized_delta"],
                "final": state["final_matrix"],
            },
            "normalization": {
                "method": "zero_arithmetic_mean_on_exact_31x31_bicubic_surface",
                "weighted_surface_mean_mm": state["statistics"][
                    "weighted_surface_mean_mm"
                ],
                "tolerance_mm": _fixed(ZERO_MEAN_TOLERANCE, 12),
            },
            "guards": {
                "warning_absolute_delta_mm": "0.050",
                "refusal_absolute_delta_mm": "0.100",
                "refusal_neighbor_jump_mm": "0.080",
                "warnings": state["warnings"],
            },
            "history": {
                "events": state["history"],
                "audit": state["audit"],
                "cursor": state["cursor"],
            },
            "qualification": copy.deepcopy(state["qualification"]),
        }
        document["fingerprint"] = {
            "algorithm": "sha256",
            "canonical_json": canonical_sha256(document),
        }
        return document


def validate_derived_document(document: Mapping[str, Any]) -> None:
    if not isinstance(document, Mapping) or document.get("schema") != DERIVED_SCHEMA:
        raise MeshEditorError("le profil dérivé n'utilise pas le schéma attendu")
    if document.get("profile_id") != DERIVED_PROFILE_ID or document.get("version") != 1:
        raise MeshEditorError("le profil dérivé n'est pas la version v001 attendue")
    source = document.get("source", {})
    expected_source = load_source_matrix()
    expected_fingerprint = source_matrix_sha256(expected_source)
    if (
        source.get("profile_id") != SOURCE_ID
        or source.get("matrix_sha256") != expected_fingerprint
        or source.get("immutable") is not True
    ):
        raise MeshEditorError("la référence à la source physique a changé")
    if document.get("global_z", {}).get("included") is not False:
        raise MeshEditorError("un profil dérivé ne doit jamais inclure le Z global")
    matrices = document.get("matrices_mm", {})
    source_matrix = decimal_matrix(matrices.get("source"), "la source exportée")
    requested = decimal_matrix(
        matrices.get("requested_delta"), "la correction demandée exportée"
    )
    normalized = decimal_matrix(
        matrices.get("normalized_delta"), "la correction normalisée exportée"
    )
    final = decimal_matrix(matrices.get("final"), "la matrice finale exportée")
    if matrix_strings(source_matrix, 6) != matrix_strings(expected_source, 6):
        raise MeshEditorError("la matrice source exportée a changé")
    recalculated_normalized = normalize_requested_delta(requested)
    if matrix_strings(normalized, 12) != matrix_strings(recalculated_normalized, 12):
        raise MeshEditorError("la correction normalisée exportée est incohérente")
    recalculated_final = add_matrices(expected_source, recalculated_normalized)
    if matrix_strings(final, 12) != matrix_strings(recalculated_final, 12):
        raise MeshEditorError("la matrice finale exportée est incohérente")
    validate_normalized_delta(normalized)
    fingerprint = document.get("fingerprint", {})
    unsigned = copy.deepcopy(dict(document))
    unsigned.pop("fingerprint", None)
    if (
        fingerprint.get("algorithm") != "sha256"
        or fingerprint.get("canonical_json") != canonical_sha256(unsigned)
    ):
        raise MeshEditorError("l'empreinte canonique du profil dérivé est invalide")
