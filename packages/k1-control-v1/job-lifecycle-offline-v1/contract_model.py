#!/usr/bin/env python3
"""Pure contract model for the complete K1 Control offline job lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Dict, Iterable, Mapping, Optional


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
TOOL_TOKEN = re.compile(r"^T(?:[0-9]|1[0-5])$")
ROUTE_TOKEN = re.compile(r"^T[12][ABCD]$")
FILAMENT_STATES = {
    "absent_confirmed",
    "engaged_known",
    "engaged_unknown",
    "transitioning",
    "fault",
}


class LifecycleError(ValueError):
    """Fail-closed lifecycle error with a stable code."""

    def __init__(self, code: str, message: Optional[str] = None):
        super().__init__(message or code)
        self.code = code


def finite(value: Any, field: str, *, minimum: Optional[float] = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LifecycleError("contract_invalid", "%s must be a finite number" % field)
    number = float(value)
    if not math.isfinite(number):
        raise LifecycleError("contract_invalid", "%s must be a finite number" % field)
    if minimum is not None and number < minimum:
        raise LifecycleError("contract_invalid", "%s is below its minimum" % field)
    return number


def require(mapping: Mapping[str, Any], fields: Iterable[str], label: str) -> None:
    missing = sorted(field for field in fields if field not in mapping)
    if missing:
        raise LifecycleError(
            "contract_invalid", "%s missing: %s" % (label, ", ".join(missing))
        )


def stable_id(value: Any, field: str) -> str:
    token = str(value)
    if not SAFE_ID.fullmatch(token):
        raise LifecycleError("contract_invalid", "%s is not a stable token" % field)
    return token


@dataclass(frozen=True)
class ToolRecipe:
    logical_tool: str
    material_id: str
    nozzle_first_c: float
    nozzle_normal_c: float
    material_min_c: float
    material_max_c: float

    def accepts(self, target_c: float) -> bool:
        return self.material_min_c <= target_c <= self.material_max_c

    def print_target(self, phase: str) -> float:
        if phase == "first_layer":
            return self.nozzle_first_c
        if phase == "normal":
            return self.nozzle_normal_c
        raise LifecycleError("print_phase_unknown")


@dataclass(frozen=True)
class TransitionRecipe:
    outgoing_tool: str
    incoming_tool: str
    unload_c: float
    load_c: float
    purge_c: float
    purge_volume_mm3: float


@dataclass(frozen=True)
class CleaningRecipe:
    material_id: str
    minimum_c: float
    nominal_c: float
    maximum_c: float
    probe_c: float
    max_hold_s: float


@dataclass(frozen=True)
class JobContract:
    contract_version: int
    job_id: str
    plate_id: str
    mesh_profile: str
    mesh_reference_revision: str
    accepted_z_revision: str
    legacy_z_offset_removed: bool
    initial_tool: str
    bed_first_c: float
    bed_normal_c: float
    tools: Mapping[str, ToolRecipe]
    transitions: Mapping[str, TransitionRecipe]
    initial_purge_volumes_mm3: Mapping[str, float]
    cleaning_recipes: Mapping[str, CleaningRecipe]
    end_policy: str

    @classmethod
    def from_mapping(
        cls, payload: Mapping[str, Any], lifecycle_contract: Mapping[str, Any]
    ) -> "JobContract":
        if not isinstance(payload, Mapping):
            raise LifecycleError("contract_invalid", "job must be an object")
        require(payload, lifecycle_contract["required_job_fields"], "job")
        version = payload["contract_version"]
        if isinstance(version, bool) or not isinstance(version, int) or version != 1:
            raise LifecycleError("contract_version_mismatch")
        job_id = stable_id(payload["job_id"], "job_id")
        plate_id = stable_id(payload["plate_id"], "plate_id")
        mesh_profile = stable_id(payload["mesh_profile"], "mesh_profile")
        mesh_reference_revision = stable_id(
            payload["mesh_reference_revision"], "mesh_reference_revision"
        )
        accepted_z_revision = stable_id(
            payload["accepted_z_revision"], "accepted_z_revision"
        )
        if payload["legacy_z_offset_removed"] is not True:
            raise LifecycleError("legacy_z_offset_not_removed")
        initial_tool = str(payload["initial_tool"])
        if not TOOL_TOKEN.fullmatch(initial_tool):
            raise LifecycleError("contract_invalid", "initial_tool is invalid")
        bed_first_c = finite(payload["bed_first_c"], "bed_first_c", minimum=0)
        bed_normal_c = finite(payload["bed_normal_c"], "bed_normal_c", minimum=0)
        if bed_first_c > 130 or bed_normal_c > 130:
            raise LifecycleError("contract_invalid", "bed target exceeds 130 C")

        tools_payload = payload["tools"]
        if not isinstance(tools_payload, Mapping) or not tools_payload:
            raise LifecycleError("contract_invalid", "tools must not be empty")
        tools: Dict[str, ToolRecipe] = {}
        for logical_tool, raw in tools_payload.items():
            logical_tool = str(logical_tool)
            if not TOOL_TOKEN.fullmatch(logical_tool) or not isinstance(raw, Mapping):
                raise LifecycleError("contract_invalid", "tool entry is invalid")
            require(
                raw,
                (
                    "material_id",
                    "nozzle_first_c",
                    "nozzle_normal_c",
                    "material_min_c",
                    "material_max_c",
                ),
                "tool %s" % logical_tool,
            )
            minimum = finite(raw["material_min_c"], "material_min_c", minimum=1)
            maximum = finite(raw["material_max_c"], "material_max_c", minimum=1)
            if maximum <= minimum:
                raise LifecycleError("contract_invalid", "material range is invalid")
            recipe = ToolRecipe(
                logical_tool=logical_tool,
                material_id=stable_id(raw["material_id"], "material_id"),
                nozzle_first_c=finite(raw["nozzle_first_c"], "nozzle_first_c"),
                nozzle_normal_c=finite(raw["nozzle_normal_c"], "nozzle_normal_c"),
                material_min_c=minimum,
                material_max_c=maximum,
            )
            if not recipe.accepts(recipe.nozzle_first_c) or not recipe.accepts(
                recipe.nozzle_normal_c
            ):
                raise LifecycleError("contract_invalid", "print target outside material range")
            tools[logical_tool] = recipe
        if initial_tool not in tools:
            raise LifecycleError("contract_invalid", "initial tool is undeclared")

        purge_payload = payload["initial_purge_volumes_mm3"]
        if not isinstance(purge_payload, Mapping):
            raise LifecycleError(
                "contract_invalid", "initial_purge_volumes_mm3 must be an object"
            )
        if set(str(key) for key in purge_payload) != set(tools):
            raise LifecycleError(
                "contract_invalid", "every tool needs one initial purge volume"
            )
        initial_purge_volumes = {
            str(logical_tool): finite(
                value, "initial_purge_volumes_mm3", minimum=0.001
            )
            for logical_tool, value in purge_payload.items()
        }

        transitions_payload = payload["transitions"]
        if not isinstance(transitions_payload, Mapping):
            raise LifecycleError("contract_invalid", "transitions must be an object")
        transitions: Dict[str, TransitionRecipe] = {}
        for key, raw in transitions_payload.items():
            key = str(key)
            if "->" not in key or not isinstance(raw, Mapping):
                raise LifecycleError("contract_invalid", "transition entry is invalid")
            outgoing, incoming = key.split("->", 1)
            if outgoing not in tools or incoming not in tools or outgoing == incoming:
                raise LifecycleError("contract_invalid", "transition tools are invalid")
            require(raw, ("unload_c", "load_c", "purge_c", "purge_volume_mm3"), key)
            transition = TransitionRecipe(
                outgoing_tool=outgoing,
                incoming_tool=incoming,
                unload_c=finite(raw["unload_c"], "unload_c"),
                load_c=finite(raw["load_c"], "load_c"),
                purge_c=finite(raw["purge_c"], "purge_c"),
                purge_volume_mm3=finite(
                    raw["purge_volume_mm3"], "purge_volume_mm3", minimum=0.001
                ),
            )
            if not tools[outgoing].accepts(transition.unload_c):
                raise LifecycleError("transition_target_out_of_bounds")
            if not tools[incoming].accepts(transition.load_c):
                raise LifecycleError("transition_target_out_of_bounds")
            if not (
                tools[outgoing].accepts(transition.purge_c)
                and tools[incoming].accepts(transition.purge_c)
            ):
                raise LifecycleError("transition_target_out_of_bounds")
            transitions[key] = transition

        cleaning_payload = payload["cleaning_recipes"]
        if not isinstance(cleaning_payload, Mapping):
            raise LifecycleError("contract_invalid", "cleaning_recipes must be an object")
        cleaning_recipes: Dict[str, CleaningRecipe] = {}
        for material_id, raw in cleaning_payload.items():
            material_id = stable_id(material_id, "cleaning material_id")
            if not isinstance(raw, Mapping):
                raise LifecycleError("contract_invalid", "cleaning recipe is invalid")
            require(raw, ("minimum_c", "nominal_c", "maximum_c", "probe_c", "max_hold_s"), material_id)
            recipe = CleaningRecipe(
                material_id=material_id,
                minimum_c=finite(raw["minimum_c"], "minimum_c"),
                nominal_c=finite(raw["nominal_c"], "nominal_c"),
                maximum_c=finite(raw["maximum_c"], "maximum_c"),
                probe_c=finite(raw["probe_c"], "probe_c"),
                max_hold_s=finite(raw["max_hold_s"], "max_hold_s", minimum=0.001),
            )
            if not (
                recipe.minimum_c
                <= recipe.nominal_c
                <= recipe.maximum_c
                and recipe.minimum_c <= recipe.probe_c <= recipe.maximum_c
            ):
                raise LifecycleError("contract_invalid", "cleaning temperatures are inconsistent")
            cleaning_recipes[material_id] = recipe
        end_policy = str(payload["end_policy"])
        if end_policy != "keep_engaged":
            raise LifecycleError("end_policy_unsupported")
        return cls(
            contract_version=version,
            job_id=job_id,
            plate_id=plate_id,
            mesh_profile=mesh_profile,
            mesh_reference_revision=mesh_reference_revision,
            accepted_z_revision=accepted_z_revision,
            legacy_z_offset_removed=True,
            initial_tool=initial_tool,
            bed_first_c=bed_first_c,
            bed_normal_c=bed_normal_c,
            tools=tools,
            transitions=transitions,
            initial_purge_volumes_mm3=initial_purge_volumes,
            cleaning_recipes=cleaning_recipes,
            end_policy=end_policy,
        )

    def transition(self, outgoing: str, incoming: str) -> TransitionRecipe:
        key = "%s->%s" % (outgoing, incoming)
        if key not in self.transitions:
            raise LifecycleError("transition_missing", key)
        return self.transitions[key]

    def bed_target(self, phase: str) -> float:
        if phase == "first_layer":
            return self.bed_first_c
        if phase == "normal":
            return self.bed_normal_c
        raise LifecycleError("print_phase_unknown")


@dataclass(frozen=True)
class MachineSnapshot:
    print_state: str
    calibration_active: bool
    plate_id: str
    filament_state: str
    engaged_tool: Optional[str]
    engaged_route: Optional[str]
    engaged_material: Optional[str]
    mapping_revision: int
    sensors_consistent: bool
    previous_material_id: Optional[str]
    homed_axes: str
    mesh_profile: str
    accepted_z_valid: bool
    accepted_z_revision: str
    effective_z_offset_mm: float
    nozzle_target_c: float
    bed_target_c: float
    toolhead_filament_present: Optional[bool]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "MachineSnapshot":
        if not isinstance(payload, Mapping):
            raise LifecycleError("machine_snapshot_invalid")
        required = (
            "print_state",
            "calibration_active",
            "plate_id",
            "filament_state",
            "engaged_tool",
            "engaged_route",
            "engaged_material",
            "mapping_revision",
            "sensors_consistent",
            "previous_material_id",
            "homed_axes",
            "mesh_profile",
            "accepted_z_valid",
            "accepted_z_revision",
            "effective_z_offset_mm",
            "nozzle_target_c",
            "bed_target_c",
            "toolhead_filament_present",
        )
        missing = [field for field in required if field not in payload]
        if missing:
            raise LifecycleError("machine_snapshot_invalid", ",".join(missing))
        filament_state = str(payload["filament_state"])
        if filament_state not in FILAMENT_STATES:
            raise LifecycleError("machine_snapshot_invalid")
        mapping_revision = payload["mapping_revision"]
        if isinstance(mapping_revision, bool) or not isinstance(mapping_revision, int) or mapping_revision < 0:
            raise LifecycleError("machine_snapshot_invalid")
        engaged_tool = payload["engaged_tool"]
        engaged_route = payload["engaged_route"]
        engaged_material = payload["engaged_material"]
        if engaged_tool is not None and not TOOL_TOKEN.fullmatch(str(engaged_tool)):
            raise LifecycleError("machine_snapshot_invalid")
        if engaged_route is not None and not ROUTE_TOKEN.fullmatch(str(engaged_route)):
            raise LifecycleError("machine_snapshot_invalid")
        present = payload["toolhead_filament_present"]
        if present is not None and not isinstance(present, bool):
            raise LifecycleError("machine_snapshot_invalid")
        if filament_state == "engaged_known" and (
            engaged_tool is None or engaged_route is None or engaged_material is None
        ):
            raise LifecycleError("machine_snapshot_invalid")
        if filament_state == "absent_confirmed" and any(
            value is not None for value in (engaged_tool, engaged_route, engaged_material)
        ):
            raise LifecycleError("machine_snapshot_invalid")
        return cls(
            print_state=str(payload["print_state"]),
            calibration_active=payload["calibration_active"] is True,
            plate_id=str(payload["plate_id"]),
            filament_state=filament_state,
            engaged_tool=None if engaged_tool is None else str(engaged_tool),
            engaged_route=None if engaged_route is None else str(engaged_route),
            engaged_material=None if engaged_material is None else str(engaged_material),
            mapping_revision=mapping_revision,
            sensors_consistent=payload["sensors_consistent"] is True,
            previous_material_id=None
            if payload["previous_material_id"] is None
            else str(payload["previous_material_id"]),
            homed_axes=str(payload["homed_axes"]),
            mesh_profile=str(payload["mesh_profile"]),
            accepted_z_valid=payload["accepted_z_valid"] is True,
            accepted_z_revision=str(payload["accepted_z_revision"]),
            effective_z_offset_mm=finite(
                payload["effective_z_offset_mm"], "effective_z_offset_mm"
            ),
            nozzle_target_c=finite(payload["nozzle_target_c"], "nozzle_target_c", minimum=0),
            bed_target_c=finite(payload["bed_target_c"], "bed_target_c", minimum=0),
            toolhead_filament_present=present,
        )
