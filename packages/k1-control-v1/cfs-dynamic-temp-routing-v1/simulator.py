#!/usr/bin/env python3
"""Deterministic offline simulator for phase-owned CFS temperatures.

This module has no printer, network, subprocess, serial, G-code, heater, or
motion transport. It validates contracts and recorded synthetic boundaries.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


TOOL_TOKEN = re.compile(r"^T(?:[0-9]|1[0-5])$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
PROTECTED_FIELDS = (
    "accepted_z_offset_mm",
    "homing_origin_z_mm",
    "mesh_profile",
    "homed_axes",
)
THERMAL_TOLERANCE_C = 0.001
Z_TOLERANCE_MM = 0.000001


class RoutingError(ValueError):
    """Fail-closed routing error with a stable machine-readable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RoutingError("job_contract_invalid", "%s must be a finite number" % field)
    number = float(value)
    if not math.isfinite(number):
        raise RoutingError("job_contract_invalid", "%s must be a finite number" % field)
    return number


def _require(mapping: Mapping[str, Any], fields: Iterable[str], label: str) -> None:
    missing = [field for field in fields if field not in mapping]
    if missing:
        raise RoutingError(
            "job_contract_invalid",
            "%s missing: %s" % (label, ", ".join(missing)),
        )


def _same_number(left: Any, right: Any, tolerance: float) -> bool:
    try:
        return abs(float(left) - float(right)) <= tolerance
    except (TypeError, ValueError):
        return False


@dataclass(frozen=True)
class ToolRecipe:
    logical_tool: str
    material_id: str
    nozzle_first_c: float
    nozzle_normal_c: float
    material_min_c: float
    material_max_c: float

    def phase_target(self, phase: str) -> float:
        if phase == "first_layer":
            return self.nozzle_first_c
        if phase == "normal":
            return self.nozzle_normal_c
        raise RoutingError("phase_unknown", "unsupported print phase: %s" % phase)

    def accepts(self, target_c: float) -> bool:
        return self.material_min_c <= target_c <= self.material_max_c


@dataclass(frozen=True)
class TransitionRecipe:
    outgoing_tool: str
    incoming_tool: str
    unload_c: float
    load_c: float
    purge_c: float


