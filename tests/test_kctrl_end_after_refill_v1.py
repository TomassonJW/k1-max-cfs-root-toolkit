"""Regression and failure-injection tests for ADR-069; no K1 transport."""
import copy
import importlib.util
from contextlib import nullcontext
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('kctrl_end_under_test', ROOT / 'packages/k1-control-v1/owned-start-print-v2/kctrl_end.py')
END = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(END)

CUT = ['// [box] cut sensor state:1', '// [box] cut to return OK',
       '// Cut sensor triggered.', '// [box] cut sensor state:0']


class Obj:
    def __init__(self, **status):
        self.status = status

    def get_status(self, now=None):
        return copy.deepcopy(self.status)


class Cmd:
    error = RuntimeError

    def __init__(self):
        self.messages = []

    def respond_info(self, text):
        self.messages.append(text)


class Reactor:
    NEVER = float('inf')

    def __init__(self):
        self.now = 0.
        self.callbacks = []
        self.timers = []
        self.events = []

    def monotonic(self):
        return self.now

    def register_timer(self, callback, when):
        timer = [when, callback]
        self.timers.append(timer)
        return timer

    def unregister_timer(self, timer):
        if timer in self.timers:
            self.timers.remove(timer)

    def register_callback(self, callback):
        self.callbacks.append(callback)

    def pause(self, when):
        while True:
            pending = [(t[0], 'timer', t) for t in self.timers if t[0] <= when]
            pending += [(t[0], 'event', t) for t in self.events if t[0] <= when]
            if not pending:
                break
            at, kind, item = min(pending, key=lambda x: x[0])
            self.now = at
            if kind == 'timer':
                item[0] = self.NEVER
                item[0] = item[1](at)
            else:
                self.events.remove(item)
                item[1]()
        self.now = when

    def drain(self):
        while self.callbacks:
            self.callbacks.pop(0)(self.now)


class SD:
    def __init__(self):
        self.active = True
        self.do_resume_status = False

    def is_active(self):
        return self.active


class Mapping:
    def __init__(self):
        self.map = {'T1A': 'T1B', 'T1B': 'T2D'}
        self.refreshed = 0

    def refresh(self):
        self.refreshed += 1


class Gcode:
    def __init__(self, printer):
        self.printer = printer
        self.scripts = []
        self.messages = []
        self.outputs = []
        self.on_script = {}
        self.cut_events = list(CUT)
        self.original_calls = []
        self.handlers = {name: (lambda cmd, n=name: self.original_calls.append(n))
                         for name in ('START_PRINT', 'END_PRINT', 'CANCEL_PRINT')}

    def register_command(self, name, handler):
        if handler is None:
            return self.handlers.pop(name, None)
        assert name not in self.handlers
        self.handlers[name] = handler

    def register_output_handler(self, callback):
        self.outputs.append(callback)

    def get_mutex(self):
        return nullcontext()

    def respond_info(self, text):
        self.messages.append(text)

    def emit(self, text):
        for callback in self.outputs:
            callback(text)

    def run_script_from_command(self, text):
        self.scripts.append(text)
        if text in self.on_script:
            self.on_script[text]()
            return
        p = self.printer
        if text == 'CANCEL_PRINT_BASE':
            p.sd.active = False
            p.sd.do_resume_status = False
            p.obj['pause_resume'].status['is_paused'] = False
        elif text == 'BOX_CUT_MATERIAL':
            for event in self.cut_events:
                self.emit(event)
        elif text.startswith('BOX_RETRUDE_MATERIAL_WITH_TNN TNN='):
            p.obj['filament_switch_sensor filament_sensor_2'].status['filament_detected'] = False
            for number in (1, 2):
                p.obj['box'].status['T%d' % number]['filament'] = 'None'


class Heaters:
    def __init__(self, printer):
        self.printer = printer
        self.calls = 0
        self.error = False
        self.lie = False

    def turn_off_all_heaters(self):
        self.calls += 1
        if self.error:
            raise RuntimeError('heater_api_failed')
        if not self.lie:
            for name in ('extruder', 'heater_bed'):
                self.printer.obj[name].status['target'] = 0.


