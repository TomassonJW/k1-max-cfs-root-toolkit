"""Reviewed one-file deployment on the printer, via Python stdin; no motion.

Input: JSON {manifest, payloads(base64), mode: preflight|install|rollback|validate}.
Local caller must pin this script and supply the reviewed manifest/payloads.
No network destination is configurable: only local Moonraker is queried.
"""
import base64
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

DESTINATIONS = ('/usr/share/klipper/klippy/extras/kctrl_end.py',)
BACKUP = Path('/usr/data/k1-control-v1/backups/cfs-end-rewind-confirm-v3')
SERVICE = '/etc/init.d/S55klipper_service'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def api(path, body=None):
    c = http.client.HTTPConnection('127.0.0.1', 7125, timeout=5)
    try:
        c.request('GET' if body is None else 'POST', path,
                  None if body is None else json.dumps(body),
                  {} if body is None else {'Content-Type': 'application/json'})
        r = c.getresponse()
        data = json.loads(r.read())
        if r.status != 200 or 'error' in data:
            raise RuntimeError('local_api_failed')
        return data['result']
    finally:
        c.close()


def state():
    return api('/printer/objects/query?webhooks=state&print_stats=state&virtual_sdcard=is_active&pause_resume&extruder=target,temperature&heater_bed=target,temperature&toolhead=homed_axes,position,print_time,estimated_print_time&kctrl_end&box&motion_report=live_velocity,live_extruder_velocity&bed_mesh=profile_name,probed_matrix&gcode_move=homing_origin&filament_switch_sensor+filament_sensor_2=filament_detected')['status']


def completed_rewind_failure(s):
    # Narrow recovery for the pinned V2 code: this failure is reachable only
    # AFTER three True ACKs and M400. The user independently confirmed rewind;
    # the current empty sensor and idle/cold checks are still mandatory.
    end = s['kctrl_end']
    return (end['revision'] == 'end-overlap-v2' and end['phase'] == 'failed'
            and end.get('failure') == 'rewind_not_confirmed'
            and end.get('thermal_failure') == '' and end.get('slot') == 'T1B'
            and end['pending'] is False)


def cold(s, before_restart=False):
    assert s['webhooks']['state'] == 'ready', 'klipper_not_ready'
    assert s['print_stats']['state'] in ('standby', 'cancelled', 'complete'), 'job_busy'
    assert s['virtual_sdcard']['is_active'] is False, 'sd_active'
    assert s['pause_resume']['is_paused'] is False, 'paused'
    assert s['extruder']['target'] == s['heater_bed']['target'] == 0, 'heaters_active'
    allowed = ('', 'xy', 'xyz') if before_restart else ('',)
    assert s['toolhead']['homed_axes'] in allowed, 'axes_referenced'
    for heater in ('extruder', 'heater_bed'):
        value = s[heater]['temperature']
        assert type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 50, 'not_cold'
    for value in s['toolhead']['position']:
        assert type(value) in (int, float) and math.isfinite(value), 'invalid_position'
    assert len(s['toolhead']['position']) == 4, 'invalid_position'
    for key in ('print_time', 'estimated_print_time'):
        value = s['toolhead'][key]
        assert type(value) in (int, float) and math.isfinite(value), 'invalid_motion_clock'
    assert s['toolhead']['print_time'] <= s['toolhead']['estimated_print_time'] + .05, 'motion_queued'
    for key in ('live_velocity', 'live_extruder_velocity'):
        value = s['motion_report'][key]
        assert type(value) in (int, float) and math.isfinite(value) and abs(value) < 1.e-6, 'motion_active'
    assert s['filament_switch_sensor filament_sensor_2']['filament_detected'] is False, 'head_loaded'
    assert s['box']['enable'] == 1 and s['box']['state'] == 'connect', 'cfs_not_ready'
    recovery = before_restart and completed_rewind_failure(s)
    assert s['box']['t_command'] in (('', 'T0') if recovery else ('',)), 'cfs_command_present'
    for unit in ('T1', 'T2'):
        allowed_slots = ('None', 'B') if recovery and unit == 'T1' else ('None',)
        assert s['box'][unit]['state'] == 'connect' and s['box'][unit]['filament'] in allowed_slots, 'cfs_route_present'
    for unit in ('T3', 'T4'):
        assert s['box'].get(unit, {}).get('state') in (None, 'None', 'disconnect'), 'unexpected_cfs_unit'
    assert not s['kctrl_end']['pending'], 'end_pending'


