"""Replace kctrl_tool_change.py on the printer, idle only, with exact rollback.

Run on the printer by `python3 -`; deploy.py puts REQUEST_B64 in front of
this source. One file changes. Every other file the print sequence depends
on is pinned before and after. No heating, no motion, no filament command:
only a Klipper service restart while nothing prints (ADR-072).

Klipper is read through its own socket, /tmp/klippy_uds, not through
Moonraker. The bytecode beside the source (kctrl_tool_change.pyc) records the
source mtime and size, so Klipper recompiles it from the replaced file; the
new status field `reloads` proves which code runs.
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
import subprocess
import time

NAME = 'resume-reload-guard-v1'
TARGET = '/usr/share/klipper/klippy/extras/kctrl_tool_change.py'
BACKUP = Path('/usr/data/k1-control-v1/backups/' + NAME)
STAGE = TARGET + '.kctrl-reload-next'
SERVICE = '/etc/init.d/S55klipper_service'
PIDFILE = Path('/var/run/klippy.pid')
KLIPPY_PYTHON = '/usr/share/klippy-env/bin/python'
SOCKET = '/tmp/klippy_uds'
LOG = '/usr/data/printer_data/logs/klippy.log'
TOOLS = ['T%d' % index for index in range(16)]
SLOTS = ['T%s%s' % (box, slot) for box in '1234' for slot in 'ABCD']
IDLE_PRINT = ('standby', 'cancelled', 'complete', 'error')
END_ACTIVE = ('waiting', 'heating', 'cutting', 'rewinding', 'finalizing')
END_WRAPPED = ['CANCEL_PRINT', 'END_PRINT', 'START_PRINT']
READY_SECONDS = 120


def digest(path):
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError('unexpected_symlink_' + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def pinned(expected):
    drift = [path for path in sorted(expected) if digest(path) != expected[path]]
    if drift:
        raise RuntimeError('protected_file_drift: ' + ','.join(drift))


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
    'box': ['enable', 'state', 't_command'],
    'kctrl_end': ['enabled', 'phase', 'pending', 'revision', 'wrapped'],
    'kctrl_start': ['enabled', 'installed', 'phase', 'revision'],
    'kctrl_tool_change': None,
}


def state():
    return klippy('objects/query', {'objects': QUERY})['status']


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def idle(s, code):
    """Nothing prints, heats, moves or changes filament; the owners are at rest.

    `code` is the tool-change module expected to run: 'before', 'after', or
    None when only rest matters (rollback).
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
    box = s['box']
    assert box['enable'] == 1 and box['state'] == 'connect', 'cfs_not_ready'
    assert box['t_command'] == '', 'cfs_command_present'
    end = s['kctrl_end']
    assert end['enabled'] is True and end['pending'] is False, 'end_busy'
    assert end['phase'] not in END_ACTIVE, 'end_active'
    assert end['revision'] == 'end-rewind-confirm-v3', 'end_revision_changed'
    assert end['wrapped'] == END_WRAPPED, 'end_wrappers_changed'
    start = s['kctrl_start']
    assert start['enabled'] is True and start['installed'] is True, 'start_not_installed'
    assert start['phase'] == 'idle', 'start_busy'
    assert start['revision'] == 'retained-start-v1', 'start_revision_changed'
    if code is None:
        return
    change = s['kctrl_tool_change']
    assert change['wrapped'] == TOOLS and change['missing'] == [], 'tool_wrappers_changed'
    if code == 'after':
        assert change.get('reloads') == SLOTS, 'reloads_not_wrapped'
    else:
        assert 'reloads' not in change, 'unexpected_reload_wrapper'


def stable(code):
    first = state()
    idle(first, code)
    time.sleep(.5)
    second = state()
    idle(second, code)
    assert first['toolhead']['print_time'] == second['toolhead']['print_time'], 'motion_started'
    return second


