"""ADR-076: the owned end switches the stock auto refill off before any cut.

Replays the whole V4 suite against V5, then the 31 October 2026 end: a CFS
filament error (key839) during the cut launched the stock refill flush, which
kept pushing after the failed end had cut the heat.
"""
from types import SimpleNamespace
from pathlib import Path
import importlib.util
import pytest

ROOT = Path(__file__).resolve().parents[1]
REPLAY = importlib.util.spec_from_file_location(
    'v4_replay_for_v5', Path(__file__).with_name('test_kctrl_end_cancel_retained_v4.py'))
v4 = importlib.util.module_from_spec(REPLAY)
REPLAY.loader.exec_module(v4)
for name in dir(v4):
    if name.startswith('test_'):
        globals()[name] = getattr(v4, name)
previous, base = v4.previous, v4.base
V4_END = v4.END

SPEC = importlib.util.spec_from_file_location(
    'end_no_stock_flush', ROOT / 'packages/k1-control-v1/end-no-stock-flush-v5/kctrl_end.py')
END = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(END)

HEAD = v4.HEAD
REWIND = previous.REWIND
REFILL = 'BOX_ENABLE_AUTO_REFILL ENABLE=%d'
SENSOR_OFF = 'SET_FILAMENT_SENSOR SENSOR=filament_sensor_2 ENABLE=0'
# The line klippy.log recorded at 19:07:36 on 31 October 2026.
KEY839 = ('!! {"code":"key839", "msg":"filament error, no filament detected at box extrude '
          'position", "values": [1, "A"]}')
COMPLETE = 'K1 Control: fin terminee, tete vide et chauffes coupees'
LEFT_OFF = ' ; auto-remplacement CFS laisse coupe, retabli au prochain depart'
STILL_ON = ' ; auto-remplacement CFS encore actif'


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
            self.obj['kctrl_purge_guard'] = v4.Guard()
            # Stock BOX_ENABLE_AUTO_REFILL: the next read shows the new switch.
            self.obj['box'].status['auto_refill'] = 0
            self.gcode.handlers['BOX_ENABLE_AUTO_REFILL'] = lambda gcmd: None
            for value in (0, 1):
                self.gcode.on_script[REFILL % value] = \
                    lambda value=value: self.obj['box'].status.update(auto_refill=value)
    monkeypatch.setattr(previous, 'END', END)
    monkeypatch.setattr(previous, 'Printer', Printer)
    monkeypatch.setattr(v4, 'END', END)


def refill_on():
    p, c = previous.setup()
    p.obj['box'].status['auto_refill'] = 1
    return p, c


def refill_commands(p):
    return [s for s in p.gcode.scripts if s.startswith('BOX_ENABLE_AUTO_REFILL')]


def test_real_cancel_keeps_filament_and_releases_the_next_start():
    p, c = previous.setup()
    cmd = v4.cancel(p)
    assert p.gcode.scripts == ['CANCEL_PRINT_BASE', *END.RETAINED_FINISH]
    assert not p.reactor.callbacks and not p.reactor.timers
    assert p.obj['toolhead'].moves == []
    assert not v4.box_effects(p) and not p.logical_updates
    assert c.phase == 'complete' and not c.failure and not c.thermal_failure
    assert c.inflight is False and c.reason == 'annulation'
    status = c.get_status()
    assert status['retained'] is True and status['slot'] == 'T1B' and status['pending'] is False
    assert status['revision'] == 'end-no-stock-flush-v5'
    assert status['auto_refill_saved'] is None and status['auto_refill_restore_pending'] is False
    assert p.obj['extruder'].status['target'] == 0 and p.obj['heater_bed'].status['target'] == 0
    assert p.obj['box'].status['T1']['filament'] == 'B'
    assert p.obj[HEAD].status['filament_detected'] is True
    assert p.obj['box'].box_action.box_save.last_cmd == 'T1B'
    assert any('T1B garde en tete' in m and 'nouveau depart possible' in m for m in cmd.messages)
    assert v4.gate_released(c)
    assert not p.shutdowns


