"""Put resilience-v2 on the printer: four files together, idle only.

Run on the printer by `python3 -`; deploy.py puts REQUEST_B64 in front of
this source. Four files change, all or none (ADR-080 and ADR-081, documents
109 and 111). resilience-v1 was never posed: this package carries it whole.

- kctrl_start.py: `start-load-recovery-v1` to `resilience-v2`, the slot
  proven at the head kept on disk, the bin exit after a stopped start, and
  the recovery of a spool relay or a resume which stock leaves in a dead end;
- kctrl_print_gate.py: an end that failed and is over no longer closes the
  next start, and the gate now publishes its `revision`;
- www/bobines/logic.js and bobines.js: the page says what the gate does.

Every other file the print sequence and the page depend on is pinned, before
and after. No heating, no motion, no filament command: only a Klipper service
restart while nothing prints.

Modes: `survey` reads what the manifest pins and changes nothing, on a busy
machine too; `preflight` checks everything and compiles both modules from
stdin, nothing written; `install` backs the four files up, stops Klipper,
writes them, starts Klipper and proves both revisions at rest, or puts the
four back; `validate` reads the installed state; `rollback` puts the four
back. Klipper is read through its own socket, /tmp/klippy_uds, not through
Moonraker. The cached .pyc of both modules is removed on install and on
rollback, and each status `revision` proves which code runs.

Head record: restarting Klipper erases the route the CFS shows, and with it
the proof of which slot feeds the head. The new start keeps that proof on
disk, but only from the moment it runs. So the installer carries it over its
own restart: read right before the stop, with the rule the module itself
applies (both sensors true and one single engaged route), written with the
source `install`. Nothing proven, no record: a record found there is removed,
the old start never kept one. A rollback removes it for the same reason.

A page file is always left 0644: nginx answers 403 on anything stricter. A
module keeps the mode it had.

Once Klipper is stopped it is started again whatever happens. After a
rollback or a failed installation the backup directory is moved aside under
a dated name: the next installation finds the place free.

Order: this package comes after start-load-recovery-v1. Every earlier
package pins kctrl_start.py or kctrl_print_gate.py at an older hash and
refuses while this one is posed: roll this one back first.
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

NAME = 'resilience-v2'
ADR = 'ADR-081'
EXTRAS = '/usr/share/klipper/klippy/extras'
START = EXTRAS + '/kctrl_start.py'
GATE = EXTRAS + '/kctrl_print_gate.py'
WWW = '/usr/data/k1-control-v1/current/www/bobines'
PAGE_MODE = 0o644
BYTECODE = EXTRAS + '/__pycache__'
BACKUP = Path('/usr/data/k1-control-v1/backups/' + NAME)
STATE = '/usr/data/k1-control-v1/state'
HEAD_FILE = STATE + '/kctrl_head.json'
HEAD_SCHEMA = 1
STAGE_SUFFIX = '.kctrl-resilience-next'
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
# The start owner publishes its revision before and after; the gate only
# after: the installed one publishes none. The gate is the file of
# resilience-v1, byte for byte, and keeps that revision.
REVISIONS = {'before': 'start-load-recovery-v1', 'after': NAME}
GATE_REVISIONS = {'before': None, 'after': 'resilience-v1'}
RECOVERY_TIMEOUT = 180.
HEAD = 'filament_switch_sensor filament_sensor_2'
UPSTREAM = 'filament_switch_sensor filament_sensor'
READY_SECONDS = 120
SETTLE_SECONDS = 3
# Names the start calls in vendor code. The Python files are pinned, so a
# missing name blocks; the CFS object is compiled, its names are only reported.
FEATURES = {
    EXTRAS + '/virtual_sdcard.py': [b'must_pause_work', b'def is_active',
                                    b'record_tn_move_z', b'move_z',
                                    b'resume_tnn', b'file_position'],
    EXTRAS + '/pause_resume.py': [b'reportInformation', b'pause_command_sent',
                                  b'sd_paused', b'inside_error',
                                  b'is_paused', b'send_resume_command', b'PAUSE_STATE'],
    EXTRAS + '/gcode_move.py': [b'def reset_last_position'],
}
CFS_FEATURES = [b'inside_error', b'record_tn_move_z', b'last_err', b'move_z',
                b'BOX_CHECK_MATERIAL_REFILL', b'BOX_RESUME_EXTRUDE', b'BOX_ERROR_CLEAR',
                b'BOX_MODIFY_TN_DATA', b'Tnn_map', b'last_cmd', b'update_filament_pos',
                b'extrude_tnn']
CFS_FILES = [EXTRAS + '/box.py', EXTRAS + '/box_wrapper.cpython-38-mipsel-linux-gnu.so']


def targets():
    """Destination -> kind, in the order the files are written."""
    return {START: 'module', GATE: 'module',
            WWW + '/logic.js': 'page', WWW + '/bobines.js': 'page'}


def siblings():
    """What the four files depend on directly: the manifest must pin it."""
    return [EXTRAS + '/' + name for name in (
        'kctrl_start_policy.py', 'kctrl_start_context.py', 'kctrl_purge_guard.py',
        'kctrl_bin_motion.py', 'kctrl_sensor_guard.py', 'kctrl_end.py',
        'kctrl_slot_map.py', 'kctrl_tool_change.py')] + [
        WWW + '/' + name for name in ('app.js', 'index.html', 'overlay.js', 'styles.css')]


def backup_file(destination):
    return BACKUP / (Path(destination).name + '.before')


def stage(path):
    return Path(str(path) + STAGE_SUFFIX)


def digest(path):
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError('unexpected_symlink_' + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def mode_of(path):
    return stat.S_IMODE(os.stat(str(path)).st_mode)


def facts(path):
    if not Path(path).exists():
        return {'sha256': None, 'mode': None}
    return {'sha256': digest(path), 'mode': oct(mode_of(path))}


def pinned(expected):
    drift = [path for path in sorted(expected) if digest(path) != expected[path]]
    if drift:
        raise RuntimeError('protected_file_drift: ' + ','.join(drift))


def page_modes():
    """A page file nginx cannot read answers 403."""
    for path, kind in targets().items():
        if kind == 'page':
            assert mode_of(path) == PAGE_MODE, 'page_mode_wrong: ' + Path(path).name


def features():
    """Vendor names the start relies on; blocks only on the Python ones."""
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
    'box': ['enable', 'state', 't_command', 'filament', 'auto_refill',
            'T1', 'T2', 'T3', 'T4'],
    HEAD: ['filament_detected'],
    UPSTREAM: ['filament_detected'],
    'kctrl_end': None,
    'kctrl_start': ['enabled', 'installed', 'phase', 'revision', 'failure', 'recovery',
                    'recovery_timeout', 'head', 'head_saved', 'rest', 'relay'],
    'kctrl_tool_change': ['wrapped', 'missing', 'reloads'],
    'kctrl_print_gate': ['pending', 'wrapped', 'revision'],
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


def start_new(start):
    """The new revision at rest, its head record written, its relay in place.

    The relay hooks are fail-soft in the module: a stock name it does not
    find leaves the start working and `relay.installed` false. Posed, that
    is not what was asked for: the installation is refused and undone.
    """
    start_running(start, REVISIONS['after'])
    assert start.get('head_saved') is True, 'start_head_not_saved'
    relay = start.get('relay')
    assert isinstance(relay, dict) and relay.get('installed') is True, \
        'start_relay_not_installed: ' + str((relay or {}).get('failure'))[:80]


def start_fresh(start):
    """A new process of the new revision: idle, nothing recovered, no exit."""
    start_new(start)
    assert start.get('phase') == 'idle' and start.get('failure') == '', 'start_not_fresh'
    assert 'recovery' in start and start['recovery'] is None, 'start_recovery_not_fresh'
    assert start.get('recovery_timeout') == RECOVERY_TIMEOUT, 'start_recovery_timeout_changed'
    assert 'rest' in start and start['rest'] is None, 'start_rest_not_fresh'
    relay = start['relay']
    assert relay.get('failure') == '' and relay.get('note') is None \
        and relay.get('last') is None, 'start_relay_not_fresh'


def gate_running(gate, *revisions):
    # A gate that is not loaded answers None to every key.
    assert gate and gate.get('wrapped') in (True, 1), 'gate_not_wrapped'
    assert gate.get('pending') in (False, 0), 'start_waiting_for_spools'
    assert gate.get('revision') in revisions, 'gate_revision_changed'


def idle(s, code):
    """Nothing prints, heats, moves or changes filament; the owners are at rest.

    `code` says which start and gate should run: 'before' the installed
    ones, 'after' the new ones in a fresh process, 'new' the new ones in any
    rest state (validation), None either (rollback).
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
        start_new(start)
    else:
        start_running(start, REVISIONS['before'], REVISIONS['after'])
    change = s['kctrl_tool_change']
    assert change['wrapped'] == TOOLS and change['missing'] == [], 'tool_wrappers_changed'
    assert change['reloads'] == SLOTS, 'reloads_not_wrapped'
    gate = s['kctrl_print_gate']
    if code == 'before':
        gate_running(gate, GATE_REVISIONS['before'])
    elif code in ('after', 'new'):
        gate_running(gate, GATE_REVISIONS['after'])
    else:
        gate_running(gate, GATE_REVISIONS['before'], GATE_REVISIONS['after'])
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


