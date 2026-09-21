"""Offline install package: no printer and no shell execution."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages/k1-control-v1/end-after-refill-install-disabled-v1'
spec = importlib.util.spec_from_file_location('end_bundle', PACKAGE / 'build_package.py')
MOD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MOD)
MANIFEST = json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))


def cold():
    return {
        'webhooks': {'state': 'ready'}, 'print_stats': {'state': 'cancelled'},
        'pause_resume': {'is_paused': False},
        'extruder': {'target': 0}, 'heater_bed': {'target': 0},
        'toolhead': {'homed_axes': ''},
        'filament_switch_sensor filament_sensor_2': {'filament_detected': False},
        'box': {'enable': 1, 'state': 'connect',
                'T1': {'state': 'connect', 'filament': 'None'},
                'T2': {'state': 'connect', 'filament': 'None'}},
        'bed_mesh': {'profile_name': MOD.MESH, 'mesh_matrix': [[0, 0], [0, 0]]},
        'gcode_move': {'homing_origin': [0, 0, -0.04]},
        'kctrl_print_gate': {'wrapped': 1, 'pending': 0},
    }


def test_frozen_payloads_and_additive_include():
    payload = MOD.payloads(MANIFEST)
    assert len(payload) == 7
    source = ROOT / 'packages/k1-control-v1/owned-start-print-v2/k1-control-owned-start-print-v2.cfg'
    patched = payload[source.name]
    assert patched.startswith(source.read_bytes())
    assert patched.count(b'[include k1-control-owned-end-candidate.cfg]') == 1
    assert b'enabled: false' in payload['k1-control-owned-end-candidate.cfg']
    assert b'enabled: true' not in payload['k1-control-owned-end-candidate.cfg']


def test_source_drift_refused_before_output(tmp_path):
    altered = copy.deepcopy(MANIFEST)
    altered['files'][0]['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='payload drift'):
        MOD.payloads(altered)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('mode', ['changed', 'missing', 'occupied_new_path'])
def test_preflight_hashes_require_fresh_exact_evidence(mode):
    observed = dict(MANIFEST['before'])
    assert MOD.check_hashes(MANIFEST, observed) is None
    path = next(iter(observed))
    if mode == 'missing':
        del observed[path]
    else:
        observed[path] = 'unexpected'
    with pytest.raises(ValueError, match='baseline mismatch'):
        MOD.check_hashes(MANIFEST, observed)


def test_plan_backups_and_rollback_are_exact_not_activation():
    plan = MOD.operation_plan(MANIFEST)
    assert plan['executable'] is False
    assert plan['activation_permitted'] is False
    assert plan['install'][0] == MOD.SERVICE + ' stop'
    assert plan['install'][-1] == MOD.SERVICE + ' start'
    assert 'owned-start-print-v2.cfg' in plan['install'][-2]
    for entry in MANIFEST['files']:
        if entry['before_sha256'] is None:
            assert 'rm -f ' + entry['destination'] in plan['rollback']
        else:
            assert any(entry['name'] + '.before' in step for step in plan['backup'])
            assert any(entry['name'] + '.before' in step for step in plan['rollback'])
    commands = '\n'.join(plan['install'] + plan['rollback'])
    assert 'enabled: true' not in commands
    assert 'BOX_' not in commands and 'START_PRINT' not in commands
    assert not any('printer.cfg' in line for line in plan['install'])


def test_cold_install_then_rollback_snapshot_contract():
    before = cold()
    assert MOD.validate_cold(before)
    installed = copy.deepcopy(before)
    end = {'enabled': False, 'phase': 'disabled', 'pending': False,
           'job_epoch': 0, 'failure': '', 'thermal_failure': ''}
    installed['kctrl_end'] = end
    installed['kctrl_print_gate']['end'] = dict(end)
    assert MOD.validate_cold(installed, installed=True, reference=before)
    assert MOD.validate_cold(before, reference=before)


@pytest.mark.parametrize('object_name,key,value', [
    ('extruder', 'target', 200), ('heater_bed', 'target', 55),
    ('print_stats', 'state', 'printing'), ('pause_resume', 'is_paused', True),
    ('toolhead', 'homed_axes', 'xyz'),
    ('filament_switch_sensor filament_sensor_2', 'filament_detected', True),
    ('bed_mesh', 'profile_name', 'default'),
    ('gcode_move', 'homing_origin', [0, 0, 0]),
    ('kctrl_print_gate', 'pending', 1),
])
def test_cold_check_rejects_unsafe_or_drifted_state(object_name, key, value):
    data = cold()
    data[object_name][key] = value
    with pytest.raises(ValueError):
        MOD.validate_cold(data)


def test_cold_check_rejects_missing_fields_and_mesh_drift():
    data = cold()
    del data['extruder']['target']
    with pytest.raises(ValueError):
        MOD.validate_cold(data)
    data = cold()
    data['bed_mesh']['mesh_matrix'][0][0] = 0.5
    with pytest.raises(ValueError, match='mesh changed'):
        MOD.validate_cold(data, reference=cold())


def test_installed_status_must_be_disabled_and_forwarded():
    data = cold()
    data['kctrl_end'] = {'enabled': True, 'phase': 'idle', 'pending': False, 'job_epoch': 0}
    with pytest.raises(ValueError, match='not inert'):
        MOD.validate_cold(data, installed=True)
    data['kctrl_end'].update(enabled=False, phase='disabled')
    with pytest.raises(ValueError, match='not connected'):
        MOD.validate_cold(data, installed=True)


def test_reviewed_plan_matches_generator():
    reviewed = json.loads((PACKAGE / 'plan.json').read_text(encoding='utf-8'))
    assert reviewed == MOD.operation_plan(MANIFEST)


def test_actual_recovered_idle_with_cleared_geometry():
    status = cold()
    status['bed_mesh'] = {'profile_name': '', 'mesh_matrix': [[]]}
    status['gcode_move']['homing_origin'] = [0, 0, -2.7755575615628914e-17, 0]
    assert MOD.validate_cold(status)
    after = copy.deepcopy(status)
    after['gcode_move']['homing_origin'][2] = 0.0
    assert MOD.validate_cold(after, reference=status)
    after['bed_mesh']['profile_name'] = MOD.MESH
    with pytest.raises(ValueError):
        MOD.validate_cold(after, reference=status)