def test_end_switches_the_refill_off_before_any_cut_and_back_after_the_heat():
    p, c = refill_on()
    targets = []

    def enable():
        targets.append(p.obj['extruder'].status['target'])
        p.obj['box'].status['auto_refill'] = 1
    p.gcode.on_script[REFILL % 1] = enable
    base.finish(p, c)
    assert c.phase == 'complete' and not c.failure
    scripts = p.gcode.scripts
    assert refill_commands(p) == [REFILL % 0, REFILL % 1]
    assert scripts.index(REFILL % 0) < scripts.index(SENSOR_OFF) < scripts.index('BOX_CUT_MATERIAL')
    assert scripts.count(REWIND) == 1
    assert scripts[-3:] == ['END_PRINT_NO_M84', 'M84', REFILL % 1]
    assert targets == [0]
    status = c.get_status()
    assert p.obj['box'].status['auto_refill'] == 1
    assert status['auto_refill_saved'] == 1 and status['auto_refill_restore_pending'] is False
    assert p.gcode.messages[-1] == COMPLETE
    assert v4.gate_released(c)


def test_refill_already_off_is_left_alone():
    p, c = previous.setup()
    base.finish(p, c)
    assert c.phase == 'complete'
    assert refill_commands(p) == [] and p.obj['box'].status['auto_refill'] == 0
    status = c.get_status()
    assert status['auto_refill_saved'] == 0 and status['auto_refill_restore_pending'] is False


def test_empty_head_end_also_switches_the_refill():
    p, c = refill_on()
    p.obj[HEAD].status['filament_detected'] = False
    p.obj['box'].status['T1']['filament'] = 'None'
    base.finish(p, c)
    assert c.phase == 'complete'
    assert p.gcode.scripts == [REFILL % 0, 'END_PRINT_NO_M84', 'M84', REFILL % 1]


def test_refill_back_on_between_two_reads_stops_the_end_before_any_effect():
    p, c = refill_on()

    def flicker():
        p.obj['box'].status['auto_refill'] = 0
        p.reactor.events.append([p.reactor.now + .05,
                                 lambda: p.obj['box'].status.update(auto_refill=1)])
    p.gcode.on_script[REFILL % 0] = flicker
    base.finish(p, c)
    base.assert_safe_failure(p, c)
    assert c.failure == 'auto_refill_not_disabled'
    assert refill_commands(p) == [REFILL % 0]
    assert 'BOX_CUT_MATERIAL' not in p.gcode.scripts
    assert p.gcode.messages[-1].endswith(STILL_ON)


def test_refill_that_never_switches_off_stops_before_sensor_cut_or_push():
    p, c = refill_on()
    p.gcode.on_script[REFILL % 0] = lambda: None
    base.finish(p, c)
    base.assert_safe_failure(p, c)
    assert c.failure == 'auto_refill_not_disabled' and p.reactor.now >= 3.
    assert not any(s.startswith(('SET_FILAMENT_SENSOR', 'BOX_CUT', 'G1 E', 'BOX_RETRUDE'))
                   for s in p.gcode.scripts)
    status = c.get_status()
    assert status['auto_refill_saved'] == 1 and status['auto_refill_restore_pending'] is True
    assert p.gcode.messages[-1].endswith(STILL_ON)
    # Still on: the next start has nothing to put back.
    p.gcode.handlers['START_PRINT'](base.Cmd())
    assert c.get_status()['auto_refill_restore_pending'] is False
    assert refill_commands(p) == [REFILL % 0]


