"""Install the spool manager in K1 Control's own Moonraker, idle only, with exact rollback.

Run on the printer by `python3 -`; deploy.py puts REQUEST_B64 in front of
this source. Four component files join K1 Control's Moonraker, eight files
of the Bobines pages are written or replaced, moonraker.conf gains the
[kctrl_spools] section and the gateway gains one location for the spool
endpoints (document 102, ADR-075). Only K1 Control's Moonraker restarts and
the gateway reloads, while nothing prints. Klipper keeps running: no G-code,
no heating, no motion, no write to the CFS.

Modes: `survey` reads what the manifest must pin and sends nothing;
`preflight` checks everything, imports the candidate in Moonraker's own
interpreter from stdin and writes nothing; `install`, `validate` and
`rollback` as in the earlier packages. Klipper is read through
/tmp/klippy_uds, Moonraker on 127.0.0.1:7125 and the gateway on
127.0.0.1:4409, the way Mainsail sees it.
"""

import base64
import hashlib
import http.client as httpclient
import json
import math
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import time

NAME = 'spool-manager-install-v1'
K1C = '/usr/data/k1-control-v1'
CURRENT = K1C + '/current'
MOONRAKER_ROOT = CURRENT + '/moonraker/moonraker'
COMPONENTS = MOONRAKER_ROOT + '/moonraker/components'
PYTHON = CURRENT + '/moonraker/moonraker-env/bin/python'
MOONRAKER_CONF = CURRENT + '/config/moonraker.conf'
NGINX = CURRENT + '/nginx/sbin/nginx'
NGINX_PREFIX = CURRENT + '/nginx/nginx'
NGINX_CONF = K1C + '/state/nginx-active.conf'
STAGE_SUFFIX = '.kctrl-spools-next'
NGINX_STAGE = NGINX_CONF + STAGE_SUFFIX
WWW = CURRENT + '/www/bobines'
MAINSAIL_INDEX = CURRENT + '/www/mainsail/index.html'
STATE_DIR = K1C + '/state/spools'
BACKUP = Path(K1C + '/backups/' + NAME)
MATERIAL_DATABASE = '/usr/data/creality/userdata/box/material_database.json'
GCODES = '/usr/data/printer_data/gcodes'
MOONRAKER_SERVICE = '/etc/init.d/S56k1_control_moonraker'
GATEWAY_SERVICE = '/etc/init.d/S57k1_control_gateway'
MOONRAKER_PID = Path('/var/run/k1-control-moonraker.pid')
NGINX_PID = Path('/var/run/k1-control-nginx.pid')
PROC = Path('/proc')
SOCKET = '/tmp/klippy_uds'
LOCAL_PORT = 7125
GATEWAY_PORT = 4409
COMPONENT = 'kctrl_spools'
MODULES = ['kctrl_spools_store', 'kctrl_spools_model', 'kctrl_spools_counter', 'kctrl_spools']
PREFIX = '/machine/k1_control/spools/'
TAG = b'<script type="module" src="/bobines/overlay.js"></script>'
IDLE_PRINT = ('standby', 'cancelled', 'complete', 'error')
END_IDLE = ('disabled', 'idle', 'complete', 'failed', 'shutdown')
START_IDLE = ('disabled', 'idle', 'complete', 'failed')
CALIBRATION_CLOSED = ('idle', 'accepted', 'cancelled', 'failed', 'mesh_rejected', 'restored',
                      'rolled_back')
READY_SECONDS = 120
SPOOLS_SECONDS = 60
MOONRAKER_FILES = ['moonraker.py', 'server.py', 'common.py', 'confighelper.py', 'eventloop.py',
                   'components/klippy_connection.py', 'utils/__init__.py', 'components/klippy_apis.py']
# Read by the survey: what the installation relies on without changing it.
PIN_CANDIDATES = [MOONRAKER_ROOT + '/moonraker/' + name for name in MOONRAKER_FILES] + [
    MOONRAKER_SERVICE, GATEWAY_SERVICE, K1C + '/state/mainsail_overlay_patch.py', MAINSAIL_INDEX,
    WWW + '/app.js', WWW + '/index.html', WWW + '/package.json',
    '/usr/data/printer_data/config/k1-control-owned-start-print-v2.cfg',
    '/usr/share/klipper/klippy/extras/kctrl_print_gate.py']

