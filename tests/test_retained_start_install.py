"""Exercise cold installation and rollback entirely in a temporary local tree."""
import base64
import copy
import importlib.util
import json
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / 'packages/k1-control-v1/retained-start-v1'


def load():
    spec = importlib.util.spec_from_file_location('retained_install_test', PACKAGE/'remote_install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def state(installed=False, restarted=False):
    return {
        'webhooks': {'state': 'ready'},
        'print_stats': {'state': 'standby' if restarted else 'error',
                        'message': 'key165 K1 Control [after_tool_change]'},
        'pause_resume': {'is_paused': False}, 'virtual_sdcard': {'is_active': False},
        'extruder': {'target': 0, 'temperature': 30}, 'heater_bed': {'target': 0, 'temperature': 27},
        'toolhead': {'homed_axes': '' if restarted else 'xyz',
                     'position': [0., 0., 0., 0.] if restarted else [210., 273., 60., 290.],
                     'print_time': 100., 'estimated_print_time': 101.},
        'motion_report': {'live_velocity': -3.55e-15, 'live_extruder_velocity': 0.},
        'filament_switch_sensor filament_sensor': {'filament_detected': True},
        'filament_switch_sensor filament_sensor_2': {'filament_detected': True},
        'box': {'enable': 1, 'state': 'connect', 't_command': '' if restarted else 'T0',
                'T1': {'state': 'connect', 'filament': 'None'},
                'T2': {'state': 'connect', 'filament': 'None'}},
        'kctrl_end': {'enabled': True, 'phase': 'idle', 'pending': False,
                      'revision': 'end-rewind-confirm-v3',
                      'wrapped': ['CANCEL_PRINT', 'END_PRINT', 'START_PRINT']},
        'kctrl_start': {'enabled': True, 'installed': True, 'phase': 'idle', 'failure': '',
                        'reference_valid': False, 'reference': 0,
                        'revision': 'retained-start-v1'} if installed else None,
        'kctrl_bin_motion': {'installed': True} if installed else None,
        'kctrl_purge_guard': {'installed': True, 'minimum_z': 30.} if installed else None,
        'bed_mesh': {'profile_name': 'k1_p001_t055_r001_n11x11', 'probed_matrix': [[.1, .2], [.3, .4]]},
        'gcode_move': {'homing_origin': [0., 0., -.04, 0.]},
    }


def fixture(tmp_path, monkeypatch):
    m = load()
    paths = [tmp_path / name for name in m.NAMES]
    paths[-1].write_bytes(b'original configuration with end V3 include')
    end = tmp_path/'protected-end.py'
    end.write_bytes(b'unchanged end V3')
    before = {str(p): m.digest(p) for p in [*paths, end]}
    payloads = {p.name: ('candidate ' + p.name).encode() for p in paths}
    files = [{'name': p.name, 'destination': str(p), 'before_sha256': before[str(p)],
              'sha256': m.hashlib.sha256(payloads[p.name]).hexdigest()} for p in paths]
    request = {'mode': 'install', 'manifest': {'name': 'retained-start-v1', 'installer_ready': True,
                'before': before, 'files': files},
               'payloads': {n: base64.b64encode(data).decode() for n,data in payloads.items()}}
    monkeypatch.setattr(m, 'DESTINATIONS', tuple(str(p) for p in paths))
    monkeypatch.setattr(m, 'BACKUP', tmp_path/'backup')
    pid = tmp_path/'pid'
    pid.write_text('100')
    monkeypatch.setattr(m, 'PIDFILE', pid)
    log = []
    current = {'restarted': False}
    def observe(): return state(installed=paths[0].exists(), restarted=current['restarted'])
    monkeypatch.setattr(m, 'state', observe)
    monkeypatch.setattr(m.time, 'sleep', lambda _: None)
    monkeypatch.setattr(m, 'stop', lambda: log.append('stop') or pid.read_text())
    def service(action):
        log.append(action)
        if action == 'start':
            current['restarted'] = True
            pid.write_text(str(int(pid.read_text()) + 1))
    monkeypatch.setattr(m, 'service', service)
    def ready(installed):
        result = observe()
        m.cold(result, installed)
        return result
    monkeypatch.setattr(m, 'wait_ready', ready)
    monkeypatch.setattr(m, 'api', lambda path, body: log.append(('api', path, body)))
    return m, request, paths, end, log


def test_observed_idle_failed_start_is_accepted_without_clearing_errors():
    load().cold(state(), before_restart=True)


@pytest.mark.parametrize('obj,key,value', [
    ('webhooks','state','shutdown'), ('print_stats','state','printing'),
    ('print_stats','message','unrelated fault'), ('pause_resume','is_paused',True),
    ('virtual_sdcard','is_active',True), ('extruder','target',150), ('heater_bed','target',55),
    ('extruder','temperature',55), ('heater_bed','temperature',float('nan')),
    ('toolhead','homed_axes',''), ('toolhead','position',[210.,305.,60.,0.]),
    ('toolhead','position',[210.,273.,29.,0.]), ('toolhead','print_time',102.),
    ('motion_report','live_velocity',.01), ('motion_report','live_extruder_velocity',.1),
    ('filament_switch_sensor filament_sensor','filament_detected',False),
    ('filament_switch_sensor filament_sensor_2','filament_detected',False),
    ('kctrl_end','pending',True), ('kctrl_end','revision','other'), ('box','t_command','T1'),
])
def test_preinstall_rejects_active_or_changed_physical_state(obj,key,value):
    s = state()
    s[obj][key] = value
    with pytest.raises(AssertionError): load().cold(s, before_restart=True)


@pytest.mark.parametrize('obj,key,value', [
    ('toolhead','homed_axes','xyz'), ('kctrl_start','reference_valid',True),
    ('kctrl_start','reference',1), ('kctrl_start','enabled',False),
    ('kctrl_start','phase','material'), ('kctrl_purge_guard','minimum_z',29.),
    ('kctrl_bin_motion','installed',False), ('box','t_command','T0'),
])
def test_post_restart_requires_fresh_idle_runtime_without_false_reference(obj,key,value):
    s = state(installed=True, restarted=True)
    s[obj][key] = value
    with pytest.raises(AssertionError): load().cold(s, installed=True)


def test_preflight_does_not_write_restart_or_send_gcode(tmp_path, monkeypatch):
    m, request, paths, end, log = fixture(tmp_path, monkeypatch)
    request['mode'] = 'preflight'
    assert m.run(request)['status'] == 'PREFLIGHT_OK'
    assert not any(p.exists() for p in paths[:-1])
    assert not m.BACKUP.exists() and log == []


def test_install_validate_and_rollback_preserve_old_config_and_end(tmp_path, monkeypatch):
    m, request, paths, end, log = fixture(tmp_path, monkeypatch)
    original = paths[-1].read_bytes()
    assert m.run(request)['status'] == 'INSTALLED_COLD_OK'
    assert all(p.exists() for p in paths)
    assert end.read_bytes() == b'unchanged end V3'
    assert (m.BACKUP/(paths[-1].name+'.before')).read_bytes() == original
    assert log[:2] == ['stop', 'start']
    script = log[2][2]['script']
    assert script.startswith('BED_MESH_PROFILE LOAD=') and script.endswith('MOVE=0')
    request['mode'] = 'validate'
    before_log = list(log)
    assert m.run(request)['status'] == 'VALIDATED_COLD_OK'
    assert log == before_log
    request['mode'] = 'rollback'
    assert m.run(request)['status'] == 'ROLLED_BACK'
    assert paths[-1].read_bytes() == original
    assert not any(p.exists() for p in paths[:-1])
    assert end.read_bytes() == b'unchanged end V3'


@pytest.mark.parametrize('failure', ['payload', 'protected', 'backup', 'stage', 'destinations'])
def test_invalid_input_refuses_before_stopping_or_replacing(tmp_path, monkeypatch, failure):
    m, request, paths, end, log = fixture(tmp_path, monkeypatch)
    original = paths[-1].read_bytes()
    if failure == 'payload': request['payloads'][paths[0].name] = base64.b64encode(b'bad').decode()
    if failure == 'protected': end.write_bytes(b'foreign update')
    if failure == 'backup': m.BACKUP.mkdir()
    if failure == 'stage': Path(str(paths[0])+'.kctrl-retained-next').write_bytes(b'existing')
    if failure == 'destinations': request['manifest']['files'][0]['destination'] = str(tmp_path/'foreign')
    with pytest.raises((AssertionError, RuntimeError)): m.run(request)
    assert paths[-1].read_bytes() == original and not paths[0].exists() and log == []


@pytest.mark.parametrize('failure_index', [0, 3, 5])
def test_partial_copy_failure_restores_exact_baseline(tmp_path, monkeypatch, failure_index):
    m, request, paths, end, log = fixture(tmp_path, monkeypatch)
    original = paths[-1].read_bytes()
    replace = m.replace
    fired = [False]
    def failing(path, content):
        if path == str(paths[failure_index]) and not fired[0]:
            fired[0] = True
            raise OSError('injected_copy_error')
        replace(path, content)
    monkeypatch.setattr(m, 'replace', failing)
    assert m.run(request)['status'] == 'INSTALL_FAILED_ROLLED_BACK'
    assert paths[-1].read_bytes() == original and not any(p.exists() for p in paths[:-1])
    assert end.read_bytes() == b'unchanged end V3'


def test_new_runtime_failure_rolls_back_and_restarts_old_runtime(tmp_path, monkeypatch):
    m, request, paths, end, log = fixture(tmp_path, monkeypatch)
    original = paths[-1].read_bytes()
    ready = m.wait_ready
    def fail(installed):
        if installed: raise RuntimeError('new_runtime_failed')
        return ready(installed)
    monkeypatch.setattr(m, 'wait_ready', fail)
    result = m.run(request)
    assert result['status'] == 'INSTALL_FAILED_ROLLED_BACK' and result['error'] == 'new_runtime_failed'
    assert log[:4] == ['stop', 'start', 'stop', 'start']
    assert paths[-1].read_bytes() == original and not any(p.exists() for p in paths[:-1])


def test_failed_service_stop_never_writes_candidate_or_guesses_restart(tmp_path, monkeypatch):
    m, request, paths, end, log = fixture(tmp_path, monkeypatch)
    original = paths[-1].read_bytes()
    def fail(): raise RuntimeError('service_state_unknown')
    monkeypatch.setattr(m, 'stop', fail)
    result = m.run(request)
    assert result['status'] == 'NO_FILES_CHANGED_SERVICE_STATE_REQUIRES_CHECK'
    assert paths[-1].read_bytes() == original and not any(p.exists() for p in paths[:-1])
    assert log == []


def test_corrupt_backup_or_foreign_candidate_is_not_overwritten(tmp_path, monkeypatch):
    m, request, paths, end, log = fixture(tmp_path, monkeypatch)
    m.run(request)
    paths[0].write_bytes(b'foreign')
    with pytest.raises(AssertionError, match='rollback_foreign_file'):
        m.rollback_files(request['manifest']['files'], request['manifest']['before'])
    assert paths[0].read_bytes() == b'foreign'
    paths[0].write_bytes(base64.b64decode(request['payloads'][paths[0].name]))
    (m.BACKUP/(paths[-1].name+'.before')).write_bytes(b'corrupt')
    with pytest.raises(AssertionError, match='backup_corrupt'):
        m.rollback_files(request['manifest']['files'], request['manifest']['before'])
    assert all(p.exists() for p in paths)


def test_atomic_replace_failure_cleans_only_owned_stage(tmp_path, monkeypatch):
    m = load()
    path = tmp_path/'target'
    path.write_bytes(b'old')
    def fail(*args): raise OSError('rename_failed')
    monkeypatch.setattr(m.os, 'replace', fail)
    with pytest.raises(OSError): m.replace(str(path), b'new')
    assert path.read_bytes() == b'old'
    assert not Path(str(path)+'.kctrl-retained-next').exists()


def test_installer_has_no_heat_axis_filament_or_print_command():
    text = (PACKAGE/'remote_install.py').read_text()
    for word in ('G28', 'G1 ', 'G0 ', 'M104', 'M109', 'M140', 'M190', 'M112', 'BOX_ERROR_CLEAR',
                 'BOX_RETRUDE', 'SET_KINEMATIC_POSITION', '/printer/print/start'):
        assert word not in text
