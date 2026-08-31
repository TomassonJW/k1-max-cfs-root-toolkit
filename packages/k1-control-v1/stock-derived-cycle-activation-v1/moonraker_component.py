"""Composant Moonraker actif du cycle stock-derived possédé par K1 Control."""

from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

from ..common import RequestType, WebRequest
from .k1_control_stock_cycle_active_core import ActiveStockDerivedOrchestrator
from .k1_control_stock_job_contract import JobContractError, build_job_contract

if TYPE_CHECKING:
    from ..confighelper import ConfigHelper


QUERY_OBJECTS = {
    "webhooks": ["state", "state_message"],
    "print_stats": ["state", "filename"],
    "extruder": ["target", "temperature"],
    "heater_bed": ["target", "temperature"],
    "toolhead": ["homed_axes", "position"],
    "gcode_move": ["homing_origin"],
    "bed_mesh": ["profile_name"],
    "box": None,
    "filament_switch_sensor filament_sensor": ["filament_detected", "enabled"],
    "filament_switch_sensor filament_sensor_2": ["filament_detected", "enabled"],
    "gcode_macro PRINTER_PARAM": ["hotend_temp", "z_safe_pause", "fan2_speed"],
    "gcode_macro KCTRL_STATE": None,
    "gcode_macro KCTRL_START_OWNER_STATE": None,
    "gcode_macro KCTRL_STOCK_CYCLE_EMPTY_END_STATE": None,
    "k1_control_cfs_startup_exclusion": None,
    "k1_control_cfs_direct_owner": None,
    "k1_control_cfs_runout_owner": None,
    "k1_control_stock_cycle_owner": None,
    "k1_control_stock_geometry_handoff": None,
}

TERMINAL_PRINT_STATES = {"complete", "cancelled", "error"}
CAMERA_PHASES = {
    "await_release_camera",
    "await_prime_camera",
    "await_tool_change_camera",
    "await_refill_camera",
}


class ControllerError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(str(temporary), str(path))


