"""Separated end: delayed firmware state and physical ordering, no transport."""
import importlib.util
from pathlib import Path
import pytest
import test_kctrl_end_after_refill_v1 as base

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('separated_end', ROOT / 'packages/k1-control-v1/end-separated-v1/kctrl_end.py')
END = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(END)
PRIMITIVES = ('BOX_CUT_MATERIAL', 'BOX_SET_BOX_MODE', 'BOX_CTRL_CONNECTION_MOTOR_ACTION', 'BOX_RETRUDE_PROCESS')
REWIND = 'BOX_RETRUDE_PROCESS ADDR=1 NUM=B TRIGGER=MATERIAL'

class Toolhead(base.Obj):
    def __init__(self, p):
        super().__init__(homed_axes='xyz', position=[150., 150., 7.42, 100.])
        self.p = p
        self.moves = []
        self.release = True
    def manual_move(self, pos, speed):
        self.moves.append((pos, speed))
        self.p.gcode.scripts.append('LOCAL_CUTTER_RELEASE')
        self.status['position'] = [old if new is None else new for old, new in zip(self.status['position'], pos)]
        if self.release:
            self.p.gcode.emit(base.CUT[-1])
    def wait_moves(self):
        pass

class Gcode(base.Gcode):
    def __init__(self, p):
        super().__init__(p)
        self.handlers.update({n: lambda c: None for n in PRIMITIVES})
        self.ready_gcode_handlers = self.handlers
        self.cut_events = base.CUT[:-1]
        self.delay = 3.
        self.on_script['BOX_CUT_MATERIAL'] = self.cut
        self.on_script[REWIND] = self.rewind
    def cut(self):
        self.printer.obj['toolhead'].status['position'][:2] = [38., 305.5]
        for event in self.cut_events:
            self.emit(event)
    def rewind(self):
        p = self.printer
        def clear():
            p.obj['box'].status['T1']['filament'] = 'None'
            p.obj['filament_switch_sensor filament_sensor_2'].status['filament_detected'] = False
        p.reactor.events.append([p.reactor.now + self.delay, clear])

class Action:
    def __init__(self,p): self.p=p; self.result=True
    def communication_set_box_mode(self,addr,mode):
        self.p.gcode.run_script_from_command('BOX_SET_BOX_MODE ADDR=%d MODE=%s NUM=0' % (addr,mode))
        return self.result
    def communication_ctrl_connection_motor_action(self,addr,action):
        self.p.gcode.run_script_from_command('BOX_CTRL_CONNECTION_MOTOR_ACTION ADDR=%d ACTION=%s' % (addr,action))
        return self.result
    def communication_retrude_process(self,addr,slot,trigger):
        self.p.gcode.run_script_from_command('BOX_RETRUDE_PROCESS ADDR=%d NUM=%s TRIGGER=%s' % (addr,slot,trigger))
        return self.result

class Printer(base.Printer):
    def __init__(self):
        super().__init__()
        self.gcode = Gcode(self)
        self.obj['gcode'] = self.gcode
        self.obj['toolhead'] = Toolhead(self)
        self.obj['box'].box_action = Action(self)

def setup(enabled=True, ready=True):
    p = Printer()
    c = END.KctrlEnd(base.Config(p, enabled))
    if ready:
        c._ready()
        if enabled:
            c.start(base.Cmd())
            p.obj['kctrl_tool_change'].last = {'tool': 'T0', 'outcome': 'done', 'slot': 'T1A'}
    return p, c

finish = base.finish

def test_delayed_route_clear_waits_at_cutter_without_z_or_bin_move():
    p, c = setup()
    finish(p, c)
    assert c.phase == 'complete'
    assert p.reactor.now >= 3.5
    assert p.obj['toolhead'].moves == [([None, 291.5, None, None], 30.)]
    assert p.obj['toolhead'].status['position'][2] == 7.42
    scripts = p.gcode.scripts
    expected = ['BOX_CUT_MATERIAL', 'LOCAL_CUTTER_RELEASE', 'M83', 'G1 E-20 F5000', 'G1 E-15 F120', 'M400',
                'BOX_SET_BOX_MODE ADDR=1 MODE=IDLE NUM=0', 'BOX_CTRL_CONNECTION_MOTOR_ACTION ADDR=1 ACTION=STOP', REWIND, 'END_PRINT_NO_M84']
    assert [s for s in scripts if s in expected] == expected
    assert not any('BOX_RETRUDE_MATERIAL' in s or 'EXTRUDE_POS' in s for s in scripts)
    assert scripts.count(REWIND) == 1
    assert p.heaters.calls == 1

@pytest.mark.parametrize('delay', [0., .1, 6., 18.])
def test_valid_completion_delay_is_accepted(delay):
    p, c = setup()
    p.gcode.delay = delay
    finish(p, c)
    assert c.phase == 'complete'

