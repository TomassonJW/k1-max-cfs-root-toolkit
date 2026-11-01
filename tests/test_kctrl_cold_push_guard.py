"""Cold push refusal added to kctrl_purge_guard (ADR-076), bin envelope unchanged.

The fake toolhead calls the two checks as the installed toolhead.move does:
kinematics only for a move in XYZ, then the extruder when the move has E.
"""
import difflib
import importlib.util
import logging
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'packages/k1-control-v1'
PACKAGE = '_cold_push_guard_test_package'
sys.modules[PACKAGE] = SimpleNamespace(__path__=[str(ROOT / 'cold-push-guard-v1')])
for name, folder in (('kctrl_start_policy', 'retained-start-v1'),
                     ('kctrl_purge_guard', 'cold-push-guard-v1')):
    spec = importlib.util.spec_from_file_location(PACKAGE + '.' + name, ROOT / folder / (name + '.py'))
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
        self.clock = 100.
        self.heater = SimpleNamespace(can_extrude=False, target_temp=0., min_extrude_temp=170.,
                                      smoothed_temp=24.)
        self.kin = SimpleNamespace(check_move=self.range_check)
        self.extruder = SimpleNamespace(check_move=self.extrude_check, get_heater=lambda: self.heater)
        self.toolhead = SimpleNamespace(get_kinematics=lambda: self.kin,
                                        get_extruder=lambda: self.extruder,
                                        get_status=lambda _: {'homed_axes': 'xyz'})
        self.heaters = SimpleNamespace(turn_off_all_heaters=lambda: self.calls.append('heat_off'))

    def range_check(self, move):
        self.calls.append('range_check')

    def extrude_check(self, move):
        self.calls.append('extrude_check')
        if abs(move.axes_d[3]) > 1000.:
            raise CommandError('Extrude only move too long')

    def get_reactor(self):
        return SimpleNamespace(monotonic=lambda: self.clock)

    def lookup_object(self, name):
        return {'toolhead': self.toolhead, 'heaters': self.heaters, 'extruder': self.extruder}[name]

    def register_event_handler(self, name, handler):
        self.handlers[name] = handler

    def move(self, start, end):
        move = SimpleNamespace(start_pos=start, end_pos=end,
                               axes_d=[e - s for s, e in zip(start, end)])
        if any(move.axes_d[:3]):
            self.kin.check_move(move)
        if move.axes_d[3]:
            self.extruder.check_move(move)
        self.calls.append('queued')


def setup(**heater):
    printer = Printer()
    printer.heater.__dict__.update(heater)
    guard = Guard(SimpleNamespace(get_printer=lambda: printer))
    printer.handlers['klippy:ready']()
    return guard, printer


def push(printer, length):
    printer.move([200., 273., 40., 10.], [200., 273., 40., 10. + length])


def test_cold_push_without_heating_is_refused_without_heater_or_motion():
    guard, printer = setup(smoothed_temp=36., target_temp=0.)
    with pytest.raises(CommandError, match='buse froide'):
        push(printer, 5.)
    assert printer.calls == ['extrude_check']
    status = guard.get_status(0)
    assert status['cold_refused'] == 1 and status['cold_last'] == 'poussee 5.00 mm a 36 C, cible 0 C'
    assert status['denied'] == 0 and status['last_error'] == ''


def test_end_of_print_case_heaters_cut_at_159_c_is_refused():
    guard, printer = setup(smoothed_temp=159., target_temp=0.)
    with pytest.raises(CommandError):
        printer.move([185.5, 305., 53.94, 0.], [185.5, 305., 53.94, 5.])
    assert guard.get_status(0)['cold_refused'] == 1


def test_target_below_extrusion_minimum_is_not_heating():
    guard, printer = setup(smoothed_temp=140., target_temp=140.)
    with pytest.raises(CommandError):
        push(printer, .5)
    assert guard.get_status(0)['cold_refused'] == 1


@pytest.mark.parametrize('heater', [
    {'smoothed_temp': 36., 'target_temp': 220.},                       # load heats then pushes
    {'smoothed_temp': 215., 'target_temp': 0., 'can_extrude': True},   # still hot after cut
    {'smoothed_temp': 220., 'target_temp': 220., 'can_extrude': True},  # printing
    {'smoothed_temp': 170., 'target_temp': 170., 'can_extrude': True},  # exactly the minimum
])
def test_push_passes_hot_or_heating(heater):
    guard, printer = setup(**heater)
    push(printer, 5.)
    assert printer.calls == ['extrude_check', 'queued']
    assert guard.get_status(0)['cold_refused'] == 0


