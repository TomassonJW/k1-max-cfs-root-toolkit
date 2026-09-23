import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'packages/k1-control-v1/retained-start-v1'
PACKAGE = '_purge_guard_test_package'
pkg = SimpleNamespace(__path__=[str(ROOT)])
sys.modules[PACKAGE] = pkg
for name in ('kctrl_start_policy', 'kctrl_purge_guard'):
    spec = importlib.util.spec_from_file_location(PACKAGE + '.' + name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
Guard = sys.modules[PACKAGE + '.kctrl_purge_guard'].KctrlPurgeGuard


class CommandError(Exception):
    pass


class Printer:
    command_error = CommandError

    def __init__(self):
        self.calls = []
        self.handlers = {}
        self.homed = 'xyz'
        self.kin = SimpleNamespace(check_move=self.original_check)
        self.toolhead = SimpleNamespace(get_kinematics=lambda: self.kin,
                                        get_status=lambda _: {'homed_axes': self.homed})
        self.heaters = SimpleNamespace(turn_off_all_heaters=lambda: self.calls.append('heat_off'))

    def original_check(self, move):
        self.calls.append('range_check')
        if move.end_pos[0] > 306.5:
            raise CommandError('out_of_range')

    def get_reactor(self):
        return SimpleNamespace(monotonic=lambda: 100.)

    def lookup_object(self, name):
        return {'toolhead': self.toolhead, 'heaters': self.heaters}[name]

    def register_event_handler(self, name, handler):
        self.handlers[name] = handler


def setup():
    printer = Printer()
    guard = Guard(SimpleNamespace(get_printer=lambda: printer))
    printer.handlers['klippy:ready']()
    return guard, printer


def move(printer, start, end):
    printer.kin.check_move(SimpleNamespace(start_pos=start, end_pos=end))


def test_low_level_rejects_stock_direct_move_and_preserves_position():
    guard, printer = setup()
    start, end = [185.5, 305., 35., 10.], [185.5, 305., 5., 10.]
    with pytest.raises(CommandError, match='bac'):
        move(printer, start, end)
    assert start == [185.5, 305., 35., 10.]
    assert end == [185.5, 305., 5., 10.]
    assert printer.calls == ['range_check', 'heat_off']
    assert guard.get_status(0)['denied'] == 1


def test_safe_exit_must_finish_before_bed_raises():
    guard, printer = setup()
    move(printer, [185.5, 273., 35., 0.], [185.5, 305., 35., 0.])
    assert guard.envelope.latched
    with pytest.raises(CommandError):
        move(printer, [185.5, 305., 35., 0.], [185.5, 273., 0., 0.])
    assert guard.envelope.latched
    move(printer, [185.5, 305., 35., 0.], [185.5, 273., 35., 0.])
    move(printer, [185.5, 273., 35., 0.], [185.5, 273., 0., 0.])
    assert not guard.envelope.latched


def test_real_coordinates_below_30_are_denied_even_if_gcode_would_say_30():
    _, printer = setup()
    with pytest.raises(CommandError):
        move(printer, [185.5, 273., 29.95, 0.], [185.5, 305., 29.95, 0.])


def test_original_range_check_still_runs_and_does_not_change_latch():
    guard, printer = setup()
    with pytest.raises(CommandError, match='out_of_range'):
        move(printer, [0., 0., 35., 0.], [500., 305., 35., 0.])
    assert not guard.envelope.latched
    assert printer.calls == ['range_check']


def test_ready_is_idempotent_without_recursive_hook():
    guard, printer = setup()
    guard._ready()
    move(printer, [0., 0., 5., 0.], [100., 100., 5., 0.])
    assert printer.calls == ['range_check']