def service(action):
    result = subprocess.run([SERVICE, action], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=20)
    assert result.returncode == 0, 'service_' + action + '_failed'


def stop():
    pid = Path('/var/run/klippy.pid').read_text().strip()
    assert pid.isdigit()
    service('stop')
    until = time.monotonic() + 10
    while Path('/proc/' + pid).exists() and time.monotonic() < until:
        time.sleep(.2)
    assert not Path('/proc/' + pid).exists(), 'old_process_remains'
    return pid


def owner(s, revision, allow_recovery=False):
    assert s['kctrl_end']['enabled'] is True, 'owner_disabled'
    assert (s['kctrl_end']['phase'] == 'idle'
            or (allow_recovery and completed_rewind_failure(s))), 'owner_not_idle'
    assert s['kctrl_end']['revision'] == revision, 'owner_revision'
    assert s['kctrl_end']['physical_validation'] is False
    assert s['kctrl_end']['wrapped'] == ['CANCEL_PRINT', 'END_PRINT', 'START_PRINT']


def preflight_state(revision):
    first = state()
    cold(first, before_restart=True)
    owner(first, revision, allow_recovery=True)
    time.sleep(.5)
    second = state()
    cold(second, before_restart=True)
    owner(second, revision, allow_recovery=True)
    for key in ('homed_axes', 'position'):
        assert first['toolhead'][key] == second['toolhead'][key], 'position_changed'
    assert first['kctrl_end'] == second['kctrl_end'], 'owner_changed'
    assert first['box']['t_command'] == second['box']['t_command'], 'command_changed'
    for unit in ('T1', 'T2'):
        assert first['box'][unit]['filament'] == second['box'][unit]['filament'], 'route_changed'
    return second


def wait_ready(revision):
    until = time.monotonic() + 90
    last = ''
    while time.monotonic() < until:
        try:
            s = state()
            cold(s)
            owner(s, revision)
            return s
        except Exception as error:
            last = str(error)
        time.sleep(1)
    raise RuntimeError('cold_start_not_validated: ' + last)


def restore_coordinates(before):
    # Software state only; axes remain unreferenced. No homing or probing.
    profile = before['bed_mesh']['profile_name']
    assert isinstance(profile, str)
    if profile:
        assert re.fullmatch(r'[A-Za-z0-9_]+', profile)
        command = 'BED_MESH_PROFILE LOAD=' + profile
    else:
        command = 'BED_MESH_CLEAR'
    origin = before['gcode_move']['homing_origin'][:3]
    assert len(origin) == 3 and all(type(v) in (int, float) and abs(v) <= 2 for v in origin)
    command += '\nSET_GCODE_OFFSET_BASE X=%.6f Y=%.6f Z=%.6f MOVE=0' % tuple(origin)
    api('/printer/gcode/script', {'script': command})
    after = state()
    cold(after)
    assert after['bed_mesh']['profile_name'] == profile
    assert after['bed_mesh']['probed_matrix'] == before['bed_mesh']['probed_matrix'], 'mesh_changed'
    assert all(abs(a-b)<1.e-6 for a,b in zip(after['gcode_move']['homing_origin'][:3],origin))


def hashes(expected):
    actual = {p: digest(p) for p in expected}
    assert actual == expected, 'protected_file_drift'
    return actual


def replace(path, content):
    temp = Path(path + '.kctrl-overlap-next')
    assert not temp.exists(), 'stale_stage_file'
    with temp.open('xb') as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(str(temp), 0o644)
    os.replace(str(temp), path)