def live_route(box):
    """The single engaged CFS route, or None.

    Same reading as kctrl_end.live_route, which the start uses; whatever that
    one refuses is None here: nothing unclear ever becomes a record.
    """
    routes = []
    for number in (1, 2, 3, 4):
        unit = box.get('T%d' % number)
        if number > 2:
            if not unit or unit.get('state') in (None, 'None', 'disconnect'):
                continue
            return None
        if not isinstance(unit, dict) or unit.get('state') != 'connect':
            return None
        slot = unit.get('filament')
        if slot == 'None':
            continue
        if slot not in ('A', 'B', 'C', 'D'):
            return None
        routes.append('T%d%s' % (number, slot))
    return routes[0] if len(routes) == 1 else None


def seed(s):
    """The slot the running start would remember now, or None.

    Both sensors true and one single engaged route: the rule of the module's
    own watch. The restart of this installation erases that route.
    """
    if s[HEAD]['filament_detected'] is not True:
        return None
    if s[UPSTREAM]['filament_detected'] is not True:
        return None
    box = s['box']
    if box.get('enable') != 1 or box.get('state') != 'connect':
        return None
    return live_route(box)


def head_record():
    """The slot the record on disk names, None without a record."""
    path = Path(HEAD_FILE)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema') == HEAD_SCHEMA and data.get('slot') in SLOTS:
            return data['slot']
    except Exception:
        pass
    return 'unreadable'