@dataclass(frozen=True)
class JobContract:
    contract_version: int
    job_id: str
    bed_first_c: float
    bed_normal_c: float
    tools: Mapping[str, ToolRecipe]
    transitions: Mapping[str, TransitionRecipe]

    @classmethod
    def from_mapping(
        cls, payload: Mapping[str, Any], routing_contract: Mapping[str, Any]
    ) -> "JobContract":
        _require(payload, routing_contract["required_job_fields"], "job")
        version = payload["contract_version"]
        if isinstance(version, bool) or not isinstance(version, int) or version != 1:
            raise RoutingError("job_contract_invalid", "unsupported contract_version")
        job_id = str(payload["job_id"])
        if not SAFE_ID.fullmatch(job_id):
            raise RoutingError("job_contract_invalid", "job_id is not a stable token")
        bed_first = _finite_number(payload["bed_first_c"], "bed_first_c")
        bed_normal = _finite_number(payload["bed_normal_c"], "bed_normal_c")
        if bed_first < 0 or bed_normal < 0:
            raise RoutingError("job_contract_invalid", "bed targets cannot be negative")

        tools_payload = payload["tools"]
        if not isinstance(tools_payload, dict) or not tools_payload:
            raise RoutingError("job_contract_invalid", "job.tools must not be empty")
        tools: Dict[str, ToolRecipe] = {}
        for logical_tool, raw in tools_payload.items():
            if not TOOL_TOKEN.fullmatch(str(logical_tool)) or not isinstance(raw, dict):
                raise RoutingError("job_contract_invalid", "invalid logical tool")
            _require(raw, routing_contract["required_tool_fields"], "tool %s" % logical_tool)
            material_id = str(raw["material_id"])
            if not SAFE_ID.fullmatch(material_id):
                raise RoutingError("job_contract_invalid", "invalid material_id")
            minimum = _finite_number(raw["material_min_c"], "material_min_c")
            maximum = _finite_number(raw["material_max_c"], "material_max_c")
            first = _finite_number(raw["nozzle_first_c"], "nozzle_first_c")
            normal = _finite_number(raw["nozzle_normal_c"], "nozzle_normal_c")
            if minimum <= 0 or maximum <= minimum:
                raise RoutingError("job_contract_invalid", "invalid material temperature range")
            recipe = ToolRecipe(str(logical_tool), material_id, first, normal, minimum, maximum)
            if not recipe.accepts(first) or not recipe.accepts(normal):
                raise RoutingError("job_contract_invalid", "print target outside material range")
            tools[str(logical_tool)] = recipe

        transitions_payload = payload["transitions"]
        if not isinstance(transitions_payload, dict):
            raise RoutingError("job_contract_invalid", "job.transitions must be an object")
        transitions: Dict[str, TransitionRecipe] = {}
        for key, raw in transitions_payload.items():
            if not isinstance(raw, dict) or "->" not in str(key):
                raise RoutingError("job_contract_invalid", "invalid transition entry")
            outgoing, incoming = str(key).split("->", 1)
            if outgoing not in tools or incoming not in tools or outgoing == incoming:
                raise RoutingError("job_contract_invalid", "transition tools are invalid")
            _require(
                raw,
                routing_contract["required_transition_fields"],
                "transition %s" % key,
            )
            transition = TransitionRecipe(
                outgoing,
                incoming,
                _finite_number(raw["unload_c"], "unload_c"),
                _finite_number(raw["load_c"], "load_c"),
                _finite_number(raw["purge_c"], "purge_c"),
            )
            if not tools[outgoing].accepts(transition.unload_c):
                raise RoutingError("transition_target_out_of_bounds", "unload target rejected")
            if not tools[incoming].accepts(transition.load_c):
                raise RoutingError("transition_target_out_of_bounds", "load target rejected")
            if not (
                tools[outgoing].accepts(transition.purge_c)
                and tools[incoming].accepts(transition.purge_c)
            ):
                raise RoutingError("transition_target_out_of_bounds", "purge target rejected")
            transitions[str(key)] = transition
        return cls(version, job_id, bed_first, bed_normal, tools, transitions)

    def bed_target(self, phase: str) -> float:
        if phase == "first_layer":
            return self.bed_first_c
        if phase == "normal":
            return self.bed_normal_c
        raise RoutingError("phase_unknown", "unsupported print phase: %s" % phase)

    def transition(self, outgoing: str, incoming: str) -> TransitionRecipe:
        key = "%s->%s" % (outgoing, incoming)
        if key not in self.transitions:
            raise RoutingError("transition_missing", "missing explicit transition %s" % key)
        return self.transitions[key]


def select_architecture(options: Mapping[str, Any]) -> Dict[str, Any]:
    """Return the unique design that satisfies every declared capability."""

    required = list(options["required_capabilities"])
    capable = []
    for option in options["options"]:
        capabilities = option.get("capabilities", {})
        if all(capabilities.get(name) is True for name in required):
            capable.append(option["id"])
    selected = options["decision"]
    if capable != [selected]:
        raise RoutingError(
            "architecture_ambiguous",
            "expected one capable architecture, got %s" % capable,
        )
    selected_option = next(item for item in options["options"] if item["id"] == selected)
    if selected_option.get("deployable_now") is not False:
        raise RoutingError("architecture_unsafe", "offline design cannot be deployable now")
    return {
        "selected": selected,
        "capable_options": capable,
        "deployment_candidate": False,
        "authorizes_printer_mutation": False,
    }