@pytest.mark.parametrize('owner', ['v5', 'v4'])
def test_cfs_filament_error_during_the_cut_finds_the_stock_refill_off(monkeypatch, owner):
    if owner == 'v4':
        monkeypatch.setattr(previous, 'END', V4_END)
    p, c = refill_on()
    armed = []

    def cut():
        p.gcode.cut()
        armed.append(p.obj['box'].status['auto_refill'])
        p.gcode.emit(KEY839)
    p.gcode.on_script['BOX_CUT_MATERIAL'] = cut
    base.finish(p, c)
    base.assert_safe_failure(p, c)
    assert 'G1 E-20 F5000' not in p.gcode.scripts and REWIND not in p.gcode.scripts
    assert not v4.gate_released(c)
    if owner == 'v4':
        # Armed when the error came: on the printer the stock flush then
        # pushed filament after this failed end had cut the heat.
        assert armed == [1] and c.failure == 'firmware_reported_error'
        assert refill_commands(p) == []
        return
    assert armed == [0] and c.failure == 'cfs_filament_error'
    assert refill_commands(p) == [REFILL % 0] and p.obj['box'].status['auto_refill'] == 0
    status = c.get_status()
    assert status['auto_refill_saved'] == 1 and status['auto_refill_restore_pending'] is True
    assert p.gcode.messages[-1] == 'K1 Control: fin incomplete (cfs_filament_error)' + LEFT_OFF


@pytest.mark.parametrize('lines', [
    ('!! failure', KEY839),
    (KEY839, '!! failure'),
    ('!! failure\n' + KEY839,),
    ('  !! Filament Error, no filament detected',),
])
def test_cfs_filament_error_is_named_whatever_the_order_or_case(lines):
    p, c = previous.setup()

    def cut():
        p.gcode.cut()
        for line in lines:
            p.gcode.emit(line)
    p.gcode.on_script['BOX_CUT_MATERIAL'] = cut
    base.finish(p, c)
    base.assert_safe_failure(p, c)
    assert c.failure == 'cfs_filament_error'


def test_unconfirmed_restore_leaves_the_refill_off_until_the_next_start():
    p, c = refill_on()
    p.gcode.on_script[REFILL % 1] = lambda: None
    base.finish(p, c)
    assert c.phase == 'complete' and not c.failure
    assert p.gcode.scripts[-3:] == ['END_PRINT_NO_M84', 'M84', REFILL % 1]
    assert p.obj['box'].status['auto_refill'] == 0
    assert c.get_status()['auto_refill_restore_pending'] is True
    assert p.gcode.messages[-1] == COMPLETE + LEFT_OFF
    assert v4.gate_released(c)
    calls = []

    def enable():
        calls.append(len(p.gcode.original_calls))
        p.obj['box'].status['auto_refill'] = 1
    p.gcode.on_script[REFILL % 1] = enable
    p.gcode.handlers['START_PRINT'](base.Cmd())
    # Proven back on before the stock START_PRINT heats anything.
    assert calls == [1] and p.gcode.original_calls == ['START_PRINT', 'START_PRINT']
    status = c.get_status()
    assert status['auto_refill_restore_pending'] is False and status['auto_refill_saved'] is None
    assert status['job_epoch'] == 2


def test_start_refuses_while_the_refill_cannot_be_put_back():
    p, c = refill_on()
    p.gcode.on_script[REFILL % 1] = lambda: None
    base.finish(p, c)
    with pytest.raises(RuntimeError, match='auto-remplacement CFS non retabli'):
        p.gcode.handlers['START_PRINT'](base.Cmd())
    assert p.gcode.original_calls == ['START_PRINT'] and c.epoch == 1
    assert c.get_status()['auto_refill_restore_pending'] is True
    assert refill_commands(p) == [REFILL % 0, REFILL % 1, REFILL % 1]


@pytest.mark.parametrize('command', [SENSOR_OFF, 'BOX_CUT_MATERIAL', 'G1 E-20 F5000'])
def test_refill_switched_back_on_stops_the_end_before_the_next_effect(command):
    p, c = refill_on()
    hook = p.gcode.on_script.get(command)

    def touchscreen():
        # The c440x screen sends BOX_ENABLE_AUTO_REFILL ENABLE=1 when it connects.
        if hook:
            hook()
        p.obj['box'].status['auto_refill'] = 1
    p.gcode.on_script[command] = touchscreen
    base.finish(p, c)
    base.assert_safe_failure(p, c)
    assert c.failure == 'auto_refill_reenabled'
    assert REWIND not in p.gcode.scripts
    assert p.gcode.messages[-1].endswith(STILL_ON)
    if command == SENSOR_OFF:
        assert 'BOX_CUT_MATERIAL' not in p.gcode.scripts
    elif command == 'BOX_CUT_MATERIAL':
        assert p.obj['toolhead'].moves == []
    else:
        assert 'G1 E-15 F120' not in p.gcode.scripts
        assert 'RESTORE_GCODE_STATE NAME=kctrl_end_withdraw MOVE=0' in p.gcode.scripts


