"""Replace the K1 Control start owner by its recovering revision, idle only.

Run on the printer by `python3 -`; deploy.py puts REQUEST_B64 in front of
this source. One file changes: kctrl_start.py, from `retained-start-v1` to
`start-load-recovery-v1`. Its policy, context, purge guard and bin motion
modules, the start configuration and every file the print sequence depends on
are pinned, before and after. No heating, no motion, no filament command:
only a Klipper service restart while nothing prints (ADR-079, document 108).

Modes: `survey` reads what the manifest pins and changes nothing; `preflight`
checks everything, looks for the vendor names the recovery relies on and
compiles the candidate from stdin, nothing written; `install`, `validate` and
`rollback` as in the earlier packages. Klipper is read through its own socket,
/tmp/klippy_uds, not through Moonraker. Its bytecode records the source mtime
and size; the cached .pyc is removed anyway on install and on rollback, and
the status `revision` proves which code runs.

The bin guard keeps its own revision, `retained-start-v1`: it is not this
module. The CFS sensor guard must run as V2.

Order: this package comes after cfs-sensor-guard-v2. Every earlier package
pins kctrl_start.py at the retained-start-v1 hash and refuses while this one
is posed: roll this one back first.
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

NAME = 'start-load-recovery-v1'
ADR = 'ADR-079'
EXTRAS = '/usr/share/klipper/klippy/extras'
MODULE = EXTRAS + '/kctrl_start.py'
BYTECODE = EXTRAS + '/__pycache__'
BACKUP = Path('/usr/data/k1-control-v1/backups/' + NAME)
STAGE_SUFFIX = '.kctrl-start-recovery-next'
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
END_REVISION = 'end-no-stock-flush-v5'
BIN_REVISION = 'retained-start-v1'
COLD_REVISION = 'cold-push-guard-v1'
SENSOR_REVISION = 'cfs-sensor-guard-v2'
REVISIONS = {'before': 'retained-start-v1', 'after': NAME}
RECOVERY_TIMEOUT = 180.
HEAD = 'filament_switch_sensor filament_sensor_2'
READY_SECONDS = 120
SETTLE_SECONDS = 3
# Names the recovery calls in vendor code. The Python files are pinned, so a
# missing name blocks; the CFS object is compiled, its names are only reported.
FEATURES = {
    EXTRAS + '/virtual_sdcard.py': [b'must_pause_work', b'def is_active',
                                    b'record_tn_move_z', b'move_z'],
    EXTRAS + '/pause_resume.py': [b'reportInformation', b'pause_command_sent',
                                  b'sd_paused', b'inside_error'],
    EXTRAS + '/gcode_move.py': [b'def reset_last_position'],
}
CFS_FEATURES = [b'inside_error', b'record_tn_move_z', b'last_err', b'move_z']
CFS_FILES = [EXTRAS + '/box.py', EXTRAS + '/box_wrapper.cpython-38-mipsel-linux-gnu.so']


def digest(path):
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError('unexpected_symlink_' + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def facts(path):
    if not Path(path).exists():
        return {'sha256': None, 'mode': None}
    return {'sha256': digest(path), 'mode': oct(stat.S_IMODE(os.stat(str(path)).st_mode))}


def pinned(expected):
    drift = [path for path in sorted(expected) if digest(path) != expected[path]]
    if drift:
        raise RuntimeError('protected_file_drift: ' + ','.join(drift))


def features():
    """Vendor names the recovery relies on; blocks only on the Python ones."""
    missing = []
    for path, needles in sorted(FEATURES.items()):
        data = Path(path).read_bytes()
        missing.extend('%s:%s' % (Path(path).name, needle.decode())
                       for needle in needles if needle not in data)
    assert not missing, 'vendor_feature_missing: ' + ','.join(missing)
    found = {}
    for needle in CFS_FEATURES:
        found[needle.decode()] = any(Path(path).exists() and needle in Path(path).read_bytes()
                                     for path in CFS_FILES)
    return found


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
    'box': ['enable', 'state', 't_command', 'filament', 'auto_refill', 'T1', 'T2'],
    HEAD: ['filament_detected'],
    'kctrl_end': None,
    'kctrl_start': ['enabled', 'installed', 'phase', 'revision', 'failure', 'recovery',
                    'recovery_timeout'],
    'kctrl_tool_change': ['wrapped', 'missing', 'reloads'],
    'kctrl_print_gate': ['pending'],
    'kctrl_purge_guard': None,
    'kctrl_sensor_guard': ['enabled', 'installed', 'revision', 'hook', 'hooked', 'failure',
                           'blind'],
}


def state():
    return klippy('objects/query', {'objects': QUERY})['status']


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def tool_memory(box):
    """The last tool command the file sent, or '' (document 105)."""
    value = box['t_command']
    assert type(value) is str and (value == '' or value in TOOLS or value in SLOTS), \
        'cfs_command_unknown'
    return value


def start_running(start, *revisions):
    assert start, 'start_not_loaded'
    assert start.get('enabled') is True and start.get('installed') is True, \
        'start_not_installed'
    assert start.get('phase') not in START_ACTIVE, 'start_busy'
    assert start.get('revision') in revisions, 'start_revision_changed'


def start_fresh(start):
    """A new process of the recovering revision: idle, nothing recovered."""
    start_running(start, REVISIONS['after'])
    assert start.get('phase') == 'idle' and start.get('failure') == '', 'start_not_fresh'
    assert 'recovery' in start and start['recovery'] is None, 'start_recovery_not_fresh'
    assert start.get('recovery_timeout') == RECOVERY_TIMEOUT, 'start_recovery_timeout_changed'


def idle(s, code):
    """Nothing prints, heats, moves or changes filament; the owners are at rest.

    `code` says which start owner should run: 'before' the retained start,
    'after' the recovering one, fresh, 'new' the recovering one in any rest
    state (validation), None either (rollback).
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
    for unit in ('T1', 'T2'):
        assert box[unit]['state'] == 'connect', 'cfs_unit_not_connected'
    tool_memory(box)
    refill = box.get('auto_refill')
    assert type(refill) is int and refill in (0, 1), 'auto_refill_unknown'
    end = s['kctrl_end']
    assert end['enabled'] is True and end['pending'] is False, 'end_busy'
    assert end['phase'] not in END_ACTIVE, 'end_active'
    assert end['wrapped'] == END_WRAPPED, 'end_wrappers_changed'
    assert end['revision'] == END_REVISION, 'end_revision_changed'
    assert end['auto_refill_restore_pending'] is False, 'end_refill_pending'
    start = s['kctrl_start']
    if code == 'before':
        start_running(start, REVISIONS['before'])
    elif code == 'after':
        start_fresh(start)
    elif code == 'new':
        start_running(start, REVISIONS['after'])
    else:
        start_running(start, REVISIONS['before'], REVISIONS['after'])
    change = s['kctrl_tool_change']
    assert change['wrapped'] == TOOLS and change['missing'] == [], 'tool_wrappers_changed'
    assert change['reloads'] == SLOTS, 'reloads_not_wrapped'
    assert s['kctrl_print_gate']['pending'] in (False, 0), 'start_waiting_for_spools'
    guard = s['kctrl_purge_guard']
    assert guard['revision'] == BIN_REVISION and guard['installed'] is True, \
        'bin_guard_not_installed'
    assert guard['minimum_z'] >= 30 and guard['bin_latched'] is False, 'bin_guard_not_at_rest'
    assert guard.get('cold_revision') == COLD_REVISION and guard.get('cold_installed') is True, \
        'cold_guard_not_installed'
    sensor = s['kctrl_sensor_guard']
    assert sensor and sensor.get('enabled') is True and sensor.get('installed') is True, \
        'sensor_guard_not_installed'
    assert sensor.get('revision') == SENSOR_REVISION, 'sensor_guard_revision_changed'
    assert sensor.get('hook') == 'inside_cold_guard' and sensor.get('hooked') is True, \
        'sensor_guard_not_hooked'
    assert sensor.get('failure') == '', 'sensor_guard_failed'


