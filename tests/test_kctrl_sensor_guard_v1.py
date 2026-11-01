"""CFS sensor guard V1 (ADR-077, document 105) on a fake Klipper with a simulated clock.

Every CFS line is synthetic: the shapes the stock module writes to the Klipper
log, without any identifier. The replays follow the timelines of document 105,
rounded to the second: the wrong ends of 15 September, 31 October and
1 November 2026, the real runouts of 13 September and 31 October (T1B), a
healthy print and a short false report. Actions due at a second run before the
guard's tick of that second; a check at x.5 sees the tick of x.
"""
import configparser
import contextlib
import heapq
import importlib.util
import itertools
import json
import logging
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'packages/k1-control-v1'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SG = load('kctrl_sensor_guard_v1_test', ROOT / 'cfs-sensor-guard-v1/kctrl_sensor_guard.py')
END = load('kctrl_end_v5_for_sensor_guard', ROOT / 'end-no-stock-flush-v5/kctrl_end.py')
PACKAGE = '_sensor_guard_test_package'
sys.modules[PACKAGE] = SimpleNamespace(__path__=[str(ROOT / 'cold-push-guard-v1')])
for name, folder in (('kctrl_start_policy', 'retained-start-v1'),
                     ('kctrl_purge_guard', 'cold-push-guard-v1')):
    load(PACKAGE + '.' + name, ROOT / folder / (name + '.py'))
ColdGuard = sys.modules[PACKAGE + '.kctrl_purge_guard'].KctrlPurgeGuard

OK, BUSY, ERR = 0x0, 0x30, 0x50
TENSION = 'filament_err_tighten_up_event'
HEADER = '[INFO] 2026-11-01 07:07:08,123 [x] [y] '
KEY839 = ('!! {"code":"key839", "msg":"filament error, no filament detected at box extrude '
          'position", "values": [1, "A"]}')
V5_PUSHES = [2., -20., -15., 1.5]
MISSING = object()


def hms(clock):
    hours, minutes, secs = (int(part) for part in clock.split(':'))
    return hours * 3600. + minutes * 60. + secs


def seconds(clock):
    return hms(clock) if isinstance(clock, str) else float(clock)


def reply(unit, status):
    return 'msg: 0xf7 0x%x 0x7 0x%x 0xa 0x0 0x0 0x0' % (unit, status)


def named(slot):
    return 'recode_err: filament_err, last_tnn: %s, tnn: %s' % (slot, slot)


def mask(unit, kind, value):
    return 'Tn_inner_data[T%d][filament_sensor][%s]: %d' % (unit, kind, value)


class CommandError(Exception):
    pass


class ConfigError(Exception):
    pass


class FakeReactor:
    NOW = 0.
    NEVER = 9999999999999999.

    def __init__(self, sim):
        self.sim = sim
        self.timers = []
        self.callbacks = []
        self.hold = False
        self.on_pause = None

    def monotonic(self):
        return self.sim.clock

    def register_timer(self, callback, waketime=NEVER):
        timer = SimpleNamespace(callback=callback, waketime=waketime)
        self.timers.append(timer)
        return timer

    def register_callback(self, callback, waketime=NOW):
        self.callbacks.append(callback)

    def pause(self, waketime):
        # A pause lets other work run in the real reactor: on_pause plays it once.
        hook, self.on_pause = self.on_pause, None
        if hook is not None:
            hook()
        self.sim.clock = max(self.sim.clock, waketime)
        return self.sim.clock


class Sim:
    """Timed actions and reactor timers on one clock. A string action is a log line."""

    def __init__(self, clock):
        self.clock = clock
        self.queue = []
        self.order = itertools.count()
        self.reactor = FakeReactor(self)

    def at(self, t, action):
        heapq.heappush(self.queue, (t, next(self.order), action))

    def every(self, start, end, step, action):
        t = start
        while t <= end:
            self.at(t, action)
            t += step

    def run_until(self, end):
        reactor = self.reactor
        while True:
            timers = [timer for timer in reactor.timers if timer.waketime < reactor.NEVER]
            timer = min(timers, key=lambda timer: timer.waketime, default=None)
            if self.queue and self.queue[0][0] <= end and (
                    timer is None or self.queue[0][0] <= timer.waketime):
                t, _, action = heapq.heappop(self.queue)
                self.clock = max(self.clock, t)
                if callable(action):
                    action()
                else:
                    logging.getLogger().info(action)
            elif timer is not None and timer.waketime <= end:
                self.clock = max(self.clock, timer.waketime)
                timer.waketime = timer.callback(self.clock)
            else:
                break
            self.run_callbacks()
        self.clock = max(self.clock, end)

    def run_callbacks(self):
        while self.reactor.callbacks and not self.reactor.hold:
            self.reactor.callbacks.pop(0)(self.clock)


class FakeGCode:
    """Klipper's dispatch as the guard uses it: registration, console, nested scripts, mutex."""

    def __init__(self):
        self.ready_gcode_handlers = {}
        self.descs = {}
        self.output_handlers = []
        self.responses = []
        self.mutex_held = False

    def register_command(self, cmd, func, when_not_ready=False, desc=None):
        if func is None:
            self.descs.pop(cmd, None)
            return self.ready_gcode_handlers.pop(cmd, None)
        if cmd in self.ready_gcode_handlers:
            raise ConfigError('gcode command %s already registered' % cmd)
        # Creality's parser cuts a command name at its first digit.
        assert not any(char.isdigit() for char in cmd), cmd
        self.ready_gcode_handlers[cmd] = func
        self.descs[cmd] = desc
        return None

    def register_output_handler(self, callback):
        self.output_handlers.append(callback)

    def respond_raw(self, msg):
        self.responses.append(msg)
        for callback in self.output_handlers:
            callback(msg)

    def respond_info(self, msg, log=True):
        if log:
            logging.info(msg)
        lines = [line.strip() for line in msg.strip().split('\n')]
        self.respond_raw('// ' + '\n// '.join(lines))

    def _respond_error(self, msg):
        logging.warning(msg)
        lines = msg.strip().split('\n')
        if len(lines) > 1:
            self.respond_info('\n'.join(lines), log=False)
        self.respond_raw('!! %s' % lines[0].strip())

    @contextlib.contextmanager
    def get_mutex(self):
        assert not self.mutex_held, 'the G-code mutex is not re-entrant'
        self.mutex_held = True
        try:
            yield
        finally:
            self.mutex_held = False

    def run_line(self, line, nested):
        words = line.split()
        cmd = words[0].upper()
        handler = self.ready_gcode_handlers.get(cmd)
        if handler is None:
            self.respond_info('Unknown command:"%s"' % cmd)
            return None
        try:
            handler(FakeGCmd(self, line, dict(word.split('=', 1) for word in words[1:])))
        except CommandError as error:
            self._respond_error(str(error))
            if nested:
                raise
            return error
        return None

    def run_script_from_command(self, script):
        # No mutex; an error prints '!!' and propagates.
        for line in script.split('\n'):
            if line.strip():
                self.run_line(line, nested=True)

    def dispatch(self, line):
        """A console line: under the mutex, an error is printed and returned."""
        with self.get_mutex():
            return self.run_line(line, nested=False)


class FakeGCmd:
    error = CommandError

    def __init__(self, gcode, line, params):
        self.gcode = gcode
        self.line = line
        self.params = params

    def get_commandline(self):
        return self.line

    def get(self, name, default=MISSING):
        value = self.params.get(name, default)
        if value is MISSING:
            raise CommandError('Error on "%s": missing %s' % (self.line, name))
        return value

    def get_int(self, name, default=MISSING, minval=None, maxval=None):
        return int(self.get(name, default))

    def respond_info(self, msg, log=True):
        self.gcode.respond_info(msg, log)


