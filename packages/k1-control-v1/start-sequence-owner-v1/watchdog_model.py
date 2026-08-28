from __future__ import annotations

from dataclasses import dataclass


TERMINAL_PHASES = frozenset({"idle", "aborted", "watchdog_aborted", "model_ready"})


@dataclass(frozen=True)
class WatchdogSnapshot:
    armed: bool
    phase: str
    printer_state: str
    now: float
    deadline: float


def evaluate(snapshot: WatchdogSnapshot) -> dict[str, object]:
    if not snapshot.armed:
        return {"action": "NOOP", "turn_off_heaters": False, "reschedule_s": 0}
    if snapshot.phase in TERMINAL_PHASES:
        return {"action": "DISARM", "turn_off_heaters": False, "reschedule_s": 0}
    if snapshot.printer_state != "printing" or snapshot.now >= snapshot.deadline:
        return {
            "action": "ABORT",
            "turn_off_heaters": True,
            "reschedule_s": 0,
            "terminal_phase": "watchdog_aborted",
        }
    return {"action": "RESCHEDULE", "turn_off_heaters": False, "reschedule_s": 5}
