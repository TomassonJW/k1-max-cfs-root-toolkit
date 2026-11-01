"""Install, validate and roll back the spool manager entirely in a temporary
tree. The printer is replaced by a status dictionary, the two services by a
log of actions, Moonraker and the gateway by fake HTTP answers, the files by
temporary copies (document 102, ADR-075)."""

import ast
import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages/k1-control-v1/spool-manager-install-v1'
SPOOLS = ROOT / 'packages/k1-control-v1/spool-manager-v1'
GATEWAY_CONF = ROOT / 'packages/k1-control-v1/gateway-private-lan-no-auth-v1/nginx.conf'
DROP = object()
S56 = 'S56k1_control_moonraker'
S57 = 'S57k1_control_gateway'
PAGES = ['styles.css', 'bobines.js', 'logic.js', 'overlay.js', 'spools.js', 'spools-logic.js',
         'tares.json', 'LICENSE-SpoolmanDB.txt']
OLD_PAGES = PAGES[:4]
KEPT_PAGES = ['app.js', 'index.html', 'package.json']
CONF = (b'[server]\nhost: 127.0.0.1\nport: 7125\n\n'
        b'[k1_control]\nstate_path: /usr/data/k1-control-v1/state\n')
MATERIALS = {'result': {'list': [{'base': {
    'id': 'AB123', 'meterialType': 'PLA', 'brand': 'Synth', 'name': 'Synthetic PLA',
    'density': 1.24, 'diameter': 1.75}}]}}
BASE = {
    'webhooks': {'state': 'ready'},
    'print_stats': {'state': 'complete'},
    'virtual_sdcard': {'is_active': False},
    'pause_resume': {'is_paused': False},
    'idle_timeout': {'state': 'Idle'},
    'extruder': {'target': 0.0},
    'heater_bed': {'target': 0.0},
    'toolhead': {'print_time': 93138.4, 'estimated_print_time': 93739.5},
    'motion_report': {'live_velocity': 5.68e-14, 'live_extruder_velocity': 0.0},
    'box': {'enable': 1, 'state': 'connect', 't_command': ''},
    'kctrl_end': {'phase': 'failed', 'pending': False},
    'kctrl_start': {'phase': 'complete'},
    'kctrl_print_gate': {'pending': 0},
}


