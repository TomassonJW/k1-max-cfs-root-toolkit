"""Bounded automatic RESUME watchdog, simulated without printer (ADR-073)."""
import importlib.util
from pathlib import Path
import types

PACKAGE = Path(__file__).resolve().parents[1] / 'packages/k1-control-v1/night-autoresume-v1'


def load(tmp_path):
    spec = importlib.util.spec_from_file_location('kctrl_autoresume', PACKAGE / 'kctrl_autoresume.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.LOG = str(tmp_path / 'autoresume.log')
    module.STOP = str(tmp_path / 'autoresume.stop')
    return module


def snap(state, idle='Ready', homed='xyz', duration=900.0, klipper='ready'):
    return {'print_stats': {'state': state, 'print_duration': duration},
            'idle_timeout': {'state': idle}, 'toolhead': {'homed_axes': homed},
            'webhooks': {'state': klipper}}


def run(module, snapshots, argv=('--arm',)):
    """Feed one snapshot per poll; return the G-code scripts sent."""
    clock = {'now': 1000.0}
    feed = iter(snapshots)
    sent = []
    module.time = types.SimpleNamespace(
        time=lambda: clock['now'],
        sleep=lambda seconds: clock.__setitem__('now', clock['now'] + seconds),
        strftime=lambda fmt: 'T ')
    module.status = lambda: next(feed)

    def call(method, params, timeout=10.0):
        sent.append(params['script'])
        return {'result': {}}
    module.call = call
    module.sys = types.SimpleNamespace(argv=['x'] + list(argv))
    module.main()
    return sent


def test_decision_rules(tmp_path):
    k = load(tmp_path)
    now = 10000.0
    assert k.may_resume(snap('paused'), now - 61, now, 0, 0)
    assert not k.may_resume(snap('paused'), now - 30, now, 0, 0)
    assert not k.may_resume(snap('printing'), now - 61, now, 0, 0)
    assert not k.may_resume(snap('paused', idle='Idle'), now - 61, now, 0, 0)
    assert not k.may_resume(snap('paused', idle='Printing'), now - 61, now, 0, 0)
    assert not k.may_resume(snap('paused', homed=''), now - 61, now, 0, 0)
    assert not k.may_resume(snap('paused', duration=120), now - 61, now, 0, 0)
    assert not k.may_resume(snap('paused'), now - 61, now, now - 100, 1)
    assert not k.may_resume(snap('paused'), now - 61, now, 0, 15)
    assert not k.may_resume(snap('paused'), None, now, 0, 0)


def test_one_resume_after_stable_pause_then_exit_on_complete(tmp_path):
    k = load(tmp_path)
    seq = ([snap('standby')] * 3 + [snap('printing')] * 3
           + [snap('paused')] * 8 + [snap('printing')] * 2 + [snap('complete')])
    assert run(k, seq) == ['RESUME']


def test_no_resume_while_gcode_busy_or_motors_off(tmp_path):
    k = load(tmp_path)
    seq = ([snap('printing')] + [snap('paused', idle='Printing')] * 20
           + [snap('paused', idle='Idle', homed='')] * 20 + [snap('cancelled')])
    assert run(k, seq) == []


def test_attempts_are_bounded(tmp_path):
    k = load(tmp_path)
    seq = [snap('printing')] + [snap('paused')] * 2000
    assert run(k, seq) == ['RESUME'] * k.MAX_ATTEMPTS


def test_dry_run_sends_nothing(tmp_path):
    k = load(tmp_path)
    seq = [snap('printing')] + [snap('paused')] * 30 + [snap('complete')]
    assert run(k, seq, argv=()) == []


def test_stops_on_klipper_shutdown_and_stop_file(tmp_path):
    k = load(tmp_path)
    assert run(k, [snap('printing'), snap('paused', klipper='shutdown')]) == []
    k = load(tmp_path)
    Path(k.STOP).write_text('')
    assert run(k, [snap('paused')] * 30) == []