class Printer:
    config_error = RuntimeError

    def __init__(self):
        self.reactor = Reactor()
        self.sd = SD()
        self.handlers = {}
        self.shutdowns = []
        self.obj = {
            'print_stats': Obj(filename='synthetic.gcode'),
            'extruder': Obj(target=200., temperature=200., can_extrude=True),
            'heater_bed': Obj(target=55.), 'toolhead': Obj(homed_axes='xyz'),
            'pause_resume': Obj(is_paused=False),
            'virtual_sdcard': self.sd,
            'filament_switch_sensor filament_sensor_2': Obj(filament_detected=True),
            'box': Obj(enable=1, state='connect',
                       T1={'state': 'connect', 'filament': 'B'},
                       T2={'state': 'connect', 'filament': 'None'}),
            'kctrl_slot_map': Mapping(),
            'kctrl_tool_change': Obj(),
        }
        self.obj['kctrl_tool_change'].last = {'tool': 'T0', 'outcome': 'done', 'slot': 'T1A'}
        self.gcode = Gcode(self)
        self.heaters = Heaters(self)
        self.obj.update(gcode=self.gcode, heaters=self.heaters)

    def get_reactor(self):
        return self.reactor

    def lookup_object(self, name, default=None):
        return self.obj.get(name, default)

    def register_event_handler(self, name, callback):
        self.handlers[name] = callback

    def invoke_shutdown(self, message):
        self.shutdowns.append(message)
        self.handlers['klippy:shutdown']()


class Config:
    def __init__(self, printer, enabled):
        self.printer, self.enabled = printer, enabled

    def get_printer(self):
        return self.printer

    def getboolean(self, key, default):
        return default if self.enabled is None else self.enabled

    def getfloat(self, key, default, **kw):
        return default

    def getint(self, key, default, **kw):
        return default


def setup(enabled=True):
    p = Printer()
    controller = END.KctrlEnd(Config(p, enabled))
    p.handlers['klippy:ready']()
    if enabled:
        p.gcode.handlers['START_PRINT'](Cmd())
        # A successful T0 on A, followed by a STOCK internal refill onto B.
        p.obj['kctrl_tool_change'].last = {'tool': 'T0', 'outcome': 'done', 'slot': 'T1A'}
    return p, controller


def finish(p, controller):
    p.gcode.handlers['END_PRINT'](Cmd())
    p.sd.active = False
    p.sd.do_resume_status = False
    p.reactor.drain()


def assert_safe_failure(p, controller):
    assert controller.phase in ('failed', 'shutdown')
    assert 'END_PRINT_NO_M84' not in p.gcode.scripts
    assert p.heaters.calls > 0
    assert p.obj['extruder'].status['target'] == 0 or p.shutdowns
    assert not p.reactor.timers


def rewinds(p):
    return [s for s in p.gcode.scripts if s.startswith('BOX_RETRUDE_')]


def test_refill_bypassing_T_wrapper_rewinds_B_not_cached_A():
    p, c = setup()
    finish(p, c)
    assert c.phase == 'complete'
    assert rewinds(p) == ['BOX_RETRUDE_MATERIAL_WITH_TNN TNN=T1B']
    assert p.gcode.scripts.index('BOX_CUT_MATERIAL') < p.gcode.scripts.index(rewinds(p)[0])
    assert p.obj['kctrl_tool_change'].last['slot'] == 'T1A'
    assert p.obj['kctrl_slot_map'].refreshed == 1
    # Physical B is NOT mapped a second time through T1B -> T2D.
    assert 'T2D' not in rewinds(p)[0]
    assert p.heaters.calls == 1