SECTION = b'[kctrl_spools]'
CONF_BLOCK = (b'# K1 Control spool manager (document 102, ADR-075).\n'
              b'[kctrl_spools]\n'
              b'state_path: /usr/data/k1-control-v1/state/spools\n'
              b'material_database: /usr/data/creality/userdata/box/material_database.json\n'
              b'gcodes_path: /usr/data/printer_data/gcodes\n')
NGINX_ANCHOR = b'        location ~ ^/(access|api|machine|printer|server)/ {\n'
NGINX_BLOCK = (b'        # K1 Control spool manager (document 102, ADR-075): a write to the CFS\n'
               b"        # can outlast nginx's 60 s default and the window waits 65 s for it.\n"
               b'        # `^~` keeps the regex location below from taking these requests.\n'
               b'        location ^~ /machine/k1_control/spools/ {\n'
               b'            proxy_pass http://k1_moonraker;\n'
               b'            proxy_read_timeout 90s;\n'
               b'            proxy_set_header Host $http_host;\n'
               b'            proxy_set_header X-Real-IP 127.0.0.1;\n'
               b'            proxy_set_header Authorization "";\n'
               b'        }\n'
               b'\n')

# Imports the candidate in Moonraker's interpreter, sources from stdin: no
# file written, no bytecode (-B), no component started.
CHECK = r'''
import base64, inspect, json, sys, types
request = json.loads(base64.b64decode(sys.stdin.buffer.read()))
sys.path.insert(0, request['root'])
import moonraker.components as package
modules = {}
for name in request['order']:
    full = 'moonraker.components.' + name
    module = types.ModuleType(full)
    module.__package__ = 'moonraker.components'
    module.__file__ = request['directory'] + '/' + name + '.py'
    sys.modules[full] = module
    setattr(package, name, module)
    exec(compile(base64.b64decode(request['sources'][name]), module.__file__, 'exec'),
         module.__dict__)
    modules[name] = module
assert callable(getattr(modules['kctrl_spools'], 'load_component', None)), 'no_load_component'
from moonraker.components.klippy_apis import KlippyAPI
assert 'callback' in inspect.signature(KlippyAPI.subscribe_objects).parameters, \
    'subscribe_signature_changed'
materials, error = modules['kctrl_spools_model'].read_materials(request['materials'])
print(json.dumps({'status': 'IMPORT_OK', 'materials': len(materials), 'error': error}))
'''


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
    'kctrl_end': ['phase', 'pending'],
    'kctrl_start': ['phase'],
    'kctrl_print_gate': ['pending'],
}


def state():
    return klippy('objects/query', {'objects': QUERY})['status']


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def field(s, name, key):
    """Klipper leaves out an unknown object or field without a word."""
    assert name in s, 'object_missing_' + name
    assert key in s[name], 'field_missing_' + name + '.' + key
    return s[name][key]


def idle(s):
    """Nothing prints, heats, moves or changes filament; the owners are at rest.

    Klipper itself is not restarted: its owners only have to be at rest, not
    at a given revision, so the end of print V5 can land before or after.
    """
    assert field(s, 'webhooks', 'state') == 'ready', 'klipper_not_ready'
    assert field(s, 'print_stats', 'state') in IDLE_PRINT, 'job_busy'
    assert field(s, 'virtual_sdcard', 'is_active') is False, 'sd_active'
    assert field(s, 'pause_resume', 'is_paused') is False, 'paused'
    assert field(s, 'idle_timeout', 'state') != 'Printing', 'idle_timeout_printing'
    for heater in ('extruder', 'heater_bed'):
        assert field(s, heater, 'target') == 0, 'heater_target_set'
    for key in ('live_velocity', 'live_extruder_velocity'):
        value = field(s, 'motion_report', key)
        assert finite(value) and abs(value) < 1.e-6, 'motion_active'
    clock = [field(s, 'toolhead', key) for key in ('print_time', 'estimated_print_time')]
    assert all(finite(value) for value in clock), 'motion_clock_unknown'
    assert clock[0] <= clock[1] + .05, 'motion_queued'
    assert field(s, 'box', 'enable') == 1 and field(s, 'box', 'state') == 'connect', \
        'cfs_not_ready'
    assert field(s, 'box', 't_command') == '', 'cfs_command_present'
    assert field(s, 'kctrl_end', 'pending') in (False, 0), 'end_busy'
    assert field(s, 'kctrl_end', 'phase') in END_IDLE, 'end_active'
    assert field(s, 'kctrl_start', 'phase') in START_IDLE, 'start_busy'
    assert field(s, 'kctrl_print_gate', 'pending') in (False, 0), 'start_waiting_for_spools'


