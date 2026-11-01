"""End-of-print watch run from the PC, simulated without printer nor network."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import types
import urllib.error
import urllib.request

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / 'packages/k1-control-v1/end-watch-v1'
END_AT = 30.


class Reached(BaseException):
    """A transport no test replaced was touched; the watch never swallows it."""


class Forbidden:
    def __init__(self, name):
        self.name = name

    def __getattr__(self, attr):
        raise Reached('%s.%s' % (self.name, attr))


def load():
    spec = importlib.util.spec_from_file_location('watch_end', PACKAGE / 'watch_end.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Network, ssh and Windows calls all raise unless a test replaces them.
    module.urllib = types.SimpleNamespace(request=Forbidden('urllib.request'))
    module.subprocess = Forbidden('subprocess')
    module.shutil = types.SimpleNamespace(which=lambda name: None)
    module.ctypes = types.SimpleNamespace()
    return module


def snap(state='complete', sd=False, phase='complete', cold=0, denied=0, e=500.,
         target=0., paused=False, hooks='ready', progress=1., failure=''):
    """One K1 status; the defaults are a quiet K1 after a clean end."""
    return {
        'webhooks': {'state': hooks, 'state_message': 'Printer is ready'},
        'print_stats': {'state': state, 'filename': 'part.gcode', 'message': ''},
        'virtual_sdcard': {'is_active': sd, 'progress': progress},
        'pause_resume': {'is_paused': paused},
        'kctrl_end': {'phase': phase, 'failure': failure},
        'kctrl_purge_guard': {'cold_refused': cold, 'denied': denied,
                              'cold_last': 'poussee 80.00 mm a 25 C, cible 0 C',
                              'last_error': ''},
        'extruder': {'temperature': 30., 'target': target},
        'heater_bed': {'target': 0.},
        'toolhead': {'position': None if e is None else [100., 100., 50., e],
                     'homed_axes': 'xyz'},
        'box': {'state': 'standby', 't_command': '', 'filament_useup': 0, 'auto_refill': 0},
    }


PRINTING = snap('printing', True, 'idle', progress=.5)
NEAR_END = snap('printing', True, 'idle', progress=.98)
PAUSED = snap('paused', True, 'idle', paused=True, progress=.5)


def ended(*after):
    """The file prints, ends at 30 s, then (seconds after the end, status) items."""
    return [(0., PRINTING), (END_AT, snap())] + [(END_AT + t, s) for t, s in after]


def http_error(code):
    # With a body, as urllib gives it: without one, any attribute lookup raises KeyError.
    return urllib.error.HTTPError('http://HOST:4409/printer/objects/query', code,
                                  'Service Unavailable', None, io.BytesIO())


def url_down():
    return urllib.error.URLError(ConnectionRefusedError())


def answer(query, status):
    """What Moonraker gives: every field asked, None where the K1 has none."""
    reply = {}
    for part in query.split('&'):
        name, _, fields = part.partition('=')
        source = status.get(name, {})
        reply[name] = {field: source.get(field) for field in fields.split(',')}
    return reply


def fresh(**changes):
    mem = {'started': 0., 'base': None, 'over': None, 'e_ref': None, 'hot': None,
           'paused': None}
    mem.update(changes)
    return mem


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class K1:
    """The K1 seen from the PC, on a fake clock starting at 0 s."""

    def __init__(self, timeline, moonraker_stop=0., socket_stop=None, post_error=None,
                 info='ready'):
        self.timeline = timeline
        self.moonraker_stop = moonraker_stop    # seconds from the POST to shutdown
        self.socket_stop = socket_stop          # seconds from the socket to shutdown
        self.post_error = post_error
        self.info = info
        self.now = 0.
        self.shutdown_at = None
        self.trace = []

    def current(self):
        status = None
        for second, item in self.timeline:
            if self.now >= second:
                status = item
        return status

    def read(self, query, timeout=8):
        self.trace.append(('read', self.now, (query, timeout)))
        status = self.current()
        if isinstance(status, BaseException):
            # The same error is raised for hours: its traceback must not grow.
            raise status.with_traceback(None)
        if self.shutdown_at is not None and self.now >= self.shutdown_at:
            status = dict(status, webhooks={'state': 'shutdown'})
        return answer(query, status)

    def urlopen(self, url, timeout=None):
        """The gateway itself, for a watch that keeps its real read()."""
        status = self.current()
        if isinstance(status, bytes):
            self.trace.append(('read', self.now, (url, timeout)))
            return Reply(status)
        status = self.read(url.partition('?')[2], timeout)
        return Reply(json.dumps({'result': {'status': status}}).encode())

    def post(self, path):
        self.trace.append(('post', self.now, path))
        if self.post_error is not None:
            raise self.post_error
        if path == '/printer/emergency_stop' and self.moonraker_stop is not None:
            self.shut(self.moonraker_stop)
        return '{"result": "ok"}'

    def klipper(self, method):
        self.trace.append(('klipper', self.now, method))
        if method == 'info':
            return self.info
        if self.socket_stop is not None:
            self.shut(self.socket_stop)
        return 'ok'

    def shut(self, delay):
        at = self.now + delay
        self.shutdown_at = at if self.shutdown_at is None else min(self.shutdown_at, at)

    def sleep(self, seconds):
        self.trace.append(('sleep', self.now, seconds))
        self.now += seconds
        if self.now > 11 * 3600:
            raise Reached('the watch outlived its 10 h')

    def print(self, *args, **kwargs):
        self.trace.append(('log', self.now, ' '.join(map(str, args))))

    def install(self, module):
        module.time = types.SimpleNamespace(time=lambda: 1000. + self.now, sleep=self.sleep,
                                            strftime=lambda fmt: 'T')
        module.read, module.post, module.klipper = self.read, self.post, self.klipper
        module.print = self.print
        self.module = module
        return self

    def of(self, kind):
        return [(at, value) for name, at, value in self.trace if name == kind]

    def lines(self):
        return [text[2:] for at, text in self.of('log')]

    def at(self, start):
        """Seconds at which a log line starting with these words was written."""
        return [at for at, text in self.of('log') if text[2:].startswith(start)]


def run(timeline, *options, **k1):
    k = K1(timeline, **k1).install(load())
    return k.module.main(['watch_end.py', 'HOST'] + list(options)), k


def with_real_read(timeline, **k1):
    module = load()
    real = module.read
    k = K1(timeline, **k1).install(module)
    module.read = real
    module.urllib = types.SimpleNamespace(request=types.SimpleNamespace(urlopen=k.urlopen))
    return k


EXIT_SCENARIOS = {
    0: dict(timeline=ended()),
    10: dict(timeline=ended((2, snap(phase='failed', failure='firmware_reported_error')))),
    11: dict(timeline=ended((2, snap(phase='idle')))),
    12: dict(timeline=ended((10, PRINTING))),
    20: dict(timeline=ended((10, snap(cold=1)))),
    21: dict(timeline=ended((10, snap(cold=1))), moonraker_stop=None),
    30: dict(timeline=[(0., PAUSED)]),
    40: dict(timeline=ended((10, snap(hooks='startup')))),
    50: dict(timeline=ended((2, url_down()))),
    60: dict(timeline=[(0., PRINTING)]),
}


@pytest.mark.parametrize('code', sorted(EXIT_SCENARIOS))
def test_every_exit_code_ends_the_log_with_its_meaning(code):
    scenario = dict(EXIT_SCENARIOS[code])
    got, k = run(scenario.pop('timeline'), **scenario)
    assert got == code
    assert k.lines()[-1] == 'exit %d: %s' % (code, k.module.EXITS[code])
    # One emergency stop at most, and only for 20 and 21.
    assert [path for at, path in k.of('post')] == (
        ['/printer/emergency_stop'] if code in (20, 21) else [])
    assert [method for at, method in k.of('klipper')] == (['emergency_stop'] if code == 21 else [])


def test_the_scenarios_cover_every_documented_exit():
    assert sorted(EXIT_SCENARIOS) == sorted(load().EXITS)


def test_a_cold_refusal_after_the_end_stops_once():
    code, k = run(ended((10, snap(cold=1))))
    assert code == 20
    assert k.of('post') == [(40., '/printer/emergency_stop')]
    assert k.of('klipper') == []
    assert k.at('EMERGENCY STOP: cold push refused 1 time(s)') == [40.]
    assert k.at('stopped: {') == [40.]
    # What was refused comes with the report: the END query does not read it.
    assert '"cold_last": "poussee 80.00 mm a 25 C, cible 0 C"' in k.lines()[-2]


def test_a_bin_refusal_after_the_end_stops():
    code, k = run(ended((10, snap(denied=2))))
    assert code == 20
    assert k.at('EMERGENCY STOP: bin move refused 2 time(s)') == [40.]


def test_e_forward_exactly_1_mm_does_not_stop():
    code, k = run(ended((2, snap(e=500.)), (10, snap(e=501.))))
    assert code == 0
    assert k.of('post') == []


def test_small_moves_add_up_from_the_lowest_e():
    code, k = run(ended((2, snap(e=500.)), (10, snap(e=500.6)), (20, snap(e=501.2))))
    assert code == 20
    assert k.at('EMERGENCY STOP: extruder forward 1.2 mm, end complete') == [50.]


def test_a_retraction_lowers_the_e_reference():
    code, k = run(ended((2, snap(e=500.)), (10, snap(e=495.)), (20, snap(e=496.1))))
    assert code == 20
    assert k.at('EMERGENCY STOP: extruder forward 1.1 mm') == [50.]


def test_the_night_of_1_november_is_stopped_at_the_push():
    # End of file 07:13:52, failed end 07:13:57, stock push of 80 mm at 07:14:08.
    failed = dict(phase='failed', failure='firmware_reported_error', target=195.)
    code, k = run([(0., NEAR_END), (END_AT, snap(phase='cutting')),
                   (END_AT + 2, snap(phase='cutting', e=499., target=195.)),
                   (END_AT + 5, snap(e=499., **failed)),
                   (END_AT + 16, snap(e=579., **failed))])
    assert code == 20
    assert k.at('EMERGENCY STOP: extruder forward 80.0 mm, end failed') == [END_AT + 16]


def test_a_nozzle_held_hot_15_min_with_no_end_running_stops():
    code, k = run(ended((2, snap(target=170.))))
    assert code == 20
    assert k.at('nozzle target 170 C with no end running: 15 min count') == [32.]
    # First read at or after 900 s of heat: every 2 s until 15 min, then 5 s.
    assert k.at('EMERGENCY STOP: nozzle held at 170 C for 15 min, end complete') == [935.]


def test_a_nozzle_below_170_c_never_stops():
    code, k = run(ended((2, snap(target=169.9))))
    assert code == 0
    assert k.of('post') == []


def test_a_target_drop_restarts_the_15_min_count():
    # Heat from 32 s, dropped at 930 s (898 s of heat), back at 935 s.
    code, k = run(ended((2, snap(target=200.)), (900, snap(target=0.)), (905, snap(target=200.))))
    assert code == 20
    assert k.at('nozzle target 200 C') == [32., 935.]
    assert k.at('EMERGENCY STOP: nozzle held at 200 C') == [1835.]


def test_an_active_end_masks_e_and_heat_until_its_90_min_bound():
    code, k = run(ended((2, snap(phase='cutting', e=520., target=220.)),
                        (600, snap(phase='rewinding', e=400., target=220.)),
                        (1200, snap(phase='rewinding', e=700., target=220.))))
    assert code == 11
    assert k.of('post') == []
    assert k.at('window over') == [END_AT + 5400]


def test_a_refusal_counts_even_in_an_active_end():
    code, k = run(ended((2, snap(phase='rewinding')), (60, snap(phase='rewinding', denied=1))))
    assert code == 20
    assert k.at('EMERGENCY STOP: bin move refused 1 time(s)') == [END_AT + 60]


def test_leaving_the_end_takes_a_new_e_reference():
    # The cut moved E inside the end: once it is over, only new moves count.
    code, k = run([(0., PRINTING), (END_AT, snap(phase='cutting')),
                   (40., snap(e=580.)), (50., snap(e=580.9))])
    assert code == 0
    assert k.of('post') == []


def test_an_end_that_completes_after_45_min_closes_the_window_at_once():
    code, k = run(ended((2, snap(phase='rewinding')), (3600, snap(phase='complete'))))
    assert code == 0
    assert k.at('window over') == [END_AT + 3600]


def test_nothing_counts_before_the_end_of_the_file():
    during = [(float(t), snap('printing', True, 'idle', cold=t // 1800, denied=t // 2400,
                              e=500. + t, target=220., progress=.5))
              for t in range(0, 7200, 600)]
    code, k = run(during + [(7200., snap(cold=3, denied=2))])
    assert code == 0
    assert k.of('post') == [] and k.of('klipper') == []
    assert {query for at, (query, timeout) in k.of('read') if at < 7200} == {k.module.PRINT}


def test_an_unknown_or_missing_print_state_is_never_taken_for_the_end():
    code, k = run([(0., snap(None, None, 'idle')), (60., snap('odd', False, 'idle')),
                   (120., snap('complete', None)), (180., snap('standby', True)),
                   (240., snap())])
    assert code == 0
    assert k.at('print over') == [240.]


def test_reads_follow_the_documented_rhythm():
    code, k = run([(0., snap('printing', True, 'idle', progress=.96)),
                   (60., snap('printing', True, 'idle', progress=.97)), (70., snap())])
    sleeps = k.of('sleep')
    assert [s for at, s in sleeps if at < 70] == [30., 30., 5., 5.]
    assert {s for at, s in sleeps if 70 <= at < 70 + 900} == {2.}
    assert {s for at, s in sleeps if at >= 70 + 900} == {5.}
    assert code == 0
    assert k.at('window over') == [70. + 2700]


@pytest.mark.parametrize('status', [PRINTING, snap('complete', True), snap('paused', False)])
def test_a_new_file_after_the_end_exits_12(status):
    code, k = run(ended((10, status)))
    assert code == 12
    assert k.at('new print: {') == [END_AT + 10]


def test_a_stock_pause_after_the_end_does_not_end_the_watch():
    code, k = run(ended((10, snap(paused=True)), (20, snap(paused=True, cold=1))))
    assert code == 20
    assert k.at('EMERGENCY STOP: cold push refused') == [END_AT + 20]


@pytest.mark.parametrize('paused', [PAUSED, snap('printing', True, 'idle', paused=True)])
def test_a_pause_of_2_min_before_the_end_exits_30(paused):
    code, k = run([(0., PRINTING), (60., paused)])
    assert code == 30
    assert k.at('paused: {') == [180.]


def test_keep_on_pause_waits_through_a_long_pause():
    code, k = run([(0., PRINTING), (60., PAUSED), (3 * 3600., PRINTING),
                   (3 * 3600. + 600, snap())], '--keep-on-pause')
    assert code == 0
    assert k.at('start ssh=None awake=False keep_on_pause=True') == [0.]


def test_the_pause_count_restarts_when_printing_resumes():
    code, k = run([(0., PAUSED), (100., PRINTING), (130., PAUSED), (230., PRINTING),
                   (260., snap())])
    assert code == 0


@pytest.mark.parametrize('timeline', [
    [(0., PRINTING), (60., snap('printing', True, 'idle', hooks='shutdown'))],
    ended((10, snap(hooks='startup'))),
    ended((10, snap(hooks=None))),
])
def test_klipper_not_ready_exits_40(timeline):
    code, k = run(timeline)
    assert code == 40
    assert len(k.at('klipper not ready: {')) == 1


@pytest.mark.parametrize('error, said', [
    (http_error(503), 'unreachable HTTPError 503'),
    (http_error(502), 'unreachable HTTPError 502'),
    (url_down(), 'unreachable URLError ConnectionRefusedError'),
    (urllib.error.URLError(TimeoutError()), 'unreachable URLError TimeoutError'),
    (TimeoutError(), 'unreachable TimeoutError'),
    (json.JSONDecodeError('Expecting value', '', 0), 'unreadable JSONDecodeError'),
    (KeyError('result'), 'unreadable KeyError'),
])
def test_a_failed_read_is_said_once_and_the_watch_goes_on(error, said):
    code, k = run(ended((10, error), (60, snap(cold=1))))
    assert code == 20
    assert k.lines().count(said) == 1
    assert [s for at, s in k.of('sleep') if END_AT + 10 <= at < END_AT + 60] == [5.] * 10
    assert k.at('EMERGENCY STOP') == [END_AT + 60]


def test_reads_lost_after_the_end_exit_50_at_90_min():
    code, k = run(ended((2, url_down())))
    assert code == 50
    assert k.of('read')[-1][0] == 5432.


def test_reads_lost_before_the_end_exit_60_after_10_h():
    code, k = run([(0., PRINTING), (60., http_error(503))])
    assert code == 60
    assert k.of('read')[-1][0] == 36000.


def test_a_null_object_in_a_200_reply_is_refused_and_watched():
    # The night version fell on AttributeError here, before any stop could go out.
    null = json.dumps({'result': {'status': dict(answer(load().END, snap()), webhooks=None)}})
    k = with_real_read(ended((10, null.encode()), (20, snap(cold=1))))
    assert k.module.main(['watch_end.py', 'HOST']) == 20
    assert k.lines().count('unreadable ValueError') == 1
    assert k.at('EMERGENCY STOP: cold push refused') == [END_AT + 20]


def test_a_lost_output_does_not_take_the_stop_with_it():
    # The night version fell on the OSError of its log, before the POST.
    k = K1(ended((10, snap(cold=1)))).install(load())

    def lost(*args, **kwargs):
        raise OSError(22, 'Invalid argument')
    k.module.print = lost
    assert k.module.main(['watch_end.py', 'HOST']) == 20
    assert k.of('post') == [(40., '/printer/emergency_stop')]


def test_moonraker_stop_seen_in_time_needs_no_socket():
    code, k = run(ended((10, snap(cold=1))), moonraker_stop=5.)
    assert code == 20
    assert k.of('klipper') == []
    assert k.at('stopped: {') == [45.]
    assert {timeout for at, (query, timeout) in k.of('read') if query == 'webhooks=state'} == {3}


def test_the_socket_takes_over_6_s_after_moonraker():
    code, k = run(ended((10, snap(cold=1))), moonraker_stop=None, socket_stop=0.)
    assert code == 20
    assert k.of('post') == [(40., '/printer/emergency_stop')]
    assert k.of('klipper') == [(46., 'emergency_stop')]
    assert k.at('klipper socket stop: ok') == [46.]


def test_a_moonraker_stop_after_6_s_still_calls_the_socket():
    code, k = run(ended((10, snap(cold=1))), moonraker_stop=6.)
    assert code == 20
    assert k.of('klipper') == [(46., 'emergency_stop')]


def test_a_stop_never_seen_exits_21_after_16_s():
    code, k = run(ended((10, snap(cold=1))), moonraker_stop=None)
    assert code == 21
    assert k.of('klipper') == [(46., 'emergency_stop')]
    assert k.at('stop not confirmed: {') == [56.]


def test_klipper_gone_after_the_stop_reads_as_not_confirmed():
    # 1 November: Klipper quit by itself 6 s after the stop, Moonraker then answers 503.
    code, k = run(ended((10, snap(cold=1)), (10.5, http_error(503))), moonraker_stop=None)
    assert code == 21
    assert k.at('stop not confirmed: report unreadable HTTPError 503') == [56.]


@pytest.mark.parametrize('error, said', [
    (urllib.error.URLError(TimeoutError()), 'moonraker stop failed URLError TimeoutError'),
    (http_error(503), 'moonraker stop failed HTTPError 503'),
])
def test_a_failed_moonraker_post_falls_back_to_the_socket(error, said):
    code, k = run(ended((10, snap(cold=1))), post_error=error, socket_stop=0.)
    assert code == 20
    assert k.at(said) == [40.]
    assert k.of('klipper') == [(46., 'emergency_stop')]


def test_dry_run_reads_and_tries_both_stop_paths_without_stopping():
    code, k = run([(0., PRINTING)], '--dry-run')
    assert code == 0
    m = k.module
    assert [query for at, (query, timeout) in k.of('read')] == [m.PRINT, m.END, m.REPORT]
    assert k.of('post') == [(0., '/printer/objects/query?webhooks=state')]
    assert k.of('klipper') == [(0., 'info')]
    assert k.of('sleep') == []
    assert k.lines()[-1] == 'dry run ok'


@pytest.mark.parametrize('timeline, extra, failed', [
    ([(0., http_error(503))], {}, 'print query, end query'),
    ([(0., PRINTING)], {'post_error': url_down()}, 'gateway POST'),
    ([(0., PRINTING)], {'info': 'no ssh'}, 'klipper socket'),
    ([(0., PRINTING)], {'info': 'exit 255'}, 'klipper socket'),
])
def test_dry_run_fails_on_any_dead_path(timeline, extra, failed):
    code, k = run(timeline, '--dry-run', **extra)
    assert code == 1
    assert k.lines()[-1] == 'dry run failed: ' + failed
    assert k.of('post') == [(0., '/printer/objects/query?webhooks=state')]
    assert k.of('klipper') == [(0., 'info')]


@pytest.mark.parametrize('argv', [
    [], ['watch_end.py'], ['watch_end.py', ''], ['watch_end.py', '--dry-run'],
    ['watch_end.py', 'HOST', '--dryrun'], ['watch_end.py', 'HOST', '--dry-run', '--keep-on-pause'],
    ['watch_end.py', 'HOST', '--keep-on-pause', '--keep-on-pause'], ['watch_end.py', 'HOST', 'x'],
])
def test_a_wrong_command_line_exits_2_without_reading(argv, capsys):
    module = load()
    assert module.main(argv) == 2
    assert capsys.readouterr().err.strip() == module.USAGE
    assert module.HOST is None


def test_decide_never_changes_the_memory_it_is_given():
    module = load()
    mem = fresh(over=0., base=(0, 0), e_ref=500.)
    frozen = dict(mem)
    status = answer(module.END, snap(cold=1, e=600., target=220.))
    first = module.decide(status, mem, 60.)
    assert mem == frozen
    assert module.decide(status, mem, 60.) == first
    assert first[2][-1][0] == 'stop'


@pytest.mark.parametrize('base, counts, reason', [
    ((0, 0), (1, 0), 'cold push refused 1 time(s)'),
    ((0, 0), (0, 3), 'bin move refused 3 time(s)'),
    ((0, 0), (2, 1), 'cold push refused 2 time(s)'),
    ((2, 1), (2, 1), None),
    ((2, 1), (0, 0), None),          # a Klipper restart puts both back to 0
    ((0, 0), (None, 4), None),       # one counter unreadable: neither is trusted
    ((None, 0), (5, 5), None),
])
def test_refusal_rules(base, counts, reason):
    module = load()
    status = answer(module.END, snap(cold=counts[0], denied=counts[1], phase='cutting'))
    actions = module.decide(status, fresh(over=0., base=base), 60.)[2]
    assert actions[-1] == (('stop', reason) if reason else ('sleep', 2))


def test_e_rules():
    module = load()

    def step(e, ref, phase='complete'):
        mem, key, actions = module.decide(answer(module.END, snap(e=e, phase=phase)),
                                          fresh(over=0., base=(0, 0), e_ref=ref), 60.)
        return mem['e_ref'], actions[-1][0]
    assert step(500., None) == (500., 'sleep')
    assert step(501., 500.) == (500., 'sleep')
    assert step(501.0001, 500.) == (500., 'stop')
    assert step(499., 500.) == (499., 'sleep')
    assert step(580., 500., phase='cutting') == (None, 'sleep')
    for unreadable in (None, True, '580'):
        assert step(unreadable, 500.) == (None, 'sleep')
    short = answer(module.END, snap())
    short['toolhead']['position'] = [100., 100., 50.]
    assert module.decide(short, fresh(over=0., base=(0, 0), e_ref=500.), 60.)[0]['e_ref'] is None


def test_heat_rules():
    module = load()

    def step(target, hot, phase='complete'):
        mem, key, actions = module.decide(answer(module.END, snap(target=target, phase=phase)),
                                          fresh(over=0., base=(0, 0), hot=hot), 1000.)
        return mem['hot'], [name for name, value in actions]
    assert step(170., None) == (1000., ['log', 'sleep'])
    assert step(170., 100.1) == (100.1, ['sleep'])
    assert step(170., 100.) == (100., ['stop'])
    assert step(169.9, 100.) == (None, ['sleep'])
    assert step(220., 100., phase='heating') == (None, ['sleep'])
    assert step(None, 100.) == (None, ['sleep'])


def test_read_asks_the_gateway_and_refuses_what_is_not_a_status():
    module = load()
    module.HOST = 'HOST'
    asked, bodies = [], []

    def urlopen(url, timeout=None):
        asked.append((url, timeout))
        return Reply(json.dumps({'result': {'status': bodies.pop(0)}}).encode())
    module.urllib = types.SimpleNamespace(request=types.SimpleNamespace(urlopen=urlopen))
    bodies.append({'webhooks': {'state': 'ready'}})
    assert module.read('webhooks=state') == {'webhooks': {'state': 'ready'}}
    assert asked == [('http://HOST:4409/printer/objects/query?webhooks=state', 8)]
    for status in ({'webhooks': None}, {'webhooks': ['ready']}, [], None):
        bodies.append(status)
        with pytest.raises(ValueError):
            module.read('webhooks=state', 3)
    assert asked[-1][1] == 3


def test_read_lets_a_503_through_with_its_code():
    module = load()
    module.HOST = 'HOST'

    def urlopen(url, timeout=None):
        raise http_error(503)
    module.urllib = types.SimpleNamespace(request=types.SimpleNamespace(urlopen=urlopen))
    with pytest.raises(urllib.error.HTTPError) as error:
        module.read('webhooks=state')
    assert module.cause(error.value) == 'HTTPError 503'


@pytest.mark.parametrize('error, said', [
    (http_error(503), 'HTTPError 503'),
    (url_down(), 'URLError ConnectionRefusedError'),
    (urllib.error.URLError('no host'), 'URLError'),
    (TimeoutError(), 'TimeoutError'),
    (ValueError('reply is not a status of objects'), 'ValueError'),
])
def test_cause_names_the_failure_and_its_http_code(error, said):
    assert load().cause(error) == said


def test_post_sends_an_empty_post_to_the_gateway():
    module = load()
    module.HOST = 'HOST'
    sent = []

    def urlopen(request, timeout=None):
        sent.append((request.full_url, request.get_method(), request.data, timeout))
        return Reply(b'{"result": "ok"}' + b' ' * 300)
    module.urllib = types.SimpleNamespace(request=types.SimpleNamespace(
        urlopen=urlopen, Request=urllib.request.Request))
    assert module.post('/printer/emergency_stop') == '{"result": "ok"}' + ' ' * 144
    assert sent == [('http://HOST:4409/printer/emergency_stop', 'POST', b'', 5)]


def test_klipper_runs_one_python_over_the_ssh_alias():
    module = load()
    calls = []

    def run_ssh(argv, input, capture_output, timeout):
        calls.append((argv, input, capture_output, timeout))
        return types.SimpleNamespace(stdout=b'ok\n', returncode=0)
    module.shutil = types.SimpleNamespace(which={'ssh': '/usr/bin/ssh'}.get)
    module.subprocess = types.SimpleNamespace(run=run_ssh)
    assert module.klipper('emergency_stop') == 'ok'
    assert calls == [(['/usr/bin/ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
                       'k1max-root', 'python3', '-'],
                      b"METHOD = 'emergency_stop'\n" + module.SOCKET.encode(), True, 40)]


@pytest.mark.parametrize('outcome, word', [
    (subprocess.TimeoutExpired('ssh', 40), 'ssh TimeoutExpired'),
    (FileNotFoundError(), 'ssh FileNotFoundError'),
    (types.SimpleNamespace(stdout=b'', returncode=255), 'exit 255'),
    (types.SimpleNamespace(stdout=b'x' * 100 + b'ready\n', returncode=0), 'x' * 75 + 'ready'),
])
def test_klipper_says_what_ssh_did(outcome, word):
    module = load()

    def run_ssh(*args, **kwargs):
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome
    module.shutil = types.SimpleNamespace(which={'ssh': '/usr/bin/ssh'}.get)
    module.subprocess = types.SimpleNamespace(run=run_ssh)
    assert module.klipper('info') == word


def test_klipper_without_ssh_runs_nothing():
    assert load().klipper('emergency_stop') == 'no ssh'


def socket_word(monkeypatch, method, *chunks):
    """The script sent over SSH, run against a fake Klipper socket."""
    script = 'METHOD = %r\n' % method + load().SOCKET
    made = []

    class UnixSocket:
        def __init__(self, family, kind):
            assert (family, kind) == ('AF_UNIX', 'SOCK_STREAM')
            self.chunks, self.sent, self.path, self.timeout = list(chunks), b'', None, None
            made.append(self)

        def settimeout(self, seconds):
            self.timeout = seconds

        def connect(self, path):
            self.path = path

        def sendall(self, data):
            self.sent += data

        def recv(self, size):
            return self.chunks.pop(0) if self.chunks else b''
    monkeypatch.setitem(sys.modules, 'socket', types.SimpleNamespace(
        socket=UnixSocket, AF_UNIX='AF_UNIX', SOCK_STREAM='SOCK_STREAM'))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(script, {})
    return out.getvalue().strip(), made[0]


def test_the_socket_script_sends_one_webhooks_request(monkeypatch):
    word, sock = socket_word(monkeypatch, 'emergency_stop', b'{"id": 1, "result": {}}\x03')
    assert word == 'ok'
    assert (sock.path, sock.timeout) == ('/tmp/klippy_uds', 5)
    assert sock.sent.endswith(b'\x03')
    assert json.loads(sock.sent[:-1]) == {'id': 1, 'method': 'emergency_stop', 'params': {}}


@pytest.mark.parametrize('chunks, word', [
    ((b'{"id": 1, "result": {"state": "ready"}}\x03',), 'ready'),
    ((b'{"id": 1, "res', b'ult": {"state": "shutdown"}}', b'\x03'), 'shutdown'),
    ((b'{"id": 1, "error": {"message": "Klippy not ready"}}\x03',), 'error'),
    ((), 'ok'),                      # closed with no reply: never 'ready'
])
def test_the_socket_script_reads_a_reply_in_chunks(monkeypatch, chunks, word):
    assert socket_word(monkeypatch, 'info', *chunks)[0] == word


def test_keep_awake_holds_the_pc_for_this_process_only():
    module = load()
    flags = []
    kernel32 = types.SimpleNamespace(
        SetThreadExecutionState=lambda value: flags.append(value) or 0x80000000)
    module.ctypes = types.SimpleNamespace(windll=types.SimpleNamespace(kernel32=kernel32))
    assert module.keep_awake() is True
    assert flags == [0x80000001]
    kernel32.SetThreadExecutionState = lambda value: 0
    assert module.keep_awake() is False
    module.ctypes = types.SimpleNamespace()
    assert module.keep_awake() is False


def test_log_survives_a_console_that_cannot_encode(monkeypatch):
    module = load()
    module.time = types.SimpleNamespace(strftime=lambda fmt: 'T')
    raw = io.BytesIO()
    console = io.TextIOWrapper(raw, encoding='cp1252', newline='\n')
    monkeypatch.setattr(sys, 'stdout', console)
    module.log('cible 170 °C → arrêt')
    console.flush()
    assert raw.getvalue().decode('cp1252') == 'T cible 170 °C \\u2192 arrêt\n'


class BrokenOutput:
    encoding = 'utf-8'

    def write(self, text):
        raise OSError(22, 'Invalid argument')

    def flush(self):
        raise OSError(22, 'Invalid argument')


def test_log_never_raises(monkeypatch):
    module = load()
    closed = io.StringIO()
    closed.close()
    for output in (closed, BrokenOutput()):
        monkeypatch.setattr(sys, 'stdout', output)
        assert module.log('EMERGENCY STOP: test') is None


def test_docstring_and_readme_list_the_same_exit_codes():
    module = load()
    doc = ' '.join(module.__doc__.split())
    listed = doc.split('Exit: ', 1)[1].split('. The dry run', 1)[0]
    assert {int(code): text for code, text in re.findall(r'(\d+) ([^,]+)', listed)} == module.EXITS
    readme = (PACKAGE / 'README.md').read_text(encoding='utf-8')
    assert {int(code) for code in re.findall(r'^\| (\d+) \|', readme, re.M)} == set(module.EXITS)


def test_readme_gives_the_real_push_count():
    readme = (PACKAGE / 'README.md').read_text(encoding='utf-8')
    for words in ("Dumping trapq 'extruder'", 'Requested toolhead position at shutdown time',
                  'jamais par `tail -n`', '0,13 mm'):
        assert words in readme


def test_no_address_lives_in_the_package():
    for path in sorted(PACKAGE.glob('*')):
        if path.suffix in ('.py', '.md'):
            text = path.read_text(encoding='utf-8')
            assert not re.search(r'\b\d{1,3}(?:\.\d{1,3}){3}\b', text), path.name
