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
BRUSH_CONTACT_Z_MM = 2.5
BRUSH_RELEASE_Z_MM = 7.5
HOT_ROUND_TRIPS = 8
HOT_FEED_MM_MIN = 12000
LIFT_FEED_MM_MIN = 3000
BRUSH_ZIGZAG_ROUND_TRIPS = (
    ((66.0, 306.5), (99.0, 303.5)),
    ((66.0, 306.0), (99.0, 304.0)),
    ((66.0, 305.5), (99.0, 304.5)),
    ((66.0, 305.0), (99.0, 305.5)),
    ((66.0, 304.5), (99.0, 306.0)),
    ((66.0, 304.0), (99.0, 306.5)),
    ((66.0, 303.5), (99.0, 306.0)),
    ((66.0, 304.0), (99.0, 305.5)),
)


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
        "G1 X99 Y303.5 Z35 F6000",
        "G1 Z7.5 F3000",
        "G1 Z2.5 F300",
    ]
    for left, right in BRUSH_ZIGZAG_ROUND_TRIPS:
        lines.append("G1 X%.1f Y%.1f Z2.5 F%d" % (left[0], left[1], HOT_FEED_MM_MIN))
        lines.append("G1 X%.1f Y%.1f Z2.5 F%d" % (right[0], right[1], HOT_FEED_MM_MIN))
    lines.extend(
        (
            "TURN_OFF_HEATERS",
            "G1 Z7.5 F3000",
            "G1 X81 Y280 F6000",
            "G1 Z35 F3000",
            "M400",
        )
    )
    return "\n".join(lines)


def build_checkpoints(material: MaterialRecipe) -> Dict[str, str]:
    material.validate()
    cleaning_target = float(material.cleaning_target_c)
    heat_and_observe = "\n".join(
        (
            "G90",
            "G1 Z35 F3000",
            "G1 X81 Y280 F6000",
            "M104 S%.1f" % cleaning_target,
            "TEMPERATURE_WAIT SENSOR=extruder MINIMUM=%.1f MAXIMUM=%.1f"
            % (cleaning_target - 2.0, cleaning_target + 2.0),
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
        "hot_clean_eight_diagonal_round_trips_lift_exit_then_cool": hot_zigzag(),
        "final_reference_once": final_reference,
        "emergency_thermal_stop": "TURN_OFF_HEATERS",
    }