def test_refill_across_both_CFS():
    p, c = setup()
    p.obj['box'].status['T1']['filament'] = 'None'
    p.obj['box'].status['T2']['filament'] = 'D'
    p.obj['kctrl_slot_map'].map['T1A'] = 'T2D'
    finish(p, c)
    assert c.phase == 'complete'
    assert rewinds(p) == ['BOX_RETRUDE_MATERIAL_WITH_TNN TNN=T2D']


def test_new_job_discards_old_tool_cache_even_same_filename():
    p, c = setup()
    p.gcode.handlers['START_PRINT'](Cmd())
    assert p.obj['kctrl_tool_change'].last == {}
    assert c.epoch == 2
    finish(p, c)
    assert c.phase == 'complete'
    assert rewinds(p)[0].endswith('T1B')


@pytest.mark.parametrize('outcome', ['start', 'empty', 'paused_by_firmware', 'refuse', 'stock'])
def test_failed_or_unconfirmed_tool_target_is_not_physical_route(outcome):
    p, c = setup()
    p.obj['kctrl_tool_change'].last = {'tool': 'T1', 'outcome': outcome, 'slot': 'T2D'}
    finish(p, c)
    assert c.phase == 'complete'
    assert rewinds(p)[0].endswith('T1B')


@pytest.mark.parametrize('kind', ['absent', 'ambiguous', 'disconnected', 'malformed', 'map_conflict', 'head_unknown', 'axes_unknown'])
def test_incomplete_or_conflicting_observation_never_cuts(kind):
    p, c = setup()
    if kind == 'absent': p.obj['box'].status['T1']['filament'] = 'None'
    if kind == 'ambiguous': p.obj['box'].status['T2']['filament'] = 'B'
    if kind == 'disconnected': p.obj['box'].status['T2']['state'] = 'disconnect'
    if kind == 'malformed': p.obj['box'].status['T1']['filament'] = None
    if kind == 'map_conflict': p.obj['kctrl_slot_map'].map['T1A'] = 'T2D'
    if kind == 'head_unknown': p.obj['filament_switch_sensor filament_sensor_2'].status.clear()
    if kind == 'axes_unknown': p.obj['toolhead'].status['homed_axes'] = 'xy'
    finish(p, c)
    assert_safe_failure(p, c)
    assert 'BOX_CUT_MATERIAL' not in p.gcode.scripts
    assert not rewinds(p)


def test_resume_is_waited_outside_gcode_worker_without_writing_flag():
    p, c = setup()
    p.sd.do_resume_status = True
    p.gcode.handlers['END_PRINT'](Cmd())
    assert p.sd.do_resume_status is True
    assert not p.gcode.scripts
    def worker_exits():
        p.sd.active = False
        p.sd.do_resume_status = False
    p.reactor.events.append([.5, worker_exits])
    p.reactor.drain()
    assert c.phase == 'complete'
    assert p.reactor.now >= .5


def test_resume_that_never_clears_times_out_without_effect():
    p, c = setup()
    p.gcode.handlers['END_PRINT'](Cmd())
    p.sd.do_resume_status = True
    p.reactor.drain()
    assert_safe_failure(p, c)
    assert c.failure == 'end_timeout'
    assert p.sd.do_resume_status is True
    assert not p.gcode.scripts


@pytest.mark.parametrize('events', [[], CUT[:1], CUT[:2], list(reversed(CUT)),
                                  ['In resume, can not cut material now'],
                                  CUT + ['!! cutter refused']])
def test_cut_return_without_complete_proof_never_rewinds(events):
    p, c = setup()
    p.gcode.cut_events = events
    finish(p, c)
    assert_safe_failure(p, c)
    assert not rewinds(p)


def test_old_cut_events_and_box_cut_pos_are_not_proof():
    p, c = setup()
    for line in CUT: p.gcode.emit(line)
    p.obj['box'].status['cut_pos'] = 1
    p.gcode.cut_events = []
    finish(p, c)
    assert_safe_failure(p, c)
    assert not rewinds(p)