@pytest.mark.parametrize('failure', ['stale_route', 'head_present', 'other_route', 'disconnect', 'ambiguous', 'missing_head', 'pause', 'firmware_error', 'cancel', 'deadline'])
def test_failure_during_rewind_cannot_finalize_or_retry(failure):
    p, c = setup()
    def effect():
        if failure == 'stale_route': return
        if failure == 'head_present': p.obj['box'].status['T1']['filament'] = 'None'
        if failure == 'other_route': p.obj['box'].status['T1']['filament'] = 'A'
        if failure == 'disconnect': p.obj['box'].status['T2']['state'] = 'disconnect'
        if failure == 'ambiguous': p.obj['box'].status['T2']['filament'] = 'D'
        if failure == 'missing_head': p.obj['filament_switch_sensor filament_sensor_2'].status.clear()
        if failure == 'pause': p.obj['pause_resume'].status['is_paused'] = True
        if failure == 'firmware_error': p.gcode.emit('!! failure')
        if failure == 'cancel': c._cancel_event()
        if failure == 'deadline': p.reactor.pause(c.run['deadline'])
    p.gcode.on_script[REWIND] = effect
    finish(p, c)
    base.assert_safe_failure(p, c)
    assert p.gcode.scripts.count(REWIND) == 1
    assert p.obj['toolhead'].status['position'][2] == 7.42

@pytest.mark.parametrize('position', [[185.5,305.,25.], [38.,230.,7.], [38.,float('nan'),7.], None])
def test_bad_cut_position_refuses_before_local_move_or_withdraw(position):
    p,c=setup()
    cut=p.gcode.cut
    def wrong():
        cut()
        p.obj['toolhead'].status['position']=position
    p.gcode.on_script['BOX_CUT_MATERIAL']=wrong
    finish(p,c)
    base.assert_safe_failure(p,c)
    assert not p.obj['toolhead'].moves
    assert REWIND not in p.gcode.scripts
    assert 'G1 E-20 F5000' not in p.gcode.scripts

def test_blade_must_release_before_extruder_or_cfs_retraction():
    p,c=setup()
    p.obj['toolhead'].release=False
    finish(p,c)
    base.assert_safe_failure(p,c)
    assert c.failure=='cutter_release_not_confirmed'
    assert 'G1 E-20 F5000' not in p.gcode.scripts
    assert REWIND not in p.gcode.scripts

@pytest.mark.parametrize('primitive',PRIMITIVES)
def test_missing_primitive_refuses_takeover_atomically(primitive):
    p,c=setup(ready=False)
    before=dict(p.gcode.handlers)
    del p.gcode.handlers[primitive]
    with pytest.raises(RuntimeError,match='missing primitive'): c._ready()
    assert p.gcode.handlers['START_PRINT']==before['START_PRINT']
    assert not c.originals
    assert not p.gcode.scripts

def test_disabled_successor_is_inert():
    p,c=setup(False)
    assert not c.originals and not p.gcode.outputs and not p.gcode.scripts

@pytest.mark.parametrize('command',['G1 E-20 F5000','G1 E-15 F120', 'BOX_SET_BOX_MODE ADDR=1 MODE=IDLE NUM=0','BOX_CTRL_CONNECTION_MOTOR_ACTION ADDR=1 ACTION=STOP'])
def test_command_failure_stops_before_next_motor(command):
    p,c=setup()
    def error(): raise RuntimeError('injected')
    p.gcode.on_script[command]=error
    finish(p,c)
    base.assert_safe_failure(p,c)
    assert REWIND not in p.gcode.scripts
    assert 'RESTORE_GCODE_STATE NAME=kctrl_end_withdraw MOVE=0' in p.gcode.scripts

def test_transient_clear_does_not_finalize():
    p,c=setup()
    p.gcode.delay=.1
    def bounce():
        p.gcode.rewind()
        p.reactor.events.append([.3,lambda:p.obj['box'].status['T1'].update(filament='B')])
    p.gcode.on_script[REWIND]=bounce
    finish(p,c)
    base.assert_safe_failure(p,c)

def test_sd_resume_really_exits_before_cut():
    p,c=setup()
    c.end(base.Cmd())
    p.sd.active=False
    p.sd.do_resume_status=True
    def clear():
        assert 'BOX_CUT_MATERIAL' not in p.gcode.scripts
        p.sd.do_resume_status=False
    p.reactor.events.append([2.,clear])
    p.reactor.drain()
    assert c.phase=='complete'

def test_repeat_end_does_not_repeat_filament_effect():
    p,c=setup()
    finish(p,c)
    c.end(base.Cmd())
    p.reactor.drain()
    assert p.gcode.scripts.count(REWIND)==1

@pytest.mark.parametrize('result',[None,False,0,1,'OK',{}])
def test_implicit_or_failed_ack_is_not_success(result):
    p,c=setup()
    p.obj['box'].box_action.result=result
    finish(p,c)
    base.assert_safe_failure(p,c)
    assert REWIND not in p.gcode.scripts
    assert c.failure.startswith('cfs_ack_not_confirmed_')

@pytest.mark.parametrize('change',[{'target':220.},{'temperature':170.},{'can_extrude':False}])
def test_temperature_drift_after_first_retraction_stops_second(change):
    p,c=setup()
    p.gcode.on_script['G1 E-20 F5000']=lambda:p.obj['extruder'].status.update(change)
    finish(p,c)
    base.assert_safe_failure(p,c)
    assert 'G1 E-15 F120' not in p.gcode.scripts
    assert REWIND not in p.gcode.scripts
