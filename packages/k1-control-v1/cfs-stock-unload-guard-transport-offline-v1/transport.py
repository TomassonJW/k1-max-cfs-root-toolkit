#!/usr/bin/env python3
"""Deterministic offline transport seam for the stock CFS unload guard.

This module deliberately contains no network, serial, SSH, subprocess, sleep,
printer address, or remote command implementation. A scripted endpoint and a
pure response adapter are injected by tests. The two command attempts remain
single-shot even when their result becomes uncertain.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Callable, Dict, Mapping, Optional


STOCK_UNLOAD_COMMAND = "BOX_QUIT_MATERIAL"
HEATER_SHUTDOWN_COMMAND = "TURN_OFF_HEATERS"
ALLOWED_COMMANDS = (STOCK_UNLOAD_COMMAND, HEATER_SHUTDOWN_COMMAND)


class TransportFailure(RuntimeError):
    """Fail-closed transport error with a stable machine-readable code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class TransportTimeout(TransportFailure):
    """The scripted request exceeded its declared deadline."""


class TransportSchemaError(TransportFailure):
    """A query response could not be translated to the guard snapshot."""


class CommandRejected(TransportFailure):
    """A command was rejected before reaching the injected endpoint."""


@dataclass(frozen=True)
class JournalEntry:
    sequence: int
    operation: str
    command: Optional[str]
    started_s: float
    deadline_s: float
    finished_s: float
    outcome: str
    effect_certainty: str
    error_code: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _positive_finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("%s must be a positive finite number" % field)
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError("%s must be a positive finite number" % field)
    return number


def _non_negative_finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TransportFailure("endpoint_event_invalid:%s" % field)
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise TransportFailure("endpoint_event_invalid:%s" % field)
    return number