class FakePrinter:
    config_error = ConfigError
    command_error = CommandError

    def __init__(self, sim):
        self.reactor = sim.reactor
        self.objects = {}
        self.handlers = {}
        self.shutdown_calls = []
        self.in_shutdown = False

    def get_reactor(self):
        return self.reactor

    def lookup_object(self, name, default=MISSING):
        if name in self.objects:
            return self.objects[name]
        if default is MISSING:
            raise ConfigError("Unknown config object '%s'" % name)
        return default

    def register_event_handler(self, event, callback):
        self.handlers.setdefault(event, []).append(callback)

    def send_event(self, event, *params):
        return [callback(*params) for callback in self.handlers.get(event, [])]

    def invoke_shutdown(self, msg):
        self.shutdown_calls.append(msg)
        if self.in_shutdown:
            return
        self.in_shutdown = True
        for callback in self.handlers.get('klippy:shutdown', []):
            try:
                callback()
            except Exception:
                logging.exception('shutdown handler')


class FakeConfig:
    def __init__(self, printer, values):
        self.printer = printer
        self.values = values
        self.read = []

    def get_printer(self):
        return self.printer

    def _get(self, convert, name, default, minval=None, maxval=None):
        self.read.append((name, default))
        value = convert(self.values.get(name, default))
        if (minval is not None and value < minval) or (maxval is not None and value > maxval):
            raise ConfigError('option %s out of range' % name)
        return value

    def getboolean(self, name, default=MISSING):
        return self._get(bool, name, default)

    def getint(self, name, default=MISSING, minval=None, maxval=None):
        return self._get(int, name, default, minval, maxval)

    def getfloat(self, name, default=MISSING, minval=None, maxval=None):
        return self._get(float, name, default, minval, maxval)


class FakeBox:
    """The CFS object: its status and BOX_ENABLE_AUTO_REFILL, normal, inert or refusing."""

    def __init__(self, sim, gcode, events):
        self.sim = sim
        self.gcode = gcode
        self.events = events
        self.auto_refill = 1
        self.mode = 'normal'
        self.times = []
        self.locked = []
        self.units = {'T1': {'state': 'connect', 'filament': 'None'},
                      'T2': {'state': 'connect', 'filament': 'None'},
                      'T3': {'state': 'None'}, 'T4': {'state': 'None'}}
        gcode.register_command('BOX_ENABLE_AUTO_REFILL', self.cmd_BOX_ENABLE_AUTO_REFILL)

    def route(self, slot):
        for name in ('T1', 'T2'):
            self.units[name]['filament'] = 'None'
        if slot is not None:
            self.units[slot[:2]]['filament'] = slot[2]

    def get_status(self, eventtime=None):
        status = {'enable': 1, 'state': 'connect', 'auto_refill': self.auto_refill}
        status.update((name, dict(unit)) for name, unit in self.units.items())
        return status

    def cmd_BOX_ENABLE_AUTO_REFILL(self, gcmd):
        value = gcmd.get_int('ENABLE')
        self.events.append(('box', value))
        self.times.append(self.sim.clock)
        self.locked.append(self.gcode.mutex_held)
        if self.mode == 'raise':
            raise gcmd.error('auto refill write refused')
        if self.mode == 'normal':
            self.auto_refill = value


class FakePrintStats:
    def __init__(self):
        self.state = 'standby'
        self.filename = ''

    def get_status(self, eventtime):
        return {'state': self.state, 'filename': self.filename}


class FakeSd:
    def __init__(self):
        self.active = False
        self.file_path = None

    def is_active(self):
        return self.active

    def get_status(self, eventtime):
        return {'file_path': self.file_path, 'is_active': self.active}


class FakeHead:
    def __init__(self):
        self.detected = True

    def get_status(self, eventtime):
        return {'filament_detected': self.detected}


class FakeExtruder:
    def __init__(self):
        self.heater = SimpleNamespace(can_extrude=True, target_temp=220., min_extrude_temp=170.,
                                      smoothed_temp=220.)
        self.check_move = self.stock_check

    def stock_check(self, move):
        if abs(move.axes_d[3]) > 1000.:
            raise CommandError('Extrude only move too long')

    def get_heater(self):
        return self.heater


class FakeToolhead:
    """E grows at a flow rate; push() calls the extruder check as toolhead.move does for an E-only move."""

    def __init__(self, sim, extruder):
        self.sim = sim
        self.extruder = extruder
        self.kin = SimpleNamespace(check_move=lambda move: None)
        self.e = 0.
        self.rate = 0.
        self.since = sim.clock
        self.queued = []
        self.refused = []

    def position_e(self):
        return self.e + self.rate * (self.sim.clock - self.since)

    def flow(self, rate):
        self.e, self.rate, self.since = self.position_e(), rate, self.sim.clock

    def get_position(self):
        return [100., 100., 10., self.position_e()]

    def get_kinematics(self):
        return self.kin

    def get_extruder(self):
        return self.extruder

    def get_status(self, eventtime):
        return {'homed_axes': 'xyz'}

    def try_push(self, mm):
        e = self.position_e()
        move = SimpleNamespace(start_pos=[100., 100., 10., e], end_pos=[100., 100., 10., e + mm],
                               axes_d=[0., 0., 0., mm])
        try:
            self.extruder.check_move(move)
        except CommandError as error:
            self.refused.append((mm, str(error)))
            return
        self.e += mm
        self.queued.append(mm)


class FakeEnd:
    """kctrl_end V5 as the guard reads it: enabled, phase, inflight, its START_PRINT, its console check."""

    def __init__(self, printer, gcode):
        self.printer = printer
        self.gcode = gcode
        self.enabled = True
        self.phase = 'idle'
        self.inflight = False
        self.command_error = ''
        self.proof = None
        self.starts = 0
        self.original = None
        printer.register_event_handler('klippy:ready', self._ready)
        printer.register_event_handler('klippy:shutdown', self._shutdown)

    def _ready(self):
        self.original = self.gcode.register_command('START_PRINT', None)
        self.gcode.register_command('START_PRINT', self.start)
        self.gcode.register_output_handler(self._output)

    def _output(self, text):
        END.KctrlEnd._output(self, text)

    def start(self, gcmd):
        if self.inflight:
            raise gcmd.error('K1 Control: finalisation encore en cours')
        self.starts += 1
        self.phase, self.command_error = 'idle', ''
        self.original(gcmd)

    def _shutdown(self):
        if self.phase in END.ACTIVE:
            self.phase = 'shutdown'


class World:
    """A K1 with two CFS, the V5 end, the cold guard and the sensor guard, created in `order`."""

    def __init__(self, clock, order=('end', 'cold', 'guard'), **values):
        self.sim = Sim(clock)
        self.events = []
        self.printer = FakePrinter(self.sim)
        self.gcode = self.printer.objects['gcode'] = FakeGCode()
        self.print_stats = FakePrintStats()
        self.sd = FakeSd()
        self.extruder = FakeExtruder()
        self.toolhead = FakeToolhead(self.sim, self.extruder)
        self.head = FakeHead()
        self.box = FakeBox(self.sim, self.gcode, self.events)
        self.stock_fail = False
        self.gcode.register_command('START_PRINT', self.stock_start)
        self.printer.objects.update({
            'print_stats': self.print_stats, 'virtual_sdcard': self.sd, 'box': self.box,
            'toolhead': self.toolhead, 'extruder': self.extruder,
            'filament_switch_sensor filament_sensor_2': self.head,
            'heaters': SimpleNamespace(turn_off_all_heaters=lambda: self.events.append(('heat_off',)))})
        self.end = self.cold = self.guard = self.config = None
        for item in order:
            if item == 'end':
                self.end = self.printer.objects['kctrl_end'] = FakeEnd(self.printer, self.gcode)
            elif item == 'cold':
                self.cold = self.printer.objects['kctrl_purge_guard'] = ColdGuard(
                    SimpleNamespace(get_printer=lambda: self.printer))
            else:
                self.config = FakeConfig(self.printer, dict({'enabled': True}, **values))
                self.guard = self.printer.objects['kctrl_sensor_guard'] = SG.load_config(self.config)

    def ready(self):
        self.printer.send_event('klippy:ready')

    def stock_start(self, gcmd):
        self.events.append(('stock_start',))
        if self.stock_fail:
            raise gcmd.error('stock start refused')

    def begin(self, route='T1A', rate=5.):
        self.sd.active, self.sd.file_path = True, 'test.gcode'
        self.print_stats.state, self.print_stats.filename = 'printing', 'test.gcode'
        self.box.route(route)
        self.head.detected = True
        self.toolhead.flow(rate)
        error = self.gcode.dispatch('START_PRINT')
        if error is not None:
            # virtual_sdcard stops the file on a command error.
            self.finish('error')
        return error

    def pause(self, head=True):
        self.print_stats.state = 'paused'
        self.sd.active = False
        self.head.detected = head
        self.toolhead.flow(0.)

    def resume(self, rate):
        self.print_stats.state = 'printing'
        self.sd.active = True
        self.toolhead.flow(rate)

    def finish(self, state='complete'):
        self.sd.active, self.sd.file_path = False, None
        self.print_stats.state = state
        self.toolhead.flow(0.)

    def phase(self, name):
        self.end.phase = name

    def cool(self, temp):
        heater = self.extruder.heater
        heater.target_temp, heater.smoothed_temp = 0., temp
        heater.can_extrude = temp >= heater.min_extrude_temp

    def at(self, clock, *actions):
        for action in actions:
            self.sim.at(seconds(clock), action)

    def every(self, start, end, step, line):
        self.sim.every(seconds(start), seconds(end), step, line)

    def run(self, clock):
        self.sim.run_until(seconds(clock))

    def said(self, text):
        return [line for line in self.gcode.responses if text in line]


