"""resilience-v2 start module (ADR-081, document 111) on the fake Klipper/CFS.

The failed spool relay of 15 November (document 110) is replayed here: the
stock load leaves the print paused, filament in the head, CFS at rest, head in
the bin. The module must bring the print back by itself, or keep a real pause
with a sentence and a working "Reprendre". Every earlier start test is rerun
twice on this module: relay hooks absent, then installed.
Software validation only, no printer transport.
"""

import ast
import importlib
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

import test_retained_start_integration as base
import test_start_load_recovery as rec
import test_resilience_start as res
from test_retained_start_integration import Gcmd

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages/k1-control-v1/resilience-v2'
NAME = '_resilience_resume'
package = ModuleType(NAME)
package.__path__ = [str(PACKAGE), str(ROOT / 'packages/k1-control-v1/retained-start-v1'),
                    str(ROOT / 'packages/k1-control-v1/end-rewind-confirm-v3')]
sys.modules[NAME] = package
module = importlib.import_module(NAME + '.kctrl_start')
policy = importlib.import_module(NAME + '.kctrl_start_policy')

# Rewritten below for this module: the count, the revision and the path.
ADAPTED = ('test_every_earlier_start_test_is_rerun_on_this_module',
           'test_status_exposes_revision_recovery_head_and_rest', 'test_python38_grammar')
RERUN = {name: value for name, value in vars(res).items()
         if name.startswith('test_') and name not in ADAPTED}
globals().update(RERUN)

HEAD = 'filament_switch_sensor filament_sensor_2'
SPOOL = 'filament_switch_sensor filament_sensor'
PARAM = 'gcode_macro PRINTER_PARAM'
TMC = 'tmc2209 extruder'
STOP = (235.225, 141.302, 3.8)
LOWERED = 46.079
PUSH = 'G1 E20 F150.00000'
EXIT = 'G1 Y273 F15000'
PAUSED_CURRENT = .280763
BODY = ('START_PRINT\nT0\nM106 S255\nM106 P2 S128\nG1 X10 Y10 E1\n'
        'M106 S128 ; layer fan\nG1 X20 Y20 E1\n')
TAIL = 'G1 X30 Y30 E1\nM107\n' + base.FOOTER
LIMITS = {'max_velocity': 600., 'max_accel': 12000., 'max_accel_to_decel': 6000.,
          'square_corner_velocity': 5.}
ADVANCE = {'pressure_advance': .04, 'smooth_time': .04}
FANS = {0: 128, 2: 128}
FRESH = {'installed': True, 'failure': '', 'note': None, 'last': None}
BY_PURGE = 'K1 Control: filament %s en tete, reprise par purge au bac'
RESUMED = 'K1 Control: filament %s repris au bac, impression relancee'
PRESS = ('K1 Control: chargement de %s en echec, filament en tete : appuyer sur Reprendre, '
         'la reprise se fera par purge au bac')
REFUSED = 'K1 Control: reprise refusee (%s), impression gardee en pause'


def key(code='key836', unit=1, letter='B'):
    return '!! ' + json.dumps({'code': code, 'msg': 'load error', 'values': [unit, letter]})


def hook(m):
    """What klippy:ready does for the relay, once the fake has what it needs."""
    owner = m.owner
    if not (owner.enabled and owner.originals) or owner.resume_hooks:
        return
    owner.resume_failure = ''
    try:
        owner._ready_resume()
    except Exception as error:
        owner.resume_failure = str(error) or type(error).__name__


def install_relay(m):
    """Give an earlier fake the least a relay install needs, without an event."""
    owner = m.owner
    if not (owner.enabled and owner.originals):
        return
    plain, added = not isinstance(m, rec.Machine), []
    if plain:
        for name, value in (('virtual_sdcard', SimpleNamespace(resume_tnn=None, file_position=0)),
                            ('gcode_move', SimpleNamespace(reset_last_position=lambda: None))):
            if name not in m.objects:
                m.objects[name] = value
                added.append(name)
        m.lookup_object = lambda name, default=KeyError: (
            m.objects[name] if default is KeyError or name in m.objects else default)
    else:
        m.sd.resume_tnn, m.sd.file_position = None, 0
    for name in module.STOCK_NAMES:
        m.ready_gcode_handlers.setdefault(name, lambda gcmd: None)
    change = m.change
    change.reload = lambda name, stock, gcmd: stock(gcmd)
    change.in_start, change.runout_armed = (lambda: False), (lambda: True)
    change.rearm_runout = lambda name: None
    m.action.box_state.Tnn_map = {}
    hook(m)
    assert owner.get_status()['relay']['installed'] is True, owner.resume_failure
    # The earlier tests must keep the very objects they were written for.
    for name in added:
        del m.objects[name]
    if plain:
        del m.lookup_object


def _install_everywhere(monkeypatch):
    def wrap(cls, skip):
        original = cls.__dict__['__init__']

        def __init__(self, *args, **kwargs):
            original(self, *args, **kwargs)
            if not isinstance(self, skip):
                install_relay(self)
        monkeypatch.setattr(cls, '__init__', __init__)
    wrap(base.Machine, rec.Machine)
    wrap(rec.Machine, ResumeMachine)


def pytest_generate_tests(metafunc):
    if any(metafunc.function is value for value in RERUN.values()):
        metafunc.parametrize('new_module', ['absent', 'installed'], indirect=True)


def adopt(monkeypatch):
    """Point every earlier harness at the tranche 2 candidate."""
    for harness in (base, rec, res):
        monkeypatch.setattr(harness, 'module', module)
        monkeypatch.setattr(harness, 'policy', policy)
    monkeypatch.setattr(res, 'PACKAGE', PACKAGE)
    monkeypatch.setattr(base.Machine, 'get', lambda self, key, default=None: (
        str(res.head_file(self.path.parent)) if key == 'head_state_file' else default),
        raising=False)
    res._keep_watch_apart(monkeypatch, base.Machine)
    res._keep_watch_apart(monkeypatch, rec.Machine)


@pytest.fixture(autouse=True)
def new_module(monkeypatch, request):
    """Every Machine, the rerun tests included, drives the tranche 2 candidate."""
    adopt(monkeypatch)
    if getattr(request, 'param', 'absent') == 'installed':
        _install_everywhere(monkeypatch)


