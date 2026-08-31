#!/usr/bin/env python3
"""Scénarios déterministes du handoff et du composant Moonraker désactivés."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import sys
import types
from pathlib import Path
from typing import Any, Dict, Optional


HERE = Path(__file__).resolve().parent


def import_geometry():
    spec = importlib.util.spec_from_file_location(
        "k1_control_stock_geometry_handoff_candidate",
        HERE / "k1_control_stock_geometry_handoff.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("geometry_import_spec_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def import_moonraker():
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
    core = types.ModuleType(
        "moonraker.components.k1_control_stock_cycle_core"
    )
    core.CURRENT_PROFILE = "k1_p001_t055_r001_n11x11"
    core.CURRENT_BED_C = 55.0
    core.CURRENT_PROBE_C = 140.0
    core.CURRENT_FIRST_C = 190.0
    core.CURRENT_Z_MM = -0.04
    sys.modules["moonraker"] = moonraker
    sys.modules["moonraker.components"] = components
    sys.modules["moonraker.common"] = common
    sys.modules["moonraker.components.k1_control_stock_cycle_core"] = core
    spec = importlib.util.spec_from_file_location(
        "moonraker.components.k1_control_stock_cycle",
        HERE / "moonraker_component.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("moonraker_import_spec_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GEOMETRY = import_geometry()
MOONRAKER = import_moonraker()


class FakeCommandError(RuntimeError):
    pass


class FakeReactor:
    def monotonic(self) -> float:
        return 123.0


class FakeStatus:
    def __init__(self, value: Dict[str, Any]):
        self.value = dict(value)

    def get_status(self, eventtime: float) -> Dict[str, Any]:
        return dict(self.value)


class FakeGcode:
    def __init__(self):
        self.commands: Dict[str, Any] = {}
        self.scripts = []
        self.fail_at: Optional[str] = None

    def register_command(self, name: str, handler, desc: Optional[str] = None):
        previous = self.commands.get(name)
        self.commands[name] = handler
        return previous

    def run_script_from_command(self, command: str) -> None:
        self.scripts.append(command)
        if self.fail_at == command:
            raise FakeCommandError("simulated_uncertain_failure")


def exact_status() -> Dict[str, Dict[str, Any]]:
    return {
        "gcode_macro KCTRL_START_OWNER_STATE": {
            "phase": "geometry_ready_for_insertion",
            "geometry_ready_token": 1,
            "watchdog_armed": 1,
            "job_bed": 55.0,
            "job_probe_nozzle": 140.0,
            "job_first_nozzle": 190.0,
            "job_plate": 1,
            "job_probe_rev": 1,
            "job_nozzle_id": 1,
            "job_config_id": 1,
            "job_x_count": 11,
            "job_y_count": 11,
        },
        "gcode_macro KCTRL_STATE": {
            "accepted_z_valid": 1,
            "low_moves_armed": 1,
            "accepted_z_offset": -0.04,
        },
        "box": {
            "auto_refill": 0,
            "t_command": "",
            "T1": {"state": "connect", "filament": None},
            "T2": {"state": "connect", "filament": "None"},
        },
        "toolhead": {"homed_axes": "xyz"},
        "bed_mesh": {"profile_name": "k1_p001_t055_r001_n11x11"},
        "gcode_move": {"homing_origin": [0.0, 0.0, -0.04]},
    }


class FakePrinter:
    def __init__(self, statuses: Optional[Dict[str, Dict[str, Any]]] = None):
        self.reactor = FakeReactor()
        self.gcode = FakeGcode()
        self.objects: Dict[str, Any] = {"gcode": self.gcode}
        for name, value in (statuses or exact_status()).items():
            self.objects[name] = FakeStatus(value)
        self.handlers = {}

    def get_reactor(self):
        return self.reactor

    def lookup_object(self, name: str, default=None):
        return self.objects.get(name, default)

    def register_event_handler(self, name: str, handler) -> None:
        self.handlers[name] = handler


class FakeGeometryConfig:
    def __init__(self, printer: FakePrinter, *, enabled: bool):
        self.printer = printer
        self.enabled = enabled

    def get_printer(self):
        return self.printer

    def getboolean(self, name: str, default: bool = False) -> bool:
        return self.enabled if name == "enabled" else default


class FakeGcmd:
    def __init__(self, values: Optional[Dict[str, Any]] = None, *, forbid_reads: bool = False):
        self.values = dict(values or {})
        self.forbid_reads = forbid_reads
        self.read_count = 0
        self.responses = []

    def get(self, name: str):
        self.read_count += 1
        if self.forbid_reads:
            raise AssertionError("argument_read_while_disabled:%s" % name)
        return self.values[name]

    def error(self, message: str):
        return FakeCommandError(message)

    def respond_info(self, message: str) -> None:
        self.responses.append(message)


def make_geometry(*, enabled: bool, statuses=None):
    printer = FakePrinter(statuses)
    owner = GEOMETRY.K1ControlStockGeometryHandoff(
        FakeGeometryConfig(printer, enabled=enabled)
    )
    return owner, printer


def expect_error(call, code: str) -> None:
    try:
        call()
    except Exception as error:
        if code not in str(error):
            raise AssertionError("wrong_error:%s" % error)
        return
    raise AssertionError("expected_error_missing:%s" % code)


def scenario_geometry_disabled_selftest() -> None:
    owner, printer = make_geometry(enabled=False)
    gcmd = FakeGcmd()
    owner.cmd_DISABLED_SELFTEST(gcmd)
    assert gcmd.responses == [
        "KCTRL_STOCK_GEOMETRY_HANDOFF_DISABLED_SELFTEST_V1_OK refused=1"
    ]
    assert printer.gcode.scripts == []
    assert owner.get_status(0)["handoff_count"] == 0


def scenario_geometry_disabled_refuses_before_arguments() -> None:
    owner, printer = make_geometry(enabled=False)
    gcmd = FakeGcmd(forbid_reads=True)
    expect_error(lambda: owner.cmd_TAKE(gcmd), "stock_geometry_handoff_disabled")
    assert gcmd.read_count == 0
    assert printer.gcode.scripts == []


def scenario_geometry_exact_context_consumes_only_r4_token() -> None:
    owner, printer = make_geometry(enabled=True)
    gcmd = FakeGcmd({"EFFECT_ID": "geometry-handoff-1"})
    owner.cmd_TAKE(gcmd)
    assert owner.get_status(0)["last_token"] == "geometry_ready_for_stock_cycle"
    assert len(printer.gcode.scripts) == 6
    assert all(
        command.startswith(("UPDATE_DELAYED_GCODE", "SET_GCODE_VARIABLE"))
        for command in printer.gcode.scripts
    )
    forbidden = ("G0", "G1", "G28", "M104", "M109", "M140", "M190", "BED_MESH", "BOX_", "KCTRL_CFS_DIRECT")
    assert not any(command.startswith(forbidden) for command in printer.gcode.scripts)


def scenario_geometry_stock_refill_must_already_be_off() -> None:
    statuses = exact_status()
    statuses["box"]["auto_refill"] = 1
    owner, printer = make_geometry(enabled=True, statuses=statuses)
    expect_error(
        lambda: owner.cmd_TAKE(FakeGcmd({"EFFECT_ID": "geometry-handoff-2"})),
        "filament_or_stock_owner_present_before_handoff",
    )
    assert printer.gcode.scripts == []


def scenario_geometry_filament_route_refused() -> None:
    statuses = exact_status()
    statuses["box"]["T1"] = {"state": "connect", "filament": "A"}
    owner, printer = make_geometry(enabled=True, statuses=statuses)
    expect_error(
        lambda: owner.cmd_TAKE(FakeGcmd({"EFFECT_ID": "geometry-handoff-3"})),
        "filament_or_stock_owner_present_before_handoff",
    )
    assert printer.gcode.scripts == []


def scenario_geometry_mesh_or_z_drift_refused() -> None:
    for field, value in (("mesh", "default"), ("z", -0.03)):
        statuses = exact_status()
        if field == "mesh":
            statuses["bed_mesh"]["profile_name"] = value
            expected = "mesh_profile_changed"
        else:
            statuses["gcode_move"]["homing_origin"][2] = value
            expected = "accepted_Z_changed"
        owner, printer = make_geometry(enabled=True, statuses=statuses)
        expect_error(
            lambda owner=owner: owner.cmd_TAKE(
                FakeGcmd({"EFFECT_ID": "geometry-handoff-drift"})
            ),
            expected,
        )
        assert printer.gcode.scripts == []


def scenario_geometry_effect_is_never_replayed() -> None:
    owner, printer = make_geometry(enabled=True)
    owner.cmd_TAKE(FakeGcmd({"EFFECT_ID": "geometry-handoff-once"}))
    commands = list(printer.gcode.scripts)
    expect_error(
        lambda: owner.cmd_TAKE(FakeGcmd({"EFFECT_ID": "geometry-handoff-once"})),
        "effect_id_already_claimed_no_retry",
    )
    assert printer.gcode.scripts == commands


def scenario_geometry_partial_failure_is_uncertain_no_retry() -> None:
    owner, printer = make_geometry(enabled=True)
    printer.gcode.fail_at = (
        "SET_GCODE_VARIABLE MACRO=KCTRL_START_OWNER_STATE "
        "VARIABLE=geometry_ready_token VALUE=0"
    )
    logging.disable(logging.CRITICAL)
    try:
        expect_error(
            lambda: owner.cmd_TAKE(FakeGcmd({"EFFECT_ID": "geometry-handoff-fail"})),
            "command_failed_uncertain_no_retry",
        )
    finally:
        logging.disable(logging.NOTSET)
    commands = list(printer.gcode.scripts)
    expect_error(
        lambda: owner.cmd_TAKE(FakeGcmd({"EFFECT_ID": "geometry-handoff-fail"})),
        "effect_id_already_claimed_no_retry",
    )
    assert printer.gcode.scripts == commands


class FakeServerError(RuntimeError):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


class FakeServer:
    def __init__(self):
        self.notifications = []
        self.endpoints = {}

    def register_notification(self, name: str) -> None:
        self.notifications.append(name)

    def register_endpoint(self, path: str, request_type: str, handler) -> None:
        self.endpoints[path] = (request_type, handler)

    def error(self, message: str, status_code: int = 500):
        return FakeServerError(message, status_code)


class FakeMoonrakerConfig:
    def __init__(self, *, enabled: str = "false"):
        self.server = FakeServer()
        self.enabled = enabled

    def get_server(self):
        return self.server

    def get(self, name: str, default=None):
        if name == "enabled":
            return self.enabled
        return default

    def error(self, message: str):
        return FakeServerError(message)


class ExplodingWebRequest:
    def __getattribute__(self, name: str):
        if name.startswith("__"):
            return object.__getattribute__(self, name)
        raise AssertionError("web_request_read_while_disabled:%s" % name)


def make_moonraker():
    config = FakeMoonrakerConfig()
    component = MOONRAKER.K1ControlStockCycle(config)
    return component, config.server


def scenario_moonraker_disabled_registers_expected_endpoints() -> None:
    component, server = make_moonraker()
    assert component.enabled is False
    assert component._public_state()["core_profile"] == "k1_p001_t055_r001_n11x11"
    assert len(server.endpoints) == 8
    assert sorted(kind for kind, _handler in server.endpoints.values()).count("POST") == 6
    assert component.component_init() is None


def scenario_moonraker_disabled_selftest_is_inert() -> None:
    component, _server = make_moonraker()
    result = asyncio.run(component._disabled_selftest(ExplodingWebRequest()))
    assert result["status"] == "K1_CONTROL_STOCK_CYCLE_DISABLED_SELFTEST_V1_OK"
    assert result["refused_effect_endpoints"] == 6
    for field in (
        "effect_request_count",
        "state_file_read_count",
        "state_file_write_count",
        "klippy_query_count",
        "gcode_dispatch_count",
        "camera_request_count",
        "automatic_retry_count",
        "stock_BOX_effect_count",
    ):
        assert result[field] == 0


def scenario_moonraker_effects_refuse_before_request_read() -> None:
    component, _server = make_moonraker()
    handlers = (
        component._begin,
        component._clean_confirm,
        component._camera_verdict,
        component._tool_change,
        component._runout,
        component._end,
    )
    for handler in handlers:
        expect_error(
            lambda handler=handler: asyncio.run(handler(ExplodingWebRequest())),
            "stock_cycle_disabled",
        )
    state = component._public_state()
    assert state["effect_request_count"] == 0
    assert state["state_file_read_count"] == 0
    assert state["state_file_write_count"] == 0


def scenario_moonraker_install_disabled_cannot_be_enabled() -> None:
    config = FakeMoonrakerConfig(enabled="true")
    expect_error(
        lambda: MOONRAKER.K1ControlStockCycle(config),
        "activation package",
    )


SCENARIOS = (
    scenario_geometry_disabled_selftest,
    scenario_geometry_disabled_refuses_before_arguments,
    scenario_geometry_exact_context_consumes_only_r4_token,
    scenario_geometry_stock_refill_must_already_be_off,
    scenario_geometry_filament_route_refused,
    scenario_geometry_mesh_or_z_drift_refused,
    scenario_geometry_effect_is_never_replayed,
    scenario_geometry_partial_failure_is_uncertain_no_retry,
    scenario_moonraker_disabled_registers_expected_endpoints,
    scenario_moonraker_disabled_selftest_is_inert,
    scenario_moonraker_effects_refuse_before_request_read,
    scenario_moonraker_install_disabled_cannot_be_enabled,
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
        "installed_enabled": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True))