def started(clock='09:59:59', order=('end', 'cold', 'guard'), **values):
    world = World(hms(clock), order, **values)
    world.ready()
    return world


def ended(state='complete', **values):
    world = started(**values)
    world.begin()
    world.run('10:00:10')
    world.finish(state)
    world.run('10:00:11')
    return world


def suspect(world, clock='10:00:00', until='10:20:00'):
    """A print whose live slot answers FILAMENT_ERR from +10 s: marked at +190 s with 905 mm."""
    world.at(clock, lambda: world.begin('T1A', 5.))
    world.every(seconds(clock) + 10, until, 4, reply(1, ERR))


def v5_end(world, clock):
    """The owned end as the guard sees it: its phases and its own pushes."""
    start = seconds(clock)
    world.at(start, world.finish, lambda: world.phase('waiting'))
    world.at(start + 1, lambda: world.phase('heating'))
    world.at(start + 5, lambda: world.phase('cutting'),
             lambda: setattr(world.end, 'proof', END.CutProof()))
    world.at(start + 6, lambda: world.toolhead.try_push(2.))
    world.at(start + 15, lambda: world.phase('rewinding'))
    world.at(start + 16, lambda: world.toolhead.try_push(-20.))
    world.at(start + 20, lambda: world.toolhead.try_push(-15.))
    world.at(start + 30, lambda: world.phase('finalizing'))
    world.at(start + 31, lambda: world.toolhead.try_push(1.5))
    world.at(start + 44, lambda: world.phase('complete'))


def assert_quiet(world, allowed=()):
    """No console line can fail the owned end: no '!!', no 'failed'."""
    for line in world.gcode.responses:
        if line not in allowed:
            assert not line.startswith('!!') and 'failed' not in line.lower(), line


@pytest.fixture(autouse=True)
def root_logger():
    # The printer logs at INFO; pytest leaves the root logger at WARNING.
    root = logging.getLogger()
    level = root.level
    root.setLevel(logging.INFO)
    yield root
    for handler in list(root.handlers):
        if getattr(handler, 'kctrl_sensor_tap', False):
            root.removeHandler(handler)
    root.setLevel(level)


# Lines read from the log.

@pytest.mark.parametrize('line, event', [
    (reply(1, ERR), ('reply', 'T1', ERR)),
    (reply(2, OK), ('reply', 'T2', OK)),
    (reply(1, BUSY), ('reply', 'T1', BUSY)),
    ('msg: 0xf7 0x4 0x7 0x50 0xa', ('reply', 'T4', ERR)),
    (HEADER + reply(1, ERR), ('reply', 'T1', ERR)),
    (named('T1A'), ('named', 'T1A')),
    ("error: filament_err, {'tnn': 'T2C', 'last_tnn': 'T1A'}", ('named', 'T2C')),
    (TENSION, ('tension',)),
    (HEADER + TENSION, ('tension',)),
    (mask(1, 'connections', 1), ('mask', 'T1', 'connections', 1)),
    (HEADER + mask(2, 'material', 15), ('mask', 'T2', 'material', 15)),
    ('extrude = 120', ('tail', 120.)),
    (HEADER + 'extrude = -2.5  ', ('tail', -2.5)),
])
def test_parse_reads_each_cfs_line_shape(line, event):
    assert SG.parse(line) == event


@pytest.mark.parametrize('line', [
    'msg: 0xf7 0x1 0x7 0x50 0xb 0x0',
    'msg: 0xf7 0x1 0x19 0x50 0xa 0x0',
    'msg: 0xf7 0x0 0x7 0x50 0xa 0x0',
    'msg: 0xf7 0x5 0x7 0x50 0xa 0x0',
    'msg: 0xf7 0x1 0x7 0x50',
    'recode_err: filament_err',
    'error: filament_err',
    'Tn_inner_data[T5][filament_sensor][material]: 8',
    'Tn_inner_data[T1][filament_sensor][material]: 8 extra',
    '[buffer] extrude = 10',
    'extrude = 10, velocity = 5',
    'extrude = 10 mm',
    '[INFO] header without its fields msg: 0xf7 0x1 0x7 0x50 0xa',
    'K1 Control: capteur du slot T1A contredit',
    '',
])
def test_parse_rejects_every_other_line(line):
    assert SG.parse(line) is None


def test_the_tap_keeps_events_of_every_line_and_counts_what_it_drops():
    tap = SG.LineTap(lambda: 5., size=2)
    tap.emit(logging.LogRecord('box', logging.INFO, __file__, 1, '%s\n%s\nnoise',
                               (reply(1, ERR), TENSION), None))
    assert tap.drain() == [(5., ('reply', 'T1', ERR)), (5., ('tension',))]
    for line in (reply(1, OK), reply(2, OK), mask(1, 'material', 8)):
        tap.emit(logging.LogRecord('box', logging.INFO, __file__, 1, line, None, None))
    assert tap.seen == 5 and tap.dropped == 1
    assert tap.drain() == [(5., ('reply', 'T2', OK)), (5., ('mask', 'T1', 'material', 8))]
    assert tap.drain() == []


def test_the_tap_never_raises():
    tap = SG.LineTap(lambda: 5.)
    tap.emit(logging.LogRecord('box', logging.INFO, __file__, 1, '%d', ('x',), None))
    tap.handleError(None)
    assert tap.drain() == []


# Route, with the rules of the V5 end.

def box(**units):
    status = {'enable': 1, 'state': 'connect',
              'T1': {'state': 'connect', 'filament': 'None'},
              'T2': {'state': 'connect', 'filament': 'None'},
              'T3': {'state': 'None'}, 'T4': {'state': 'None'}}
    status.update(units)
    return status


@pytest.mark.parametrize('status, boxes, expected', [
    (box(), 2, (None, 'no_route')),
    (box(T1={'state': 'connect', 'filament': 'A'}), 2, ('T1A', '')),
    (box(T2={'state': 'connect', 'filament': 'D'}), 2, ('T2D', '')),
    (dict(box(), enable=0), 2, (None, 'cfs_not_ready')),
    (dict(box(), state='disconnect'), 2, (None, 'cfs_not_ready')),
    (box(T2={'state': 'disconnect', 'filament': 'None'}), 2, (None, 'cfs_unit_missing')),
    (box(T2=None), 2, (None, 'cfs_unit_missing')),
    (box(T3={'state': 'connect', 'filament': 'None'}), 2, (None, 'unexpected_cfs_unit')),
    (box(T3={}), 2, (None, 'no_route')),
    (box(T3={'state': 'disconnect'}), 2, (None, 'no_route')),
    (box(T1={'state': 'connect', 'filament': 'E'}), 2, (None, 'cfs_route_unknown')),
    (box(T1={'state': 'connect'}), 2, (None, 'cfs_route_unknown')),
    (box(T1={'state': 'connect', 'filament': 'A'}, T2={'state': 'connect', 'filament': 'B'}), 2,
     (None, 'cfs_routes_ambiguous')),
    (box(T1={'state': 'connect', 'filament': 'C'}), 1, (None, 'unexpected_cfs_unit')),
    (box(T1={'state': 'connect', 'filament': 'C'}, T2={'state': 'None'}), 1, ('T1C', '')),
])
def test_the_route_follows_the_v5_end_rules(status, boxes, expected):
    assert SG.engaged_route(status, boxes) == expected
    try:
        route = END.live_route(status, boxes)
    except END.EndRefused as error:
        assert expected == (None, str(error))
    else:
        assert expected == ((route, '') if route else (None, 'no_route'))