def stable(code):
    first = state()
    idle(first, code)
    time.sleep(.5)
    second = state()
    idle(second, code)
    assert first['toolhead']['print_time'] == second['toolhead']['print_time'], 'motion_started'
    assert first['box']['t_command'] == second['box']['t_command'], 'cfs_command_changed'
    return second


def summary(s):
    box = s['box']
    start = s['kctrl_start']
    return {'print_state': s['print_stats']['state'], 't_command': box['t_command'],
            'box_filament': box.get('filament'), 'auto_refill': box.get('auto_refill'),
            'units': [box[unit].get('filament') for unit in ('T1', 'T2')],
            'head_filament': s[HEAD]['filament_detected'],
            'end_phase': s['kctrl_end']['phase'],
            'start_revision': start.get('revision'), 'start_phase': start.get('phase'),
            'start_failure': start.get('failure'), 'start_recovery': start.get('recovery'),
            'sensor_revision': s['kctrl_sensor_guard'].get('revision')}


def compiles(data):
    """Compile with Klipper's own interpreter, from stdin: no file written."""
    result = subprocess.run(
        [KLIPPY_PYTHON, '-c',
         'import sys; compile(sys.stdin.buffer.read(), "kctrl_start.py", "exec")'],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    assert result.returncode == 0, 'candidate_does_not_compile: ' + \
        result.stderr.decode(errors='replace')[-300:]


def bytecode():
    cache = Path(BYTECODE)
    return sorted(str(entry) for entry in cache.glob('kctrl_start.*.pyc')) \
        if cache.exists() else []


def clear_bytecode():
    for path in bytecode():
        os.unlink(path)
    assert bytecode() == [], 'bytecode_remains'


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
    """Start owner lines and tracebacks written since `offset`.

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
                    if b'kctrl_start' in part:
                        lines.append(part.decode('utf-8', errors='replace')[-240:])
                    if b'Traceback' in part:
                        tracebacks += 1
    except Exception as error:
        return {'lines': lines[-4:], 'tracebacks': tracebacks, 'error': str(error)[:200]}
    return {'lines': lines[-4:], 'tracebacks': tracebacks}


def replace(path, data, mode):
    target = Path(path)
    assert not target.is_symlink(), 'unexpected_symlink'
    stage = Path(str(path) + STAGE_SUFFIX)
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


def rollback_possible(manifest):
    """Everything a rollback relies on, before anything is stopped."""
    assert digest(BACKUP / 'module.before') == manifest['before_sha256'], 'backup_corrupt'
    assert digest(MODULE) in (manifest['before_sha256'], manifest['sha256']), \
        'rollback_foreign_file'


def restore_backup(manifest):
    rollback_possible(manifest)
    if digest(MODULE) != manifest['before_sha256']:
        mode = int(json.loads((BACKUP / 'mode.json').read_text())['mode'], 8)
        replace(MODULE, (BACKUP / 'module.before').read_bytes(), mode)
    assert digest(MODULE) == manifest['before_sha256'], 'rollback_hash_mismatch'
    clear_bytecode()


def receipt(status, **details):
    value = dict({'status': status, 'time': time.time()}, **details)
    if BACKUP.exists():
        (BACKUP / 'receipt.json').write_text(json.dumps(value), encoding='utf-8')
    return value


def recover(manifest, oldpid):
    """Stop whatever runs, put the retained start back, start and prove rest."""
    try:
        service('stop')
    except Exception:
        pass
    restore_backup(manifest)
    service('start')
    wait_ready('before', oldpid)
    pinned(manifest['protected'])


def survey(manifest):
    """Everything the manifest pins, read at rest; nothing is changed."""
    try:
        current = stable('before')
    except AssertionError as error:
        return {'status': 'BUSY', 'problem': str(error)}
    protected = manifest['protected']
    found = {path: facts(path) for path in sorted(protected)}
    try:
        vendor = {'cfs': features()}
    except AssertionError as error:
        vendor = {'missing': str(error)}
    return {'status': 'SURVEY_OK', 'rest': summary(current), 'protected': found,
            'drift': [path for path in sorted(protected)
                      if found[path]['sha256'] != protected[path]],
            'module': dict(facts(MODULE), expected=manifest['before_sha256']),
            'bytecode': bytecode(),
            'stage': Path(MODULE + STAGE_SUFFIX).exists(),
            'backup': BACKUP.exists(), 'features': vendor}


def run(request):
    manifest = request['manifest']
    assert (manifest['name'] == NAME and manifest['destination'] == MODULE), 'manifest_mismatch'
    protected = manifest['protected']
    assert MODULE not in protected, 'target_also_protected'
    for sibling in ('kctrl_start_policy.py', 'kctrl_start_context.py', 'kctrl_purge_guard.py',
                    'kctrl_bin_motion.py', 'kctrl_sensor_guard.py'):
        assert EXTRAS + '/' + sibling in protected, 'sibling_not_pinned'
    data = base64.b64decode(request['payload'], validate=True)
    assert hashlib.sha256(data).hexdigest() == manifest['sha256'], 'payload_hash_changed'
    assert manifest['before_sha256'] not in (None, manifest['sha256']), 'manifest_mismatch'
    mode = request['mode']
    assert mode in ('survey', 'preflight', 'install', 'validate', 'rollback'), 'invalid_mode'

    if mode == 'survey':
        return survey(manifest)
    assert manifest['surveyed'] is True, 'survey_not_recorded'

    if mode == 'validate':
        pinned(protected)
        assert digest(MODULE) == manifest['sha256'], 'candidate_not_installed'
        assert digest(BACKUP / 'module.before') == manifest['before_sha256'], 'backup_corrupt'
        current = stable('new')
        start = current['kctrl_start']
        return dict(summary(current), status='VALIDATED_IDLE_OK',
                    revision=start['revision'], recovery=start.get('recovery'),
                    recovery_timeout=start.get('recovery_timeout'))

    if mode == 'rollback':
        pinned(protected)
        rollback_possible(manifest)
        stable(None)
        oldpid = stop()
        restore_backup(manifest)
        service('start')
        current = wait_ready('before', oldpid)
        pinned(protected)
        return receipt('ROLLED_BACK', rest=summary(current))

    pinned(protected)
    assert digest(MODULE) == manifest['before_sha256'], 'module_not_retained_start'
    cfs = features()
    compiles(data)
    reference = stable('before')
    assert not BACKUP.exists(), 'backup_already_exists'
    assert not Path(MODULE + STAGE_SUFFIX).exists(), 'stale_stage_file'
    if mode == 'preflight':
        return {'status': 'PREFLIGHT_OK', 'protected': len(protected), 'cfs_features': cfs,
                'rest': summary(reference)}

    original = Path(MODULE).read_bytes()
    module_mode = stat.S_IMODE(os.stat(MODULE).st_mode)
    BACKUP.mkdir(parents=True)
    backup = BACKUP / 'module.before'
    backup.write_bytes(original)
    assert digest(backup) == manifest['before_sha256'], 'backup_corrupt'
    (BACKUP / 'mode.json').write_text(json.dumps({'mode': oct(module_mode)}), encoding='utf-8')
    (BACKUP / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    receipt('BACKED_UP')
    # Checked again right before the stop: a print launched meanwhile ends
    # the installation here, with nothing changed.
    try:
        current = state()
        idle(current, 'before')
        assert current['box']['t_command'] == reference['box']['t_command'], 'cfs_command_changed'
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
        replace(MODULE, data, module_mode)
        assert digest(MODULE) == manifest['sha256'], 'candidate_hash_mismatch'
        clear_bytecode()
        receipt('FILE_WRITTEN')
        service('start')
        wait_ready('after', oldpid)
        time.sleep(SETTLE_SECONDS)
        current = state()
        idle(current, 'after')
        pinned(protected)
        start = current['kctrl_start']
        return receipt('INSTALLED_IDLE_OK', rest=summary(current), revision=start['revision'],
                       recovery_timeout=start['recovery_timeout'], cfs_features=cfs,
                       log=log_lines(offset))
    except Exception as error:
        recover(manifest, oldpid)
        return receipt('INSTALL_FAILED_ROLLED_BACK', error=str(error), log=log_lines(offset))


if __name__ == '__main__':
    print(json.dumps(run(json.loads(base64.b64decode(REQUEST_B64)))), flush=True)  # noqa: F821