def write_head(slot):
    """Leave exactly what is proven: this slot, or no record at all."""
    path = Path(HEAD_FILE)
    assert not path.is_symlink(), 'unexpected_symlink'
    if slot is None:
        if path.exists():
            path.unlink()
        return
    assert slot in SLOTS, 'head_slot_unknown'
    record = {'schema': HEAD_SCHEMA, 'slot': slot, 'source': 'install', 'saved': time.time()}
    replace(HEAD_FILE, json.dumps(record, sort_keys=True).encode(), PAGE_MODE)


def head_matches(start, slot):
    """The new start read what the installer left for it."""
    head = start.get('head')
    if slot is None:
        # No record was left; the watch may have proven a route since.
        assert head is None or (isinstance(head, dict) and head.get('slot') in SLOTS), \
            'start_head_unknown'
    else:
        assert isinstance(head, dict) and head.get('slot') == slot, 'start_head_not_read'


def summary(s):
    box = s['box']
    start = s['kctrl_start']
    gate = s['kctrl_print_gate']
    head = start.get('head')
    return {'print_state': s['print_stats']['state'], 't_command': box['t_command'],
            'box_filament': box.get('filament'), 'auto_refill': box.get('auto_refill'),
            'units': [box[unit].get('filament') for unit in ('T1', 'T2')],
            'head_filament': s[HEAD]['filament_detected'],
            'upstream_filament': s[UPSTREAM]['filament_detected'],
            'end_phase': s['kctrl_end']['phase'],
            'start_revision': start.get('revision'), 'start_phase': start.get('phase'),
            'start_failure': start.get('failure'), 'start_recovery': start.get('recovery'),
            'start_head': head.get('slot') if isinstance(head, dict) else None,
            'start_relay': (start.get('relay') or {}).get('installed'),
            'head_record': head_record(),
            'gate_revision': gate.get('revision'), 'gate_wrapped': gate.get('wrapped'),
            'sensor_revision': s['kctrl_sensor_guard'].get('revision')}