class Reactor:
    """Klipper's reactor: the fake machine keeps the clock and the timers."""
    NEVER = float('inf')

    def __init__(self, machine):
        self.machine = machine

    def monotonic(self):
        return self.machine.now

    def pause(self, when):
        m = self.machine
        m.waits.append(round(when - m.now, 3))
        m.now = max(m.now, when)
        m.on_wait()
        return m.now

    def register_timer(self, fn, when):
        return self.machine.register_timer(fn, when)

    def unregister_timer(self, timer):
        return self.machine.unregister_timer(timer)

    def update_timer(self, timer, when):
        return self.machine.update_timer(timer, when)


class ResumeMachine(rec.Machine):
    """A mono-filament print on T1C with the stock pause, relay and resume."""

    def __init__(self, tmp_path, route='T1C', missing=(), install=True, **kwargs):
        self.reactor_fake = Reactor(self)
        self.console, self.waits, self.on_wait = [], [], lambda: None
        self.load_mode, self.relay_to, self.refill_mode = 'nov15', 'T1B', 'relay'
        self.resume_in, self.started = None, False
        self.sticky_route = self.flush_at_bin = False
        self.resume_effective = True
        self.load_lines, self.load_raises = None, False
        self.second_drop = self.cut_heaters = self.inside_error_after = False
        self.extrude_tnn_after = None
        self.refusals, self.stop_point = 0, None
        self.fans, self.tn_cur_tnn = dict(FANS), 'T1A'
        super().__init__(tmp_path, head=True, route=route, failure=None, **kwargs)
        self.position = list(STOP) + [0.]
        self.data[PARAM] = {'hotend_temp': 0, 'fans': 3, 'z_safe_pause': 0., 'fan2_speed': 0}
        self.objects[PARAM] = base.State(self.data[PARAM])
        self.data['toolhead'].update(LIMITS)
        self.data['extruder'].update(temperature=200., target=200., can_extrude=True, **ADVANCE)
        self.data[HEAD]['enabled'] = True
        self.data['box']['T' + route[1]]['mode'] = '2'
        self.data[TMC].update(run_current=.55, hold_current=.55)
        self.sd.resume_tnn, self.sd.file_position = None, len(BODY.encode())
        self.path.write_bytes((BODY + TAIL).encode())
        self.action.box_state.Tnn_map = {'T1A': route}
        change = self.change
        change.reload, change.in_start = self.tool_reload, lambda: self.started
        change.runout_armed = lambda: bool(self.data[HEAD]['enabled'])
        change.rearm_runout, change.last_reload = self.rearm_runout, None
        for name, handler in (('RESUME', self.stock_resume),
                              ('BOX_CHECK_MATERIAL_REFILL', self.stock_refill),
                              ('BOX_RESUME_EXTRUDE', self.stock_flush)):
            if name not in missing:
                self.ready_gcode_handlers[name] = handler
        if install:
            hook(self)

    def get_reactor(self):
        return self.reactor_fake

    def gcmd(self, **params):
        command = Gcmd(**params)
        command.messages = self.console
        return command

    def unit(self, slot):
        return self.data['box']['T' + slot[1]]

    def routes(self):
        return tuple('T%d%s' % (index, self.data['box']['T%d' % index]['filament'])
                     for index in (1, 2)
                     if self.data['box']['T%d' % index]['filament'] in tuple('ABCD'))

    def tmc(self):
        return self.data[TMC]['run_current'], self.data[TMC]['hold_current']

    def paused(self):
        return self.data['pause_resume']['is_paused']

    def count(self, name):
        return sum(event[0] == name for event in self.events)

    def commit(self, slot, value):
        self.events.append(('commit', slot, value))
        unit = self.unit(slot)
        if value is None:
            if unit['filament'] == slot[2]:
                unit['filament'] = 'None'
        elif not (self.sticky_route and unit['filament'] not in ('None', value[2])):
            unit['filament'] = value[2]

    # kctrl_tool_change, as owned-start-print-v2 writes it.
    def set_runout(self, enable):
        self.run_script_from_command(
            'SET_FILAMENT_SENSOR SENSOR=filament_sensor_2 ENABLE=%d' % enable)

    def rearm_runout(self, name):
        self.run_script_from_command('M400')
        self.set_runout(True)

    def tool_reload(self, name, stock, gcmd):
        change = self.change
        if change.in_start():
            stock(gcmd)
            return
        armed = change.runout_armed()
        if armed:
            self.set_runout(False)
        failed = True
        try:
            stock(gcmd)
            failed = False
        finally:
            if armed:
                change.rearm_runout(name)
            change.last_reload = {'tool': name, 'error': failed,
                                  'head': self.data[HEAD]['filament_detected'],
                                  'paused': self.paused()}

    # Stock firmware and macros.
    def stock_move(self, x=None, y=None, z=None, planner=True):
        target = self.position[:]
        for index, value in enumerate((x, y, z)):
            if value is not None:
                target[index] = value
        try:
            latch = self.envelope.check(self.position, target)
        except policy.StartRefused:
            self.refusals += 1
            self.cool()
            self.emit('!! ' + module.GUARD_REFUSAL)
            raise RuntimeError(module.GUARD_REFUSAL)
        self.position = target
        self.envelope.commit(latch)
        self.events.append(('stock_move', tuple(target[:3])))
        if not planner:
            self.stale = True

    def pause_print(self, park=False):
        self.stop_point = tuple(self.position[:3])
        self.data['pause_resume']['is_paused'] = True
        self.data['print_stats']['state'] = 'paused'
        self.pause.pause_command_sent = self.pause.sd_paused = True
        self.data[PARAM].update(hotend_temp=int(self.data['extruder']['target']),
                                z_safe_pause=LOWERED)
        self.stock_move(z=self.position[2] + LOWERED)
        if park:
            self.stock_move(x=210., y=291.5)
        self.data[TMC].update(run_current=PAUSED_CURRENT, hold_current=PAUSED_CURRENT)
        self.fans = {0: 0, 2: 0}
        self.events.append(('stock_pause',))

    def runout(self):
        """The head sensor sees the end of the spool: PAUSE, then its runout gcode."""
        self.data[HEAD]['filament_detected'] = False
        self.pause_print()
        self.data[HEAD]['enabled'] = False
        self.run_script_from_command('BOX_CHECK_MATERIAL_REFILL')

    def stock_refill(self, gcmd):
        self.events.append(('stock_refill',))
        if self.refill_mode == 'rest':
            for route in self.routes():
                self.unit(route)['mode'] = '0'
            return
        if self.refill_mode == 'nothing':
            return
        table = {'T1A': self.relay_to}
        table.update({route: self.relay_to for route in self.routes()})
        self.action.box_state.Tnn_map = table
        self.run_script_from_command('T1A')
        if self.resume_in == 'refill':
            self.run_script_from_command('RESUME')

    def stock_load(self, name, gcmd):
        target = self.action.box_state.Tnn_map.get(name, name)
        if self.routes() == (target,) and self.data[HEAD]['filament_detected'] is True:
            self.events.append(('stock_T_noop',))
            return
        self.events.append(('stock_T',))
        self.stock_ran += 1
        self.now += 180.
        if self.load_mode == 'quiet':
            return
        unit, back = self.unit(target), None
        if self.position[2] < 35.:
            back = tuple(self.position[:3])
            self.stock_move(z=35.0133, planner=False)
        self.stock_move(x=210., y=273., planner=False)
        self.stock_move(y=305., planner=False)
        if self.load_mode == 'success':
            for route in self.routes():
                self.unit(route)['filament'] = 'None'
            unit.update(filament=target[2], mode='2')
            self.action.box_save.last_cmd = self.action.extrude_tnn = target
            self.data[HEAD]['filament_detected'] = True
            self.stock_move(y=291.5, planner=False)
            if back:
                self.stock_move(y=273., planner=False)
                self.stock_move(x=back[0], y=back[1], planner=False)
                self.stock_move(z=back[2], planner=False)
            if self.resume_in == 'reload':
                self.run_script_from_command('RESUME')
            return
        self.data[HEAD]['filament_detected'] = self.load_mode != 'empty'
        for line in self.load_lines or [key(unit=int(target[1]), letter=target[2])]:
            self.emit(line)
        unit['mode'] = '0'
        self.action.box_save.last_err = 'box_extrude_err'
        self.action.extrude_tnn = self.extrude_tnn_after
        self.data['extruder'].update(target=195., temperature=195., pressure_advance=0.)
        self.data['toolhead'].update(max_velocity=100., max_accel=5000.)
        self.stock_move(y=291.5, planner=False)
        if self.second_drop:
            self.data[TMC].update(run_current=PAUSED_CURRENT, hold_current=PAUSED_CURRENT)
        if self.cut_heaters:
            self.cool()
        if self.inside_error_after:
            self.objects['box'].inside_error = True
        if self.load_raises:
            raise RuntimeError('stock load raised')

    def stock_flush(self, gcmd):
        self.events.append(('stock_flush',))
        if self.flush_at_bin:
            self.stock_move(y=273., planner=False)
            self.stock_move(x=210., planner=False)
            self.stock_move(y=305., planner=False)
            self.stock_move(y=291.5, planner=False)

    def stock_resume(self, gcmd):
        """The stock RESUME macro, line for line."""
        self.events.append(('stock_resume',))
        run, param = self.run_script_from_command, self.data[PARAM]
        run('BOX_ERROR_CLEAR')
        run('RESTORE_E_CURRENT')
        run('BOX_RESUME_EXTRUDE')
        wanted = int(param['hotend_temp'])
        if wanted:
            above = wanted > self.data['extruder']['temperature']
            run(('M109 S%d' if above else 'M104 S%d') % wanted)
            param['hotend_temp'] = 0
        if self.position[1] > 291.5:
            self.stock_move(y=291.5)
        lift = int(param['z_safe_pause'])
        if lift > 2:
            self.stock_move(z=self.position[2] - (lift - 2))
        if self.resume_effective:
            self.resume_base()

    def resume_base(self):
        if not self.paused():
            self.console.append('Print is not paused, resume aborted')
            return
        self.stock_move(*self.stop_point)
        self.stale = False
        self.data['pause_resume']['is_paused'] = False
        self.data['print_stats']['state'] = 'printing'
        self.pause.pause_command_sent = self.pause.sd_paused = False
        self.data[PARAM]['z_safe_pause'] = 0.
        self.sd.resume_tnn = self.tn_cur_tnn
        self.events.append(('resume_base',))

    def work(self):
        """virtual_sdcard replays the load named at the resume, then prints on."""
        name, self.sd.resume_tnn = self.sd.resume_tnn, None
        if name:
            self.run_script_from_command(name)

    def press_resume(self):
        self.run_script_from_command('RESUME')

    def run_script_from_command(self, text):
        for line in text.splitlines():
            parts = line.split()
            command = parts[0] if parts else ''
            args = dict(part.split('=', 1) for part in parts[1:] if '=' in part)
            if not (command in module.STOCK_NAMES or command in module.SLOTS or command in (
                    'M104', 'M106', 'M107', 'SET_FILAMENT_SENSOR', 'SET_VELOCITY_LIMIT',
                    'SET_PRESSURE_ADVANCE', 'BOX_MODIFY_TN_DATA', 'RESTORE_E_CURRENT')):
                super().run_script_from_command(line)
                continue
            self.events.append(('gcode', line))
            if command in module.STOCK_NAMES:
                self.ready_gcode_handlers[command](self.gcmd(**args))
            elif command in module.SLOTS:
                self.change.reload(
                    command, lambda gcmd, name=command: self.stock_load(name, gcmd), self.gcmd())
            elif command == 'M104':
                self.data['extruder']['target'] = float(parts[1][1:])
            elif command in ('M106', 'M107'):
                words = {part[0]: float(part[1:]) for part in parts[1:]}
                self.fans[int(words.get('P', 0))] = (
                    0 if command == 'M107' else int(words.get('S', 255)))
            elif command == 'SET_FILAMENT_SENSOR':
                assert args['SENSOR'] == 'filament_sensor_2'
                self.data[HEAD]['enabled'] = args['ENABLE'] == '1'
            elif command == 'SET_VELOCITY_LIMIT':
                names = {word: name for name, word in module.LIMIT_WORDS.items()}
                self.data['toolhead'].update(
                    {names[word]: float(value) for word, value in args.items()})
            elif command == 'SET_PRESSURE_ADVANCE':
                names = {word: name for name, word in module.ADVANCE_WORDS.items()}
                self.data['extruder'].update(
                    {names[word]: float(value) for word, value in args.items()})
            elif command == 'BOX_MODIFY_TN_DATA':
                assert args['PART'] == 'filament'
                self.data['box']['T' + args['ADDR']]['filament'] = args['DATA']
            else:
                self.data[TMC].update(run_current=.55, hold_current=.55)
            self.callback(line)