def test_delayed_release_event_is_required_before_finalization():
    p, c = setup()
    p.gcode.cut_events = CUT[:3]
    p.reactor.events.append([.2, lambda: p.gcode.emit(CUT[3])])
    finish(p, c)
    assert c.phase == 'complete'
    assert p.reactor.now >= .2


def test_cut_exception_does_not_skip_heater_shutdown():
    p, c = setup()
    p.gcode.on_script['BOX_CUT_MATERIAL'] = lambda: (_ for _ in ()).throw(RuntimeError('cut failed'))
    finish(p, c)
    assert_safe_failure(p, c)
    assert not rewinds(p)


def test_incomplete_rewind_is_not_retried_or_passed_to_BOX_END():
    p, c = setup()
    p.gcode.on_script['BOX_RETRUDE_MATERIAL_WITH_TNN TNN=T1B'] = lambda: None
    finish(p, c)
    assert_safe_failure(p, c)
    assert len(rewinds(p)) == 1
    assert c.failure == 'rewind_not_confirmed'


def test_route_change_during_cut_prevents_rewind():
    p, c = setup()
    def cut():
        for line in CUT: p.gcode.emit(line)
        p.obj['box'].status['T1']['filament'] = 'D'
    p.gcode.on_script['BOX_CUT_MATERIAL'] = cut
    finish(p, c)
    assert_safe_failure(p, c)
    assert not rewinds(p)


def test_empty_head_and_no_route_skips_all_filament_actions():
    p, c = setup()
    p.obj['filament_switch_sensor filament_sensor_2'].status['filament_detected'] = False
    p.obj['box'].status['T1']['filament'] = 'None'
    finish(p, c)
    assert c.phase == 'complete'
    assert p.gcode.scripts == ['END_PRINT_NO_M84', 'M84']


def test_empty_head_but_route_engaged_is_not_success():
    p, c = setup()
    p.obj['filament_switch_sensor filament_sensor_2'].status['filament_detected'] = False
    finish(p, c)
    assert_safe_failure(p, c)
    assert not p.gcode.scripts


@pytest.mark.parametrize('target', [0, 100, 321, float('nan'), float('inf'), True, '200'])
def test_cold_or_invalid_target_never_reheats(target):
    p, c = setup()
    p.obj['extruder'].status['target'] = target
    finish(p, c)
    assert_safe_failure(p, c)
    assert not any(s.startswith(('BOX_', 'M104', 'M109')) for s in p.gcode.scripts)


def test_temperature_is_observed_without_overriding_recipe():
    p, c = setup()
    p.obj['extruder'].status.update(target=240, temperature=210)
    p.reactor.events.append([.3, lambda: p.obj['extruder'].status.update(temperature=240)])
    finish(p, c)
    assert c.phase == 'complete'
    assert not any(s.startswith(('M104', 'M109')) for s in p.gcode.scripts)


def test_independent_watchdog_stops_heaters_inside_blocked_cut():
    p, c = setup()
    def cut():
        p.reactor.pause(181.)
        assert p.heaters.calls > 0
        assert p.obj['extruder'].status['target'] == 0
        for line in CUT: p.gcode.emit(line)
    p.gcode.on_script['BOX_CUT_MATERIAL'] = cut
    finish(p, c)
    assert_safe_failure(p, c)
    assert not rewinds(p)
    assert c.failure == 'end_timeout'


@pytest.mark.parametrize('mode', ['raise', 'lie'])
def test_heater_failure_requests_firmware_shutdown(mode):
    p, c = setup()
    p.gcode.cut_events = []
    p.heaters.error = mode == 'raise'
    p.heaters.lie = mode == 'lie'
    finish(p, c)
    assert_safe_failure(p, c)
    assert p.shutdowns
    assert c.thermal_failure


def test_duplicate_end_and_cancel_never_repeat_filament_actions():
    p, c = setup()
    finish(p, c)
    p.gcode.handlers['END_PRINT'](Cmd())
    p.gcode.handlers['CANCEL_PRINT'](Cmd())
    p.reactor.drain()
    assert len(rewinds(p)) == 1
    assert p.gcode.scripts.count('BOX_CUT_MATERIAL') == 1


