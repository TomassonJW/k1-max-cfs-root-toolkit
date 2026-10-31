"""ADR-074: a cancellation keeps a loaded head and releases the owner.

Replays the whole V3 suite against V4, then the 2 October 2026 cancel: the
stock webhook had lowered the nozzle to 140 C before CANCEL_PRINT, so the
deferred cut refused and the failed owner blocked every new start.
"""
from types import SimpleNamespace
from pathlib import Path
import importlib.util
import pytest

ROOT = Path(__file__).resolve().parents[1]
REPLAY = importlib.util.spec_from_file_location(
    'v3_replay_for_v4', Path(__file__).with_name('test_kctrl_end_rewind_confirm_v3.py'))
v3 = importlib.util.module_from_spec(REPLAY)
REPLAY.loader.exec_module(v3)
for name in dir(v3):
    if name.startswith('test_'):
        globals()[name] = getattr(v3, name)
previous, base = v3.previous, v3.base

SPEC = importlib.util.spec_from_file_location(
    'cancel_retained', ROOT / 'packages/k1-control-v1/cancel-retained-end-v4/kctrl_end.py')
END = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(END)
GATE_SPEC = importlib.util.spec_from_file_location(
    'print_gate_for_v4', ROOT / 'packages/k1-control-v1/spool-choice-gate-v1/kctrl_print_gate.py')
GATE = importlib.util.module_from_spec(GATE_SPEC)
GATE_SPEC.loader.exec_module(GATE)

HEAD = 'filament_switch_sensor filament_sensor_2'


class Guard:
    def __init__(self):
        self.latched = False

    def get_status(self, eventtime=None):
        return {'bin_latched': self.latched}


@pytest.fixture(autouse=True)
def successor(monkeypatch):
    original = previous.Printer

    class Printer(original):
        def __init__(self):
            super().__init__()
            action = self.obj['box'].box_action
            action.box_save = SimpleNamespace(last_cmd='T1B', last_cmd_tmp='T1A')
            self.logical_updates = []

            def update(route, destination):
                assert destination is None
                self.logical_updates.append(route)
                self.obj['box'].status[route[:2]]['filament'] = 'None'
            action.update_filament_pos = update
            self.obj['kctrl_purge_guard'] = Guard()
    monkeypatch.setattr(previous, 'END', END)
    monkeypatch.setattr(previous, 'Printer', Printer)


def cancel(p, webhook_target=140.):
    """The stock webhook: WAIT_EXTRUSION_ALL_MATERIALS, then CANCEL_PRINT."""
    if webhook_target is not None:
        p.obj['extruder'].status.update(target=webhook_target, can_extrude=False)
    cmd = base.Cmd()
    p.gcode.handlers['CANCEL_PRINT'](cmd)
    return cmd


def gate_released(c):
    gcmd = SimpleNamespace(error=RuntimeError)
    owner = SimpleNamespace(end_status=lambda: c.get_status())
    try:
        GATE.KctrlPrintGate.assert_end_released(owner, gcmd)
    except RuntimeError:
        return False
    return True


def box_effects(p):
    return [s for s in p.gcode.scripts if 'BOX' in s and s != 'CANCEL_PRINT_BASE']


def test_retained_finish_never_empties_the_head_or_drops_cfs_bookkeeping():
    assert not any('BOX' in command for command in END.RETAINED_FINISH)
    assert END.RETAINED_FINISH[-2:] == ('END_PRINT_POINT', 'WAIT_TEMP_START')
    assert 'TURN_OFF_HEATERS' in END.RETAINED_FINISH


def test_real_cancel_keeps_filament_and_releases_the_next_start():
    p, c = previous.setup()
    cmd = cancel(p)
    # Synchronous: nothing deferred behind the webhook's M84.
    assert p.gcode.scripts == ['CANCEL_PRINT_BASE', *END.RETAINED_FINISH]
    assert not p.reactor.callbacks and not p.reactor.timers
    assert p.obj['toolhead'].moves == []
    assert not box_effects(p) and not p.logical_updates
    assert c.phase == 'complete' and not c.failure and not c.thermal_failure
    assert c.inflight is False and c.reason == 'annulation'
    status = c.get_status()
    assert status['retained'] is True and status['slot'] == 'T1B' and status['pending'] is False
    assert status['revision'] == 'cancel-retained-v4'
    assert p.obj['extruder'].status['target'] == 0 and p.obj['heater_bed'].status['target'] == 0
    assert p.obj['box'].status['T1']['filament'] == 'B'
    assert p.obj[HEAD].status['filament_detected'] is True
    assert p.obj['box'].box_action.box_save.last_cmd == 'T1B'
    assert any('T1B garde en tete' in m and 'nouveau depart possible' in m for m in cmd.messages)
    assert gate_released(c)
    assert not p.shutdowns