def printing(tmp_path, **kwargs):
    m = ResumeMachine(tmp_path, **kwargs)
    res.watch(m)
    assert m.owner.get_status()['relay'] == FRESH
    assert m.owner.head['slot'] == m.routes()[0] and m.owner.printing['filename'] == 'job.gcode'
    return m


def relay(m):
    return m.owner.get_status()['relay']


def once(m, line, effect):
    """Run `effect` the first time the machine executes `line`."""
    done = []

    def callback(command):
        if command == line and not done:
            done.append(command)
            effect()
    m.callback = callback


def assert_plain(texts):
    for text in texts:
        assert text.isascii() and "'" not in text and not text.startswith('!!'), text
        assert 'failed' not in text.lower(), text


def assert_printing(m, slot):
    assert m.paused() is False and m.data['print_stats']['state'] == 'printing'
    assert tuple(m.position[:3]) == STOP
    assert m.routes() == (slot,) and m.unit(slot)['mode'] == '2'
    assert m.action.box_save.last_cmd == slot and m.action.box_save.last_err is None
    assert m.sd.resume_tnn is None and m.data[HEAD]['enabled'] is True
    assert m.fans == FANS and m.tmc() == (.55, .55)
    assert {name: m.data['toolhead'][name] for name in LIMITS} == LIMITS
    assert {name: m.data['extruder'][name] for name in ADVANCE} == ADVANCE
    assert m.data['extruder']['target'] == 200. and m.data[PARAM]['hotend_temp'] == 0
    assert m.envelope.latched is False and m.refusals == 0 and ('cool',) not in m.events
    assert m.owner.head['slot'] == slot and m.owner.resume_run is None
    assert_plain(m.console)


