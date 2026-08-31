#!/usr/bin/env python3
"""Orchestrateur pur du cycle CFS dérivé des mouvements stock observés.

Le module n'ouvre aucune connexion et n'exécute aucune commande. Il prépare
des tickets persistables, déjà encodés vers les primitives Klipper revues. Un
ticket est revendiqué avant son premier effet et ne peut jamais être rejoué si
son issue devient inconnue.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import math
import re
from typing import Any, Dict, Mapping, Optional, Sequence


ROUTE = re.compile(r"^T[12][ABCD]$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
EFFECT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
CURRENT_PROFILE = "k1_p001_t055_r001_n11x11"
CURRENT_BED_C = 55.0
CURRENT_PROBE_C = 140.0
CURRENT_FIRST_C = 190.0
CURRENT_Z_MM = -0.04
IDENTITY_FIELDS = (
    "reference_id",
    "material_type",
    "color",
    "diameter_mm",
    "thermal_recipe_id",
    "user_approved",
)


class OrchestratorError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _number(value: Any, code: str) -> float:
    if isinstance(value, bool):
        raise OrchestratorError(code)
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise OrchestratorError(code)
    if not math.isfinite(result):
        raise OrchestratorError(code)
    return result


def _close(left: Any, right: float, tolerance: float = 0.001) -> bool:
    try:
        return abs(float(left) - right) <= tolerance
    except (TypeError, ValueError):
        return False


def _safe_id(value: Any, code: str) -> str:
    result = str(value)
    if not SAFE_ID.fullmatch(result):
        raise OrchestratorError(code)
    return result


def _route(value: Any, code: str) -> str:
    result = str(value)
    if not ROUTE.fullmatch(result):
        raise OrchestratorError(code)
    return result


def _material(value: Any) -> Dict[str, Any]:
    if not isinstance(value, Mapping) or any(field not in value for field in IDENTITY_FIELDS):
        raise OrchestratorError("material_identity_incomplete")
    result = {field: value[field] for field in IDENTITY_FIELDS}
    for field in ("reference_id", "thermal_recipe_id"):
        result[field] = _safe_id(result[field], "material_identity_invalid")
    for field in ("material_type", "color"):
        if not isinstance(result[field], str) or not result[field] or len(result[field]) > 128:
            raise OrchestratorError("material_identity_invalid")
    diameter = _number(result["diameter_mm"], "material_identity_invalid")
    if diameter <= 0:
        raise OrchestratorError("material_identity_invalid")
    result["diameter_mm"] = diameter
    if result["user_approved"] is not True:
        raise OrchestratorError("material_identity_not_approved")
    result["user_approved"] = True
    return result


def material_digest(value: Mapping[str, Any]) -> str:
    normalized = _material(value)
    payload = json.dumps(
        normalized,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return sha256(payload).hexdigest()


def _command_digest(command: str) -> str:
    return sha256(command.encode("utf-8")).hexdigest()


def _json_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return sha256(encoded).hexdigest()


def _format_number(value: float) -> str:
    return ("%.3f" % value).rstrip("0").rstrip(".")


class StockDerivedOrchestrator:
    """Machine d'état persistable et encodeur de commandes sans transport."""

    def __init__(
        self,
        job: Mapping[str, Any],
        inventory: Sequence[Mapping[str, Any]],
        state: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.job = self._validate_job(job)
        self.inventory = self._validate_inventory(inventory)
        if state is None:
            self.state = {
                "schema": 1,
                "job_id": self.job["job_id"],
                "job_sha256": _json_digest(self.job),
                "inventory_sha256": _json_digest(self.inventory),
                "phase": "idle",
                "active_route": None,
                "filament_loaded": False,
                "geometry_ready": False,
                "stock_auto_refill_previous": None,
                "stock_auto_refill_owned": False,
                "pause_context": None,
                "pending_ticket": None,
                "tickets": {},
                "sequence": 0,
                "last_error": None,
                "tool_changes": 0,
                "equivalent_refills": 0,
                "trace": [],
            }
        else:
            self.state = deepcopy(dict(state))
            self._validate_state()
            pending = self.state.get("pending_ticket")
            if pending is not None:
                ticket = self.state["tickets"].get(pending, {})
                if ticket.get("status") == "claimed":
                    ticket["status"] = "uncertain"
                    self._block("claimed_ticket_recovered_without_outcome", uncertain=True)

    def snapshot(self) -> Dict[str, Any]:
        result = deepcopy(self.state)
        result.update(
            {
                "job": deepcopy(self.job),
                "printer_transport": False,
                "physical_action": False,
                "remote_write": False,
                "service_action": False,
                "deployment_candidate": False,
                "production_authorized": False,
            }
        )
        return result

    def acquire_owner(
        self,
        stock_auto_refill_previous: Any,
        observed_stock_auto_refill: Any,
        stock_owner_boundary_verified: bool,
    ) -> Dict[str, Any]:
        self._require_phase("idle")
        previous = stock_auto_refill_previous
        if not isinstance(previous, int) or isinstance(previous, bool) or previous not in (0, 1):
            self._fail("stock_auto_refill_previous_invalid")
        if (
            not isinstance(observed_stock_auto_refill, int)
            or isinstance(observed_stock_auto_refill, bool)
            or observed_stock_auto_refill != 0
            or stock_owner_boundary_verified is not True
        ):
            self._fail("stock_auto_refill_exclusion_not_proven")
        self.state["stock_auto_refill_previous"] = int(previous)
        self.state["stock_auto_refill_owned"] = True
        self.state["phase"] = "await_empty_filament"
        self._trace("owner_acquired", previous_auto_refill=int(previous))
        return self.snapshot()

    def observe_initial_filament(
        self,
        routes: Any,
        head_sensor: Any,
        after_cutter_sensor: Any,
    ) -> Dict[str, Any]:
        self._require_phase("await_empty_filament")
        normalized = self._routes(routes)
        if not isinstance(head_sensor, bool) or not isinstance(after_cutter_sensor, bool):
            self._fail("initial_filament_sensor_missing")
        if normalized == [] and head_sensor is False and after_cutter_sensor is False:
            self.state["phase"] = "await_manual_clean"
            self._trace("filament_path_empty")
            return self.snapshot()
        if len(normalized) == 1 and head_sensor is True and after_cutter_sensor is True:
            self.state["active_route"] = normalized[0]
            self.state["filament_loaded"] = True
            self.state["phase"] = "preclean_unload_ready"
            self._trace("preclean_unload_required", route=normalized[0])
            return self.snapshot()
        self._fail("initial_filament_state_ambiguous")

    def plan_preclean_unload(self) -> Dict[str, Any]:
        self._require_phase("preclean_unload_ready")
        route = self._active_route()
        ticket_id = self._next_ticket_id("preclean-unload")
        command = self._cut_unload_command(route, ticket_id)
        return self._claim("preclean_unload", command, "preclean_unload_pending", ticket_id)

    def complete_preclean_unload(self, ticket_id: str, proof: Mapping[str, Any]) -> Dict[str, Any]:
        self._require_phase("preclean_unload_pending")
        self._observe_ticket(ticket_id, proof)
        if proof.get("route_after") is not None or proof.get("head_sensor") is not False or proof.get("after_cutter_sensor") is not False:
            self._fail("preclean_unload_not_proven")
        self.state["active_route"] = None
        self.state["filament_loaded"] = False
        self.state["phase"] = "await_manual_clean"
        self._trace("preclean_unload_complete")
        return self.snapshot()

    def confirm_manual_clean(self, *, fresh: bool, filament_loaded: bool) -> Dict[str, Any]:
        self._require_phase("await_manual_clean")
        if fresh is not True or filament_loaded is not False:
            self._fail("fresh_clean_before_geometry_missing")
        if self.state["active_route"] is not None:
            self._fail("geometry_with_route_forbidden")
        self.state["phase"] = "geometry_ready_to_dispatch"
        self._trace("manual_clean_confirmed")
        return self.snapshot()

    def plan_geometry(self) -> Dict[str, Any]:
        self._require_phase("geometry_ready_to_dispatch")
        self._require_current_geometry_runtime()
        ticket_id = self._next_ticket_id("geometry")
        command = (
            "KCTRL_PREPARE_GEOMETRY_BEFORE_INSERTION_R4 "
            "BED=55 PROBE_NOZZLE=140 FIRST_NOZZLE=190 "
            "PLATE=1 PROBE_REV=1 NOZZLE_ID=1 CONFIG_ID=1 X_COUNT=11 Y_COUNT=11"
        )
        return self._claim("geometry_before_filament", command, "geometry_pending", ticket_id)

    def complete_geometry(self, ticket_id: str, proof: Mapping[str, Any]) -> Dict[str, Any]:
        self._require_phase("geometry_pending")
        self._observe_ticket(ticket_id, proof)
        if proof.get("filament_loaded") is not False or proof.get("routes") != []:
            self._fail("geometry_completed_with_filament")
        if proof.get("reference_axes") != ["X", "Y", "Z"] or proof.get("mesh_recalculated") is not False:
            self._fail("geometry_reference_contract_invalid")
        if proof.get("mesh_profile") != self.job["mesh_profile"] or not _close(proof.get("accepted_z_mm"), self.job["accepted_z_mm"], 0.0005):
            self._fail("geometry_profile_or_z_changed")
        if proof.get("geometry_token") != "geometry_ready_for_stock_cycle":
            self._fail("geometry_handoff_token_missing")
        self.state["geometry_ready"] = True
        self.state["phase"] = "initial_load_ready"
        self._trace("geometry_complete_before_filament")
        return self.snapshot()

    def plan_initial_load_purge(self) -> Dict[str, Any]:
        self._require_phase("initial_load_ready")
        self._require_geometry_before_filament()
        route = self.job["initial_route"]
        self._require_available_target(route)
        ticket_id = self._next_ticket_id("initial-load-purge")
        command = self._load_purge_command(route, ticket_id)
        return self._claim("initial_load_purge", command, "initial_load_purge_pending", ticket_id)

    def complete_initial_load_purge(self, ticket_id: str, proof: Mapping[str, Any]) -> Dict[str, Any]:
        self._require_phase("initial_load_purge_pending")
        self._observe_ticket(ticket_id, proof)
        self._require_loaded_proof(proof, self.job["initial_route"])
        self.state["active_route"] = self.job["initial_route"]
        self.state["filament_loaded"] = True
        self.state["phase"] = "await_release_camera"
        self._trace("initial_load_purge_complete")
        return self.snapshot()

    def confirm_release_camera(self, verdict: str, evidence_id: str) -> Dict[str, Any]:
        self._require_phase("await_release_camera")
        self._camera_pass(verdict, evidence_id)
        self.state["phase"] = "initial_prime_ready"
        self._trace("purge_release_camera_pass", evidence_id=evidence_id)
        return self.snapshot()

    def plan_initial_prime(self) -> Dict[str, Any]:
        self._require_phase("initial_prime_ready")
        ticket_id = self._next_ticket_id("initial-prime")
        command = (
            "KCTRL_STOCK_CYCLE_PRIME_V1 EFFECT_ID=%s FIRST_C=%s"
            % (ticket_id, _format_number(self.job["first_nozzle_c"]))
        )
        return self._claim("initial_prime", command, "initial_prime_pending", ticket_id)

    def complete_initial_prime(self, ticket_id: str, proof: Mapping[str, Any]) -> Dict[str, Any]:
        self._require_phase("initial_prime_pending")
        self._observe_ticket(ticket_id, proof)
        if proof.get("stock_prime_exact") is not True or not _close(proof.get("relative_positive_z_mm"), 5.0):
            self._fail("stock_prime_not_proven")
        self._require_post_filament_no_contact(proof)
        self.state["phase"] = "await_prime_camera"
        self._trace("initial_prime_complete")
        return self.snapshot()

    def confirm_prime_camera(self, verdict: str, evidence_id: str) -> Dict[str, Any]:
        self._require_phase("await_prime_camera")
        self._camera_pass(verdict, evidence_id)
        self.state["phase"] = "ready_to_print"
        self._trace("prime_camera_pass", evidence_id=evidence_id)
        return self.snapshot()

    def mark_print_started(self, proof: Mapping[str, Any]) -> Dict[str, Any]:
        self._require_phase("ready_to_print")
        if proof.get("filename") != self.job["filename"] or proof.get("virtual_sd_state") != "printing":
            self._fail("print_start_not_proven")
        if proof.get("route") != self._active_route():
            self._fail("print_route_changed")
        if proof.get("mesh_profile") != self.job["mesh_profile"] or not _close(proof.get("accepted_z_mm"), self.job["accepted_z_mm"], 0.0005):
            self._fail("print_geometry_changed")
        self._require_post_filament_no_contact(proof)
        self.state["phase"] = "printing"
        self._trace("print_started")
        return self.snapshot()

    def plan_tool_change(self, target_route: str) -> Dict[str, Any]:
        self._require_phase("printing")
        target = _route(target_route, "tool_change_target_invalid")
        source = self._active_route()
        if target == source:
            self._fail("tool_change_target_same_as_source")
        self._require_available_target(target)
        ticket_id = self._next_ticket_id("tool-change")
        command = "\n".join(
            [
                self._cut_unload_command(source, ticket_id + "-unload"),
                self._load_purge_command(target, ticket_id + "-load"),
            ]
        )
        self.state["planned_target_route"] = target
        return self._claim("tool_change", command, "tool_change_pending", ticket_id)

    def complete_tool_change(self, ticket_id: str, proof: Mapping[str, Any]) -> Dict[str, Any]:
        self._require_phase("tool_change_pending")
        self._observe_ticket(ticket_id, proof)
        target = self.state.get("planned_target_route")
        self._require_loaded_proof(proof, target)
        self.state["active_route"] = target
        self.state["phase"] = "await_tool_change_camera"
        self._trace("tool_change_effect_complete", route=target)
        return self.snapshot()

    def confirm_tool_change_camera(self, verdict: str, evidence_id: str) -> Dict[str, Any]:
        self._require_phase("await_tool_change_camera")
        self._camera_pass(verdict, evidence_id)
        self.state["phase"] = "printing"
        self.state["tool_changes"] += 1
        self.state.pop("planned_target_route", None)
        self._trace("tool_change_camera_pass", evidence_id=evidence_id)
        return self.snapshot()

    def plan_equivalent_refill(self, pause_context: Mapping[str, Any]) -> Dict[str, Any]:
        self._require_phase("printing")
        source = self._active_route()
        target, digest = self._unique_identical_spare(source)
        if not isinstance(pause_context, Mapping) or pause_context.get("pause_latched") is not True:
            self._fail("runout_pause_not_latched")
        context = deepcopy(dict(pause_context))
        if context.get("engaged_route") != source:
            self._fail("runout_pause_route_invalid")
        ticket_id = self._next_ticket_id("equivalent-refill")
        guard = (
            "KCTRL_STOCK_CYCLE_REFILL_GUARD_V1 FROM=%s TO=%s "
            "SOURCE_IDENTITY=%s TARGET_IDENTITY=%s CANDIDATES=1 PAUSE_LATCHED=1"
            % (source, target, digest, digest)
        )
        command = "\n".join(
            [
                guard,
                self._cut_unload_command(source, ticket_id + "-unload"),
                self._load_purge_command(target, ticket_id + "-load"),
            ]
        )
        self.state["pause_context"] = context
        self.state["planned_target_route"] = target
        return self._claim("equivalent_refill", command, "equivalent_refill_pending", ticket_id)

    def complete_equivalent_refill(self, ticket_id: str, proof: Mapping[str, Any]) -> Dict[str, Any]:
        self._require_phase("equivalent_refill_pending")
        self._observe_ticket(ticket_id, proof)
        target = self.state.get("planned_target_route")
        self._require_loaded_proof(proof, target)
        if proof.get("pause_still_latched") is not True:
            self._fail("runout_pause_lost")
        if not _close(proof.get("active_nozzle_target_c"), self.state["pause_context"].get("nozzle_target_c")):
            self._fail("runout_temperature_changed")
        self.state["active_route"] = target
        self.state["phase"] = "await_refill_camera"
        self._trace("equivalent_refill_effect_complete", route=target)
        return self.snapshot()

    def confirm_refill_camera_and_resume(
        self,
        verdict: str,
        evidence_id: str,
        resume_context: Mapping[str, Any],
    ) -> Dict[str, Any]:
        self._require_phase("await_refill_camera")
        self._camera_pass(verdict, evidence_id)
        if dict(resume_context) != self.state.get("pause_context"):
            self._fail("runout_resume_context_changed")
        self.state["phase"] = "printing"
        self.state["equivalent_refills"] += 1
        self.state["pause_context"] = None
        self.state.pop("planned_target_route", None)
        self._trace("equivalent_refill_resumed", evidence_id=evidence_id)
        return self.snapshot()

    def plan_end(self) -> Dict[str, Any]:
        self._require_phase("printing")
        route = self._active_route()
        ticket_id = self._next_ticket_id("normal-end")
        command = (
            "KCTRL_STOCK_CYCLE_END_V1 ROUTE=%s EFFECT_ID=%s "
            "UNLOAD_C=%s MATERIAL_MIN_C=%s MATERIAL_MAX_C=%s"
            % (
                route,
                ticket_id,
                _format_number(self.job["unload_c"]),
                _format_number(self.job["material_min_c"]),
                _format_number(self.job["material_max_c"]),
            )
        )
        return self._claim("normal_end", command, "normal_end_pending", ticket_id)

    def complete_end(self, ticket_id: str, proof: Mapping[str, Any]) -> Dict[str, Any]:
        self._require_phase("normal_end_pending")
        self._observe_ticket(ticket_id, proof)
        if proof.get("route_after") is not None or proof.get("head_sensor") is not False or proof.get("after_cutter_sensor") is not False:
            self._fail("end_unload_not_proven")
        if not all(proof.get(field) is True for field in (
            "safe_park", "heater_targets_zero", "fans_zero", "motors_released"
        )):
            self._fail("end_terminal_state_not_proven")
        self._require_post_filament_no_contact(proof)
        self.state["active_route"] = None
        self.state["filament_loaded"] = False
        self.state["phase"] = "owner_release_pending"
        self._trace("normal_end_complete")
        return self.snapshot()

    def release_owner(
        self,
        observed_auto_refill: Any,
        stock_owner_boundary_verified: bool,
    ) -> Dict[str, Any]:
        self._require_phase("owner_release_pending")
        previous = self.state["stock_auto_refill_previous"]
        if (
            not isinstance(observed_auto_refill, int)
            or isinstance(observed_auto_refill, bool)
            or observed_auto_refill != previous
            or stock_owner_boundary_verified is not True
        ):
            self._fail("stock_auto_refill_restore_mismatch")
        self.state["stock_auto_refill_owned"] = False
        self.state["phase"] = "closed_safe"
        self._trace("owner_released", restored_auto_refill=previous)
        return self.snapshot()

    def mark_ticket_uncertain(self, ticket_id: str) -> Dict[str, Any]:
        ticket = self._pending_ticket(ticket_id)
        ticket["status"] = "uncertain"
        self._block("effect_outcome_unknown_no_retry", uncertain=True)

    def _claim(self, kind: str, command: str, phase: str, ticket_id: str) -> Dict[str, Any]:
        if self.state.get("pending_ticket") is not None:
            self._fail("another_ticket_pending")
        if any(marker in command for marker in ("BOX_", "BED_MESH_CALIBRATE", "CX_PRINT_LEVELING_CALIBRATION")):
            self._fail("forbidden_command_encoded")
        self.state["tickets"][ticket_id] = {
            "ticket_id": ticket_id,
            "kind": kind,
            "status": "claimed",
            "attempt_count": 1,
            "automatic_retry_count": 0,
            "command": command,
            "command_sha256": _command_digest(command),
            "proof_sha256": None,
        }
        self.state["pending_ticket"] = ticket_id
        self.state["phase"] = phase
        self._trace("ticket_claimed_before_effect", ticket_id=ticket_id, operation=kind)
        return deepcopy(self.state["tickets"][ticket_id])

    def _observe_ticket(self, ticket_id: str, proof: Mapping[str, Any]) -> None:
        ticket = self._pending_ticket(ticket_id)
        if proof.get("outcome") != "proved" or proof.get("attempt_count") != 1 or proof.get("automatic_retry_count") != 0:
            ticket["status"] = "uncertain"
            self._block("effect_outcome_unknown_no_retry", uncertain=True)
        encoded = json.dumps(dict(proof), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        ticket["proof_sha256"] = sha256(encoded.encode("ascii")).hexdigest()
        ticket["status"] = "complete"
        self.state["pending_ticket"] = None
        self._trace("ticket_completed", ticket_id=ticket_id)

    def _pending_ticket(self, ticket_id: str) -> Dict[str, Any]:
        normalized = _safe_id(ticket_id, "ticket_id_invalid")
        if self.state.get("pending_ticket") != normalized:
            self._fail("ticket_order_invalid")
        ticket = self.state["tickets"].get(normalized)
        if not isinstance(ticket, dict) or ticket.get("status") != "claimed":
            self._fail("ticket_not_claimed_or_already_consumed")
        return ticket

    def _next_ticket_id(self, operation: str) -> str:
        self.state["sequence"] += 1
        result = "%s-%03d-%s" % (self.job["job_id"], self.state["sequence"], operation)
        if not EFFECT_ID.fullmatch(result) or not EFFECT_ID.fullmatch(result + "-unload"):
            self._fail("effect_id_too_long")
        return result

    def _cut_unload_command(self, route: str, effect_id: str) -> str:
        return (
            "KCTRL_STOCK_CYCLE_CUT_UNLOAD_V1 ROUTE=%s EFFECT_ID=%s "
            "UNLOAD_C=%s MATERIAL_MIN_C=%s MATERIAL_MAX_C=%s"
            % (
                route,
                effect_id,
                _format_number(self.job["unload_c"]),
                _format_number(self.job["material_min_c"]),
                _format_number(self.job["material_max_c"]),
            )
        )

    def _load_purge_command(self, route: str, effect_id: str) -> str:
        return (
            "KCTRL_STOCK_CYCLE_LOAD_PURGE_V1 ROUTE=%s EFFECT_ID=%s "
            "LOAD_C=%s PURGE_C=%s PURGE_MM=%s TRIPS=%d "
            "MATERIAL_MIN_C=%s MATERIAL_MAX_C=%s"
            % (
                route,
                effect_id,
                _format_number(self.job["load_c"]),
                _format_number(self.job["purge_c"]),
                _format_number(self.job["purge_mm"]),
                self.job["release_trips"],
                _format_number(self.job["material_min_c"]),
                _format_number(self.job["material_max_c"]),
            )
        )

    def _unique_identical_spare(self, source_route: str):
        source = self.inventory.get(source_route)
        if source is None:
            self._fail("runout_source_missing_from_inventory")
        digest = material_digest(source["material"])
        candidates = []
        for route, slot in self.inventory.items():
            if route == source_route or slot["available"] is not True:
                continue
            if material_digest(slot["material"]) == digest:
                candidates.append(route)
        if not candidates:
            self._fail("identical_replacement_missing")
        if len(candidates) != 1:
            self._fail("identical_replacement_ambiguous")
        return candidates[0], digest

    def _require_available_target(self, route: str) -> None:
        slot = self.inventory.get(route)
        if slot is None or slot.get("available") is not True:
            self._fail("target_route_not_available")

    def _require_loaded_proof(self, proof: Mapping[str, Any], route: Any) -> None:
        if proof.get("route_after") != route or proof.get("head_sensor") is not True or proof.get("after_cutter_sensor") is not True:
            self._fail("loaded_route_not_proven")
        if proof.get("purge_release_round_trips") not in (3, 4):
            self._fail("purge_release_not_proven")
        self._require_post_filament_no_contact(proof)

    def _require_post_filament_no_contact(self, proof: Mapping[str, Any]) -> None:
        if proof.get("probe_count", 0) != 0 or proof.get("mesh_recalculated", False) is not False:
            self._fail("contact_after_filament_forbidden")

    def _require_geometry_before_filament(self) -> None:
        if self.state.get("geometry_ready") is not True or self.state.get("filament_loaded") is not False:
            self._fail("geometry_before_filament_not_proven")

    def _require_current_geometry_runtime(self) -> None:
        if (
            self.job["mesh_profile"] != CURRENT_PROFILE
            or not _close(self.job["bed_c"], CURRENT_BED_C)
            or not _close(self.job["probe_nozzle_c"], CURRENT_PROBE_C)
            or not _close(self.job["first_nozzle_c"], CURRENT_FIRST_C)
            or not _close(self.job["accepted_z_mm"], CURRENT_Z_MM, 0.0005)
        ):
            self._fail("thermal_geometry_runtime_not_qualified")

    def _active_route(self) -> str:
        route = self.state.get("active_route")
        if not isinstance(route, str) or not ROUTE.fullmatch(route):
            self._fail("active_route_missing")
        return route

    def _camera_pass(self, verdict: str, evidence_id: str) -> None:
        if verdict != "PASS" or not SAFE_ID.fullmatch(str(evidence_id)):
            self._fail("camera_proof_missing")

    def _routes(self, value: Any):
        if not isinstance(value, list) or len(value) != len(set(value)):
            self._fail("routes_invalid")
        result = [_route(route, "routes_invalid") for route in value]
        if len(result) > 1:
            self._fail("multiple_routes_engaged")
        return result

    def _validate_job(self, value: Mapping[str, Any]) -> Dict[str, Any]:
        required = (
            "job_id", "filename", "initial_route", "mesh_profile",
            "accepted_z_mm", "bed_c", "probe_nozzle_c", "first_nozzle_c",
            "load_c", "unload_c", "purge_c", "purge_mm",
            "material_min_c", "material_max_c", "release_trips",
        )
        if not isinstance(value, Mapping) or any(field not in value for field in required):
            raise OrchestratorError("job_contract_incomplete")
        result = deepcopy(dict(value))
        result["job_id"] = _safe_id(result["job_id"], "job_id_invalid")
        if len(result["job_id"]) > 48:
            raise OrchestratorError("job_id_too_long_for_effect_ticket")
        result["initial_route"] = _route(result["initial_route"], "initial_route_invalid")
        result["mesh_profile"] = _safe_id(result["mesh_profile"], "mesh_profile_invalid")
        if not isinstance(result["filename"], str) or not result["filename"] or ".." in result["filename"]:
            raise OrchestratorError("filename_invalid")
        for field in (
            "accepted_z_mm", "bed_c", "probe_nozzle_c", "first_nozzle_c",
            "load_c", "unload_c", "purge_c", "purge_mm",
            "material_min_c", "material_max_c",
        ):
            result[field] = _number(result[field], "%s_invalid" % field)
        if not 150 <= result["material_min_c"] <= result["material_max_c"] <= 320:
            raise OrchestratorError("material_temperature_bounds_invalid")
        for field in ("first_nozzle_c", "load_c", "unload_c", "purge_c"):
            if not result["material_min_c"] <= result[field] <= result["material_max_c"]:
                raise OrchestratorError("%s_out_of_bounds" % field)
        if (
            not 0.1 <= result["purge_mm"] <= 80
            or not isinstance(result["release_trips"], int)
            or isinstance(result["release_trips"], bool)
            or result["release_trips"] not in (3, 4)
        ):
            raise OrchestratorError("purge_contract_invalid")
        return result

    def _validate_inventory(self, value: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise OrchestratorError("inventory_invalid")
        result = {}
        for item in value:
            if not isinstance(item, Mapping):
                raise OrchestratorError("inventory_invalid")
            route = _route(item.get("route"), "inventory_route_invalid")
            if route in result or not isinstance(item.get("available"), bool):
                raise OrchestratorError("inventory_invalid")
            result[route] = {
                "available": item["available"],
                "material": _material(item.get("material")),
            }
        if self.job["initial_route"] not in result:
            raise OrchestratorError("initial_route_missing_from_inventory")
        return result

    def _validate_state(self) -> None:
        required = {
            "schema", "job_id", "job_sha256", "inventory_sha256", "phase",
            "active_route", "filament_loaded",
            "geometry_ready", "stock_auto_refill_previous",
            "stock_auto_refill_owned", "pause_context", "pending_ticket",
            "tickets", "sequence", "last_error", "tool_changes",
            "equivalent_refills", "trace",
        }
        if (
            not required.issubset(self.state)
            or self.state["schema"] != 1
            or self.state["job_id"] != self.job["job_id"]
            or self.state["job_sha256"] != _json_digest(self.job)
            or self.state["inventory_sha256"] != _json_digest(self.inventory)
        ):
            raise OrchestratorError("persistent_state_invalid")
        if not isinstance(self.state["tickets"], dict) or not isinstance(self.state["trace"], list):
            raise OrchestratorError("persistent_state_invalid")
        for ticket_id, ticket in self.state["tickets"].items():
            if (
                not isinstance(ticket, Mapping)
                or ticket.get("ticket_id") != ticket_id
                or ticket.get("status") not in {"claimed", "complete", "uncertain"}
                or ticket.get("attempt_count") != 1
                or ticket.get("automatic_retry_count") != 0
                or not isinstance(ticket.get("command"), str)
                or ticket.get("command_sha256") != _command_digest(ticket["command"])
            ):
                raise OrchestratorError("persistent_ticket_invalid")
        pending = self.state.get("pending_ticket")
        if pending is not None and pending not in self.state["tickets"]:
            raise OrchestratorError("persistent_ticket_invalid")

    def _require_phase(self, phase: str) -> None:
        if self.state["phase"] != phase:
            self._fail("phase_order_invalid")

    def _trace(self, kind: str, **fields: Any) -> None:
        entry = {"index": len(self.state["trace"]) + 1, "kind": kind}
        entry.update(fields)
        self.state["trace"].append(entry)

    def _block(self, code: str, *, uncertain: bool) -> None:
        self.state["last_error"] = code
        self.state["phase"] = "blocked_uncertain" if uncertain else "failed_safe"
        self._trace("blocked", code=code, automatic_retry=False)
        raise OrchestratorError(code)

    def _fail(self, code: str) -> None:
        self._block(code, uncertain=False)
