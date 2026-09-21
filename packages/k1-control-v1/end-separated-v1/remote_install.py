"""Reviewed two-file deployment on the printer, via Python stdin; no motion.

Input: JSON {manifest, payloads(base64), mode: install|rollback}.
Local caller must pin this script and supply the reviewed manifest/payloads.
No network destination is configurable: only local Moonraker is queried.
"""
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

DESTINATIONS = ('/usr/share/klipper/klippy/extras/kctrl_end.py',
                '/usr/data/printer_data/config/k1-control-owned-end-candidate.cfg')
BACKUP = Path('/usr/data/k1-control-v1/backups/cfs-separated-end-v1')
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
    return api('/printer/objects/query?webhooks=state&print_stats=state&pause_resume&extruder=target&heater_bed=target&toolhead=homed_axes,position&kctrl_end&box&bed_mesh=profile_name&gcode_move=homing_origin&filament_switch_sensor+filament_sensor_2=filament_detected')['status']


def cold(s):
    assert s['webhooks']['state'] == 'ready', 'klipper_not_ready'
    assert s['print_stats']['state'] in ('standby', 'cancelled', 'complete'), 'job_busy'
    assert s['pause_resume']['is_paused'] is False, 'paused'
    assert s['extruder']['target'] == s['heater_bed']['target'] == 0, 'heaters_active'
    assert s['toolhead']['homed_axes'] == '', 'axes_referenced'
    assert s['filament_switch_sensor filament_sensor_2']['filament_detected'] is False, 'head_loaded'
    assert s['box']['enable'] == 1 and s['box']['state'] == 'connect', 'cfs_not_ready'
    assert s['box']['t_command'] == '', 'cfs_command_present'
    for unit in ('T1', 'T2'):
        assert s['box'][unit]['state'] == 'connect' and s['box'][unit]['filament'] == 'None', 'cfs_route_present'
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


def wait_ready(enabled):
    until = time.monotonic() + 90
    last = ''
    while time.monotonic() < until:
        try:
            s = state()
            cold(s)
            assert s['kctrl_end']['enabled'] is enabled
            assert s['kctrl_end']['phase'] == ('idle' if enabled else 'disabled')
            if enabled:
                assert s['kctrl_end']['revision'] == 'separated-end-v1'
                assert s['kctrl_end']['wrapped'] == ['CANCEL_PRINT', 'END_PRINT', 'START_PRINT']
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
    assert all(abs(a-b)<1.e-6 for a,b in zip(after['gcode_move']['homing_origin'][:3],origin))


def hashes(expected):
    actual = {p: digest(p) for p in expected}
    assert actual == expected, 'protected_file_drift'
    return actual


def replace(path, content):
    temp = Path(path + '.kctrl-separated-next')
    assert not temp.exists(), 'stale_stage_file'
    with temp.open('xb') as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(str(temp), 0o644)
    os.replace(str(temp), path)


def run(request):
    manifest = request['manifest']
    assert manifest['name'] == 'cfs-separated-end-v1'
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
    if request['mode'] == 'rollback':
        hashes(after_pins)
        before = json.loads((BACKUP/'state.before.json').read_text())
        cold(state())
        oldpid = stop()
        for f in files:
            original = BACKUP/(f['name'] + '.before')
            assert digest(original) == before_pins[f['destination']]
            replace(f['destination'], original.read_bytes())
        service('start')
        wait_ready(False)
        restore_coordinates(before)
        hashes(before_pins)
        return {'status': 'ROLLED_BACK', 'backup': str(BACKUP)}
    assert request['mode'] == 'install'
    hashes(before_pins)
    before = state()
    cold(before)
    assert before['kctrl_end']['enabled'] is False
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
        wait_ready(True)
        assert Path('/var/run/klippy.pid').read_text().strip() != oldpid
        restore_coordinates(before)
        hashes(after_pins)
        # Independent second observation after CFS reconnection.
        after = wait_ready(True)
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
        wait_ready(False)
        restore_coordinates(before)
        hashes(before_pins)
        return {'status': 'INSTALL_FAILED_ROLLED_BACK', 'error': str(error), 'backup': str(BACKUP)}

if __name__ == '__main__':
    print(json.dumps(run(json.load(sys.stdin))))