def assert_kept_paused(m, y=273.):
    """A real pause: head out of the bin, bed never raised, nothing refused."""
    assert m.paused() is True and m.data['print_stats']['state'] == 'paused'
    assert m.position[1] == y and m.position[2] == pytest.approx(STOP[2] + LOWERED)
    assert m.envelope.latched is False and m.refusals == 0
    assert m.owner.resume_run is None and m.owner.moving == 0
    assert m.owner.in_refill == m.owner.in_reload == m.owner.envelope == m.owner.in_resume == 0
    assert_plain(m.console)


# The 15 November relay.

def test_failed_relay_of_november_15_resumes_by_itself(tmp_path):
    m = printing(tmp_path)
    m.runout()
    m.work()
    assert m.count('stock_T') == 1 and m.count('stock_T_noop') == 0
    assert_printing(m, 'T1B')
    assert m.change.last_reload == {'tool': 'T1A', 'error': False, 'head': True, 'paused': True}
    commands = m.commands()
    assert commands.count(PUSH) == 7 and module.SETTLE in m.waits
    # The extruder gets its running current before the stock load, not after.
    current = next(index for index, event in enumerate(m.events)
                   if event[0] == 'gcode' and event[1].startswith('SET_TMC_CURRENT'))
    assert m.events[current][1] == 'SET_TMC_CURRENT STEPPER=extruder CURRENT=0.550000 HOLDCURRENT=0.550000'
    assert current < m.events.index(('stock_T',))
    # The head leaves the bin at constant height before the stock resume raises the bed.
    assert m.events.index(('gcode', EXIT)) < m.events.index(('stock_resume',))
    assert m.count('stock_resume') == 1 and m.count('stock_flush') == 0
    assert ('mode', 1, 'PRINT', 'B') in m.events
    assert commands.index('SET_VELOCITY_LIMIT ACCEL=12000.000 VELOCITY=600.000') > commands.index(PUSH)
    assert 'SET_PRESSURE_ADVANCE ADVANCE=0.040000' in commands
    assert 'M106 P0 S128' in commands and 'M106 P2 S128' in commands
    assert commands[-4:] == ['SAVE_GCODE_STATE NAME=KCTRL_RESUME_PRIME', 'M83', 'G1 E0.800 F1800',
                             'M400'] or commands[-1] == 'RESTORE_GCODE_STATE NAME=KCTRL_RESUME_PRIME MOVE=0'
    assert m.console == [BY_PURGE % 'T1B', RESUMED % 'T1B']
    assert relay(m) == {'installed': True, 'failure': '', 'note': None,
                        'last': {'outcome': 'resumed', 'slot': 'T1B', 'reason': 'relay_failed'}}
    res.watch(m)
    assert res.on_disk(tmp_path)['slot'] == 'T1B' and m.owner.head['slot'] == 'T1B'


def test_same_unit_route_that_sticks_is_written_by_the_vendor_command(tmp_path):
    m = printing(tmp_path)
    m.sticky_route = True
    m.runout()
    assert 'BOX_MODIFY_TN_DATA ADDR=1 PART=filament DATA=B' in m.commands()
    assert_printing(m, 'T1B')


def test_two_stock_lines_naming_the_same_slot_still_attribute_it(tmp_path):
    m = printing(tmp_path)
    m.load_lines = [key('key837'), key('key836')]
    m.runout()
    assert_printing(m, 'T1B')
    assert relay(m)['last']['outcome'] == 'resumed'


def test_stock_load_that_raises_is_recovered_and_nothing_escapes(tmp_path):
    m = printing(tmp_path)
    m.load_raises = True
    m.runout()
    assert m.change.last_reload['error'] is True
    assert_printing(m, 'T1B')
    assert m.owner.in_refill == m.owner.in_reload == m.owner.envelope == 0


def test_second_current_drop_during_the_load_is_raised_again_for_the_purge(tmp_path):
    m = printing(tmp_path)
    m.second_drop = True
    m.runout()
    sets = [line for line in m.commands() if line.startswith('SET_TMC_CURRENT')]
    assert sets == ['SET_TMC_CURRENT STEPPER=extruder CURRENT=0.550000 HOLDCURRENT=0.550000'] * 2
    assert_printing(m, 'T1B')