def test_cancel_pending_end_aborts_before_any_cut():
    p, c = setup()
    p.gcode.handlers['END_PRINT'](Cmd())
    p.gcode.handlers['CANCEL_PRINT'](Cmd())
    p.reactor.drain()
    assert_safe_failure(p, c)
    assert not rewinds(p)
    assert p.gcode.scripts == ['CANCEL_PRINT_BASE']


def test_new_job_cannot_start_while_waiting():
    p, c = setup()
    p.gcode.handlers['END_PRINT'](Cmd())
    with pytest.raises(RuntimeError, match='finalisation'):
        p.gcode.handlers['START_PRINT'](Cmd())
    assert p.gcode.original_calls == ['START_PRINT']


def test_shutdown_invalidates_pending_callback():
    p, c = setup()
    p.gcode.handlers['END_PRINT'](Cmd())
    p.handlers['klippy:disconnect']()
    p.sd.active = False
    p.reactor.drain()
    assert not rewinds(p)
    assert c.phase == 'shutdown'


def test_disabled_candidate_keeps_all_original_handlers_and_has_no_effect():
    p, c = setup(enabled=None)
    p.gcode.handlers['END_PRINT'](Cmd())
    assert p.gcode.original_calls == ['END_PRINT']
    assert not p.gcode.outputs
    assert not p.gcode.scripts
    assert p.heaters.calls == 0
    assert c.phase == 'disabled'


def test_missing_handler_rolls_back_all_registration():
    p = Printer()
    del p.gcode.handlers['CANCEL_PRINT']
    before = dict(p.gcode.handlers)
    c = END.KctrlEnd(Config(p, True))
    with pytest.raises(RuntimeError): p.handlers['klippy:ready']()
    assert p.gcode.handlers == before
    assert not p.gcode.outputs


def test_no_resume_write_homing_mesh_or_transport_in_candidate():
    source = Path(SPEC.origin).read_text(encoding='utf-8')
    import ast
    tree = ast.parse(source, feature_version=(3, 8))
    imports = {node.name for n in ast.walk(tree) if isinstance(n, ast.Import) for node in n.names}
    assert imports == {'logging', 'math', 're'}
    for n in ast.walk(tree):
        if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            assert not any(isinstance(t, ast.Attribute) and t.attr == 'do_resume_status' for t in targets)
    p, c = setup()
    finish(p, c)
    assert not any(s.startswith(('G28', 'BED_MESH', 'RESUME', 'T0', 'BOX_ERROR_CLEAR')) for s in p.gcode.scripts)

def test_failed_callback_still_pending_blocks_new_start():
    p, c = setup()
    p.gcode.handlers['END_PRINT'](Cmd())
    p.gcode.handlers['CANCEL_PRINT'](Cmd())
    # The failure is visible, but its old callback has not drained yet.
    with pytest.raises(RuntimeError, match='finalisation'):
        p.gcode.handlers['START_PRINT'](Cmd())
    p.reactor.drain()
    p.gcode.handlers['START_PRINT'](Cmd())
    assert c.epoch == 2


def test_cut_cooling_the_nozzle_prevents_rewind():
    p, c = setup()
    def cut():
        for line in CUT: p.gcode.emit(line)
        p.obj['extruder'].status['target'] = 0
    p.gcode.on_script['BOX_CUT_MATERIAL'] = cut
    finish(p, c)
    assert_safe_failure(p, c)
    assert not rewinds(p)


def test_release_before_success_markers_does_not_prove_completed_cut():
    proof = END.CutProof()
    for line in [CUT[0], CUT[3], CUT[1], CUT[2]]:
        proof.feed(line)
    assert not proof.complete