def test_paused_print_cancel_also_keeps_filament():
    p, c = previous.setup()
    p.sd.active = False
    p.obj['pause_resume'].status['is_paused'] = True
    cancel(p, webhook_target=None)
    assert c.phase == 'complete' and c.get_status()['retained'] is True
    assert not box_effects(p)


def test_next_start_resets_the_retained_cancel():
    p, c = previous.setup()
    cancel(p)
    p.gcode.handlers['START_PRINT'](base.Cmd())
    assert c.phase == 'idle' and c.run is None and c.epoch == 2
    assert c.get_status()['retained'] is False and c.get_status()['slot'] is None


def test_duplicate_cancel_or_end_after_retained_cancel_does_nothing_more():
    p, c = previous.setup()
    cancel(p)
    first = list(p.gcode.scripts)
    cmd = base.Cmd()
    p.gcode.handlers['CANCEL_PRINT'](cmd)
    p.gcode.handlers['END_PRINT'](base.Cmd())
    p.reactor.drain()
    assert p.gcode.scripts == first + ['CANCEL_PRINT_BASE']
    assert any('fin deja demandee (complete)' in m for m in cmd.messages)
    assert c.phase == 'complete' and gate_released(c)


@pytest.mark.parametrize('how', ['rectangle', 'latched'])
def test_bin_exit_forward_at_constant_height_before_parking(how):
    p, c = previous.setup()
    # The purge guard latches any move ending past Y280 that touched the bin.
    position = [200., 300., 36., 100.] if how == 'rectangle' else [150., 300., 36., 100.]
    p.obj['toolhead'].status['position'] = position
    p.obj['kctrl_purge_guard'].latched = how == 'latched'

    def leave():
        p.obj['toolhead'].status['position'][1] = 273.
    p.gcode.on_script[END.BIN_EXIT] = leave
    cancel(p)
    assert p.gcode.scripts == ['CANCEL_PRINT_BASE', END.BIN_EXIT, *END.RETAINED_FINISH]
    assert 'G1 Y273' in END.BIN_EXIT and 'Z' not in END.BIN_EXIT.replace('NAME=kctrl_end_bin_exit', '')
    assert p.obj['toolhead'].status['position'][2] == 36.
    assert c.phase == 'complete'


def test_bin_with_bed_too_high_refuses_every_move():
    p, c = previous.setup()
    p.obj['toolhead'].status['position'] = [200., 300., 12., 100.]
    cmd = cancel(p)
    assert p.gcode.scripts == ['CANCEL_PRINT_BASE']
    assert c.phase == 'failed' and c.failure == 'bin_exit_unsafe_bed_too_high'
    assert p.obj['extruder'].status['target'] == 0
    assert any('annulation incomplete' in m for m in cmd.messages)
    assert not gate_released(c)


@pytest.mark.parametrize('after', [[200., 300., 36., 100.], [190., 273., 36., 100.], [200., 273., 20., 100.]])
def test_unconfirmed_bin_exit_never_parks(after):
    p, c = previous.setup()
    p.obj['toolhead'].status['position'] = [200., 300., 36., 100.]
    p.gcode.on_script[END.BIN_EXIT] = lambda: p.obj['toolhead'].status.update(position=list(after))
    cancel(p)
    assert 'END_PRINT_POINT' not in p.gcode.scripts
    assert c.phase == 'failed' and c.failure == 'bin_exit_not_confirmed'


def test_unknown_position_while_homed_refuses():
    p, c = previous.setup()
    p.obj['toolhead'].status['position'] = [200., float('nan'), 36., 100.]
    cancel(p)
    assert p.gcode.scripts == ['CANCEL_PRINT_BASE']
    assert c.phase == 'failed' and c.failure == 'position_unknown'


