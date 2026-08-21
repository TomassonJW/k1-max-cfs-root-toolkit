"""Offline mesh planning and qualification for K1 Control.

This module deliberately has no printer, network, G-code, or filesystem side
effect.  It converts an explicit calibration request into a bounded plan and
qualifies repeated measurements before a future G4 package may use them.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import re
from typing import Sequence


FULL_BED_BOUNDS_MM = (5.0, 5.0, 295.0, 295.0)
MIN_PROBE_COUNT = 3
MAX_PROBE_COUNT = 25
DEFAULT_REPEATABILITY_TOLERANCE_MM = 0.025
SAFE_PROFILE_TOKEN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")

MESH_PRESETS = {
    "quick": (6, 6),
    "standard": (9, 9),
    "precise": (11, 11),
    "expert": (15, 15),
}


class MeshPlanRejected(ValueError):
    """Raised when a requested calibration cannot be executed safely."""


@dataclass(frozen=True)
class MeshCalibrationPlan:
    mode: str
    plate_id: str
    temperature_band_c: str
    probe_reference_revision: str
    bounds_mm: tuple[float, float, float, float]
    probe_count: tuple[int, int]
    point_count: int
    spacing_mm: tuple[float, float]
    algorithm: str
    mesh_pps: tuple[int, int]
    profile_name: str
    persist_after_calibration: bool

    def moonraker_parameters(self) -> dict[str, str]:
        """Return inert, reviewable BED_MESH_CALIBRATE parameters.

        The caller still owns command authorization and execution.  Producing
        this mapping does not contact Moonraker or the printer.
        """

        min_x, min_y, max_x, max_y = self.bounds_mm
        count_x, count_y = self.probe_count
        pps_x, pps_y = self.mesh_pps
        return {
            "PROFILE": self.profile_name,
            "MESH_MIN": f"{min_x:.3f},{min_y:.3f}",
            "MESH_MAX": f"{max_x:.3f},{max_y:.3f}",
            "PROBE_COUNT": f"{count_x},{count_y}",
            "MESH_PPS": f"{pps_x},{pps_y}",
            "ALGORITHM": self.algorithm,
        }


@dataclass(frozen=True)
class MeshStatistics:
    rows: int
    columns: int
    minimum_mm: float
    maximum_mm: float
    range_mm: float


@dataclass(frozen=True)
class MeshRepeatability:
    accepted: bool
    tolerance_mm: float
    maximum_delta_mm: float
    mean_delta_mm: float
    compared_points: int


def plan_mesh_calibration(
    *,
    mode: str,
    plate_id: str,
    temperature_band_c: str,
    probe_reference_revision: str,
    probe_count: tuple[int, int],
    bounds_mm: tuple[float, float, float, float] = FULL_BED_BOUNDS_MM,
) -> MeshCalibrationPlan:
    if mode not in {"reference", "adaptive"}:
        raise MeshPlanRejected("mesh mode must be reference or adaptive")
    for label, value in {
        "plate_id": plate_id,
        "temperature_band_c": temperature_band_c,
        "probe_reference_revision": probe_reference_revision,
    }.items():
        if not SAFE_PROFILE_TOKEN.fullmatch(value):
            raise MeshPlanRejected(f"{label} must be a stable uppercase token")

    count_x, count_y = probe_count
    if not (
        MIN_PROBE_COUNT <= count_x <= MAX_PROBE_COUNT
        and MIN_PROBE_COUNT <= count_y <= MAX_PROBE_COUNT
    ):
        raise MeshPlanRejected(
            f"probe count must stay between {MIN_PROBE_COUNT} and {MAX_PROBE_COUNT} per axis"
        )

    min_x, min_y, max_x, max_y = (float(value) for value in bounds_mm)
    full_min_x, full_min_y, full_max_x, full_max_y = FULL_BED_BOUNDS_MM
    if min_x >= max_x or min_y >= max_y:
        raise MeshPlanRejected("mesh bounds must describe a positive area")
    if (
        min_x < full_min_x
        or min_y < full_min_y
        or max_x > full_max_x
        or max_y > full_max_y
    ):
        raise MeshPlanRejected("mesh bounds exceed the reviewed K1 Max probe area")

    spacing_x = (max_x - min_x) / (count_x - 1)
    spacing_y = (max_y - min_y) / (count_y - 1)
    algorithm = "lagrange" if count_x <= 6 and count_y <= 6 else "bicubic"
    profile_name = (
        f"K1_{plate_id}_{temperature_band_c}_{probe_reference_revision}_{count_x}X{count_y}"
        if mode == "reference"
        else "K1_ADAPTIVE_RUNTIME"
    )

    return MeshCalibrationPlan(
        mode=mode,
        plate_id=plate_id,
        temperature_band_c=temperature_band_c,
        probe_reference_revision=probe_reference_revision,
        bounds_mm=(min_x, min_y, max_x, max_y),
        probe_count=(count_x, count_y),
        point_count=count_x * count_y,
        spacing_mm=(spacing_x, spacing_y),
        algorithm=algorithm,
        mesh_pps=(2, 2),
        profile_name=profile_name,
        persist_after_calibration=mode == "reference",
    )


def plan_mesh_preset(
    preset: str,
    *,
    mode: str,
    plate_id: str,
    temperature_band_c: str,
    probe_reference_revision: str,
    bounds_mm: tuple[float, float, float, float] = FULL_BED_BOUNDS_MM,
) -> MeshCalibrationPlan:
    try:
        probe_count = MESH_PRESETS[preset]
    except KeyError as exc:
        raise MeshPlanRejected(f"unknown mesh preset: {preset}") from exc
    return plan_mesh_calibration(
        mode=mode,
        plate_id=plate_id,
        temperature_band_c=temperature_band_c,
        probe_reference_revision=probe_reference_revision,
        probe_count=probe_count,
        bounds_mm=bounds_mm,
    )


def summarize_mesh(matrix: Sequence[Sequence[float]]) -> MeshStatistics:
    rows = [tuple(float(value) for value in row) for row in matrix]
    if not rows or not rows[0]:
        raise MeshPlanRejected("mesh matrix is empty")
    columns = len(rows[0])
    if any(len(row) != columns for row in rows):
        raise MeshPlanRejected("mesh matrix is not rectangular")
    values = [value for row in rows for value in row]
    if any(not isfinite(value) for value in values):
        raise MeshPlanRejected("mesh matrix contains a non-finite value")
    minimum = min(values)
    maximum = max(values)
    return MeshStatistics(
        rows=len(rows),
        columns=columns,
        minimum_mm=minimum,
        maximum_mm=maximum,
        range_mm=maximum - minimum,
    )


def compare_repeated_meshes(
    first: Sequence[Sequence[float]],
    second: Sequence[Sequence[float]],
    *,
    tolerance_mm: float = DEFAULT_REPEATABILITY_TOLERANCE_MM,
) -> MeshRepeatability:
    if tolerance_mm <= 0:
        raise MeshPlanRejected("repeatability tolerance must be positive")
    first_stats = summarize_mesh(first)
    second_stats = summarize_mesh(second)
    if (first_stats.rows, first_stats.columns) != (second_stats.rows, second_stats.columns):
        raise MeshPlanRejected("repeated mesh matrices have different dimensions")

    deltas = [
        abs(float(first_value) - float(second_value))
        for first_row, second_row in zip(first, second)
        for first_value, second_value in zip(first_row, second_row)
    ]
    maximum_delta = max(deltas)
    return MeshRepeatability(
        accepted=maximum_delta <= tolerance_mm,
        tolerance_mm=tolerance_mm,
        maximum_delta_mm=maximum_delta,
        mean_delta_mm=sum(deltas) / len(deltas),
        compared_points=len(deltas),
    )