@pytest.mark.parametrize('status, reason', [
    (None, 'cfs_not_ready'), ('box', 'cfs_not_ready'), ([], 'cfs_not_ready'),
    (dict(box(), enable='1'), 'cfs_not_ready'), (box(T3='connect'), 'unexpected_cfs_unit')])
def test_the_route_never_raises_on_an_odd_status(status, reason):
    assert SG.engaged_route(status) == (None, reason)


# Episodes, without Klipper: one tick a second.

class Feed:
    """SensorWatch alone: one tick a second, E growing at rate while printing."""

    def __init__(self, route='T1A', rate=5.):
        self.watch = SG.SensorWatch()
        self.route = route
        self.rate = rate
        self.e = 0.
        self.now = -1.
        self.printing = True
        self.head = True
        self.listening = True
        self.out = []

    def tick(self, *events):
        self.now += 1.
        if self.printing:
            self.e += self.rate
        self.out += self.watch.tick(self.now, self.printing, self.route, self.head, self.e,
                                    [(self.now, event) for event in events], self.listening)

    def run(self, count, *events):
        for _ in range(count):
            self.tick(*events)


def test_a_material_mask_alone_opens_a_suspect_episode_that_marks():
    # 31 October: the mask said A missing while T1A printed.
    feed = Feed(rate=3.)
    for second in range(181):
        events = [('reply', 'T1', OK)] if second % 4 == 0 else []
        if second % 5 == 0:
            events.append(('mask', 'T1', 'material', 8))
        feed.tick(*events)
        if second == 179:
            assert feed.watch.marked is None
    episode = feed.watch.episodes['T1A']
    assert not episode['real'] and episode['reasons'] == {'material'} and episode['start'] == 0.
    assert feed.watch.marked['at'] == 180. and feed.out == [('mark', feed.watch.marked)]


def test_a_connections_mask_without_the_slot_makes_the_episode_real():
    feed = Feed()
    feed.tick(('reply', 'T1', ERR))
    feed.run(9)
    feed.tick(('mask', 'T1', 'connections', 1))
    assert not feed.watch.episodes['T1A']['real']
    feed.tick(('mask', 'T1', 'connections', 2))
    episode = feed.watch.episodes['T1A']
    assert episode['real'] and episode['real_at'] == 11.
    feed.run(300, ('reply', 'T1', ERR))
    assert feed.watch.marked is None


def test_a_connections_mask_older_than_the_episode_proves_nothing():
    feed = Feed()
    feed.tick(('mask', 'T1', 'connections', 0))
    feed.run(20)
    feed.tick(('reply', 'T1', ERR))
    assert not feed.watch.episodes['T1A']['real']


def test_the_tail_line_alone_makes_the_live_route_real():
    feed = Feed()
    feed.run(5)
    feed.tick(('tail', 120.))
    episode = feed.watch.episodes['T1A']
    assert episode['real'] and episode['real_at'] == 5. and episode['reasons'] == {'tail'}


@pytest.mark.parametrize('head', [False, None])
def test_a_head_without_filament_or_unread_blocks_the_mark(head):
    feed = Feed()
    feed.head = head
    feed.run(300, ('reply', 'T1', ERR))
    assert feed.watch.marked is None
    feed.head = True
    feed.tick(('reply', 'T1', ERR))
    assert feed.watch.marked['at'] == 300.


def test_a_log_level_above_info_blinds_the_watch_and_is_told_once():
    feed = Feed()
    feed.tick(('reply', 'T1', ERR))
    feed.listening = False
    feed.run(300)
    assert feed.watch.marked is None and feed.watch.blind == 'log_level'
    assert feed.out == [('blind', 'log_level')]
    feed.listening = True
    feed.tick(('reply', 'T1', ERR))
    assert feed.watch.blind is None and feed.watch.marked['at'] == 301.


def test_a_silent_route_blinds_the_watch_until_its_next_reply():
    feed = Feed()
    feed.tick(('reply', 'T1', ERR))
    feed.run(60)
    assert feed.watch.blind is None
    feed.run(180)
    assert feed.watch.blind == 'no_cfs_reply' and feed.watch.marked is None
    assert feed.out == [('blind', 'no_cfs_reply')]
    feed.tick(('reply', 'T1', ERR))
    assert feed.watch.blind is None and feed.watch.marked['at'] == 241.


def test_printed_counts_while_printing_at_high_water_with_a_step_cap():
    watch = SG.SensorWatch()
    steps = [(True, 0.), (True, 10.), (True, 5.), (True, 12.), (True, 400.), (True, 100.),
             (True, 150.), (False, 300.), (True, 310.), (True, 320.)]
    for second, (printing, e) in enumerate(steps):
        events = [(0., ('reply', 'T1', ERR))] if second == 0 else []
        watch.tick(float(second), printing, 'T1A', True, e, events)
    # +10, a retraction and its recovery once (+2), a jump capped (+100), a drop
    # re-baselines, +50, a pause re-baselines, +10.
    assert watch.episodes['T1A']['printed'] == 172.


def test_a_short_false_report_closes_without_a_mark():
    feed = Feed()
    for second in range(200):
        status = ERR if second in (0, 4, 8) else OK if second >= 12 and second % 4 == 0 else None
        feed.tick(*([('reply', 'T1', status)] if status is not None else []))
        if second == 23:
            assert 'T1A' in feed.watch.episodes
    assert feed.watch.episodes == {} and feed.watch.closed == 1 and feed.watch.marked is None


def test_reset_forgets_real_episodes_and_restarts_suspect_ones():
    feed = Feed()
    feed.tick(('reply', 'T1', ERR), ('named', 'T2C'), ('mask', 'T2', 'connections', 0))
    assert feed.watch.episodes['T2C']['real'] and not feed.watch.episodes['T1A']['real']
    feed.run(200, ('reply', 'T1', ERR))
    assert feed.watch.marked is not None
    feed.watch.reset(500.)
    assert feed.watch.episodes == {'T1A': {'start': 500., 'last': 500., 'reasons': {'carried'},
                                           'real': False, 'real_at': None, 'printed': 0.}}
    assert feed.watch.marked is None and feed.watch.job_start == 500.


def test_reports_logged_before_the_job_are_ignored():
    watch = SG.SensorWatch()
    watch.tick(0., True, 'T1A', True, 0., [])
    watch.reset(100.)
    old = [(99., ('reply', 'T1', ERR)), (99., ('named', 'T1A')), (99., ('tension',)),
           (99., ('tail', 10.))]
    watch.tick(101., True, 'T1A', True, 5., old)
    assert watch.episodes == {}


def test_an_episode_never_starts_before_its_job():
    # A runout proven in the previous job must not prove the next one.
    feed = Feed()
    feed.tick(('mask', 'T1', 'material', 8))
    feed.run(6)
    feed.tick(('mask', 'T1', 'material', 8))
    feed.run(7)
    feed.tick(('mask', 'T1', 'material', 8), ('mask', 'T1', 'connections', 0))
    assert feed.watch.episodes['T1A']['real'] and feed.now == 15.
    feed.run(4)
    feed.watch.reset(20.)
    feed.tick()
    episode = feed.watch.episodes['T1A']
    assert episode['start'] == 20. and not episode['real']


def test_a_stale_material_mask_neither_lacks_nor_backdates():
    feed = Feed()
    for second in range(41):
        events = [('reply', 'T1', OK)] if second and second % 4 == 0 else []
        if second in (0, 40):
            events.append(('mask', 'T1', 'material', 8))
        feed.tick(*events)
        if second == 30:
            assert 'T1A' in feed.watch.episodes
        elif second == 31:
            assert 'T1A' not in feed.watch.episodes
    assert feed.watch.episodes['T1A']['start'] == 40.