def test_refill_switched_on_after_the_last_cfs_command_is_kept_without_a_command():
    p, c = refill_on()

    def rewind():
        p.gcode.rewind()
        p.obj['box'].status['auto_refill'] = 1
    p.gcode.on_script[REWIND] = rewind
    base.finish(p, c)
    assert c.phase == 'complete' and not c.failure
    assert refill_commands(p) == [REFILL % 0]
    assert c.get_status()['auto_refill_restore_pending'] is False
    assert p.gcode.messages[-1] == COMPLETE


@pytest.mark.parametrize('value', [None, True, 2, '1', 'missing'])
def test_unknown_refill_state_refuses_before_any_effect(value):
    p, c = previous.setup()
    if value == 'missing':
        p.obj['box'].status.pop('auto_refill')
    else:
        p.obj['box'].status['auto_refill'] = value
    base.finish(p, c)
    base.assert_safe_failure(p, c)
    assert c.failure == 'auto_refill_unknown'
    assert refill_commands(p) == [] and 'BOX_CUT_MATERIAL' not in p.gcode.scripts
    status = c.get_status()
    assert status['auto_refill_saved'] is None and status['auto_refill_restore_pending'] is False
    assert p.gcode.messages[-1] == 'K1 Control: fin incomplete (auto_refill_unknown)'


def test_refill_unreadable_after_the_switch_off_blocks_the_start_until_read():
    p, c = refill_on()

    def cut():
        p.gcode.cut()
        p.obj['box'].status.pop('auto_refill')
    p.gcode.on_script['BOX_CUT_MATERIAL'] = cut
    base.finish(p, c)
    base.assert_safe_failure(p, c)
    assert c.failure == 'auto_refill_unknown'
    assert p.gcode.messages[-1].endswith(' ; auto-remplacement CFS non confirme')
    with pytest.raises(RuntimeError, match='non retabli'):
        p.gcode.handlers['START_PRINT'](base.Cmd())
    p.obj['box'].status['auto_refill'] = 1
    p.gcode.handlers['START_PRINT'](base.Cmd())
    assert c.get_status()['auto_refill_restore_pending'] is False
    assert p.gcode.original_calls == ['START_PRINT', 'START_PRINT']


def test_retained_cancel_never_touches_the_refill():
    p, c = refill_on()
    v4.cancel(p)
    assert c.phase == 'complete' and c.get_status()['retained'] is True
    assert not v4.box_effects(p) and p.obj['box'].status['auto_refill'] == 1
    status = c.get_status()
    assert status['auto_refill_saved'] is None and status['auto_refill_restore_pending'] is False


def test_missing_refill_primitive_wraps_nothing():
    p, c = previous.setup(ready=False)
    del p.gcode.handlers['BOX_ENABLE_AUTO_REFILL']
    before = dict(p.gcode.handlers)
    with pytest.raises(RuntimeError, match='missing primitive BOX_ENABLE_AUTO_REFILL'):
        c._ready()
    assert p.gcode.handlers == before and c.originals == {}
    assert p.gcode.scripts == []


def test_fresh_owner_reports_a_refill_it_has_not_touched():
    # What remote_install.py requires right after the restart (end_not_fresh).
    p, c = previous.setup(ready=False)
    c._ready()
    status = c.get_status()
    assert status['phase'] == 'idle' and status['retained'] is False
    assert status['auto_refill_saved'] is None and status['auto_refill_restore_pending'] is False
    assert status['revision'] == 'end-no-stock-flush-v5'
    assert status['wrapped'] == ['CANCEL_PRINT', 'END_PRINT', 'START_PRINT']
