"""Pinned retained-start installation via Python stdin, with exact rollback.

No heating, motion, filament command or synthetic homing. Only a cold service
restart and restoration of the pre-existing mesh/offsets with MOVE=0.
"""

import base64
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

NAMES = ('kctrl_start_policy.py', 'kctrl_start_context.py', 'kctrl_purge_guard.py',
         'kctrl_bin_motion.py', 'kctrl_start.py', 'k1-control-owned-start-print-v2.cfg')
DESTINATIONS = tuple('/usr/share/klipper/klippy/extras/' + name for name in NAMES[:-1]) + (
    '/usr/data/printer_data/config/' + NAMES[-1],)
BACKUP = Path('/usr/data/k1-control-v1/backups/retained-start-v1')
SERVICE = '/etc/init.d/S55klipper_service'
PIDFILE = Path('/var/run/klippy.pid')


def digest(path):
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError('unexpected_symlink_' + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def hashes(expected):
    actual = {p: digest(p) for p in expected}
    if actual != expected:
        raise RuntimeError('protected_file_drift: ' + ','.join(p for p in expected if actual[p] != expected[p]))
    return actual


def api(path, body=None):
    conn = http.client.HTTPConnection('127.0.0.1', 7125, timeout=5)
    try:
        conn.request('GET' if body is None else 'POST', path,
                     None if body is None else json.dumps(body),
                     {} if body is None else {'Content-Type': 'application/json'})
        response = conn.getresponse()
        data = json.loads(response.read())
        if response.status != 200 or 'error' in data:
            raise RuntimeError('local_api_failed')
        return data['result']
    finally:
        conn.close()


def state():
    available = set(api('/printer/objects/list')['objects'])
    extra = ''.join('&' + name for name in ('kctrl_start', 'kctrl_purge_guard', 'kctrl_bin_motion')
                    if name in available)
    return api('/printer/objects/query?webhooks=state&print_stats&virtual_sdcard=is_active'
               '&pause_resume&extruder=target,temperature&heater_bed=target,temperature'
               '&toolhead=homed_axes,position,print_time,estimated_print_time'
               '&motion_report=live_velocity,live_extruder_velocity&box&kctrl_end'
               '&bed_mesh=profile_name,probed_matrix&gcode_move=homing_origin'
               '&filament_switch_sensor+filament_sensor=filament_detected'
               '&filament_switch_sensor+filament_sensor_2=filament_detected' + extra)['status']


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def cold(s, installed=False, before_restart=False):
    assert s['webhooks']['state'] == 'ready', 'klipper_not_ready'
    assert s['print_stats']['state'] in ('standby', 'error', 'cancelled', 'complete'), 'job_busy'
    assert s['virtual_sdcard']['is_active'] is False, 'sd_active'
    assert s['pause_resume']['is_paused'] is False, 'paused'
    for heater in ('extruder', 'heater_bed'):
        assert s[heater]['target'] == 0, 'heaters_active'
        value = s[heater]['temperature']
        assert finite(value) and 0 <= value <= 50, 'not_cold'
    for key in ('live_velocity', 'live_extruder_velocity'):
        value = s['motion_report'][key]
        assert finite(value) and abs(value) < 1.e-6, 'motion_active'
    head = s['toolhead']
    assert len(head['position']) == 4 and all(finite(v) for v in head['position']), 'position_unknown'
    assert all(finite(head[k]) for k in ('print_time', 'estimated_print_time')), 'motion_clock_unknown'
    assert head['print_time'] <= head['estimated_print_time'] + .05, 'motion_queued'
    if before_restart:
        assert head['homed_axes'] == 'xyz', 'unexpected_preinstall_axes'
        # Current recovery park, outside the purge mechanism. Never use this
        # estimate as a homing reference after the service restart.
        assert 200 <= head['position'][0] <= 220 and 270 <= head['position'][1] <= 280, 'not_forward_parked'
        assert 35 <= head['position'][2] <= 315, 'park_clearance_unknown'
    else:
        assert head['homed_axes'] == '', 'restart_did_not_release_references'
    for sensor in ('filament_sensor', 'filament_sensor_2'):
        assert s['filament_switch_sensor ' + sensor]['filament_detected'] is True, 'retained_filament_lost'
    box = s['box']
    assert box['enable'] == 1 and box['state'] == 'connect', 'cfs_not_ready'
    for unit in ('T1', 'T2'):
        assert box[unit]['state'] == 'connect', 'cfs_unit_missing'
        assert box[unit]['filament'] == 'None', 'unexpected_engaged_route'
    for unit in ('T3', 'T4'):
        assert box.get(unit, {}).get('state') in (None, 'None', 'disconnect'), 'unexpected_cfs_unit'
    # The observed stale T0 belongs to the completed failed START_PRINT, not
    # to an active stock call: SD inactive, unpaused, cold, drained and stable.
    stale_start = (before_restart and s['print_stats']['state'] == 'error'
                   and '[after_tool_change]' in s['print_stats'].get('message', '')
                   and 'key165' in s['print_stats'].get('message', ''))
    assert box['t_command'] in (('', 'T0') if stale_start else ('',)), 'cfs_command_present'
    end = s['kctrl_end']
    assert end['enabled'] is True and end['phase'] == 'idle' and end['pending'] is False, 'end_busy'
    assert end['revision'] == 'end-rewind-confirm-v3', 'end_revision_changed'
    assert end['wrapped'] == ['CANCEL_PRINT', 'END_PRINT', 'START_PRINT'], 'end_wrappers_changed'
    if installed:
        start = s.get('kctrl_start') or {}
        assert start.get('enabled') is True and start.get('installed') is True, 'start_not_installed'
        assert start.get('phase') == 'idle' and start.get('failure') == '', 'start_not_idle'
        assert start.get('reference_valid') is False and start.get('reference') == 0, 'false_reference'
        assert start.get('revision') == 'retained-start-v1', 'start_revision_changed'
        assert s['kctrl_bin_motion']['installed'] is True, 'bin_adapter_missing'
        guard = s['kctrl_purge_guard']
        assert guard['installed'] is True and guard['minimum_z'] >= 30., 'bin_guard_missing'
    else:
        assert not s.get('kctrl_start'), 'unexpected_existing_start_owner'


def preflight(installed=False, before_restart=True):
    first = state()
    cold(first, installed, before_restart)
    time.sleep(.5)
    second = state()
    cold(second, installed, before_restart)
    for name in ('toolhead', 'kctrl_end', 'box'):
        keys = ('position', 'homed_axes') if name == 'toolhead' else ('phase', 'pending') if name == 'kctrl_end' else ('t_command',)
        assert all(first[name][key] == second[name][key] for key in keys), 'state_changed'
    return second


def service(action):
    result = subprocess.run([SERVICE, action], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    assert result.returncode == 0, 'service_' + action + '_failed'


def stop():
    pid = PIDFILE.read_text().strip()
    assert pid.isdigit(), 'invalid_pid'
    service('stop')
    deadline = time.monotonic() + 10
    while Path('/proc/' + pid).exists() and time.monotonic() < deadline:
        time.sleep(.2)
    assert not Path('/proc/' + pid).exists(), 'old_process_remains'
    return pid


def wait_ready(installed):
    deadline = time.monotonic() + 75
    last = ''
    while time.monotonic() < deadline:
        try:
            result = state()
            cold(result, installed=installed)
            return result
        except Exception as error:
            last = str(error)
            time.sleep(1)
    raise RuntimeError('cold_ready_not_confirmed: ' + last)


def restore_profile(before, installed):
    profile = before['bed_mesh']['profile_name']
    assert isinstance(profile, str) and re.fullmatch(r'[A-Za-z0-9_]+', profile), 'profile_invalid'
    origin = before['gcode_move']['homing_origin'][:3]
    assert len(origin) == 3 and all(finite(v) and abs(v) <= 2 for v in origin), 'offset_invalid'
    script = 'BED_MESH_PROFILE LOAD=' + profile
    script += '\nSET_GCODE_OFFSET_BASE X=%.6f Y=%.6f Z=%.6f MOVE=0' % tuple(origin)
    api('/printer/gcode/script', {'script': script})
    after = state()
    cold(after, installed)
    assert after['bed_mesh'] == before['bed_mesh'], 'mesh_not_restored'
    assert all(abs(a-b) < 1.e-6 for a,b in zip(after['gcode_move']['homing_origin'][:3], origin)), 'offset_not_restored'


def replace(path, content):
    target = Path(path)
    assert not target.is_symlink(), 'unexpected_symlink'
    temp = Path(str(target) + '.kctrl-retained-next')
    assert not temp.exists(), 'stale_stage_file'
    created = False
    try:
        with temp.open('xb') as stream:
            created = True
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(str(temp), 0o644)
        os.replace(str(temp), str(target))
    finally:
        if created and temp.exists():
            data = temp.read_bytes()
            assert content.startswith(data), 'stage_file_changed_by_other_writer'
            temp.unlink()


def rollback_files(files, before):
    # First validate every restoration source and target. Never partly restore
    # then discover that another file belongs to an unrelated intervention.
    for entry in files:
        path, old = entry['destination'], before[entry['destination']]
        assert digest(path) in (old, entry['sha256']), 'rollback_foreign_file'
        if old is not None:
            assert digest(BACKUP/(entry['name'] + '.before')) == old, 'backup_corrupt'
    for entry in reversed(files):
        path, old = entry['destination'], before[entry['destination']]
        if old is None:
            if Path(path).exists():
                Path(path).unlink()
        elif digest(path) != old:
            replace(path, (BACKUP/(entry['name'] + '.before')).read_bytes())
    hashes(before)


def receipt(status, **details):
    value = {'status': status, 'time': time.time(), **details}
    (BACKUP/'receipt.json').write_text(json.dumps(value), encoding='utf-8')
    return value


def run(request):
    manifest = request['manifest']
    assert manifest['name'] == 'retained-start-v1' and manifest['installer_ready'] is True, 'manifest_not_ready'
    files = manifest['files']
    assert tuple(e['name'] for e in files) == NAMES, 'unexpected_files'
    assert tuple(e['destination'] for e in files) == DESTINATIONS, 'unexpected_destinations'
    before_pins = manifest['before']
    after_pins, contents = dict(before_pins), {}
    for entry in files:
        path = entry['destination']
        assert entry['before_sha256'] == before_pins[path], 'baseline_inconsistent'
        data = base64.b64decode(request['payloads'][entry['name']], validate=True)
        assert hashlib.sha256(data).hexdigest() == entry['sha256'], 'payload_hash_changed'
        contents[path] = data
        after_pins[path] = entry['sha256']
    mode = request['mode']
    assert mode in ('preflight', 'install', 'validate', 'rollback'), 'invalid_mode'
    if mode == 'validate':
        hashes(after_pins)
        saved = json.loads((BACKUP/'state.before.json').read_text())
        for entry in files:
            if entry['before_sha256'] is not None:
                assert digest(BACKUP/(entry['name']+'.before')) == entry['before_sha256'], 'backup_corrupt'
        current = preflight(installed=True, before_restart=False)
        assert current['bed_mesh'] == saved['bed_mesh'], 'mesh_changed'
        assert all(abs(a-b) < 1.e-6 for a,b in zip(current['gcode_move']['homing_origin'][:3],
                                                 saved['gcode_move']['homing_origin'][:3])), 'offset_changed'
        return {'status': 'VALIDATED_COLD_OK', 'physical_validation': False,
                'head_loaded': True, 'homed_axes': '', 'end_revision': current['kctrl_end']['revision']}
    if mode == 'rollback':
        hashes(after_pins)
        preflight(installed=True, before_restart=False)
        saved = json.loads((BACKUP/'state.before.json').read_text())
        stop()
        rollback_files(files, before_pins)
        service('start')
        wait_ready(False)
        restore_profile(saved, False)
        return receipt('ROLLED_BACK', physical_validation=False)
    hashes(before_pins)
    original = preflight()
    assert not BACKUP.exists(), 'backup_already_exists'
    assert not any(Path(path + '.kctrl-retained-next').exists() for path in DESTINATIONS), 'stale_stage_file'
    if mode == 'preflight':
        return {'status': 'PREFLIGHT_OK', 'files': len(files), 'protected': len(before_pins),
                'head_loaded': True, 'targets': [0, 0], 'physical_validation': False}
    BACKUP.mkdir()
    (BACKUP/'state.before.json').write_text(json.dumps(original), encoding='utf-8')
    (BACKUP/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    for entry in files:
        if entry['before_sha256'] is not None:
            backup = BACKUP/(entry['name'] + '.before')
            backup.write_bytes(Path(entry['destination']).read_bytes())
            assert digest(backup) == entry['before_sha256'], 'backup_corrupt'
    receipt('BACKED_UP')
    stopped = False
    try:
        # Recheck idle/cold immediately before stopping, after the backups.
        cold(state(), before_restart=True)
        oldpid = stop()
        stopped = True
        hashes(before_pins)
        for entry in files:
            replace(entry['destination'], contents[entry['destination']])
        hashes(after_pins)
        receipt('FILES_REPLACED')
        service('start')
        wait_ready(True)
        assert PIDFILE.read_text().strip() != oldpid, 'process_not_replaced'
        restore_profile(original, True)
        hashes(after_pins)
        preflight(installed=True, before_restart=False)
        return receipt('INSTALLED_COLD_OK', physical_validation=False, files=len(files),
                       head_loaded=True, homed_axes='', end_revision='end-rewind-confirm-v3')
    except Exception as error:
        if not stopped:
            # No candidate file was written. Do not guess whether a failed
            # service operation actually stopped the old process.
            return receipt('NO_FILES_CHANGED_SERVICE_STATE_REQUIRES_CHECK', error=str(error))
        service('stop')
        rollback_files(files, before_pins)
        service('start')
        wait_ready(False)
        restore_profile(original, False)
        return receipt('INSTALL_FAILED_ROLLED_BACK', error=str(error), physical_validation=False)


if __name__ == '__main__':
    print(json.dumps(run(json.load(sys.stdin))), flush=True)
