"""One-file cold patch and restoration, using only fake local hardware."""
import base64
import copy
import json
from types import ModuleType

import pytest

from test_retained_start_install import fixture as initial_fixture, state, PACKAGE


def fixture(tmp_path, monkeypatch):
    base, initial, paths, end, log = initial_fixture(tmp_path, monkeypatch)
    assert base.run(initial)['status'] == 'INSTALLED_COLD_OK'
    target = next(p for p in paths if p.name == 'kctrl_start.py')
    old = target.read_bytes()
    current_pid = int(base.PIDFILE.read_text())
    patch = ModuleType('selection_patch_test')
    patch.base = base
    source = (PACKAGE/'remote_selection_patch.py').read_text().replace('from . import remote_install as base\n', '')
    exec(compile(source, str(PACKAGE/'remote_selection_patch.py'), 'exec'), patch.__dict__)
    monkeypatch.setattr(patch, 'TARGET', str(target))
    monkeypatch.setattr(patch, 'OLD_SHA', base.digest(target))
    monkeypatch.setattr(patch, 'BACKUP', tmp_path/'temperature-backup')
    payload = b'patched target with duplicate tool preservation'
    request = {'initial_manifest': copy.deepcopy(initial['manifest']), 'mode': 'install',
        'payload': base64.b64encode(payload).decode(), 'sha256': base.hashlib.sha256(payload).hexdigest()}
    def observe():
        restarted = int(base.PIDFILE.read_text()) > current_pid
        s = state(installed=True, restarted=True)
        s['filament_switch_sensor filament_sensor_2']['filament_detected'] = False
        s['box']['t_command'] = '' if restarted else 'T1A'
        s['kctrl_end']['phase'] = 'idle' if restarted else 'complete'
        s['kctrl_start']['phase'] = 'idle' if restarted else 'complete'
        s['kctrl_purge_guard'].update(bin_latched=False, denied=0)
        if target.read_bytes() == payload:
            s['kctrl_start']['selection_policy'] = patch.POLICY
        return s
    monkeypatch.setattr(base, 'state', observe)
    def ready(patched):
        s = observe()
        patch.cold(s, restarted=True, patched=patched)
        return s
    monkeypatch.setattr(patch, 'ready', ready)
    log.clear()
    return patch, request, target, old, end, log


def test_preflight_only_reads(tmp_path, monkeypatch):
    m, req, target, old, end, log = fixture(tmp_path, monkeypatch)
    req['mode'] = 'preflight'
    assert m.run(req)['status'] == 'TEMPERATURE_PATCH_PREFLIGHT_OK'
    assert target.read_bytes() == old and not log and not m.BACKUP.exists()


def test_install_and_independent_validation_change_only_the_owner(tmp_path, monkeypatch):
    m, req, target, old, end, log = fixture(tmp_path, monkeypatch)
    assert m.run(req)['status'] == 'TEMPERATURE_PATCH_INSTALLED_COLD_OK'
    assert target.read_bytes() != old
    assert (m.BACKUP/'kctrl_start.py.before').read_bytes() == old
    assert end.read_bytes() == b'unchanged end V3'
    assert log[:2] == ['stop', 'start']
    assert log[2][2]['script'].endswith('MOVE=0')
    before_log = list(log)
    req['mode'] = 'validate'
    assert m.run(req)['status'] == 'TEMPERATURE_PATCH_VALIDATED_COLD_OK'
    assert log == before_log


@pytest.mark.parametrize('obj,key,value', [
    ('print_stats','state','printing'), ('pause_resume','is_paused',True),
    ('virtual_sdcard','is_active',True), ('extruder','target',150),
    ('extruder','temperature',55), ('heater_bed','temperature',float('nan')),
    ('toolhead','homed_axes','xyz'), ('motion_report','live_velocity',10),
    ('filament_switch_sensor filament_sensor_2','filament_detected',True),
    ('kctrl_end','phase','failed'), ('kctrl_end','pending',True),
    ('kctrl_start','phase','material'), ('kctrl_start','reference_valid',True),
    ('kctrl_purge_guard','bin_latched',True), ('box','t_command','T2D'),
])
def test_active_or_changed_state_refuses_before_effect(tmp_path, monkeypatch, obj, key, value):
    m, req, target, old, end, log = fixture(tmp_path, monkeypatch)
    s = m.base.state()
    s[obj][key] = value
    monkeypatch.setattr(m.base, 'state', lambda: s)
    with pytest.raises(AssertionError): m.run(req)
    assert target.read_bytes() == old and not log


@pytest.mark.parametrize('failure', ['payload', 'initial_manifest', 'protected', 'backup', 'stage'])
def test_wrong_inputs_refuse_before_service_stop(tmp_path, monkeypatch, failure):
    m, req, target, old, end, log = fixture(tmp_path, monkeypatch)
    if failure == 'payload': req['payload'] = base64.b64encode(b'incorrect').decode()
    if failure == 'initial_manifest': req['initial_manifest']['name'] = 'other'
    if failure == 'protected': end.write_bytes(b'foreign file')
    if failure == 'backup': m.BACKUP.mkdir()
    if failure == 'stage': m.base.Path(str(target)+'.kctrl-retained-next').write_bytes(b'foreign')
    with pytest.raises((AssertionError, RuntimeError)): m.run(req)
    assert target.read_bytes() == old and not log


@pytest.mark.parametrize('failure', ['copy', 'runtime'])
def test_update_failure_restores_initial_installed_owner(tmp_path, monkeypatch, failure):
    m, req, target, old, end, log = fixture(tmp_path, monkeypatch)
    if failure == 'copy':
        replace = m.base.replace
        def fail_once(path, content):
            if content != old: raise RuntimeError('copy_failed')
            replace(path, content)
        monkeypatch.setattr(m.base, 'replace', fail_once)
    else:
        ready = m.ready
        def fail_new(patched):
            if patched: raise RuntimeError('new_runtime_failed')
            return ready(patched)
        monkeypatch.setattr(m, 'ready', fail_new)
    assert m.run(req)['status'] == 'TEMPERATURE_PATCH_ROLLED_BACK'
    assert target.read_bytes() == old and end.read_bytes() == b'unchanged end V3'


def test_uncertain_stop_does_not_rewrite_or_guess_a_restart(tmp_path, monkeypatch):
    m, req, target, old, end, log = fixture(tmp_path, monkeypatch)
    def fail(): raise RuntimeError('stop_uncertain')
    monkeypatch.setattr(m.base, 'stop', fail)
    assert m.run(req)['status'] == 'NO_FILES_CHANGED_SERVICE_STATE_REQUIRES_CHECK'
    assert target.read_bytes() == old and not log