# Replays of the real ends, with the guard installed.

def test_31_october_t1a_is_marked_and_the_stock_push_after_the_end_is_stopped():
    world = started('18:26:59')
    guard = world.guard
    world.at('18:27:34', lambda: world.begin('T1B', 6.4))
    world.every('18:27:34', '19:10:24', 4, reply(2, OK))
    world.every('18:27:36', '18:55:28', 4, reply(1, OK))
    world.at('18:56:02', reply(1, BUSY))
    world.every('18:56:06', '18:56:57', 4, reply(1, ERR))
    world.at('18:56:06', named('T1B'))
    world.at('18:56:07', TENSION)
    world.every('18:56:09', '18:56:34', 5, mask(1, 'connections', 2))
    world.at('18:56:39', mask(1, 'connections', 0), 'extrude = 120')
    world.every('18:56:57', '19:01:19', 5, mask(1, 'material', 9))
    world.every('18:57:01', '19:01:17', 4, reply(1, OK))
    world.at('19:00:56', lambda: world.pause(head=False))
    world.at('19:01:06', mask(1, 'connections', 0), mask(2, 'connections', 0),
             mask(2, 'material', 15), lambda: world.box.route(None))
    world.at('19:01:24', lambda: world.box.route('T1A'), lambda: world.toolhead.flow(2.6))
    world.at('19:01:25', reply(1, BUSY))
    world.every('19:01:26', '19:07:33', 5, mask(1, 'material', 8))
    world.at('19:02:10', lambda: world.toolhead.flow(0.),
             lambda: setattr(world.head, 'detected', True))
    world.every('19:02:18', '19:02:54', 4, reply(1, ERR))
    world.at('19:02:18', named('T1A'))
    world.at('19:02:59', named('T1A'))
    world.at('19:03:01', reply(1, OK))
    world.every('19:03:06', '19:10:24', 6, reply(1, ERR))
    world.at('19:04:31', lambda: world.resume(6.4))
    world.at('19:07:32', world.finish, lambda: world.phase('waiting'))
    world.at('19:07:33', lambda: world.phase('heating'))
    world.at('19:07:35', lambda: world.phase('cutting'),
             lambda: setattr(world.end, 'proof', END.CutProof()))
    world.at('19:07:36', lambda: world.gcode.respond_raw(KEY839), named('T1A'))
    world.at('19:07:42', lambda: world.phase('failed'), lambda: world.cool(159.))
    world.at('19:08:17', lambda: world.toolhead.try_push(80.))

    def t1b_runout_proven():
        episode = guard.watch.episodes['T1B']
        assert episode['real'] and episode['real_at'] == hms('18:56:39')
        assert episode['real_at'] - episode['start'] == 33.

    def t1a_still_suspect():
        episode = guard.watch.episodes['T1A']
        assert episode['start'] == hms('19:01:26') and not episode['real']
        assert guard.watch.marked is None

    world.at(hms('18:57:00') + .5, t1b_runout_proven)
    world.at(hms('19:05:32') + .5, t1a_still_suspect)
    world.run('19:10:30')

    marked = guard.watch.marked
    assert marked['slot'] == 'T1A' and marked['reasons'] == ['filament_err', 'material', 'named']
    assert hms('19:05:33') <= marked['at'] <= hms('19:05:35')
    assert 247. <= marked['seconds'] <= 249. and 400. <= marked['printed'] <= 407.
    assert world.said('contredit') == ['// ' + SG.MARK_MESSAGE % (
        'T1A', 248, 403, SG.MARK_OUTCOMES['confirmed'])]
    assert guard.cut == 'confirmed' and world.box.auto_refill == 0
    assert world.box.times == [marked['at']] and world.box.locked == [True]
    assert guard.trip == {'at': hms('19:08:17'), 'push': 80., 'level': 80., 'phase': 'failed'}
    assert world.toolhead.queued == [] and world.toolhead.refused == [(80., SG.TRIP_MESSAGE)]
    assert world.printer.shutdown_calls == [SG.TRIP_MESSAGE] and world.cold.cold_refused == 0
    assert len(world.said('garde de fin active 15 min')) == 1
    assert_quiet(world, allowed=(KEY839,))


def one_november(world, pushes=(('07:14:08', 80.),), cutting=None):
    world.at('06:30:00', lambda: world.begin('T1A', 4.4))
    world.every('06:30:00', '07:07:04', 4, reply(1, OK))
    world.every('06:30:02', '07:14:08', 4, reply(2, OK))
    world.every('07:07:08', '07:07:40', 4, reply(1, ERR))
    world.every('07:07:10', '07:14:03', 5, mask(1, 'connections', 1))
    world.at('07:07:46', reply(1, BUSY))
    world.at('07:07:50', reply(1, BUSY))
    world.every('07:07:55', '07:14:07', 4, reply(1, ERR))
    world.at('07:13:52', world.finish, lambda: world.phase('waiting'))
    world.at('07:13:53', lambda: world.phase('heating'))
    world.at('07:13:54', named('T1A'))
    if cutting:
        world.at(cutting, lambda: world.phase('cutting'))
    for clock, mm in pushes:
        world.at(clock, lambda mm=mm: world.toolhead.try_push(mm))
    world.run('07:15:00')
    return world


def test_1_november_marks_after_180_s_and_stops_the_stock_push_while_heating():
    world = one_november(started('06:29:59'))
    marked = world.guard.watch.marked
    assert marked['at'] == hms('07:10:08') and marked['seconds'] == 180.
    assert marked['printed'] == pytest.approx(181 * 4.4)
    assert world.guard.cut == 'confirmed' and world.box.auto_refill == 0
    assert world.guard.trip['phase'] == 'heating' and world.toolhead.queued == []
    assert world.printer.shutdown_calls == [SG.TRIP_MESSAGE]
    assert_quiet(world)


def test_1_november_small_pushes_trip_past_one_net_millimetre():
    world = one_november(started('06:29:59'),
                         pushes=[('07:14:08', .5), ('07:14:09', .5), ('07:14:10', .5)])
    assert world.toolhead.queued == [.5, .5] and world.guard.trip['level'] == 1.5


def test_1_november_a_stock_push_during_the_cut_is_not_seen():
    # Documented limit: the owned cut may push, so the window lets it through.
    world = one_november(started('06:29:59'), cutting='07:14:00')
    assert world.toolhead.queued == [80.] and not world.guard.tripped


def test_15_september_marks_on_the_contradicted_slot_and_trips_after_the_owned_end():
    world = started('03:29:59')
    world.at('03:30:00', lambda: world.begin('T1A', 4.))
    world.every('03:30:02', '03:45:54', 4, reply(1, OK))
    world.at('03:45:58', reply(1, ERR), named('T1A'))
    world.at('03:45:59', TENSION)
    world.every('03:46:00', '03:55:00', 5, mask(1, 'connections', 1))
    world.every('03:46:02', '04:00:02', 4, reply(1, OK))
    world.every('04:00:10', '12:03:16', 10, reply(1, OK))
    world.every('03:30:00', '12:05:30', 10, reply(2, OK))
    v5_end(world, '12:03:16')
    for clock in ('12:04:05', '12:04:45', '12:05:25'):
        world.at(clock, lambda: world.toolhead.try_push(80.))
    world.run('12:06:00')
    guard = world.guard
    assert guard.watch.marked['at'] == hms('03:48:58') and guard.cut == 'confirmed'
    assert guard.watch.closed == 1 and guard.watch.episodes == {}
    assert world.toolhead.queued == V5_PUSHES
    assert guard.trip['at'] == hms('12:04:05') and guard.trip['phase'] == 'complete'
    assert world.toolhead.refused == [(80., SG.TRIP_MESSAGE)] * 3
    assert world.printer.shutdown_calls == [SG.TRIP_MESSAGE]
    assert world.end.command_error == '' and not world.end.proof.failed
    assert_quiet(world)