def test_second_relay_of_the_same_print_recovers_again(tmp_path):
    m = printing(tmp_path)
    m.runout()
    res.watch(m)
    assert relay(m)['note'] is None
    m.relay_to = 'T1D'
    m.runout()
    m.work()
    assert m.count('stock_T') == 2 and m.commands().count(PUSH) == 14
    assert_printing(m, 'T1D')
    assert relay(m)['last'] == {'outcome': 'resumed', 'slot': 'T1D', 'reason': 'relay_failed'}


def test_without_the_relay_hooks_the_stock_resume_is_refused_by_the_bin_guard(tmp_path):
    """Document 110, section 2: what "Reprendre" would have done on 15 November."""
    m = ResumeMachine(tmp_path, install=False)
    res.watch(m)
    assert relay(m)['installed'] is False
    assert m.ready_gcode_handlers['RESUME'] == m.stock_resume
    m.runout()
    assert m.paused() is True and m.envelope.latched is True
    with pytest.raises(RuntimeError, match='proteger le bac'):
        m.press_resume()
    assert m.refusals == 1 and ('cool',) in m.events and m.paused() is True


# The relay that works, as on 31 October.

@pytest.mark.parametrize('resume_in', ['reload', 'refill'])
@pytest.mark.parametrize('flush_at_bin', [False, True])
def test_working_relay_passes_through_with_a_quiet_bin_exit(tmp_path, resume_in, flush_at_bin):
    m = printing(tmp_path)
    m.load_mode, m.resume_in, m.flush_at_bin = 'success', resume_in, flush_at_bin
    m.runout()
    m.work()
    assert m.count('stock_T') == 1 and m.count('stock_T_noop') == 1
    assert m.count('stock_resume') == 1 and m.count('stock_flush') == 1
    assert m.commands().count(PUSH) == 0 and m.console == []
    assert m.paused() is False and tuple(m.position[:3]) == STOP
    assert m.routes() == ('T1B',) and m.owner.head['slot'] == 'T1B'
    assert m.refusals == 0 and ('cool',) not in m.events and m.envelope.latched is False
    assert m.tmc() == (.55, .55)
    assert relay(m) == FRESH
    assert m.owner.in_refill == m.owner.in_reload == m.owner.envelope == m.owner.in_resume == 0


# "Reprendre" pressed by hand.

@pytest.mark.parametrize('park', [False, True])
def test_plain_pause_resumes_through_the_stock_macro_untouched(tmp_path, park):
    m = printing(tmp_path)
    m.pause_print(park=park)
    m.press_resume()
    assert m.commands() == ['RESUME', 'BOX_ERROR_CLEAR', 'RESTORE_E_CURRENT',
                            'BOX_RESUME_EXTRUDE', 'M104 S200']
    assert m.count('stock_resume') == 1 and m.count('stock_flush') == 1
    assert m.paused() is False and tuple(m.position[:3]) == STOP and m.console == []
    m.work()
    assert m.count('stock_T') == 0 and m.count('stock_T_noop') == 1
    assert relay(m) == FRESH and m.owner.head['slot'] == 'T1C'


def test_cfs_left_at_rest_is_purged_back_when_resume_is_pressed(tmp_path):
    """Document 106: after "extrude all" the unit is at rest and nothing comes out."""
    m = printing(tmp_path)
    m.pause_print(park=True)
    m.unit('T1C')['mode'] = '0'
    m.press_resume()
    m.work()
    assert m.commands().count(PUSH) == 7 and m.count('stock_T') == 0
    assert_printing(m, 'T1C')
    assert m.console == [BY_PURGE % 'T1C', RESUMED % 'T1C']
    assert relay(m)['last'] == {'outcome': 'resumed', 'slot': 'T1C', 'reason': 'cfs_at_rest'}
    assert not any(line.startswith('SET_VELOCITY_LIMIT') for line in m.commands())


def test_refill_that_leaves_the_cfs_at_rest_says_what_resume_will_do(tmp_path):
    m = printing(tmp_path)
    m.refill_mode = 'rest'
    m.pause_print()
    m.run_script_from_command('BOX_CHECK_MATERIAL_REFILL')
    assert m.console == ['K1 Control: CFS au repos, filament en tete : appuyer sur Reprendre, '
                         'la reprise se fera par purge au bac']
    assert m.paused() is True and m.tmc() == (PAUSED_CURRENT, PAUSED_CURRENT)
    assert m.commands().count(PUSH) == 0
    m.press_resume()
    assert_printing(m, 'T1C')


def test_resume_with_stock_parameter_goes_straight_to_the_stock_macro(tmp_path):
    m = printing(tmp_path)
    m.pause_print()
    m.unit('T1C')['mode'] = '0'
    m.run_script_from_command('RESUME STOCK=1')
    assert m.commands().count(PUSH) == 0 and m.count('stock_resume') == 1
    assert m.paused() is False and relay(m)['last'] is None


def test_resume_on_a_running_print_is_swallowed(tmp_path):
    m = printing(tmp_path)
    m.press_resume()
    assert m.console == ['K1 Control: impression deja en cours, reprise ignoree']
    assert m.count('stock_resume') == 0 and m.commands() == ['RESUME']


@pytest.mark.parametrize('start', [lambda m: setattr(m, 'started', True),
                                   lambda m: setattr(m.owner, 'phase', 'material')])
def test_during_a_start_everything_is_left_to_the_stock_flow(tmp_path, start):
    m = printing(tmp_path)
    m.pause_print()
    m.unit('T1C')['mode'] = '0'
    start(m)
    m.refill_mode = 'nothing'
    m.run_script_from_command('BOX_CHECK_MATERIAL_REFILL')
    m.press_resume()
    assert m.count('stock_refill') == 1 and m.count('stock_resume') == 1
    assert m.commands().count(PUSH) == 0 and m.console == []
    assert not any(line.startswith('SET_TMC_CURRENT') for line in m.commands())
    assert relay(m)['last'] is None


def test_latched_guard_with_a_high_bed_refuses_resume_before_any_move(tmp_path):
    m = printing(tmp_path)
    m.pause_print()
    m.position[:3] = [185.5, 305., 10.]
    m.envelope.commit(True)
    before = len(m.events)
    with pytest.raises(RuntimeError) as error:
        m.press_resume()
    assert str(error.value) == REFUSED % 'plateau trop haut pour sortir du bac'
    assert m.events[before:] == [('gcode', 'RESUME')]
    assert m.paused() is True and m.envelope.latched is True