def compiles(data):
    """Compile with Klipper's own interpreter, from stdin: no file written."""
    result = subprocess.run(
        [KLIPPY_PYTHON, '-c',
         'import sys; compile(sys.stdin.buffer.read(), "kctrl_tool_change.py", "exec")'],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    assert result.returncode == 0, 'candidate_does_not_compile: ' + \
        result.stderr.decode(errors='replace')[-300:]


def service(action):
    result = subprocess.run([SERVICE, action], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=30)
    assert result.returncode == 0, 'service_' + action + '_failed'


def stop():
    pid = PIDFILE.read_text().strip()
    assert pid.isdigit(), 'invalid_pid'
    service('stop')
    deadline = time.monotonic() + 15
    while Path('/proc/' + pid).exists() and time.monotonic() < deadline:
        time.sleep(.2)
    assert not Path('/proc/' + pid).exists(), 'old_process_remains'
    return pid


def wait_ready(code, oldpid):
    deadline = time.monotonic() + READY_SECONDS
    last = ''
    while time.monotonic() < deadline:
        try:
            pid = PIDFILE.read_text().strip()
            assert pid.isdigit() and pid != oldpid, 'process_not_replaced'
            current = state()
            idle(current, code)
            return current
        except Exception as error:
            last = str(error)
            time.sleep(1)
    raise RuntimeError('ready_not_confirmed: ' + last)


def log_lines(offset):
    """kctrl_tool_change lines and tracebacks written since `offset`.

    Read forward by 1 MB chunks, at most 16 MB: never the whole log.
    Informative only: a log it cannot read never decides the installation.
    """
    lines, tracebacks, rest = [], 0, b''
    try:
        size = os.stat(LOG).st_size
        start = offset if 0 <= offset <= size else 0
        with open(LOG, 'rb') as stream:
            stream.seek(start)
            remaining = min(size - start, 16 << 20)
            while remaining > 0:
                chunk = stream.read(min(1 << 20, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                parts = (rest + chunk).split(b'\n')
                rest = parts.pop()
                for part in parts:
                    if b'kctrl_tool_change:' in part:
                        lines.append(part.decode('utf-8', errors='replace')[-240:])
                    if b'Traceback' in part:
                        tracebacks += 1
    except Exception as error:
        return {'lines': lines[-4:], 'tracebacks': tracebacks, 'error': str(error)[:200]}
    return {'lines': lines[-4:], 'tracebacks': tracebacks}


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
    backup = BACKUP / 'kctrl_tool_change.py.before'
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


def recover(manifest, oldpid):
    """Stop whatever runs, put the original file back, start and prove rest."""
    try:
        service('stop')
    except Exception:
        pass
    restore_backup(manifest)
    service('start')
    wait_ready('before', oldpid)
    pinned(manifest['protected'])


def run(request):
    manifest = request['manifest']
    assert manifest['name'] == NAME and manifest['destination'] == TARGET, 'manifest_mismatch'
    protected = manifest['protected']
    assert TARGET not in protected, 'target_also_protected'
    data = base64.b64decode(request['payload'], validate=True)
    assert hashlib.sha256(data).hexdigest() == manifest['sha256'], 'payload_hash_changed'
    mode = request['mode']
    assert mode in ('preflight', 'install', 'validate', 'rollback'), 'invalid_mode'

    if mode == 'validate':
        pinned(protected)
        assert digest(TARGET) == manifest['sha256'], 'candidate_not_installed'
        assert digest(BACKUP / 'kctrl_tool_change.py.before') == manifest['before_sha256'], \
            'backup_corrupt'
        current = stable('after')
        change = current['kctrl_tool_change']
        return {'status': 'VALIDATED_IDLE_OK', 'reloads': change['reloads'],
                'wrapped': len(change['wrapped']), 'print_state': current['print_stats']['state']}

    if mode == 'rollback':
        pinned(protected)
        stable(None)
        oldpid = stop()
        restore_backup(manifest)
        service('start')
        wait_ready('before', oldpid)
        pinned(protected)
        return receipt('ROLLED_BACK')

    pinned(protected)
    assert digest(TARGET) == manifest['before_sha256'], 'target_not_at_baseline'
    compiles(data)
    stable('before')
    assert not BACKUP.exists(), 'backup_already_exists'
    assert not Path(STAGE).exists(), 'stale_stage_file'
    if mode == 'preflight':
        return {'status': 'PREFLIGHT_OK', 'protected': len(protected)}

    target_mode = stat.S_IMODE(os.stat(TARGET).st_mode)
    BACKUP.mkdir(parents=True)
    backup = BACKUP / 'kctrl_tool_change.py.before'
    backup.write_bytes(Path(TARGET).read_bytes())
    assert digest(backup) == manifest['before_sha256'], 'backup_corrupt'
    (BACKUP / 'mode.json').write_text(json.dumps({'mode': oct(target_mode)}), encoding='utf-8')
    (BACKUP / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    receipt('BACKED_UP')
    # Checked again right before the stop: a print launched meanwhile ends
    # the installation here, with nothing changed.
    try:
        idle(state(), 'before')
    except Exception as error:
        shutil.rmtree(str(BACKUP))
        return {'status': 'NOT_INSTALLED_NOTHING_CHANGED', 'error': str(error)}
    try:
        offset = os.stat(LOG).st_size
    except OSError:
        offset = -1
    oldpid = PIDFILE.read_text().strip()
    try:
        oldpid = stop()
        pinned(protected)
        replace(data, target_mode)
        assert digest(TARGET) == manifest['sha256'], 'candidate_hash_mismatch'
        receipt('FILE_REPLACED')
        service('start')
        current = wait_ready('after', oldpid)
        pinned(protected)
        return receipt('INSTALLED_IDLE_OK', reloads=current['kctrl_tool_change']['reloads'],
                       log=log_lines(offset))
    except Exception as error:
        recover(manifest, oldpid)
        return receipt('INSTALL_FAILED_ROLLED_BACK', error=str(error), log=log_lines(offset))


if __name__ == '__main__':
    print(json.dumps(run(json.loads(base64.b64decode(REQUEST_B64)))), flush=True)  # noqa: F821