def rest_problem():
    """Why the printer is not at rest, '' when it is. Klipper unreadable
    counts as not at rest: nothing is restarted blind."""
    try:
        idle(state())
    except Exception as error:
        return str(error)[:200] or type(error).__name__
    return ''


def stable():
    first = state()
    idle(first)
    time.sleep(.5)
    second = state()
    idle(second)
    assert first['toolhead']['print_time'] == second['toolhead']['print_time'], 'motion_started'
    return second


def http(port, path, timeout=10):
    conn = httpclient.HTTPConnection('127.0.0.1', port, timeout=timeout)
    try:
        conn.request('GET', path)
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


def api(path, port=LOCAL_PORT):
    status, body = http(port, path)
    assert status == 200, 'api_status_%d_%s' % (status, path)
    data = json.loads(body.decode('utf-8'))
    assert isinstance(data, dict) and 'result' in data, 'api_no_result_' + path
    return data['result']


def calibration():
    """The calibration lives in the Moonraker that restarts: closed phases only."""
    try:
        value = api('/machine/k1_control/status')
        phase, busy = value['phase'], value['busy']
    except Exception as error:
        raise RuntimeError('calibration_status_unreadable: ' + str(error)[:200])
    return {'phase': phase, 'busy': busy}


def calibration_idle():
    value = calibration()
    assert value['phase'] in CALIBRATION_CLOSED and value['busy'] is False, 'calibration_busy'


def meminfo():
    values = {}
    for line in (PROC / 'meminfo').read_text().splitlines():
        name, _, rest = line.partition(':')
        parts = rest.split()
        if parts and parts[0].isdigit():
            values[name] = int(parts[0])
    return {'available_kb': values['MemAvailable'],
            'swap_used_kb': values.get('SwapTotal', 0) - values.get('SwapFree', 0)}


def proc_status(pid):
    values = {}
    for line in (PROC / str(pid) / 'status').read_text().splitlines():
        name, _, rest = line.partition(':')
        values[name] = rest.strip()
    return values


def rss_kb(pid):
    return int(proc_status(pid)['VmRSS'].split()[0])


def workers(master):
    found = set()
    for entry in PROC.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if proc_status(entry.name).get('PPid') == str(master):
                found.add(entry.name)
        except OSError:
            continue  # the process ended meanwhile
    return found


def alive(pidfile):
    pid = pidfile.read_text().strip() if pidfile.exists() else ''
    return pid if pid.isdigit() and (PROC / pid).exists() else ''


def running(pidfile, code):
    pid = alive(pidfile)
    assert pid, code
    return pid


def service(script, action):
    result = subprocess.run([script, action], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=30)
    assert result.returncode == 0, 'service_' + action + '_failed'


def stop_moonraker():
    """S56 removes the pid file at once: the process itself is waited for."""
    pid = running(MOONRAKER_PID, 'moonraker_not_running')
    service(MOONRAKER_SERVICE, 'stop')
    deadline = time.monotonic() + 15
    while (PROC / pid).exists() and time.monotonic() < deadline:
        time.sleep(.2)
    assert not (PROC / pid).exists(), 'old_process_remains'
    return pid


def reload_gateway():
    """S57 reload: the master stays, its workers are replaced once the new
    configuration is read. nginx keeps the old one without a word when it
    cannot read the new: a new worker is the only proof."""
    master = running(NGINX_PID, 'gateway_not_running')
    before = workers(master)
    service(GATEWAY_SERVICE, 'reload')
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        assert (PROC / master).exists() and NGINX_PID.read_text().strip() == master, \
            'gateway_master_changed'
        if workers(master) - before:
            return
        time.sleep(.2)
    raise RuntimeError('nginx_reload_not_proven')