# Recoveries that cannot be proven keep a real pause.

def test_empty_head_keeps_the_pause_and_resume_reloads_through_stock(tmp_path):
    m = printing(tmp_path)
    m.load_mode = 'empty'
    m.runout()
    assert m.console == ['K1 Control: chargement en echec, tete vide : verifier la bobine '
                         'puis appuyer sur Reprendre']
    assert_kept_paused(m)
    assert m.tmc() == (PAUSED_CURRENT, PAUSED_CURRENT) and m.commands().count(PUSH) == 0
    assert relay(m)['note']['slot'] is None and m.owner.head is None
    m.load_mode = 'success'
    m.press_resume()
    m.work()
    assert m.count('stock_resume') == 1 and m.count('stock_T') == 2
    assert m.commands().count(PUSH) == 0 and m.refusals == 0
    assert m.paused() is False and m.routes() == ('T1B',) and m.owner.head['slot'] == 'T1B'
    assert tuple(m.position[:3]) == STOP and m.envelope.latched is False


@pytest.mark.parametrize('change', [
    lambda m: setattr(m, 'load_lines', [key(letter='B'), key(letter='D')]),
    lambda m: setattr(m, 'extrude_tnn_after', 'T1D'),
    lambda m: setattr(m, 'load_lines', [key()] * (module.MAX_STOCK_LINES + 1))])
def test_filament_that_cannot_be_attributed_is_left_to_the_stock_resume(tmp_path, change):
    m = printing(tmp_path)
    change(m)
    m.runout()
    assert m.console == ['K1 Control: chargement en echec, filament en tete non attribue : '
                         'Reprendre relancera le chargement stock']
    assert_kept_paused(m)
    assert m.commands().count(PUSH) == 0 and m.owner.head is None
    m.press_resume()
    assert m.count('stock_resume') == 1 and m.commands().count(PUSH) == 0
    assert m.paused() is False and m.sd.resume_tnn == 'T1A' and m.refusals == 0


def test_purge_that_proves_nothing_keeps_the_pause_until_resume_succeeds(tmp_path):
    m = printing(tmp_path)
    m.buffer = 1
    m.runout()
    sentence = REFUSED % 'le filament ne vient pas de la bobine'
    assert m.console == [BY_PURGE % 'T1B', sentence]
    assert_kept_paused(m)
    assert m.commands().count(PUSH) == 7 and m.count('stock_resume') == 0
    assert m.data['extruder']['target'] == 195. and m.tmc() == (PAUSED_CURRENT, PAUSED_CURRENT)
    assert relay(m)['last'] == {'outcome': 'refused', 'slot': 'T1B', 'cause': 'relay_failed',
                                'reason': 'buffer_consumption_unconfirmed'}
    assert relay(m)['note'] == {'tool': 'T1A', 'target': 'T1B', 'slot': 'T1B', 'head': True,
                                'paused': True, 'tried': True}
    with pytest.raises(RuntimeError) as error:
        m.press_resume()
    assert str(error.value) == sentence
    assert_kept_paused(m)
    assert m.count('stock_resume') == 0 and m.tmc() == (PAUSED_CURRENT, PAUSED_CURRENT)
    m.buffer = 0
    m.press_resume()
    m.work()
    assert m.count('stock_T') == 1 and m.commands().count(PUSH) == 21
    assert_printing(m, 'T1B')


def test_cfs_error_that_does_not_clear_stops_before_any_push(tmp_path):
    m = printing(tmp_path)
    m.clears_error = False
    m.runout()
    assert m.console[-1] == REFUSED % 'le CFS signale encore une erreur'
    assert_kept_paused(m)
    assert m.commands().count(PUSH) == 0
    assert relay(m)['last']['reason'] == 'cfs_error_not_cleared'


def test_cfs_still_handling_its_error_is_waited_one_minute_then_left_to_resume(tmp_path):
    m = printing(tmp_path)
    m.inside_error_after = True
    m.runout()
    assert m.console == ['K1 Control: le CFS traite encore son erreur, appuyer sur Reprendre '
                         'quand il a fini']
    assert m.waits == [1.] * 60
    assert_kept_paused(m)
    with pytest.raises(RuntimeError) as error:
        m.press_resume()
    assert str(error.value) == REFUSED % 'le CFS signale encore une erreur'
    assert m.commands().count(PUSH) == 0
    m.objects['box'].inside_error = False
    m.press_resume()
    assert_printing(m, 'T1B')


def test_cfs_that_finishes_its_error_in_time_is_recovered_without_a_press(tmp_path):
    m = printing(tmp_path)
    m.inside_error_after = True
    m.on_wait = lambda: setattr(m.objects['box'], 'inside_error', len(m.waits) < 10)
    m.runout()
    assert m.waits[:11] == [1.] * 10 + [module.SETTLE]
    assert_printing(m, 'T1B')


def test_error_line_during_the_settle_leaves_the_decision_to_resume(tmp_path):
    m = printing(tmp_path)
    m.on_wait = lambda: m.emit('!! EXTRUDE_ERR8') if m.waits == [module.SETTLE] else None
    m.runout()
    assert m.console == [PRESS % 'T1B']
    assert_kept_paused(m)
    assert m.commands().count(PUSH) == 0
    m.on_wait = lambda: None
    m.press_resume()
    assert_printing(m, 'T1B')


def test_bed_cut_during_the_failure_is_heated_back_before_the_print_resumes(tmp_path):
    m = printing(tmp_path)
    m.cut_heaters = True
    m.runout()
    commands = m.commands()
    assert commands.index('M140 S55.000') < commands.index(PUSH) < commands.index('M190 S55.000')
    assert commands.index('M190 S55.000') < m.events.index(('stock_resume',))
    assert m.data['heater_bed']['target'] == 55.
    assert m.paused() is False and tuple(m.position[:3]) == STOP and m.routes() == ('T1B',)
    assert m.data['extruder']['target'] == 200. and m.refusals == 0


