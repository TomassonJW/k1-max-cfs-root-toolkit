"""Set the Creality log level from 1 (debug) to 3 (warning), idle only.

Run on the printer by `python3 -`; deploy.py puts REQUEST_B64 in front of
this source. One file changes, by one digit: log_config.json, which the
Creality programs read when they start (document 103, option 1). Nothing is
restarted here: the new level applies at the next power-on, done by Thomas.
No Klipper command, no heating, no motion, no filament command.

The vendor file is not shipped: the manifest pins its exact fingerprint
before and after, and the candidate is computed here from the bytes read.
Klipper is read through its own socket, /tmp/klippy_uds, only to prove rest.
"""

import base64
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import socket
import stat
import time

NAME = 'flash-log-level-v1'
TARGET = '/usr/data/creality/userdata/log/log_config.json'
BACKUP = Path('/usr/data/k1-control-v1/backups/' + NAME)
STAGE = TARGET + '.kctrl-next'
SOCKET = '/tmp/klippy_uds'
OLD = b'"log_level":1,'
NEW = b'"log_level":3,'
IDLE_PRINT = ('standby', 'cancelled', 'complete', 'error')
# Allowed rather than refused phases: a phase added later counts as busy.
END_REST = ('idle', 'disabled', 'complete', 'failed')
START_REST = ('idle', 'complete')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError('unexpected_symlink_' + str(path))
    return sha(path.read_bytes()) if path.exists() else None


def edited(before):
    """The same bytes with the level digit changed, nothing else."""
    assert before.count(OLD) == 1, 'level_line_not_unique'
    data = before.replace(OLD, NEW)
    old, new = json.loads(before.decode('utf-8')), json.loads(data.decode('utf-8'))
    assert old.get('log_level') == 1 and new.get('log_level') == 3, 'level_not_changed'
    old.pop('log_level')
    new.pop('log_level')
    assert old == new, 'other_settings_changed'
    return data


def klippy(method, params):
    conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    conn.settimeout(5)
    try:
        conn.connect(SOCKET)
        conn.sendall((json.dumps({'id': 1, 'method': method, 'params': params})
                      + '\x03').encode())
        data = b''
        while not data.endswith(b'\x03'):
            chunk = conn.recv(65536)
            if not chunk:
                raise RuntimeError('klippy_socket_closed')
            data += chunk
    finally:
        conn.close()
    reply = json.loads(data[:-1].decode())
    if 'error' in reply:
        raise RuntimeError('klippy_error: ' + str(reply['error'])[:200])
    return reply['result']


QUERY = {
    'webhooks': ['state'],
    'print_stats': ['state'],
    'virtual_sdcard': ['is_active'],
    'pause_resume': ['is_paused'],
    'idle_timeout': ['state'],
    'extruder': ['target'],
    'heater_bed': ['target'],
    'toolhead': ['print_time', 'estimated_print_time'],
    'motion_report': ['live_velocity', 'live_extruder_velocity'],
    'box': ['t_command'],
    'kctrl_end': ['phase', 'pending'],
    'kctrl_start': ['phase'],
}


def state():
    return klippy('objects/query', {'objects': QUERY})['status']


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def idle(s):
    """Nothing prints, heats, moves or changes filament; the owners are at rest.

    Revisions are not pinned: the other K1 Control deliveries may change
    them, and none of them reads this file.
    """
    assert s['webhooks']['state'] == 'ready', 'klipper_not_ready'
    assert s['print_stats']['state'] in IDLE_PRINT, 'job_busy'
    assert s['virtual_sdcard']['is_active'] is False, 'sd_active'
    assert s['pause_resume']['is_paused'] is False, 'paused'
    assert s['idle_timeout']['state'] != 'Printing', 'idle_timeout_printing'
    for heater in ('extruder', 'heater_bed'):
        assert s[heater]['target'] == 0, 'heater_target_set'
    for key in ('live_velocity', 'live_extruder_velocity'):
        value = s['motion_report'][key]
        assert finite(value) and abs(value) < 1.e-6, 'motion_active'
    head = s['toolhead']
    assert all(finite(head[key]) for key in ('print_time', 'estimated_print_time')), \
        'motion_clock_unknown'
    assert head['print_time'] <= head['estimated_print_time'] + .05, 'motion_queued'
    assert s['box'].get('t_command') == '', 'cfs_command_present'
    end = s['kctrl_end']
    assert end.get('pending') is False and end.get('phase') in END_REST, 'end_active'
    assert s['kctrl_start'].get('phase') in START_REST, 'start_active'