@pytest.mark.parametrize('route, proven', [('T1B', '12:33:04'), ('T1A', '12:31:44')])
def test_13_september_a_real_runout_is_proven_and_never_marked(route, proven):
    world = started('11:59:59')
    world.at('12:00:00', lambda: world.begin(route, 5.))
    world.every('12:00:00', '12:31:40', 4, reply(1, OK))
    world.every('12:00:02', '12:50:00', 4, reply(2, OK))
    world.at('12:31:43', TENSION)
    world.every('12:31:43', '12:33:39', 4, reply(1, ERR))
    world.every('12:33:43', '12:50:00', 4, reply(1, OK))
    world.every('12:31:44', '12:32:59', 5, mask(1, 'connections', 2))
    world.at('12:33:04', mask(1, 'connections', 0))
    world.every('12:33:43', '12:48:48', 5, mask(1, 'material', 9))

    def proof():
        episode = world.guard.watch.episodes[route]
        assert episode['real'] and episode['real_at'] == hms(proven)
        assert episode['start'] == hms('12:31:43')

    world.at(hms(proven) + .5, proof)
    world.run('12:50:00')
    assert world.guard.watch.marked is None and world.box.times == []


def test_a_healthy_print_and_its_owned_end_leave_no_trace():
    world = started('09:59:59')
    guard = world.guard
    world.at('10:00:00', lambda: world.begin('T1A', 5.))
    world.every('10:00:00', '10:45:00', 4, reply(1, OK))
    world.every('10:00:02', '10:45:00', 4, reply(2, OK))
    v5_end(world, '10:28:00')

    def window_still_open():
        assert guard.window is not None and guard.armed

    world.at(hms('10:43:42') + .5, window_still_open)
    world.run('10:45:00')
    assert guard.watch.marked is None and guard.watch.episodes == {} and guard.watch.blind is None
    assert guard.cut is None and world.box.times == [] and not guard.tripped
    assert world.toolhead.queued == V5_PUSHES
    assert guard.window is None and guard.closed_by == 'expired' and not guard.armed
    assert len(world.said('garde de fin active 15 min')) == 1
    assert world.end.command_error == '' and not world.end.proof.failed
    assert_quiet(world)


# The cut of the auto refill.

def test_the_cut_runs_under_the_mutex_is_proven_by_reads_and_is_said_once():
    world = started()
    suspect(world)
    world.run('10:05:00')
    guard = world.guard
    assert guard.watch.marked['at'] == hms('10:03:10') and guard.cut == 'confirmed'
    assert world.box.auto_refill == 0 and guard.refill_pending
    assert world.box.times == [hms('10:03:10')] and world.box.locked == [True]
    assert world.said('contredit') == ['// ' + SG.MARK_MESSAGE % (
        'T1A', 180, 905, SG.MARK_OUTCOMES['confirmed'])]


def test_an_unconfirmed_cut_is_retried_while_the_refill_reads_1():
    world = started()
    world.box.mode = 'inert'
    suspect(world)
    world.run('10:04:00')
    guard = world.guard
    times = world.box.times
    assert guard.cut == 'unconfirmed' and world.box.auto_refill == 1 and guard.refill_pending
    assert len(times) >= 3 and all(b - a >= SG.RECUT_SECONDS for a, b in zip(times, times[1:]))
    assert guard.recuts == len(times) - 1
    assert len(world.said(SG.MARK_OUTCOMES['unconfirmed'])) == 1
    assert len(world.said(SG.RECUT_MESSAGE)) == 1


def test_a_refill_already_off_is_left_alone_and_not_restored():
    world = started()
    world.box.auto_refill = 0
    suspect(world)
    world.run('10:05:00')
    assert world.guard.cut == 'already' and not world.guard.refill_pending
    assert world.said(SG.MARK_OUTCOMES['already'])
    world.finish()
    world.run('10:05:05')
    assert world.begin() is None
    assert world.box.times == [] and world.box.auto_refill == 0


def test_a_cut_reached_after_the_end_began_is_left_to_the_owned_end():
    world = started()
    reactor = world.sim.reactor
    suspect(world)
    world.at(hms('10:03:09') + .5, lambda: setattr(reactor, 'hold', True))
    world.at('10:03:11', lambda: world.phase('waiting'), lambda: setattr(reactor, 'hold', False))
    world.run('10:04:00')
    assert world.guard.cut == 'end' and world.box.times == [] and world.box.auto_refill == 1
    assert world.said(SG.MARK_OUTCOMES['end'])


def test_a_refused_cut_neither_counts_nor_speaks_again_and_needs_no_restore():
    world = started()
    world.box.mode = 'raise'
    suspect(world)
    world.run('10:04:00')
    guard = world.guard
    assert guard.cut == 'error' and guard.recuts == 0 and guard.failure.startswith('cut: ')
    assert len(world.box.times) >= 3
    assert len(world.said('contredit')) == 1 and world.said(SG.MARK_OUTCOMES['error'])
    assert not world.said(SG.RECUT_MESSAGE)
    assert_quiet(world, allowed=('!! auto refill write refused',))
    world.finish()
    world.run('10:04:05')
    world.box.mode = 'normal'
    del world.events[:]
    assert world.begin() is None
    assert world.events == [('stock_start',)] and not guard.refill_pending


def test_a_recut_waits_ten_seconds_and_is_said_once():
    world = started()
    suspect(world)
    for clock in ('10:03:12', '10:03:30', '10:03:31', '10:03:50'):
        world.at(clock, lambda: setattr(world.box, 'auto_refill', 1))
    world.run('10:04:30')
    times = world.box.times
    assert times[0] == hms('10:03:10') and len(times) == 4
    assert all(b - a >= SG.RECUT_SECONDS for a, b in zip(times, times[1:]))
    assert world.box.auto_refill == 0 and world.guard.cut == 'confirmed'
    assert world.guard.recuts == 3 and len(world.said(SG.RECUT_MESSAGE)) == 1


def test_no_recut_once_the_end_began():
    world = started()
    suspect(world, until='10:03:40')
    world.at('10:03:30', lambda: world.phase('waiting'))
    world.at('10:03:31', lambda: setattr(world.box, 'auto_refill', 1))
    world.at('10:03:50', world.finish, lambda: world.phase('complete'))
    world.run('10:05:00')
    assert world.box.times == [hms('10:03:10')] and world.guard.recuts == 0
    assert world.box.auto_refill == 1


def test_a_start_during_the_read_back_takes_the_cut_out_of_the_old_job():
    world = started()
    reactor = world.sim.reactor
    suspect(world)
    world.at(hms('10:03:09') + .5,
             lambda: setattr(reactor, 'on_pause', lambda: world.gcode.dispatch('START_PRINT')))
    world.run('10:03:30')
    guard = world.guard
    assert guard.job == 2 and guard.watch.marked is None
    assert guard.cut is None and guard.last_cut is None and guard.recuts == 0
    assert not guard.cut_pending and not world.said('contredit')
    assert world.box.auto_refill == 1 and not guard.refill_pending
    assert [event for event in world.events if event[0] == 'box'] == [('box', 0), ('box', 1)]


def test_a_log_level_above_info_blinds_the_guard_and_says_so_once():
    world = started()
    suspect(world)
    world.at('10:01:00', lambda: logging.getLogger().setLevel(logging.WARNING))
    world.run('10:06:00')
    assert world.guard.watch.blind == 'log_level' and world.guard.watch.marked is None
    assert world.said('contredit') == [] and world.box.times == []
    assert len(world.said(SG.BLIND_MESSAGES['log_level'])) == 1


def test_a_silent_route_blinds_the_guard_and_says_so_once():
    world = started()
    world.at('10:00:00', lambda: world.begin('T1A', 5.))
    world.every('10:00:10', '10:00:30', 4, reply(1, ERR))
    world.run('10:05:00')
    assert world.guard.watch.blind == 'no_cfs_reply' and world.guard.watch.marked is None
    assert len(world.said('garde capteur aveugle, aucune reponse du CFS depuis 60 s')) == 1


# The next START_PRINT.

def marked_and_ended():
    world = started()
    suspect(world, until='10:03:40')
    world.at('10:04:00', world.finish)
    world.run('10:04:10')
    assert world.guard.cut == 'confirmed' and world.guard.window is not None
    return world


def test_the_start_puts_the_refill_back_before_the_stock_start():
    world = marked_and_ended()
    del world.events[:]
    assert world.begin() is None
    assert world.events == [('box', 1), ('stock_start',)] and world.box.locked[-1] is True
    assert world.box.auto_refill == 1 and not world.guard.refill_pending
    assert world.guard.window is None and world.guard.closed_by == 'new_print'