def test_disabled_cancel_entrypoint_is_inert_even_if_called_directly():
    p, c = setup(enabled=None)
    with pytest.raises(RuntimeError): c.cancel(Cmd())
    assert not p.gcode.scripts
    assert p.heaters.calls == 0


def test_job_changed_after_request_is_refused_without_cfs_effect():
    p, c = setup()
    p.gcode.handlers['END_PRINT'](Cmd())
    p.obj['print_stats'].status['filename'] = 'another.gcode'
    p.sd.active = False
    p.reactor.drain()
    assert_safe_failure(p, c)
    assert not p.gcode.scripts


def test_error_while_finishing_cuts_heaters_without_retry():
    p, c = setup()
    p.gcode.on_script['END_PRINT_NO_M84'] = lambda: (_ for _ in ()).throw(RuntimeError('stock end failed'))
    finish(p, c)
    assert c.phase == 'failed'
    assert p.heaters.calls > 0
    assert p.obj['extruder'].status['target'] == 0
    assert len(rewinds(p)) == 1
    assert p.gcode.scripts.count('END_PRINT_NO_M84') == 1


def test_cancel_standalone_uses_same_safe_route_and_cut():
    p, c = setup()
    p.sd.do_resume_status = True
    p.gcode.handlers['CANCEL_PRINT'](Cmd())
    p.reactor.drain()
    assert c.phase == 'complete'
    assert c.reason == 'annulation'
    assert rewinds(p) == ['BOX_RETRUDE_MATERIAL_WITH_TNN TNN=T1B']

def test_firmware_cancel_event_can_abort_a_cut_holding_gcode_mutex():
    p, c = setup()
    def cut():
        p.handlers['gcode:cancel']()
        assert p.heaters.calls > 0
        assert p.obj['extruder'].status['target'] == 0
        for line in CUT: p.gcode.emit(line)
    p.gcode.on_script['BOX_CUT_MATERIAL'] = cut
    finish(p, c)
    assert_safe_failure(p, c)
    assert c.failure == 'cancelled_during_end'
    assert not rewinds(p)


def test_disabled_candidate_ignores_firmware_cancel_event():
    p, c = setup(enabled=None)
    p.handlers['gcode:cancel']()
    assert p.heaters.calls == 0
    assert not p.gcode.scripts


def captured_dispatcher(monkeypatch):
    # Optional private fixture: no vendor source is redistributed. Runs here
    # against the exact captured Creality dispatcher, without starting Klipper.
    import sys
    import types
    source = ROOT / 'inventory/raw/20260821-224828-g4-k1-control-z-mesh-runtime-v1/gcode.py'
    if not source.exists():
        pytest.skip('private Creality dispatcher capture not available')
    import hashlib
    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        '20d21ace63ac249c5e38d237898ff18d924047d4532a917124cb92eaed24cde7')
    extras, tool = types.ModuleType('extras'), types.ModuleType('extras.tool')
    tool.reportInformation = lambda *args, **kw: None
    monkeypatch.setitem(sys.modules, 'extras', extras)
    monkeypatch.setitem(sys.modules, 'extras.tool', tool)
    spec = importlib.util.spec_from_file_location('private_gcode_end_check', source)
    vendor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vendor)
    p = Printer()
    gcode = vendor.GCodeDispatch.__new__(vendor.GCodeDispatch)
    gcode.printer = p
    gcode.base_gcode_handlers = {}
    gcode.ready_gcode_handlers = {}
    gcode.gcode_handlers = gcode.ready_gcode_handlers
    gcode.gcode_help = {}
    gcode.output_callbacks = []
    gcode.is_fileinput = False
    gcode.is_printer_ready = True
    gcode.is_cancel = False
    gcode.mutex = nullcontext()
    called = []
    for name in ('START_PRINT', 'END_PRINT', 'CANCEL_PRINT'):
        gcode.register_command(name, lambda cmd, n=name: called.append((n, cmd.get('EXTRUDER_TEMP'))))
    p.obj['gcode'] = gcode
    return p, gcode, called


