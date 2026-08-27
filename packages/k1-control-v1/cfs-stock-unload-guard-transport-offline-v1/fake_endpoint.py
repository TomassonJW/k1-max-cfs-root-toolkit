#!/usr/bin/env python3
"""Scripted endpoint used only by the offline guard transport matrix."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Optional, Sequence


class EndpointScriptError(RuntimeError):
    """The simulator was called outside the declared deterministic script."""


class ScriptedEndpoint:
    def __init__(self, events: Sequence[Mapping[str, Any]]):
        self._events = [deepcopy(dict(event)) for event in events]
        self.calls: list[Dict[str, Optional[str]]] = []

    @property
    def remaining(self) -> int:
        return len(self._events)

    def exchange(self, operation: str, command: Optional[str]) -> Dict[str, Any]:
        if not self._events:
            raise EndpointScriptError("script_exhausted")
        event = self._events.pop(0)
        expected_operation = event.pop("operation", None)
        expected_command = event.pop("command", None)
        if operation != expected_operation:
            raise EndpointScriptError(
                "operation_mismatch:%s!=%s" % (operation, expected_operation)
            )
        if command != expected_command:
            raise EndpointScriptError(
                "command_mismatch:%s!=%s" % (command, expected_command)
            )
        self.calls.append({"operation": operation, "command": command})
        return event
