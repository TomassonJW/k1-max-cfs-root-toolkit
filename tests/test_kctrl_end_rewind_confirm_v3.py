"""Replay the real ACK + empty head + stale B, preserving V2 motion tests."""
from types import SimpleNamespace
from pathlib import Path
import importlib.util
import pytest

# Separate module globals: the inherited motion test monkeypatches its END
# binding, which must not leak into the historical V2 suite.
ROOT = Path(__file__).resolve().parents[1]
REPLAY = importlib.util.spec_from_file_location('v2_replay_for_v3', Path(__file__).with_name('test_kctrl_end_overlap_v2.py'))
previous = importlib.util.module_from_spec(REPLAY)
REPLAY.loader.exec_module(previous)
for name in dir(previous):
    if name.startswith('test_'):
        globals()[name] = getattr(previous, name)
setup, finish, base, REWIND = previous.setup, previous.finish, previous.base, previous.REWIND

SPEC = importlib.util.spec_from_file_location('rewind_confirm', ROOT / 'packages/k1-control-v1/end-rewind-confirm-v3/kctrl_end.py')
END = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(END)


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
    monkeypatch.setattr(previous, 'END', END)
    monkeypatch.setattr(previous, 'Printer', Printer)


def test_real_success_ack_empty_head_stale_route_commits_without_extra_motors():
    p, c = setup()
    def ack():
        # Actual CFS ACK after 13.8 s; this primitive does not clear Tn_data.
        p.reactor.pause(p.reactor.now + 13.8)
        p.obj['filament_switch_sensor filament_sensor_2'].status['filament_detected'] = False
    p.gcode.on_script[REWIND] = ack
    finish(p, c)
    assert c.phase == 'complete' and not c.failure
    assert p.logical_updates == ['T1B']
    save = p.obj['box'].box_action.box_save
    assert save.last_cmd is None and save.last_cmd_tmp == 'T1B'
    assert p.gcode.scripts.count(REWIND) == 1
    assert p.obj['toolhead'].moves == [([None, 291.5, None, None], 30.)]
    assert p.gcode.scripts[-2:] == ['END_PRINT_NO_M84', 'M84']


def test_transient_clear_does_not_finalize():
    p, c = setup()
    def ack():
        p.obj['filament_switch_sensor filament_sensor_2'].status['filament_detected'] = False
        p.reactor.events.append([.3, lambda: p.obj['filament_switch_sensor filament_sensor_2'].status.update(filament_detected=True)])
    p.gcode.on_script[REWIND] = ack
    finish(p, c)
    base.assert_safe_failure(p, c)
    assert not p.logical_updates


@pytest.mark.parametrize('failure', ['ack_false', 'ack_none', 'head_present', 'wrong_route', 'stock_changed', 'cancelled'])
def test_no_logical_clear_without_current_complete_evidence(failure):
    p, c = setup()
    action = p.obj['box'].box_action
    def ack(*args):
        p.obj['filament_switch_sensor filament_sensor_2'].status['filament_detected'] = failure == 'head_present'
        if failure == 'wrong_route': p.obj['box'].status['T1']['filament'] = 'D'
        if failure == 'stock_changed': action.box_save.last_cmd = 'T2A'
        if failure == 'cancelled': c._cancel_event()
        return {'ack_false': False, 'ack_none': None}.get(failure, True)
    action.communication_retrude_process = ack
    finish(p, c)
    base.assert_safe_failure(p, c)
    assert not p.logical_updates


@pytest.mark.parametrize('failure', ['noop', 'exception', 'route_reappears', 'head_reappears'])
def test_failed_bookkeeping_or_later_drift_stays_failed(failure):
    p, c = setup()
    action = p.obj['box'].box_action
    def ack(*args):
        p.obj['filament_switch_sensor filament_sensor_2'].status['filament_detected'] = False
        return True
    action.communication_retrude_process = ack
    original = action.update_filament_pos
    def update(route, destination):
        if failure == 'noop': return
        if failure == 'exception': raise RuntimeError('injected bookkeeping failure')
        original(route, destination)
        def drift():
            if failure == 'route_reappears': p.obj['box'].status['T1']['filament'] = 'B'
            else: p.obj['filament_switch_sensor filament_sensor_2'].status['filament_detected'] = True
        p.reactor.events.append([p.reactor.now + .1, drift])
    action.update_filament_pos = update
    finish(p, c)
    base.assert_safe_failure(p, c)


def test_missing_bookkeeping_refuses_registration_before_any_motion():
    p, c = setup(ready=False)
    del p.obj['box'].box_action.update_filament_pos
    with pytest.raises(RuntimeError, match='missing primitive'): c._ready()
    assert not c.originals and not p.gcode.scripts


def test_successive_prints_do_not_keep_previous_failure_or_route():
    p, c = setup()
    finish(p, c)
    assert c.phase == 'complete'
    c.start(base.Cmd())
    assert c.phase == 'idle' and c.epoch == 2 and c.run is None and not c.failure
