#!/usr/bin/env python3
"""Scénarios hors imprimante de l'adaptateur Klipper désactivé."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import struct
import sys
import types


HERE = Path(__file__).resolve().parent
OFFLINE = HERE.parent / "cfs-direct-owner-offline-v1"
PAYLOAD = "k1_control_cfs_direct_payload_test"


def load_module(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


payload_package = types.ModuleType(PAYLOAD)
payload_package.__path__ = [str(OFFLINE)]
sys.modules[PAYLOAD] = payload_package
protocol = load_module(PAYLOAD + ".protocol", OFFLINE / "protocol.py")
owner_core = load_module(PAYLOAD + ".owner", OFFLINE / "owner.py")
runtime_adapter = load_module(
    PAYLOAD + ".runtime_adapter", OFFLINE / "runtime_adapter.py"
)

klippy = types.ModuleType("klippy")
klippy.__path__ = []
extras = types.ModuleType("klippy.extras")
extras.__path__ = []
payload_alias = types.ModuleType("klippy.extras.k1_control_cfs_direct")
payload_alias.__path__ = [str(OFFLINE)]
payload_alias.owner = owner_core
payload_alias.protocol = protocol
payload_alias.runtime_adapter = runtime_adapter
sys.modules["klippy"] = klippy
sys.modules["klippy.extras"] = extras
sys.modules["klippy.extras.k1_control_cfs_direct"] = payload_alias
sys.modules["klippy.extras.k1_control_cfs_direct.owner"] = owner_core
sys.modules["klippy.extras.k1_control_cfs_direct.protocol"] = protocol
sys.modules[
    "klippy.extras.k1_control_cfs_direct.runtime_adapter"
] = runtime_adapter
component = load_module(
    "klippy.extras.k1_control_cfs_direct_owner",
    HERE / "k1_control_cfs_direct_owner.py",
)


class FakeCommandError(RuntimeError):
    pass


class FakeGcmd:
    def __init__(self, values=None):
        self.values = dict(values or {})
        self.responses = []

    def get(self, name):
        if name not in self.values:
            raise FakeCommandError("missing_%s" % name)
        return self.values[name]

    def get_float(self, name, minval=None, maxval=None):
        value = float(self.get(name))
        if minval is not None and value < minval:
            raise FakeCommandError("below_%s" % name)
        if maxval is not None and value > maxval:
            raise FakeCommandError("above_%s" % name)
        return value

    def error(self, message):
        return FakeCommandError(message)

    def respond_info(self, message):
        self.responses.append(str(message))


class FakeGcode:
    def __init__(self, stock=True):
        self.ready_gcode_handlers = {}
        if stock:
            for name in component.STOCK_EFFECT_COMMANDS:
                self.ready_gcode_handlers[name] = self._stock_handler
        self.scripts = []

    @staticmethod
    def _stock_handler(_gcmd):
        raise AssertionError("stock_handler_called")

    def register_command(self, name, func, when_not_ready=False, desc=None):
        if func is None:
            return self.ready_gcode_handlers.pop(name, None)
        if name in self.ready_gcode_handlers:
            raise RuntimeError("duplicate_command_%s" % name)
        self.ready_gcode_handlers[name] = func
        return None

    def run_script_from_command(self, script):
        self.scripts.append(str(script))


class FakeReactor:
    def monotonic(self):
        return 123.0


class FakeSensor:
    def __init__(self, values):
        self.values = list(values)

    def get_status(self, _eventtime):
        if not self.values:
            raise AssertionError("unexpected_sensor_read")
        return {"filament_detected": self.values.pop(0)}


class FakeStatusObject:
    def __init__(self, value):
        self.value = dict(value)

    def get_status(self, _eventtime):
        return dict(self.value)


class FakeSerial:
    def __init__(self, plan=None):
        self.plan = list(plan or [])
        self.calls = []

    def cmd_send_data_with_response(self, frame, timeout_s, retry):
        frame = bytes(frame)
        self.calls.append((frame, float(timeout_s), retry))
        if not self.plan:
            raise AssertionError("unexpected_CFS_frame_%r" % list(frame))
        expected, response = self.plan.pop(0)
        if frame != expected:
            raise AssertionError(
                "frame_mismatch_%r_%r" % (list(frame), list(expected))
            )
        return response


class FakePrinter:
    def __init__(self, objects):
        self.objects = dict(objects)
        self.reactor = FakeReactor()
        self.handlers = {}
        self.lookups = []

    def get_reactor(self):
        return self.reactor

    def lookup_object(self, name, default_marker=...):
        self.lookups.append(name)
        if name in self.objects:
            return self.objects[name]
        if default_marker is not ...:
            return default_marker
        raise KeyError(name)

    def register_event_handler(self, name, handler):
        self.handlers[name] = handler


class FakeConfig:
    def __init__(self, printer, enabled=False, values=None):
        self.printer = printer
        self.values = {
            "enabled": enabled,
            "connected_boxes": "1, 2",
            "head_sensor": "filament_switch_sensor filament_sensor",
            "after_cutter_sensor": "filament_switch_sensor filament_sensor_2",
            "max_pushes": 8,
        }
        self.values.update(values or {})

    def get_printer(self):
        return self.printer

    def getboolean(self, name, default=False):
        return bool(self.values.get(name, default))

    def get(self, name, default=None):
        return self.values.get(name, default)

    def getint(self, name, default=None, minval=None, maxval=None):
        value = int(self.values.get(name, default))
        if minval is not None and value < minval:
            raise ValueError(name)
        if maxval is not None and value > maxval:
            raise ValueError(name)
        return value


def response(frame, data=b"", status=0):
    return protocol.wire_frame(frame[0], status, frame[3], data)


def ok_plan(items):
    return [(frame, response(frame, data)) for frame, data in items]


def load_plan():
    target = protocol.route("T1A")
    return ok_plan(
        [
            (protocol.get_material_sensor(target), b"\x01"),
            (protocol.set_feed_mode(target), b""),
            (protocol.tighten(1, True), b""),
            (protocol.tighten(2, True), b""),
            (protocol.extrude_stage(target, 0), b""),
            (protocol.extrude_stage(target, 4), b""),
            (protocol.extrude_stage(target, 5), struct.pack(">f", 0.25)),
            (protocol.extrude_stage(target, 6), b""),
            (protocol.get_buffer_state(target), b"\x00"),
            (protocol.set_print_mode(target), b""),
            (protocol.tighten(1, False), b""),
            (protocol.tighten(2, False), b""),
        ]
    )


def unload_plan():
    target = protocol.route("T1A")
    return ok_plan(
        [
            (protocol.set_feed_mode(target), b""),
            (protocol.retrude(target, protocol.TRIGGER_BUFFER), b""),
            (protocol.retrude(target, protocol.TRIGGER_MATERIAL), b""),
        ]
    )


def box_status(auto_refill=0, t_command="", second_state="connect"):
    return {
        "auto_refill": auto_refill,
        "enable": 1,
        "t_command": t_command,
        "T1": {"state": "connect"},
        "T2": {"state": second_state},
    }


def make_component(
    enabled=False,
    serial=None,
    head_values=(),
    after_values=(),
    box=None,
    extruder=None,
):
    gcode = FakeGcode(stock=True)
    serial = serial or FakeSerial()
    objects = {
        "gcode": gcode,
        "serial_485 serial485": serial,
        "filament_switch_sensor filament_sensor": FakeSensor(head_values),
        "filament_switch_sensor filament_sensor_2": FakeSensor(after_values),
        "box": FakeStatusObject(box or box_status()),
        "extruder": FakeStatusObject(
            extruder
            or {
                "target": 220.0,
                "temperature": 219.5,
                "can_extrude": True,
            }
        ),
    }
    printer = FakePrinter(objects)
    instance = component.K1ControlCfsDirectOwner(
        FakeConfig(printer, enabled=enabled)
    )
    return instance, printer, gcode, serial


def require_error(callback, code):
    try:
        callback()
    except FakeCommandError as error:
        if code not in str(error):
            raise AssertionError("wrong_error_%s_expected_%s" % (error, code))
        return
    raise AssertionError("missing_error_%s" % code)


def temperature_args(effect_id="effect-1"):
    return {
        "ROUTE": "T1A",
        "EFFECT_ID": effect_id,
        "EXPECTED_C": 220,
        "MATERIAL_MIN_C": 200,
        "MATERIAL_MAX_C": 240,
    }


def scenario_disabled_status_is_inert():
    instance, printer, gcode, serial = make_component(enabled=False)
    printer.handlers["klippy:ready"]()
    status = instance.get_status(123.0)
    assert status["enabled"] is False
    assert status["phase"] == "disabled"
    assert status["transport_bound"] is False
    assert status["stock_commands_blocked"] is False
    assert serial.calls == []


def scenario_disabled_selftest_refuses_three_effects():
    instance, _printer, _gcode, serial = make_component(enabled=False)
    command = FakeGcmd()
    instance.cmd_DISABLED_SELFTEST(command)
    assert command.responses == [
        "KCTRL_CFS_DIRECT_DISABLED_SELFTEST_OK refused=3"
    ]
    assert instance.get_status(123.0)["disabled_selftest_count"] == 1
    assert serial.calls == []


def scenario_disabled_effect_entries_fail_before_arguments_or_transport():
    instance, printer, _gcode, serial = make_component(enabled=False)
    initial_lookups = list(printer.lookups)
    require_error(lambda: instance.cmd_RECONCILE(FakeGcmd()), "direct_owner_disabled")
    require_error(lambda: instance.cmd_LOAD(FakeGcmd()), "direct_owner_disabled")
    require_error(lambda: instance.cmd_UNLOAD(FakeGcmd()), "direct_owner_disabled")
    assert printer.lookups == initial_lookups
    assert serial.calls == []


def scenario_disabled_owner_preserves_stock_handlers():
    instance, _printer, gcode, _serial = make_component(enabled=False)
    assert instance.stock_commands_replaced == []
    assert all(name in gcode.ready_gcode_handlers for name in component.STOCK_EFFECT_COMMANDS)
    assert all(
        gcode.ready_gcode_handlers[name] == gcode._stock_handler
        for name in component.STOCK_EFFECT_COMMANDS
    )


def scenario_enabled_owner_blocks_every_present_stock_entry():
    instance, _printer, gcode, _serial = make_component(enabled=True)
    assert instance.stock_commands_blocked is True
    assert instance.stock_commands_absent == []
    assert instance.stock_commands_replaced == sorted(component.STOCK_EFFECT_COMMANDS)
    for name in component.STOCK_EFFECT_COMMANDS:
        require_error(
            lambda command=name: gcode.ready_gcode_handlers[command](FakeGcmd()),
            "stock_effect_command_blocked",
        )


def scenario_enabled_preflight_binds_without_serial_frame():
    instance, _printer, _gcode, serial = make_component(enabled=True)
    command = FakeGcmd()
    instance.cmd_PREFLIGHT(command)
    status = instance.get_status(123.0)
    assert status["transport_bound"] is True
    assert status["preflight_count"] == 1
    assert status["last_box_proof"]["connected"] == ["T1", "T2"]
    assert serial.calls == []
    assert command.responses == [
        "KCTRL_CFS_DIRECT_PREFLIGHT_OK boxes=1,2 no_frame=1"
    ]


def scenario_enabled_preflight_requires_stock_auto_refill_zero():
    instance, _printer, _gcode, serial = make_component(
        enabled=True, box=box_status(auto_refill=1)
    )
    require_error(
        lambda: instance.cmd_PREFLIGHT(FakeGcmd()),
        "stock_auto_refill_not_disabled",
    )
    assert serial.calls == []


def scenario_enabled_preflight_refuses_active_stock_command():
    instance, _printer, _gcode, serial = make_component(
        enabled=True, box=box_status(t_command="T1A")
    )
    require_error(
        lambda: instance.cmd_PREFLIGHT(FakeGcmd()), "stock_command_active"
    )
    assert serial.calls == []


def scenario_enabled_preflight_requires_both_boxes():
    instance, _printer, _gcode, serial = make_component(
        enabled=True, box=box_status(second_state="disconnect")
    )
    require_error(
        lambda: instance.cmd_PREFLIGHT(FakeGcmd()), "CFS_T2_not_connected"
    )
    assert serial.calls == []


def scenario_runtime_load_uses_offline_owner_without_hidden_commands():
    serial = FakeSerial(load_plan())
    instance, _printer, gcode, serial = make_component(
        enabled=True,
        serial=serial,
        head_values=(False, True, True),
        after_values=(False, True),
    )
    command = FakeGcmd(temperature_args("load-runtime-1"))
    instance.cmd_LOAD(command)
    status = instance.get_status(123.0)
    assert status["phase"] == "loaded"
    assert status["active_route"] == "T1A"
    assert status["frames_sent_count"] == 12
    assert status["temperature_commands"] == []
    assert status["geometry_commands"] == []
    assert status["mesh_commands"] == []
    assert status["purge_commands"] == []
    assert gcode.scripts == []
    assert serial.plan == []
    assert all(retry is False for _frame, _timeout, retry in serial.calls)


def scenario_runtime_unload_uses_one_exact_local_pull():
    serial = FakeSerial(unload_plan())
    instance, _printer, gcode, serial = make_component(
        enabled=True,
        serial=serial,
        head_values=(True, False),
        after_values=(True, False),
    )
    instance._ensure_runtime()
    instance.owner.active_route = "T1A"
    instance.owner.phase = "loaded"
    command = FakeGcmd(temperature_args("unload-runtime-1"))
    instance.cmd_UNLOAD(command)
    status = instance.get_status(123.0)
    assert status["phase"] == "idle"
    assert status["active_route"] is None
    assert status["tip_pull_count"] == 1
    assert gcode.scripts == [
        "SAVE_GCODE_STATE NAME=KCTRL_CFS_DIRECT_PULL",
        "M83",
        "G1 E-20 F8400",
        "M400",
        "RESTORE_GCODE_STATE NAME=KCTRL_CFS_DIRECT_PULL MOVE=0",
    ]
    assert serial.plan == []


def scenario_temperature_mismatch_stops_before_first_frame():
    instance, _printer, _gcode, serial = make_component(
        enabled=True,
        extruder={
            "target": 215.0,
            "temperature": 219.5,
            "can_extrude": True,
        },
    )
    require_error(
        lambda: instance.cmd_LOAD(FakeGcmd(temperature_args("temp-ko"))),
        "target_temperature_mismatch",
    )
    assert serial.calls == []
    assert instance.get_status(123.0)["phase"] == "failed_safe"


def scenario_invalid_connected_boxes_fail_at_config_load():
    gcode = FakeGcode(stock=True)
    printer = FakePrinter({"gcode": gcode})
    try:
        component.K1ControlCfsDirectOwner(
            FakeConfig(
                printer,
                enabled=False,
                values={"connected_boxes": "1, 3"},
            )
        )
    except component.RuntimeGateError as error:
        assert error.code == "connected_boxes_invalid"
        return
    raise AssertionError("connected_boxes_invalid_not_rejected")


SCENARIOS = (
    scenario_disabled_status_is_inert,
    scenario_disabled_selftest_refuses_three_effects,
    scenario_disabled_effect_entries_fail_before_arguments_or_transport,
    scenario_disabled_owner_preserves_stock_handlers,
    scenario_enabled_owner_blocks_every_present_stock_entry,
    scenario_enabled_preflight_binds_without_serial_frame,
    scenario_enabled_preflight_requires_stock_auto_refill_zero,
    scenario_enabled_preflight_refuses_active_stock_command,
    scenario_enabled_preflight_requires_both_boxes,
    scenario_runtime_load_uses_offline_owner_without_hidden_commands,
    scenario_runtime_unload_uses_one_exact_local_pull,
    scenario_temperature_mismatch_stops_before_first_frame,
    scenario_invalid_connected_boxes_fail_at_config_load,
)


def run():
    results = []
    for scenario in SCENARIOS:
        scenario()
        results.append({"name": scenario.__name__, "status": "OK"})
    return results


if __name__ == "__main__":
    values = run()
    print(
        "CFS_DIRECT_OWNER_INSTALL_DISABLED_OFFLINE_V1_OK %d/%d"
        % (len(values), len(SCENARIOS))
    )
