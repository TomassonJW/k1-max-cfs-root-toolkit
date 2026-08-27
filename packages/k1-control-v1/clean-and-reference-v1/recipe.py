"""Pure builder for the reviewed CLEAN-AND-REFERENCE-V1 checkpoints.

This module has no network, process, filesystem or printer transport. It only
builds the exact scripts that a separately reviewed physical runner may send.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


BEST_PROFILE = "k1_p001_t055_r001_n11x11"
REFERENCE_NOZZLE_C = 140.0
REFERENCE_BED_C = 55.0
BRUSH_CONTACT_Z_MM = 32.0
BRUSH_RELEASE_Z_MM = 34.0
HOT_ROUND_TRIPS = 6
HOT_FEED_MM_MIN = 600
COOLING_FEED_MM_MIN = 30


class RecipeError(ValueError):
    pass


@dataclass(frozen=True)
class MaterialRecipe:
    material_id: str
    cleaning_target_c: float

    def validate(self) -> None:
        if not self.material_id or self.material_id.strip().lower() in {"unknown", "none"}:
            raise RecipeError("previous_material_required")
        if not 160.0 <= float(self.cleaning_target_c) <= 300.0:
            raise RecipeError("cleaning_target_out_of_bounds")


def hot_zigzag() -> str:
    lines = [
        "G90",
        "G1 X203 Y273 Z35 F600",
        "G1 Z32 F300",
        "G1 Y305 F600",
    ]
    for index in range(HOT_ROUND_TRIPS):
        y_value = 305 if index % 2 == 0 else 304
        lines.append("G1 X206 Y%d Z32 F%d" % (y_value, HOT_FEED_MM_MIN))
        lines.append("G1 X203 Y%d Z32 F%d" % (y_value, HOT_FEED_MM_MIN))
    lines.extend(("M104 S0", "M400"))
    return "\n".join(lines)


def cooling_z_for_temperature(temperature_c: float, cleaning_target_c: float) -> float:
    if cleaning_target_c <= REFERENCE_NOZZLE_C:
        raise RecipeError("cleaning_target_must_exceed_reference")
    progress = (cleaning_target_c - temperature_c) / (cleaning_target_c - REFERENCE_NOZZLE_C)
    progress = min(1.0, max(0.0, progress))
    raw_z = BRUSH_CONTACT_Z_MM + (BRUSH_RELEASE_Z_MM - BRUSH_CONTACT_Z_MM) * progress
    return round(raw_z * 20.0) / 20.0


def cooling_move(index: int, z_mm: float) -> str:
    if not BRUSH_CONTACT_Z_MM <= z_mm <= BRUSH_RELEASE_Z_MM:
        raise RecipeError("cooling_z_out_of_bounds")
    x_value = 206 if index % 2 == 0 else 203
    y_value = 305 if (index // 2) % 2 == 0 else 304
    return "\n".join((
        "G90",
        "G1 X%d Y%d Z%.2f F%d" % (x_value, y_value, z_mm, COOLING_FEED_MM_MIN),
        "M400",
    ))


def build_checkpoints(material: MaterialRecipe) -> Dict[str, str]:
    material.validate()
    cleaning_target = float(material.cleaning_target_c)
    heat_and_observe = "\n".join(
        (
            "G90",
            "G1 Z35 F300",
            "G1 X203 Y273 F600",
            "G1 X204.5 Y304.5 F600",
            "M104 S%.1f" % cleaning_target,
            "TEMPERATURE_WAIT SENSOR=extruder MINIMUM=%.1f MAXIMUM=%.1f"
            % (cleaning_target - 2.0, cleaning_target + 2.0),
            "M400",
        )
    )
    finish_cooling = "\n".join(
        (
            "G90",
            "G1 X203 Y304 Z34 F30",
            "TURN_OFF_HEATERS",
            "M400",
        )
    )
    final_reference = "\n".join(
        (
            "M104 S%.1f" % REFERENCE_NOZZLE_C,
            "M140 S%.1f" % REFERENCE_BED_C,
            "TEMPERATURE_WAIT SENSOR=extruder MINIMUM=138.0 MAXIMUM=142.0",
            "TEMPERATURE_WAIT SENSOR=heater_bed MINIMUM=54.0 MAXIMUM=56.0",
            "ACCURATE_G28",
            "BED_MESH_PROFILE LOAD=%s" % BEST_PROFILE,
            "TURN_OFF_HEATERS",
            "M400",
        )
    )
    return {
        "heat_and_observe_flow": heat_and_observe,
        "hot_clean_six_round_trips_and_begin_cooling": hot_zigzag(),
        "finish_sensor_controlled_cooling": finish_cooling,
        "final_reference_once": final_reference,
        "emergency_thermal_stop": "TURN_OFF_HEATERS",
    }