def test_not_homed_has_no_bin_exit_and_still_completes():
    p, c = previous.setup()
    p.obj['toolhead'].status.update(homed_axes='', position=[200., 300., 0., 0.])
    cancel(p)
    assert p.gcode.scripts == ['CANCEL_PRINT_BASE', *END.RETAINED_FINISH]
    assert c.phase == 'complete'


@pytest.mark.parametrize('case,note', [
    ('no_route', 'head_loaded_without_route'),
    ('ambiguous', 'cfs_routes_ambiguous'),
    ('conflict', 'mapping_route_conflict'),
])
def test_unproven_slot_still_releases_without_inventing_one(case, note):
    p, c = previous.setup()
    if case == 'no_route':
        p.obj['box'].status['T1']['filament'] = 'None'
    elif case == 'ambiguous':
        p.obj['box'].status['T2']['filament'] = 'C'
    else:
        p.obj['kctrl_tool_change'].last = {'tool': 'T1', 'outcome': 'done', 'slot': 'T1B'}
    cmd = cancel(p)
    assert c.phase == 'complete' and c.get_status()['slot'] is None
    assert c.get_status()['retained'] is True
    assert any('sans emplacement prouve (%s)' % note in m for m in cmd.messages)
    assert not any('T1B' in m or 'T2C' in m for m in cmd.messages)
    assert not box_effects(p) and gate_released(c)


def test_empty_head_keeps_the_v3_deferred_end():
    p, c = previous.setup()
    p.obj[HEAD].status['filament_detected'] = False
    p.obj['box'].status['T1']['filament'] = 'None'
    cancel(p)
    assert p.reactor.callbacks
    p.reactor.drain()
    assert c.phase == 'complete' and c.get_status()['retained'] is False
    assert p.gcode.scripts[-2:] == ['END_PRINT_NO_M84', 'M84']


def test_unknown_head_sensor_keeps_the_v3_safe_refusal():
    p, c = previous.setup()
    p.obj[HEAD].status['filament_detected'] = None
    cancel(p)
    p.reactor.drain()
    base.assert_safe_failure(p, c)
    assert c.get_status()['retained'] is False


def test_sd_still_running_after_base_cancel_falls_back_to_v3():
    p, c = previous.setup()
    p.gcode.on_script['CANCEL_PRINT_BASE'] = lambda: None
    cancel(p)
    assert 'END_PRINT_POINT' not in p.gcode.scripts
    assert c.phase == 'waiting' and c.inflight is True


def test_pending_end_then_cancel_is_unchanged():
    p, c = previous.setup()
    p.gcode.handlers['END_PRINT'](base.Cmd())
    cancel(p)
    p.reactor.drain()
    base.assert_safe_failure(p, c)
    assert c.failure == 'cancelled_during_end'
    assert 'END_PRINT_POINT' not in p.gcode.scripts and not box_effects(p)


def test_firmware_error_during_finish_fails_closed():
    p, c = previous.setup()
    p.gcode.on_script['PRINT_PREPARE_CLEAR'] = lambda: p.gcode.emit('!! Move out of range')
    cancel(p)
    assert c.phase == 'failed' and c.failure == 'firmware_reported_error'
    assert 'END_PRINT_POINT' not in p.gcode.scripts
    assert p.obj['extruder'].status['target'] == 0 and not gate_released(c)


def test_shutdown_during_finish_stops_without_more_commands():
    p, c = previous.setup()
    p.gcode.on_script['M220 S100'] = lambda: p.handlers['klippy:shutdown']()
    cancel(p)
    assert c.phase == 'shutdown'
    assert p.gcode.scripts[-1] == 'M220 S100'
    assert p.heaters.calls > 0


def test_firmware_cancel_event_during_finish_does_not_fail_it():
    p, c = previous.setup()
    p.gcode.on_script['M107 P1'] = lambda: p.handlers['gcode:cancel']()
    cancel(p)
    assert c.phase == 'complete' and not c.failure


def test_heaters_that_stay_on_shut_the_printer_down():
    p, c = previous.setup()
    p.heaters.lie = True
    cancel(p)
    assert c.phase in ('failed', 'shutdown') and c.thermal_failure == 'targets_not_zero'
    assert p.shutdowns and not gate_released(c)