def nginx_test(path):
    """The gateway's own binary and prefix, the way S57 starts it."""
    result = subprocess.run([NGINX, '-t', '-g', 'error_log stderr;', '-c', path,
                             '-p', NGINX_PREFIX],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    return result.returncode, result.stderr.decode(errors='replace')[-600:]


def import_check(sources):
    request = {'root': MOONRAKER_ROOT, 'directory': COMPONENTS, 'order': MODULES,
               'materials': MATERIAL_DATABASE,
               'sources': {name: base64.b64encode(sources[name]).decode() for name in MODULES}}
    result = subprocess.run([PYTHON, '-B', '-I', '-c', CHECK],
                            input=base64.b64encode(json.dumps(request).encode()),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    assert result.returncode == 0, 'import_check_failed: ' + \
        result.stderr.decode(errors='replace')[-400:]
    lines = result.stdout.decode(errors='replace').strip().splitlines()
    value = json.loads(lines[-1]) if lines else {}
    assert value.get('status') == 'IMPORT_OK', 'import_check_unclear'
    assert value['materials'] > 0, 'material_database_unusable: ' + str(value['error'])[:200]
    return value


def conf_candidate(live):
    assert SECTION not in [line.strip() for line in live.split(b'\n')], \
        'moonraker_section_already_present'
    text = live if live.endswith(b'\n') else live + b'\n'
    if not text.endswith(b'\n\n'):
        text += b'\n'
    return text + CONF_BLOCK


def nginx_candidate(live):
    assert live.count(NGINX_ANCHOR) == 1, 'nginx_anchor_not_unique'
    assert PREFIX.encode() not in live, 'nginx_block_already_present'
    return live.replace(NGINX_ANCHOR, NGINX_BLOCK + NGINX_ANCHOR, 1)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def facts(path):
    path = Path(path)
    if not path.exists():
        return None
    return {'sha256': digest(path), 'size': path.stat().st_size,
            'mode': oct(stat.S_IMODE(path.stat().st_mode))}


def bytecode():
    cache = Path(COMPONENTS) / '__pycache__'
    return sorted(entry.name for entry in cache.glob(COMPONENT + '*.pyc')) if cache.exists() else []


def changes(manifest):
    """(path, before, after) for every path the installation writes."""
    value = [(entry['destination'], entry['before_sha256'], entry['sha256'])
             for entry in manifest['files']]
    for key in ('moonraker_conf', 'nginx'):
        value.append((manifest[key]['path'], manifest[key]['before_sha256'],
                      manifest[key]['sha256']))
    return value


def saved(path):
    return BACKUP / 'before' / Path(path).name


def backup_intact(manifest):
    for path, before, _ in changes(manifest):
        if before is not None:
            assert digest(saved(path)) == before, 'backup_corrupt'


def replace(target, data, mode):
    target = Path(target)
    assert not target.is_symlink(), 'unexpected_symlink'
    stage = Path(str(target) + STAGE_SUFFIX)
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


def put_back(path, before):
    modes = json.loads((BACKUP / 'modes.json').read_text(encoding='utf-8'))
    source = saved(path)
    assert digest(source) == before, 'backup_corrupt'
    replace(path, source.read_bytes(), int(modes[path], 8))


def restore(manifest):
    """Every changed file back, every new one removed, the spool state moved
    into the backup (never deleted), the gateway reloaded if it changed.
    Moonraker must be stopped: its component writes on close."""
    for path, before, _ in changes(manifest):
        if path == NGINX_CONF:
            continue
        if before is None:
            if Path(path).exists():
                Path(path).unlink()
        elif digest(path) != before:
            put_back(path, before)
    cache = Path(COMPONENTS) / '__pycache__'
    for name in bytecode():
        (cache / name).unlink()
    moved = ''
    if Path(STATE_DIR).exists():
        moved = str(BACKUP / ('spools-state-%d' % int(time.time())))
        os.replace(STATE_DIR, moved)
    if Path(NGINX_STAGE).exists():
        Path(NGINX_STAGE).unlink()
    before = manifest['nginx']['before_sha256']
    if digest(NGINX_CONF) != before:
        put_back(NGINX_CONF, before)
        reload_gateway()
    for path, before, _ in changes(manifest):
        assert digest(path) == before, 'rollback_hash_mismatch_' + Path(path).name
    assert bytecode() == [], 'rollback_bytecode_left'
    return moved


def receipt(status, **details):
    value = dict({'status': status, 'time': time.time()}, **details)
    if BACKUP.exists():
        (BACKUP / 'receipt.json').write_text(json.dumps(value), encoding='utf-8')
    return value


def check_server(info, loaded):
    failed = info.get('failed_components')
    assert failed == [], 'failed_components: ' + ','.join(str(name) for name in failed or ['?'])
    assert 'k1_control' in info['components'], 'moonraker_not_k1_control'
    assert (COMPONENT in info['components']) is loaded, \
        'component_not_loaded' if loaded else 'component_loaded'


def wait_moonraker(oldpid, loaded):
    """The new process answers, Klipper is ready for it, and the component is
    there (`loaded`) or gone. Moonraker answers once its components are
    initialised: a failed one is final at once."""
    deadline = time.monotonic() + READY_SECONDS
    last = ''
    while time.monotonic() < deadline:
        try:
            pid = running(MOONRAKER_PID, 'moonraker_not_running')
            assert pid != oldpid, 'process_not_replaced'
            info = api('/server/info')
        except Exception as error:
            last = str(error)
            time.sleep(1)
            continue
        check_server(info, loaded)
        if info['klippy_state'] == 'ready':
            return pid, info
        last = 'klippy_' + str(info['klippy_state'])
        time.sleep(1)
    raise RuntimeError('moonraker_not_ready: ' + last)


def spools_ready(fresh):
    """Writable, its material base read, Klipper and the CFS seen; a fresh
    library has nothing waiting. A library that cannot save is a failed
    installation."""
    value = api(PREFIX + 'status')
    assert value['version'] == 1, 'spools_version_changed'
    assert value['read_only'] == '', 'spools_read_only: ' + str(value['read_only'])[:200]
    store = value['store']
    assert store['locked'] == '' and store['damaged'] == [] and store['quarantined'] == '', \
        'spools_store_damaged'
    materials = value['materials']
    assert materials['error'] == '' and materials['count'] > 0, \
        'spools_materials: ' + str(materials['error'])[:200]
    assert value['klippy']['connected'] is True, 'spools_klippy_not_connected'
    assert value['klippy']['cfs_ready'] is True, 'spools_cfs_not_seen'
    assert value['klippy']['printing'] is False, 'spools_sees_a_print'
    assert value['slots_error'] == '', 'spools_slots: ' + str(value['slots_error'])[:200]
    if fresh:
        assert value['pending_cfs'] == {} and value['unsaved_writes'] == [], \
            'spools_writes_pending'
    return value


def wait_spools():
    deadline = time.monotonic() + SPOOLS_SECONDS
    last = ''
    while time.monotonic() < deadline:
        try:
            return spools_ready(True)
        except Exception as error:
            last = str(error)
            time.sleep(1)
    raise RuntimeError('spools_not_ready: ' + last)


def gateway(manifest):
    """What Mainsail loads through nginx: the pages, the spool endpoint, the overlay tag."""
    for entry in manifest['files']:
        path = Path(entry['destination'])
        if str(path.parent) != WWW:
            continue
        status, body = http(GATEWAY_PORT, '/bobines/' + path.name)
        assert status == 200 and sha(body) == entry['sha256'], 'gateway_page_' + path.name
    status, body = http(GATEWAY_PORT, PREFIX + 'status')
    assert status == 200 and json.loads(body.decode('utf-8'))['result']['version'] == 1, \
        'gateway_spools_status_%d' % status
    status, body = http(GATEWAY_PORT, '/index.html')
    assert status == 200 and TAG in body, 'gateway_overlay_missing'


def budget(manifest, pid, before):
    limits = manifest['budget']
    after = meminfo()
    rss = rss_kb(pid)
    assert rss <= limits['rss_kb'], 'moonraker_rss_over_budget_%d' % rss
    assert after['available_kb'] >= limits['available_kb'], \
        'memory_available_low_%d' % after['available_kb']
    growth = after['swap_used_kb'] - before['swap_used_kb'] if before else 0
    assert growth <= limits['swap_growth_kb'], 'swap_growth_%d' % growth
    return {'rss_kb': rss, 'available_kb': after['available_kb'], 'swap_growth_kb': growth}


def survey(manifest):
    """Everything the manifest pins, read at rest; nothing is sent or changed."""
    try:
        stable()
    except AssertionError as error:
        return {'status': 'BUSY', 'problem': str(error)}
    conf = Path(MOONRAKER_CONF).read_bytes()
    nginx = Path(NGINX_CONF).read_bytes()
    sections = [line.strip() for line in conf.split(b'\n')]
    report = {
        'status': 'SURVEY_OK',
        'files': {entry['destination']: facts(entry['destination'])
                  for entry in manifest['files']},
        'directories': {path: oct(stat.S_IMODE(os.stat(path).st_mode))
                        for path in (WWW, COMPONENTS) if os.path.isdir(path)},
        'bytecode': bytecode(),
        'moonraker_conf': dict(facts(MOONRAKER_CONF), section=SECTION in sections,
                               sections=[line.decode(errors='replace') for line in sections
                                         if line.startswith(b'[')],
                               candidate_sha256=None if SECTION in sections
                               else sha(conf_candidate(conf))),
        'nginx': dict(facts(NGINX_CONF), anchors=nginx.count(NGINX_ANCHOR),
                      block=PREFIX.encode() in nginx,
                      locations=[line.strip().decode(errors='replace')
                                 for line in nginx.split(b'\n')
                                 if line.strip().startswith(b'location')],
                      candidate_sha256=sha(nginx_candidate(nginx))
                      if nginx.count(NGINX_ANCHOR) == 1 and PREFIX.encode() not in nginx
                      else None),
        'pins': {path: digest(path) for path in PIN_CANDIDATES},
        'binaries': {path: os.path.exists(path) for path in (PYTHON, NGINX, NGINX_PREFIX)},
        'state_dir': os.path.exists(STATE_DIR),
        'material_database': facts(MATERIAL_DATABASE) is not None,
        'material_database_size': os.path.getsize(MATERIAL_DATABASE)
        if os.path.exists(MATERIAL_DATABASE) else 0,
        'gcodes': os.path.isdir(GCODES),
        'backup': BACKUP.exists(),
        'stage': [path for path, _, _ in changes(manifest)
                  if os.path.exists(path + STAGE_SUFFIX)],
    }
    info = api('/server/info')
    report['server'] = {key: info.get(key) for key in (
        'klippy_state', 'components', 'failed_components', 'moonraker_version')}
    report['server']['warnings'] = [str(text)[:300] for text in info.get('warnings') or []]
    roots = api('/server/files/roots')
    report['gcodes_root'] = [root.get('path') for root in roots if root.get('name') == 'gcodes']
    pid = running(MOONRAKER_PID, 'moonraker_not_running')
    report['moonraker'] = {'rss_kb': rss_kb(pid)}
    report['memory'] = meminfo()
    try:
        report['calibration'] = calibration()
    except RuntimeError as error:
        report['calibration'] = {'error': str(error)}
    master = running(NGINX_PID, 'gateway_not_running')
    report['gateway'] = {'workers': len(workers(master))}
    report['kctrl_filament'] = 'KCTRL_FILAMENT' in klippy('gcode/help', {})
    return report


def run(request):
    manifest = request['manifest']
    assert manifest['name'] == NAME, 'manifest_mismatch'
    assert manifest['moonraker_conf']['path'] == MOONRAKER_CONF, 'manifest_mismatch'
    assert manifest['nginx']['path'] == NGINX_CONF, 'manifest_mismatch'
    assert manifest['state_dir'] == STATE_DIR and manifest['backup'] == str(BACKUP), \
        'manifest_mismatch'
    for entry in manifest['files']:
        assert str(Path(entry['destination']).parent) in (COMPONENTS, WWW), 'destination_outside'
    written = [path for path, _, _ in changes(manifest)]
    names = [Path(path).name for path, before, _ in changes(manifest) if before is not None]
    assert len(set(names)) == len(names), 'backup_names_collide'
    protected = manifest['protected']
    assert not set(written) & set(protected), 'target_also_protected'
    mode = request['mode']
    assert mode in ('survey', 'preflight', 'install', 'validate', 'rollback'), 'invalid_mode'

    if mode == 'survey':
        return survey(manifest)
    assert manifest['surveyed'] is True, 'manifest_not_surveyed'

    if mode == 'validate':
        pinned(protected)
        stable()
        for path, _, after in changes(manifest):
            assert digest(path) == after, 'candidate_not_installed_' + Path(path).name
        backup_intact(manifest)
        check_server(api('/server/info'), True)
        value = spools_ready(False)
        gateway(manifest)
        memory = budget(manifest, running(MOONRAKER_PID, 'moonraker_not_running'), None)
        return {'status': 'VALIDATED_OK', 'revision': value['revision'],
                'materials': value['materials']['count'], 'slots': len(value['slots']),
                'spools': len(value['spools']), 'memory': memory}

    if mode == 'rollback':
        pinned(protected)
        stable()
        backup_intact(manifest)
        for path, before, after in changes(manifest):
            assert digest(path) in (before, after), 'rollback_foreign_file_' + Path(path).name
        # A rollback stopped halfway may have left Moonraker down: no
        # calibration runs then, and the rollback can be run again.
        oldpid = alive(MOONRAKER_PID)
        if oldpid:
            calibration_idle()
        problems, moved = recover(manifest, oldpid)
        if problems:
            return receipt('ROLLBACK_INCOMPLETE', problems=problems, state_moved_to=moved)
        stable()
        return retire('rolled-back', receipt('ROLLED_BACK', state_moved_to=moved))

    payload = {path: base64.b64decode(value, validate=True)
               for path, value in request['payload'].items()}
    assert sorted(payload) == sorted(entry['destination'] for entry in manifest['files']), \
        'payload_files_changed'
    for entry in manifest['files']:
        assert sha(payload[entry['destination']]) == entry['sha256'], 'payload_hash_changed'
    pinned(protected)
    for entry in manifest['files']:
        assert digest(entry['destination']) == entry['before_sha256'], \
            'target_not_at_baseline_' + Path(entry['destination']).name
    assert bytecode() == [], 'stale_bytecode'
    assert not os.path.exists(STATE_DIR), 'spool_state_already_present'
    assert not BACKUP.exists(), 'backup_already_exists'
    assert not any(os.path.exists(path + STAGE_SUFFIX) for path in written), 'stale_stage_file'
    conf = Path(MOONRAKER_CONF).read_bytes()
    assert sha(conf) == manifest['moonraker_conf']['before_sha256'], 'moonraker_conf_changed'
    conf_next = conf_candidate(conf)
    assert sha(conf_next) == manifest['moonraker_conf']['sha256'], 'moonraker_conf_candidate_changed'
    nginx = Path(NGINX_CONF).read_bytes()
    assert sha(nginx) == manifest['nginx']['before_sha256'], 'nginx_conf_changed'
    nginx_next = nginx_candidate(nginx)
    assert sha(nginx_next) == manifest['nginx']['sha256'], 'nginx_candidate_changed'
    info = api('/server/info')
    check_server(info, False)
    assert info['klippy_state'] == 'ready', 'moonraker_klippy_not_ready'
    calibration_idle()
    assert 'KCTRL_FILAMENT' in klippy('gcode/help', {}), 'kctrl_filament_missing'
    assert meminfo()['available_kb'] >= manifest['budget']['available_kb'], \
        'memory_available_low'
    sources = {Path(path).name[:-3]: data for path, data in payload.items()
               if str(Path(path).parent) == COMPONENTS}
    imported = import_check(sources)
    stable()
    if mode == 'preflight':
        return {'status': 'PREFLIGHT_OK', 'files': len(manifest['files']),
                'protected': len(protected), 'materials': imported['materials'],
                'memory': meminfo()}

    stage = Path(NGINX_STAGE)
    try:
        with stage.open('xb') as stream:
            stream.write(nginx_next)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(str(stage), stat.S_IMODE(os.stat(NGINX_CONF).st_mode))
        code, output = nginx_test(str(stage))
        assert code == 0, 'nginx_test_failed: ' + output
        modes = back_up(manifest)
        # Checked again right before the stop: a print launched meanwhile ends
        # the installation here, with nothing changed.
        idle(state())
        calibration_idle()
        oldpid = running(MOONRAKER_PID, 'moonraker_not_running')
        memory = meminfo()
    except Exception as error:
        if stage.exists():
            stage.unlink()
        if BACKUP.exists():
            shutil.rmtree(str(BACKUP))
        return {'status': 'NOT_INSTALLED_NOTHING_CHANGED', 'error': str(error)}
    try:
        oldpid = stop_moonraker()
        pinned(protected)
        for entry in manifest['files']:
            replace(entry['destination'], payload[entry['destination']], int(entry['mode'], 8))
        replace(MOONRAKER_CONF, conf_next, int(modes[MOONRAKER_CONF], 8))
        os.replace(str(stage), NGINX_CONF)
        for path, _, after in changes(manifest):
            assert digest(path) == after, 'candidate_hash_mismatch_' + Path(path).name
        receipt('FILES_REPLACED')
        reload_gateway()
        service(MOONRAKER_SERVICE, 'start')
        pid, started = wait_moonraker(oldpid, True)
        new = sorted(set(started.get('warnings') or []) - set(info.get('warnings') or []))
        assert not new, 'new_moonraker_warnings: ' + ' | '.join(new)[:300]
        value = wait_spools()
        assert isinstance(api(PREFIX + 'journal?limit=1')['entries'], list), 'spools_journal'
        gateway(manifest)
        used = budget(manifest, pid, memory)
        stable()
        pinned(protected)
        return receipt('INSTALLED_IDLE_OK', revision=value['revision'],
                       fresh=value['store']['fresh'], materials=value['materials']['count'],
                       slots=len(value['slots']), attention=len(value['attention']),
                       memory=used)
    except Exception as error:
        # Not at rest any more (a print started, Klipper unreadable): no
        # service is stopped or started under it. The backup stays; validate
        # or rollback runs once the printer is at rest again.
        problem = rest_problem()
        if problem:
            return receipt('INSTALL_STOPPED_NOT_AT_REST', error=str(error), rest=problem,
                           moonraker_running=bool(alive(MOONRAKER_PID)))
        problems, moved = recover(manifest, oldpid)
        if problems:
            return receipt('INSTALL_FAILED_RECOVERY_INCOMPLETE', error=str(error),
                           problems=problems, state_moved_to=moved)
        return retire('failed', receipt('INSTALL_FAILED_ROLLED_BACK', error=str(error),
                                        state_moved_to=moved))


def back_up(manifest):
    """Every file the installation changes, copied and checked, with its mode."""
    (BACKUP / 'before').mkdir(parents=True)
    modes = {}
    for path, before, _ in changes(manifest):
        if before is None:
            continue
        saved(path).write_bytes(Path(path).read_bytes())
        assert digest(saved(path)) == before, 'backup_corrupt'
        modes[path] = oct(stat.S_IMODE(os.stat(path).st_mode))
    (BACKUP / 'modes.json').write_text(json.dumps(modes), encoding='utf-8')
    (BACKUP / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    receipt('BACKED_UP')
    return modes


def recover(manifest, oldpid):
    """Stop whatever runs, put every file back, start and prove rest. Each
    step runs even after an earlier one failed; what failed is returned.
    Nothing is put back under a Moonraker that would not stop."""
    try:
        if alive(MOONRAKER_PID):
            stop_moonraker()
        assert not (oldpid and (PROC / oldpid).exists()), 'old_process_remains'
    except Exception as error:
        return ['moonraker_not_stopped: ' + str(error)[:300]], ''
    problems, moved = [], ''
    try:
        moved = restore(manifest)
    except Exception as error:
        problems.append(str(error)[:300])
    for step in (lambda: service(MOONRAKER_SERVICE, 'start'),
                 lambda: wait_moonraker(oldpid, False),
                 lambda: pinned(manifest['protected'])):
        try:
            step()
        except Exception as error:
            problems.append(str(error)[:300])
    return problems, moved


def retire(label, value):
    """The backup, its receipt and any moved spool state stay, under a dated
    name: the installation can then be tried again."""
    kept = BACKUP.parent / ('%s-%s-%d' % (NAME, label, int(time.time())))
    os.replace(str(BACKUP), str(kept))
    value['kept_in'] = str(kept)
    if value.get('state_moved_to'):
        value['state_moved_to'] = str(kept / Path(value['state_moved_to']).name)
    (kept / 'receipt.json').write_text(json.dumps(value), encoding='utf-8')
    return value


if __name__ == '__main__':
    print(json.dumps(run(json.loads(base64.b64decode(REQUEST_B64)))), flush=True)  # noqa: F821