def test_cold_printing_move_is_refused_after_the_range_check():
    guard, printer = setup(smoothed_temp=120., target_temp=0.)
    with pytest.raises(CommandError, match='buse froide'):
        printer.move([100., 100., .3, 10.], [120., 100., .3, 10.8])
    assert printer.calls == ['range_check', 'extrude_check']


def test_cold_retraction_always_passes():
    guard, printer = setup(smoothed_temp=24., target_temp=0.)
    push(printer, -15.)
    assert printer.calls[-1] == 'queued'
    assert guard.get_status(0)['cold_refused'] == 0


def test_travel_without_extrusion_never_reaches_the_extruder_check():
    guard, printer = setup()
    printer.move([10., 10., 40., 3.], [100., 100., 40., 3.])
    assert printer.calls == ['range_check', 'queued']


def test_original_extruder_check_still_runs_first_and_is_not_counted():
    guard, printer = setup(smoothed_temp=24., target_temp=0.)
    with pytest.raises(CommandError, match='too long'):
        push(printer, 1500.)
    assert guard.get_status(0)['cold_refused'] == 0


def test_retrying_loop_logs_once_per_ten_seconds(caplog):
    guard, printer = setup(smoothed_temp=80., target_temp=0.)
    with caplog.at_level(logging.ERROR):
        for second in (0., 1., 4., 9.9, 10., 12.):
            printer.clock = 100. + second
            with pytest.raises(CommandError):
                push(printer, 5.)
    lines = [r for r in caplog.records if 'cold push refused' in r.getMessage()]
    assert len(lines) == 2
    assert guard.get_status(0)['cold_refused'] == 6


def test_status_keeps_bin_fields_and_reports_live_hook():
    guard, printer = setup()
    status = guard.get_status(0)
    assert status['revision'] == 'retained-start-v1' and status['installed'] is True
    assert status['bin_latched'] is False and status['minimum_z'] == 30.
    assert status['cold_revision'] == 'cold-push-guard-v1' and status['cold_installed'] is True
    printer.extruder.check_move = printer.extrude_check
    assert guard.get_status(0)['cold_installed'] is False


def test_status_before_ready_is_safe():
    printer = Printer()
    guard = Guard(SimpleNamespace(get_printer=lambda: printer))
    status = guard.get_status(0)
    assert status['installed'] is False and status['cold_installed'] is False


def test_ready_is_idempotent_without_recursive_hooks():
    guard, printer = setup(smoothed_temp=220., target_temp=220., can_extrude=True)
    guard._ready()
    push(printer, 5.)
    assert printer.calls == ['extrude_check', 'queued']


def test_bin_envelope_unchanged_low_move_refused_with_heat_cut():
    guard, printer = setup(smoothed_temp=220., target_temp=220., can_extrude=True)
    with pytest.raises(CommandError, match='bac'):
        printer.move([185.5, 305., 35., 10.], [185.5, 305., 5., 10.])
    assert printer.calls == ['range_check', 'heat_off']
    assert guard.get_status(0)['denied'] == 1 and guard.get_status(0)['cold_refused'] == 0


def test_bin_exit_sequence_unchanged():
    guard, printer = setup()
    printer.move([185.5, 273., 35., 0.], [185.5, 305., 35., 0.])
    assert guard.envelope.latched
    with pytest.raises(CommandError):
        printer.move([185.5, 305., 35., 0.], [185.5, 273., 0., 0.])
    printer.move([185.5, 305., 35., 0.], [185.5, 273., 35., 0.])
    printer.move([185.5, 273., 35., 0.], [185.5, 273., 0., 0.])
    assert not guard.envelope.latched


def test_candidate_only_adds_to_the_installed_guard():
    old = (ROOT / 'retained-start-v1/kctrl_purge_guard.py').read_text(encoding='utf-8').splitlines()
    new = (ROOT / 'cold-push-guard-v1/kctrl_purge_guard.py').read_text(encoding='utf-8').splitlines()
    removed = [line[2:] for line in difflib.ndiff(old, new) if line.startswith('- ')]
    assert removed == ["                'denied': self.denied, 'last_error': self.last_error}"]