def run(request):
    manifest = request['manifest']
    assert manifest['name'] == 'cfs-end-rewind-confirm-v3'
    files = manifest['files']
    assert tuple(f['destination'] for f in files) == DESTINATIONS
    before_pins = manifest['before']
    after_pins = dict(before_pins)
    contents = {}
    for f in files:
        content = base64.b64decode(request['payloads'][f['name']], validate=True)
        assert hashlib.sha256(content).hexdigest() == f['sha256']
        after_pins[f['destination']] = f['sha256']
        contents[f['destination']] = content
    if request['mode'] == 'preflight':
        hashes(before_pins)
        before = preflight_state('end-overlap-v2')
        assert not BACKUP.exists(), 'backup_already_exists'
        return {'status': 'PREFLIGHT_OK', 'axes': before['toolhead']['homed_axes'],
                'protected_files': len(before_pins), 'physical_validation': False}
    if request['mode'] == 'validate':
        hashes(after_pins)
        after = wait_ready('end-rewind-confirm-v3')
        before = json.loads((BACKUP/'state.before.json').read_text())
        for f in files:
            assert digest(BACKUP/(f['name']+'.before')) == before_pins[f['destination']]
        assert after['bed_mesh'] == before['bed_mesh'], 'mesh_changed'
        assert all(abs(a-b)<1.e-6 for a,b in zip(after['gcode_move']['homing_origin'][:3],before['gcode_move']['homing_origin'][:3]))
        return {'status': 'VALIDATED_COLD_OK', 'revision': after['kctrl_end']['revision'],
                'protected_files': len(before_pins), 'physical_validation': False,
                'axes': after['toolhead']['homed_axes'], 'targets': [0, 0],
                'mesh_profile': after['bed_mesh']['profile_name']}
    if request['mode'] == 'rollback':
        hashes(after_pins)
        before = json.loads((BACKUP/'state.before.json').read_text())
        preflight_state('end-rewind-confirm-v3')
        for f in files:
            assert digest(BACKUP/(f['name']+'.before')) == before_pins[f['destination']]
        oldpid = stop()
        for f in files:
            original = BACKUP/(f['name'] + '.before')
            assert digest(original) == before_pins[f['destination']]
            replace(f['destination'], original.read_bytes())
        service('start')
        wait_ready('end-overlap-v2')
        restore_coordinates(before)
        hashes(before_pins)
        return {'status': 'ROLLED_BACK', 'backup': str(BACKUP)}
    assert request['mode'] == 'install'
    hashes(before_pins)
    before = preflight_state('end-overlap-v2')
    assert not BACKUP.exists(), 'backup_already_exists'
    BACKUP.mkdir()
    (BACKUP/'state.before.json').write_text(json.dumps(before), encoding='utf-8')
    for f in files:
        shutil.copy2(f['destination'], str(BACKUP/(f['name']+'.before')))
        assert digest(BACKUP/(f['name']+'.before')) == before_pins[f['destination']]
    try:
        oldpid = stop()
        for f in files:
            replace(f['destination'], contents[f['destination']])
        service('start')
        wait_ready('end-rewind-confirm-v3')
        assert Path('/var/run/klippy.pid').read_text().strip() != oldpid
        restore_coordinates(before)
        hashes(after_pins)
        # Independent second observation after CFS reconnection.
        after = wait_ready('end-rewind-confirm-v3')
        return {'status': 'INSTALLED_COLD_OK', 'enabled': True,
                'revision': after['kctrl_end']['revision'], 'backup': str(BACKUP),
                'changed_files': list(DESTINATIONS), 'protected_files': len(before_pins),
                'physical_validation': False, 'new_process_confirmed': True,
                'mesh_profile': after['bed_mesh']['profile_name'],
                'homing_origin': after['gcode_move']['homing_origin'],
                'targets': [after['extruder']['target'],after['heater_bed']['target']],
                'axes': after['toolhead']['homed_axes']}
    except Exception as error:
        service('stop')
        for f in files:
            original = BACKUP/(f['name']+'.before')
            assert digest(original) == before_pins[f['destination']]
            replace(f['destination'], original.read_bytes())
        service('start')
        wait_ready('end-overlap-v2')
        restore_coordinates(before)
        hashes(before_pins)
        return {'status': 'INSTALL_FAILED_ROLLED_BACK', 'error': str(error), 'backup': str(BACKUP)}

if __name__ == '__main__':
    print(json.dumps(run(json.load(sys.stdin))))
