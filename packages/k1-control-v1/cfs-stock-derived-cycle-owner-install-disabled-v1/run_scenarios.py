#!/usr/bin/env python3
"""Scénarios déterministes du composant stock-derived installé désactivé."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, Optional


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "k1_control_stock_cycle_owner_candidate",
    HERE / "k1_control_stock_cycle_owner.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("candidate_import_spec_missing")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


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
    def __init__(self, box=None):
        self.commands: Dict[str, Any] = {}
        self.scripts = []
        self.box = box

    def register_command(self, name: str, handler, desc: Optional[str] = None):
        previous = self.commands.get(name)
        self.commands[name] = handler
        return previous

    def run_script_from_command(self, command: str) -> None:
        self.scripts.append(command)
        if self.box is not None and command == "G1 X38 Y304.5 F7000":
            self.box.value["cut_pos"] = 1.0
        if self.box is not None and command == "G1 X38 Y230 F7000":
            self.box.value["cut_pos"] = 0.0


class FakePrinter:
    def __init__(self, *, auto_refill: int = 0, homed_axes: str = "xyz", direct_enabled: bool = True):
        self.reactor = FakeReactor()
        box = FakeStatus({"auto_refill": auto_refill, "t_command": "", "cut_pos": 0.0})
        self.gcode = FakeGcode(box)
        self.objects = {
            "gcode": self.gcode,
            "toolhead": FakeStatus({"homed_axes": homed_axes}),
            "box": box,
            "k1_control_cfs_direct_owner": FakeStatus(
                {
                    "enabled": direct_enabled,
                    "stock_commands_blocked": direct_enabled,
                    "failure_code": None,
                }
            ),
        }
        self.handlers = {}

    def get_reactor(self):
        return self.reactor

    def lookup_object(self, name: str, default=None):
        return self.objects.get(name, default)

    def register_event_handler(self, name: str, handler) -> None:
        self.handlers[name] = handler


class FakeConfig:
    def __init__(self, printer: FakePrinter, *, enabled: bool):
        self.printer = printer
        self.enabled = enabled

    def get_printer(self):
        return self.printer

    def getboolean(self, name: str, default: bool = False) -> bool:
        return self.enabled if name == "enabled" else default

    def get(self, name: str, default=None):
        return default


class FakeGcmd:
    def __init__(self, values: Optional[Dict[str, Any]] = None, *, forbid_reads: bool = False):
        self.values = dict(values or {})
        self.forbid_reads = forbid_reads
        self.read_count = 0
        self.responses = []

    def _read(self, name: str):
        self.read_count += 1
        if self.forbid_reads:
            raise AssertionError("argument_read_while_disabled:%s" % name)
        if name not in self.values:
            raise FakeCommandError("missing_argument:%s" % name)
        return self.values[name]

    def get(self, name: str):
        return self._read(name)

    def get_float(self, name: str, minval=None, maxval=None):
        value = float(self._read(name))
        if minval is not None and value < minval:
            raise FakeCommandError("below_min:%s" % name)
        if maxval is not None and value > maxval:
            raise FakeCommandError("above_max:%s" % name)
        return value

    def get_int(self, name: str, minval=None, maxval=None):
        value = int(self._read(name))
        if minval is not None and value < minval:
            raise FakeCommandError("below_min:%s" % name)
        if maxval is not None and value > maxval:
            raise FakeCommandError("above_max:%s" % name)
        return value

    def error(self, message: str):
        return FakeCommandError(message)

    def respond_info(self, message: str) -> None:
        self.responses.append(message)


def make_owner(*, enabled: bool, auto_refill: int = 0, homed_axes: str = "xyz", direct_enabled: bool = True):
    printer = FakePrinter(
        auto_refill=auto_refill,
        homed_axes=homed_axes,
        direct_enabled=direct_enabled,
    )
    owner = MODULE.K1ControlStockCycleOwner(FakeConfig(printer, enabled=enabled))
    return owner, printer


def cut_args() -> Dict[str, Any]:
    return {
        "ROUTE": "T1A",
        "EFFECT_ID": "cut-1",
        "UNLOAD_C": 195,
        "MATERIAL_MIN_C": 180,
        "MATERIAL_MAX_C": 230,
    }


def load_args(trips: int = 3) -> Dict[str, Any]:
    return {
        "ROUTE": "T2D",
        "EFFECT_ID": "load-1",
        "LOAD_C": 205,
        "PURGE_C": 210,
        "PURGE_MM": 140,
        "TRIPS": trips,
        "MATERIAL_MIN_C": 180,
        "MATERIAL_MAX_C": 230,
    }


def end_args() -> Dict[str, Any]:
    result = cut_args()
    result["EFFECT_ID"] = "end-1"
    return result


def expect_error(call, code: str) -> None:
    try:
        call()
    except FakeCommandError as error:
        if code not in str(error):
            raise AssertionError("wrong_error:%s" % error)
        return
    raise AssertionError("expected_error_missing:%s" % code)


def contains_in_order(values, expected) -> bool:
    cursor = 0
    for item in expected:
        try:
            cursor = values.index(item, cursor) + 1
        except ValueError:
            return False
    return True


def scenario_disabled_selftest() -> None:
    owner, printer = make_owner(enabled=False)
    gcmd = FakeGcmd()
    owner.cmd_DISABLED_SELFTEST(gcmd)
    assert gcmd.responses == [
        "KCTRL_STOCK_CYCLE_DISABLED_SELFTEST_V1_OK refused=5"
    ]
    assert printer.gcode.scripts == []
    assert owner.get_status(0)["effect_count"] == 0


def scenario_disabled_entries_refuse_before_arguments() -> None:
    owner, printer = make_owner(enabled=False)
    entries = (
        owner.cmd_CUT_UNLOAD,
        owner.cmd_LOAD_PURGE,
        owner.cmd_PRIME,
        owner.cmd_REFILL_GUARD,
        owner.cmd_END,
    )
    for entry in entries:
        gcmd = FakeGcmd(forbid_reads=True)
        expect_error(lambda entry=entry, gcmd=gcmd: entry(gcmd), "stock_derived_cycle_disabled")
        assert gcmd.read_count == 0
    assert printer.gcode.scripts == []


def scenario_enabled_requires_auto_refill_zero() -> None:
    owner, printer = make_owner(enabled=True, auto_refill=1)
    expect_error(lambda: owner.cmd_CUT_UNLOAD(FakeGcmd(cut_args())), "stock_auto_refill_not_disabled")
    assert printer.gcode.scripts == []


def scenario_enabled_requires_xyz() -> None:
    owner, printer = make_owner(enabled=True, homed_axes="xy")
    expect_error(lambda: owner.cmd_LOAD_PURGE(FakeGcmd(load_args())), "XYZ_reference_missing")
    assert printer.gcode.scripts == []


def scenario_enabled_requires_direct_owner() -> None:
    owner, printer = make_owner(enabled=True, direct_enabled=False)
    expect_error(lambda: owner.cmd_CUT_UNLOAD(FakeGcmd(cut_args())), "direct_owner_not_enabled")
    assert printer.gcode.scripts == []


def scenario_uncertain_effect_ticket_is_never_replayed() -> None:
    owner, printer = make_owner(enabled=True)
    original = printer.gcode.run_script_from_command

    def fail_on_cut(command: str) -> None:
        original(command)
        if command == "G1 X38 Y304.5 F7000":
            raise FakeCommandError("simulated_uncertain_cut_failure")

    printer.gcode.run_script_from_command = fail_on_cut
    expect_error(
        lambda: owner.cmd_CUT_UNLOAD(FakeGcmd(cut_args())),
        "command_failed_uncertain_no_retry",
    )
    commands_after_failure = list(printer.gcode.scripts)
    expect_error(
        lambda: owner.cmd_CUT_UNLOAD(FakeGcmd(cut_args())),
        "effect_id_already_claimed_no_retry",
    )
    assert printer.gcode.scripts == commands_after_failure
    assert owner.get_status(0)["claimed_effect_count"] == 1


def scenario_cut_unload_exact_stock_geometry() -> None:
    owner, printer = make_owner(enabled=True)
    owner.cmd_CUT_UNLOAD(FakeGcmd(cut_args()))
    scripts = printer.gcode.scripts
    expected = [
        "G1 X38 Y230 F7000",
        "G1 X38 Y304.5 F7000",
        "M400",
        "G4 P1500",
        next(item for item in scripts if item.startswith("KCTRL_CFS_DIRECT_UNLOAD ROUTE=T1A")),
        "G1 X38 Y230 F7000",
        "M400",
        "G4 P1000",
    ]
    assert contains_in_order(scripts, expected), scripts
    assert any(item.startswith("KCTRL_CFS_DIRECT_UNLOAD ROUTE=T1A") for item in scripts)
    assert not any(item.startswith(("BOX_", "G28", "BED_MESH_")) for item in scripts)


def scenario_cut_sensor_must_trigger_before_unload() -> None:
    owner, printer = make_owner(enabled=True)
    printer.gcode.box = None
    expect_error(
        lambda: owner.cmd_CUT_UNLOAD(FakeGcmd(cut_args())),
        "cutter_sensor_not_triggered",
    )
    assert not any(
        item.startswith("KCTRL_CFS_DIRECT_UNLOAD")
        for item in printer.gcode.scripts
    )
    assert printer.objects["box"].value["cut_pos"] == 0.0


def scenario_unload_failure_still_releases_cutter() -> None:
    owner, printer = make_owner(enabled=True)
    original = printer.gcode.run_script_from_command

    def fail_on_direct_unload(command: str) -> None:
        original(command)
        if command.startswith("KCTRL_CFS_DIRECT_UNLOAD ROUTE=T1A"):
            raise FakeCommandError("simulated_direct_unload_failure")

    printer.gcode.run_script_from_command = fail_on_direct_unload
    expect_error(
        lambda: owner.cmd_CUT_UNLOAD(FakeGcmd(cut_args())),
        "command_failed_uncertain_no_retry",
    )
    scripts = printer.gcode.scripts
    unload_index = next(
        index for index, command in enumerate(scripts)
        if command.startswith("KCTRL_CFS_DIRECT_UNLOAD ROUTE=T1A")
    )
    release_index = scripts.index("G1 X38 Y230 F7000", unload_index)
    assert unload_index < release_index
    assert printer.objects["box"].value["cut_pos"] == 0.0


def scenario_load_purge_three_trips() -> None:
    owner, printer = make_owner(enabled=True)
    owner.cmd_LOAD_PURGE(FakeGcmd(load_args(3)))
    scripts = printer.gcode.scripts
    assert scripts.index("G1 Z32 F600") < scripts.index("G1 X185.5 Y305 F1200") < scripts.index("G1 Z30 F600")
    assert any(item.startswith("KCTRL_CFS_DIRECT_LOAD ROUTE=T2D") for item in scripts)
    assert "G1 E140.000 F360" in scripts
    assert [item for item in scripts if item in ("G1 Y305 F600", "G1 Y304 F600")] == [
        "G1 Y305 F600", "G1 Y304 F600", "G1 Y305 F600"
    ]
    assert scripts.count("G1 X206 F180") == 3
    assert scripts.count("G1 X203 F180") == 3


def scenario_load_purge_four_trips() -> None:
    owner, printer = make_owner(enabled=True)
    owner.cmd_LOAD_PURGE(FakeGcmd(load_args(4)))
    scripts = printer.gcode.scripts
    assert [item for item in scripts if item in ("G1 Y305 F600", "G1 Y304 F600")] == [
        "G1 Y305 F600", "G1 Y304 F600", "G1 Y305 F600", "G1 Y304 F600"
    ]
    assert scripts.count("G1 X206 F180") == 4
    assert scripts.count("G1 X203 F180") == 4


def scenario_orca_colour_purge_quantity_is_representable() -> None:
    owner, printer = make_owner(enabled=True)
    args = load_args(4)
    args["PURGE_MM"] = 318.466
    owner.cmd_LOAD_PURGE(FakeGcmd(args))
    assert "G1 E318.466 F360" in printer.gcode.scripts


def scenario_prime_is_exact_stock_line_plus_relative_z5() -> None:
    owner, printer = make_owner(enabled=True)
    owner.cmd_PRIME(FakeGcmd({"EFFECT_ID": "prime-1", "FIRST_C": 210}))
    scripts = printer.gcode.scripts
    expected = [
        "G1 X0.1 Y20 Z0.3 F6000",
        "G1 X0.1 Y180 Z0.3 F3000 E10",
        "G1 X0.4 Y180 Z0.3 F3000",
        "G1 X0.4 Y20 Z0.3 F3000 E10",
        "G1 Y10 F3000",
        "G91",
        "G1 Z5 F1200",
        "G90",
    ]
    assert contains_in_order(scripts, expected), scripts


def refill_args(**changes) -> Dict[str, Any]:
    result = {
        "FROM": "T1A",
        "TO": "T2D",
        "SOURCE_IDENTITY": "sha256-identical-material",
        "TARGET_IDENTITY": "sha256-identical-material",
        "CANDIDATES": 1,
        "PAUSE_LATCHED": 1,
    }
    result.update(changes)
    return result


def scenario_refill_unique_identical_spare_passes_without_motion() -> None:
    owner, printer = make_owner(enabled=True)
    gcmd = FakeGcmd(refill_args())
    owner.cmd_REFILL_GUARD(gcmd)
    assert printer.gcode.scripts == []
    assert owner.get_status(0)["last_operation"] == "refill_guard"


def scenario_refill_near_match_rejected() -> None:
    owner, printer = make_owner(enabled=True)
    args = refill_args(TARGET_IDENTITY="sha256-near-match")
    expect_error(lambda: owner.cmd_REFILL_GUARD(FakeGcmd(args)), "refill_material_not_identical")
    assert printer.gcode.scripts == []


def scenario_refill_ambiguous_rejected() -> None:
    owner, printer = make_owner(enabled=True)
    args = refill_args(CANDIDATES=2)
    expect_error(lambda: owner.cmd_REFILL_GUARD(FakeGcmd(args)), "refill_candidate_not_unique")
    assert printer.gcode.scripts == []


def scenario_end_cuts_unloads_cools_and_releases_without_G28() -> None:
    owner, printer = make_owner(enabled=True)
    owner.cmd_END(FakeGcmd(end_args()))
    scripts = printer.gcode.scripts
    direct_index = next(index for index, item in enumerate(scripts) if item.startswith("KCTRL_CFS_DIRECT_UNLOAD"))
    assert scripts.index("G1 X38 Y304.5 F7000") < direct_index
    assert direct_index < scripts.index("G1 X203 Y273 F1200")
    assert scripts.index("TURN_OFF_HEATERS") < scripts.index("M84")
    assert not any(item.startswith(("G28", "BOX_", "BED_MESH_")) for item in scripts)


SCENARIOS = (
    scenario_disabled_selftest,
    scenario_disabled_entries_refuse_before_arguments,
    scenario_enabled_requires_auto_refill_zero,
    scenario_enabled_requires_xyz,
    scenario_enabled_requires_direct_owner,
    scenario_uncertain_effect_ticket_is_never_replayed,
    scenario_cut_unload_exact_stock_geometry,
    scenario_cut_sensor_must_trigger_before_unload,
    scenario_unload_failure_still_releases_cutter,
    scenario_load_purge_three_trips,
    scenario_load_purge_four_trips,
    scenario_orca_colour_purge_quantity_is_representable,
    scenario_prime_is_exact_stock_line_plus_relative_z5,
    scenario_refill_unique_identical_spare_passes_without_motion,
    scenario_refill_near_match_rejected,
    scenario_refill_ambiguous_rejected,
    scenario_end_cuts_unloads_cools_and_releases_without_G28,
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
        "deployment_candidate": True,
        "installed_enabled": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True))
