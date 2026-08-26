#!/usr/bin/env python3
"""Deterministic fake API for the offline stock-unload guard."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping


class FakeApiError(RuntimeError):
    pass


class FakePrinterApi:
    """Replay synthetic snapshots and record commands without any transport."""

    def __init__(self, scenario: Mapping[str, Any]):
        self.scenario = deepcopy(dict(scenario))
        self.commands: List[str] = []
        self._phase = "preflight"
        self._index = 0
        self._last = deepcopy(self.scenario["initial"])

    def snapshot(self) -> Dict[str, Any]:
        if self._phase == "preflight":
            self._last = deepcopy(self.scenario["initial"])
            return deepcopy(self._last)
        key = "after_stock" if self._phase == "stock" else "after_cleanup"
        snapshots = self.scenario.get(key, [])
        if snapshots:
            selected = snapshots[min(self._index, len(snapshots) - 1)]
            self._index += 1
            self._last = deepcopy(selected)
        return deepcopy(self._last)

    def run_gcode(self, script: str) -> Dict[str, str]:
        self.commands.append(script)
        if script == "BOX_QUIT_MATERIAL":
            self._phase = "stock"
            self._index = 0
            error = self.scenario.get("stock_error")
            if error:
                raise FakeApiError(str(error))
            return deepcopy(self.scenario.get("stock_ack", {"result": "ok"}))
        if script == "TURN_OFF_HEATERS":
            self._phase = "cleanup"
            self._index = 0
            error = self.scenario.get("cleanup_error")
            if error:
                raise FakeApiError(str(error))
            return deepcopy(self.scenario.get("cleanup_ack", {"result": "ok"}))
        raise FakeApiError("unexpected command: %s" % script)