class RoutingSimulator:
    def __init__(self, routing_contract: Mapping[str, Any], job: JobContract, state: Mapping[str, Any]):
        self.contract = routing_contract
        self.job = job
        self.state: Dict[str, Any] = deepcopy(dict(state))
        self.used_route_proofs: set[str] = set()
        self.trace: List[Dict[str, Any]] = []
        self.effects = 0
        self.cut_count = 0
        self.unload_count = 0
        self.resume_armed = True
        self.blind_z_restore = False
        self.cancelled = False
        self._validate_initial_state()

    def _validate_initial_state(self) -> None:
        _require(
            self.state,
            (
                "phase",
                "mapping_revision",
                "filament_state",
                "engaged_tool",
                "nozzle_target_c",
                "bed_target_c",
                "target_owner",
                "protected",
            ),
            "initial_state",
        )
        if self.state["phase"] not in {"first_layer", "normal"}:
            raise RoutingError("phase_unknown", "initial phase is unsupported")
        if isinstance(self.state["mapping_revision"], bool) or not isinstance(
            self.state["mapping_revision"], int
        ):
            raise RoutingError("route_revision_invalid", "mapping revision must be an integer")
        protected = self.state["protected"]
        if not isinstance(protected, dict):
            raise RoutingError("protected_state_incomplete", "protected state must be an object")
        missing = [field for field in PROTECTED_FIELDS if protected.get(field) is None]
        if missing:
            raise RoutingError(
                "protected_state_incomplete",
                "protected state missing: %s" % ", ".join(missing),
            )
        engaged = self.state["engaged_tool"]
        if engaged is not None and engaged not in self.job.tools:
            raise RoutingError("engaged_tool_unknown", "engaged tool is not declared")
        _finite_number(self.state["nozzle_target_c"], "initial nozzle target")
        _finite_number(self.state["bed_target_c"], "initial bed target")
        self.state["paused_snapshot"] = None

    def _fail_safe(self, error: RoutingError) -> Dict[str, Any]:
        self.state["nozzle_target_c"] = 0.0
        self.state["bed_target_c"] = 0.0
        self.state["target_owner"] = "safe_stop"
        self.resume_armed = False
        self.trace.append({"kind": "safe_stop", "code": error.code})
        return self.result("blocked_safe", error.code, str(error))

    def result(self, verdict: str, reason_code: Optional[str], detail: str) -> Dict[str, Any]:
        return {
            "contract_id": self.contract["contract_id"],
            "job_id": self.job.job_id,
            "verdict": verdict,
            "reason_code": reason_code,
            "detail": detail,
            "final_state": {
                "phase": self.state["phase"],
                "engaged_tool": self.state["engaged_tool"],
                "filament_state": self.state["filament_state"],
                "nozzle_target_c": self.state["nozzle_target_c"],
                "bed_target_c": self.state["bed_target_c"],
                "target_owner": self.state["target_owner"],
                "protected": deepcopy(self.state["protected"]),
                "mapping_revision": self.state["mapping_revision"],
            },
            "effects": self.effects,
            "cut_count": self.cut_count,
            "unload_count": self.unload_count,
            "route_proofs_used": sorted(self.used_route_proofs),
            "resume_armed": self.resume_armed,
            "blind_z_restore": self.blind_z_restore,
            "trace": deepcopy(self.trace),
            "authorizes_printer_mutation": False,
            "deployment_candidate": False,
            "printer_transport": False,
        }

    def run(self, events: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        try:
            for event in events:
                self._apply(event)
                if self.cancelled:
                    return self.result("cancelled_safe", None, "explicit cancellation")
        except RoutingError as error:
            return self._fail_safe(error)
        return self.result("pass_offline", None, "all synthetic boundaries passed")

    def _apply(self, event: Mapping[str, Any]) -> None:
        kind = event.get("kind")
        if kind == "set_phase":
            self._set_phase(str(event.get("phase")))
        elif kind == "operator_target":
            self._operator_target(event.get("target_c"))
        elif kind == "cfs_boundary":
            self._boundary(event)
        elif kind == "pause":
            self._pause()
        elif kind == "resume":
            self._resume()
        elif kind == "reconnect_cfs":
            self.state["mapping_revision"] += 1
            self.state["filament_state"] = "engaged_unknown"
            self.trace.append({"kind": kind, "mapping_revision": self.state["mapping_revision"]})
        elif kind == "cancel":
            self.state["nozzle_target_c"] = 0.0
            self.state["bed_target_c"] = 0.0
            self.state["target_owner"] = "explicit_cancel"
            self.resume_armed = False
            self.cancelled = True
            self.trace.append({"kind": kind})
        else:
            raise RoutingError("event_unknown", "unsupported event kind: %s" % kind)

    def _set_phase(self, phase: str) -> None:
        if phase not in {"first_layer", "normal"}:
            raise RoutingError("phase_unknown", "unsupported print phase: %s" % phase)
        self.state["phase"] = phase
        self.state["bed_target_c"] = self.job.bed_target(phase)
        engaged = self.state["engaged_tool"]
        if engaged is not None:
            self.state["nozzle_target_c"] = self.job.tools[engaged].phase_target(phase)
            self.state["target_owner"] = "job_contract"
        self.trace.append({"kind": "set_phase", "phase": phase})

    def _operator_target(self, value: Any) -> None:
        engaged = self.state["engaged_tool"]
        if engaged is None:
            raise RoutingError("operator_target_without_tool", "operator target needs an engaged tool")
        target = _finite_number(value, "operator target")
        if not self.job.tools[engaged].accepts(target):
            raise RoutingError("operator_target_out_of_bounds", "operator target rejected")
        self.state["nozzle_target_c"] = target
        self.state["target_owner"] = "operator"
        self.trace.append({"kind": "operator_target", "target_c": target})

    def _pause(self) -> None:
        if self.state["paused_snapshot"] is not None:
            raise RoutingError("pause_state_invalid", "already paused")
        self.state["paused_snapshot"] = {
            "nozzle_target_c": self.state["nozzle_target_c"],
            "bed_target_c": self.state["bed_target_c"],
            "target_owner": self.state["target_owner"],
        }
        self.trace.append({"kind": "pause", "cfs_effect": False})

    def _resume(self) -> None:
        snapshot = self.state["paused_snapshot"]
        if snapshot is None:
            raise RoutingError("pause_state_invalid", "resume has no pause snapshot")
        self.state.update(snapshot)
        self.state["paused_snapshot"] = None
        self.trace.append({"kind": "resume", "cfs_effect": False})

    def _boundary(self, event: Mapping[str, Any]) -> None:
        operation = str(event.get("operation"))
        rules = self.contract["operations"]
        if operation not in rules:
            raise RoutingError("operation_unknown", "unsupported CFS operation")
        rule = rules[operation]
        outgoing = event.get("outgoing_tool")
        incoming = event.get("incoming_tool")
        active = self.state["engaged_tool"]
        expected_nozzle = self._resolve_target(rule["nozzle_source"], active, outgoing, incoming)
        expected_bed = float(self.state["bed_target_c"])
        route_tool = self._route_tool(rule["route_role"], active, outgoing, incoming)
        route = event.get("route")
        self._verify_route(route, route_tool)

        observed = event.get("observed")
        if not isinstance(observed, dict):
            raise RoutingError("boundary_evidence_missing", "boundary observation is required")
        if observed.get("target_armed_before_first_effect") is not True:
            raise RoutingError("target_not_armed_before_effect", "target was not armed before effect")
        if not _same_number(
            observed.get("nozzle_target_before_first_effect_c"),
            expected_nozzle,
            THERMAL_TOLERANCE_C,
        ):
            raise RoutingError(
                "nozzle_target_before_effect_mismatch",
                "wrong nozzle target before first filament effect",
            )
        if not _same_number(
            observed.get("bed_target_during_boundary_c"), expected_bed, THERMAL_TOLERANCE_C
        ):
            raise RoutingError("bed_target_changed", "bed target changed inside boundary")
        if observed.get("cfs_nozzle_command") is not False:
            raise RoutingError("cfs_nozzle_command", "CFS emitted a nozzle command")
        if observed.get("cfs_bed_command") is not False:
            raise RoutingError("cfs_bed_command", "CFS emitted a bed command")
        if observed.get("geometry_command") is not False:
            raise RoutingError("forbidden_geometry_command", "CFS emitted a geometry command")
        protected_after = observed.get("protected_after")
        self._verify_protected(protected_after)
        if rule["requires_visible_flow"] and observed.get("flow_proven") is not True:
            raise RoutingError("flow_not_proven", "visible flow proof is required")

        self.state["nozzle_target_c"] = expected_nozzle
        self.state["target_owner"] = "job_contract_or_operator"
        self.effects += 1
        if operation == "intentional_unload":
            self.unload_count += 1
            self.cut_count += 1
            self.state["engaged_tool"] = None
            self.state["filament_state"] = "absent_confirmed"
        elif operation in {"initial_load", "intentional_load"}:
            self.state["engaged_tool"] = incoming
            self.state["filament_state"] = "engaged_known"
        elif operation in {"equivalent_refill", "runout_equivalent"}:
            self.state["engaged_tool"] = route_tool
            self.state["filament_state"] = "engaged_known"
        self.trace.append(
            {
                "kind": "cfs_boundary",
                "operation": operation,
                "route_tool": route_tool,
                "nozzle_target_c": expected_nozzle,
                "bed_target_c": expected_bed,
                "proof_id": route["proof_id"],
            }
        )

    def _resolve_target(
        self,
        source: str,
        active: Optional[str],
        outgoing: Any,
        incoming: Any,
    ) -> float:
        if source == "active_explicit_target":
            if active is None or self.state["target_owner"] not in {
                "job_contract",
                "operator",
                "job_contract_or_operator",
            }:
                raise RoutingError("active_target_missing", "no active explicit target")
            return float(self.state["nozzle_target_c"])
        if source == "incoming_tool_current_print_phase":
            if incoming not in self.job.tools:
                raise RoutingError("incoming_tool_unknown", "incoming tool is not declared")
            return self.job.tools[str(incoming)].phase_target(self.state["phase"])
        if outgoing not in self.job.tools or incoming not in self.job.tools:
            raise RoutingError("transition_missing", "transition tools must be explicit")
        transition = self.job.transition(str(outgoing), str(incoming))
        if source == "transition_unload_target":
            return transition.unload_c
        if source == "transition_load_target":
            return transition.load_c
        if source == "transition_purge_target":
            return transition.purge_c
        raise RoutingError("target_source_unknown", "unsupported target source")

    @staticmethod
    def _route_tool(
        role: str, active: Optional[str], outgoing: Any, incoming: Any
    ) -> str:
        route_tool = {"active": active, "outgoing": outgoing, "incoming": incoming}.get(role)
        if route_tool is None:
            raise RoutingError("route_missing", "route role has no logical tool")
        return str(route_tool)

    def _verify_route(self, route: Any, expected_tool: str) -> None:
        if not isinstance(route, dict):
            raise RoutingError("route_missing", "fresh CFS route proof is required")
        required = self.contract["route_proof"]["required_fields"]
        missing = [field for field in required if field not in route]
        if missing:
            raise RoutingError("route_missing", "route proof is incomplete")
        proof_id = str(route["proof_id"])
        if not SAFE_ID.fullmatch(proof_id):
            raise RoutingError("route_missing", "route proof id is invalid")
        if proof_id in self.used_route_proofs:
            raise RoutingError("route_proof_reused", "route proof cannot be reused")
        if route["mapping_revision"] != self.state["mapping_revision"]:
            raise RoutingError("route_stale", "route proof uses a stale mapping revision")
        if route["logical_tool"] != expected_tool:
            raise RoutingError("route_tool_mismatch", "route resolves another logical tool")
        if route["cfs_unit"] not in self.contract["route_proof"]["allowed_cfs_units"]:
            raise RoutingError("route_cfs_invalid", "route uses an unknown CFS unit")
        if route["slot"] not in self.contract["route_proof"]["allowed_slots"]:
            raise RoutingError("route_slot_invalid", "route uses an unknown slot")
        if expected_tool not in self.job.tools:
            raise RoutingError("route_tool_mismatch", "route tool is not declared")
        if route["material_id"] != self.job.tools[expected_tool].material_id:
            raise RoutingError("route_material_mismatch", "route material is inconsistent")
        self.used_route_proofs.add(proof_id)

    def _verify_protected(self, protected_after: Any) -> None:
        if not isinstance(protected_after, dict):
            raise RoutingError("protected_state_incomplete", "post-boundary state is missing")
        before = self.state["protected"]
        for field in PROTECTED_FIELDS:
            if field not in protected_after or protected_after[field] is None:
                raise RoutingError("protected_state_incomplete", "missing protected field")
            tolerance = Z_TOLERANCE_MM if field.endswith("_mm") else None
            matches = (
                _same_number(before[field], protected_after[field], tolerance)
                if tolerance is not None
                else before[field] == protected_after[field]
            )
            if not matches:
                raise RoutingError("protected_state_changed", "%s changed" % field)


def simulate_scenario(
    routing_contract: Mapping[str, Any],
    job_payload: Mapping[str, Any],
    initial_state: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Simulate one scenario and always return a deterministic safe verdict."""

    try:
        job = JobContract.from_mapping(job_payload, routing_contract)
        simulator = RoutingSimulator(routing_contract, job, initial_state)
    except RoutingError as error:
        protected = deepcopy(initial_state.get("protected", {})) if isinstance(initial_state, dict) else {}
        return {
            "contract_id": routing_contract["contract_id"],
            "job_id": str(job_payload.get("job_id", "invalid")),
            "verdict": "blocked_safe",
            "reason_code": error.code,
            "detail": str(error),
            "final_state": {
                "nozzle_target_c": 0.0,
                "bed_target_c": 0.0,
                "protected": protected,
            },
            "effects": 0,
            "cut_count": 0,
            "unload_count": 0,
            "route_proofs_used": [],
            "resume_armed": False,
            "blind_z_restore": False,
            "trace": [{"kind": "safe_stop", "code": error.code}],
            "authorizes_printer_mutation": False,
            "deployment_candidate": False,
            "printer_transport": False,
        }
    return simulator.run(events)


def _matches_expected(result: Mapping[str, Any], expected: Mapping[str, Any]) -> Tuple[bool, str]:
    checks = {
        "verdict": result.get("verdict"),
        "reason_code": result.get("reason_code"),
        "effects": result.get("effects"),
        "cut_count": result.get("cut_count"),
        "unload_count": result.get("unload_count"),
        "engaged_tool": result.get("final_state", {}).get("engaged_tool"),
        "nozzle_target_c": result.get("final_state", {}).get("nozzle_target_c"),
        "bed_target_c": result.get("final_state", {}).get("bed_target_c"),
        "resume_armed": result.get("resume_armed"),
    }
    for field, wanted in expected.items():
        if field not in checks:
            continue
        actual = checks[field]
        if isinstance(wanted, (int, float)) and not isinstance(wanted, bool):
            if not _same_number(actual, wanted, THERMAL_TOLERANCE_C):
                return False, "%s expected %r got %r" % (field, wanted, actual)
        elif actual != wanted:
            return False, "%s expected %r got %r" % (field, wanted, actual)
    return True, "expected verdict and final state observed"


def run_matrix(
    routing_contract: Mapping[str, Any], matrix: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    results = []
    for scenario in matrix["scenarios"]:
        job_payload = matrix["jobs"][scenario["job"]]
        initial_state = matrix["initial_states"][scenario["initial_state"]]
        result = simulate_scenario(
            routing_contract,
            job_payload,
            initial_state,
            scenario.get("events", []),
        )
        passed, detail = _matches_expected(result, scenario["expected"])
        results.append(
            {
                "id": scenario["id"],
                "passed": passed,
                "detail": detail,
                "result": result,
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("matrix", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    results = run_matrix(contract, matrix)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for item in results:
            print("%s %s: %s" % ("OK" if item["passed"] else "KO", item["id"], item["detail"]))
        print("TOTAL %d/%d" % (sum(item["passed"] for item in results), len(results)))
    return 0 if all(item["passed"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