def test_real_captured_gcode_parser_hooks_and_multiline_console(monkeypatch):
    p, gcode, called = captured_dispatcher(monkeypatch)
    c = END.KctrlEnd(Config(p, True))
    p.handlers['klippy:ready']()
    command = gcode.create_gcode_command('START_PRINT', 'START_PRINT EXTRUDER_TEMP=205', {})
    gcode.ready_gcode_handlers['START_PRINT'](command)
    assert called == [('START_PRINT', '205')]
    c.phase, c.proof = 'cutting', END.CutProof()
    gcode.respond_info('\n'.join(line[3:] for line in CUT))
    assert c.proof.complete
    assert gcode.get_mutex() is gcode.mutex


def test_firmware_error_between_request_and_callback_is_retained():
    p, c = setup()
    p.gcode.handlers['END_PRINT'](Cmd())
    p.gcode.emit('!! late SD error')
    p.sd.active = False
    p.reactor.drain()
    assert_safe_failure(p, c)
    assert c.failure == 'firmware_reported_error'
    assert not p.gcode.scripts


def test_target_changed_while_worker_exits_is_not_adopted():
    p, c = setup()
    p.gcode.handlers['END_PRINT'](Cmd())
    p.obj['extruder'].status.update(target=240, temperature=240)
    p.sd.active = False
    p.reactor.drain()
    assert_safe_failure(p, c)
    assert 'BOX_CUT_MATERIAL' not in p.gcode.scripts


@pytest.mark.parametrize('temperature', [120, float('nan'), True, None])
def test_temperature_must_still_be_valid_after_cut(temperature):
    p, c = setup()
    def cut():
        for line in CUT: p.gcode.emit(line)
        p.obj['extruder'].status['temperature'] = temperature
    p.gcode.on_script['BOX_CUT_MATERIAL'] = cut
    finish(p, c)
    assert_safe_failure(p, c)
    assert not rewinds(p)


def test_cutter_must_remain_released_at_end_of_command():
    p, c = setup()
    p.gcode.cut_events = CUT + [CUT[0]]
    finish(p, c)
    assert_safe_failure(p, c)
    assert not rewinds(p)


def test_observed_recovery_release_after_rewind_is_accepted():
    # Actual 2026-09-21 trace, relative to BOX_CUT_MATERIAL at 09:19:48.864.
    # Cut returned at +24.465 s; the release arrived at +99.335 s, AFTER rewind.
    p, c = setup()
    def cut():
        for at, line in [(23.322, CUT[0]), (24.449, CUT[1]), (24.458, CUT[2])]:
            p.reactor.pause(at)
            p.gcode.emit(line)
        p.reactor.pause(24.465)
    def rewind():
        assert c.proof is not None and c.proof.cut_confirmed
        assert not c.proof.released
        p.reactor.pause(99.012)
        p.obj['filament_switch_sensor filament_sensor_2'].status['filament_detected'] = False
        p.obj['box'].status['T1']['filament'] = 'None'
        p.reactor.events.append([99.335, lambda: p.gcode.emit(CUT[3])])
    p.gcode.on_script['BOX_CUT_MATERIAL'] = cut
    p.gcode.on_script['BOX_RETRUDE_MATERIAL_WITH_TNN TNN=T1B'] = rewind
    finish(p, c)
    assert c.phase == 'complete'
    assert rewinds(p) == ['BOX_RETRUDE_MATERIAL_WITH_TNN TNN=T1B']
    assert p.reactor.now >= 99.335


def test_missing_release_after_rewind_refuses_finalization_without_retry():
    p, c = setup()
    p.gcode.cut_events = CUT[:3]
    finish(p, c)
    assert_safe_failure(p, c)
    assert c.failure == 'cutter_release_not_confirmed'
    assert len(rewinds(p)) == 1