def test_the_start_is_refused_when_the_refill_does_not_come_back():
    world = marked_and_ended()
    world.box.mode = 'inert'
    del world.events[:]
    error = world.begin()
    assert str(error) == ('K1 Control: auto-remplacement CFS coupe par la garde capteur '
                          'non retabli, depart refuse')
    assert world.events == [('box', 1)] and world.end.starts == 1 and world.guard.job == 1
    assert world.guard.refill_pending and world.guard.window is not None
    world.run('10:04:20')
    assert world.guard.window is not None and world.guard.closed_by == ''


@pytest.mark.parametrize('field, value', [('inflight', True), ('phase', 'heating')])
def test_the_start_is_refused_while_the_owned_end_runs(field, value):
    world = marked_and_ended()
    setattr(world.end, field, value)
    del world.events[:]
    error = world.begin()
    assert str(error) == 'K1 Control: finalisation encore en cours'
    assert world.events == [] and world.end.starts == 1 and world.guard.job == 1


@pytest.mark.parametrize('order', [('end', 'cold', 'guard'), ('guard', 'end', 'cold'),
                                   ('cold', 'guard', 'end')])
def test_the_stock_start_runs_once_in_any_wrap_order(order):
    world = started(order=order)
    assert world.begin() is None
    assert world.events == [('stock_start',)] and world.end.starts == 1 and world.guard.job == 1


def test_a_start_that_fails_further_on_rearms_the_window():
    world = started()
    world.stock_fail = True
    assert str(world.begin()) == 'stock start refused'
    assert world.guard.armed and world.guard.job == 1
    world.run('10:00:00')
    assert world.guard.window['cause'] == 'end'


# Order of the extruder checks.

@pytest.mark.parametrize('order', [('end', 'cold', 'guard'), ('end', 'guard', 'cold')])
def test_the_guard_sits_inside_the_cold_guard_in_both_orders(order):
    world = started(order=order)
    assert world.guard.get_status()['hook'] == 'inside_cold_guard'
    assert world.cold.get_status(0.)['cold_installed'] is True
    assert world.extruder.check_move == world.cold.check_extrude
    assert world.guard.inner == world.extruder.stock_check


def test_without_the_cold_guard_the_hook_is_direct():
    world = started(order=('end', 'guard'))
    assert world.guard.get_status()['hook'] == 'direct'
    assert world.extruder.check_move == world.guard.check_extrude


@pytest.mark.parametrize('order', [('end', 'cold', 'guard'), ('end', 'guard', 'cold')])
def test_each_check_judges_after_the_one_it_wraps(order):
    world = started(order=order)
    world.begin()
    world.cool(24.)
    world.toolhead.try_push(5.)
    assert world.cold.cold_refused == 1 and not world.guard.tripped
    world.finish()
    world.run('10:00:05')
    world.toolhead.try_push(2000.)
    assert world.toolhead.refused[-1] == (2000., 'Extrude only move too long')
    assert not world.guard.tripped
    world.toolhead.try_push(80.)
    assert world.guard.tripped and world.cold.cold_refused == 1
    assert world.toolhead.refused[-1] == (80., SG.TRIP_MESSAGE) and world.toolhead.queued == []


# The end window.

@pytest.mark.parametrize('state', ['complete', 'cancelled', 'error', 'standby'])
def test_every_end_state_opens_the_window(state):
    world = ended(state)
    assert world.guard.window == {'opened': hms('10:00:11'), 'cause': 'end'}
    assert world.guard.ended and world.guard.until == hms('10:15:11')


def test_a_push_right_after_the_end_opens_the_window_itself():
    world = started()
    world.begin()
    world.run('10:00:10')
    world.finish()
    world.toolhead.try_push(5.)
    assert world.guard.window['cause'] == 'push' and world.guard.tripped


def test_the_pushing_phases_of_the_owned_end_reset_the_net_level():
    world = ended()
    for phase, mm in (('waiting', .8), ('cutting', 3.), ('rewinding', -20.), ('finalizing', 1.5),
                      ('complete', .8)):
        world.phase(phase)
        world.toolhead.try_push(mm)
    assert world.toolhead.queued == [.8, 3., -20., 1.5, .8] and world.guard.level == .8
    world.toolhead.try_push(.3)
    assert world.guard.tripped and world.toolhead.queued[-1] == .8


def test_after_the_trip_pushes_are_refused_and_retractions_pass():
    world = ended()
    world.toolhead.try_push(5.)
    assert world.toolhead.queued == [] and world.printer.shutdown_calls == [SG.TRIP_MESSAGE]
    world.toolhead.try_push(-3.)
    world.toolhead.try_push(.2)
    assert world.toolhead.queued == [-3.] and world.printer.shutdown_calls == [SG.TRIP_MESSAGE]
    assert world.toolhead.refused == [(5., SG.TRIP_MESSAGE), (.2, SG.TRIP_MESSAGE)]
    assert world.guard.timer.callback(world.sim.clock) == world.sim.reactor.NEVER


def test_a_retraction_buys_no_credit_for_a_later_push():
    world = ended()
    world.toolhead.try_push(-5.)
    world.toolhead.try_push(1.5)
    assert world.guard.tripped and world.toolhead.queued == [-5.]


def test_the_window_lasts_end_window_after_the_owned_end_leaves_its_phases():
    world = started(end_window=120.)
    guard = world.guard
    world.begin()
    world.at('10:00:10', world.finish, lambda: world.phase('waiting'))
    world.at('10:01:00', lambda: world.phase('complete'))

    def still_open():
        assert guard.window is not None and guard.until == hms('10:02:59')

    world.at(hms('10:02:58') + .5, still_open)
    world.run('10:03:10')
    assert guard.window is None and guard.closed_by == 'expired' and not guard.armed
    assert len(world.said('garde de fin active 2 min')) == 1
    world.toolhead.try_push(5.)
    assert world.toolhead.queued == [5.] and not guard.tripped


def test_a_pause_during_the_file_opens_no_window():
    world = started()
    world.begin()
    world.at('10:00:10', world.pause)
    world.run('10:01:00')
    assert world.guard.window is None and world.guard.armed
    world.toolhead.try_push(30.)
    assert world.toolhead.queued == [30.] and not world.guard.tripped


def test_a_pause_without_an_open_file_counts_as_the_end():
    world = started()
    world.begin()
    world.at('10:00:10', world.finish, lambda: setattr(world.print_stats, 'state', 'paused'))
    world.run('10:00:12')
    assert world.guard.window is not None


def test_a_new_file_closes_the_window_at_the_tick_or_at_its_first_push():
    world = ended()
    world.sd.active = True
    world.run('10:00:12')
    assert world.guard.window is None and world.guard.closed_by == 'new_print' and world.guard.armed
    world = ended()
    world.sd.active = True
    world.toolhead.try_push(5.)
    assert world.guard.window is None and world.guard.closed_by == 'new_print'
    assert world.toolhead.queued == [5.]


def test_after_a_cancel_the_window_holds_once_the_owned_end_is_done():
    world = ended('cancelled')
    world.phase('finalizing')
    world.toolhead.try_push(1.5)
    world.phase('complete')
    world.run('10:00:20')
    world.toolhead.try_push(5.)
    assert world.toolhead.queued == [1.5] and world.guard.tripped


def test_a_file_without_start_print_still_arms_the_window():
    world = started()
    world.sd.active = True
    world.print_stats.state = 'printing'
    world.run('10:00:05')
    world.finish()
    world.run('10:00:06')
    assert world.guard.window is not None and world.guard.job == 0


# Console commands and status.

def test_release_lifts_only_an_open_window_outside_the_owned_end():
    world = started()
    assert world.gcode.dispatch('KCTRL_SENSOR_GUARD_RELEASE') is None
    assert world.said('aucune fenetre de fin ouverte')
    world = ended()
    world.phase('heating')
    world.gcode.dispatch('KCTRL_SENSOR_GUARD_RELEASE')
    assert world.said('garde de fin maintenue pendant la fin K1 Control')
    assert world.guard.window is not None
    world.phase('complete')
    world.gcode.dispatch('KCTRL_SENSOR_GUARD_RELEASE')
    assert world.said('garde de fin levee, poussee a la main permise')
    assert world.guard.window is None and world.guard.closed_by == 'release' and not world.guard.armed
    world.toolhead.try_push(30.)
    world.run('10:01:00')
    assert world.toolhead.queued == [30.] and world.guard.window is None and not world.guard.tripped


