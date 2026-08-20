"""Offline execution rules for the K1-CONTROL-V1 product contract.

The classes in this module have no network, printer, heater, movement, or file
write side effect.  They make the fail-closed rules executable before a G4
package exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Optional, Sequence

from prototype.control_state import ProductionBlocked, TemperatureController


SUPPORTED_CONTRACT_VERSION = 1
REQUIRED_JOB_FIELDS = {
    "contract_version",
    "mode",
    "plate_id",
    "bed_target_c",
    "initial_tool",
    "tool_temperature_targets_c",
    "object_bounds",
    "cleaning_profile",
    "purge_profile",
}
SAFE_TOKEN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")


@dataclass(frozen=True)
class JobContract:
    contract_version: int
    mode: str
    plate_id: str
    bed_target_c: float
    initial_tool: int
    tool_temperature_targets_c: Mapping[int, float]
    object_bounds: tuple[float, float, float, float]
    cleaning_profile: str
    purge_profile: str
    mesh_mode: str = "adaptive"

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "JobContract":
        missing = sorted(REQUIRED_JOB_FIELDS - payload.keys())
        if missing:
            raise ProductionBlocked(f"job contract is incomplete: {', '.join(missing)}")
        version = int(payload["contract_version"])
        if version != SUPPORTED_CONTRACT_VERSION:
            raise ProductionBlocked(
                f"unsupported Orca contract version {version}; expected {SUPPORTED_CONTRACT_VERSION}"
            )
        mode = str(payload["mode"])
        if mode not in {"production", "calibration", "validation_high"}:
            raise ProductionBlocked(f"unsupported job mode: {mode}")
        plate_id = str(payload["plate_id"])
        if not SAFE_TOKEN.fullmatch(plate_id):
            raise ProductionBlocked("plate_id must be a stable uppercase token")
        targets = {int(tool): float(temp) for tool, temp in payload["tool_temperature_targets_c"].items()}
        initial_tool = int(payload["initial_tool"])
        if initial_tool not in targets:
            raise ProductionBlocked("initial tool has no declared G-code temperature")
        if not targets or any(tool < 0 or tool > 7 for tool in targets):
            raise ProductionBlocked("tool targets must use T0 through T7")
        if any(temp <= 0 or temp > 350 for temp in targets.values()):
            raise ProductionBlocked("a tool temperature is outside the accepted range")
        bed_target = float(payload["bed_target_c"])
        if bed_target < 0 or bed_target > 130:
            raise ProductionBlocked("bed target is outside the accepted range")
        bounds_raw = tuple(float(value) for value in payload["object_bounds"])
        if len(bounds_raw) != 4:
            raise ProductionBlocked("object_bounds must contain min_x, min_y, max_x, max_y")
        min_x, min_y, max_x, max_y = bounds_raw
        if min_x < 0 or min_y < 0 or max_x > 300 or max_y > 300:
            raise ProductionBlocked("object bounds exceed the K1 Max bed")
        if min_x >= max_x or min_y >= max_y:
            raise ProductionBlocked("object bounds do not describe a positive area")
        cleaning = str(payload["cleaning_profile"])
        purge = str(payload["purge_profile"])
        if not SAFE_TOKEN.fullmatch(cleaning) or not SAFE_TOKEN.fullmatch(purge):
            raise ProductionBlocked("cleaning and purge profiles must be stable tokens")
        mesh_mode = str(payload.get("mesh_mode", "adaptive"))
        if mesh_mode not in {"adaptive", "reference"}:
            raise ProductionBlocked(f"unsupported mesh mode: {mesh_mode}")
        return cls(
            contract_version=version,
            mode=mode,
            plate_id=plate_id,
            bed_target_c=bed_target,
            initial_tool=initial_tool,
            tool_temperature_targets_c=targets,
            object_bounds=bounds_raw,
            cleaning_profile=cleaning,
            purge_profile=purge,
            mesh_mode=mesh_mode,
        )


@dataclass
class SafeStartController:
    sequence: Sequence[Mapping[str, Any]]
    completed: list[str] = field(default_factory=list)
    production_low_moves_armed: bool = False
    hazards: list[str] = field(default_factory=list)

    def advance(self, stage_id: str) -> None:
        if len(self.completed) >= len(self.sequence):
            raise ProductionBlocked("the start sequence is already complete")
        stage = self.sequence[len(self.completed)]
        expected = str(stage["id"])
        if stage_id != expected:
            raise ProductionBlocked(f"stage {stage_id} cannot run before {expected}")
        required = set(stage.get("requires", []))
        produced = {
            value
            for prior in self.sequence[: len(self.completed)]
            for value in prior.get("sets", [])
        }
        if not required.issubset(produced):
            missing = ", ".join(sorted(required - produced))
            raise ProductionBlocked(f"stage {stage_id} is missing prerequisites: {missing}")
        if stage.get("hazard") and not self.production_low_moves_armed:
            raise ProductionBlocked(f"production hazard blocked before arm: {stage_id}")
        self.completed.append(stage_id)
        if stage_id == "arm_production_low_moves":
            self.production_low_moves_armed = True
        if stage.get("hazard"):
            self.hazards.append(stage_id)

    def attempt_production_hazard(self, label: str) -> None:
        if not self.production_low_moves_armed:
            raise ProductionBlocked(f"production hazard blocked before arm: {label}")
        self.hazards.append(label)


@dataclass(frozen=True)
class DeploymentSnapshot:
    files: Mapping[str, str]

    @classmethod
    def from_contents(cls, contents: Mapping[str, bytes]) -> "DeploymentSnapshot":
        return cls({path: sha256(data).hexdigest() for path, data in sorted(contents.items())})

    def matches(self, other: "DeploymentSnapshot") -> bool:
        return dict(self.files) == dict(other.files)


@dataclass
class PrintRuntime:
    job: JobContract
    temperature: TemperatureController = field(init=False)
    paused_target_c: Optional[float] = None
    heaters_safe: bool = False
    ended: bool = False

    def __post_init__(self) -> None:
        self.temperature = TemperatureController(dict(self.job.tool_temperature_targets_c))

    def initial_load(self) -> float:
        return self.temperature.start_initial_tool(self.job.initial_tool)

    def equivalent_refill(self, observed_cfs_target_c: float) -> float:
        expected = self.temperature.equivalent_refill()
        matches, correction = self.temperature.check_cfs_write(observed_cfs_target_c)
        return expected if matches else correction

    def intentional_tool_change(self, next_tool: int, observed_cfs_target_c: float) -> float:
        expected = self.temperature.intentional_tool_change(next_tool)
        matches, correction = self.temperature.check_cfs_write(observed_cfs_target_c)
        return expected if matches else correction

    def pause(self) -> float:
        if self.temperature.expected_target_c is None:
            raise ProductionBlocked("pause has no active temperature target")
        self.paused_target_c = self.temperature.expected_target_c
        return self.paused_target_c

    def resume(self, observed_cfs_target_c: float) -> float:
        if self.paused_target_c is None:
            raise ProductionBlocked("resume has no saved pause target")
        self.temperature.expected_target_c = self.paused_target_c
        matches, correction = self.temperature.check_cfs_write(observed_cfs_target_c)
        self.paused_target_c = None
        return self.temperature.expected_target_c if matches else correction

    def operator_temperature(self, target_c: float) -> float:
        return self.temperature.operator_change(target_c)

    def explicit_gcode_temperature(self, tool: int, target_c: float) -> float:
        return self.temperature.gcode_change(tool, target_c)

    def cancel_or_end(self) -> None:
        self.temperature.expected_target_c = 0.0
        self.temperature.owner = "safety_end"
        self.heaters_safe = True
        self.ended = True


def load_product_sequence(contract_path: Any) -> list[Mapping[str, Any]]:
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    return list(payload["sequence"])