@pytest.mark.parametrize('failure', ['runtime_exception', 'command_error', 'console_error'])
def test_real_dispatcher_errors_cannot_be_swallowed_by_stock(failure, monkeypatch):
    p, gcode, _ = captured_dispatcher(monkeypatch)
    p.sd.print_id, p.sd.cur_print_data = '', {}
    p.send_event = lambda name: None
    reached = []
    def cut(cmd):
        if failure == 'runtime_exception':
            raise RuntimeError('synthetic cutter failure')
        if failure == 'command_error':
            raise gcode.error('synthetic command refusal')
        gcode.respond_raw('!! synthetic console failure')
    gcode.register_command('SET_FILAMENT_SENSOR', lambda cmd: None)
    gcode.register_command('BOX_CUT_MATERIAL', cut)
    gcode.register_command('BOX_RETRUDE_MATERIAL_WITH_TNN', lambda cmd: reached.append('rewind'))
    gcode.register_command('END_PRINT_NO_M84', lambda cmd: reached.append('finalize'))
    c = END.KctrlEnd(Config(p, True))
    p.handlers['klippy:ready']()
    gcode.run_script_from_command('START_PRINT EXTRUDER_TEMP=200')
    gcode.run_script_from_command('END_PRINT')
    p.sd.active = False
    p.reactor.drain()
    assert c.phase == 'failed'
    assert not reached
    assert p.heaters.calls > 0
    assert p.obj['extruder'].status['target'] == 0


def test_real_dispatcher_handles_full_deferred_sequence(monkeypatch):
    p, gcode, _ = captured_dispatcher(monkeypatch)
    reached = []
    def cut(cmd):
        reached.append('cut')
        gcode.respond_info('\n'.join(line[3:] for line in CUT[:3]))
    def rewind(cmd):
        assert cmd.get('TNN') == 'T1B'
        reached.append('rewind')
        p.obj['filament_switch_sensor filament_sensor_2'].status['filament_detected'] = False
        p.obj['box'].status['T1']['filament'] = 'None'
        p.reactor.events.append([.3, lambda: gcode.respond_info(CUT[3][3:])])
    for name, handler in {
        'SET_FILAMENT_SENSOR': lambda cmd: None,
        'BOX_CUT_MATERIAL': cut,
        'BOX_RETRUDE_MATERIAL_WITH_TNN': rewind,
        'M400': lambda cmd: None,
        'END_PRINT_NO_M84': lambda cmd: reached.append('finalize'),
        'M84': lambda cmd: reached.append('motors_off'),
    }.items():
        gcode.register_command(name, handler)
    c = END.KctrlEnd(Config(p, True))
    p.handlers['klippy:ready']()
    gcode.run_script_from_command('START_PRINT EXTRUDER_TEMP=200')
    p.obj['kctrl_tool_change'].last = {'tool': 'T0', 'outcome': 'done', 'slot': 'T1A'}
    gcode.run_script_from_command('END_PRINT')
    assert not reached
    p.sd.active = False
    p.reactor.drain()
    assert reached == ['cut', 'rewind', 'finalize', 'motors_off']
    assert c.phase == 'complete'
    assert p.reactor.now >= .3


def test_real_cancel_emits_event_before_waiting_for_mutex(monkeypatch):
    p, gcode, _ = captured_dispatcher(monkeypatch)
    order = []
    class Mutex:
        def __enter__(self):
            order.append('mutex')
            assert p.obj['extruder'].status['target'] == 0
        def __exit__(self, *args):
            pass
    def event(name):
        order.append(name)
        p.handlers[name]()
    p.send_event = event
    gcode.mutex = Mutex()
    c = END.KctrlEnd(Config(p, True))
    p.handlers['klippy:ready']()
    gcode.run_script_from_command('START_PRINT EXTRUDER_TEMP=200')
    gcode.run_script_from_command('END_PRINT')
    gcode.invoke_cancel()
    assert order == ['gcode:cancel', 'mutex']
    assert c.failure == 'cancelled_during_end'
    assert gcode.gcode_handlers is gcode.ready_gcode_handlers
    p.sd.active = False
    p.reactor.drain()