def test_release_and_status_never_fail_the_owned_end():
    world = ended()
    world.phase('cutting')
    world.end.proof = END.CutProof()
    for line in ('KCTRL_SENSOR_GUARD_RELEASE', 'KCTRL_SENSOR_GUARD_STATUS'):
        assert world.gcode.dispatch(line) is None
    assert world.end.command_error == '' and not world.end.proof.failed
    assert world.guard.window is not None
    assert_quiet(world)


def test_status_reads_in_french_and_says_echec_for_a_failed_end():
    world = started()
    suspect(world)
    world.run('10:05:00')
    world.finish()
    world.phase('failed')
    world.run('10:05:02')
    assert world.gcode.dispatch('KCTRL_SENSOR_GUARD_STATUS') is None
    lines = world.gcode.responses[-1].split('\n')
    assert lines[0] == '// K1 Control: garde capteur cfs-sensor-guard-v1, posee'
    assert lines[1] == '// crochet: inside_cold_guard ; aveugle: non'
    assert lines[2] == '// route: T1A'
    assert lines[3].startswith('// episode T1A: ') and lines[3].endswith(' mm, suspect (filament_err)')
    assert lines[4] == '// marque: T1A apres 180 s et 905 mm, coupe confirmed, recoupes 0'
    assert lines[5] == '// auto-remplacement a retablir au depart: oui'
    assert lines[6] == '// fenetre de fin: ouverte, 899 s restantes, 0.0 mm nets'
    assert lines[7] == "// fin K1 Control: echec ; arret d'urgence: non ; erreur interne: non"
    assert len(lines) == 8
    assert world.gcode.descs['KCTRL_SENSOR_GUARD_STATUS'] == SG.STATUS_HELP


def test_status_falls_back_when_its_text_breaks(monkeypatch):
    world = started()
    monkeypatch.setattr(world.guard, 'get_status', lambda eventtime=None: {})
    assert world.gcode.dispatch('KCTRL_SENSOR_GUARD_STATUS') is None
    assert world.gcode.responses[-1] == (
        '// K1 Control: garde capteur cfs-sensor-guard-v1, etat illisible (voir le journal)')


def test_get_status_never_raises():
    world = started()
    world.guard.watch.episodes = None
    status = world.guard.get_status()
    assert set(status) == {'enabled', 'revision', 'installed', 'status_error'}


def test_the_status_is_json_safe():
    world = started()
    suspect(world)
    world.run('10:05:00')
    world.finish()
    world.run('10:05:02')
    world.toolhead.try_push(5.)
    status = world.guard.get_status()
    json.dumps(status)
    assert status['tripped'] and status['trip']['push'] == 5. and status['hooked']
    assert status['episodes']['T1A']['reasons'] == ['filament_err']
    assert status['marked'] == {'slot': 'T1A', 'seconds': 180., 'printed': 905.,
                                'reasons': ['filament_err']}
    assert status['tap_seen'] > 0 and status['tap_dropped'] == 0


# Installation.

def section():
    parser = configparser.ConfigParser()
    parser.read(ROOT / 'cfs-sensor-guard-v1/sections.cfg', encoding='utf-8')
    return parser['kctrl_sensor_guard']


def test_a_disabled_guard_reads_every_option_and_installs_nothing():
    sim = Sim(0.)
    printer = FakePrinter(sim)
    printer.objects['gcode'] = FakeGCode()
    config = FakeConfig(printer, {})
    guard = SG.load_config(config)
    assert not guard.enabled and printer.handlers == {}
    cfg = section()
    assert [name for name, _ in config.read] == list(cfg)
    for name, default in config.read:
        value = cfg.getboolean(name) if type(default) is bool else type(default)(cfg[name])
        assert value == default, name
    assert cfg.getboolean('enabled') is False


@pytest.mark.parametrize('breakage, reason', [
    (lambda world: world.printer.objects.pop('box'), 'missing box'),
    (lambda world: world.printer.objects.pop('filament_switch_sensor filament_sensor_2'),
     'missing filament_switch_sensor filament_sensor_2'),
    (lambda world: setattr(world.end, 'enabled', False), 'kctrl_end not enabled'),
    (lambda world: world.gcode.register_command('BOX_ENABLE_AUTO_REFILL', None),
     'missing primitive BOX_ENABLE_AUTO_REFILL'),
])
def test_ready_refuses_without_what_the_guard_needs(breakage, reason):
    world = World(hms('10:00:00'))
    breakage(world)
    with pytest.raises(ConfigError, match=reason):
        world.ready()
    assert not world.guard.installed and world.sim.reactor.timers == []


def test_ready_refuses_without_start_print():
    world = World(hms('10:00:00'), order=('guard', 'end', 'cold'))
    world.gcode.register_command('START_PRINT', None)
    with pytest.raises(ConfigError, match='missing START_PRINT'):
        world.ready()
    assert not world.guard.installed and world.guard.original is None


def test_ready_undoes_every_step_when_one_fails():
    world = World(hms('10:00:00'))
    world.gcode.register_command('KCTRL_SENSOR_GUARD_RELEASE', lambda gcmd: None)
    with pytest.raises(ConfigError, match='already registered'):
        world.ready()
    guard = world.guard
    assert world.gcode.ready_gcode_handlers['START_PRINT'] == world.end.start
    assert world.extruder.check_move == world.cold.check_extrude
    assert world.cold.original_extrude_check == world.extruder.stock_check
    assert 'KCTRL_SENSOR_GUARD_STATUS' not in world.gcode.ready_gcode_handlers
    assert not any(getattr(handler, 'kctrl_sensor_tap', False)
                   for handler in logging.getLogger().handlers)
    assert not guard.installed and guard.original is None and guard.timer is None


def test_a_restart_leaves_one_tap_and_a_disconnect_removes_it():
    root = logging.getLogger()
    root.addHandler(SG.LineTap(lambda: 0.))
    world = started()
    assert [handler for handler in root.handlers
            if getattr(handler, 'kctrl_sensor_tap', False)] == [world.guard.tap]
    world.printer.send_event('klippy:disconnect')
    assert not any(getattr(handler, 'kctrl_sensor_tap', False) for handler in root.handlers)
    assert world.guard.timer.callback(world.sim.clock) == world.sim.reactor.NEVER


def test_a_second_ready_installs_nothing_more():
    world = started()
    handlers = dict(world.gcode.ready_gcode_handlers)
    world.guard._ready()
    assert world.gcode.ready_gcode_handlers == handlers and len(world.sim.reactor.timers) == 1


def test_a_broken_read_is_kept_and_the_tick_goes_on():
    world = started()

    def broken(eventtime):
        raise RuntimeError('boom')

    world.print_stats.get_status = broken
    world.run('10:00:03')
    assert world.guard.failure == 'watch: boom'
    assert world.guard.timer.waketime == hms('10:00:04')


def test_no_guard_message_parses_as_a_cfs_event_or_fails_the_owned_end():
    lines = [SG.TRIP_MESSAGE, SG.WINDOW_MESSAGE % 15, SG.RECUT_MESSAGE, SG.STATUS_HELP,
             SG.RELEASE_HELP]
    lines += [SG.MARK_MESSAGE % ('T1A', 248, 403, outcome) for outcome in SG.MARK_OUTCOMES.values()]
    lines += [text % 60 if '%d' in text else text for text in SG.BLIND_MESSAGES.values()]
    end = SimpleNamespace(phase='cutting', command_error='', proof=END.CutProof())
    for line in lines:
        assert SG.parse(line) is None and line.isascii(), line
        END.KctrlEnd._output(end, '// ' + line)
    assert end.command_error == '' and not end.proof.failed
    assert SG.END_ACTIVE == END.ACTIVE
    assert set(SG.END_PUSH_PHASES) < set(END.ACTIVE)
