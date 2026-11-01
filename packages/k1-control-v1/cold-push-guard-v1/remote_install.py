"""Replace kctrl_purge_guard.py on the printer, idle only, with exact rollback.

Run on the printer by `python3 -`; deploy.py puts REQUEST_B64 in front of
this source. One file changes: the bin guard gains the cold push refusal
(ADR-076), its bin part untouched. Every other file the print sequence depends
on is pinned before and after. No heating, no motion, no filament command:
only a Klipper service restart while nothing prints. The separate `probe`
mode then sends one short push on the cold, empty head and proves the refusal.

Klipper is read through its own socket, /tmp/klippy_uds, not through
Moonraker. Its bytecode records the source mtime and size, so Klipper
recompiles the replaced file; the status `cold_revision` proves which code runs.
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

NAME = 'cold-push-guard-v1'
TARGET = '/usr/share/klipper/klippy/extras/kctrl_purge_guard.py'
BACKUP = Path('/usr/data/k1-control-v1/backups/' + NAME)
STAGE = TARGET + '.kctrl-cold-next'
SERVICE = '/etc/init.d/S55klipper_service'
PIDFILE = Path('/var/run/klippy.pid')
KLIPPY_PYTHON = '/usr/share/klippy-env/bin/python'
SOCKET = '/tmp/klippy_uds'
LOG = '/usr/data/printer_data/logs/klippy.log'
TOOLS = ['T%d' % index for index in range(16)]
SLOTS = ['T%s%s' % (box, slot) for box in '1234' for slot in 'ABCD']
IDLE_PRINT = ('standby', 'cancelled', 'complete', 'error')
END_ACTIVE = ('waiting', 'heating', 'cutting', 'rewinding', 'finalizing')
START_ACTIVE = ('planned', 'referenced', 'material')
END_WRAPPED = ['CANCEL_PRINT', 'END_PRINT', 'START_PRINT']
END_REVISION = 'cancel-retained-v4'
COLD_REVISION = 'cold-push-guard-v1'
HEAD = 'filament_switch_sensor filament_sensor_2'
PROBE = 'G1 E0.5 F60'
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
    'extruder': ['target', 'temperature', 'can_extrude'],
    'heater_bed': ['target'],
    'toolhead': ['print_time', 'estimated_print_time', 'position'],
    'motion_report': ['live_velocity', 'live_extruder_velocity'],
    'gcode_move': ['absolute_extrude'],
    'box': ['enable', 'state', 't_command'],
    HEAD: ['filament_detected'],
    'kctrl_end': None,
    'kctrl_start': ['enabled', 'installed', 'phase', 'revision'],
    'kctrl_tool_change': ['wrapped', 'missing', 'reloads'],
    'kctrl_purge_guard': None,
}


def state():
    return klippy('objects/query', {'objects': QUERY})['status']


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def idle(s, code):
    """Nothing prints, heats, moves or changes filament; the owners are at rest.

    `code` is the guard expected to run: 'before', 'after', or None when only
    rest matters (rollback, validate, probe).
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
    assert end['wrapped'] == END_WRAPPED, 'end_wrappers_changed'
    assert end['revision'] == END_REVISION, 'end_revision_changed'
    start = s['kctrl_start']
    assert start['enabled'] is True and start['installed'] is True, 'start_not_installed'
    assert start['phase'] not in START_ACTIVE, 'start_busy'
    assert start['revision'] == 'retained-start-v1', 'start_revision_changed'
    change = s['kctrl_tool_change']
    assert change['wrapped'] == TOOLS and change['missing'] == [], 'tool_wrappers_changed'
    assert change['reloads'] == SLOTS, 'reloads_not_wrapped'
    guard = s['kctrl_purge_guard']
    assert guard['revision'] == 'retained-start-v1' and guard['installed'] is True, \
        'bin_guard_not_installed'
    # The head outside the bin: a restart drops the latch with the homing.
    assert guard['minimum_z'] >= 30 and guard['bin_latched'] is False, 'bin_guard_not_at_rest'
    if code is None:
        assert guard.get('cold_revision') in (None, COLD_REVISION), 'cold_revision_unknown'
        return
    if code == 'before':
        assert 'cold_revision' not in guard, 'cold_guard_already_running'
        return
    # Fresh process: the new hook is live and has refused nothing yet.
    assert guard.get('cold_revision') == COLD_REVISION, 'cold_revision_changed'
    assert guard['cold_installed'] is True, 'cold_hook_missing'
    assert guard['cold_refused'] == 0 and guard['denied'] == 0, 'guard_not_fresh'


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
         'import sys; compile(sys.stdin.buffer.read(), "kctrl_purge_guard.py", "exec")'],
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
    """kctrl_purge_guard lines and tracebacks written since `offset`.

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
                    if b'kctrl_purge_guard' in part:
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
    backup = BACKUP / 'kctrl_purge_guard.py.before'
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


def probe():
    """One short push on the cold, empty head: the new hook must refuse it.

    Only at rest, head sensor empty, no heater target and the nozzle below its
    extrusion minimum. Had the hook failed, the extruder would turn 0.5 mm on
    an empty head. The extrusion mode is set relative and put back as it was.
    """
    before = stable(None)
    guard = before['kctrl_purge_guard']
    assert guard.get('cold_revision') == COLD_REVISION and guard['cold_installed'] is True, \
        'cold_hook_missing'
    assert before[HEAD]['filament_detected'] is False, 'head_not_empty'
    assert before['extruder']['can_extrude'] is False, 'nozzle_not_cold'
    refused = ''
    try:
        klippy('gcode/script', {'script': 'M83\n' + PROBE})
    except RuntimeError as error:
        refused = str(error)
    finally:
        if before['gcode_move']['absolute_extrude']:
            klippy('gcode/script', {'script': 'M82'})
    after = stable(None)
    count = after['kctrl_purge_guard']['cold_refused'] - guard['cold_refused']
    moved = after['toolhead']['position'][3] != before['toolhead']['position'][3]
    assert 'buse froide' in refused, 'push_not_refused: ' + refused[:200]
    assert count == 1 and not moved, 'push_effect_unclear'
    assert after['gcode_move']['absolute_extrude'] == before['gcode_move']['absolute_extrude'], \
        'extrude_mode_not_restored'
    return {'status': 'PROBE_REFUSED_OK', 'refused': refused[:200],
            'cold_last': after['kctrl_purge_guard']['cold_last'],
            'temperature': before['extruder']['temperature']}


def run(request):
    manifest = request['manifest']
    assert manifest['name'] == NAME and manifest['destination'] == TARGET, 'manifest_mismatch'
    protected = manifest['protected']
    assert TARGET not in protected, 'target_also_protected'
    data = base64.b64decode(request['payload'], validate=True)
    assert hashlib.sha256(data).hexdigest() == manifest['sha256'], 'payload_hash_changed'
    mode = request['mode']
    assert mode in ('preflight', 'install', 'validate', 'probe', 'rollback'), 'invalid_mode'

    if mode in ('validate', 'probe'):
        pinned(protected)
        assert digest(TARGET) == manifest['sha256'], 'candidate_not_installed'
        assert digest(BACKUP / 'kctrl_purge_guard.py.before') == manifest['before_sha256'], \
            'backup_corrupt'
        if mode == 'probe':
            return probe()
        guard = stable(None)['kctrl_purge_guard']
        assert guard.get('cold_revision') == COLD_REVISION, 'cold_revision_changed'
        assert guard['cold_installed'] is True, 'cold_hook_missing'
        return {'status': 'VALIDATED_IDLE_OK', 'cold_revision': guard['cold_revision'],
                'cold_refused': guard['cold_refused'], 'denied': guard['denied']}

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
    backup = BACKUP / 'kctrl_purge_guard.py.before'
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
        return receipt('INSTALLED_IDLE_OK',
                       cold_revision=current['kctrl_purge_guard']['cold_revision'],
                       log=log_lines(offset))
    except Exception as error:
        recover(manifest, oldpid)
        return receipt('INSTALL_FAILED_ROLLED_BACK', error=str(error), log=log_lines(offset))


if __name__ == '__main__':
    print(json.dumps(run(json.loads(base64.b64decode(REQUEST_B64)))), flush=True)  # noqa: F821