def test_cancel_during_the_purge_stops_it_without_heating_again(tmp_path):
    m = printing(tmp_path)
    once(m, PUSH, lambda: m.fire('gcode:cancel'))
    m.runout()
    commands = m.commands()
    assert commands.count(PUSH) == 1 and m.count('stock_resume') == 0
    assert 'M104 S195.000' not in commands
    assert m.envelope.latched is False and m.position[1] == 273. and m.refusals == 0
    assert relay(m)['last']['reason'] == 'print_cancelled' and relay(m)['note'] is None
    assert_plain(m.console)


def test_disconnect_during_the_purge_sends_nothing_more(tmp_path):
    m = printing(tmp_path)
    marks = []
    once(m, PUSH, lambda: (m.fire('klippy:disconnect'), marks.append(len(m.events))))
    m.runout()
    after = [event[1].split()[0] for event in m.events[marks[0]:] if event[0] == 'gcode']
    assert set(after) <= {'M400', 'RESTORE_GCODE_STATE'}
    assert m.owner.down is True and m.count('stock_resume') == 0
    assert relay(m)['last']['reason'] == 'resume_invalidated'


def test_purge_longer_than_its_deadline_is_abandoned(tmp_path):
    m = printing(tmp_path)
    once(m, PUSH, lambda: setattr(m, 'now', m.now + module.RESUME_TIMEOUT))
    m.runout()
    assert m.console[-1] == REFUSED % 'purge trop longue'
    assert_kept_paused(m)
    assert m.commands().count(PUSH) == 1


def test_route_that_changes_during_the_purge_stops_it(tmp_path):
    m = printing(tmp_path)
    once(m, PUSH, lambda: m.unit('T1B').update(filament='D'))
    m.runout()
    assert m.console[-1] == REFUSED % 'le filament a bouge pendant la purge'
    assert_kept_paused(m)
    assert m.commands().count(PUSH) == 1


def test_head_that_empties_during_the_purge_stops_it(tmp_path):
    m = printing(tmp_path)
    once(m, PUSH, lambda: m.data[HEAD].update(filament_detected=False))
    m.runout()
    assert m.console[-1] == REFUSED % 'le filament a bouge pendant la purge'
    assert_kept_paused(m)


def test_stock_resume_that_leaves_the_pause_is_said(tmp_path):
    m = printing(tmp_path)
    m.resume_effective = False
    m.runout()
    assert m.console[-1] == REFUSED % 'la machine est restee en pause'
    assert m.paused() is True and m.count('stock_resume') == 1 and m.refusals == 0
    assert relay(m)['last']['reason'] == 'stock_resume_not_effective'
    assert m.owner.resume_run is None and m.owner.resuming is False and m.owner.flushed is False


def test_extruder_current_that_does_not_come_back_never_breaks_the_reload(tmp_path):
    """ADR-072: nothing of ours raises inside the T1A..T4D envelope."""
    m = printing(tmp_path)
    m.current_success = False
    m.runout()
    assert m.change.last_reload == {'tool': 'T1A', 'error': False, 'head': True, 'paused': True}
    assert m.console == [REFUSED % 'courant extrudeur non retabli']
    assert_kept_paused(m)
    assert m.commands().count(PUSH) == 0


def test_unreadable_sensor_never_breaks_the_reload(tmp_path):
    m = printing(tmp_path)
    m.data[SPOOL]['filament_detected'] = None
    m.runout()
    assert m.change.last_reload['error'] is False and m.count('stock_T') == 1
    assert m.paused() is True and m.envelope.latched is False and m.refusals == 0
    assert relay(m)['note'] is None and m.commands().count(PUSH) == 0


def test_reload_during_a_pause_with_a_loaded_head_and_no_error_is_not_a_failure(tmp_path):
    m = printing(tmp_path)
    m.pause_print()
    m.load_mode = 'quiet'
    m.action.box_state.Tnn_map = {'T1A': 'T1B'}
    m.run_script_from_command('T1A')
    assert m.count('stock_T') == 1 and m.console == [] and relay(m)['note'] is None
    assert m.paused() is True and m.commands().count(PUSH) == 0


def test_inline_reload_outside_a_refill_says_it_and_resume_recovers(tmp_path):
    m = printing(tmp_path)
    m.data[HEAD]['filament_detected'] = False
    m.pause_print()
    m.action.box_state.Tnn_map = {'T1A': 'T1B'}
    m.run_script_from_command('T1A')
    assert m.console == [PRESS % 'T1B']
    assert m.paused() is True and m.commands().count(PUSH) == 0
    assert m.routes() == ('T1B',) and m.tmc() == (PAUSED_CURRENT, PAUSED_CURRENT)
    assert m.owner.in_reload == m.owner.envelope == m.owner.moving == 0
    m.press_resume()
    assert_printing(m, 'T1B')


@pytest.mark.parametrize('state', ['printing', 'standby'])
def test_refill_outside_a_pause_touches_nothing(tmp_path, state):
    m = printing(tmp_path)
    m.data['print_stats']['state'] = state
    m.refill_mode = 'nothing'
    m.run_script_from_command('BOX_CHECK_MATERIAL_REFILL')
    assert m.commands() == ['BOX_CHECK_MATERIAL_REFILL'] and m.console == []
    assert m.count('stock_refill') == 1 and relay(m) == FRESH


# Installation of the relay hooks.

def test_disabled_module_leaves_every_stock_handler_in_place(tmp_path):
    m = ResumeMachine(tmp_path, enabled=False)
    assert relay(m) == dict(FRESH, installed=False)
    assert m.ready_gcode_handlers['RESUME'] == m.stock_resume
    assert m.ready_gcode_handlers['BOX_CHECK_MATERIAL_REFILL'] == m.stock_refill
    assert m.ready_gcode_handlers['BOX_RESUME_EXTRUDE'] == m.stock_flush
    assert m.change.reload == m.tool_reload and m.events == []


def test_machine_without_resume_fields_keeps_the_start_and_says_why(tmp_path):
    m = rec.Machine(tmp_path)
    status = relay(m)
    assert status['installed'] is False
    assert status['failure'] == 'virtual_sdcard_resume_fields_missing'
    assert m.owner.originals and m.owner.get_status()['installed'] is True


def test_relay_registration_failure_rolls_everything_back(tmp_path):
    m = ResumeMachine(tmp_path, install=False)
    before, m.fail_register = dict(m.ready_gcode_handlers), 'BOX_CHECK_MATERIAL_REFILL'
    with pytest.raises(RuntimeError, match='registration_failure'):
        m.owner._ready_resume()
    assert m.ready_gcode_handlers == before and m.change.reload == m.tool_reload
    assert m.owner.resume_hooks == {} and m.events == []
    hook(m)
    assert relay(m) == FRESH