def load(name):
    spec = importlib.util.spec_from_file_location('spool_install_v1_' + name,
                                                  PACKAGE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def status(**changes):
    """The printer at rest; None removes an object, DROP removes a field."""
    value = copy.deepcopy(BASE)
    for name, update in changes.items():
        if update is None:
            del value[name]
            continue
        value[name] = dict(value[name], **update)
        for key in [key for key, item in value[name].items() if item is DROP]:
            del value[name][key]
    return value


def printing(machine):
    machine.status['print_stats']['state'] = 'printing'


def unreadable(machine):
    raise RuntimeError('klippy_socket_closed')


def probe_mode(folder, mode):
    """The mode a file shows after chmod: 0o644 reads back 0o666 on Windows."""
    probe = folder / 'probe-mode'
    probe.write_bytes(b'')
    os.chmod(str(probe), mode)
    value = stat.S_IMODE(probe.stat().st_mode)
    probe.unlink()
    return value


class Machine:
    def __init__(self, tmp_path, monkeypatch):
        self.tmp = tmp_path
        m = self.m = load('remote_install')
        k1c = tmp_path / 'k1c'
        current = k1c / 'current'
        root = current / 'moonraker/moonraker'
        paths = {
            'MOONRAKER_ROOT': root,
            'COMPONENTS': root / 'moonraker/components',
            'PYTHON': current / 'moonraker/moonraker-env/bin/python',
            'MOONRAKER_CONF': current / 'config/moonraker.conf',
            'NGINX': current / 'nginx/sbin/nginx',
            'NGINX_PREFIX': current / 'nginx/nginx',
            'NGINX_CONF': k1c / 'state/nginx-active.conf',
            'WWW': current / 'www/bobines',
            'MAINSAIL_INDEX': current / 'www/mainsail/index.html',
            'STATE_DIR': k1c / 'state/spools',
            'MATERIAL_DATABASE': tmp_path / 'data/material_database.json',
            'GCODES': tmp_path / 'data/gcodes',
            'MOONRAKER_SERVICE': tmp_path / 'init.d' / S56,
            'GATEWAY_SERVICE': tmp_path / 'init.d' / S57,
        }
        for name, path in paths.items():
            monkeypatch.setattr(m, name, str(path))
        monkeypatch.setattr(m, 'NGINX_STAGE', str(paths['NGINX_CONF']) + m.STAGE_SUFFIX)
        monkeypatch.setattr(m, 'BACKUP', k1c / 'backups' / m.NAME)
        monkeypatch.setattr(m, 'MOONRAKER_PID', tmp_path / 'run/k1-control-moonraker.pid')
        monkeypatch.setattr(m, 'NGINX_PID', tmp_path / 'run/k1-control-nginx.pid')
        self.proc = tmp_path / 'proc'
        monkeypatch.setattr(m, 'PROC', self.proc)
        self.absent = str(tmp_path / 'pins/absent.cfg')
        monkeypatch.setattr(m, 'PIN_CANDIDATES', [str(paths['WWW'] / name) for name in KEPT_PAGES]
                            + [m.MAINSAIL_INDEX, str(tmp_path / 'pins/kctrl_print_gate.py'),
                               self.absent])

        components = paths['COMPONENTS']
        (components / '__pycache__').mkdir(parents=True)
        (components / '__pycache__/klippy_apis.cpython-38.pyc').write_bytes(b'cache')
        (components / 'klippy_apis.py').write_bytes(b'# synthetic klippy_apis\n')
        paths['MOONRAKER_CONF'].parent.mkdir(parents=True)
        paths['MOONRAKER_CONF'].write_bytes(CONF)
        os.chmod(str(paths['MOONRAKER_CONF']), 0o640)
        paths['NGINX_CONF'].parent.mkdir(parents=True)
        paths['NGINX_CONF'].write_bytes(GATEWAY_CONF.read_bytes())
        paths['WWW'].mkdir(parents=True)
        for name in OLD_PAGES:
            (paths['WWW'] / name).write_bytes(('/* synthetic %s, before */\n' % name).encode())
        for name in KEPT_PAGES:
            (paths['WWW'] / name).write_bytes(('/* synthetic %s, kept */\n' % name).encode())
        paths['MAINSAIL_INDEX'].parent.mkdir(parents=True)
        paths['MAINSAIL_INDEX'].write_bytes(b'<html><head>' + m.TAG + b'</head></html>\n')
        (tmp_path / 'pins').mkdir()
        (tmp_path / 'pins/kctrl_print_gate.py').write_bytes(b'# synthetic gate\n')
        paths['MATERIAL_DATABASE'].parent.mkdir(parents=True)
        paths['MATERIAL_DATABASE'].write_text(json.dumps(MATERIALS), encoding='utf-8')
        paths['GCODES'].mkdir()
        for name in ('MOONRAKER_SERVICE', 'GATEWAY_SERVICE', 'PYTHON', 'NGINX'):
            paths[name].parent.mkdir(parents=True, exist_ok=True)
            paths[name].write_bytes(b'#!/bin/sh\n')
        paths['NGINX_PREFIX'].mkdir(parents=True)
        (k1c / 'backups').mkdir()
        (tmp_path / 'run').mkdir()
        self.proc.mkdir()
        self.write_meminfo()
        self.process('1834', '1', 30000)
        self.process('1420', '1')
        self.process('1421', '1420')
        m.MOONRAKER_PID.write_text('1834\n')
        m.NGINX_PID.write_text('1420\n')

        self.status = status()
        self.queries = 0
        self.hooks = {}
        self.gcode_help = {'KCTRL_FILAMENT': 'K1 Control filament', 'M115': 'Firmware'}
        self.actions = []
        self.pid = '1834'
        self.master = '1420'
        self.next_pid = 2000
        self.loaded = False
        self.failed = []
        self.klippy_state = 'ready'
        self.base_warnings = ['synthetic warning already there']
        self.warnings = list(self.base_warnings)
        self.calibration = {'phase': 'idle', 'busy': False}
        self.spools = {}
        self.page_status = {}
        self.starts = 0
        self.failing_starts = set()
        self.component_fails = False
        self.stuck_stop = False
        self.reload_failures = 0
        self.rss = 30000
        self.after_start = {}
        self.new_warning = ''
        self.nginx_answer = (0, '')
        self.nginx_calls = []
        self.imports = []
        self.clock = clock = [0.0]
        monkeypatch.setattr(m, 'time', types.SimpleNamespace(
            monotonic=lambda: clock[0], time=lambda: 1.0e9 + clock[0],
            sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds)))
        monkeypatch.setattr(m, 'klippy', self.klippy)
        monkeypatch.setattr(m, 'http', self.http)
        monkeypatch.setattr(m, 'service', self.service)
        monkeypatch.setattr(m, 'nginx_test', self.nginx_test)
        monkeypatch.setattr(m, 'import_check', self.import_check)
        self.build()

    # The printer side.

    def write_meminfo(self, available=90000, swap_free=120000):
        (self.proc / 'meminfo').write_text(
            'MemTotal:         240000 kB\nMemAvailable:   %d kB\n'
            'SwapTotal:      131072 kB\nSwapFree:       %d kB\n' % (available, swap_free))

    def process(self, pid, ppid, rss=None):
        (self.proc / pid).mkdir()
        lines = ['Name:\tsynthetic', 'PPid:\t' + ppid]
        if rss is not None:
            lines.append('VmRSS:\t%d kB' % rss)
        (self.proc / pid / 'status').write_text('\n'.join(lines) + '\n')

    def klippy(self, method, params):
        if method == 'gcode/help':
            return dict(self.gcode_help)
        assert method == 'objects/query', method
        self.queries += 1
        hook = self.hooks.get(self.queries)
        if hook:
            hook(self)
        found = {}
        for name, keys in params['objects'].items():
            if name in self.status:
                found[name] = {key: self.status[name][key] for key in keys
                               if key in self.status[name]}
        return {'eventtime': 1.0, 'status': copy.deepcopy(found)}

    def http(self, port, path, timeout=10):
        m = self.m
        if port == m.GATEWAY_PORT:
            if path.startswith('/bobines/'):
                name = path[len('/bobines/'):]
                if name in self.page_status:
                    return self.page_status[name], b'refused'
                page = Path(m.WWW) / name
                return (200, page.read_bytes()) if page.exists() else (404, b'')
            if path == '/index.html':
                return 200, Path(m.MAINSAIL_INDEX).read_bytes()
            if not self.pid:
                return 502, b'bad gateway'
        else:
            assert port == m.LOCAL_PORT, port
            if not self.pid:
                raise ConnectionRefusedError(111, 'Connection refused')
        result = self.moonraker(path)
        if result is None:
            return 404, b'{"error": {"code": 404}}'
        return 200, json.dumps({'result': result}).encode()

    def moonraker(self, path):
        m = self.m
        if path == '/server/info':
            return {'klippy_state': self.klippy_state,
                    'components': ['klippy_apis', 'file_manager', 'k1_control']
                    + (['kctrl_spools'] if self.loaded else []),
                    'failed_components': list(self.failed), 'warnings': list(self.warnings),
                    'moonraker_version': 'v0.8.0-synthetic'}
        if path == '/server/files/roots':
            return [{'name': 'config', 'path': '/synthetic/config'},
                    {'name': 'gcodes', 'path': m.GCODES}]
        if path == '/machine/k1_control/status':
            return dict(self.calibration) if self.calibration is not None else None
        if self.loaded and path == m.PREFIX + 'status':
            value = {'version': 1, 'revision': 3, 'read_only': '',
                     'store': {'locked': '', 'damaged': [], 'quarantined': '', 'fresh': True},
                     'materials': {'count': 1, 'error': ''},
                     'klippy': {'connected': True, 'cfs_ready': True, 'printing': False},
                     'slots_error': '', 'pending_cfs': {}, 'unsaved_writes': [],
                     'slots': [{'slot': 'T1A'}], 'attention': [], 'spools': []}
            value.update(copy.deepcopy(self.spools))
            return value
        if self.loaded and path == m.PREFIX + 'journal?limit=1':
            return {'entries': []}
        return None

    def service(self, script, action):
        m = self.m
        name = Path(script).name
        self.actions.append((name, action))
        if (name, action) == (S56, 'stop'):
            if m.MOONRAKER_PID.exists():
                m.MOONRAKER_PID.unlink()
            if self.pid and not self.stuck_stop:
                shutil.rmtree(str(self.proc / self.pid))
            self.pid, self.loaded = '', False
        elif (name, action) == (S56, 'start'):
            self.starts += 1
            if self.starts in self.failing_starts:
                raise AssertionError('service_start_failed')
            self.start()
        elif (name, action) == (S57, 'reload'):
            if self.reload_failures:
                self.reload_failures -= 1
                return
            for entry in list(self.proc.iterdir()):
                if entry.name.isdigit() and m.proc_status(entry.name).get('PPid') == self.master:
                    shutil.rmtree(str(entry))
            self.process(str(self.next_pid), self.master)
            self.next_pid += 1
        else:
            raise AssertionError('unexpected service call %s %s' % (name, action))

    def start(self):
        """Moonraker loads the component when its section and its four files
        are there; a component that fails leaves the store's bytecode."""
        m = self.m
        pid = str(self.next_pid)
        self.next_pid += 1
        self.process(pid, '1', self.after_start.get('rss', self.rss))
        m.MOONRAKER_PID.write_text(pid + '\n')
        self.pid = pid
        lines = [line.strip() for line in Path(m.MOONRAKER_CONF).read_bytes().split(b'\n')]
        section = m.SECTION in lines
        present = all((Path(m.COMPONENTS) / (name + '.py')).exists() for name in m.MODULES)
        cache = Path(m.COMPONENTS) / '__pycache__'
        self.loaded = section and present and not self.component_fails
        self.failed = ['kctrl_spools'] if section and not self.loaded else []
        if self.loaded:
            for name in m.MODULES:
                (cache / (name + '.cpython-38.pyc')).write_bytes(b'bytecode')
            Path(m.STATE_DIR).mkdir(parents=True, exist_ok=True)
            (Path(m.STATE_DIR) / 'library.json').write_text('{"spools": []}')
        elif section:
            (cache / 'kctrl_spools_store.cpython-38.pyc').write_bytes(b'bytecode')
        if 'available' in self.after_start or 'swap_free' in self.after_start:
            self.write_meminfo(self.after_start.get('available', 90000),
                               self.after_start.get('swap_free', 120000))
        self.warnings = self.base_warnings + ([self.new_warning]
                                              if section and self.new_warning else [])

    def nginx_test(self, path):
        self.nginx_calls.append(Path(path).read_bytes())
        return self.nginx_answer

    def import_check(self, sources):
        self.imports.append(sorted(sources))
        return {'status': 'IMPORT_OK', 'materials': 1, 'error': ''}

    # The workstation side.

    def build(self):
        m = self.m
        self.candidates = {}
        files = []
        for name in [module + '.py' for module in m.MODULES] + PAGES:
            folder = m.COMPONENTS if name.endswith('.py') else m.WWW
            destination = str(Path(folder) / name)
            data = ('/* synthetic %s, candidate */\n' % name).encode()
            self.candidates[destination] = data
            before = Path(destination).read_bytes() if name in OLD_PAGES else None
            files.append({'source': 'synthetic/' + name, 'destination': destination,
                          'before_sha256': sha(before) if before else None,
                          'sha256': sha(data), 'mode': '0644'})
        conf = Path(m.MOONRAKER_CONF).read_bytes()
        nginx = Path(m.NGINX_CONF).read_bytes()
        self.manifest = {
            'schema': 1, 'name': m.NAME, 'surveyed': True, 'files': files,
            'moonraker_conf': {'before_sha256': sha(conf), 'sha256': sha(m.conf_candidate(conf)),
                               'path': m.MOONRAKER_CONF, 'section': m.SECTION.decode(),
                               'block': m.CONF_BLOCK.decode()},
            'nginx': {'before_sha256': sha(nginx), 'sha256': sha(m.nginx_candidate(nginx)),
                      'path': m.NGINX_CONF, 'anchor': m.NGINX_ANCHOR.decode(),
                      'block': m.NGINX_BLOCK.decode()},
            'state_dir': m.STATE_DIR, 'backup': str(m.BACKUP),
            'budget': dict(load('build_manifest').BUDGET),
            'protected': {path: m.digest(path) for path in m.PIN_CANDIDATES if m.digest(path)},
        }

    def request(self, mode):
        value = {'mode': mode, 'manifest': copy.deepcopy(self.manifest)}
        if mode in ('preflight', 'install'):
            value['payload'] = {path: base64.b64encode(data).decode()
                                for path, data in self.candidates.items()}
        return value

    def run(self, mode):
        return self.m.run(self.request(mode))

    def tree(self, skip=('proc', 'run', 'k1c/backups')):
        value = {}
        for path in sorted(self.tmp.rglob('*')):
            relative = path.relative_to(self.tmp).as_posix()
            if path.is_dir() or any(relative == item or relative.startswith(item + '/')
                                    for item in skip):
                continue
            value[relative] = (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        return value

    def at_before(self):
        return all(self.m.digest(path) == before
                   for path, before, _ in self.m.changes(self.manifest))

    def at_after(self):
        return all(self.m.digest(path) == after
                   for path, _, after in self.m.changes(self.manifest))


@pytest.fixture
def machine(tmp_path, monkeypatch):
    return Machine(tmp_path, monkeypatch)


@pytest.fixture(scope='module')
def installer():
    return load('remote_install')


# Rest.

@pytest.mark.parametrize('changes,error', [
    ({'webhooks': {'state': 'shutdown'}}, 'klipper_not_ready'),
    ({'print_stats': {'state': 'printing'}}, 'job_busy'),
    ({'print_stats': {'state': 'paused'}}, 'job_busy'),
    ({'virtual_sdcard': {'is_active': True}}, 'sd_active'),
    ({'pause_resume': {'is_paused': True}}, 'paused'),
    ({'idle_timeout': {'state': 'Printing'}}, 'idle_timeout_printing'),
    ({'extruder': {'target': 140.0}}, 'heater_target_set'),
    ({'heater_bed': {'target': 55.0}}, 'heater_target_set'),
    ({'motion_report': {'live_velocity': 12.5}}, 'motion_active'),
    ({'motion_report': {'live_extruder_velocity': float('nan')}}, 'motion_active'),
    ({'toolhead': {'print_time': 93800.0}}, 'motion_queued'),
    ({'toolhead': {'estimated_print_time': None}}, 'motion_clock_unknown'),
    ({'box': {'state': 'disconnect'}}, 'cfs_not_ready'),
    ({'box': {'enable': 0}}, 'cfs_not_ready'),
    ({'box': {'t_command': 'T1A'}}, 'cfs_command_present'),
    ({'kctrl_end': {'pending': True}}, 'end_busy'),
    ({'kctrl_end': {'phase': 'rewinding'}}, 'end_active'),
    ({'kctrl_start': {'phase': 'loading'}}, 'start_busy'),
    ({'kctrl_print_gate': {'pending': 1}}, 'start_waiting_for_spools'),
    ({'kctrl_print_gate': None}, 'object_missing_kctrl_print_gate'),
    ({'kctrl_end': {'pending': DROP}}, 'field_missing_kctrl_end.pending'),
])
def test_rien_ne_redemarre_hors_du_repos(installer, changes, error):
    with pytest.raises(AssertionError, match=re.escape(error)):
        installer.idle(status(**changes))


@pytest.mark.parametrize('end', ['disabled', 'idle', 'complete', 'failed', 'shutdown'])
@pytest.mark.parametrize('start', ['disabled', 'idle', 'complete', 'failed'])
def test_les_proprietaires_au_repos_laissent_passer(installer, end, start):
    installer.idle(status(kctrl_end={'phase': end, 'pending': 0},
                          kctrl_start={'phase': start}, kctrl_print_gate={'pending': False}))


def test_un_mouvement_entre_deux_lectures_arrete_tout(machine):
    machine.hooks[2] = lambda mm: mm.status['toolhead'].update(print_time=93139.0)
    with pytest.raises(AssertionError, match='motion_started'):
        machine.m.stable()


# Survey.

def test_le_releve_ne_touche_a_rien_et_donne_ce_que_le_manifeste_epingle(machine):
    m = machine.m
    before = machine.tree(skip=())
    report = machine.run('survey')
    assert report['status'] == 'SURVEY_OK'
    assert machine.tree(skip=()) == before and machine.actions == []
    conf, nginx = report['moonraker_conf'], report['nginx']
    assert conf['sha256'] == machine.manifest['moonraker_conf']['before_sha256']
    assert conf['candidate_sha256'] == machine.manifest['moonraker_conf']['sha256']
    assert conf['section'] is False and conf['sections'] == ['[server]', '[k1_control]']
    assert nginx['sha256'] == machine.manifest['nginx']['before_sha256']
    assert nginx['candidate_sha256'] == machine.manifest['nginx']['sha256']
    assert nginx['anchors'] == 1 and nginx['block'] is False
    assert report['pins'][machine.absent] is None
    assert {path: value for path, value in report['pins'].items() if value} == \
        machine.manifest['protected']
    assert report['files'][str(Path(m.WWW) / 'spools.js')] is None
    assert report['files'][str(Path(m.WWW) / 'styles.css')]['sha256'] == \
        machine.manifest['files'][4]['before_sha256']
    assert report['bytecode'] == [] and report['stage'] == []
    assert report['state_dir'] is False and report['backup'] is False
    assert report['kctrl_filament'] is True and report['gcodes_root'] == [m.GCODES]
    assert report['gateway'] == {'workers': 1} and report['moonraker'] == {'rss_kb': 30000}
    assert report['calibration'] == {'phase': 'idle', 'busy': False}
    assert report['server']['warnings'] == machine.base_warnings


def test_le_releve_s_arrete_pendant_une_impression(machine):
    printing(machine)
    assert machine.run('survey') == {'status': 'BUSY', 'problem': 'job_busy'}


@pytest.mark.parametrize('mode', ['preflight', 'install', 'validate', 'rollback'])
def test_sans_releve_seul_le_releve_passe(machine, mode):
    machine.manifest['surveyed'] = False
    assert machine.run('survey')['status'] == 'SURVEY_OK'
    with pytest.raises(AssertionError, match='manifest_not_surveyed'):
        machine.run(mode)
    assert machine.actions == []


# Preflight and install.

def test_le_preflight_verifie_tout_sans_rien_ecrire(machine):
    before = machine.tree(skip=())
    result = machine.run('preflight')
    assert result['status'] == 'PREFLIGHT_OK' and result['files'] == 12
    assert result['protected'] == len(machine.manifest['protected']) == 5
    assert result['materials'] == 1
    assert machine.tree(skip=()) == before
    assert machine.actions == [] and machine.nginx_calls == []
    assert machine.imports == [sorted(machine.m.MODULES)]


def test_la_pose_complete_remplace_tout_au_repos_puis_se_valide(machine):
    m = machine.m
    conf_mode = stat.S_IMODE(os.stat(m.MOONRAKER_CONF).st_mode)
    result = machine.run('install')
    assert result['status'] == 'INSTALLED_IDLE_OK', result
    assert machine.actions == [(S56, 'stop'), (S57, 'reload'), (S56, 'start')]
    assert machine.at_after() and machine.loaded
    page_mode = probe_mode(machine.tmp, 0o644)
    for entry in machine.manifest['files']:
        assert stat.S_IMODE(os.stat(entry['destination']).st_mode) == page_mode
    assert stat.S_IMODE(os.stat(m.MOONRAKER_CONF).st_mode) == conf_mode
    assert Path(m.MOONRAKER_CONF).read_bytes() == CONF + b'\n' + m.CONF_BLOCK
    assert m.NGINX_BLOCK + m.NGINX_ANCHOR in Path(m.NGINX_CONF).read_bytes()
    assert machine.nginx_calls == [m.nginx_candidate(GATEWAY_CONF.read_bytes())]
    assert machine.imports == [sorted(m.MODULES)]
    saved = sorted(path.name for path in (m.BACKUP / 'before').iterdir())
    assert saved == sorted(OLD_PAGES + ['moonraker.conf', 'nginx-active.conf'])
    modes = json.loads((m.BACKUP / 'modes.json').read_text(encoding='utf-8'))
    assert sorted(modes) == sorted(path for path, before, _ in m.changes(machine.manifest)
                                   if before)
    assert json.loads((m.BACKUP / 'manifest.json').read_text(encoding='utf-8')) == \
        machine.manifest
    receipt = json.loads((m.BACKUP / 'receipt.json').read_text(encoding='utf-8'))
    assert receipt['status'] == 'INSTALLED_IDLE_OK'
    assert not any(Path(path + m.STAGE_SUFFIX).exists()
                   for path, _, _ in m.changes(machine.manifest))
    assert (result['materials'], result['slots'], result['fresh']) == (1, 1, True)
    assert result['memory'] == {'rss_kb': 30000, 'available_kb': 90000, 'swap_growth_kb': 0}
    validated = machine.run('validate')
    assert validated['status'] == 'VALIDATED_OK' and validated['materials'] == 1
    assert machine.actions == [(S56, 'stop'), (S57, 'reload'), (S56, 'start')]


def test_la_validation_avant_la_pose_est_refusee(machine):
    with pytest.raises(AssertionError, match='candidate_not_installed_kctrl_spools_store.py'):
        machine.run('validate')


def test_une_seconde_pose_est_refusee_sans_rien_toucher(machine):
    machine.run('install')
    after = machine.tree()
    machine.actions.clear()
    with pytest.raises(AssertionError, match='target_not_at_baseline_kctrl_spools_store.py'):
        machine.run('install')
    assert machine.tree() == after and machine.actions == []


@pytest.mark.parametrize('setup,error', [
    pytest.param(lambda machine: machine.hooks.update({3: printing}), 'job_busy',
                 id='print_started'),
    pytest.param(lambda machine: machine.hooks.update({3: unreadable}), 'klippy_socket_closed',
                 id='klipper_unreadable'),
    pytest.param(lambda machine: setattr(machine, 'nginx_answer',
                                         (1, 'nginx: [emerg] unexpected "}"')),
                 'nginx_test_failed', id='nginx_refused'),
    pytest.param(lambda machine: machine.hooks.update({3: lambda mm: setattr(
        mm, 'calibration', {'phase': 'mesh', 'busy': True})}), 'calibration_busy',
        id='calibration_started'),
])
def test_un_ecart_juste_avant_l_arret_annule_la_pose_sans_rien_changer(machine, setup, error):
    m = machine.m
    before = machine.tree()
    setup(machine)
    result = machine.run('install')
    assert result['status'] == 'NOT_INSTALLED_NOTHING_CHANGED' and error in result['error']
    assert machine.tree() == before and machine.actions == []
    assert list((m.BACKUP.parent).iterdir()) == [] and not Path(m.NGINX_STAGE).exists()


FAILURES = [
    pytest.param(lambda machine: setattr(machine, 'component_fails', True),
                 'failed_components: kctrl_spools', id='failed_components'),
    pytest.param(lambda machine: setattr(machine, 'new_warning', 'kctrl_spools: option unknown'),
                 'new_moonraker_warnings: kctrl_spools', id='new_moonraker_warnings'),
    pytest.param(lambda machine: machine.spools.update(read_only='disque plein'),
                 'spools_read_only: disque plein', id='spools_read_only'),
    pytest.param(lambda machine: machine.spools.update(
        materials={'count': 0, 'error': 'base illisible'}), 'spools_materials: base illisible',
        id='spools_materials'),
    pytest.param(lambda machine: machine.spools.update(
        klippy={'connected': True, 'cfs_ready': False, 'printing': False}),
        'spools_cfs_not_seen', id='spools_cfs_not_seen'),
    pytest.param(lambda machine: machine.spools.update(pending_cfs={'T1A': {'grams': 500}}),
                 'spools_writes_pending', id='spools_writes_pending'),
    pytest.param(lambda machine: setattr(machine, 'reload_failures', 1),
                 'nginx_reload_not_proven', id='nginx_reload_not_proven'),
    pytest.param(lambda machine: machine.page_status.update({'spools.js': 403}),
                 'gateway_page_spools.js', id='gateway_page'),
    pytest.param(lambda machine: machine.after_start.update(rss=50000),
                 'moonraker_rss_over_budget_50000', id='rss'),
    pytest.param(lambda machine: machine.after_start.update(swap_free=111000),
                 'swap_growth_9000', id='swap'),
    pytest.param(lambda machine: machine.after_start.update(available=60000),
                 'memory_available_low_60000', id='available'),
]


@pytest.mark.parametrize('setup,error', FAILURES)
def test_un_echec_apres_l_arret_remet_tout_en_place(machine, setup, error):
    m = machine.m
    original = machine.tree()
    setup(machine)
    result = machine.run('install')
    assert result['status'] == 'INSTALL_FAILED_ROLLED_BACK', result
    assert error in result['error']
    assert machine.tree() == original and machine.at_before()
    assert machine.actions[0] == (S56, 'stop') and machine.actions[-1] == (S56, 'start')
    if error == 'nginx_reload_not_proven':
        assert machine.actions == [(S56, 'stop'), (S57, 'reload'), (S57, 'reload'),
                                   (S56, 'start')]
    assert not machine.loaded and machine.failed == [] and m.bytecode() == []
    assert not m.BACKUP.exists() and not Path(m.STATE_DIR).exists()
    kept = Path(result['kept_in'])
    assert 'failed' in kept.name
    assert json.loads((kept / 'receipt.json').read_text(encoding='utf-8'))['status'] == \
        'INSTALL_FAILED_ROLLED_BACK'
    machine.clock[0] += 5
    machine.after_start.clear()
    machine.write_meminfo()
    machine.spools.clear()
    machine.page_status.clear()
    machine.component_fails, machine.new_warning = False, ''
    assert machine.run('install')['status'] == 'INSTALLED_IDLE_OK'


def test_la_bibliotheque_creee_avant_l_echec_est_gardee_dans_la_sauvegarde(machine):
    machine.page_status['spools.js'] = 403
    result = machine.run('install')
    assert result['status'] == 'INSTALL_FAILED_ROLLED_BACK'
    moved = Path(result['state_moved_to'])
    assert moved.parent == Path(result['kept_in']) and (moved / 'library.json').exists()


def test_une_remise_en_place_inachevee_garde_la_sauvegarde_puis_le_retour_arriere_finit(machine):
    m = machine.m
    original = machine.tree()
    machine.component_fails = True
    machine.failing_starts = {2}
    result = machine.run('install')
    assert result['status'] == 'INSTALL_FAILED_RECOVERY_INCOMPLETE', result
    assert any('service_start_failed' in text for text in result['problems'])
    assert any('moonraker_not_ready' in text for text in result['problems'])
    assert m.BACKUP.exists() and machine.at_before()
    machine.actions.clear()
    rolled = machine.run('rollback')
    assert rolled['status'] == 'ROLLED_BACK' and machine.actions == [(S56, 'start')]
    assert machine.tree() == original and not m.BACKUP.exists()


def test_un_moonraker_qui_ne_s_arrete_pas_ne_fait_rien_remettre(machine):
    m = machine.m
    machine.stuck_stop = True
    result = machine.run('install')
    assert result['status'] == 'INSTALL_FAILED_RECOVERY_INCOMPLETE'
    assert result['problems'] == ['moonraker_not_stopped: old_process_remains']
    assert machine.actions == [(S56, 'stop')]
    assert machine.at_before() and m.BACKUP.exists() and Path(m.NGINX_STAGE).exists()


def test_une_impression_lancee_apres_l_arret_laisse_les_services_tranquilles(machine):
    machine.hooks[4] = printing
    result = machine.run('install')
    assert result['status'] == 'INSTALL_STOPPED_NOT_AT_REST', result
    assert result['error'] == 'job_busy' and result['rest'] == 'job_busy'
    assert result['moonraker_running'] is True
    assert machine.actions == [(S56, 'stop'), (S57, 'reload'), (S56, 'start')]
    assert machine.m.BACKUP.exists() and machine.at_after()
    machine.status = status()
    assert machine.run('validate')['status'] == 'VALIDATED_OK'


def test_un_echec_suivi_d_une_impression_attend_le_repos_pour_revenir(machine):
    original = machine.tree()
    machine.component_fails = True
    machine.hooks[4] = printing
    result = machine.run('install')
    assert result['status'] == 'INSTALL_STOPPED_NOT_AT_REST', result
    assert 'failed_components' in result['error'] and result['rest'] == 'job_busy'
    assert machine.actions == [(S56, 'stop'), (S57, 'reload'), (S56, 'start')]
    assert machine.at_after()
    machine.status = status()
    assert machine.run('rollback')['status'] == 'ROLLED_BACK'
    assert machine.tree() == original


def test_un_klipper_illisible_apres_l_arret_compte_comme_pas_au_repos(machine):
    machine.component_fails = True
    machine.hooks[4] = unreadable
    result = machine.run('install')
    assert result['status'] == 'INSTALL_STOPPED_NOT_AT_REST'
    assert result['rest'] == 'klippy_socket_closed'
    assert machine.actions == [(S56, 'stop'), (S57, 'reload'), (S56, 'start')]


@pytest.mark.parametrize('mode', ['preflight', 'install'])
def test_un_fichier_protege_change_arrete_tout(machine, mode):
    m = machine.m
    (Path(m.WWW) / 'app.js').write_bytes(b'/* changed */\n')
    before = machine.tree()
    with pytest.raises(RuntimeError, match='protected_file_drift'):
        machine.run(mode)
    assert machine.tree() == before and machine.actions == []


def first(request):
    return sorted(request['payload'])[0]


@pytest.mark.parametrize('change,error', [
    (lambda machine, request: setattr(machine, 'calibration', {'phase': 'mesh', 'busy': True}),
     'calibration_busy'),
    (lambda machine, request: setattr(machine, 'calibration', {'phase': 'idle', 'busy': True}),
     'calibration_busy'),
    (lambda machine, request: setattr(machine, 'calibration', None),
     'calibration_status_unreadable'),
    (lambda machine, request: machine.gcode_help.pop('KCTRL_FILAMENT'),
     'kctrl_filament_missing'),
    (lambda machine, request: machine.write_meminfo(available=60000), 'memory_available_low'),
    (lambda machine, request: Path(machine.m.MOONRAKER_CONF).write_bytes(CONF + b'# edited\n'),
     'moonraker_conf_changed'),
    (lambda machine, request: Path(machine.m.NGINX_CONF).write_bytes(
        GATEWAY_CONF.read_bytes() + b'# edited\n'), 'nginx_conf_changed'),
    (lambda machine, request: (Path(machine.m.WWW) / 'styles.css').write_bytes(b'edited'),
     'target_not_at_baseline_styles.css'),
    (lambda machine, request: Path(machine.m.STATE_DIR).mkdir(), 'spool_state_already_present'),
    (lambda machine, request: machine.m.BACKUP.mkdir(), 'backup_already_exists'),
    (lambda machine, request: (Path(machine.m.COMPONENTS) / '__pycache__'
                               / 'kctrl_spools.cpython-38.pyc').write_bytes(b'old'),
     'stale_bytecode'),
    (lambda machine, request: (Path(machine.m.WWW) / 'styles.css.kctrl-spools-next')
     .write_bytes(b'half'), 'stale_stage_file'),
    (lambda machine, request: setattr(machine, 'loaded', True), 'component_loaded'),
    (lambda machine, request: setattr(machine, 'failed', ['webcam']), 'failed_components: webcam'),
    (lambda machine, request: setattr(machine, 'klippy_state', 'startup'),
     'moonraker_klippy_not_ready'),
    (lambda machine, request: request['payload'].update(
        {first(request): base64.b64encode(b'other').decode()}), 'payload_hash_changed'),
    (lambda machine, request: request['payload'].pop(first(request)), 'payload_files_changed'),
    (lambda machine, request: request['manifest']['files'][0].update(
        destination=str(Path(machine.m.MAINSAIL_INDEX).parent / 'x.js')), 'destination_outside'),
    (lambda machine, request: request['manifest'].update(name='other'), 'manifest_mismatch'),
    (lambda machine, request: request['manifest'].update(backup='/elsewhere'),
     'manifest_mismatch'),
    (lambda machine, request: request['manifest']['protected'].update(
        {machine.m.MOONRAKER_CONF: '0' * 64}), 'target_also_protected'),
    (lambda machine, request: request['manifest']['moonraker_conf'].update(sha256='0' * 64),
     'moonraker_conf_candidate_changed'),
    (lambda machine, request: request['manifest']['nginx'].update(sha256='0' * 64),
     'nginx_candidate_changed'),
    (lambda machine, request: request['manifest']['files'][4].update(
        destination=str(Path(machine.m.WWW) / 'nginx-active.conf')), 'backup_names_collide'),
    (lambda machine, request: request.update(mode='bogus'), 'invalid_mode'),
])
def test_le_preflight_refuse_sans_rien_toucher(machine, change, error):
    request = machine.request('preflight')
    change(machine, request)
    before = machine.tree(skip=())
    with pytest.raises((AssertionError, RuntimeError), match=re.escape(error)):
        machine.m.run(request)
    assert machine.tree(skip=()) == before
    assert machine.actions == [] and machine.nginx_calls == []


# Rollback.

def test_le_retour_arriere_rend_l_arbre_exact_et_garde_l_etat_des_bobines(machine):
    m = machine.m
    original = machine.tree()
    assert machine.run('install')['status'] == 'INSTALLED_IDLE_OK'
    machine.actions.clear()
    result = machine.run('rollback')
    assert result['status'] == 'ROLLED_BACK', result
    assert machine.actions == [(S56, 'stop'), (S57, 'reload'), (S56, 'start')]
    assert machine.tree() == original and machine.at_before()
    assert not machine.loaded and m.bytecode() == [] and not m.BACKUP.exists()
    kept = Path(result['kept_in'])
    assert 'rolled-back' in kept.name
    moved = Path(result['state_moved_to'])
    assert moved.parent == kept and (moved / 'library.json').exists()
    assert json.loads((kept / 'receipt.json').read_text(encoding='utf-8'))['status'] == \
        'ROLLED_BACK'
    machine.clock[0] += 5
    assert machine.run('install')['status'] == 'INSTALLED_IDLE_OK'


def test_un_retour_arriere_interrompu_se_relance(machine):
    m = machine.m
    original = machine.tree()
    machine.run('install')
    machine.failing_starts = {machine.starts + 1}
    machine.actions.clear()
    result = machine.run('rollback')
    assert result['status'] == 'ROLLBACK_INCOMPLETE', result
    assert any('service_start_failed' in text for text in result['problems'])
    assert m.BACKUP.exists() and machine.at_before()
    assert machine.actions == [(S56, 'stop'), (S57, 'reload'), (S56, 'start')]
    machine.actions.clear()
    again = machine.run('rollback')
    assert again['status'] == 'ROLLED_BACK' and machine.actions == [(S56, 'start')]
    assert machine.tree() == original
    assert [path.name for path in Path(again['kept_in']).iterdir()
            if path.name.startswith('spools-state-')]


@pytest.mark.parametrize('change,error', [
    (lambda machine: (Path(machine.m.WWW) / 'styles.css').write_bytes(b'edited'),
     'rollback_foreign_file_styles.css'),
    (printing, 'job_busy'),
    (lambda machine: (machine.m.BACKUP / 'before/styles.css').write_bytes(b'edited'),
     'backup_corrupt'),
])
def test_le_retour_arriere_refuse_sans_rien_toucher(machine, change, error):
    machine.run('install')
    change(machine)
    machine.actions.clear()
    before = machine.tree(skip=('proc', 'run'))
    with pytest.raises(AssertionError, match=re.escape(error)):
        machine.run('rollback')
    assert machine.tree(skip=('proc', 'run')) == before and machine.actions == []


# Candidates.

@pytest.mark.parametrize('live', [b'[server]\nport: 7125', b'[server]\nport: 7125\n',
                                  b'[server]\nport: 7125\n\n'])
def test_la_section_s_ajoute_apres_une_ligne_vide(installer, live):
    assert installer.conf_candidate(live) == b'[server]\nport: 7125\n\n' + installer.CONF_BLOCK


def test_une_section_deja_la_est_refusee(installer):
    with pytest.raises(AssertionError, match='moonraker_section_already_present'):
        installer.conf_candidate(b'[server]\n  [kctrl_spools]  \nstate_path: x\n')


@pytest.mark.parametrize('live,error', [
    (lambda m: GATEWAY_CONF.read_bytes() + m.NGINX_ANCHOR, 'nginx_anchor_not_unique'),
    (lambda m: GATEWAY_CONF.read_bytes().replace(m.NGINX_ANCHOR, b''), 'nginx_anchor_not_unique'),
    (lambda m: m.nginx_candidate(GATEWAY_CONF.read_bytes()), 'nginx_block_already_present'),
])
def test_la_passerelle_refuse_une_ancre_douteuse(installer, live, error):
    with pytest.raises(AssertionError, match=error):
        installer.nginx_candidate(live(installer))


def test_le_bloc_de_la_passerelle_s_insere_dans_la_configuration_du_depot(installer):
    live = GATEWAY_CONF.read_bytes()
    assert b'\r' not in live and live.count(b'proxy_pass') == 3
    after = installer.nginx_candidate(live)
    assert after.count(b'proxy_pass') == 4
    assert installer.NGINX_BLOCK + installer.NGINX_ANCHOR in after
    assert b'location ^~ /machine/k1_control/spools/ {' in after
    assert b'proxy_read_timeout 90s;' in after
    assert after.replace(installer.NGINX_BLOCK, b'', 1) == live


# The import in Moonraker's interpreter, for real.

def fake_moonraker(root, signature='self, objects, callback=None, default=None'):
    (root / 'moonraker/components').mkdir(parents=True, exist_ok=True)
    (root / 'moonraker/__init__.py').write_text('')
    (root / 'moonraker/common.py').write_text(
        'class RequestType:\n    GET = 1\n    POST = 2\n\n\nclass WebRequest:\n    pass\n')
    (root / 'moonraker/components/__init__.py').write_text('')
    (root / 'moonraker/components/klippy_apis.py').write_text(
        'class KlippyAPI:\n    async def subscribe_objects(%s):\n        pass\n' % signature)


@pytest.fixture
def importer(tmp_path, monkeypatch):
    m = load('remote_install')
    root = tmp_path / 'moonraker-root'
    fake_moonraker(root)
    database = tmp_path / 'material_database.json'
    database.write_text(json.dumps(MATERIALS), encoding='utf-8')
    monkeypatch.setattr(m, 'MOONRAKER_ROOT', str(root))
    monkeypatch.setattr(m, 'COMPONENTS', str(root / 'moonraker/components'))
    monkeypatch.setattr(m, 'PYTHON', sys.executable)
    monkeypatch.setattr(m, 'MATERIAL_DATABASE', str(database))
    m.fake_root, m.fake_database = root, database
    return m


def sources(m):
    return {name: (SPOOLS / (name + '.py')).read_bytes() for name in m.MODULES}


def test_les_vrais_composants_s_importent_sans_rien_ecrire(importer):
    before = sorted(path.relative_to(importer.fake_root).as_posix()
                    for path in importer.fake_root.rglob('*'))
    result = importer.import_check(sources(importer))
    assert result == {'status': 'IMPORT_OK', 'materials': 1, 'error': ''}
    assert sorted(path.relative_to(importer.fake_root).as_posix()
                  for path in importer.fake_root.rglob('*')) == before


def test_une_erreur_de_syntaxe_arrete_l_import(importer):
    broken = dict(sources(importer), kctrl_spools_counter=b'def broken(:\n')
    with pytest.raises(AssertionError, match='import_check_failed'):
        importer.import_check(broken)


def test_un_moonraker_sans_rappel_d_abonnement_est_refuse(importer):
    fake_moonraker(importer.fake_root, signature='self, objects, default=None')
    with pytest.raises(AssertionError, match='subscribe_signature_changed'):
        importer.import_check(sources(importer))


def test_une_base_materiau_vide_est_refusee(importer):
    importer.fake_database.write_text('{"result": {"list": []}}', encoding='utf-8')
    with pytest.raises(AssertionError, match='material_database_unusable'):
        importer.import_check(sources(importer))


# The repository.

def test_le_manifeste_du_depot_suit_le_candidat_et_l_installateur(installer):
    m = installer
    build = load('build_manifest')
    manifest = json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['schema'] == 1 and manifest['name'] == m.NAME
    assert manifest['installer_sha256'] == sha((PACKAGE / 'remote_install.py').read_bytes())
    assert len(manifest['files']) == 12
    names = []
    for entry in manifest['files']:
        source = ROOT / entry['source']
        assert sha(source.read_bytes()) == entry['sha256'], entry['source']
        folder, name = entry['destination'].rsplit('/', 1)
        assert name == source.name and entry['mode'] == '0644'
        names.append(name)
        if folder == m.COMPONENTS:
            assert name[:-3] in m.MODULES and entry['before_sha256'] is None
        else:
            assert folder == m.WWW and entry['before_sha256'] == build.PAGES_BEFORE[name]
    assert sorted(names) == sorted([name + '.py' for name in m.MODULES] + list(build.PAGES_BEFORE))
    conf, nginx = manifest['moonraker_conf'], manifest['nginx']
    assert conf['path'] == m.MOONRAKER_CONF and conf['section'].encode() == m.SECTION
    assert conf['block'].encode() == m.CONF_BLOCK
    assert nginx['path'] == m.NGINX_CONF and nginx['anchor'].encode() == m.NGINX_ANCHOR
    assert nginx['block'].encode() == m.NGINX_BLOCK
    assert manifest['state_dir'] == m.STATE_DIR
    assert manifest['backup'] == m.K1C + '/backups/' + m.NAME
    assert manifest['budget'] == build.BUDGET
    assert manifest['effects'] == {
        'moonraker_restart_idle_only': True, 'gateway_reload': True, 'klipper_restart': False,
        'gcode': False, 'heating': False, 'motion': False, 'filament': False,
        'cfs_write': False, 'printer_cfg_change': False}
    filled = all(manifest[key][field] for key in ('moonraker_conf', 'nginx')
                 for field in ('before_sha256', 'sha256'))
    assert manifest['surveyed'] is (filled and bool(manifest['protected']))
    written = {path for path, _, _ in m.changes(manifest)}
    assert set(manifest['protected']) <= set(m.PIN_CANDIDATES)
    assert not set(manifest['protected']) & written


def decode(script):
    line, _, rest = script.partition(b'\n')
    prefix = 'REQUEST_B64 = '
    assert line.decode().startswith(prefix)
    return json.loads(base64.b64decode(ast.literal_eval(line.decode()[len(prefix):]))), rest


def test_l_envoi_du_releve_ne_porte_que_l_installateur():
    deploy = load('deploy')
    body, rest = decode(deploy.request('survey'))
    assert body['mode'] == 'survey' and 'payload' not in body
    assert rest == (PACKAGE / 'remote_install.py').read_bytes()


def test_l_envoi_du_preflight_porte_les_douze_fichiers_du_manifeste():
    deploy = load('deploy')
    body, _ = decode(deploy.request('preflight'))
    entries = {entry['destination']: entry['source'] for entry in body['manifest']['files']}
    assert sorted(body['payload']) == sorted(entries) and len(entries) == 12
    for destination, value in body['payload'].items():
        assert base64.b64decode(value) == (ROOT / entries[destination]).read_bytes()


def test_un_installateur_ou_un_fichier_modifie_n_est_pas_envoye(tmp_path, monkeypatch):
    deploy = load('deploy')
    installer = tmp_path / 'remote_install.py'
    installer.write_bytes((PACKAGE / 'remote_install.py').read_bytes() + b'\n')
    monkeypatch.setattr(deploy, 'INSTALLER', installer)
    with pytest.raises(SystemExit, match='remote_install.py differs'):
        deploy.request('survey')
    monkeypatch.setattr(deploy, 'INSTALLER', PACKAGE / 'remote_install.py')
    manifest = json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))
    manifest['files'][0]['sha256'] = '0' * 64
    altered = tmp_path / 'manifest.json'
    altered.write_text(json.dumps(manifest), encoding='utf-8')
    monkeypatch.setattr(deploy, 'MANIFEST', altered)
    with pytest.raises(SystemExit, match='differs from manifest.json'):
        deploy.request('preflight')


@pytest.mark.parametrize('argv', [['deploy.py', 'bogus'], ['deploy.py'],
                                  ['deploy.py', 'install', 'extra']])
def test_un_mode_inconnu_ne_part_pas(argv):
    with pytest.raises(SystemExit):
        load('deploy').main(argv)


def test_l_installateur_reste_lisible_par_le_python_3_8_de_la_k1(installer):
    ast.parse((PACKAGE / 'remote_install.py').read_text(encoding='utf-8'), feature_version=(3, 8))
    ast.parse(installer.CHECK, feature_version=(3, 8))
