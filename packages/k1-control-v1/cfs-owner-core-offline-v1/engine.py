#!/usr/bin/env python3
"""Pure CFS lifecycle-owner core for deterministic offline qualification.

The module validates synthetic observations and emits abstract, non-dispatchable
intents. It deliberately has no printer, network, serial, subprocess, G-code,
filesystem, heater, motion, command encoding, or deployment surface.
"""

from __future__ import annotations

from copy import deepcopy
import math
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
ROUTE = re.compile(r"^T[12][ABCD]$")


class OwnerCoreError(ValueError):
    """Fail-closed error with a stable machine-readable code."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise OwnerCoreError(code, detail)


def _require_fields(value: Mapping[str, Any], fields: Iterable[str], label: str) -> None:
    missing = [field for field in fields if field not in value]
    if missing:
        raise OwnerCoreError(
            "%s_incomplete" % label,
            "%s missing: %s" % (label, ", ".join(missing)),
        )


def _finite(value: Any, field: str, code: str = "material_identity_invalid") -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OwnerCoreError(code, "%s must be numeric" % field)
    result = float(value)
    if not math.isfinite(result):
        raise OwnerCoreError(code, "%s must be finite" % field)
    return result


def _stable_token(value: Any, code: str) -> str:
    if not isinstance(value, str):
        raise OwnerCoreError(code, "stable token must be a string")
    token = value
    if not SAFE_ID.fullmatch(token):
        raise OwnerCoreError(code, "invalid stable token")
    return token


def _route_list(value: Any, allowed: Sequence[str]) -> List[str]:
    if not isinstance(value, list):
        raise OwnerCoreError("engaged_routes_invalid", "engaged routes must be a list")
    routes = [str(route) for route in value]
    if len(routes) != len(set(routes)):
        raise OwnerCoreError("engaged_routes_invalid", "duplicate engaged route")
    if any(not ROUTE.fullmatch(route) or route not in allowed for route in routes):
        raise OwnerCoreError("engaged_routes_invalid", "unknown engaged route")
    return routes


def _material(value: Any, fields: Sequence[str]) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OwnerCoreError("material_identity_invalid", "material must be an object")
    _require_fields(value, list(fields) + ["user_approved"], "material_identity")
    result = {field: value[field] for field in fields}
    for field in fields:
        if field == "diameter_mm":
            diameter = _finite(value[field], field)
            _require(diameter > 0, "material_identity_invalid", "diameter must be positive")
            result[field] = diameter
        elif field in {"reference_id", "thermal_recipe_id"}:
            result[field] = _stable_token(value[field], "material_identity_invalid")
        else:
            _require(
                isinstance(value[field], str),
                "material_identity_invalid",
                "%s must be a string" % field,
            )
            text = value[field]
            _require(
                bool(text) and len(text) <= 128 and all(ord(character) >= 32 for character in text),
                "material_identity_invalid",
                "%s must be a short printable value" % field,
            )
            result[field] = text
    result["user_approved"] = value["user_approved"] is True
    return result


def _same_material(left: Mapping[str, Any], right: Mapping[str, Any], fields: Sequence[str]) -> bool:
    return all(left.get(field) == right.get(field) for field in fields)


class OwnerCoreSimulator:
    """Deterministic owner lease, route planner and runout state machine."""

    def __init__(
        self,
        contract: Mapping[str, Any],
        initial_snapshot: Mapping[str, Any],
        inventory: Mapping[str, Any],
    ):
        self.contract = contract
        self._validate_contract()
        _require(isinstance(initial_snapshot, Mapping), "snapshot_invalid")
        _require(isinstance(inventory, Mapping), "inventory_invalid")
        self.snapshot = deepcopy(dict(initial_snapshot))
        self.inventory = deepcopy(dict(inventory))
        self.allowed_routes = list(contract["topology"]["allowed_routes"])
        self.required_units = list(contract["topology"]["required_connected_units"])
        self.material_fields = list(contract["material_identity"]["required_exact_fields"])
        self.protected_fields = list(contract["protected_state"]["required_fields"])
        self.phase = "idle"
        self.reason_code: Optional[str] = None
        self.detail = ""
        self.replay_allowed = True
        self.resume_eligible = False
        self.lease_active = False
        self.lease_id: Optional[str] = None
        self.job_id: Optional[str] = None
        self.saved_stock_auto_refill: Optional[int] = None
        self.stock_cfs_print_enable = self.snapshot.get("stock_cfs_print_enable")
        self.mapping_revision = str(self.snapshot.get("mapping_revision"))
        self.connection_epoch = self.snapshot.get("connection_epoch")
        self.protected = deepcopy(self.snapshot.get("protected"))
        self.active_route: Optional[str] = None
        self.flow_verified = False
        self.paused_context: Optional[Dict[str, Any]] = None
        self.pending_plan: Optional[Dict[str, Any]] = None
        self.plan_sequence = 0
        self.completed_intent_ids: set[str] = set()
        self.simulated_observations = 0
        self.journal: List[Dict[str, Any]] = []
        self.release_required = False
        self._validate_snapshot(self.snapshot, require_owner_excluded=False)
        self._validate_inventory()
        routes = _route_list(self.snapshot["engaged_routes"], self.allowed_routes)
        self.active_route = routes[0] if len(routes) == 1 else None

    def _validate_contract(self) -> None:
        _require(isinstance(self.contract, Mapping), "contract_invalid")
        _require_fields(
            self.contract,
            (
                "contract_id",
                "schema",
                "authority",
                "boundaries",
                "topology",
                "material_identity",
                "protected_state",
                "runout_pause",
                "abstract_intents",
            ),
            "contract",
        )
        _stable_token(self.contract["contract_id"], "contract_id_invalid")
        _require(self.contract["schema"] == 1, "contract_schema_invalid")
        _require(
            self.contract.get("authority") == "offline_only",
            "contract_authority_invalid",
        )
        boundaries = self.contract.get("boundaries")
        _require(isinstance(boundaries, Mapping), "contract_boundary_invalid")
        _require(bool(boundaries), "contract_boundary_invalid", "boundaries missing")
        _require(
            all(value is False for value in boundaries.values()),
            "contract_boundary_invalid",
            "every runtime boundary must stay false",
        )
        topology = self.contract["topology"]
        _require(isinstance(topology, Mapping), "contract_topology_invalid")
        _require_fields(topology, ("allowed_routes", "required_connected_units"), "contract_topology")
        _require(
            isinstance(topology["allowed_routes"], list)
            and isinstance(topology["required_connected_units"], list),
            "contract_topology_invalid",
        )
        for section, field in (
            ("material_identity", "required_exact_fields"),
            ("protected_state", "required_fields"),
            ("runout_pause", "required_context_fields"),
        ):
            spec = self.contract[section]
            _require(isinstance(spec, Mapping), "contract_%s_invalid" % section)
            _require_fields(spec, (field,), "contract_%s" % section)
            values = spec[field]
            _require(
                isinstance(values, list)
                and bool(values)
                and all(isinstance(item, str) for item in values)
                and len(values) == len(set(values)),
                "contract_%s_invalid" % section,
            )
        intents = self.contract["abstract_intents"]
        _require(isinstance(intents, Mapping) and bool(intents), "contract_intents_invalid")
        for name, spec in intents.items():
            _stable_token(name, "contract_intent_invalid")
            _require(isinstance(spec, Mapping), "contract_intent_invalid", str(name))
            _require_fields(spec, ("dispatchable", "maximum_attempts", "next_gate"), "contract_intent")
            _require(spec.get("dispatchable") is False, "dispatchable_intent_forbidden", name)
            _require(
                isinstance(spec["maximum_attempts"], int)
                and not isinstance(spec["maximum_attempts"], bool)
                and spec["maximum_attempts"] >= 0,
                "contract_intent_invalid",
                name,
            )
            _stable_token(spec["next_gate"], "contract_intent_invalid")

    def _validate_snapshot(
        self,
        snapshot: Mapping[str, Any],
        *,
        require_owner_excluded: bool,
        compare_freshness: bool = False,
    ) -> None:
        required = (
            "schema",
            "mapping_revision",
            "connection_epoch",
            "printer_state",
            "connected_units",
            "active_command",
            "stock_auto_refill",
            "stock_cfs_print_enable",
            "engaged_routes",
            "head_sensor_present",
            "after_cutter_sensor_present",
            "protected",
        )
        _require_fields(snapshot, required, "snapshot")
        _require(snapshot["schema"] == 1, "snapshot_schema_invalid")
        _stable_token(snapshot["mapping_revision"], "mapping_revision_invalid")
        _stable_token(snapshot["printer_state"], "printer_state_invalid")
        epoch = snapshot["connection_epoch"]
        _require(
            isinstance(epoch, int) and not isinstance(epoch, bool) and epoch >= 0,
            "connection_epoch_invalid",
        )
        units = snapshot["connected_units"]
        _require(
            isinstance(units, list) and all(isinstance(unit, str) for unit in units),
            "cfs_units_invalid",
        )
        _require(sorted(units) == sorted(self.required_units), "cfs_units_not_ready")
        _require(snapshot["active_command"] in (None, ""), "cfs_command_active")
        _require(
            isinstance(snapshot["stock_auto_refill"], int)
            and not isinstance(snapshot["stock_auto_refill"], bool)
            and snapshot["stock_auto_refill"] in (0, 1),
            "stock_auto_refill_invalid",
        )
        _require(
            isinstance(snapshot["stock_cfs_print_enable"], int)
            and not isinstance(snapshot["stock_cfs_print_enable"], bool)
            and snapshot["stock_cfs_print_enable"] in (0, 1),
            "stock_print_enable_invalid",
        )
        routes = _route_list(snapshot["engaged_routes"], self.allowed_routes)
        _require(len(routes) <= 1, "multiple_engaged_routes")
        _require(
            isinstance(snapshot["head_sensor_present"], bool)
            and isinstance(snapshot["after_cutter_sensor_present"], bool),
            "sensor_state_invalid",
        )
        _require(isinstance(snapshot["protected"], Mapping), "protected_state_invalid")
        _require_fields(snapshot["protected"], self.protected_fields, "protected_state")
        for field in ("effective_z_offset_mm", "nozzle_target_c", "bed_target_c"):
            number = _finite(
                snapshot["protected"][field],
                field,
                "protected_state_invalid",
            )
            if field != "effective_z_offset_mm":
                _require(number >= 0, "protected_state_invalid", "%s must be non-negative" % field)
        for field in ("mesh_profile", "accepted_z_revision", "homed_axes"):
            _stable_token(snapshot["protected"][field], "protected_state_invalid")
        if require_owner_excluded:
            _require(snapshot["stock_auto_refill"] == 0, "stock_owner_not_excluded")
            _require(
                snapshot["stock_cfs_print_enable"] == self.stock_cfs_print_enable,
                "stock_print_enable_changed",
            )
        if compare_freshness:
            _require(
                str(snapshot["mapping_revision"]) == self.mapping_revision,
                "mapping_revision_changed",
            )
            _require(snapshot["connection_epoch"] == self.connection_epoch, "connection_epoch_changed")
            _require(dict(snapshot["protected"]) == self.protected, "protected_state_changed")

    def _validate_inventory(self) -> None:
        _require_fields(
            self.inventory,
            ("schema", "mapping_revision", "connection_epoch", "slots"),
            "inventory",
        )
        _require(self.inventory["schema"] == 1, "inventory_schema_invalid")
        _require(
            str(self.inventory["mapping_revision"]) == self.mapping_revision,
            "inventory_mapping_stale",
        )
        _require(
            self.inventory["connection_epoch"] == self.connection_epoch,
            "inventory_epoch_stale",
        )
        slots = self.inventory["slots"]
        _require(isinstance(slots, list), "inventory_slots_invalid")
        seen: set[str] = set()
        normalized = []
        for slot in slots:
            _require(isinstance(slot, Mapping), "inventory_slot_invalid")
            _require_fields(
                slot,
                ("route", "enabled", "available", "sensor_present", "material"),
                "inventory_slot",
            )
            route = str(slot["route"])
            _require(route in self.allowed_routes and ROUTE.fullmatch(route) is not None, "route_invalid")
            _require(route not in seen, "inventory_route_duplicate")
            seen.add(route)
            for field in ("enabled", "available", "sensor_present"):
                _require(isinstance(slot[field], bool), "inventory_slot_invalid", field)
            normalized.append(
                {
                    "route": route,
                    "enabled": slot["enabled"],
                    "available": slot["available"],
                    "sensor_present": slot["sensor_present"],
                    "material": _material(slot["material"], self.material_fields),
                }
            )
        self.inventory["slots"] = normalized

    def run(self, events: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        try:
            _require(
                isinstance(events, Sequence) and not isinstance(events, (str, bytes)),
                "events_invalid",
            )
            for event in events:
                self._apply(event)
                if self.phase in {"blocked_safe", "cancelled_safe", "closed_safe"}:
                    break
        except OwnerCoreError as error:
            self._block(error)
        return self.result()

    def result(self) -> Dict[str, Any]:
        verdict = {
            "blocked_safe": "blocked_safe",
            "cancelled_safe": "cancelled_safe",
            "closed_safe": "closed_safe",
        }.get(self.phase, "pass_offline")
        pending = []
        if self.pending_plan is not None:
            index = int(self.pending_plan.get("next_index", 0))
            pending = deepcopy(self.pending_plan.get("intents", [])[index:])
        return {
            "contract_id": self.contract["contract_id"],
            "verdict": verdict,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "phase": self.phase,
            "job_id": self.job_id,
            "lease_id": self.lease_id,
            "lease_active": self.lease_active,
            "lease_release_required": self.release_required,
            "saved_stock_auto_refill": self.saved_stock_auto_refill,
            "active_route": self.active_route,
            "flow_verified": self.flow_verified,
            "resume_eligible": self.resume_eligible,
            "replay_allowed": self.replay_allowed,
            "pending_intents": pending,
            "pending_plan_invalidated": bool(
                self.pending_plan is not None and self.pending_plan.get("invalidated") is True
            ),
            "completed_intent_ids": sorted(self.completed_intent_ids),
            "simulated_observations": self.simulated_observations,
            "journal": deepcopy(self.journal),
            "printer_connection": False,
            "printer_mutation": False,
            "gcode_sent": False,
            "heat": False,
            "motion": False,
            "cfs_effect": False,
            "remote_write": False,
            "service_action": False,
            "real_connector_present": False,
            "command_encoder_present": False,
            "deployment_candidate": False,
            "production_authorized": False,
        }

    def _apply(self, event: Mapping[str, Any]) -> None:
        _require(isinstance(event, Mapping), "event_invalid")
        kind = str(event.get("kind"))
        handlers = {
            "prepare_lease": self._prepare_lease,
            "confirm_lease": self._confirm_lease,
            "plan_start": self._plan_start,
            "observe_intent": self._observe_intent,
            "verify_plan": self._verify_plan,
            "begin_print": self._begin_print,
            "pause_runout": self._pause_runout,
            "plan_runout": self._plan_runout,
            "owned_resume": self._owned_resume,
            "close_job": self._close_job,
            "confirm_release": self._confirm_release,
            "connection_epoch_changed": self._connection_epoch_changed,
            "stock_callback": self._stock_callback,
            "cancel": self._cancel,
        }
        handler = handlers.get(kind)
        if handler is None:
            raise OwnerCoreError("event_unknown", kind)
        handler(event)

    def _prepare_lease(self, event: Mapping[str, Any]) -> None:
        self._require_phase("idle")
        _require(self.snapshot["printer_state"] == "standby", "printer_not_standby")
        self.job_id = _stable_token(event.get("job_id"), "job_id_invalid")
        self.lease_id = _stable_token(event.get("lease_id"), "lease_id_invalid")
        self.saved_stock_auto_refill = int(self.snapshot["stock_auto_refill"])
        operation = (
            "exclude_stock_auto_refill"
            if self.saved_stock_auto_refill == 1
            else "verify_stock_auto_refill_disabled"
        )
        intent = self._intent(
            "%s:owner-exclusion" % self.lease_id,
            operation,
            target_value=0,
        )
        self.pending_plan = {
            "kind": "lease",
            "target_route": self.active_route,
            "intents": [intent],
            "next_index": 0,
            "invalidated": False,
        }
        self.phase = "lease_pending"
        self.release_required = True
        self._journal("lease_prepared", operation=operation, previous_value=self.saved_stock_auto_refill)

    def _confirm_lease(self, event: Mapping[str, Any]) -> None:
        self._require_phase("lease_pending")
        _require(self.pending_plan is not None, "lease_plan_missing")
        intent = self.pending_plan["intents"][0]
        _require(event.get("intent_id") == intent["intent_id"], "intent_order_invalid")
        _require(event.get("synthetic_observation") is True, "offline_observation_required")
        expected_attempts = int(intent["maximum_attempts"])
        _require(event.get("attempt_count") == expected_attempts, "attempt_count_invalid")
        _require(event.get("stock_owner_boundary_verified") is True, "stock_owner_effect_unproven")
        _require(event.get("configuration_unchanged") is True, "configuration_changed")
        observed = event.get("observed")
        _require(isinstance(observed, Mapping), "snapshot_missing")
        self._validate_snapshot(observed, require_owner_excluded=True, compare_freshness=True)
        _require(
            observed["engaged_routes"] == self.snapshot["engaged_routes"],
            "lease_changed_filament_route",
        )
        self.completed_intent_ids.add(intent["intent_id"])
        self.pending_plan = None
        self.lease_active = True
        self.phase = "owned_idle"
        self._journal("lease_active", previous_value=self.saved_stock_auto_refill)

    def _plan_start(self, event: Mapping[str, Any]) -> None:
        self._require_phase("owned_idle")
        observed = self._fresh_observation(event)
        routes = _route_list(observed["engaged_routes"], self.allowed_routes)
        _require(len(routes) <= 1, "multiple_engaged_routes")
        intended_route = str(event.get("intended_route"))
        _require(intended_route in self.allowed_routes, "intended_route_invalid")
        intended_material = _material(event.get("intended_material"), self.material_fields)
        _require(intended_material["user_approved"], "material_identity_not_approved")
        intended_slot = self._slot(intended_route)
        _require(_same_material(intended_slot["material"], intended_material, self.material_fields), "route_material_mismatch")
        _require(intended_slot["enabled"], "intended_route_disabled")
        operations: List[str]
        decision: str
        if not routes:
            residual_present = observed["head_sensor_present"] or observed["after_cutter_sensor_present"]
            if residual_present:
                _require(
                    event.get("confirmed_residual_route") == intended_route,
                    "residual_segment_route_ambiguous",
                )
            _require(intended_slot["available"] and intended_slot["sensor_present"], "intended_route_unavailable")
            decision = "LOAD"
            operations = ["load_selected_route", "purge_visible"]
            self.active_route = None
        else:
            current = routes[0]
            _require(
                event.get("engaged_material_identity_confirmed") is True,
                "engaged_material_identity_unproven",
            )
            current_slot = self._slot(current)
            _require(current_slot["material"]["user_approved"], "engaged_material_identity_unapproved")
            if current == intended_route and _same_material(
                current_slot["material"], intended_material, self.material_fields
            ):
                decision = "KEEP"
                operations = ["purge_visible"]
            else:
                _require(intended_slot["available"] and intended_slot["sensor_present"], "intended_route_unavailable")
                decision = "CHANGE"
                operations = [
                    "cut_current_filament",
                    "retract_current_filament",
                    "load_selected_route",
                    "purge_visible",
                ]
            self.active_route = current
        self._create_plan("start", decision, intended_route, operations)

    def _begin_print(self, event: Mapping[str, Any]) -> None:
        self._require_phase("filament_ready")
        observed = self._fresh_observation(event)
        _require(self.flow_verified, "flow_not_verified")
        _require(event.get("stock_start_command") is False, "stock_start_forbidden")
        _require(observed["engaged_routes"] == [self.active_route], "start_route_unverified")
        self.phase = "printing"
        self._journal("printing_started", active_route=self.active_route)

    def _pause_runout(self, event: Mapping[str, Any]) -> None:
        self._require_phase("printing")
        observed = self._fresh_observation(event)
        routes = _route_list(observed["engaged_routes"], self.allowed_routes)
        _require(len(routes) == 1 and routes[0] == self.active_route, "runout_active_route_ambiguous")
        _require(event.get("pause_latched") is True, "runout_pause_not_latched")
        _require(event.get("stock_pause_command") is False, "stock_pause_forbidden")
        _require(event.get("stock_callback_seen") is False, "stock_owner_conflict")
        self.paused_context = self._validate_paused_context(
            event.get("paused_context"),
            observed=observed,
            expected_route=self.active_route,
        )
        self.phase = "paused_runout"
        self.resume_eligible = False
        self._journal("runout_paused", exhausted_route=self.active_route)

    def _plan_runout(self, event: Mapping[str, Any]) -> None:
        self._require_phase("paused_runout")
        observed = self._fresh_observation(event)
        exhausted_route = str(event.get("exhausted_route"))
        _require(exhausted_route == self.active_route, "runout_exhausted_route_mismatch")
        observed_routes = _route_list(observed["engaged_routes"], self.allowed_routes)
        _require(
            observed_routes in ([], [exhausted_route]),
            "runout_active_route_ambiguous",
        )
        exhausted = self._slot(exhausted_route)
        _require(exhausted["material"]["user_approved"], "runout_material_identity_unapproved")
        candidates = []
        for slot in self.inventory["slots"]:
            if slot["route"] == exhausted_route:
                continue
            if not (slot["enabled"] and slot["available"] and slot["sensor_present"]):
                continue
            if not slot["material"]["user_approved"]:
                continue
            if _same_material(slot["material"], exhausted["material"], self.material_fields):
                candidates.append(slot["route"])
        _require(bool(candidates), "identical_replacement_missing")
        _require(len(candidates) == 1, "identical_replacement_ambiguous")
        self._create_plan(
            "refill",
            "REFILL_IDENTICAL",
            candidates[0],
            ["resolve_runout_tail", "load_selected_route", "purge_visible"],
            exhausted_route=exhausted_route,
        )

    def _observe_intent(self, event: Mapping[str, Any]) -> None:
        intent_id = str(event.get("intent_id"))
        if intent_id in self.completed_intent_ids:
            raise OwnerCoreError("intent_replay_rejected")
        _require(
            self.phase in {"start_plan_pending", "refill_plan_pending"},
            "intent_observation_phase_invalid",
        )
        _require(self.pending_plan is not None, "pending_plan_missing")
        index = int(self.pending_plan["next_index"])
        intents = self.pending_plan["intents"]
        _require(index < len(intents), "pending_intent_missing")
        intent = intents[index]
        _require(intent_id == intent["intent_id"], "intent_order_invalid")
        _require(event.get("synthetic_observation") is True, "offline_observation_required")
        _require(event.get("attempt_count") == 1, "attempt_count_invalid")
        _require(event.get("automatic_retry_count") == 0, "automatic_retry_forbidden")
        outcome = event.get("outcome")
        if outcome == "unknown":
            raise OwnerCoreError("effect_outcome_unknown")
        _require(outcome == "proved", "effect_not_proved")
        observed = self._fresh_observation(event)
        _require(event.get("configuration_unchanged") is True, "configuration_changed")
        _require(event.get("protected_state_unchanged") is True, "protected_state_changed")
        _require(event.get("stock_callback_seen") is False, "stock_owner_conflict")
        operation = intent["operation"]
        target = self.pending_plan["target_route"]
        routes = _route_list(observed["engaged_routes"], self.allowed_routes)
        if operation == "cut_current_filament":
            _require(event.get("cut_observed") is True, "cut_effect_unproven")
        elif operation in {"retract_current_filament", "resolve_runout_tail"}:
            _require(event.get("route_released") is True and routes == [], "route_release_unproven")
            if operation == "resolve_runout_tail":
                _require(event.get("tail_state_resolved") is True, "runout_tail_unresolved")
            self.active_route = None
        elif operation == "load_selected_route":
            _require(routes == [target], "load_route_unproven")
            _require(event.get("route_sensor_present") is True, "load_sensor_unproven")
            self.active_route = target
        elif operation == "purge_visible":
            _require(routes == [target], "purge_route_mismatch")
            _require(event.get("visible_flow") is True, "visible_flow_unproven")
            self.active_route = target
            self.flow_verified = True
        else:
            raise OwnerCoreError("intent_operation_unknown", operation)
        self.completed_intent_ids.add(intent_id)
        self.simulated_observations += 1
        self.pending_plan["next_index"] = index + 1
        self._journal("intent_observed", intent_id=intent_id, operation=operation)
        if self.pending_plan["next_index"] == len(intents):
            self.phase = (
                "start_plan_observed"
                if self.pending_plan["kind"] == "start"
                else "refill_plan_observed"
            )

    def _verify_plan(self, event: Mapping[str, Any]) -> None:
        _require(
            self.phase in {"start_plan_observed", "refill_plan_observed"},
            "plan_verification_phase_invalid",
        )
        _require(self.pending_plan is not None, "pending_plan_missing")
        observed = self._fresh_observation(event)
        target = self.pending_plan["target_route"]
        _require(observed["engaged_routes"] == [target], "final_route_unverified")
        _require(event.get("visible_flow") is True and self.flow_verified, "visible_flow_unproven")
        _require(event.get("protected_state_unchanged") is True, "protected_state_changed")
        _require(event.get("stock_callback_seen") is False, "stock_owner_conflict")
        _require(event.get("automatic_retry_count") == 0, "automatic_retry_forbidden")
        kind = self.pending_plan["kind"]
        if kind == "refill":
            _require(event.get("pause_still_latched") is True, "runout_pause_lost")
            self.phase = "resume_ready"
            self.resume_eligible = True
        else:
            self.phase = "filament_ready"
        self.active_route = target
        self._journal("plan_verified", plan_kind=kind, active_route=target)
        self.pending_plan = None

    def _owned_resume(self, event: Mapping[str, Any]) -> None:
        self._require_phase("resume_ready")
        observed = self._fresh_observation(event)
        _require(self.resume_eligible, "resume_not_eligible")
        required = {
            "owner": "k1_control",
            "stock_resume_command": False,
            "homing": False,
            "z_reference": False,
            "mesh_mutation": False,
        }
        for field, expected in required.items():
            _require(event.get(field) == expected, "owned_resume_invalid", field)
        _require(self.paused_context is not None, "owned_resume_invalid", "paused_context_missing")
        resume_context = self._validate_paused_context(
            event.get("paused_context"),
            expected_route=self.paused_context["engaged_route"],
        )
        _require(
            resume_context == self.paused_context,
            "owned_resume_invalid",
            "paused_context_changed",
        )
        _require(observed["engaged_routes"] == [self.active_route], "resume_route_unverified")
        self.phase = "printing"
        self.resume_eligible = False
        self.paused_context = None
        self._journal("owned_resume_accepted", active_route=self.active_route)

    def _close_job(self, event: Mapping[str, Any]) -> None:
        _require(
            self.phase in {"owned_idle", "filament_ready", "printing", "resume_ready"},
            "close_phase_invalid",
        )
        _require(self.pending_plan is None, "close_with_pending_plan")
        observed = self._fresh_observation(event)
        _require(event.get("stock_end_command") is False, "stock_end_forbidden")
        _require(event.get("heater_targets_zero_verified") is True, "heater_shutdown_unproven")
        _require(event.get("resume_closed") is True, "resume_still_armed")
        expected_routes = [] if self.active_route is None else [self.active_route]
        _require(observed["engaged_routes"] == expected_routes, "close_route_changed")
        operation = (
            "restore_stock_auto_refill"
            if self.saved_stock_auto_refill == 1
            else "verify_stock_auto_refill_disabled"
        )
        intent = self._intent(
            "%s:owner-release" % self.lease_id,
            operation,
            target_value=self.saved_stock_auto_refill,
        )
        self.pending_plan = {
            "kind": "release",
            "target_route": self.active_route,
            "intents": [intent],
            "next_index": 0,
            "invalidated": False,
        }
        self.phase = "release_pending"
        self.resume_eligible = False
        self._journal("release_prepared", restore_value=self.saved_stock_auto_refill)

    def _confirm_release(self, event: Mapping[str, Any]) -> None:
        self._require_phase("release_pending")
        _require(self.pending_plan is not None, "release_plan_missing")
        intent = self.pending_plan["intents"][0]
        _require(event.get("intent_id") == intent["intent_id"], "intent_order_invalid")
        _require(event.get("synthetic_observation") is True, "offline_observation_required")
        _require(event.get("attempt_count") == intent["maximum_attempts"], "attempt_count_invalid")
        _require(event.get("stock_owner_boundary_verified") is True, "stock_owner_effect_unproven")
        _require(event.get("configuration_unchanged") is True, "configuration_changed")
        observed = event.get("observed")
        _require(isinstance(observed, Mapping), "snapshot_missing")
        self._validate_snapshot(observed, require_owner_excluded=False, compare_freshness=True)
        _require(observed["stock_auto_refill"] == self.saved_stock_auto_refill, "stock_owner_restore_mismatch")
        _require(
            observed["stock_cfs_print_enable"] == self.stock_cfs_print_enable,
            "stock_print_enable_changed",
        )
        expected_routes = [] if self.active_route is None else [self.active_route]
        _require(observed["engaged_routes"] == expected_routes, "release_changed_filament_route")
        self.completed_intent_ids.add(intent["intent_id"])
        self.pending_plan = None
        self.lease_active = False
        self.release_required = False
        self.phase = "closed_safe"
        self._journal("lease_released", restored_value=self.saved_stock_auto_refill)

    def _connection_epoch_changed(self, event: Mapping[str, Any]) -> None:
        new_epoch = event.get("new_connection_epoch")
        _require(new_epoch != self.connection_epoch, "connection_epoch_not_changed")
        raise OwnerCoreError("connection_epoch_changed")

    def _stock_callback(self, event: Mapping[str, Any]) -> None:
        _require(self.lease_active, "stock_callback_without_owner")
        callback = _stable_token(event.get("callback"), "stock_callback_invalid")
        raise OwnerCoreError("stock_owner_conflict", callback)

    def _cancel(self, event: Mapping[str, Any]) -> None:
        _require(self.phase not in {"idle", "closed_safe", "cancelled_safe", "blocked_safe"}, "cancel_phase_invalid")
        _require(event.get("automatic_retry") is False, "automatic_retry_forbidden")
        _require(event.get("stock_resume_command") is False, "stock_resume_forbidden")
        if self.pending_plan is not None:
            self.pending_plan["invalidated"] = True
        self.replay_allowed = False
        self.resume_eligible = False
        self.phase = "cancelled_safe"
        self._journal("cancelled", lease_release_required=self.release_required)

    def _fresh_observation(self, event: Mapping[str, Any]) -> Mapping[str, Any]:
        observed = event.get("observed")
        _require(isinstance(observed, Mapping), "snapshot_missing")
        self._validate_snapshot(observed, require_owner_excluded=True, compare_freshness=True)
        _require(event.get("inventory_mapping_revision", self.mapping_revision) == self.mapping_revision, "inventory_mapping_stale")
        _require(event.get("inventory_connection_epoch", self.connection_epoch) == self.connection_epoch, "inventory_epoch_stale")
        return observed

    def _validate_paused_context(
        self,
        value: Any,
        *,
        observed: Optional[Mapping[str, Any]] = None,
        expected_route: Optional[str] = None,
    ) -> Dict[str, Any]:
        _require(isinstance(value, Mapping), "runout_snapshot_incomplete")
        fields = self.contract["runout_pause"]["required_context_fields"]
        _require_fields(value, fields, "runout_snapshot")
        context = deepcopy(dict(value))

        position = context["resume_position_xyz_mm"]
        _require(isinstance(position, Mapping), "runout_snapshot_invalid", "resume position")
        _require_fields(position, ("x", "y", "z"), "resume_position")
        for axis in ("x", "y", "z"):
            _finite(position[axis], "resume_position_%s" % axis, "runout_snapshot_invalid")

        modes = context["motion_modes"]
        _require(isinstance(modes, Mapping), "runout_snapshot_invalid", "motion modes")
        _require_fields(modes, ("axes", "extruder"), "motion_modes")
        for mode in (modes["axes"], modes["extruder"]):
            _require(mode in {"absolute", "relative"}, "runout_snapshot_invalid", "motion mode")

        _finite(context["extruder_e_position"], "extruder_e_position", "runout_snapshot_invalid")
        _finite(context["speed_factor_percent"], "speed_factor_percent", "runout_snapshot_invalid")
        _finite(context["flow_factor_percent"], "flow_factor_percent", "runout_snapshot_invalid")
        pressure_advance = _finite(
            context["pressure_advance"],
            "pressure_advance",
            "runout_snapshot_invalid",
        )
        _require(pressure_advance >= 0, "runout_snapshot_invalid", "pressure advance")

        fans = context["fans"]
        _require(isinstance(fans, Mapping) and bool(fans), "runout_snapshot_invalid", "fans")
        for fan, speed in fans.items():
            _stable_token(fan, "runout_snapshot_invalid")
            normalized = _finite(speed, "fan_speed", "runout_snapshot_invalid")
            _require(0 <= normalized <= 1, "runout_snapshot_invalid", "fan speed")

        _stable_token(context["logical_tool"], "runout_snapshot_invalid")
        if expected_route is not None:
            _require(
                context["engaged_route"] == expected_route,
                "runout_snapshot_invalid",
                "route",
            )
        _require(
            isinstance(context["head_sensor_present"], bool)
            and isinstance(context["after_cutter_sensor_present"], bool),
            "runout_snapshot_invalid",
            "sensors",
        )
        _require(context["mapping_revision"] == self.mapping_revision, "runout_snapshot_invalid", "mapping")
        _require(context["connection_epoch"] == self.connection_epoch, "runout_snapshot_invalid", "epoch")
        _require(context["protected"] == self.protected, "runout_snapshot_invalid", "protected state")
        if observed is not None:
            _require(
                context["head_sensor_present"] == observed["head_sensor_present"]
                and context["after_cutter_sensor_present"]
                == observed["after_cutter_sensor_present"],
                "runout_snapshot_invalid",
                "sensor snapshot",
            )
        return context

    def _create_plan(
        self,
        kind: str,
        decision: str,
        target_route: str,
        operations: Sequence[str],
        *,
        exhausted_route: Optional[str] = None,
    ) -> None:
        self.plan_sequence += 1
        intents = []
        for index, operation in enumerate(operations, 1):
            intents.append(
                self._intent(
                    "%s:plan-%d:%d-%s" % (self.lease_id, self.plan_sequence, index, operation),
                    operation,
                    target_route=target_route,
                )
            )
        self.pending_plan = {
            "kind": kind,
            "decision": decision,
            "target_route": target_route,
            "exhausted_route": exhausted_route,
            "intents": intents,
            "next_index": 0,
            "invalidated": False,
        }
        self.phase = "start_plan_pending" if kind == "start" else "refill_plan_pending"
        self.flow_verified = False
        self._journal(
            "plan_created",
            plan_kind=kind,
            decision=decision,
            target_route=target_route,
            operations=list(operations),
        )

    def _intent(self, intent_id: str, operation: str, **fields: Any) -> Dict[str, Any]:
        intent_id = _stable_token(intent_id, "intent_id_invalid")
        _require(intent_id not in self.completed_intent_ids, "intent_id_duplicate")
        spec = self.contract["abstract_intents"].get(operation)
        _require(isinstance(spec, Mapping), "intent_operation_unknown", operation)
        _require(spec.get("dispatchable") is False, "dispatchable_intent_forbidden", operation)
        intent = {
            "intent_id": intent_id,
            "operation": operation,
            "dispatchable": False,
            "maximum_attempts": int(spec["maximum_attempts"]),
            "requires_separate_gate": spec["next_gate"],
        }
        intent.update(fields)
        return intent

    def _slot(self, route: str) -> Mapping[str, Any]:
        for slot in self.inventory["slots"]:
            if slot["route"] == route:
                return slot
        raise OwnerCoreError("route_not_in_inventory", route)

    def _block(self, error: OwnerCoreError) -> None:
        self.reason_code = error.code
        self.detail = error.detail
        self.replay_allowed = False
        self.resume_eligible = False
        if self.pending_plan is not None:
            self.pending_plan["invalidated"] = True
        self.phase = "blocked_safe"
        self._journal("safe_block", code=error.code)

    def _journal(self, kind: str, **fields: Any) -> None:
        entry = {"index": len(self.journal) + 1, "kind": kind}
        entry.update(fields)
        self.journal.append(entry)

    def _require_phase(self, expected: str) -> None:
        if self.phase != expected:
            raise OwnerCoreError(
                "phase_order_invalid",
                "expected %s got %s" % (expected, self.phase),
            )


def simulate(
    contract: Mapping[str, Any],
    initial_snapshot: Mapping[str, Any],
    inventory: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Run one deterministic scenario and always return a safe result."""

    try:
        simulator = OwnerCoreSimulator(contract, initial_snapshot, inventory)
    except OwnerCoreError as error:
        return {
            "contract_id": contract.get("contract_id") if isinstance(contract, Mapping) else None,
            "verdict": "blocked_safe",
            "reason_code": error.code,
            "detail": error.detail,
            "phase": "blocked_safe",
            "job_id": None,
            "lease_id": None,
            "lease_active": False,
            "lease_release_required": False,
            "saved_stock_auto_refill": None,
            "active_route": None,
            "flow_verified": False,
            "resume_eligible": False,
            "replay_allowed": False,
            "pending_intents": [],
            "pending_plan_invalidated": False,
            "completed_intent_ids": [],
            "simulated_observations": 0,
            "journal": [{"index": 1, "kind": "safe_block", "code": error.code}],
            "printer_connection": False,
            "printer_mutation": False,
            "gcode_sent": False,
            "heat": False,
            "motion": False,
            "cfs_effect": False,
            "remote_write": False,
            "service_action": False,
            "real_connector_present": False,
            "command_encoder_present": False,
            "deployment_candidate": False,
            "production_authorized": False,
        }
    return simulator.run(events)


def matches_expected(result: Mapping[str, Any], expected: Mapping[str, Any]) -> Tuple[bool, str]:
    """Compare the compact scenario expectations used by the matrix runner."""

    for field, wanted in expected.items():
        if field == "pending_operations":
            actual = [item["operation"] for item in result.get("pending_intents", [])]
        else:
            actual = result.get(field)
        if actual != wanted:
            return False, "%s expected %r got %r" % (field, wanted, actual)
    return True, "expected offline verdict observed"