class K1ControlStockCycle:
    def __init__(self, config: "ConfigHelper") -> None:
        self.server = config.get_server()
        raw_enabled = str(config.get("enabled", "true")).strip().lower()
        if raw_enabled != "true":
            raise config.error("activation-v1 requires enabled: true")
        self.enabled = True
        self.file_manager = self.server.lookup_component("file_manager")
        self.klippy_apis = self.server.lookup_component("klippy_apis")
        self.selection_path = Path(config.get(
            "selection_path",
            "/usr/data/k1-control-v1/state/stock-derived-selection.json",
        ))
        self.run_path = Path(config.get(
            "run_path",
            "/usr/data/k1-control-v1/state/stock-derived-cycle-state.json",
        ))
        self.selection: Optional[Dict[str, Any]] = self._load_json(self.selection_path)
        self.controller: Dict[str, Any] = {
            "camera_checkpoint": None,
            "pause_context": None,
            "last_camera_evidence_id": None,
            "last_failure": None,
            "last_runout_seq": 0,
        }
        self.engine: Optional[ActiveStockDerivedOrchestrator] = None
        self.lock = asyncio.Lock()
        self.monitor_task: Optional[asyncio.Task[Any]] = None
        self.effect_dispatch_count = 0
        self.automatic_retry_count = 0
        self.camera_pass_count = 0
        self.camera_fail_count = 0
        self.state_write_count = 0
        self._restore_run()

        self.server.register_notification("k1_control:stock_cycle_update")
        endpoints = (
            ("/machine/k1_control/stock-cycle/status", RequestType.GET, self._status),
            ("/machine/k1_control/stock-cycle/files", RequestType.GET, self._files),
            ("/machine/k1_control/stock-cycle/inventory", RequestType.POST, self._inventory),
            ("/machine/k1_control/stock-cycle/select", RequestType.POST, self._select),
            ("/machine/k1_control/stock-cycle/begin", RequestType.POST, self._begin),
            ("/machine/k1_control/stock-cycle/clean-confirm", RequestType.POST, self._clean_confirm),
            ("/machine/k1_control/stock-cycle/camera-verdict", RequestType.POST, self._camera_verdict),
            ("/machine/k1_control/stock-cycle/tool-change", RequestType.POST, self._tool_change),
            ("/machine/k1_control/stock-cycle/abort", RequestType.POST, self._abort),
        )
        for path, request_type, handler in endpoints:
            self.server.register_endpoint(path, request_type, handler)

    def component_init(self) -> None:
        if self.engine is not None and self.engine.state.get("phase") == "printing":
            self._start_monitor()

    def _load_json(self, path: Path) -> Optional[Dict[str, Any]]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as error:
            raise self.server.error("Persistent state unreadable: %s" % path, 500) from error
        if not isinstance(value, dict):
            raise self.server.error("Persistent state must be an object: %s" % path, 500)
        return value

    def _restore_run(self) -> None:
        record = self._load_json(self.run_path)
        if record is None:
            return
        try:
            job = record["job"]
            inventory = record["inventory"]
            state = deepcopy(record["state"])
            controller = record["controller"]
            if not isinstance(controller, dict):
                raise ValueError("controller_invalid")
            recovered_claim = False
            pending = state.get("pending_ticket") if isinstance(state, dict) else None
            if pending is not None:
                ticket = state.get("tickets", {}).get(pending, {})
                if ticket.get("status") == "claimed":
                    ticket["status"] = "uncertain"
                    state["phase"] = "blocked_uncertain"
                    state["last_error"] = "claimed_ticket_recovered_without_outcome"
                    state.setdefault("trace", []).append({
                        "index": len(state.get("trace", [])) + 1,
                        "kind": "blocked",
                        "code": "claimed_ticket_recovered_without_outcome",
                        "automatic_retry": False,
                    })
                    recovered_claim = True
            self.engine = ActiveStockDerivedOrchestrator(job, inventory, state)
            self.controller.update(deepcopy(controller))
            if recovered_claim:
                self.controller["last_failure"] = "claimed_ticket_recovered_without_outcome"
                self._persist_run()
        except Exception as error:
            raise self.server.error("Persistent stock cycle state is invalid", 500) from error

    def _persist_selection(self) -> None:
        if self.selection is None:
            raise ControllerError("selection_missing")
        _atomic_json(self.selection_path, self.selection)

    def _persist_run(self) -> None:
        if self.engine is None:
            raise ControllerError("run_not_initialized")
        _atomic_json(
            self.run_path,
            {
                "schema": 1,
                "job": self.engine.job,
                "inventory": [
                    {
                        "route": route,
                        "available": item["available"],
                        "material": item["material"],
                    }
                    for route, item in sorted(self.engine.inventory.items())
                ],
                "state": self.engine.state,
                "controller": self.controller,
            },
        )
        self.state_write_count += 1
        self._notify()

    def _notify(self) -> None:
        try:
            self.server.send_event("k1_control:stock_cycle_update", self._public_state())
        except Exception:
            logging.exception("K1 Control stock cycle notification failed")

    def _public_state(self) -> Dict[str, Any]:
        state = deepcopy(self.engine.state) if self.engine is not None else {
            "phase": "idle",
            "pending_ticket": None,
            "last_error": None,
            "active_route": None,
            "filament_loaded": False,
            "tool_changes": 0,
            "equivalent_refills": 0,
        }
        return {
            "owner": "k1_control_stock_cycle",
            "version": "activation-v1",
            "enabled": self.enabled,
            "phase": state.get("phase"),
            "pending_ticket": state.get("pending_ticket"),
            "last_error": state.get("last_error"),
            "active_route": state.get("active_route"),
            "filament_loaded": state.get("filament_loaded"),
            "tool_changes": state.get("tool_changes", 0),
            "equivalent_refills": state.get("equivalent_refills", 0),
            "camera_checkpoint": self.controller.get("camera_checkpoint"),
            "last_camera_evidence_id": self.controller.get("last_camera_evidence_id"),
            "last_failure": self.controller.get("last_failure"),
            "last_runout_seq": self.controller.get("last_runout_seq", 0),
            "selected": deepcopy(self.selection),
            "effect_dispatch_count": self.effect_dispatch_count,
            "automatic_retry_count": self.automatic_retry_count,
            "camera_pass_count": self.camera_pass_count,
            "camera_fail_count": self.camera_fail_count,
            "state_write_count": self.state_write_count,
            "stock_BOX_effect_count": 0,
            "post_filament_probe_count": 0,
            "mesh_recalculation_count": 0,
            "run_state_present": self.run_path.exists(),
            "runout_owner": "k1_control_cfs_runout_owner",
        }

    async def _status(self, web_request: WebRequest) -> Dict[str, Any]:
        return self._public_state()

    async def _files(self, web_request: WebRequest) -> Dict[str, Any]:
        storage = self.file_manager.get_metadata_storage()
        files = self.file_manager.get_file_list("gcodes", list_format=True)
        result = []
        for item in sorted(files, key=lambda row: row.get("modified", 0), reverse=True)[:50]:
            filename = item.get("path")
            metadata = storage.get(filename, {}) if isinstance(filename, str) else {}
            result.append({
                "filename": filename,
                "modified": item.get("modified"),
                "size": item.get("size"),
                "filament_type": metadata.get("filament_type"),
                "first_layer_extr_temp": metadata.get("first_layer_extr_temp"),
                "first_layer_bed_temp": metadata.get("first_layer_bed_temp"),
            })
        return {"files": result, "selected": deepcopy(self.selection)}

    def _require_idle_controller(self) -> None:
        if self.engine is not None and self.engine.state.get("phase") not in {
            "closed_safe", "idle"
        }:
            raise ControllerError("cycle_not_closed")

    async def _inventory(self, web_request: WebRequest) -> Dict[str, Any]:
        async with self.lock:
            self._require_idle_controller()
            raw = web_request.get_str("inventory_json")
            try:
                inventory = json.loads(raw)
            except ValueError as error:
                raise self.server.error("Inventaire JSON invalide.", 422) from error
            if not isinstance(inventory, list) or not inventory:
                raise self.server.error("L'inventaire doit être une liste non vide.", 422)
            if self.selection is None:
                self.selection = {"inventory": inventory, "job": None}
            else:
                self.selection["inventory"] = inventory
                self.selection["job"] = None
            self._persist_selection()
            self._notify()
            return self._public_state()

    async def _select(self, web_request: WebRequest) -> Dict[str, Any]:
        async with self.lock:
            self._require_idle_controller()
            if self.selection is None or not isinstance(self.selection.get("inventory"), list):
                raise self.server.error("Configure d'abord l'inventaire CFS approuvé.", 409)
            filename = web_request.get_str("filename")
            initial_route = web_request.get_str("initial_route").upper()
            if not self.file_manager.check_file_exists("gcodes", filename):
                raise self.server.error("Le fichier G-code n'existe plus.", 404)
            metadata = self.file_manager.get_metadata_storage().get(filename, None)
            if metadata is None:
                raise self.server.error("Les informations Orca sont absentes.", 422)
            gcode_root = Path(self.file_manager.get_directory("gcodes")).resolve()
            full_path = gcode_root.joinpath(filename).resolve()
            if gcode_root not in full_path.parents:
                raise self.server.error("Le chemin G-code sort du dossier autorisé.", 422)
            try:
                job = await self.server.get_event_loop().run_in_thread(
                    build_job_contract, filename, metadata, full_path, initial_route
                )
                probe = ActiveStockDerivedOrchestrator(
                    job, self.selection["inventory"]
                )
                material = probe.inventory[initial_route]["material"]
                if material["material_type"].upper() != job["material_type"]:
                    raise JobContractError("initial_route_material_mismatch")
            except JobContractError as error:
                raise self.server.error("Fichier refusé : %s" % error.code, 422)
            except Exception as error:
                code = getattr(error, "code", "inventory_invalid")
                raise self.server.error("Inventaire refusé : %s" % code, 422)
            self.selection["job"] = job
            self._persist_selection()
            self._notify()
            return self._public_state()

    async def _query(self) -> Dict[str, Any]:
        raw = await self.klippy_apis.query_objects(QUERY_OBJECTS)
        box = raw.get("box", {})
        logical_routes: List[str] = []
        for unit_name in ("T1", "T2"):
            unit = box.get(unit_name, {}) if isinstance(box, Mapping) else {}
            filament = unit.get("filament") if isinstance(unit, Mapping) else None
            if filament in ("A", "B", "C", "D"):
                logical_routes.append(unit_name + str(filament))
        direct = raw.get("k1_control_cfs_direct_owner", {})
        position = raw.get("toolhead", {}).get("position", [None, None, None])
        origin = raw.get("gcode_move", {}).get("homing_origin", [None, None, None])
        try:
            xyz = [float(position[0]), float(position[1]), float(position[2])]
            origin_z = float(origin[2])
        except (TypeError, ValueError, IndexError):
            xyz = [None, None, None]
            origin_z = None
        return {
            "klippy_ready": raw.get("webhooks", {}).get("state") == "ready",
            "print_state": raw.get("print_stats", {}).get("state"),
            "filename": raw.get("print_stats", {}).get("filename"),
            "nozzle_target_c": float(raw.get("extruder", {}).get("target", 0.0)),
            "bed_target_c": float(raw.get("heater_bed", {}).get("target", 0.0)),
            "homed_axes": raw.get("toolhead", {}).get("homed_axes"),
            "position": xyz,
            "origin_z": origin_z,
            "mesh_profile": raw.get("bed_mesh", {}).get("profile_name"),
            "box": box,
            "logical_routes": logical_routes,
            "head_sensor": raw.get("filament_switch_sensor filament_sensor", {}).get("filament_detected"),
            "after_cutter_sensor": raw.get("filament_switch_sensor filament_sensor_2", {}).get("filament_detected"),
            "head_sensor_enabled": raw.get("filament_switch_sensor filament_sensor", {}).get("enabled"),
            "after_cutter_sensor_enabled": raw.get("filament_switch_sensor filament_sensor_2", {}).get("enabled"),
            "pause_macro": raw.get("gcode_macro PRINTER_PARAM", {}),
            "runtime": raw.get("gcode_macro KCTRL_STATE", {}),
            "start_owner": raw.get("gcode_macro KCTRL_START_OWNER_STATE", {}),
            "empty_end": raw.get("gcode_macro KCTRL_STOCK_CYCLE_EMPTY_END_STATE", {}),
            "startup": raw.get("k1_control_cfs_startup_exclusion", {}),
            "direct": direct,
            "runout": raw.get("k1_control_cfs_runout_owner", {}),
            "stock": raw.get("k1_control_stock_cycle_owner", {}),
            "geometry": raw.get("k1_control_stock_geometry_handoff", {}),
            "active_route": direct.get("active_route"),
        }

    def _assert_begin_snapshot(self, value: Mapping[str, Any]) -> None:
        runtime = value["runtime"]
        box = value["box"]
        if (
            value["klippy_ready"] is not True
            or value["print_state"] != "standby"
            or value["nozzle_target_c"] != 0.0
            or value["bed_target_c"] != 0.0
            or value["mesh_profile"] != "k1_p001_t055_r001_n11x11"
            or int(runtime.get("accepted_z_valid", 0)) != 1
            or abs(float(runtime.get("accepted_z_offset", 99.0)) + 0.04) > 0.0005
            or box.get("auto_refill") != 0
            or box.get("t_command") != ""
            or box.get("enable") not in (1, True)
            or value["startup"].get("ready_verified") is not True
            or value["direct"].get("enabled") is not True
            or value["direct"].get("stock_commands_blocked") is not True
            or value["runout"].get("enabled") is not True
            or value["runout"].get("ready_verified") is not True
            or value["runout"].get("stock_handler_isolated") is not True
            or value["runout"].get("public_box_check_owned") is not True
            or value["runout"].get("event_seq") != value["runout"].get("consumed_seq")
            or value["stock"].get("enabled") is not True
            or value["geometry"].get("enabled") is not True
        ):
            raise ControllerError("active_owner_preflight_invalid")
        for name in ("T1", "T2"):
            unit = box.get(name)
            if not isinstance(unit, Mapping) or unit.get("state") != "connect":
                raise ControllerError("%s_not_connected" % name)
        if len(value["logical_routes"]) > 1:
            raise ControllerError("multiple_stock_routes_engaged")

    def _proof_base(self) -> Dict[str, Any]:
        return {"outcome": "proved", "attempt_count": 1, "automatic_retry_count": 0}

    async def _run_ticket(self, ticket: Mapping[str, Any]) -> None:
        if self.engine is None:
            raise ControllerError("run_not_initialized")
        self._persist_run()
        self.effect_dispatch_count += 1
        try:
            await self.klippy_apis.run_gcode(str(ticket["command"]))
        except Exception as error:
            try:
                self.engine.mark_ticket_uncertain(str(ticket["ticket_id"]))
            finally:
                self.controller["last_failure"] = "effect_outcome_unknown_no_retry"
                self._persist_run()
            raise ControllerError("effect_outcome_unknown_no_retry") from error

    async def _begin(self, web_request: WebRequest) -> Dict[str, Any]:
        if not all((
            web_request.get_boolean("operator_present", False),
            web_request.get_boolean("camera_available", False),
            web_request.get_boolean("machine_clear", False),
        )):
            raise self.server.error("Présence, caméra et machine libre sont obligatoires.", 422)
        async with self.lock:
            self._require_idle_controller()
            if self.selection is None or not isinstance(self.selection.get("job"), dict):
                raise self.server.error("Choisis d'abord un G-code compatible.", 409)
            snapshot = await self._query()
            try:
                self._assert_begin_snapshot(snapshot)
                self.engine = ActiveStockDerivedOrchestrator(
                    self.selection["job"], self.selection["inventory"]
                )
                self.controller = {
                    "camera_checkpoint": None,
                    "pause_context": None,
                    "last_camera_evidence_id": None,
                    "last_failure": None,
                    "last_runout_seq": int(snapshot["runout"].get("event_seq", 0)),
                }
                self.engine.acquire_owner(0, 0, True)
                routes = list(snapshot["logical_routes"])
                if snapshot["active_route"] is not None and snapshot["active_route"] not in routes:
                    routes.append(snapshot["active_route"])
                self.engine.observe_initial_filament(
                    routes,
                    snapshot["head_sensor"],
                    snapshot["after_cutter_sensor"],
                )
                self._persist_run()
                if self.engine.state["phase"] == "preclean_unload_ready":
                    ticket = self.engine.plan_preclean_unload()
                    await self._run_ticket(ticket)
                    after = await self._query()
                    proof = self._proof_base()
                    proof.update({
                        "route_after": after["active_route"],
                        "head_sensor": after["head_sensor"],
                        "after_cutter_sensor": after["after_cutter_sensor"],
                    })
                    self.engine.complete_preclean_unload(ticket["ticket_id"], proof)
                    self._persist_run()
            except Exception as error:
                if self.engine is not None:
                    self.controller["last_failure"] = getattr(error, "code", str(error))
                    self._persist_run()
                raise self.server.error("Départ refusé : %s" % getattr(error, "code", error), 409)
            return self._public_state()

    async def _clean_confirm(self, web_request: WebRequest) -> Dict[str, Any]:
        if not all((
            web_request.get_boolean("operator_confirmed", False),
            web_request.get_boolean("nozzle_visibly_clean", False),
            web_request.get_boolean("plate_clean", False),
            web_request.get_boolean("confirmation_fresh", False),
        )):
            raise self.server.error("Confirme seulement après nettoyage réel buse et plateau.", 422)
        async with self.lock:
            if self.engine is None:
                raise self.server.error("Aucun cycle n'est préparé.", 409)
            try:
                await self.klippy_apis.run_gcode("KCTRL_CONFIRM_MANUAL_NOZZLE_CLEAN_V1")
                self.engine.confirm_manual_clean(fresh=True, filament_loaded=False)
                self._persist_run()
                geometry = self.engine.plan_geometry()
                await self._run_ticket(geometry)
                after_geometry = await self._query()
                proof = self._proof_base()
                proof.update({
                    "filament_loaded": False,
                    "routes": [],
                    "reference_axes": ["X", "Y", "Z"],
                    "mesh_recalculated": False,
                    "mesh_profile": after_geometry["mesh_profile"],
                    "accepted_z_mm": after_geometry["runtime"].get("accepted_z_offset"),
                    "geometry_token": after_geometry["geometry"].get("last_token"),
                })
                self.engine.complete_geometry(geometry["ticket_id"], proof)
                self._persist_run()
                load = self.engine.plan_initial_load_purge()
                await self._run_ticket(load)
                after_load = await self._query()
                load_proof = self._proof_base()
                load_proof.update({
                    "route_after": after_load["active_route"],
                    "head_sensor": after_load["head_sensor"],
                    "after_cutter_sensor": after_load["after_cutter_sensor"],
                    "purge_release_round_trips": 4,
                    "probe_count": 0,
                    "mesh_recalculated": False,
                })
                self.engine.complete_initial_load_purge(load["ticket_id"], load_proof)
                self.controller["camera_checkpoint"] = "PURGE_BIN_RELEASE"
                self._persist_run()
            except Exception as error:
                self.controller["last_failure"] = getattr(error, "code", str(error))
                self._persist_run()
                raise self.server.error("Préparation refusée : %s" % getattr(error, "code", error), 409)
            return self._public_state()

    async def _camera_verdict(self, web_request: WebRequest) -> Dict[str, Any]:
        verdict = web_request.get_str("verdict").upper()
        evidence_id = web_request.get_str("evidence_id")
        if verdict not in {"PASS", "FAIL"} or not evidence_id:
            raise self.server.error("Verdict caméra invalide.", 422)
        async with self.lock:
            if self.engine is None or self.engine.state.get("phase") not in CAMERA_PHASES:
                raise self.server.error("Aucun contrôle caméra n'est attendu.", 409)
            if verdict == "FAIL":
                self.camera_fail_count += 1
                self.controller["last_camera_evidence_id"] = evidence_id
                await self._safe_close_locked("camera_fail")
                return self._public_state()
            self.camera_pass_count += 1
            self.controller["last_camera_evidence_id"] = evidence_id
            phase = self.engine.state["phase"]
            try:
                if phase == "await_release_camera":
                    self.engine.confirm_release_camera("PASS", evidence_id)
                    self._persist_run()
                    ticket = self.engine.plan_initial_prime()
                    await self._run_ticket(ticket)
                    after = await self._query()
                    proof = self._proof_base()
                    proof.update({
                        "stock_prime_exact": after["stock"].get("last_operation") == "prime",
                        "relative_positive_z_mm": 5.0,
                        "probe_count": 0,
                        "mesh_recalculated": False,
                    })
                    self.engine.complete_initial_prime(ticket["ticket_id"], proof)
                    self.controller["camera_checkpoint"] = "ORIGIN_PRIME_LINE"
                    self._persist_run()
                elif phase == "await_prime_camera":
                    self.engine.confirm_prime_camera("PASS", evidence_id)
                    self._persist_run()
                    await self._arm_runout(self.engine.state.get("active_route"))
                    await self.klippy_apis.start_print(self.engine.job["filename"])
                    printing = await self._wait_print_state({"printing"}, 30.0)
                    proof = {
                        "filename": printing["filename"],
                        "virtual_sd_state": printing["print_state"],
                        "route": printing["active_route"],
                        "mesh_profile": printing["mesh_profile"],
                        "accepted_z_mm": printing["runtime"].get("accepted_z_offset"),
                        "probe_count": 0,
                        "mesh_recalculated": False,
                    }
                    self.engine.mark_print_started(proof)
                    self.controller["camera_checkpoint"] = None
                    self._persist_run()
                    self._start_monitor()
                elif phase == "await_tool_change_camera":
                    await self._arm_runout(self.engine.state.get("active_route"))
                    await self._owned_resume()
                    self.engine.confirm_tool_change_camera("PASS", evidence_id)
                    self.controller["pause_context"] = None
                    self.controller["camera_checkpoint"] = None
                    self._persist_run()
                    self._start_monitor()
                elif phase == "await_refill_camera":
                    context = deepcopy(self.controller.get("pause_context"))
                    if context != self.engine.state.get("pause_context"):
                        raise ControllerError("runout_resume_context_changed")
                    await self._arm_runout(self.engine.state.get("active_route"))
                    await self._owned_resume()
                    self.engine.confirm_refill_camera_and_resume(
                        "PASS", evidence_id, context
                    )
                    self.controller["pause_context"] = None
                    self.controller["camera_checkpoint"] = None
                    self._persist_run()
                    self._start_monitor()
            except Exception as error:
                self.controller["last_failure"] = getattr(error, "code", str(error))
                self._persist_run()
                raise self.server.error("Suite caméra refusée : %s" % getattr(error, "code", error), 409)
            return self._public_state()

    async def _tool_change(self, web_request: WebRequest) -> Dict[str, Any]:
        target = web_request.get_str("target_route").upper()
        async with self.lock:
            if self.engine is None or self.engine.state.get("phase") != "printing":
                raise self.server.error("Aucune impression possédée n'est active.", 409)
            try:
                await self.klippy_apis.run_gcode("PAUSE")
                paused = await self._wait_print_state({"paused"}, 15.0)
                self.controller["pause_context"] = self._pause_context(paused)
                ticket = self.engine.plan_tool_change(target, self.controller["pause_context"])
                await self._run_ticket(ticket)
                after = await self._query()
                proof = self._loaded_proof(after, target)
                self.engine.complete_tool_change(ticket["ticket_id"], proof)
                self.controller["camera_checkpoint"] = "TOOL_CHANGE_PURGE_RELEASE"
                self._persist_run()
            except Exception as error:
                self.controller["last_failure"] = getattr(error, "code", str(error))
                self._persist_run()
                raise self.server.error("Changement refusé : %s" % getattr(error, "code", error), 409)
            return self._public_state()

    def _loaded_proof(self, value: Mapping[str, Any], route: str) -> Dict[str, Any]:
        proof = self._proof_base()
        proof.update({
            "route_after": value["active_route"],
            "head_sensor": value["head_sensor"],
            "after_cutter_sensor": value["after_cutter_sensor"],
            "purge_release_round_trips": 4,
            "probe_count": 0,
            "mesh_recalculated": False,
            "active_nozzle_target_c": value["nozzle_target_c"],
        })
        return proof

    def _pause_context(self, value: Mapping[str, Any], *, runout_signal: bool = False) -> Dict[str, Any]:
        saved_target = value.get("pause_macro", {}).get("hotend_temp")
        try:
            original_target = float(saved_target)
        except (TypeError, ValueError):
            original_target = value["nozzle_target_c"]
        if original_target <= 0.0:
            original_target = value["nozzle_target_c"]
        return {
            "pause_latched": value["print_state"] == "paused",
            "filename": value["filename"],
            "engaged_route": self.engine.state.get("active_route") if self.engine else None,
            "nozzle_target_c": original_target,
            "bed_target_c": value["bed_target_c"],
            "head_sensor": value["head_sensor"],
            "after_cutter_sensor": value["after_cutter_sensor"],
            "runout_owner": "k1_control_cfs_runout_owner" if runout_signal else None,
            "runout_signal_seq": int(value.get("runout", {}).get("event_seq", 0)) if runout_signal else 0,
        }

    async def _arm_runout(self, route: Any) -> None:
        if not isinstance(route, str):
            raise ControllerError("runout_arm_route_missing")
        await self.klippy_apis.run_gcode("\n".join([
            "SET_FILAMENT_SENSOR SENSOR=filament_sensor ENABLE=1",
            "SET_FILAMENT_SENSOR SENSOR=filament_sensor_2 ENABLE=1",
            "KCTRL_CFS_RUNOUT_ARM_V1 ROUTE=%s" % route,
        ]))
        value = await self._query()
        if (
            value["runout"].get("armed") is not True
            or value["head_sensor_enabled"] is not True
            or value["after_cutter_sensor_enabled"] is not True
        ):
            raise ControllerError("runout_arm_not_proven")
        self.controller["last_runout_seq"] = int(value["runout"].get("event_seq", 0))
        self._persist_run()

    async def _owned_resume(self) -> None:
        context = self.controller.get("pause_context")
        if not isinstance(context, Mapping):
            raise ControllerError("pause_context_missing")
        target = context.get("nozzle_target_c")
        if isinstance(target, bool) or not isinstance(target, (int, float)):
            raise ControllerError("resume_nozzle_target_invalid")
        await self.klippy_apis.run_gcode(
            "KCTRL_STOCK_RESUME_OWNED_V1 TARGET_C=%.3f" % float(target)
        )
        resumed = await self._wait_print_state({"printing"}, 15.0)
        if abs(resumed["nozzle_target_c"] - float(target)) > 0.01:
            raise ControllerError("resume_nozzle_target_changed")

    async def _wait_print_state(self, accepted, timeout_s: float) -> Dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout_s
        while asyncio.get_running_loop().time() < deadline:
            value = await self._query()
            if value["print_state"] in accepted:
                return value
            await asyncio.sleep(0.25)
        raise ControllerError("print_state_transition_timeout")

    def _start_monitor(self) -> None:
        if self.monitor_task is not None and not self.monitor_task.done():
            return
        self.monitor_task = asyncio.create_task(self._monitor_print())
        self.monitor_task.add_done_callback(self._monitor_done)

    def _monitor_done(self, task: asyncio.Task[Any]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logging.exception("K1 Control stock cycle monitor failed")

    async def _monitor_print(self) -> None:
        while self.engine is not None and self.engine.state.get("phase") == "printing":
            value = await self._query()
            if value["print_state"] in TERMINAL_PRINT_STATES:
                async with self.lock:
                    if self.engine is not None and self.engine.state.get("phase") == "printing":
                        if value["print_state"] == "complete":
                            await self._normal_end_locked()
                        else:
                            await self._safe_close_locked("print_%s" % value["print_state"])
                return
            runout_seq = int(value.get("runout", {}).get("event_seq", 0))
            if (
                value["print_state"] == "paused"
                and runout_seq > int(self.controller.get("last_runout_seq", 0))
            ):
                async with self.lock:
                    await self._runout_locked(value)
                return
            await asyncio.sleep(0.5)

    async def _runout_locked(self, paused: Optional[Mapping[str, Any]] = None) -> None:
        if self.engine is None or self.engine.state.get("phase") != "printing":
            return
        if paused is None:
            paused = await self._query()
        if paused["print_state"] != "paused":
            raise ControllerError("runout_pause_not_latched")
        runout = paused.get("runout", {})
        runout_seq = int(runout.get("event_seq", 0))
        if runout_seq <= int(self.controller.get("last_runout_seq", 0)):
            raise ControllerError("fresh_runout_signal_missing")
        if runout.get("last_route") != self.engine.state.get("active_route"):
            raise ControllerError("runout_signal_route_mismatch")
        context = self._pause_context(paused, runout_signal=True)
        self.controller["pause_context"] = context
        try:
            ticket = self.engine.plan_equivalent_refill(context)
            await self._run_ticket(ticket)
            after = await self._query()
            proof = self._loaded_proof(after, self.engine.state.get("planned_target_route"))
            proof.update({
                "pause_still_latched": True,
                "active_nozzle_target_c": after["nozzle_target_c"],
            })
            if after["runout"].get("consumed_seq") != runout_seq:
                raise ControllerError("runout_release_not_proven")
            if after["runout"].get("logical_release_count", 0) < 1:
                raise ControllerError("runout_logical_release_missing")
            self.engine.complete_equivalent_refill(ticket["ticket_id"], proof)
            self.controller["last_runout_seq"] = runout_seq
            self.controller["camera_checkpoint"] = "REFILL_PURGE_RELEASE"
            self._persist_run()
        except Exception as error:
            self.controller["last_failure"] = getattr(error, "code", str(error))
            self._persist_run()
            current = await self._query()
            current_runout = current.get("runout", {})
            if (
                self.engine.state.get("phase") == "failed_safe"
                and self.engine.state.get("pending_ticket") is None
                and current["print_state"] == "paused"
                and current["head_sensor"] is False
                and current["after_cutter_sensor"] is False
                and current["active_route"] == context.get("engaged_route")
                and int(current_runout.get("event_seq", 0)) == runout_seq
                and int(current_runout.get("consumed_seq", 0)) < runout_seq
            ):
                await self._empty_runout_close_locked(
                    getattr(error, "code", "runout_refill_refused"), context
                )
                return
            raise

    async def _empty_runout_close_locked(
        self, reason: str, context: Mapping[str, Any]
    ) -> None:
        if self.engine is None:
            raise ControllerError("run_not_initialized")
        ticket = self.engine.plan_empty_runout_safe_close(reason, context)
        await self._run_ticket(ticket)
        after = await self._query()
        self.engine.complete_safe_close(
            ticket["ticket_id"],
            self._end_proof(after, expected_empty_effect_id=ticket["ticket_id"]),
        )
        self.engine.release_owner(0, True)
        self.controller["last_runout_seq"] = int(
            after.get("runout", {}).get("consumed_seq", 0)
        )
        self.controller["camera_checkpoint"] = None
        self.controller["pause_context"] = None
        self._persist_run()

    async def _normal_end_locked(self) -> None:
        if self.engine is None:
            return
        ticket = self.engine.plan_end()
        await self._run_ticket(ticket)
        after = await self._query()
        self.engine.complete_end(ticket["ticket_id"], self._end_proof(after))
        self.engine.release_owner(0, True)
        self.controller["camera_checkpoint"] = None
        self._persist_run()

    def _end_proof(
        self,
        value: Mapping[str, Any],
        *,
        expected_empty_effect_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        position = value["position"]
        empty_end = value.get("empty_end", {})
        empty_end_proven = (
            expected_empty_effect_id is not None
            and int(empty_end.get("completed", 0)) == 1
            and empty_end.get("last_effect_id") == expected_empty_effect_id
            and value["print_state"] in {"standby", "cancelled"}
        )
        proof = self._proof_base()
        proof.update({
            "route_after": value["active_route"],
            "head_sensor": value["head_sensor"],
            "after_cutter_sensor": value["after_cutter_sensor"],
            "safe_park": (
                position[0] is not None and position[1] is not None
                and abs(position[0] - 203.0) <= 0.5
                and abs(position[1] - 273.0) <= 0.5
            ),
            "heater_targets_zero": value["nozzle_target_c"] == 0.0 and value["bed_target_c"] == 0.0,
            "fans_zero": (
                value["stock"].get("last_operation") == "end"
                if expected_empty_effect_id is None
                else empty_end_proven
            ),
            "motors_released": value["homed_axes"] == "",
            "probe_count": 0,
            "mesh_recalculated": False,
        })
        return proof

    async def _safe_close_locked(self, reason: str) -> None:
        if self.engine is None:
            return
        plan = self.engine.plan_safe_close(reason)
        ticket_id = plan.get("ticket_id")
        if ticket_id is not None:
            await self._run_ticket(plan)
            after = await self._query()
            self.engine.complete_safe_close(ticket_id, self._end_proof(after))
        self.engine.release_owner(0, True)
        self.controller["camera_checkpoint"] = None
        self._persist_run()

    async def _abort(self, web_request: WebRequest) -> Dict[str, Any]:
        if not web_request.get_boolean("operator_confirmed", False):
            raise self.server.error("Confirmation d'arrêt obligatoire.", 422)
        async with self.lock:
            if self.monitor_task is not None and not self.monitor_task.done():
                self.monitor_task.cancel()
            if self.engine is None or self.engine.state.get("phase") in {"idle", "closed_safe"}:
                return self._public_state()
            try:
                await self._safe_close_locked("operator_abort")
            except Exception as error:
                self.controller["last_failure"] = getattr(error, "code", str(error))
                self._persist_run()
                raise self.server.error("Arrêt sûr refusé : %s" % getattr(error, "code", error), 409)
            return self._public_state()


def load_component(config: "ConfigHelper") -> K1ControlStockCycle:
    return K1ControlStockCycle(config)