def compiles(name, data):
    """Compile with Klipper's own interpreter, from stdin: no file written."""
    result = subprocess.run(
        [KLIPPY_PYTHON, '-c',
         'import sys; compile(sys.stdin.buffer.read(), sys.argv[1], "exec")', name],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    assert result.returncode == 0, 'candidate_does_not_compile: ' + name + ': ' + \
        result.stderr.decode(errors='replace')[-300:]


def bytecode():
    cache = Path(BYTECODE)
    if not cache.exists():
        return []
    stems = [Path(path).stem for path, kind in targets().items() if kind == 'module']
    return sorted(str(entry) for stem in stems for entry in cache.glob(stem + '.*.pyc'))


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
    """Start and gate lines, and tracebacks, written since `offset`.

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
                    if b'kctrl_start' in part or b'kctrl_print_gate' in part:
                        lines.append(part.decode('utf-8', errors='replace')[-240:])
                    if b'Traceback' in part:
                        tracebacks += 1
    except Exception as error:
        return {'lines': lines[-6:], 'tracebacks': tracebacks, 'error': str(error)[:200]}
    return {'lines': lines[-6:], 'tracebacks': tracebacks}


def replace(path, data, mode):
    target = Path(path)
    assert not target.is_symlink(), 'unexpected_symlink'
    staged = stage(path)
    assert not staged.exists(), 'stale_stage_file'
    created = False
    try:
        with staged.open('xb') as stream:
            created = True
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(str(staged), mode)
        os.replace(str(staged), str(target))
    finally:
        if created and staged.exists():
            staged.unlink()


def backup_sound(manifest):
    """The four saved files and their modes, exactly as they were saved."""
    for entry in manifest['targets']:
        saved = digest(backup_file(entry['destination']))
        assert saved == entry['before_sha256'], 'backup_corrupt'
    modes = json.loads((BACKUP / 'modes.json').read_text())
    assert sorted(modes) == sorted(targets()), 'backup_corrupt'
    return modes


def rollback_possible(manifest):
    """Everything a rollback relies on, before anything is stopped."""
    backup_sound(manifest)
    for entry in manifest['targets']:
        found = digest(entry['destination'])
        assert found in (entry['before_sha256'], entry['sha256']), 'rollback_foreign_file'


def restore_backup(manifest, mine):
    """Put the four files back as they were saved.

    `mine`: this very run wrote them, Klipper stopped. Whatever they hold
    now, a file the disk stored wrong included, is this installer's to undo.
    Otherwise a file that is neither the old nor the new one belongs to
    someone else and nothing is touched.
    """
    modes = backup_sound(manifest)
    if not mine:
        rollback_possible(manifest)
    for entry in manifest['targets']:
        destination = entry['destination']
        if digest(destination) != entry['before_sha256']:
            replace(destination, backup_file(destination).read_bytes(),
                    int(modes[destination], 8))
        assert digest(destination) == entry['before_sha256'], 'rollback_hash_mismatch'
    clear_bytecode()
    # The installed start never keeps a record: one left here would be read,
    # unproven, by the next installation of this package.
    write_head(None)


def put_back(manifest, oldpid, mine=False):
    """Klipper is stopped: restore, and start it again whatever happens."""
    try:
        restore_backup(manifest, mine)
    finally:
        service('start')
    return wait_ready('before', oldpid)


def receipt(status, **details):
    value = dict({'status': status, 'time': time.time()}, **details)
    if BACKUP.exists():
        (BACKUP / 'receipt.json').write_text(json.dumps(value), encoding='utf-8')
    return value


def archived(result, word):
    """Move the backup aside: the next installation finds the place free."""
    target = Path('%s.%s-%d' % (BACKUP, word, int(time.time())))
    try:
        os.rename(str(BACKUP), str(target))
        result['backup'] = target.name
    except OSError as error:
        result['backup'] = 'not_moved: ' + str(error)[:120]
    return result


def neighbours(result, protected):
    """Name a pinned file that changed while this installer worked.

    None of them is ever written here: once the four files are back the
    change is reported, and the backup still moves out of the way.
    """
    try:
        pinned(protected)
    except RuntimeError as error:
        result['neighbour'] = str(error)
    return result


def recover(manifest, oldpid):
    """Stop whatever runs, put the four files back, start and prove rest."""
    try:
        service('stop')
    except Exception:
        pass
    put_back(manifest, oldpid, mine=True)


def survey(manifest):
    """Everything the manifest pins, read as it is; nothing is changed."""
    protected = manifest['protected']
    found = {path: facts(path) for path in sorted(protected)}
    files = {entry['destination']: dict(facts(entry['destination']),
                                        expected=entry['before_sha256'])
             for entry in manifest['targets']}
    try:
        vendor = {'cfs': features()}
    except AssertionError as error:
        vendor = {'missing': str(error)}
    result = {
        'targets': files, 'protected': found,
        'drift': [path for path in sorted(protected)
                  if found[path]['sha256'] != protected[path]],
        'target_drift': [path for path in files
                         if files[path]['sha256'] != files[path]['expected']],
        'bytecode': bytecode(),
        'stage': [str(stage(path)) for path in list(targets()) + [HEAD_FILE]
                  if stage(path).exists()],
        'backup': BACKUP.exists(), 'features': vendor,
        'state_directory': Path(STATE).is_dir() and os.access(STATE, os.W_OK),
        'head_record': head_record(),
        'page_real_path': os.path.realpath(WWW),
    }
    try:
        # Either revision: the survey also reads a machine already posed.
        current = stable(None)
    except Exception as error:
        return dict(result, status='BUSY', problem=str(error)[:200])
    return dict(result, status='SURVEY_OK', rest=summary(current), head_seed=seed(current))


def checked(request):
    """The manifest names exactly the four targets, each with its payload."""
    manifest = request['manifest']
    assert manifest['name'] == NAME, 'manifest_mismatch'
    wanted = targets()
    entries = manifest['targets']
    assert [entry['destination'] for entry in entries] == list(wanted), 'manifest_mismatch'
    assert len({Path(path).name for path in wanted}) == len(wanted), 'manifest_mismatch'
    protected = manifest['protected']
    sent = request['payloads']
    assert sorted(sent) == sorted(wanted), 'payload_set_changed'
    payloads = {}
    for entry in entries:
        destination = entry['destination']
        assert entry['kind'] == wanted[destination], 'manifest_mismatch'
        assert destination not in protected, 'target_also_protected'
        assert entry['before_sha256'] not in (None, entry['sha256']), 'manifest_mismatch'
        data = base64.b64decode(sent[destination], validate=True)
        assert hashlib.sha256(data).hexdigest() == entry['sha256'], 'payload_hash_changed'
        payloads[destination] = data
    for sibling in siblings():
        assert sibling in protected, 'sibling_not_pinned'
    return entries, payloads


def run(request):
    entries, payloads = checked(request)
    manifest = request['manifest']
    protected = manifest['protected']
    mode = request['mode']
    assert mode in ('survey', 'preflight', 'install', 'validate', 'rollback'), 'invalid_mode'

    if mode == 'survey':
        return survey(manifest)
    assert manifest['surveyed'] is True, 'survey_not_recorded'

    if mode == 'validate':
        pinned(protected)
        for entry in entries:
            assert digest(entry['destination']) == entry['sha256'], 'candidate_not_installed'
            assert digest(backup_file(entry['destination'])) == entry['before_sha256'], \
                'backup_corrupt'
        page_modes()
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
        current = put_back(manifest, oldpid)
        return archived(neighbours(receipt('ROLLED_BACK', rest=summary(current)), protected),
                        'rolled-back')

    pinned(protected)
    for entry in entries:
        assert digest(entry['destination']) == entry['before_sha256'], \
            'target_not_as_surveyed: ' + Path(entry['destination']).name
    cfs = features()
    for destination, kind in targets().items():
        if kind == 'module':
            compiles(Path(destination).name, payloads[destination])
        else:
            assert payloads[destination].decode('utf-8').strip(), 'page_file_empty'
    assert Path(STATE).is_dir() and os.access(STATE, os.W_OK), 'state_directory_missing'
    reference = stable('before')
    assert not BACKUP.exists(), 'backup_already_exists'
    for path in list(targets()) + [HEAD_FILE]:
        assert not stage(path).exists(), 'stale_stage_file'
    if mode == 'preflight':
        return {'status': 'PREFLIGHT_OK', 'protected': len(protected), 'cfs_features': cfs,
                'rest': summary(reference), 'head_seed': seed(reference)}

    modes = {}
    BACKUP.mkdir(parents=True)
    for entry in entries:
        destination = entry['destination']
        modes[destination] = oct(mode_of(destination))
        backup_file(destination).write_bytes(Path(destination).read_bytes())
        assert digest(backup_file(destination)) == entry['before_sha256'], 'backup_corrupt'
    (BACKUP / 'modes.json').write_text(json.dumps(modes), encoding='utf-8')
    (BACKUP / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    receipt('BACKED_UP')
    # Checked again right before the stop: a print launched meanwhile ends
    # the installation here, with nothing changed. The route read here is the
    # last one the old process shows.
    try:
        current = state()
        idle(current, 'before')
        assert current['box']['t_command'] == reference['box']['t_command'], 'cfs_command_changed'
        slot = seed(current)
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
        for entry in entries:
            destination = entry['destination']
            page = targets()[destination] == 'page'
            replace(destination, payloads[destination],
                    PAGE_MODE if page else int(modes[destination], 8))
            assert digest(destination) == entry['sha256'], 'candidate_hash_mismatch'
        clear_bytecode()
        write_head(slot)
        receipt('FILES_WRITTEN', head_seed=slot)
        service('start')
        wait_ready('after', oldpid)
        time.sleep(SETTLE_SECONDS)
        current = state()
        idle(current, 'after')
        head_matches(current['kctrl_start'], slot)
        pinned(protected)
        page_modes()
        start = current['kctrl_start']
        return receipt('INSTALLED_IDLE_OK', rest=summary(current), revision=start['revision'],
                       gate_revision=current['kctrl_print_gate']['revision'], head_seed=slot,
                       recovery_timeout=start['recovery_timeout'], cfs_features=cfs,
                       log=log_lines(offset))
    except Exception as error:
        recover(manifest, oldpid)
        return archived(neighbours(receipt('INSTALL_FAILED_ROLLED_BACK', error=str(error),
                                           log=log_lines(offset)), protected),
                        'install-failed')


if __name__ == '__main__':
    print(json.dumps(run(json.loads(base64.b64decode(REQUEST_B64)))), flush=True)  # noqa: F821
