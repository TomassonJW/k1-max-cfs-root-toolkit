"""Cold deployment from active V1; no printer access."""
import base64
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages/k1-control-v1/end-rewind-confirm-v3'


def load(name):
    spec = importlib.util.spec_from_file_location(name, PACKAGE / (name + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def state(revision='end-overlap-v2', axes='xy'):
    return {
        'webhooks': {'state': 'ready'}, 'print_stats': {'state': 'standby'},
        'pause_resume': {'is_paused': False}, 'virtual_sdcard': {'is_active': False},
        'extruder': {'target': 0, 'temperature': 29},
        'heater_bed': {'target': 0, 'temperature': 28},
        'toolhead': {'homed_axes': axes, 'position': [38, 100, 0, 0], 'print_time': 100., 'estimated_print_time': 101.},
        'motion_report': {'live_velocity': 0, 'live_extruder_velocity': 0},
        'filament_switch_sensor filament_sensor_2': {'filament_detected': False},
        'box': {'enable': 1, 'state': 'connect', 't_command': '',
                'T1': {'state': 'connect', 'filament': 'None'},
                'T2': {'state': 'connect', 'filament': 'None'}},
        'kctrl_end': {'enabled': True, 'pending': False, 'phase': 'idle',
                      'revision': revision, 'physical_validation': False, 'failure': '', 'thermal_failure': '', 'slot': None,
                      'wrapped': ['CANCEL_PRINT', 'END_PRINT', 'START_PRINT']},
        'bed_mesh': {'profile_name': 'default', 'probed_matrix': [[0, .1], [.2, .3]]},
        'gcode_move': {'homing_origin': [0, 0, -.04, 0]},
    }


def test_manifest_reproduces_active_v1_baseline_and_one_file():
    manifest = json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest == load('build_manifest').build()
    old = json.loads((PACKAGE.parent / 'end-overlap-v2/manifest.json').read_text(encoding='utf-8'))
    expected = dict(old['before'])
    expected.update({f['destination']: f['sha256'] for f in old['files']})
    assert manifest['before'] == expected
    assert len(manifest['before']) == 22 and len(manifest['files']) == 1
    assert manifest['files'][0]['destination'].endswith('/kctrl_end.py')


@pytest.mark.parametrize('axes', ['', 'xy', 'xyz'])
def test_pre_restart_allows_idle_xy_without_a_motion(axes):
    m = load('remote_install')
    m.cold(state(axes=axes), before_restart=True)


@pytest.mark.parametrize('obj,key,value', [
    ('webhooks', 'state', 'shutdown'), ('print_stats', 'state', 'printing'),
    ('pause_resume', 'is_paused', True), ('extruder', 'target', 200),
    ('heater_bed', 'target', 55), ('extruder', 'temperature', 51),
    ('heater_bed', 'temperature', float('nan')), ('virtual_sdcard', 'is_active', True),
    ('toolhead', 'position', [0, 0, float('nan'), 0]),
    ('motion_report', 'live_velocity', 1), ('motion_report', 'live_extruder_velocity', -2),
    ('filament_switch_sensor filament_sensor_2', 'filament_detected', True),
    ('box', 't_command', 'T1B'), ('kctrl_end', 'pending', True),
])
def test_unsafe_state_rejected(obj, key, value):
    m = load('remote_install')
    s = state()
    s[obj][key] = value
    with pytest.raises(AssertionError):
        m.cold(s, before_restart=True)


def test_post_restart_cannot_keep_xy_reference():
    with pytest.raises(AssertionError, match='axes_referenced'):
        load('remote_install').cold(state())


def test_two_samples_reject_position_change(monkeypatch):
    m = load('remote_install')
    first, second = state(), state()
    second['toolhead']['position'][0] += 1
    samples = iter([first, second])
    monkeypatch.setattr(m, 'state', lambda: next(samples))
    monkeypatch.setattr(m.time, 'sleep', lambda _: None)
    with pytest.raises(AssertionError, match='position_changed'):
        m.preflight_state('end-overlap-v2')


def fixture(tmp_path, monkeypatch):
    m = load('remote_install')
    path = tmp_path / 'kctrl_end.py'
    path.write_bytes(b'before')
    protected = tmp_path / 'config.cfg'
    protected.write_bytes(b'unchanged')
    pins = {str(p): m.digest(p) for p in (path, protected)}
    request = {'mode': 'install', 'manifest': {'name': 'cfs-end-rewind-confirm-v3',
               'before': pins, 'files': [{'name': path.name, 'destination': str(path),
                                         'sha256': m.hashlib.sha256(b'after').hexdigest()}]},
               'payloads': {path.name: base64.b64encode(b'after').decode()}}
    monkeypatch.setattr(m, 'DESTINATIONS', (str(path),))
    monkeypatch.setattr(m, 'BACKUP', tmp_path / 'backup')
    pid = tmp_path / 'pid'
    pid.write_text('new')
    original_path = m.Path
    monkeypatch.setattr(m, 'Path', lambda p: pid if p == '/var/run/klippy.pid' else original_path(p))
    log = []
    monkeypatch.setattr(m, 'state', lambda: state())
    monkeypatch.setattr(m.time, 'sleep', lambda _: None)
    monkeypatch.setattr(m, 'stop', lambda: log.append('stop') or 'old')
    monkeypatch.setattr(m, 'service', lambda a: log.append(a))
    def ready(revision):
        assert path.read_bytes() == (b'after' if revision == 'end-rewind-confirm-v3' else b'before')
        return state(revision, '')
    monkeypatch.setattr(m, 'wait_ready', ready)
    monkeypatch.setattr(m, 'restore_coordinates', lambda s: log.append('restore_MOVE_0'))
    return m, request, path, protected, log


def test_preflight_is_read_only(tmp_path, monkeypatch):
    m, request, path, _, log = fixture(tmp_path, monkeypatch)
    request['mode'] = 'preflight'
    assert m.run(request)['status'] == 'PREFLIGHT_OK'
    assert path.read_bytes() == b'before' and not m.BACKUP.exists() and log == []


def test_install_and_independent_validation(tmp_path, monkeypatch):
    m, request, path, protected, log = fixture(tmp_path, monkeypatch)
    assert m.run(request)['status'] == 'INSTALLED_COLD_OK'
    assert path.read_bytes() == b'after' and protected.read_bytes() == b'unchanged'
    assert (m.BACKUP / 'kctrl_end.py.before').read_bytes() == b'before'
    assert log == ['stop', 'start', 'restore_MOVE_0']
    request['mode'] = 'validate'
    assert m.run(request)['status'] == 'VALIDATED_COLD_OK'
    assert log == ['stop', 'start', 'restore_MOVE_0']


@pytest.mark.parametrize('failure', ['pin', 'payload', 'revision', 'backup'])
def test_preflight_failure_has_no_mutation(tmp_path, monkeypatch, failure):
    m, request, path, protected, log = fixture(tmp_path, monkeypatch)
    if failure == 'pin': protected.write_bytes(b'foreign')
    if failure == 'payload': request['payloads'][path.name] = base64.b64encode(b'bad').decode()
    if failure == 'revision': monkeypatch.setattr(m, 'state', lambda: state('unexpected'))
    if failure == 'backup': m.BACKUP.mkdir()
    with pytest.raises(AssertionError): m.run(request)
    assert path.read_bytes() == b'before' and log == []


def test_failed_new_runtime_rolls_back_to_active_old_runtime(tmp_path, monkeypatch):
    m, request, path, _, log = fixture(tmp_path, monkeypatch)
    ready = m.wait_ready
    def fail_new(revision):
        if revision == 'end-rewind-confirm-v3': raise RuntimeError('injected')
        return ready(revision)
    monkeypatch.setattr(m, 'wait_ready', fail_new)
    assert m.run(request)['status'] == 'INSTALL_FAILED_ROLLED_BACK'
    assert path.read_bytes() == b'before'
    assert log == ['stop', 'start', 'stop', 'start', 'restore_MOVE_0']


def test_explicit_rollback(tmp_path, monkeypatch):
    m, request, path, _, log = fixture(tmp_path, monkeypatch)
    m.run(request)
    monkeypatch.setattr(m, 'state', lambda: state('end-rewind-confirm-v3', ''))
    request['mode'] = 'rollback'
    assert m.run(request)['status'] == 'ROLLED_BACK'
    assert path.read_bytes() == b'before'


def test_coordinate_restore_sends_only_nonmoving_state(monkeypatch):
    m = load('remote_install')
    before, after = state(), state(axes='')
    calls = []
    monkeypatch.setattr(m, 'api', lambda path, body: calls.append((path, body)))
    monkeypatch.setattr(m, 'state', lambda: after)
    m.restore_coordinates(before)
    assert calls == [('/printer/gcode/script', {'script':
        'BED_MESH_PROFILE LOAD=default\nSET_GCODE_OFFSET_BASE X=0.000000 Y=0.000000 Z=-0.040000 MOVE=0'})]
    after['bed_mesh']['probed_matrix'][0][0] = .8
    with pytest.raises(AssertionError, match='mesh_changed'): m.restore_coordinates(before)


def test_installer_has_no_physical_gcode():
    source = (PACKAGE / 'remote_install.py').read_text(encoding='utf-8')
    for forbidden in ('G28', 'G1 ', 'G0 ', 'M104', 'M109', 'M140', 'M190', 'BOX_RETRUDE', '/printer/print/start'):
        assert forbidden not in source


def failed_completed_rewind():
    s = state(axes='xyz')
    s['kctrl_end'].update(phase='failed', failure='rewind_not_confirmed', slot='T1B')
    s['box']['t_command'] = 'T0'
    s['box']['T1']['filament'] = 'B'
    s['motion_report']['live_velocity'] = -3.552713678800501e-15
    return s


def test_exact_real_failure_is_recoverable_cold_without_motion():
    m = load('remote_install')
    s = failed_completed_rewind()
    m.cold(s, before_restart=True)
    m.owner(s, 'end-overlap-v2', allow_recovery=True)
    with pytest.raises(AssertionError): m.cold(s)


@pytest.mark.parametrize('obj,key,value', [
    ('kctrl_end', 'failure', 'cfs_ack_not_confirmed'),
    ('kctrl_end', 'thermal_failure', 'unknown'),
    ('kctrl_end', 'slot', 'T1A'), ('kctrl_end', 'pending', True),
    ('kctrl_end', 'phase', 'rewinding'), ('kctrl_end', 'revision', 'unknown'),
    ('filament_switch_sensor filament_sensor_2', 'filament_detected', True),
    ('virtual_sdcard', 'is_active', True), ('toolhead', 'print_time', 102.),
    ('toolhead', 'print_time', float('nan')),
    ('motion_report', 'live_velocity', float('nan')),
    ('motion_report', 'live_extruder_velocity', 0.01),
    ('box', 't_command', 'T5'),
])
def test_narrow_recovery_rejects_unproven_or_active_state(obj,key,value):
    s = failed_completed_rewind()
    s[obj][key] = value
    with pytest.raises(AssertionError): load('remote_install').cold(s, before_restart=True)


@pytest.mark.parametrize('unit,slot', [('T1','A'), ('T2','D')])
def test_narrow_recovery_rejects_changed_route(unit,slot):
    s = failed_completed_rewind()
    s['box'][unit]['filament'] = slot
    with pytest.raises(AssertionError): load('remote_install').cold(s, before_restart=True)
