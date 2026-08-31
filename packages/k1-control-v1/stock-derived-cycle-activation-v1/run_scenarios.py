#!/usr/bin/env python3
"""Scénarios hors imprimante de l'activation stock-derived V1."""

from __future__ import annotations

import asyncio
from copy import deepcopy
import importlib.util
import json
import logging
from pathlib import Path
import sys
import tempfile
import types
from typing import Any, Dict, Optional


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load_file(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("module_spec_missing:%s" % name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def import_modules():
    moonraker = types.ModuleType("moonraker")
    moonraker.__path__ = []
    components = types.ModuleType("moonraker.components")
    components.__path__ = []
    common = types.ModuleType("moonraker.common")

    class RequestType:
        GET = "GET"
        POST = "POST"

    class WebRequest:
        pass

    common.RequestType = RequestType
    common.WebRequest = WebRequest
    sys.modules["moonraker"] = moonraker
    sys.modules["moonraker.components"] = components
    sys.modules["moonraker.common"] = common
    core = load_file(
        "moonraker.components.k1_control_stock_cycle_core",
        ROOT / "packages/k1-control-v1/cfs-stock-derived-orchestrator-offline-v1/orchestrator.py",
    )
    active = load_file(
        "moonraker.components.k1_control_stock_cycle_active_core",
        HERE / "active_core.py",
    )
    job = load_file(
        "moonraker.components.k1_control_stock_job_contract",
        HERE / "job_contract.py",
    )
    component = load_file(
        "moonraker.components.k1_control_stock_cycle",
        HERE / "moonraker_component.py",
    )
    return core, active, job, component


CORE, ACTIVE, JOB, COMPONENT = import_modules()
STARTUP = load_file("startup_exclusion_candidate", HERE / "k1_control_cfs_startup_exclusion.py")
RUNOUT = load_file("runout_owner_candidate", HERE / "k1_control_cfs_runout_owner.py")


def material(reference: str = "pla-black", color: str = "black") -> Dict[str, Any]:
    return {
        "reference_id": reference,
        "material_type": "PLA",
        "color": color,
        "diameter_mm": 1.75,
        "thermal_recipe_id": "pla-190",
        "user_approved": True,
    }


def inventory(ambiguous: bool = False):
    values = [
        {"route": "T1A", "available": True, "material": material()},
        {"route": "T2D", "available": True, "material": material()},
        {"route": "T1B", "available": True, "material": material("pla-red", "red")},
    ]
    if ambiguous:
        values.append({"route": "T2C", "available": True, "material": material()})
    return values


def job(filename: str = "owned.gcode") -> Dict[str, Any]:
    return {
        "job_id": "activation-job",
        "filename": filename,
        "initial_route": "T1A",
        "mesh_profile": "k1_p001_t055_r001_n11x11",
        "accepted_z_mm": -0.04,
        "bed_c": 55,
        "probe_nozzle_c": 140,
        "first_nozzle_c": 190,
        "load_c": 190,
        "unload_c": 190,
        "purge_c": 190,
        "purge_mm": 20,
        "material_min_c": 180,
        "material_max_c": 230,
        "release_trips": 4,
        "material_type": "PLA",
    }


class FakeCommandError(RuntimeError):
    pass


class FakeReactor:
    def monotonic(self) -> float:
        return 10.0


class FakeBox:
    def __init__(self, auto_refill: int = 1):
        self.status = {
            "auto_refill": auto_refill,
            "t_command": "",
            "enable": 1,
            "T1": {"state": "connect"},
            "T2": {"state": "connect"},
        }

    def get_status(self, eventtime: float) -> Dict[str, Any]:
        return deepcopy(self.status)


class FakeStartupGcmd:
    def __init__(self):
        self.responses = []

    def error(self, message: str):
        return FakeCommandError(message)

    def respond_info(self, message: str) -> None:
        self.responses.append(message)


class FakeStartupGcode:
    def __init__(self, box: FakeBox, with_stock: bool = True, fail: bool = False):
        self.box = box
        self.handlers = {}
        self.fail = fail
        if with_stock:
            self.handlers["BOX_ENABLE_AUTO_REFILL"] = self.stock_handler

    def stock_handler(self, gcmd) -> None:
        if self.fail:
            raise FakeCommandError("private_handler_failed")
        self.box.status["auto_refill"] = int(gcmd.get("ENABLE"))

    def register_command(self, name: str, handler, desc: Optional[str] = None):
        previous = self.handlers.get(name)
        if handler is None:
            self.handlers.pop(name, None)
        else:
            self.handlers[name] = handler
        return previous

    def create_gcode_command(self, command: str, commandline: str, params: Dict[str, str]):
        class Command:
            def get(self, name: str):
                return params[name]

        return Command()


class FakeStartupPrinter:
    def __init__(self, *, auto_refill: int = 1, with_stock: bool = True, fail: bool = False):
        self.reactor = FakeReactor()
        self.box = FakeBox(auto_refill)
        self.gcode = FakeStartupGcode(self.box, with_stock, fail)
        self.handlers = {}
        self.shutdowns = []

    def get_reactor(self):
        return self.reactor

    def lookup_object(self, name: str, default=None):
        return {"gcode": self.gcode, "box": self.box}.get(name, default)

    def register_event_handler(self, name: str, handler) -> None:
        self.handlers[name] = handler

    def invoke_shutdown(self, message: str) -> None:
        self.shutdowns.append(message)


class FakeStartupConfig:
    def __init__(self, printer: FakeStartupPrinter, enabled: bool = True):
        self.printer = printer
        self.enabled = enabled

    def get_printer(self):
        return self.printer

    def getboolean(self, name: str, default: bool = False) -> bool:
        return self.enabled if name == "enabled" else default

    def get(self, name: str, default=None):
        return default

    def error(self, message: str):
        return FakeCommandError(message)


def scenario_startup_exclusion_calls_only_policy_once() -> None:
    printer = FakeStartupPrinter(auto_refill=1)
    owner = STARTUP.K1ControlCfsStartupExclusion(FakeStartupConfig(printer))
    owner._handle_ready()
    status = owner.get_status(0)
    assert status["ready_verified"] is True
    assert status["policy_call_count"] == 1
    assert status["cfs_frame_count"] == 0
    assert printer.box.status["auto_refill"] == 0
    gcmd = FakeStartupGcmd()
    owner.cmd_SELFTEST(gcmd)
    assert "SELFTEST_V1_OK" in gcmd.responses[0]


def scenario_startup_exclusion_accepts_already_zero_without_call() -> None:
    printer = FakeStartupPrinter(auto_refill=0)
    owner = STARTUP.K1ControlCfsStartupExclusion(FakeStartupConfig(printer))
    owner._handle_ready()
    status = owner.get_status(0)
    assert status["policy_call_count"] == 0
    assert status["policy_already_zero_count"] == 1


def scenario_startup_exclusion_load_order_is_strict() -> None:
    printer = FakeStartupPrinter(with_stock=False)
    try:
        STARTUP.K1ControlCfsStartupExclusion(FakeStartupConfig(printer))
    except FakeCommandError as error:
        assert "load_order" in str(error)
        return
    raise AssertionError("missing_load_order_failure")


def scenario_startup_exclusion_failure_shuts_klipper_down() -> None:
    printer = FakeStartupPrinter(fail=True)
    owner = STARTUP.K1ControlCfsStartupExclusion(FakeStartupConfig(printer))
    previous_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        owner._handle_ready()
    finally:
        logging.disable(previous_disable)
    assert len(printer.shutdowns) == 1
    assert owner.get_status(0)["ready_verified"] is False


class FakeStatusObject:
    def __init__(self, **status):
        self.status = status

    def get_status(self, eventtime: float):
        return deepcopy(self.status)


class FakeDirectOwnerState:
    def __init__(self):
        self.active_route = "T1A"
        self.phase = "loaded"
        self.trace = []

    def result(self):
        return {
            "phase": self.phase,
            "active_route": self.active_route,
            "failure_code": None,
        }


class FakeDirectWrapper:
    def __init__(self):
        self.owner = FakeDirectOwnerState()
        self.last_result = self.owner.result()
        self.last_operation = None
        self.last_effect_id = None

    def blocker(self, gcmd):
        raise gcmd.error("stock command blocked")

    def get_status(self, eventtime: float):
        result = self.last_result or self.owner.result()
        return {
            "owner": "k1_control_cfs_direct_owner",
            "enabled": True,
            "stock_commands_blocked": True,
            "phase": result["phase"],
            "active_route": result["active_route"],
            "failure_code": result.get("failure_code"),
        }


class FakeRunoutGcode:
    def __init__(self, direct: FakeDirectWrapper):
        self.handlers = {"BOX_CHECK_MATERIAL_REFILL": direct.blocker}

    def register_command(self, name: str, handler, desc: Optional[str] = None):
        previous = self.handlers.get(name)
        if handler is None:
            self.handlers.pop(name, None)
        else:
            self.handlers[name] = handler
        return previous


class FakeRunoutPrinter:
    def __init__(self):
        self.reactor = FakeReactor()
        self.direct = FakeDirectWrapper()
        self.gcode = FakeRunoutGcode(self.direct)
        self.head = FakeStatusObject(filament_detected=True, enabled=True)
        self.runout = FakeStatusObject(filament_detected=True, enabled=True)
        self.print_stats = FakeStatusObject(state="standby")
        self.pause_macro = FakeStatusObject(hotend_temp=195.0)
        self.bed = FakeStatusObject(target=55.0)
        self.handlers = {}
        self.shutdowns = []

    def get_reactor(self):
        return self.reactor

    def lookup_object(self, name: str, default=None):
        return {
            "gcode": self.gcode,
            "k1_control_cfs_direct_owner": self.direct,
            "filament_switch_sensor filament_sensor": self.head,
            "filament_switch_sensor filament_sensor_2": self.runout,
            "print_stats": self.print_stats,
            "gcode_macro PRINTER_PARAM": self.pause_macro,
            "heater_bed": self.bed,
        }.get(name, default)

    def register_event_handler(self, name: str, handler) -> None:
        self.handlers[name] = handler

    def invoke_shutdown(self, message: str) -> None:
        self.shutdowns.append(message)


class FakeRunoutConfig:
    def __init__(self, printer: FakeRunoutPrinter):
        self.printer = printer

    def get_printer(self):
        return self.printer

    def getboolean(self, name: str, default: bool = False):
        return True if name == "enabled" else default

    def get(self, name: str, default=None):
        return default

    def error(self, message: str):
        return FakeCommandError(message)


class FakeRunoutGcmd:
    def __init__(self, **params):
        self.params = params
        self.responses = []

    def get(self, name: str):
        return self.params[name]

    def error(self, message: str):
        return FakeCommandError(message)

    def respond_info(self, message: str) -> None:
        self.responses.append(message)


def scenario_runout_owner_replaces_only_blocker_and_releases_without_motor() -> None:
    printer = FakeRunoutPrinter()
    owner = RUNOUT.K1ControlCfsRunoutOwner(FakeRunoutConfig(printer))
    owner._handle_ready()
    owner.cmd_ARM(FakeRunoutGcmd(ROUTE="T1A"))
    printer.print_stats.status["state"] = "paused"
    printer.runout.status["filament_detected"] = False
    owner.cmd_LATCH(FakeRunoutGcmd())
    assert owner.event_seq == 1 and owner.last_nozzle_target_c == 195.0
    try:
        owner.cmd_RELEASE(FakeRunoutGcmd(ROUTE="T1A", EFFECT_ID="runout-001"))
    except FakeCommandError as error:
        assert "tail_not_clear" in str(error)
    else:
        raise AssertionError("head_tail_not_refused")
    printer.head.status["filament_detected"] = False
    owner.cmd_RELEASE(FakeRunoutGcmd(ROUTE="T1A", EFFECT_ID="runout-001"))
    status = owner.get_status(0)
    assert status["consumed_seq"] == 1
    assert status["logical_release_count"] == 1
    assert status["motor_effect_count"] == 0 and status["cfs_frame_count"] == 0
    assert printer.direct.owner.active_route is None
    assert printer.direct.owner.phase == "idle"


def scenario_active_core_claims_reconcile_before_preclean_unload() -> None:
    owner = ACTIVE.ActiveStockDerivedOrchestrator(job(), inventory())
    owner.acquire_owner(0, 0, True)
    owner.observe_initial_filament(["T1A"], True, True)
    ticket = owner.plan_preclean_unload()
    lines = ticket["command"].splitlines()
    assert lines[0].startswith("KCTRL_CFS_DIRECT_RECONCILE ROUTE=T1A")
    assert lines[1] == "KCTRL_CFS_RUNOUT_DISARM_V1"
    assert "SET_FILAMENT_SENSOR SENSOR=filament_sensor_2 ENABLE=0" in lines
    assert any("KCTRL_STOCK_CYCLE_CUT_UNLOAD_V1" in line for line in lines)
    assert owner.state["tickets"][ticket["ticket_id"]]["status"] == "claimed"


def scenario_active_core_geometry_ticket_contains_handoff() -> None:
    owner = ACTIVE.ActiveStockDerivedOrchestrator(job(), inventory())
    owner.acquire_owner(0, 0, True)
    owner.observe_initial_filament([], False, False)
    owner.confirm_manual_clean(fresh=True, filament_loaded=False)
    ticket = owner.plan_geometry()
    assert "KCTRL_PREPARE_GEOMETRY_BEFORE_INSERTION_R4" in ticket["command"]
    assert "KCTRL_STOCK_GEOMETRY_HANDOFF_TAKE_V1" in ticket["command"]


def scenario_safe_close_without_filament_has_no_command() -> None:
    owner = ACTIVE.ActiveStockDerivedOrchestrator(job(), inventory())
    owner.acquire_owner(0, 0, True)
    owner.observe_initial_filament([], False, False)
    result = owner.plan_safe_close("operator_abort")
    assert result["ticket_id"] is None
    assert owner.state["phase"] == "owner_release_pending"


def scenario_job_contract_requires_owned_boundaries() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "owned.gcode"
        path.write_text(
            "KCTRL_STOCK_JOB_ASSERT_V1\nG1 X10 Y10\nKCTRL_STOCK_JOB_END_V1\n",
            encoding="utf-8",
        )
        metadata = {
            "slicer": "OrcaSlicer",
            "filament_type": "PLA",
            "first_layer_extr_temp": 190,
            "first_layer_bed_temp": 55,
            "referenced_tools": [0],
        }
        result = JOB.build_job_contract("owned.gcode", metadata, path, "T1A")
        assert result["mesh_profile"] == "k1_p001_t055_r001_n11x11"
        path.write_text(
            "KCTRL_STOCK_JOB_ASSERT_V1\nG28\nKCTRL_STOCK_JOB_END_V1\n",
            encoding="utf-8",
        )
        try:
            JOB.build_job_contract("owned.gcode", metadata, path, "T1A")
        except JOB.JobContractError as error:
            assert "forbidden_gcode_command:G28" == error.code
        else:
            raise AssertionError("G28_not_rejected")
        for forbidden in ("M104 S0", "TURN_OFF_HEATERS"):
            path.write_text(
                "KCTRL_STOCK_JOB_ASSERT_V1\n%s\nKCTRL_STOCK_JOB_END_V1\n"
                % forbidden,
                encoding="utf-8",
            )
            try:
                JOB.build_job_contract("owned.gcode", metadata, path, "T1A")
            except JOB.JobContractError as error:
                if forbidden == "M104 S0":
                    assert error.code == "premature_owner_shutdown_command:M104"
                else:
                    assert error.code == "forbidden_gcode_command:TURN_OFF_HEATERS"
            else:
                raise AssertionError("end_heat_override_not_rejected:%s" % forbidden)


class FakeServerError(RuntimeError):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


class FakeLoop:
    async def run_in_thread(self, function, *args):
        return function(*args)


class FakeMetadata:
    def __init__(self, metadata):
        self.metadata = metadata

    def get(self, filename, default=None):
        return deepcopy(self.metadata) if filename == "owned.gcode" else default


class FakeFileManager:
    def __init__(self, root: Path):
        self.root = root
        self.metadata = FakeMetadata({
            "slicer": "OrcaSlicer",
            "filament_type": "PLA",
            "first_layer_extr_temp": 190,
            "first_layer_bed_temp": 55,
            "referenced_tools": [0],
        })

    def get_metadata_storage(self):
        return self.metadata

    def get_file_list(self, root: str, list_format: bool = True):
        return [{"path": "owned.gcode", "modified": 1, "size": 64}]

    def check_file_exists(self, root: str, filename: str) -> bool:
        return filename == "owned.gcode"

    def get_directory(self, root: str) -> str:
        return str(self.root)


def base_raw() -> Dict[str, Any]:
    return {
        "webhooks": {"state": "ready", "state_message": "ready"},
        "print_stats": {"state": "standby", "filename": ""},
        "extruder": {"target": 0.0, "temperature": 25.0},
        "heater_bed": {"target": 0.0, "temperature": 25.0},
        "toolhead": {"homed_axes": "", "position": [0.0, 0.0, 0.0]},
        "gcode_move": {"homing_origin": [0.0, 0.0, -0.04]},
        "bed_mesh": {"profile_name": "k1_p001_t055_r001_n11x11"},
        "box": {
            "auto_refill": 0,
            "t_command": "",
            "enable": 1,
            "T1": {"state": "connect", "filament": "None"},
            "T2": {"state": "connect", "filament": "None"},
        },
        "filament_switch_sensor filament_sensor": {
            "filament_detected": False,
            "enabled": True,
        },
        "filament_switch_sensor filament_sensor_2": {
            "filament_detected": False,
            "enabled": True,
        },
        "gcode_macro PRINTER_PARAM": {
            "hotend_temp": 0.0,
            "z_safe_pause": 5,
            "fan2_speed": 0,
        },
        "gcode_macro KCTRL_STATE": {"accepted_z_valid": 1, "accepted_z_offset": -0.04},
        "gcode_macro KCTRL_START_OWNER_STATE": {"phase": "idle"},
        "gcode_macro KCTRL_STOCK_CYCLE_EMPTY_END_STATE": {
            "completed": 0,
            "last_effect_id": "none",
        },
        "k1_control_cfs_startup_exclusion": {"enabled": True, "ready_verified": True},
        "k1_control_cfs_direct_owner": {
            "enabled": True,
            "stock_commands_blocked": True,
            "active_route": None,
            "phase": "idle",
            "failure_code": None,
        },
        "k1_control_cfs_runout_owner": {
            "enabled": True,
            "ready_verified": True,
            "stock_handler_isolated": True,
            "public_box_check_owned": True,
            "armed": False,
            "event_seq": 0,
            "consumed_seq": 0,
            "last_route": None,
            "logical_release_count": 0,
        },
        "k1_control_stock_cycle_owner": {"enabled": True, "last_operation": None},
        "k1_control_stock_geometry_handoff": {"enabled": True, "last_token": None},
    }


class FakeKlippy:
    def __init__(self):
        self.raw = base_raw()
        self.scripts = []
        self.started = []

    async def query_objects(self, objects):
        return deepcopy(self.raw)

    async def run_gcode(self, script: str):
        self.scripts.append(script)
        if "KCTRL_CFS_RUNOUT_DISARM_V1" in script:
            self.raw["k1_control_cfs_runout_owner"]["armed"] = False
        if "SET_FILAMENT_SENSOR SENSOR=filament_sensor ENABLE=0" in script:
            self.raw["filament_switch_sensor filament_sensor"]["enabled"] = False
        if "SET_FILAMENT_SENSOR SENSOR=filament_sensor_2 ENABLE=0" in script:
            self.raw["filament_switch_sensor filament_sensor_2"]["enabled"] = False
        if "SET_FILAMENT_SENSOR SENSOR=filament_sensor ENABLE=1" in script:
            self.raw["filament_switch_sensor filament_sensor"]["enabled"] = True
        if "SET_FILAMENT_SENSOR SENSOR=filament_sensor_2 ENABLE=1" in script:
            self.raw["filament_switch_sensor filament_sensor_2"]["enabled"] = True
        if "KCTRL_PREPARE_GEOMETRY_BEFORE_INSERTION_R4" in script:
            self.raw["toolhead"]["homed_axes"] = "xyz"
            self.raw["gcode_move"]["homing_origin"][2] = -0.04
            self.raw["k1_control_stock_geometry_handoff"]["last_token"] = "geometry_ready_for_stock_cycle"
        if "KCTRL_STOCK_CYCLE_CUT_UNLOAD_V1" in script:
            self.raw["k1_control_cfs_direct_owner"]["active_route"] = None
            self.raw["k1_control_cfs_direct_owner"]["phase"] = "idle"
            self.raw["filament_switch_sensor filament_sensor"]["filament_detected"] = False
            self.raw["filament_switch_sensor filament_sensor_2"]["filament_detected"] = False
        if "KCTRL_CFS_RUNOUT_RELEASE_V1" in script:
            self.raw["k1_control_cfs_direct_owner"]["active_route"] = None
            self.raw["k1_control_cfs_direct_owner"]["phase"] = "idle"
            runout = self.raw["k1_control_cfs_runout_owner"]
            runout["consumed_seq"] = runout["event_seq"]
            runout["logical_release_count"] += 1
        if "KCTRL_STOCK_CYCLE_LOAD_PURGE_V1" in script:
            route = script.split("KCTRL_STOCK_CYCLE_LOAD_PURGE_V1 ROUTE=", 1)[1].split()[0]
            self.raw["k1_control_cfs_direct_owner"]["active_route"] = route
            self.raw["k1_control_cfs_direct_owner"]["phase"] = "loaded"
            self.raw["filament_switch_sensor filament_sensor"]["filament_detected"] = True
            self.raw["filament_switch_sensor filament_sensor_2"]["filament_detected"] = True
            self.raw["k1_control_stock_cycle_owner"]["last_operation"] = "load_purge"
            load_c = script.split(" LOAD_C=", 1)[1].split()[0]
            self.raw["extruder"]["target"] = float(load_c)
        if "KCTRL_STOCK_CYCLE_PRIME_V1" in script:
            self.raw["k1_control_stock_cycle_owner"]["last_operation"] = "prime"
        if "KCTRL_CFS_RUNOUT_ARM_V1 ROUTE=" in script:
            self.raw["k1_control_cfs_runout_owner"]["armed"] = True
        if script == "PAUSE":
            self.raw["gcode_macro PRINTER_PARAM"]["hotend_temp"] = self.raw["extruder"]["target"]
            self.raw["extruder"]["target"] = 140.0
            self.raw["print_stats"]["state"] = "paused"
        if script.startswith("KCTRL_STOCK_RESUME_OWNED_V1 TARGET_C="):
            target = float(script.split("TARGET_C=", 1)[1])
            self.raw["extruder"]["target"] = target
            self.raw["gcode_macro PRINTER_PARAM"]["hotend_temp"] = 0.0
            self.raw["print_stats"]["state"] = "printing"
        if "KCTRL_STOCK_CYCLE_END_V1" in script:
            self.raw["k1_control_cfs_direct_owner"]["active_route"] = None
            self.raw["k1_control_cfs_direct_owner"]["phase"] = "idle"
            self.raw["filament_switch_sensor filament_sensor"]["filament_detected"] = False
            self.raw["filament_switch_sensor filament_sensor_2"]["filament_detected"] = False
            self.raw["extruder"]["target"] = 0.0
            self.raw["heater_bed"]["target"] = 0.0
            self.raw["toolhead"]["homed_axes"] = ""
            self.raw["toolhead"]["position"] = [203.0, 273.0, 50.0]
            self.raw["k1_control_stock_cycle_owner"]["last_operation"] = "end"
        if "KCTRL_STOCK_CYCLE_EMPTY_END_V1" in script:
            effect_id = script.split(
                "KCTRL_STOCK_CYCLE_EMPTY_END_V1 EFFECT_ID=", 1
            )[1].split()[0]
            self.raw["extruder"]["target"] = 0.0
            self.raw["heater_bed"]["target"] = 0.0
            self.raw["toolhead"]["homed_axes"] = ""
            self.raw["toolhead"]["position"] = [203.0, 273.0, 50.0]
            self.raw["print_stats"]["state"] = "standby"
            self.raw["gcode_macro KCTRL_STOCK_CYCLE_EMPTY_END_STATE"] = {
                "completed": 1,
                "last_effect_id": effect_id,
            }

    async def start_print(self, filename: str):
        self.started.append(filename)
        self.raw["print_stats"] = {"state": "printing", "filename": filename}

    def emit_runout(self) -> None:
        runout = self.raw["k1_control_cfs_runout_owner"]
        if runout["armed"] is not True:
            raise AssertionError("runout_not_armed")
        self.raw["gcode_macro PRINTER_PARAM"]["hotend_temp"] = self.raw["extruder"]["target"]
        self.raw["extruder"]["target"] = 140.0
        self.raw["print_stats"]["state"] = "paused"
        self.raw["filament_switch_sensor filament_sensor"]["filament_detected"] = False
        self.raw["filament_switch_sensor filament_sensor_2"]["filament_detected"] = False
        runout["event_seq"] += 1
        runout["last_route"] = self.raw["k1_control_cfs_direct_owner"]["active_route"]
        runout["armed"] = False


class FakeServer:
    def __init__(self, file_manager, klippy):
        self.file_manager = file_manager
        self.klippy = klippy
        self.endpoints = {}
        self.events = []
        self.loop = FakeLoop()

    def lookup_component(self, name: str):
        return {"file_manager": self.file_manager, "klippy_apis": self.klippy}[name]

    def register_notification(self, name: str):
        return None

    def register_endpoint(self, path, request_type, handler):
        self.endpoints[path] = (request_type, handler)

    def send_event(self, name: str, payload):
        self.events.append((name, payload))

    def error(self, message: str, status_code: int = 500):
        return FakeServerError(message, status_code)

    def get_event_loop(self):
        return self.loop


class FakeComponentConfig:
    def __init__(self, server: FakeServer, root: Path):
        self.server = server
        self.root = root

    def get_server(self):
        return self.server

    def get(self, name: str, default=None):
        values = {
            "enabled": "true",
            "selection_path": str(self.root / "selection.json"),
            "run_path": str(self.root / "run.json"),
        }
        return values.get(name, default)

    def error(self, message: str):
        return FakeServerError(message)


class FakeRequest:
    def __init__(self, **values):
        self.values = values

    def get_boolean(self, name: str, default: bool = False):
        return self.values.get(name, default)

    def get_str(self, name: str):
        return str(self.values[name])


def make_component(root: Path):
    (root / "owned.gcode").write_text(
        "KCTRL_STOCK_JOB_ASSERT_V1\nG1 X10 Y10\nKCTRL_STOCK_JOB_END_V1\n",
        encoding="utf-8",
    )
    klippy = FakeKlippy()
    files = FakeFileManager(root)
    server = FakeServer(files, klippy)
    component = COMPONENT.K1ControlStockCycle(FakeComponentConfig(server, root))
    component._start_monitor = lambda: None
    return component, klippy, server


async def complete_flow(root: Path, inventory_values=None):
    component, klippy, server = make_component(root)
    await component._inventory(FakeRequest(
        inventory_json=json.dumps(
            inventory() if inventory_values is None else inventory_values
        )
    ))
    await component._select(FakeRequest(filename="owned.gcode", initial_route="T1A"))
    await component._begin(FakeRequest(operator_present=True, camera_available=True, machine_clear=True))
    assert component.engine.state["phase"] == "await_manual_clean"
    await component._clean_confirm(FakeRequest(
        operator_confirmed=True,
        nozzle_visibly_clean=True,
        plate_clean=True,
        confirmation_fresh=True,
    ))
    assert component.engine.state["phase"] == "await_release_camera"
    await component._camera_verdict(FakeRequest(verdict="PASS", evidence_id="release-001"))
    assert component.engine.state["phase"] == "await_prime_camera"
    await component._camera_verdict(FakeRequest(verdict="PASS", evidence_id="prime-001"))
    assert component.engine.state["phase"] == "printing"
    return component, klippy, server


def scenario_component_full_start_has_no_post_filament_probe() -> None:
    with tempfile.TemporaryDirectory() as directory:
        component, klippy, _server = asyncio.run(complete_flow(Path(directory)))
        scripts = "\n".join(klippy.scripts)
        load_at = scripts.index("KCTRL_STOCK_CYCLE_LOAD_PURGE_V1")
        after_load = scripts[load_at:]
        assert "G28" not in after_load
        assert "BED_MESH_CALIBRATE" not in after_load
        assert component._public_state()["post_filament_probe_count"] == 0


def scenario_component_equivalent_runout_resumes_on_unique_spare() -> None:
    with tempfile.TemporaryDirectory() as directory:
        component, klippy, _server = asyncio.run(complete_flow(Path(directory)))

        async def flow():
            klippy.raw["extruder"]["target"] = 195.0
            klippy.raw["heater_bed"]["target"] = 55.0
            klippy.emit_runout()
            await component._runout_locked()
            assert component.engine.state["phase"] == "await_refill_camera"
            assert component.engine.state["planned_target_route"] == "T2D"
            refill_script = klippy.scripts[-1]
            assert "KCTRL_CFS_RUNOUT_RELEASE_V1 ROUTE=T1A" in refill_script
            assert "KCTRL_STOCK_CYCLE_CUT_UNLOAD_V1" not in refill_script
            assert "LOAD_C=195" in refill_script and "PURGE_C=195" in refill_script
            assert "220" not in refill_script and "LOAD_C=140" not in refill_script
            await component._camera_verdict(FakeRequest(verdict="PASS", evidence_id="refill-001"))
            assert component.engine.state["phase"] == "printing"
            assert component.engine.state["equivalent_refills"] == 1
            assert klippy.raw["k1_control_cfs_direct_owner"]["active_route"] == "T2D"
            assert klippy.raw["extruder"]["target"] == 195.0
            assert all(script != "RESUME" for script in klippy.scripts)

        asyncio.run(flow())


def scenario_sensor_state_without_owned_event_never_refills() -> None:
    with tempfile.TemporaryDirectory() as directory:
        component, klippy, _server = asyncio.run(complete_flow(Path(directory)))

        async def flow():
            before = len(klippy.scripts)
            klippy.raw["print_stats"]["state"] = "paused"
            klippy.raw["filament_switch_sensor filament_sensor"]["filament_detected"] = False
            klippy.raw["filament_switch_sensor filament_sensor_2"]["filament_detected"] = False
            try:
                await component._runout_locked()
            except COMPONENT.ControllerError as error:
                assert error.code == "fresh_runout_signal_missing"
            else:
                raise AssertionError("sensor_only_refill_not_refused")
            assert len(klippy.scripts) == before
            assert component.engine.state["phase"] == "printing"

        asyncio.run(flow())


def scenario_no_unique_spare_closes_cold_without_cutter() -> None:
    cases = []
    ambiguous = inventory(ambiguous=True)
    cases.append(ambiguous)
    unavailable = inventory()
    unavailable[1]["available"] = False
    cases.append(unavailable)
    near_match = inventory()
    near_match[1]["material"] = material()
    near_match[1]["material"]["thermal_recipe_id"] = "pla-205"
    cases.append(near_match)

    for index, inventory_values in enumerate(cases, start=1):
        with tempfile.TemporaryDirectory() as directory:
            component, klippy, _server = asyncio.run(
                complete_flow(Path(directory), inventory_values)
            )

            async def flow():
                klippy.raw["extruder"]["target"] = 195.0
                klippy.raw["heater_bed"]["target"] = 55.0
                before = len(klippy.scripts)
                klippy.emit_runout()
                await component._runout_locked()
                scripts = "\n".join(klippy.scripts[before:])
                assert "KCTRL_CFS_RUNOUT_RELEASE_V1 ROUTE=T1A" in scripts
                assert "KCTRL_STOCK_CYCLE_EMPTY_END_V1" in scripts
                assert "KCTRL_STOCK_CYCLE_CUT_UNLOAD_V1" not in scripts
                assert "KCTRL_STOCK_CYCLE_LOAD_PURGE_V1" not in scripts
                assert component.engine.state["phase"] == "closed_safe"
                assert klippy.raw["extruder"]["target"] == 0.0
                assert klippy.raw["heater_bed"]["target"] == 0.0
                assert klippy.raw["toolhead"]["homed_axes"] == ""

            try:
                asyncio.run(flow())
            except Exception as error:
                raise AssertionError("no_spare_case_%d:%r" % (index, error)) from error


def scenario_tool_change_keeps_gcode_temperature_and_uses_cutter() -> None:
    with tempfile.TemporaryDirectory() as directory:
        component, klippy, _server = asyncio.run(complete_flow(Path(directory)))

        async def flow():
            klippy.raw["extruder"]["target"] = 205.0
            await component._tool_change(FakeRequest(target_route="T1B"))
            script = klippy.scripts[-1]
            assert "KCTRL_STOCK_CYCLE_CUT_UNLOAD_V1 ROUTE=T1A" in script
            assert "KCTRL_STOCK_CYCLE_LOAD_PURGE_V1 ROUTE=T1B" in script
            assert "UNLOAD_C=205" in script
            assert "LOAD_C=205" in script and "PURGE_C=205" in script
            await component._camera_verdict(
                FakeRequest(verdict="PASS", evidence_id="tool-change-001")
            )
            assert component.engine.state["phase"] == "printing"
            assert klippy.raw["extruder"]["target"] == 205.0
            assert all(script != "RESUME" for script in klippy.scripts)

        asyncio.run(flow())


def scenario_component_normal_end_cuts_unloads_and_closes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        component, klippy, _server = asyncio.run(complete_flow(Path(directory)))

        async def flow():
            await component._normal_end_locked()
            assert component.engine.state["phase"] == "closed_safe"
            assert component.engine.state["active_route"] is None
            assert klippy.raw["toolhead"]["position"][:2] == [203.0, 273.0]
            assert klippy.raw["toolhead"]["homed_axes"] == ""

        asyncio.run(flow())


def scenario_claimed_ticket_restart_becomes_uncertain_without_dispatch() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        component, klippy, _server = make_component(root)
        engine = ACTIVE.ActiveStockDerivedOrchestrator(job(), inventory())
        engine.acquire_owner(0, 0, True)
        engine.observe_initial_filament([], False, False)
        engine.confirm_manual_clean(fresh=True, filament_loaded=False)
        engine.plan_geometry()
        record = {
            "schema": 1,
            "job": engine.job,
            "inventory": inventory(),
            "state": engine.state,
            "controller": {},
        }
        (root / "run.json").write_text(json.dumps(record), encoding="utf-8")
        reloaded, reloaded_klippy, _server = make_component(root)
        assert reloaded.engine.state["phase"] == "blocked_uncertain"
        assert reloaded.engine.state["last_error"] == "claimed_ticket_recovered_without_outcome"
        assert reloaded_klippy.scripts == []


def scenario_claimed_refill_restart_never_replays_and_keeps_inventory() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        component, klippy, _server = asyncio.run(complete_flow(root))

        async def claim_only():
            klippy.raw["extruder"]["target"] = 195.0
            klippy.raw["heater_bed"]["target"] = 55.0
            klippy.emit_runout()
            paused = await component._query()
            context = component._pause_context(paused, runout_signal=True)
            component.controller["pause_context"] = context
            ticket = component.engine.plan_equivalent_refill(context)
            component._persist_run()
            return ticket["ticket_id"]

        ticket_id = asyncio.run(claim_only())
        persisted = json.loads((root / "run.json").read_text(encoding="utf-8"))
        assert {item["route"] for item in persisted["inventory"]} == {
            "T1A", "T1B", "T2D"
        }
        assert persisted["state"]["tickets"][ticket_id]["status"] == "claimed"
        reloaded, reloaded_klippy, _server = make_component(root)
        assert reloaded.engine.state["phase"] == "blocked_uncertain"
        assert reloaded.engine.state["tickets"][ticket_id]["status"] == "uncertain"
        assert reloaded_klippy.scripts == []


def scenario_camera_pass_does_not_advance_engine_before_resume_proof() -> None:
    with tempfile.TemporaryDirectory() as directory:
        component, klippy, _server = asyncio.run(complete_flow(Path(directory)))

        async def flow():
            klippy.raw["extruder"]["target"] = 205.0
            await component._tool_change(FakeRequest(target_route="T1B"))
            assert component.engine.state["phase"] == "await_tool_change_camera"

            async def refuse_resume():
                raise COMPONENT.ControllerError("synthetic_resume_refusal")

            component._owned_resume = refuse_resume
            try:
                await component._camera_verdict(
                    FakeRequest(verdict="PASS", evidence_id="tool-change-resume-ko")
                )
            except FakeServerError as error:
                assert "synthetic_resume_refusal" in str(error)
            else:
                raise AssertionError("resume_refusal_not_propagated")
            assert component.engine.state["phase"] == "await_tool_change_camera"
            assert component.engine.state["tool_changes"] == 0

        asyncio.run(flow())


SCENARIOS = (
    scenario_startup_exclusion_calls_only_policy_once,
    scenario_startup_exclusion_accepts_already_zero_without_call,
    scenario_startup_exclusion_load_order_is_strict,
    scenario_startup_exclusion_failure_shuts_klipper_down,
    scenario_runout_owner_replaces_only_blocker_and_releases_without_motor,
    scenario_active_core_claims_reconcile_before_preclean_unload,
    scenario_active_core_geometry_ticket_contains_handoff,
    scenario_safe_close_without_filament_has_no_command,
    scenario_job_contract_requires_owned_boundaries,
    scenario_component_full_start_has_no_post_filament_probe,
    scenario_component_equivalent_runout_resumes_on_unique_spare,
    scenario_sensor_state_without_owned_event_never_refills,
    scenario_no_unique_spare_closes_cold_without_cutter,
    scenario_tool_change_keeps_gcode_temperature_and_uses_cutter,
    scenario_component_normal_end_cuts_unloads_and_closes,
    scenario_claimed_ticket_restart_becomes_uncertain_without_dispatch,
    scenario_claimed_refill_restart_never_replays_and_keeps_inventory,
    scenario_camera_pass_does_not_advance_engine_before_resume_proof,
)


def run() -> Dict[str, Any]:
    results = []
    for scenario in SCENARIOS:
        name = scenario.__name__.replace("scenario_", "", 1)
        try:
            scenario()
            results.append({"name": name, "passed": True})
        except Exception as error:
            results.append({"name": name, "passed": False, "error": repr(error)})
    passed = sum(1 for item in results if item["passed"])
    return {
        "status": "OK" if passed == len(results) else "KO",
        "passed": passed,
        "total": len(results),
        "cases": results,
        "printer_transport": False,
        "physical_action": False,
        "automatic_retry": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True))
