#!/usr/bin/env python3
"""Émulateur déterministe et sans transport du protocole CFS observé.

Ce module ne parle à aucun périphérique. Il rejoue uniquement des trames déjà
capturées, vérifie leur lien exact avec la carte de preuves et modélise les
cas où la corrélation observée devient ambiguë.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Tuple


Frame = Tuple[int, ...]
Key = Tuple[int, int]


def _frame(value: Iterable[int]) -> Frame:
    frame = tuple(int(item) for item in value)
    if any(item < 0 or item > 255 for item in frame):
        raise ValueError("frame_byte_out_of_range")
    return frame


def _request_key(frame: Frame) -> Key:
    if len(frame) < 4 or frame[2] != 0xFF or frame[1] != len(frame) - 1:
        raise ValueError("invalid_observed_request_envelope")
    return frame[0], frame[3]


def _response_key(frame: Frame) -> Key:
    if len(frame) < 6 or frame[0] != 0xF7 or frame[2] != len(frame) - 3:
        raise ValueError("invalid_observed_response_envelope")
    return frame[1], frame[4]


def _index_frames(items: Iterable[Mapping[str, Any]]) -> Dict[str, Frame]:
    return {str(item["evidence_id"]): _frame(item["frame"]) for item in items}


class OfflineProtocolEmulator:
    """Petit automate de preuve. Il ne possède volontairement aucun `send`."""

    def __init__(self, contract: Mapping[str, Any], evidence: Mapping[str, Any]):
        self.contract = deepcopy(dict(contract))
        self.evidence = deepcopy(dict(evidence))
        self.request_frames = _index_frames(evidence["observed_request_frames"])
        self.response_frames = _index_frames(evidence["observed_response_frames"])
        self.route_observations = {
            str(item["evidence_id"]): deepcopy(dict(item))
            for item in evidence["observed_route_actions"]
        }
        self.method_only = {
            str(item["symbol"]): deepcopy(dict(item))
            for item in evidence["method_name_only"]
        }
        self.now_ms = 0
        self.connection_generation = 1
        self.mapping_revision = 1
        self.pending: MutableMapping[Key, Dict[str, Any]] = {}
        self.quarantined: MutableMapping[Key, str] = {}
        self.routes: MutableMapping[str, Dict[str, Any]] = {}
        self.trace: List[Dict[str, Any]] = []

    def _record(self, code: str, **details: Any) -> Dict[str, Any]:
        event = {"code": code, "at_ms": self.now_ms, **details}
        self.trace.append(event)
        return event

    def observe_route(
        self,
        evidence_id: str,
        logical_tool: str,
        address: int,
        slot: str,
        numeric_slot: int,
    ) -> Dict[str, Any]:
        proof = self.route_observations.get(evidence_id)
        claimed = {
            "logical_tool": logical_tool,
            "address": int(address),
            "slot": slot,
            "numeric_slot": int(numeric_slot),
        }
        if proof is None or any(proof.get(key) != value for key, value in claimed.items()):
            return self._record(
                "route_not_tied_to_exact_evidence",
                logical_tool=logical_tool,
            )
        self.routes[logical_tool] = {
            **claimed,
            "mapping_revision": self.mapping_revision,
            "connection_generation": self.connection_generation,
            "scope": "captured_observation_only_not_production_proof",
        }
        return self._record(
            "route_observed_evidence_only",
            logical_tool=logical_tool,
            address=int(address),
            slot=slot,
        )

    def replay_request(
        self,
        evidence_id: str,
        frame: Iterable[int],
        request_id: str,
        timeout_ms: int = 1000,
    ) -> Dict[str, Any]:
        candidate = _frame(frame)
        exact = self.request_frames.get(evidence_id)
        if exact is None or exact != candidate:
            return self._record(
                "request_not_tied_to_exact_evidence",
                evidence_id=evidence_id,
            )
        try:
            key = _request_key(candidate)
        except ValueError as exc:
            return self._record(str(exc), evidence_id=evidence_id)
        if key in self.pending:
            return self._record(
                "duplicate_pending_key",
                address=key[0],
                command=key[1],
            )
        if key in self.quarantined:
            return self._record(
                "correlation_key_quarantined",
                address=key[0],
                command=key[1],
            )
        if timeout_ms <= 0:
            return self._record("invalid_timeout", request_id=request_id)
        self.pending[key] = {
            "request_id": request_id,
            "evidence_id": evidence_id,
            "deadline_ms": self.now_ms + int(timeout_ms),
            "connection_generation": self.connection_generation,
        }
        return self._record(
            "offline_request_registered",
            request_id=request_id,
            address=key[0],
            command=key[1],
        )

    def receive_response(self, evidence_id: str, frame: Iterable[int]) -> Dict[str, Any]:
        candidate = _frame(frame)
        exact = self.response_frames.get(evidence_id)
        if exact is None or exact != candidate:
            return self._record(
                "response_not_tied_to_exact_evidence",
                evidence_id=evidence_id,
            )
        try:
            key = _response_key(candidate)
        except ValueError as exc:
            return self._record(str(exc), evidence_id=evidence_id)
        pending = self.pending.get(key)
        if pending is None:
            if key in self.quarantined:
                return self._record(
                    "late_response_quarantined",
                    address=key[0],
                    command=key[1],
                )
            return self._record(
                "uncorrelated_event_not_ack",
                address=key[0],
                command=key[1],
            )
        if self.now_ms > pending["deadline_ms"]:
            self.pending.pop(key)
            self.quarantined[key] = "deadline_elapsed"
            return self._record(
                "late_response_quarantined",
                address=key[0],
                command=key[1],
            )
        if pending["connection_generation"] != self.connection_generation:
            self.pending.pop(key)
            self.quarantined[key] = "connection_generation_changed"
            return self._record(
                "response_generation_mismatch",
                address=key[0],
                command=key[1],
            )
        self.pending.pop(key)
        state = candidate[3]
        if state != 0:
            self.quarantined[key] = "device_error_state"
            return self._record(
                "device_error_state",
                address=key[0],
                command=key[1],
                state=state,
            )
        return self._record(
            "offline_response_matched",
            request_id=pending["request_id"],
            address=key[0],
            command=key[1],
        )

    def advance(self, milliseconds: int) -> Dict[str, Any]:
        if milliseconds < 0:
            return self._record("invalid_time_advance")
        self.now_ms += int(milliseconds)
        expired = [
            key
            for key, item in self.pending.items()
            if self.now_ms > item["deadline_ms"]
        ]
        for key in expired:
            self.pending.pop(key)
            self.quarantined[key] = "response_timeout"
        if expired:
            return self._record(
                "response_timeout",
                expired_keys=[list(key) for key in sorted(expired)],
            )
        return self._record("offline_clock_advanced")

    def reconnect(self) -> Dict[str, Any]:
        for key in list(self.pending):
            self.quarantined[key] = "reconnect_with_request_pending"
        invalidated = sorted(self.routes)
        self.pending.clear()
        self.connection_generation += 1
        self.mapping_revision += 1
        return self._record(
            "reconnect_invalidates_pending_and_routes",
            invalidated_routes=invalidated,
            connection_generation=self.connection_generation,
            mapping_revision=self.mapping_revision,
        )

    def revise_route(self) -> Dict[str, Any]:
        self.mapping_revision += 1
        return self._record(
            "route_revision_changed",
            mapping_revision=self.mapping_revision,
        )

    def classify_method(self, symbol: str) -> Dict[str, Any]:
        if symbol in self.method_only:
            return self._record(
                "method_name_only_not_callable",
                symbol=symbol,
            )
        return self._record("unknown_method_not_callable", symbol=symbol)

    def evaluate_effect(self, command: int, logical_tool: str) -> Dict[str, Any]:
        blockers: List[str] = []
        if self.contract["transport"] != "absent":
            raise ValueError("offline_contract_must_not_expose_transport")
        blockers.append("transport_absent")
        if int(command) not in self.contract["callable_messages"]:
            blockers.append("command_not_in_callable_allowlist")
        if self.evidence["envelope"]["integrity_or_checksum"] == "unknown":
            blockers.append("frame_integrity_rule_unqualified")
        if self.evidence["ownership"]["stock_owner_exclusion"] != "proven":
            blockers.append("stock_owner_exclusion_unproven")
        route = self.routes.get(logical_tool)
        if route is None:
            blockers.append("route_missing")
        else:
            if route["mapping_revision"] != self.mapping_revision:
                blockers.append("route_revision_stale")
            if route["connection_generation"] != self.connection_generation:
                blockers.append("route_connection_stale")
        return self._record(
            "effect_blocked_safe",
            command=int(command),
            logical_tool=logical_tool,
            blockers=blockers,
        )

    def result(self) -> Dict[str, Any]:
        last_code = self.trace[-1]["code"] if self.trace else "no_action"
        blocked_codes = {
            "correlation_key_quarantined",
            "device_error_state",
            "duplicate_pending_key",
            "effect_blocked_safe",
            "invalid_observed_request_envelope",
            "invalid_observed_response_envelope",
            "late_response_quarantined",
            "method_name_only_not_callable",
            "request_not_tied_to_exact_evidence",
            "response_not_tied_to_exact_evidence",
            "response_timeout",
            "route_not_tied_to_exact_evidence",
            "uncorrelated_event_not_ack",
            "unknown_method_not_callable",
        }
        return {
            "verdict": "blocked_safe" if last_code in blocked_codes else "pass_offline",
            "last_code": last_code,
            "pending_count": len(self.pending),
            "quarantined_count": len(self.quarantined),
            "connection_generation": self.connection_generation,
            "mapping_revision": self.mapping_revision,
            "routes": deepcopy(dict(self.routes)),
            "trace": deepcopy(self.trace),
        }


def _contains(actual: Any, expected: Any) -> bool:
    if isinstance(expected, Mapping):
        return isinstance(actual, Mapping) and all(
            key in actual and _contains(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return actual == expected
    return actual == expected


def run_scenario(
    contract: Mapping[str, Any],
    evidence: Mapping[str, Any],
    scenario: Mapping[str, Any],
) -> Dict[str, Any]:
    emulator = OfflineProtocolEmulator(contract, evidence)
    for step in scenario["steps"]:
        action = step["action"]
        if action == "observe_route":
            emulator.observe_route(
                step["evidence_id"],
                step["logical_tool"],
                step["address"],
                step["slot"],
                step["numeric_slot"],
            )
        elif action == "replay_request":
            emulator.replay_request(
                step["evidence_id"],
                step["frame"],
                step["request_id"],
                step.get("timeout_ms", 1000),
            )
        elif action == "receive_response":
            emulator.receive_response(step["evidence_id"], step["frame"])
        elif action == "advance":
            emulator.advance(step["milliseconds"])
        elif action == "reconnect":
            emulator.reconnect()
        elif action == "revise_route":
            emulator.revise_route()
        elif action == "classify_method":
            emulator.classify_method(step["symbol"])
        elif action == "evaluate_effect":
            emulator.evaluate_effect(step["command"], step["logical_tool"])
        else:
            raise ValueError("unknown_scenario_action:%s" % action)
    return emulator.result()


def run_matrix(
    contract: Mapping[str, Any],
    evidence: Mapping[str, Any],
    matrix: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    results = []
    for scenario in matrix["scenarios"]:
        result = run_scenario(contract, evidence, scenario)
        results.append(
            {
                "id": scenario["id"],
                "passed": _contains(result, scenario["expect"]),
                "result": result,
            }
        )
    return results


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    package = Path(__file__).resolve().parent
    contract = _load(package / "contract.json")
    evidence = _load(package / "evidence-map.json")
    matrix = _load(package / "scenarios.json")
    results = run_matrix(contract, evidence, matrix)
    passed = sum(1 for item in results if item["passed"])
    print("CFS_MINIMAL_OWNER_PROTOCOL_V1 %d/%d" % (passed, len(results)))
    for item in results:
        print("%s %s" % ("OK" if item["passed"] else "KO", item["id"]))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
