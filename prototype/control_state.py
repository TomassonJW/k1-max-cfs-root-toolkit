"""Pure offline state model for K1-CONTROL-V1.

This module has no printer, network, Moonraker, Klipper, or filesystem side
effect. It exists to make the product rules executable before any deployment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Mapping, Optional


class ProductionBlocked(RuntimeError):
    """Raised when the current state is not qualified for production."""


@dataclass(frozen=True)
class MachineContext:
    plate_id: str
    bed_temperature_band_c: str
    nozzle_id: str
    nozzle_diameter_mm: float
    probe_reference_revision: str
    relevant_config_hashes: Mapping[str, str]

    def signature(self) -> str:
        payload = {
            "bed_temperature_band_c": self.bed_temperature_band_c,
            "nozzle_diameter_mm": self.nozzle_diameter_mm,
            "nozzle_id": self.nozzle_id,
            "plate_id": self.plate_id,
            "probe_reference_revision": self.probe_reference_revision,
            "relevant_config_hashes": dict(sorted(self.relevant_config_hashes.items())),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CalibrationRecord:
    offset_mm: float
    context_signature: str
    plate_id: str
    bed_temperature_band_c: str
    nozzle_id: str
    nozzle_diameter_mm: float
    probe_reference_revision: str
    accepted_at: str


@dataclass
class CalibrationSession:
    context: MachineContext
    seed_offset_mm: float
    current_offset_mm: float


@dataclass
class ZCalibrationController:
    accepted: Optional[CalibrationRecord] = None
    history: list[CalibrationRecord] = field(default_factory=list)
    invalid_reason: Optional[str] = None
    session: Optional[CalibrationSession] = None

    def start_session(self, context: MachineContext, *, seed_offset_mm: float) -> None:
        if self.session is not None:
            raise ValueError("a calibration session is already active")
        self.session = CalibrationSession(
            context=context,
            seed_offset_mm=seed_offset_mm,
            current_offset_mm=seed_offset_mm,
        )

    def adjust(self, delta_mm: float) -> float:
        if self.session is None:
            raise ValueError("live Z adjustment requires an active calibration session")
        self.session.current_offset_mm = round(self.session.current_offset_mm + delta_mm, 4)
        return self.session.current_offset_mm

    def commit(self, *, accepted_at: Optional[str] = None) -> CalibrationRecord:
        if self.session is None:
            raise ValueError("nothing to commit outside a calibration session")
        if self.accepted is not None:
            self.history.append(self.accepted)
        context = self.session.context
        record = CalibrationRecord(
            offset_mm=self.session.current_offset_mm,
            context_signature=context.signature(),
            plate_id=context.plate_id,
            bed_temperature_band_c=context.bed_temperature_band_c,
            nozzle_id=context.nozzle_id,
            nozzle_diameter_mm=context.nozzle_diameter_mm,
            probe_reference_revision=context.probe_reference_revision,
            accepted_at=accepted_at or datetime.now(timezone.utc).isoformat(),
        )
        self.accepted = record
        self.invalid_reason = None
        self.session = None
        return record

    def cancel(self) -> None:
        self.session = None

    def invalidate(self, reason: str) -> None:
        if not reason.strip():
            raise ValueError("an invalidation reason is required")
        self.invalid_reason = reason
        self.session = None

    def production_offset(self, context: MachineContext) -> float:
        if self.accepted is None:
            raise ProductionBlocked("no accepted Z calibration")
        if self.invalid_reason is not None:
            raise ProductionBlocked(self.invalid_reason)
        if self.accepted.context_signature != context.signature():
            raise ProductionBlocked("the accepted Z calibration does not match this context")
        return self.accepted.offset_mm

    def on_print_end(self) -> None:
        """A normal print end must not modify accepted calibration."""

    def on_restart(self) -> None:
        """A restart must not modify accepted calibration."""

    def restore_previous(self) -> CalibrationRecord:
        if not self.history:
            raise ValueError("no previous calibration is available")
        if self.accepted is not None:
            current = self.accepted
        else:
            current = None
        restored = self.history.pop()
        if current is not None:
            self.history.append(current)
        self.accepted = restored
        self.invalid_reason = None
        self.session = None
        return restored


@dataclass(frozen=True)
class MeshProfile:
    profile_id: str
    plate_id: str
    bed_temperature_band_c: str
    probe_reference_revision: str
    status: str = "accepted"

    def matches(self, context: MachineContext) -> bool:
        return (
            self.status == "accepted"
            and self.plate_id == context.plate_id
            and self.bed_temperature_band_c == context.bed_temperature_band_c
            and self.probe_reference_revision == context.probe_reference_revision
        )


@dataclass(frozen=True)
class MeshDecision:
    mode: str
    profile_id: Optional[str]
    bounds: Optional[tuple[float, float, float, float]]
    persist_after_job: bool


@dataclass
class MeshCatalog:
    profiles: list[MeshProfile] = field(default_factory=list)

    def reference_for(self, context: MachineContext) -> MeshDecision:
        matches = [profile for profile in self.profiles if profile.matches(context)]
        if len(matches) != 1:
            raise ProductionBlocked("no unique accepted mesh matches plate, temperature, and reference")
        return MeshDecision(
            mode="reference",
            profile_id=matches[0].profile_id,
            bounds=None,
            persist_after_job=True,
        )

    def adaptive_for(self, bounds: tuple[float, float, float, float]) -> MeshDecision:
        min_x, min_y, max_x, max_y = bounds
        if min_x >= max_x or min_y >= max_y:
            raise ValueError("adaptive mesh bounds must describe a positive area")
        return MeshDecision(
            mode="adaptive",
            profile_id=None,
            bounds=bounds,
            persist_after_job=False,
        )


@dataclass
class TemperatureController:
    tool_targets_c: dict[int, float]
    active_tool: Optional[int] = None
    expected_target_c: Optional[float] = None
    owner: str = "none"

    def start_initial_tool(self, tool: int) -> float:
        return self._apply_tool_target(tool, owner="gcode")

    def equivalent_refill(self) -> float:
        if self.expected_target_c is None:
            raise ProductionBlocked("equivalent refill has no active temperature target")
        return self.expected_target_c

    def intentional_tool_change(self, next_tool: int) -> float:
        return self._apply_tool_target(next_tool, owner="gcode")

    def operator_change(self, target_c: float) -> float:
        if target_c < 0:
            raise ValueError("temperature cannot be negative")
        self.expected_target_c = target_c
        self.owner = "operator"
        return target_c

    def gcode_change(self, tool: int, target_c: float) -> float:
        if target_c < 0:
            raise ValueError("temperature cannot be negative")
        self.tool_targets_c[tool] = target_c
        self.active_tool = tool
        self.expected_target_c = target_c
        self.owner = "gcode"
        return target_c

    def check_cfs_write(self, observed_target_c: float) -> tuple[bool, float]:
        if self.expected_target_c is None:
            raise ProductionBlocked("no expected temperature target is available")
        return observed_target_c == self.expected_target_c, self.expected_target_c

    def _apply_tool_target(self, tool: int, *, owner: str) -> float:
        if tool not in self.tool_targets_c:
            raise ProductionBlocked(f"tool T{tool} has no G-code temperature target")
        self.active_tool = tool
        self.expected_target_c = self.tool_targets_c[tool]
        self.owner = owner
        return self.expected_target_c