def stable():
    first = state()
    idle(first)
    time.sleep(.5)
    second = state()
    idle(second)
    assert first['toolhead']['print_time'] == second['toolhead']['print_time'], 'motion_started'
    return second


def durable(path, data):
    with open(str(path), 'xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def replace(data, mode):
    target = Path(TARGET)
    assert not target.is_symlink(), 'unexpected_symlink'
    stage = Path(STAGE)
    assert not stage.exists(), 'stale_stage_file'
    created = False
    try:
        with stage.open('xb') as stream:
            created = True
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(str(stage), mode)
        os.replace(str(stage), str(target))
    finally:
        if created and stage.exists():
            stage.unlink()


def restore_backup(manifest):
    backup = BACKUP / 'log_config.json.before'
    assert digest(backup) == manifest['before_sha256'], 'backup_corrupt'
    current = digest(TARGET)
    assert current in (manifest['before_sha256'], manifest['sha256']), 'rollback_foreign_file'
    if current != manifest['before_sha256']:
        mode = int(json.loads((BACKUP / 'mode.json').read_text())['mode'], 8)
        replace(backup.read_bytes(), mode)
    assert digest(TARGET) == manifest['before_sha256'], 'rollback_hash_mismatch'


def receipt(status, **details):
    value = dict({'status': status, 'time': time.time()}, **details)
    if BACKUP.exists():
        (BACKUP / 'receipt.json').write_text(json.dumps(value), encoding='utf-8')
    return value


def level(data):
    return json.loads(data.decode('utf-8')).get('log_level')


def run(request):
    manifest = request['manifest']
    assert manifest['name'] == NAME and manifest['destination'] == TARGET, 'manifest_mismatch'
    mode = request['mode']
    assert mode in ('preflight', 'install', 'validate', 'rollback'), 'invalid_mode'

    if mode == 'validate':
        # Read only, allowed at any time: the file, not the programs, is checked.
        data = Path(TARGET).read_bytes()
        assert sha(data) == manifest['sha256'], 'candidate_not_installed'
        assert digest(BACKUP / 'log_config.json.before') == manifest['before_sha256'], \
            'backup_corrupt'
        recorded = json.loads((BACKUP / 'receipt.json').read_text())['status']
        return {'status': 'VALIDATED_OK', 'log_level': level(data), 'receipt': recorded}

    if mode == 'rollback':
        stable()
        restore_backup(manifest)
        return receipt('ROLLED_BACK', log_level=level(Path(TARGET).read_bytes()))

    assert not Path(TARGET).is_symlink(), 'unexpected_symlink'
    before = Path(TARGET).read_bytes()
    assert sha(before) == manifest['before_sha256'], 'target_not_at_baseline: ' + sha(before)
    data = edited(before)
    assert sha(data) == manifest['sha256'], 'candidate_hash_mismatch'
    stable()
    assert not BACKUP.exists(), 'backup_already_exists'
    assert not Path(STAGE).exists(), 'stale_stage_file'
    if mode == 'preflight':
        return {'status': 'PREFLIGHT_OK', 'log_level': level(before), 'size': len(before)}

    info = os.stat(TARGET)
    target_mode = stat.S_IMODE(info.st_mode)
    BACKUP.mkdir(parents=True)
    durable(BACKUP / 'log_config.json.before', before)
    assert digest(BACKUP / 'log_config.json.before') == manifest['before_sha256'], 'backup_corrupt'
    (BACKUP / 'mode.json').write_text(json.dumps({
        'mode': oct(target_mode), 'uid': info.st_uid, 'gid': info.st_gid,
        'mtime': info.st_mtime}), encoding='utf-8')
    (BACKUP / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    receipt('BACKED_UP')
    # Checked again right before the write: a print or a heat-up started
    # meanwhile ends the installation here, with nothing changed.
    try:
        idle(state())
    except Exception as error:
        shutil.rmtree(str(BACKUP))
        return {'status': 'NOT_INSTALLED_NOTHING_CHANGED', 'error': str(error)}
    try:
        replace(data, target_mode)
        assert digest(TARGET) == manifest['sha256'], 'candidate_hash_mismatch'
        return receipt('INSTALLED_OK', log_level=3, effect='next_power_on')
    except Exception as error:
        restore_backup(manifest)
        return receipt('INSTALL_FAILED_ROLLED_BACK', error=str(error))


if __name__ == '__main__':
    print(json.dumps(run(json.loads(base64.b64decode(REQUEST_B64)))), flush=True)  # noqa: F821