class OfflineGuardTransport:
    """Expose the exact API expected by ``StockUnloadGuard`` without I/O.

    ``endpoint.exchange`` returns a scripted mapping containing ``elapsed_s``
    and either ``payload`` or ``error``. ``adapt_snapshot`` is the already
    qualified pure K1 response adapter. No retry exists in this class.
    """

    def __init__(
        self,
        endpoint: Any,
        adapt_snapshot: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        *,
        query_timeout_s: float = 2.0,
        stock_timeout_s: float = 150.0,
        cleanup_timeout_s: float = 15.0,
    ):
        if not callable(adapt_snapshot):
            raise ValueError("adapt_snapshot must be callable")
        self.endpoint = endpoint
        self.adapt_snapshot = adapt_snapshot
        self.query_timeout_s = _positive_finite(query_timeout_s, "query_timeout_s")
        self.command_timeouts = {
            STOCK_UNLOAD_COMMAND: _positive_finite(
                stock_timeout_s, "stock_timeout_s"
            ),
            HEATER_SHUTDOWN_COMMAND: _positive_finite(
                cleanup_timeout_s, "cleanup_timeout_s"
            ),
        }
        self._time_s = 0.0
        self._sequence = 0
        self._attempted_commands: list[str] = []
        self._journal: list[JournalEntry] = []

    @property
    def attempted_commands(self) -> tuple[str, ...]:
        return tuple(self._attempted_commands)

    @property
    def journal(self) -> tuple[JournalEntry, ...]:
        return tuple(self._journal)

    @property
    def elapsed_s(self) -> float:
        return self._time_s

    def snapshot(self) -> Dict[str, Any]:
        started = self._time_s
        try:
            payload = self._exchange("query", None, self.query_timeout_s)
            adapted = self.adapt_snapshot(payload)
            if not isinstance(adapted, Mapping):
                raise TypeError("adapter result must be a mapping")
        except TransportFailure:
            raise
        except Exception as exc:
            code = "query_schema_invalid:%s" % type(exc).__name__
            self._record(
                "query",
                None,
                started,
                self.query_timeout_s,
                "schema_error",
                "none",
                code,
            )
            raise TransportSchemaError(code) from exc
        self._record(
            "query",
            None,
            started,
            self.query_timeout_s,
            "completed",
            "read_only",
            None,
        )
        return dict(adapted)

    def run_gcode(self, command: str) -> Mapping[str, Any]:
        if command not in ALLOWED_COMMANDS:
            self._reject(command, "command_not_allowlisted")
        if command in self._attempted_commands:
            self._reject(command, "duplicate_command_rejected")
        if (
            command == HEATER_SHUTDOWN_COMMAND
            and STOCK_UNLOAD_COMMAND not in self._attempted_commands
        ):
            self._reject(command, "cleanup_before_stock_rejected")
        if (
            command == STOCK_UNLOAD_COMMAND
            and HEATER_SHUTDOWN_COMMAND in self._attempted_commands
        ):
            self._reject(command, "stock_after_cleanup_rejected")

        self._attempted_commands.append(command)
        started = self._time_s
        payload = self._exchange(
            "command", command, self.command_timeouts[command]
        )
        if not isinstance(payload, Mapping):
            code = "command_response_invalid"
            self._record(
                "command",
                command,
                started,
                self.command_timeouts[command],
                "response_invalid",
                "unknown",
                code,
            )
            raise TransportFailure(code)
        self._record(
            "command",
            command,
            started,
            self.command_timeouts[command],
            "completed",
            "unproven_request_return",
            None,
        )
        return payload

    def journal_dicts(self) -> list[Dict[str, Any]]:
        return [entry.to_dict() for entry in self._journal]

    def _exchange(
        self, operation: str, command: Optional[str], timeout_s: float
    ) -> Any:
        started = self._time_s
        try:
            event = self.endpoint.exchange(operation, command)
        except Exception as exc:
            code = "endpoint_exception:%s" % type(exc).__name__
            self._record(
                operation,
                command,
                started,
                timeout_s,
                "endpoint_error",
                "unknown" if operation == "command" else "none",
                code,
            )
            raise TransportFailure(code) from exc
        if not isinstance(event, Mapping):
            code = "endpoint_event_invalid:mapping"
            self._record(
                operation,
                command,
                started,
                timeout_s,
                "endpoint_error",
                "unknown" if operation == "command" else "none",
                code,
            )
            raise TransportFailure(code)

        try:
            elapsed = _non_negative_finite(event.get("elapsed_s"), "elapsed_s")
        except TransportFailure as error:
            self._record(
                operation,
                command,
                started,
                timeout_s,
                "endpoint_error",
                "unknown" if operation == "command" else "none",
                error.code,
            )
            raise
        if elapsed > timeout_s:
            self._time_s += timeout_s
            code = "%s_timeout" % operation
            self._record(
                operation,
                command,
                started,
                timeout_s,
                "timeout",
                "unknown" if operation == "command" else "none",
                code,
            )
            raise TransportTimeout(code)

        self._time_s += elapsed
        error = event.get("error")
        if error is not None:
            code = "%s_error:%s" % (operation, str(error))
            self._record(
                operation,
                command,
                started,
                timeout_s,
                "endpoint_error",
                "unknown" if operation == "command" else "none",
                code,
            )
            raise TransportFailure(code)
        if "payload" not in event:
            code = "endpoint_event_invalid:payload"
            self._record(
                operation,
                command,
                started,
                timeout_s,
                "endpoint_error",
                "unknown" if operation == "command" else "none",
                code,
            )
            raise TransportFailure(code)
        return event["payload"]

    def _reject(self, command: Any, code: str) -> None:
        rendered = command if isinstance(command, str) else None
        self._record(
            "command",
            rendered,
            self._time_s,
            0.0,
            "rejected_before_endpoint",
            "none",
            code,
        )
        raise CommandRejected(code)

    def _record(
        self,
        operation: str,
        command: Optional[str],
        started_s: float,
        deadline_s: float,
        outcome: str,
        effect_certainty: str,
        error_code: Optional[str],
    ) -> None:
        self._sequence += 1
        self._journal.append(
            JournalEntry(
                sequence=self._sequence,
                operation=operation,
                command=command,
                started_s=round(started_s, 6),
                deadline_s=round(deadline_s, 6),
                finished_s=round(self._time_s, 6),
                outcome=outcome,
                effect_certainty=effect_certainty,
                error_code=error_code,
            )
        )