def test_relay_install_twice_does_not_nest(tmp_path):
    m = printing(tmp_path)
    handlers, reload = dict(m.ready_gcode_handlers), m.change.reload
    m.owner._ready_resume()
    assert m.ready_gcode_handlers == handlers and m.change.reload == reload
    assert m.owner.resume_hooks['RESUME'] == m.stock_resume
    assert m.owner.resume_hooks['reload'] == m.tool_reload


# Pure functions.

@pytest.mark.parametrize('lines, target, before, head, tnn, expected', [
    ([key()], 'T1B', False, True, None, 'T1B'),
    ([key()], None, False, True, 'T1B', 'T1B'),
    ([], 'T1B', False, True, None, 'T1B'),
    ([key('key999', letter='D'), '!! not json', key('key837')], 'T1B', False, True, 'T1B', 'T1B'),
    ([], None, False, True, None, None),
    ([key()], 'T1B', True, True, None, None),
    ([key()], 'T1B', None, True, None, None),
    ([key()], 'T1B', False, False, None, None),
    ([key()], 'T1B', False, None, None, None),
    (None, 'T1B', False, True, None, None),
    ([key(), key(letter='D')], 'T1B', False, True, None, None),
    ([key()], 'T1D', False, True, None, None),
    ([key()], 'T1B', False, True, 'T1D', None),
    ([key(unit=9)], None, False, True, None, None),
    (['!! ' + json.dumps({'code': 'key836', 'values': ['1', 'B']})], None, False, True, None, None),
    (['!! ' + json.dumps({'code': 'key836', 'values': [True, 'B']})], None, False, True, None, None),
    (['!! ' + json.dumps(['key836', 1, 'B'])], None, False, True, None, None)])
def test_relay_slot_only_attributes_what_is_proven(lines, target, before, head, tnn, expected):
    assert module.relay_slot(lines, target, before, head, tnn) == expected


@pytest.mark.parametrize('line, fans, expected', [
    ('M107', 3, {0: 0, 2: 0}), ('M107', 1, {0: 0}), ('M107 P2', 3, {2: 0}),
    ('M107 P7', 3, {0: 0}), ('M106', 3, {0: 255}), ('m106 s128 ; layer', 3, {0: 128}),
    ('M106 P2 S127.6', 3, {2: 128}), ('M106 P7 S10', 3, {0: 10}), ('M106 S300', 3, {0: 255}),
    ('M106 S-4', 3, {0: 0}), ('G1 X1', 3, None), ('', 3, None), ('; M106 S9', 3, None)])
def test_fan_command_reads_the_file_like_the_stock_macros(line, fans, expected):
    assert module.fan_command(line, fans) == expected


@pytest.mark.parametrize('line', ['M106 P-1', 'M106 P1.5', 'M106 Snan', 'M106 Sx', 'M106 S'])
def test_fan_command_refuses_a_line_it_cannot_follow(line):
    with pytest.raises((ValueError, IndexError)):
        module.fan_command(line, 3)


@pytest.mark.parametrize('chunk', [1, 7, 64, module.FAN_CHUNK])
def test_file_fans_keeps_the_latest_command_of_each_fan(tmp_path, chunk):
    path, pauses = tmp_path / 'fans.gcode', []
    path.write_bytes((BODY + TAIL).encode())
    read = lambda position, **kwargs: module.file_fans(
        str(path), position, chunk=chunk, pause=lambda: pauses.append(1), **kwargs)
    assert read(len(BODY.encode())) == FANS
    assert read(len((BODY + 'G1 X30 Y30 E1\nM107\n').encode())) == {0: 0, 2: 0}
    assert read(len('START_PRINT\nT0\nM106 S255\n'.encode())) == {0: 255}
    assert read(0) == {} and pauses
    assert read(len(BODY.encode()), fans=1) == {0: 128}
    assert read(len(BODY.encode()), limit=40) == {0: 128}


def test_file_fans_gives_up_on_a_file_it_cannot_follow(tmp_path):
    path = tmp_path / 'fans.gcode'
    assert module.file_fans(str(path), 10) is None
    path.write_bytes(b'M106 S128\nM106 P-1 S4\n')
    assert module.file_fans(str(path), 22) is None
    assert module.file_fans(str(path), None) is None
    assert module.file_fans(str(path), 10) == {0: 128}


def test_every_console_sentence_is_plain_ascii_and_never_an_error_line():
    tree = ast.parse((PACKAGE / 'kctrl_start.py').read_text(encoding='utf-8'))
    texts = [node.value for node in ast.walk(tree)
             if isinstance(node, ast.Constant) and isinstance(node.value, str)
             and node.value.startswith('K1 Control')]
    assert len(texts) >= 12 and len(module.RESUME_HINTS) >= 30
    assert_plain(texts + list(module.RESUME_HINTS.values()))


# Adapted from the tranche 1 bench.

def test_every_earlier_start_test_is_rerun_on_this_module():
    earlier = {name for name in vars(res) if name.startswith('test_')}
    assert earlier - set(RERUN) == set(ADAPTED) and len(RERUN) == 76
    assert all(globals()[name] is value for name, value in RERUN.items())
    assert base.module is module and rec.module is module and res.module is module
    assert base.policy is policy and rec.policy is policy and res.policy is policy


def test_python38_grammar():
    ast.parse((PACKAGE / 'kctrl_start.py').read_text(encoding='utf-8'), feature_version=(3, 8))


def test_status_exposes_revision_recovery_head_rest_and_relay(tmp_path):
    m = rec.Machine(tmp_path)
    status = m.owner.get_status()
    assert status['revision'] == 'resilience-v2' == module.REVISION
    assert status['recovery'] is None and status['recovery_timeout'] == 180.
    assert status['head'] is None and status['head_saved'] is True and status['rest'] is None
    assert module.HEAD_STATE_FILE == '/usr/data/k1-control-v1/state/kctrl_head.json'
    assert m.owner.head_file == str(res.head_file(tmp_path))
    assert set(status['relay']) == {'installed', 'failure', 'note', 'last'}
    assert ResumeMachine(tmp_path).owner.get_status()['relay'] == FRESH
