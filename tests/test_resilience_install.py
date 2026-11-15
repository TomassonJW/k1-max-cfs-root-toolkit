"""Put resilience-v1 on the printer: four files together, refused or undone.

The printer is replaced by a status dictionary answered the way Klipper's
`objects/query` answers (a key an object does not publish comes back None),
the service by a log of actions, the files by temporary copies. The start
that comes up after the fake restart reads the head record with the real
`read_head` of the candidate (ADR-080, document 109).
"""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import types

import pytest

import test_resilience_gate as rg
import test_resilience_start as rs

# Each harness builds the candidate module only under its own fixture.
start_harness = rs.new_module
gate_harness = rg.new_module

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ROOT / 'packages/k1-control-v1'
PACKAGE = PACKAGES / 'resilience-v1'
RECOVERY = PACKAGES / 'start-load-recovery-v1'
PAGES = PACKAGES / 'spool-manager-install-v1'
END = PACKAGES / 'end-no-stock-flush-v5'
TOOLS = ['T%d' % index for index in range(16)]
SLOTS = ['T%s%s' % (box, slot) for box in '1234' for slot in 'ABCD']
WRAPPED = ['CANCEL_PRINT', 'END_PRINT', 'START_PRINT']
HEAD = 'filament_switch_sensor filament_sensor_2'
UPSTREAM = 'filament_switch_sensor filament_sensor'
GUARD = {'revision': 'retained-start-v1', 'installed': True, 'bin_latched': False,
         'minimum_z': 30.0, 'denied': 0, 'last_error': '',
         'cold_revision': 'cold-push-guard-v1', 'cold_installed': True, 'cold_refused': 0,
         'cold_last': ''}
SENSOR_STATUS = {'enabled': True, 'installed': True, 'revision': 'cfs-sensor-guard-v2',
                 'hook': 'inside_cold_guard', 'hooked': True, 'failure': '', 'blind': None}
NAMES = ['kctrl_start.py', 'kctrl_print_gate.py', 'logic.js', 'bobines.js']
MODULES, PAGE_FILES = NAMES[:2], NAMES[2:]
OLD = {'kctrl_start.py': b'# installed start-load-recovery-v1\n',
       'kctrl_print_gate.py': b'# installed gate, publishes no revision\n',
       'logic.js': b'// installed logic\n',
       'bobines.js': b'// installed page\n'}
NEW = {'kctrl_start.py': b'# candidate start resilience-v1\n',
       'kctrl_print_gate.py': b'# candidate gate resilience-v1\n',
       'logic.js': b'// candidate logic\n',
       'bobines.js': b'// candidate page\n'}
SIBLINGS = ['kctrl_start_policy.py', 'kctrl_start_context.py', 'kctrl_purge_guard.py',
            'kctrl_bin_motion.py', 'kctrl_sensor_guard.py', 'kctrl_end.py',
            'kctrl_slot_map.py', 'kctrl_tool_change.py']
PAGE_SIBLINGS = ['app.js', 'index.html', 'overlay.js', 'styles.css']
VENDOR = {
    'virtual_sdcard.py': b'must_pause_work\ndef is_active(self):\nrecord_tn_move_z(0)\nmove_z\n',
    'pause_resume.py': b'reportInformation\npause_command_sent\nsd_paused\ninside_error\n',
    'gcode_move.py': b'def reset_last_position(self):\n',
}
OLD_GATE = {'pending': 0, 'wrapped': 1}
NEW_GATE = {'pending': 0, 'wrapped': 1, 'revision': 'resilience-v1'}


def load():
    spec = importlib.util.spec_from_file_location('resilience_install',
                                                  PACKAGE / 'remote_install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def before_status(**changes):
    """The installed start at rest."""
    value = {'enabled': True, 'installed': True, 'phase': 'complete',
             'revision': 'start-load-recovery-v1', 'failure': '', 'recovery': None,
             'recovery_timeout': 180.0}
    value.update(changes)
    return value


def after_status(**changes):
    value = {'enabled': True, 'installed': True, 'phase': 'idle', 'revision': 'resilience-v1',
             'failure': '', 'recovery': None, 'recovery_timeout': 180.0,
             'head': None, 'head_saved': True, 'rest': None}
    value.update(changes)
    return value


def status(**changes):
    value = {
        'webhooks': {'state': 'ready'},
        'print_stats': {'state': 'complete'},
        'virtual_sdcard': {'is_active': False},
        'pause_resume': {'is_paused': False},
        'idle_timeout': {'state': 'Idle'},
        'extruder': {'target': 0.0},
        'heater_bed': {'target': 0.0},
        'toolhead': {'print_time': 93138.4, 'estimated_print_time': 93739.5},
        'motion_report': {'live_velocity': 5.68e-14, 'live_extruder_velocity': 0.0},
        'box': {'enable': 1, 'state': 'connect', 't_command': 'T1B', 'filament': 0,
                'auto_refill': 1,
                'T1': {'state': 'connect', 'filament': 'None', 'sn': 'SERIAL-T1'},
                'T2': {'state': 'connect', 'filament': 'None', 'uuid': 'SERIAL-T2'},
                'T3': {'state': 'None', 'filament': 'None'},
                'T4': {'state': 'None', 'filament': 'None'}},
        HEAD: {'filament_detected': True},
        # PC15: always "present" with the CFS.
        UPSTREAM: {'filament_detected': True},
        'kctrl_end': {'enabled': True, 'phase': 'complete', 'pending': False,
                      'wrapped': list(WRAPPED), 'revision': 'end-no-stock-flush-v5',
                      'auto_refill_restore_pending': False},
        'kctrl_start': before_status(),
        'kctrl_tool_change': {'wrapped': list(TOOLS), 'missing': [], 'reloads': list(SLOTS)},
        'kctrl_print_gate': dict(OLD_GATE),
        'kctrl_purge_guard': dict(GUARD),
        'kctrl_sensor_guard': dict(SENSOR_STATUS),
    }
    for key, update in changes.items():
        value[key] = dict(value[key], **update)
    return value


class Machine:
    """Temporary tree, fake Klipper status and service, same names as the printer."""

    def __init__(self, tmp_path, monkeypatch, loaded=None, surveyed=True):
        self.m = m = load()
        self.root = tmp_path
        extras = tmp_path / 'extras'
        www = tmp_path / 'www' / 'bobines'
        self.state_directory = tmp_path / 'state'
        self.cache = extras / '__pycache__'
        for folder in (self.cache, www, self.state_directory):
            folder.mkdir(parents=True)
        self.extras, self.www = extras, www
        self.log = tmp_path / 'klippy.log'
        self.log.write_bytes(b'old line\n')
        self.pid = tmp_path / 'klippy.pid'
        self.pid.write_text('2210')
        self.head_file = self.state_directory / 'kctrl_head.json'
        printer = m.EXTRAS
        features = {name: m.FEATURES[printer + '/' + name] for name in VENDOR}
        # The temporary tree stands for the printer: same file names.
        for name, value in (('EXTRAS', extras.as_posix()), ('WWW', www.as_posix()),
                            ('START', extras.as_posix() + '/kctrl_start.py'),
                            ('GATE', extras.as_posix() + '/kctrl_print_gate.py'),
                            ('BYTECODE', self.cache.as_posix()),
                            ('BACKUP', tmp_path / 'backups' / 'resilience-v1'),
                            ('STATE', self.state_directory.as_posix()),
                            ('HEAD_FILE', self.head_file.as_posix()),
                            ('LOG', self.log), ('PIDFILE', self.pid)):
            monkeypatch.setattr(m, name, value)
        self.files = {name: (extras if name in MODULES else www) / name for name in NAMES}
        self.destination = {name: self.files[name].as_posix() for name in NAMES}
        assert list(m.targets()) == [self.destination[name] for name in NAMES]
        self.modes = {}
        if os.name == 'nt':
            # No permission bits there: the table stands for them.
            monkeypatch.setattr(m, 'mode_of', lambda path: self.modes.get(
                Path(path).as_posix(), 0o644))
        for name in NAMES:
            self.files[name].write_bytes(OLD[name])
            self.chmod(self.files[name], 0o644)
        protected = {}
        for name in SIBLINGS + PAGE_SIBLINGS:
            path = self.sibling(name)
            path.write_bytes(('# %s\n' % name).encode())
            protected[path.as_posix()] = sha(path.read_bytes())
        assert sorted(protected) == sorted(m.siblings())
        self.vendor = {}
        for name, data in VENDOR.items():
            path = extras / name
            path.write_bytes(data)
            self.vendor[name] = path
        self.cfs = extras / 'box_wrapper.so'
        self.cfs.write_bytes(b'\x00inside_error\x00record_tn_move_z\x00last_err\x00move_z\x00')
        monkeypatch.setattr(m, 'FEATURES', {str(self.vendor[name]): needles
                                            for name, needles in features.items()})
        monkeypatch.setattr(m, 'CFS_FILES', [str(extras / 'box.py'), str(self.cfs)])
        clock = [0.0]
        monkeypatch.setattr(m, 'time', types.SimpleNamespace(
            monotonic=lambda: clock[0], time=lambda: 1.0e9 + clock[0],
            sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds)))
        monkeypatch.setattr(m, 'compiles', lambda name, data: compile(data, name, 'exec'))
        self.actions = []
        self.writes = []
        self.fail_write = None
        replace = m.replace

        def recording(path, data, mode):
            if len(self.writes) + 1 == self.fail_write:
                self.fail_write = None
                self.failing()
                raise OSError('No space left on device')
            name = Path(path).name
            self.writes.append((name, data))
            if name == self.corrupt:
                # A disk that stores something else than what it was given.
                self.corrupt, data = None, data[:-1]
            if name == self.wrong_mode:
                self.wrong_mode, mode = None, 0o600
            replace(path, data, mode)
            self.modes[Path(path).as_posix()] = mode
        monkeypatch.setattr(m, 'replace', recording)
        self.failing = lambda: None
        self.corrupt = self.wrong_mode = None
        self.at_stop = lambda: None
        self.running = True
        self.loaded = loaded
        self.status = status()
        self.calls = 0
        self.at_call = {}
        monkeypatch.setattr(m, 'state', self.state)
        monkeypatch.setattr(m, 'service', self.service)
        monkeypatch.setattr(m, 'stop', self.stop)
        self.payloads = dict(NEW)
        self.manifest = {
            'name': m.NAME, 'surveyed': surveyed, 'protected': protected,
            'targets': [{'destination': self.destination[name],
                         'kind': 'module' if name in MODULES else 'page',
                         'before_sha256': sha(OLD[name]), 'sha256': sha(NEW[name])}
                        for name in NAMES],
        }

    def sibling(self, name):
        return (self.www if name in PAGE_SIBLINGS else self.extras) / name

    def chmod(self, path, mode):
        os.chmod(str(path), mode)
        self.modes[Path(path).as_posix()] = mode

    def mode(self, path):
        return self.m.mode_of(path)

    def engage(self, *slots):
        for slot in slots:
            self.status['box']['T' + slot[1]]['filament'] = slot[2]

    def state(self):
        """Answer as `objects/query` does: a key not published comes back None."""
        self.calls += 1
        if self.calls in self.at_call:
            self.at_call[self.calls]()
        if not self.running:
            raise RuntimeError('klippy_socket_closed')
        answer = {}
        for name, keys in self.m.QUERY.items():
            value = json.loads(json.dumps(self.status.get(name, {})))
            answer[name] = value if keys is None else {key: value.get(key) for key in keys}
        return answer

    def service(self, action):
        self.actions.append(action)
        if action == 'stop':
            self.running = False
            return
        if action != 'start':
            return
        self.running = True
        self.pid.write_text(str(int(self.pid.read_text()) + 1))
        # A new process: the route the CFS showed is gone.
        self.status = status(print_stats={'state': 'standby'})
        code = {name: self.files[name].read_bytes() for name in MODULES}
        if code['kctrl_start.py'] == NEW['kctrl_start.py']:
            start = after_status(head=rs.module.read_head(str(self.head_file)))
        elif code['kctrl_start.py'] == OLD['kctrl_start.py']:
            start = before_status(phase='idle')
        else:
            self.status['webhooks'] = {'state': 'error'}
            return
        if code['kctrl_print_gate.py'] == NEW['kctrl_print_gate.py']:
            gate = dict(NEW_GATE)
        elif code['kctrl_print_gate.py'] == OLD['kctrl_print_gate.py']:
            gate = dict(OLD_GATE)
        else:
            self.status['webhooks'] = {'state': 'error'}
            return
        if self.loaded:
            self.loaded(start, gate)
        for name in MODULES:
            (self.cache / (Path(name).stem + '.cpython-38.pyc')).write_bytes(code[name])
        self.status['kctrl_start'] = start
        self.status['kctrl_print_gate'] = gate
        with self.log.open('ab') as stream:
            stream.write(b'[INFO] kctrl_print_gate: wrapped\n[INFO] kctrl_start: ready\n')

    def stop(self):
        pid = self.pid.read_text()
        self.at_stop()
        self.service('stop')
        return pid

    def run(self, mode, payloads=None):
        sent = self.payloads if payloads is None else payloads
        return self.m.run({'mode': mode, 'manifest': self.manifest, 'payloads': {
            self.destination.get(name, name): base64.b64encode(data).decode()
            for name, data in sent.items()}})

    def content(self):
        return {name: self.files[name].read_bytes() for name in NAMES}

    def at_before(self):
        assert self.content() == OLD
        assert all(self.mode(self.files[name]) == 0o644 for name in NAMES)

    def record(self):
        return rs.module.read_head(str(self.head_file))

    def archives(self):
        return sorted(path.name for path in (self.root / 'backups').iterdir()) \
            if (self.root / 'backups').exists() else []


def untouched(machine):
    assert machine.actions == [] and machine.writes == []
    assert not machine.m.BACKUP.exists()
    machine.at_before()


# --- survey -------------------------------------------------------------------


def test_le_releve_lit_les_epingles_sans_rien_changer(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    result = machine.run('survey')
    assert result['status'] == 'SURVEY_OK'
    assert result['drift'] == [] and result['target_drift'] == []
    for name in NAMES:
        found = result['targets'][machine.destination[name]]
        assert found['sha256'] == found['expected'] == sha(OLD[name])
    assert len(result['protected']) == len(SIBLINGS + PAGE_SIBLINGS)
    assert result['bytecode'] == [] and result['stage'] == [] and result['backup'] is False
    assert result['features'] == {'cfs': {'inside_error': True, 'record_tn_move_z': True,
                                          'last_err': True, 'move_z': True}}
    assert result['state_directory'] is True and result['head_record'] is None
    assert result['head_seed'] is None
    rest = result['rest']
    assert rest['start_revision'] == 'start-load-recovery-v1' and rest['gate_revision'] is None
    assert rest['gate_wrapped'] == 1 and rest['sensor_revision'] == 'cfs-sensor-guard-v2'
    assert rest['head_filament'] is True and rest['upstream_filament'] is True
    untouched(machine)


def test_le_releve_dit_la_case_qu_il_porterait(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    machine.engage('T1C')
    machine.head_file.write_text('{"schema": 1, "slot": "T2A"}')
    result = machine.run('survey')
    assert result['head_seed'] == 'T1C' and result['head_record'] == 'T2A'
    assert result['rest']['units'] == ['C', 'None']
    assert machine.record()['slot'] == 'T2A'


def test_le_releve_signale_un_fichier_qui_a_bouge(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    machine.sibling('kctrl_purge_guard.py').write_bytes(b'changed elsewhere\n')
    machine.sibling('overlay.js').write_bytes(b'changed elsewhere\n')
    machine.files['logic.js'].write_bytes(b'// another page\n')
    result = machine.run('survey')
    assert result['drift'] == sorted([machine.sibling('kctrl_purge_guard.py').as_posix(),
                                      machine.sibling('overlay.js').as_posix()])
    assert result['target_drift'] == [machine.destination['logic.js']]


def test_le_releve_dit_un_nom_manquant_sans_refuser(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    machine.vendor['gcode_move.py'].write_bytes(b'nothing here\n')
    result = machine.run('survey')
    assert result['status'] == 'SURVEY_OK'
    assert 'gcode_move.py:def reset_last_position' in result['features']['missing']


def test_le_releve_d_une_machine_occupee_rend_quand_meme_les_fichiers(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    machine.status['print_stats'] = {'state': 'printing'}
    result = machine.run('survey')
    assert result['status'] == 'BUSY' and result['problem'] == 'job_busy'
    assert result['drift'] == [] and result['target_drift'] == []
    assert 'rest' not in result and 'head_seed' not in result
    untouched(machine)


def test_le_releve_d_un_klipper_arrete_rend_quand_meme_les_fichiers(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    machine.running = False
    result = machine.run('survey')
    assert result['status'] == 'BUSY' and result['problem'] == 'klippy_socket_closed'
    assert sorted(result['targets']) == sorted(machine.destination.values())


def test_le_releve_lit_aussi_une_machine_deja_posee(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    result = machine.run('survey')
    assert result['status'] == 'SURVEY_OK' and result['backup'] is True
    assert result['target_drift'] == [machine.destination[name] for name in NAMES]
    assert result['rest']['start_revision'] == result['rest']['gate_revision'] == 'resilience-v1'
    assert len(result['bytecode']) == 2


@pytest.mark.parametrize('mode', ['preflight', 'install', 'validate', 'rollback'])
def test_sans_releve_seul_le_releve_est_permis(tmp_path, monkeypatch, mode):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    with pytest.raises(AssertionError, match='survey_not_recorded'):
        machine.run(mode)
    untouched(machine)


# --- preflight ----------------------------------------------------------------


def test_le_preflight_ne_touche_a_rien(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.engage('T2D')
    result = machine.run('preflight')
    assert result['status'] == 'PREFLIGHT_OK'
    assert result['protected'] == len(SIBLINGS + PAGE_SIBLINGS)
    assert all(result['cfs_features'].values()) and result['head_seed'] == 'T2D'
    untouched(machine)
    assert not machine.head_file.exists()


@pytest.mark.parametrize('name,needle', [
    ('virtual_sdcard.py', 'must_pause_work'),
    ('pause_resume.py', 'reportInformation'),
    ('pause_resume.py', 'inside_error'),
    ('gcode_move.py', 'def reset_last_position'),
])
def test_un_nom_constructeur_absent_ferme_la_pose(tmp_path, monkeypatch, name, needle):
    machine = Machine(tmp_path, monkeypatch)
    path = machine.vendor[name]
    path.write_bytes(path.read_bytes().replace(needle.encode(), b'gone'))
    with pytest.raises(AssertionError, match='vendor_feature_missing'):
        machine.run('install')
    untouched(machine)


def test_un_nom_absent_du_cfs_compile_est_seulement_rapporte(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.cfs.write_bytes(b'\x00inside_error\x00')
    result = machine.run('preflight')
    assert result['cfs_features'] == {'inside_error': True, 'record_tn_move_z': False,
                                      'last_err': False, 'move_z': False}


@pytest.mark.parametrize('name', MODULES)
def test_un_module_qui_ne_compile_pas_ferme_la_pose(tmp_path, monkeypatch, name):
    machine = Machine(tmp_path, monkeypatch)
    machine.payloads[name] = b'def broken(:\n'
    machine.manifest['targets'][NAMES.index(name)]['sha256'] = sha(machine.payloads[name])
    with pytest.raises(SyntaxError):
        machine.run('install')
    untouched(machine)


@pytest.mark.parametrize('data', [b'', b'  \n', b'\xff\xfe page'])
def test_un_fichier_de_page_vide_ou_illisible_ferme_la_pose(tmp_path, monkeypatch, data):
    machine = Machine(tmp_path, monkeypatch)
    machine.payloads['bobines.js'] = data
    machine.manifest['targets'][3]['sha256'] = sha(data)
    with pytest.raises((AssertionError, UnicodeDecodeError)):
        machine.run('install')
    untouched(machine)


# --- install ------------------------------------------------------------------


def test_la_pose_remplace_les_quatre_fichiers_redemarre_et_prouve_les_revisions(
        tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.chmod(machine.files['kctrl_start.py'], 0o640)
    machine.chmod(machine.files['bobines.js'], 0o600)
    for name in MODULES:
        (machine.cache / (Path(name).stem + '.cpython-38.pyc')).write_bytes(OLD[name])
    (machine.cache / 'kctrl_sensor_guard.cpython-38.pyc').write_bytes(b'other module')
    result = machine.run('install')
    assert result['status'] == 'INSTALLED_IDLE_OK'
    assert result['revision'] == result['gate_revision'] == 'resilience-v1'
    assert result['recovery_timeout'] == 180 and result['head_seed'] is None
    rest = result['rest']
    assert rest['start_phase'] == 'idle' and rest['start_recovery'] is None
    assert rest['start_head'] is None and rest['head_record'] is None
    assert result['log']['lines'][-1].endswith('kctrl_start: ready')
    assert result['log']['tracebacks'] == 0
    assert machine.actions == ['stop', 'start']
    assert machine.content() == NEW
    assert machine.writes == [(name, NEW[name]) for name in NAMES]
    # A module keeps the mode it had; a page file is always readable by nginx.
    assert machine.mode(machine.files['kctrl_start.py']) == 0o640
    assert machine.mode(machine.files['kctrl_print_gate.py']) == 0o644
    assert all(machine.mode(machine.files[name]) == 0o644 for name in PAGE_FILES)
    backup = machine.m.BACKUP
    for name in NAMES:
        assert (backup / (name + '.before')).read_bytes() == OLD[name]
    modes = json.loads((backup / 'modes.json').read_text())
    assert modes[machine.destination['kctrl_start.py']] == oct(0o640)
    assert modes[machine.destination['bobines.js']] == oct(0o600)
    assert json.loads((backup / 'manifest.json').read_text()) == machine.manifest
    assert json.loads((backup / 'receipt.json').read_text())['status'] == 'INSTALLED_IDLE_OK'
    # Only the bytecode of the two modules went; another module's is not touched.
    assert {path.name: path.read_bytes() for path in machine.cache.iterdir()} == {
        'kctrl_sensor_guard.cpython-38.pyc': b'other module',
        'kctrl_start.cpython-38.pyc': NEW['kctrl_start.py'],
        'kctrl_print_gate.cpython-38.pyc': NEW['kctrl_print_gate.py']}
    for name in SIBLINGS + PAGE_SIBLINGS:
        assert machine.sibling(name).read_bytes() == ('# %s\n' % name).encode()
    assert not machine.head_file.exists()
    validated = machine.run('validate')
    assert validated['status'] == 'VALIDATED_IDLE_OK'
    assert validated['revision'] == validated['gate_revision'] == 'resilience-v1'
    assert validated['recovery'] is None and validated['recovery_timeout'] == 180
    assert machine.actions == ['stop', 'start']


def test_le_bytecode_des_deux_modules_part_avant_le_demarrage(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    for name in MODULES:
        (machine.cache / (Path(name).stem + '.cpython-38.pyc')).write_bytes(OLD[name])
    seen = []
    service = machine.service

    def watching(action):
        if action == 'start':
            seen.append(sorted(path.name for path in machine.cache.iterdir()))
        service(action)
    monkeypatch.setattr(machine.m, 'service', watching)
    assert machine.run('install')['status'] == 'INSTALLED_IDLE_OK'
    assert seen == [[]]
    # The same on the way back: Klipper never starts on the other revision's bytecode.
    assert len(list(machine.cache.iterdir())) == 2
    assert machine.run('rollback')['status'] == 'ROLLED_BACK'
    assert seen == [[], []]


# --- head record carried over the restart ---------------------------------------


def test_la_pose_porte_la_case_en_tete_par_dessus_son_redemarrage(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.engage('T1B')
    result = machine.run('install')
    assert result['status'] == 'INSTALLED_IDLE_OK' and result['head_seed'] == 'T1B'
    # Written before the start, read by the real reader of the new module.
    assert machine.writes[-1][0] == 'kctrl_head.json'
    stored = json.loads(machine.head_file.read_text())
    assert stored == {'schema': 1, 'slot': 'T1B', 'source': 'install', 'saved': stored['saved']}
    assert machine.record() == {'slot': 'T1B', 'source': 'install', 'saved': stored['saved']}
    assert machine.mode(machine.head_file) == 0o644
    assert result['rest']['start_head'] == 'T1B' and result['rest']['head_record'] == 'T1B'
    # The restart erased the route: without the record nothing would name the slot.
    assert result['rest']['units'] == ['None', 'None']
    assert machine.run('validate')['start_head'] == 'T1B'


@pytest.mark.parametrize('change', [
    lambda machine: None,
    lambda machine: machine.status[HEAD].update(filament_detected=False),
    lambda machine: machine.status[UPSTREAM].update(filament_detected=False),
    lambda machine: machine.status[HEAD].update(filament_detected=None),
    lambda machine: machine.engage('T2A'),
    lambda machine: machine.status['box']['T1'].update(filament='E'),
    lambda machine: machine.status['box']['T1'].pop('filament'),
    lambda machine: machine.status['box'].update(T3={'state': 'connect', 'filament': 'None'}),
], ids=['aucune_route', 'tete_vide', 'amont_vide', 'tete_illisible', 'deux_routes',
        'case_inconnue', 'case_absente', 'troisieme_cfs'])
def test_rien_de_prouve_rien_d_ecrit_et_un_ancien_enregistrement_part(
        tmp_path, monkeypatch, change):
    machine = Machine(tmp_path, monkeypatch)
    if change.__code__.co_consts != (None,):
        machine.engage('T1B')
    change(machine)
    # Left by an earlier installation, never kept by the installed start.
    machine.head_file.write_text('{"schema": 1, "slot": "T2C", "source": "route"}')
    result = machine.run('install')
    assert result['status'] == 'INSTALLED_IDLE_OK' and result['head_seed'] is None
    assert not machine.head_file.exists() and result['rest']['start_head'] is None
    assert [name for name, data in machine.writes] == NAMES


def test_un_ancien_enregistrement_est_remplace_par_la_case_prouvee(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.engage('T2D')
    machine.head_file.write_text('{"schema": 1, "slot": "T1A", "source": "route"}')
    result = machine.run('install')
    assert result['head_seed'] == 'T2D' and machine.record()['slot'] == 'T2D'
    assert machine.record()['source'] == 'install'


def test_la_case_portee_est_celle_lue_juste_avant_l_arret(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.engage('T1B')
    # Between the preflight and the stop the screen unloaded: nothing proven.
    machine.at_call[3] = lambda: machine.status['box']['T1'].update(filament='None')
    result = machine.run('install')
    assert result['status'] == 'INSTALLED_IDLE_OK' and result['head_seed'] is None
    assert not machine.head_file.exists()


def real_route():
    spec = importlib.util.spec_from_file_location('kctrl_end_v5', END / 'kctrl_end.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


UNIT = {'state': 'connect', 'filament': 'None'}
ROUTES = {
    'aucune': {},
    'T1B': {'T1': dict(UNIT, filament='B')},
    'T2D': {'T2': dict(UNIT, filament='D')},
    'deux': {'T1': dict(UNIT, filament='A'), 'T2': dict(UNIT, filament='C')},
    'case_inconnue': {'T1': dict(UNIT, filament='E')},
    'case_absente': {'T1': {'state': 'connect'}},
    'inconnue_et_route': {'T1': dict(UNIT, filament='E'), 'T2': dict(UNIT, filament='C')},
    'absente_et_route': {'T1': {'state': 'connect'}, 'T2': dict(UNIT, filament='C')},
    'route_et_deconnectee': {'T1': dict(UNIT, filament='B'),
                             'T2': dict(UNIT, state='disconnect')},
    'unite_absente': {'T1': None},
    'unite_deconnectee': {'T2': dict(UNIT, state='disconnect')},
    'troisieme_connectee': {'T1': dict(UNIT, filament='B'), 'T3': dict(UNIT)},
    'troisieme_none': {'T1': dict(UNIT, filament='B'), 'T3': {'state': 'None'}},
    'troisieme_absente': {'T2': dict(UNIT, filament='A'), 'T3': None, 'T4': None},
    'troisieme_vide': {'T2': dict(UNIT, filament='A'), 'T3': {}},
    'cfs_coupe': {'enable': 0, 'T1': dict(UNIT, filament='B')},
    'cfs_deconnecte': {'state': 'disconnect', 'T1': dict(UNIT, filament='B')},
}


@pytest.mark.parametrize('name', sorted(ROUTES))
def test_la_route_de_l_installeur_est_celle_que_lit_le_module(name):
    # The start reads its route with kctrl_end.live_route: wherever that one
    # names a slot the installer names the same, and nothing where it refuses.
    m, end = load(), real_route()
    box = dict({'enable': 1, 'state': 'connect', 'T1': dict(UNIT), 'T2': dict(UNIT),
                'T3': {'state': 'None', 'filament': 'None'},
                'T4': {'state': 'None', 'filament': 'None'}}, **ROUTES[name])
    try:
        expected = end.live_route(box, 2)
    except end.EndRefused:
        expected = None
    sensors = {HEAD: {'filament_detected': True}, UPSTREAM: {'filament_detected': True}}
    assert m.seed(dict(sensors, box=box)) == expected
    assert expected == {'T1B': 'T1B', 'T2D': 'T2D', 'troisieme_none': 'T1B',
                        'troisieme_absente': 'T2A', 'troisieme_vide': 'T2A'}.get(name)


def test_le_vrai_depart_lit_l_enregistrement_ecrit_par_la_pose(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.engage('T1C')
    machine.run('install')
    # A real start module, pointed at the record the installer left.
    monkeypatch.setattr(rs.base.Machine, 'get', lambda self, key, default=None: (
        str(machine.head_file) if key == 'head_state_file' else default), raising=False)
    (tmp_path / 'real').mkdir()
    owner = rs.machine(tmp_path / 'real', head=True, route=None).owner
    head = owner.get_status()['head']
    assert head['slot'] == 'T1C' and head['source'] == 'install'
    assert owner.get_status()['head_saved'] is True


# --- validate -----------------------------------------------------------------


def test_la_validation_refuse_avant_la_pose(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    with pytest.raises(AssertionError, match='candidate_not_installed'):
        machine.run('validate')


def test_la_validation_accepte_un_depart_repris_ou_sorti_du_bac(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    recovered = {'slot': 'T1B', 'codes': ['bin_guard', 'key837'], 'paused': True,
                 'lift': 30.14, 'bed': 55.0, 'outcome': 'purged'}
    machine.status['kctrl_start'].update(phase='complete', recovery=recovered)
    result = machine.run('validate')
    assert result['status'] == 'VALIDATED_IDLE_OK' and result['recovery'] == recovered
    machine.status['kctrl_start'].update(phase='failed', failure='stock_load_failed',
                                         rest='out_of_bin')
    assert machine.run('validate')['start_phase'] == 'failed'


@pytest.mark.parametrize('change,error', [
    (lambda machine: machine.status.update(kctrl_start=before_status()),
     'start_revision_changed'),
    (lambda machine: machine.status.update(kctrl_print_gate=dict(OLD_GATE)),
     'gate_revision_changed'),
    (lambda machine: machine.status['kctrl_print_gate'].update(wrapped=0), 'gate_not_wrapped'),
    (lambda machine: machine.status['kctrl_start'].update(head_saved=False),
     'start_head_not_saved'),
    (lambda machine: machine.chmod(machine.files['logic.js'], 0o600), 'page_mode_wrong'),
    (lambda machine: machine.files['bobines.js'].write_bytes(OLD['bobines.js']),
     'candidate_not_installed'),
    (lambda machine: (machine.m.BACKUP / 'logic.js.before').write_bytes(b'damaged'),
     'backup_corrupt'),
], ids=['ancien_depart', 'ancienne_porte', 'porte_inactive', 'enregistrement_non_ecrit',
        'page_illisible', 'page_ancienne', 'sauvegarde'])
def test_la_validation_refuse_ce_qui_n_est_pas_la_pose_complete(
        tmp_path, monkeypatch, change, error):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    change(machine)
    with pytest.raises(AssertionError, match=error):
        machine.run('validate')
    assert machine.actions == ['stop', 'start']


def test_les_identifiants_des_cfs_ne_sortent_jamais_de_la_machine(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.engage('T1B')
    results = [machine.run(mode) for mode in ('survey', 'preflight', 'install', 'validate')]
    kept = [path.read_text() for path in machine.m.BACKUP.iterdir()
            if path.suffix == '.json']
    results.append(machine.run('rollback'))
    assert len(kept) == 3
    assert 'SERIAL' not in json.dumps(results) + ''.join(kept)
    assert 'sn' not in json.dumps(results) and 'uuid' not in json.dumps(results)


# --- rest, before any effect ------------------------------------------------------


@pytest.mark.parametrize('command', ['', 'T0', 'T15', 'T1A', 'T1B', 'T4D'])
def test_la_memoire_du_dernier_outil_n_empeche_pas_la_pose(tmp_path, monkeypatch, command):
    machine = Machine(tmp_path, monkeypatch)
    machine.status['box']['t_command'] = command
    result = machine.run('install')
    assert result['status'] == 'INSTALLED_IDLE_OK'


@pytest.mark.parametrize('command', ['T16', 'T5A', 'T1E', 'G28', None, 1])
def test_une_valeur_inconnue_du_dernier_outil_ferme_la_pose(tmp_path, monkeypatch, command):
    machine = Machine(tmp_path, monkeypatch)
    machine.status['box']['t_command'] = command
    with pytest.raises(AssertionError, match='cfs_command_unknown'):
        machine.run('install')
    untouched(machine)


@pytest.mark.parametrize('changes,error', [
    ({'print_stats': {'state': 'printing'}}, 'job_busy'),
    ({'kctrl_print_gate': {'pending': 1}}, 'start_waiting_for_spools'),
    ({'box': {'t_command': 'T2'}}, 'cfs_command_changed'),
    ({'extruder': {'target': 150.0}}, 'heater_target_set'),
])
def test_ce_qui_arrive_juste_avant_l_arret_annule_la_pose_sans_rien_changer(
        tmp_path, monkeypatch, changes, error):
    machine = Machine(tmp_path, monkeypatch)
    machine.engage('T1B')

    def launched():
        for key, update in changes.items():
            machine.status[key].update(update)
    # The preflight reads twice; the third read is the one right before the stop.
    machine.at_call[3] = launched
    result = machine.run('install')
    assert result == {'status': 'NOT_INSTALLED_NOTHING_CHANGED', 'error': error}
    untouched(machine)
    assert not machine.head_file.exists() and machine.archives() == []


@pytest.mark.parametrize('changes,error', [
    ({'webhooks': {'state': 'shutdown'}}, 'klipper_not_ready'),
    ({'print_stats': {'state': 'printing'}}, 'job_busy'),
    ({'print_stats': {'state': 'paused'}}, 'job_busy'),
    ({'virtual_sdcard': {'is_active': True}}, 'sd_active'),
    ({'pause_resume': {'is_paused': True}}, 'paused'),
    ({'idle_timeout': {'state': 'Printing'}}, 'idle_timeout_printing'),
    ({'extruder': {'target': 150.0}}, 'heater_target_set'),
    ({'heater_bed': {'target': 55.0}}, 'heater_target_set'),
    ({'motion_report': {'live_velocity': 12.0}}, 'motion_active'),
    ({'motion_report': {'live_extruder_velocity': 1.5}}, 'motion_active'),
    ({'motion_report': {'live_velocity': None}}, 'motion_active'),
    ({'toolhead': {'print_time': None}}, 'motion_clock_unknown'),
    ({'toolhead': {'print_time': 93740.0}}, 'motion_queued'),
    ({'box': {'enable': 0}}, 'cfs_not_ready'),
    ({'box': {'state': 'disconnect'}}, 'cfs_not_ready'),
    ({'box': {'T2': {'state': 'disconnect', 'filament': 'None'}}}, 'cfs_unit_not_connected'),
    ({'box': {'auto_refill': None}}, 'auto_refill_unknown'),
    ({'box': {'auto_refill': True}}, 'auto_refill_unknown'),
    ({'kctrl_end': {'pending': True}}, 'end_busy'),
    ({'kctrl_end': {'enabled': False}}, 'end_busy'),
    ({'kctrl_end': {'phase': 'cutting'}}, 'end_active'),
    ({'kctrl_end': {'phase': 'rewinding'}}, 'end_active'),
    ({'kctrl_end': {'wrapped': ['END_PRINT']}}, 'end_wrappers_changed'),
    ({'kctrl_end': {'revision': 'end-no-stock-flush-v4'}}, 'end_revision_changed'),
    ({'kctrl_end': {'auto_refill_restore_pending': True}}, 'end_refill_pending'),
    ({'kctrl_start': {'enabled': False}}, 'start_not_installed'),
    ({'kctrl_start': {'installed': False}}, 'start_not_installed'),
    ({'kctrl_start': {'phase': 'planned'}}, 'start_busy'),
    ({'kctrl_start': {'phase': 'material'}}, 'start_busy'),
    ({'kctrl_start': {'revision': 'retained-start-v1'}}, 'start_revision_changed'),
    ({'kctrl_start': {'revision': 'resilience-v1'}}, 'start_revision_changed'),
    ({'kctrl_tool_change': {'wrapped': TOOLS[:4]}}, 'tool_wrappers_changed'),
    ({'kctrl_tool_change': {'missing': ['T7']}}, 'tool_wrappers_changed'),
    ({'kctrl_tool_change': {'reloads': []}}, 'reloads_not_wrapped'),
    ({'kctrl_print_gate': {'pending': 1}}, 'start_waiting_for_spools'),
    ({'kctrl_print_gate': {'pending': True}}, 'start_waiting_for_spools'),
    ({'kctrl_print_gate': {'wrapped': 0}}, 'gate_not_wrapped'),
    ({'kctrl_print_gate': {'revision': 'resilience-v1'}}, 'gate_revision_changed'),
    ({'kctrl_purge_guard': {'installed': False}}, 'bin_guard_not_installed'),
    ({'kctrl_purge_guard': {'revision': 'purge-guard-v1'}}, 'bin_guard_not_installed'),
    ({'kctrl_purge_guard': {'bin_latched': True}}, 'bin_guard_not_at_rest'),
    ({'kctrl_purge_guard': {'minimum_z': 10.0}}, 'bin_guard_not_at_rest'),
    ({'kctrl_purge_guard': {'cold_installed': False}}, 'cold_guard_not_installed'),
    ({'kctrl_purge_guard': {'cold_revision': None}}, 'cold_guard_not_installed'),
    ({'kctrl_sensor_guard': {'installed': False}}, 'sensor_guard_not_installed'),
    ({'kctrl_sensor_guard': {'revision': 'cfs-sensor-guard-v1'}},
     'sensor_guard_revision_changed'),
    ({'kctrl_sensor_guard': {'hooked': False}}, 'sensor_guard_not_hooked'),
    ({'kctrl_sensor_guard': {'failure': 'hook_lost'}}, 'sensor_guard_failed'),
])
def test_la_pose_refuse_une_machine_qui_n_est_pas_au_repos(tmp_path, monkeypatch, changes, error):
    machine = Machine(tmp_path, monkeypatch)
    for key, update in changes.items():
        machine.status[key].update(update)
    for mode in ('preflight', 'install'):
        with pytest.raises(AssertionError, match=error):
            machine.run(mode)
    untouched(machine)


@pytest.mark.parametrize('name,error', [('kctrl_start', 'start_not_installed'),
                                        ('kctrl_print_gate', 'gate_not_wrapped')])
def test_sans_depart_ou_sans_porte_charges_la_pose_refuse(tmp_path, monkeypatch, name, error):
    # Klipper answers None to every key of an object it does not have.
    machine = Machine(tmp_path, monkeypatch)
    del machine.status[name]
    with pytest.raises(AssertionError, match=error):
        machine.run('install')
    untouched(machine)


def test_un_depart_et_une_fin_en_echec_au_repos_n_empechent_pas_la_pose(tmp_path, monkeypatch):
    # The very state this package is made for: both failed, nothing running.
    machine = Machine(tmp_path, monkeypatch)
    machine.status['kctrl_start'].update(phase='failed', failure='stock_load_failed')
    machine.status['kctrl_end'].update(phase='failed', failure='cut_not_confirmed')
    machine.status['print_stats'] = {'state': 'error'}
    assert machine.run('install')['status'] == 'INSTALLED_IDLE_OK'


# --- failed installation: the four files come back ---------------------------------


def restored(machine, result, error):
    assert result['status'] == 'INSTALL_FAILED_ROLLED_BACK' and error in result['error']
    machine.at_before()
    assert machine.running and machine.actions[-1] == 'start'
    assert machine.status['kctrl_start']['revision'] == 'start-load-recovery-v1'
    assert 'revision' not in machine.status['kctrl_print_gate']
    assert not machine.head_file.exists()
    # The backup is kept, moved aside: the next installation finds the place free.
    assert not machine.m.BACKUP.exists()
    assert machine.archives() == [result['backup']]
    assert result['backup'].startswith('resilience-v1.install-failed-')
    receipt = json.loads((machine.root / 'backups' / result['backup'] / 'receipt.json')
                         .read_text())
    assert receipt['status'] == 'INSTALL_FAILED_ROLLED_BACK'
    assert {path.name: path.read_bytes() for path in machine.cache.iterdir()} == {
        'kctrl_start.cpython-38.pyc': OLD['kctrl_start.py'],
        'kctrl_print_gate.cpython-38.pyc': OLD['kctrl_print_gate.py']}


@pytest.mark.parametrize('change,error', [
    (lambda start, gate: start.update(phase='failed', failure='x'), 'start_not_fresh'),
    (lambda start, gate: start.update(recovery={'slot': 'T1B'}), 'start_recovery_not_fresh'),
    (lambda start, gate: start.update(recovery_timeout=60.0), 'start_recovery_timeout_changed'),
    (lambda start, gate: start.update(rest='skipped'), 'start_rest_not_fresh'),
    (lambda start, gate: start.update(head_saved=False), 'start_head_not_saved'),
    (lambda start, gate: start.update(revision='start-load-recovery-v1'),
     'start_revision_changed'),
    (lambda start, gate: start.update(installed=False), 'start_not_installed'),
    # A field the module does not publish reads None: only this one, True
    # in the new start alone, tells the two revisions apart beyond the name.
    (lambda start, gate: start.pop('head_saved'), 'start_head_not_saved'),
    (lambda start, gate: gate.pop('revision'), 'gate_revision_changed'),
    (lambda start, gate: gate.update(wrapped=0), 'gate_not_wrapped'),
    (lambda start, gate: start.update(head=None), 'start_head_not_read'),
    (lambda start, gate: start.update(head={'slot': 'T2A', 'source': 'route'}),
     'start_head_not_read'),
], ids=['phase', 'reprise', 'delai', 'sortie', 'enregistrement', 'revision', 'non_installe',
        'sans_champ_enregistrement', 'porte_ancienne', 'porte_inactive', 'tete_non_lue', 'autre_case'])
def test_un_demarrage_qui_n_est_pas_celui_prevu_remet_les_quatre_fichiers(
        tmp_path, monkeypatch, change, error):
    def once(start, gate):
        if start['revision'] == 'resilience-v1':
            change(start, gate)
    machine = Machine(tmp_path, monkeypatch, loaded=once)
    machine.engage('T1B')
    machine.chmod(machine.files['bobines.js'], 0o644)
    result = machine.run('install')
    restored(machine, result, error)
    assert machine.actions == ['stop', 'start', 'stop', 'start']
    # Nothing in the way of a second try.
    machine.loaded = None
    machine.engage('T1B')
    again = machine.run('install')
    assert again['status'] == 'INSTALLED_IDLE_OK' and again['head_seed'] == 'T1B'
    assert len(machine.archives()) == 2


def test_une_tete_vue_sans_enregistrement_laisse_n_importe_quelle_case_connue(
        tmp_path, monkeypatch):
    # No record was left; the watch of the new start may prove a route since.
    machine = Machine(tmp_path, monkeypatch, loaded=lambda start, gate: start.update(
        head={'slot': 'T1D', 'source': 'route', 'saved': 1.0}))
    assert machine.run('install')['status'] == 'INSTALLED_IDLE_OK'


def test_une_tete_illisible_sans_enregistrement_revient_a_l_ancien(tmp_path, monkeypatch):
    def unknown(start, gate):
        if start['revision'] == 'resilience-v1':
            start.update(head={'slot': 'T9Z'})
    machine = Machine(tmp_path, monkeypatch, loaded=unknown)
    restored(machine, machine.run('install'), 'start_head_unknown')


def test_un_voisin_qui_change_pendant_la_pose_la_defait_et_se_voit(tmp_path, monkeypatch):
    def changed(start, gate):
        if start['revision'] == 'resilience-v1':
            machine.sibling('kctrl_end.py').write_bytes(b'changed meanwhile\n')
    machine = Machine(tmp_path, monkeypatch, loaded=changed)
    machine.engage('T1B')
    result = machine.run('install')
    restored(machine, result, 'protected_file_drift')
    # Never written here, so only named; the backup does not stay in the way.
    assert result['neighbour'] == 'protected_file_drift: ' + machine.sibling(
        'kctrl_end.py').as_posix()
    assert machine.actions == ['stop', 'start', 'stop', 'start']


def test_un_voisin_qui_change_pendant_le_retour_arriere_se_voit(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')

    def changed(start, gate):
        machine.sibling('styles.css').write_bytes(b'changed meanwhile\n')
    machine.loaded = changed
    result = machine.run('rollback')
    assert result['status'] == 'ROLLED_BACK' and machine.content() == OLD
    assert result['neighbour'].startswith('protected_file_drift: ')
    assert result['backup'].startswith('resilience-v1.rolled-back-')
    assert not machine.m.BACKUP.exists()


def test_un_depart_qui_cesse_d_etre_neuf_pendant_l_attente_defait_la_pose(
        tmp_path, monkeypatch):
    # Ready and fresh at first, then a start launched during the settle time.
    machine = Machine(tmp_path, monkeypatch)
    calls = []

    def launched():
        machine.status['kctrl_start'].update(phase='failed', failure='stock_load_failed',
                                             rest='out_of_bin')
    state = machine.state

    def counting():
        calls.append(machine.running)
        # The first answer after the start is the ready check; the next one
        # comes after the settle time.
        if machine.actions == ['stop', 'start'] and calls.count(True) == 5:
            launched()
        return state()
    monkeypatch.setattr(machine.m, 'state', counting)
    result = machine.run('install')
    restored(machine, result, 'start_not_fresh')
    assert result['error'] == 'start_not_fresh'


@pytest.mark.parametrize('name', MODULES)
def test_klipper_qui_refuse_de_demarrer_revient_aux_anciens(tmp_path, monkeypatch, name):
    machine = Machine(tmp_path, monkeypatch)
    machine.payloads[name] = b'# compiles, but Klipper does not come up with it\n'
    machine.manifest['targets'][NAMES.index(name)]['sha256'] = sha(machine.payloads[name])
    result = machine.run('install')
    restored(machine, result, 'ready_not_confirmed: klipper_not_ready')
    assert machine.actions == ['stop', 'start', 'stop', 'start']


@pytest.mark.parametrize('failing', [1, 2, 3, 4, 5])
def test_une_ecriture_qui_echoue_en_route_remet_tout(tmp_path, monkeypatch, failing):
    # 1 to 4: one of the four files; 5: the head record.
    machine = Machine(tmp_path, monkeypatch)
    machine.engage('T1B')
    machine.fail_write = failing
    result = machine.run('install')
    restored(machine, result, 'No space left on device')
    assert machine.actions == ['stop', 'stop', 'start']
    written = [name for name, data in machine.writes]
    assert written == NAMES[:failing - 1] + NAMES[:failing - 1]


@pytest.mark.parametrize('name', NAMES)
def test_un_fichier_mal_ecrit_se_voit_avant_de_demarrer_klipper(tmp_path, monkeypatch, name):
    machine = Machine(tmp_path, monkeypatch)
    machine.corrupt = name
    result = machine.run('install')
    restored(machine, result, 'candidate_hash_mismatch')
    # Klipper never started on it.
    assert machine.actions == ['stop', 'stop', 'start']


def test_une_page_ecrite_illisible_defait_la_pose(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.wrong_mode = 'logic.js'
    result = machine.run('install')
    restored(machine, result, 'page_mode_wrong: logic.js')
    assert machine.actions == ['stop', 'start', 'stop', 'start']


def test_un_voisin_qui_change_juste_avant_l_arret_n_ecrit_rien(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.at_stop = lambda: machine.sibling('kctrl_bin_motion.py').write_bytes(b'changed\n')
    result = machine.run('install')
    restored(machine, result, 'protected_file_drift')
    assert machine.writes == [] and 'kctrl_bin_motion.py' in result['neighbour']
    assert machine.actions == ['stop', 'stop', 'start']


def test_un_retour_arriere_mal_ecrit_le_dit_et_relance_klipper(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.corrupt = 'kctrl_print_gate.py'
    with pytest.raises(AssertionError, match='rollback_hash_mismatch'):
        machine.run('rollback')
    # Not hidden, Klipper not left stopped, the backup still there to try again.
    assert machine.actions == ['stop', 'start', 'stop', 'start'] and machine.running
    assert (machine.m.BACKUP / 'kctrl_print_gate.py.before').read_bytes() == \
        OLD['kctrl_print_gate.py']


def test_une_sauvegarde_abimee_pendant_la_pose_relance_quand_meme_klipper(
        tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.fail_write = 3
    machine.failing = lambda: (machine.m.BACKUP / 'kctrl_start.py.before').write_bytes(b'bad')
    with pytest.raises(AssertionError, match='backup_corrupt'):
        machine.run('install')
    # Nothing can be put back, and it says so; Klipper is not left stopped
    # and the backup stays where it is.
    assert machine.actions == ['stop', 'stop', 'start'] and machine.running
    assert machine.m.BACKUP.exists()


# --- refused before anything --------------------------------------------------------


@pytest.mark.parametrize('mode', ['preflight', 'install', 'validate', 'rollback'])
@pytest.mark.parametrize('name', ['kctrl_end.py', 'styles.css'])
def test_un_fichier_protege_modifie_bloque_tout(tmp_path, monkeypatch, mode, name):
    machine = Machine(tmp_path, monkeypatch)
    machine.sibling(name).write_bytes(b'changed elsewhere\n')
    with pytest.raises(RuntimeError, match='protected_file_drift'):
        machine.run(mode)
    untouched(machine)


@pytest.mark.parametrize('name', SIBLINGS + PAGE_SIBLINGS)
def test_chaque_voisin_doit_etre_epingle(tmp_path, monkeypatch, name):
    machine = Machine(tmp_path, monkeypatch)
    del machine.manifest['protected'][machine.sibling(name).as_posix()]
    for mode in ('survey', 'install'):
        with pytest.raises(AssertionError, match='sibling_not_pinned'):
            machine.run(mode)
    untouched(machine)


@pytest.mark.parametrize('name', NAMES)
def test_une_charge_alteree_est_refusee_avant_tout(tmp_path, monkeypatch, name):
    machine = Machine(tmp_path, monkeypatch)
    machine.payloads[name] = NEW[name] + b'# one more line\n'
    for mode in ('survey', 'preflight', 'install', 'validate', 'rollback'):
        with pytest.raises(AssertionError, match='payload_hash_changed'):
            machine.run(mode)
    untouched(machine)


@pytest.mark.parametrize('change,error', [
    (lambda machine: machine.payloads.pop('logic.js'), 'payload_set_changed'),
    (lambda machine: machine.payloads.update({'/etc/passwd': b'x'}), 'payload_set_changed'),
    (lambda machine: machine.manifest.update(name='start-load-recovery-v1'),
     'manifest_mismatch'),
    (lambda machine: machine.manifest['targets'].reverse(), 'manifest_mismatch'),
    (lambda machine: machine.manifest['targets'].pop(), 'manifest_mismatch'),
    (lambda machine: machine.manifest['targets'][2].update(kind='module'),
     'manifest_mismatch'),
    (lambda machine: machine.manifest['targets'][0].update(
        before_sha256=machine.manifest['targets'][0]['sha256']), 'manifest_mismatch'),
    (lambda machine: machine.manifest['targets'][1].update(before_sha256=None),
     'manifest_mismatch'),
    (lambda machine: machine.manifest['targets'][0].update(
        destination=machine.destination['kctrl_start.py'] + '.other'), 'manifest_mismatch'),
    (lambda machine: machine.manifest['protected'].update(
        {machine.destination['kctrl_print_gate.py']: sha(OLD['kctrl_print_gate.py'])}),
     'target_also_protected'),
], ids=['charge_absente', 'charge_en_trop', 'autre_paquet', 'autre_ordre', 'cible_absente',
        'autre_nature', 'avant_egal_apres', 'avant_inconnu', 'autre_chemin', 'cible_epinglee'])
def test_un_manifeste_ou_un_envoi_incoherent_est_refuse_avant_tout(
        tmp_path, monkeypatch, change, error):
    machine = Machine(tmp_path, monkeypatch)
    change(machine)
    for mode in ('survey', 'install'):
        with pytest.raises(AssertionError, match=error):
            machine.run(mode)
    untouched(machine)


def test_un_mode_inconnu_est_refuse(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    with pytest.raises(AssertionError, match='invalid_mode'):
        machine.run('uninstall')
    untouched(machine)


@pytest.mark.parametrize('name', NAMES)
def test_chaque_cible_doit_etre_celle_du_releve(tmp_path, monkeypatch, name):
    machine = Machine(tmp_path, monkeypatch)
    machine.files[name].write_bytes(b'another revision\n')
    for mode in ('preflight', 'install'):
        with pytest.raises(AssertionError, match='target_not_as_surveyed: ' + name):
            machine.run(mode)
    assert machine.actions == [] and machine.writes == [] and not machine.m.BACKUP.exists()


@pytest.mark.parametrize('name', NAMES + ['kctrl_head.json'])
def test_un_fichier_d_attente_oublie_ferme_la_pose(tmp_path, monkeypatch, name):
    machine = Machine(tmp_path, monkeypatch)
    target = machine.files.get(name, machine.head_file)
    Path(str(target) + machine.m.STAGE_SUFFIX).write_bytes(b'left behind')
    assert machine.run('survey')['stage'] != []
    with pytest.raises(AssertionError, match='stale_stage_file'):
        machine.run('install')
    untouched(machine)


def test_une_sauvegarde_deja_la_ferme_la_pose(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.m.BACKUP.mkdir(parents=True)
    with pytest.raises(AssertionError, match='backup_already_exists'):
        machine.run('install')
    assert machine.actions == [] and machine.writes == []


def test_sans_dossier_d_etat_la_pose_refuse(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.state_directory.rmdir()
    assert machine.run('survey')['state_directory'] is False
    with pytest.raises(AssertionError, match='state_directory_missing'):
        machine.run('install')
    untouched(machine)


def test_une_pose_deja_faite_ne_se_rejoue_pas(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    with pytest.raises(AssertionError, match='target_not_as_surveyed'):
        machine.run('install')
    assert machine.actions == ['stop', 'start'] and machine.content() == NEW


# --- rollback -----------------------------------------------------------------


def test_le_retour_arriere_remet_les_quatre_fichiers_exacts_et_libere_la_place(
        tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.chmod(machine.files['kctrl_start.py'], 0o640)
    machine.chmod(machine.files['logic.js'], 0o600)
    machine.engage('T1B')
    machine.run('install')
    assert machine.record()['slot'] == 'T1B'
    (machine.cache / 'kctrl_sensor_guard.cpython-38.pyc').write_bytes(b'other module')
    result = machine.run('rollback')
    assert result['status'] == 'ROLLED_BACK'
    assert result['rest']['start_revision'] == 'start-load-recovery-v1'
    assert result['rest']['gate_revision'] is None and result['rest']['head_record'] is None
    assert machine.actions == ['stop', 'start', 'stop', 'start']
    assert machine.content() == OLD
    assert machine.mode(machine.files['kctrl_start.py']) == 0o640
    assert machine.mode(machine.files['logic.js']) == 0o600
    assert machine.mode(machine.files['bobines.js']) == 0o644
    assert {path.name: path.read_bytes() for path in machine.cache.iterdir()} == {
        'kctrl_sensor_guard.cpython-38.pyc': b'other module',
        'kctrl_start.cpython-38.pyc': OLD['kctrl_start.py'],
        'kctrl_print_gate.cpython-38.pyc': OLD['kctrl_print_gate.py']}
    # The installed start never kept a record: none is left for a later one.
    assert not machine.head_file.exists()
    assert not machine.m.BACKUP.exists() and machine.archives() == [result['backup']]
    assert result['backup'].startswith('resilience-v1.rolled-back-')
    kept = machine.root / 'backups' / result['backup']
    assert json.loads((kept / 'receipt.json').read_text())['status'] == 'ROLLED_BACK'
    assert (kept / 'bobines.js.before').read_bytes() == OLD['bobines.js']
    # And the package goes on again, without anyone clearing anything.
    machine.engage('T2A')
    again = machine.run('install')
    assert again['status'] == 'INSTALLED_IDLE_OK' and again['head_seed'] == 'T2A'
    assert machine.content() == NEW and machine.run('validate')['start_head'] == 'T2A'


def test_le_retour_arriere_ne_reecrit_que_ce_qui_a_change(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.files['logic.js'].write_bytes(OLD['logic.js'])
    del machine.writes[:]
    assert machine.run('rollback')['status'] == 'ROLLED_BACK'
    assert [name for name, data in machine.writes] == [
        'kctrl_start.py', 'kctrl_print_gate.py', 'bobines.js']
    assert machine.content() == OLD


@pytest.mark.parametrize('change,error', [
    (lambda machine: machine.status.update(print_stats={'state': 'printing'}), 'job_busy'),
    # Rule of 24 September: no restart during a print, even paused.
    (lambda machine: (machine.status.update(print_stats={'state': 'paused'}),
                      machine.status.update(pause_resume={'is_paused': True})), 'job_busy'),
    (lambda machine: machine.status['kctrl_start'].update(phase='material'), 'start_busy'),
    (lambda machine: machine.status['kctrl_print_gate'].update(pending=1),
     'start_waiting_for_spools'),
    (lambda machine: machine.status['kctrl_end'].update(phase='heating'), 'end_active'),
], ids=['impression', 'pause', 'depart', 'choix_de_bobines', 'fin'])
def test_le_retour_arriere_refuse_une_machine_occupee(tmp_path, monkeypatch, change, error):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    change(machine)
    with pytest.raises(AssertionError, match=error):
        machine.run('rollback')
    assert machine.actions == ['stop', 'start'] and machine.content() == NEW
    assert machine.m.BACKUP.exists()


@pytest.mark.parametrize('breakage,error', [
    (lambda machine: (machine.m.BACKUP / 'kctrl_print_gate.py.before').write_bytes(b'damaged'),
     'backup_corrupt'),
    (lambda machine: (machine.m.BACKUP / 'bobines.js.before').unlink(), 'backup_corrupt'),
    (lambda machine: (machine.m.BACKUP / 'modes.json').write_text('{}'), 'backup_corrupt'),
    (lambda machine: machine.files['logic.js'].write_bytes(b'// someone else\n'),
     'rollback_foreign_file'),
], ids=['sauvegarde', 'sauvegarde_absente', 'modes', 'fichier_etranger'])
def test_un_retour_arriere_impossible_se_voit_avant_d_arreter_klipper(
        tmp_path, monkeypatch, breakage, error):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    breakage(machine)
    with pytest.raises(AssertionError, match=error):
        machine.run('rollback')
    assert machine.actions == ['stop', 'start']
    assert machine.running


def test_sans_pose_le_retour_arriere_refuse(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    with pytest.raises(AssertionError, match='backup_corrupt'):
        machine.run('rollback')
    untouched(machine)


# --- the installer against the real modules and files --------------------------------


def test_le_journal_est_lu_depuis_l_arret_par_morceaux_bornes(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.log.write_bytes(b'x' * (3 << 20) + b'\nTraceback before\n')
    offset = machine.log.stat().st_size
    with machine.log.open('ab') as stream:
        stream.write(b'y' * ((1 << 20) - 20) + b' kctrl_start: ready\n')
        stream.write(b'kctrl_print_gate: wrapped\nTraceback (most recent call last):\n')
    result = machine.m.log_lines(offset)
    assert result['tracebacks'] == 1
    assert result['lines'] == [('y' * 240 + ' kctrl_start: ready')[-240:],
                               'kctrl_print_gate: wrapped']


def test_les_champs_lus_sont_ceux_du_vrai_depart(tmp_path):
    m = load()
    start = json.loads(json.dumps(rs.machine(tmp_path).owner.get_status()))
    assert set(m.QUERY['kctrl_start']) <= set(start)
    # Fresh as the installer wants it after the restart.
    m.start_fresh({key: start[key] for key in m.QUERY['kctrl_start']})
    assert start['revision'] == rs.module.REVISION == m.REVISIONS['after'] == m.NAME
    assert "REVISION = '%s'" % m.REVISIONS['before'] in (RECOVERY / 'kctrl_start.py').read_text(
        encoding='utf-8')
    assert (m.HEAD_FILE, m.HEAD_SCHEMA) == (rs.module.HEAD_STATE_FILE, rs.module.HEAD_SCHEMA)
    assert m.SLOTS == list(rs.module.SLOTS)


def test_les_champs_lus_sont_ceux_de_la_vraie_porte(tmp_path, monkeypatch):
    m = load()
    asked = m.QUERY['kctrl_print_gate']
    new = json.loads(json.dumps(rg.machine(tmp_path).get_status()))
    assert set(asked) <= set(new)
    m.gate_running({key: new[key] for key in asked}, m.GATE_REVISIONS['after'])
    assert rg.MOD.REVISION == m.NAME
    # The installed gate publishes no revision: Klipper answers None for it.
    monkeypatch.setattr(rg.base, 'MOD', rg.OLD)
    old = json.loads(json.dumps(rg.machine(tmp_path).get_status()))
    assert 'revision' not in old and not hasattr(rg.OLD, 'REVISION')
    m.gate_running({key: old.get(key) for key in asked}, m.GATE_REVISIONS['before'])
    with pytest.raises(AssertionError, match='gate_revision_changed'):
        m.gate_running({key: old.get(key) for key in asked}, m.GATE_REVISIONS['after'])


def test_le_nouveau_depart_n_appelle_que_les_noms_constructeur_verifies():
    m = load()
    source = (PACKAGE / 'kctrl_start.py').read_bytes()
    for needles in list(m.FEATURES.values()) + [m.CFS_FEATURES]:
        for needle in needles:
            assert needle.replace(b'def ', b'') in source, needle
    recovery = load_other(RECOVERY)
    assert m.FEATURES == recovery.FEATURES and m.CFS_FEATURES == recovery.CFS_FEATURES


def load_other(package):
    spec = importlib.util.spec_from_file_location('earlier_install',
                                                  package / 'remote_install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_l_installeur_tourne_sur_le_python_de_la_machine():
    # BusyBox printer, Python 3.8: nothing newer in the file sent there.
    import ast
    source = (PACKAGE / 'remote_install.py').read_text(encoding='utf-8')
    ast.parse(source, feature_version=(3, 8))
    assert '\r' not in source and source.isascii()


# --- manifest and transport ---------------------------------------------------------


def manifest():
    return json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))


def test_le_manifeste_epingle_les_quatre_candidats_et_l_installateur():
    pins = manifest()
    m = load()
    assert pins['schema'] == 2 and pins['name'] == m.NAME and pins['adr'] == 'ADR-080'
    assert [entry['destination'] for entry in pins['targets']] == list(m.targets())
    for entry in pins['targets']:
        assert sha((ROOT / entry['source']).read_bytes()) == entry['sha256']
        assert entry['kind'] == m.targets()[entry['destination']]
        assert entry.get('mode') == ('0644' if entry['kind'] == 'page' else None)
        assert entry['destination'] not in pins['protected']
    assert sha((PACKAGE / 'remote_install.py').read_bytes()) == pins['installer_sha256']
    assert pins['backup'] == '/usr/data/k1-control-v1/backups/resilience-v1'
    assert pins['head_record'] == '/usr/data/k1-control-v1/state/kctrl_head.json'
    assert (ROOT / pins['document']).exists()
    assert pins['surveyed'] is (pins['surveyed_on'] is not None)
    effects = pins['effects']
    assert effects['klipper_restart_idle_only'] is True
    assert not any(effects[key] for key in ('heating', 'motion', 'filament', 'config_change',
                                            'printer_cfg_change'))
    for sibling in m.siblings():
        assert sibling in pins['protected'], sibling


def test_avant_c_est_ce_que_les_paquets_precedents_ont_laisse():
    pins = manifest()
    before = {Path(entry['destination']).name: entry['before_sha256']
              for entry in pins['targets']}
    recovery = json.loads((RECOVERY / 'manifest.json').read_text(encoding='utf-8'))
    pages = json.loads((PAGES / 'manifest.json').read_text(encoding='utf-8'))
    gate = '/usr/share/klipper/klippy/extras/kctrl_print_gate.py'
    assert before['kctrl_start.py'] == recovery['sha256'] == sha(
        (RECOVERY / 'kctrl_start.py').read_bytes())
    assert before['kctrl_print_gate.py'] == recovery['protected'][gate] == sha(
        (PACKAGES / 'spool-choice-gate-v1' / 'kctrl_print_gate.py').read_bytes())
    installed = {entry['destination']: entry['installed_sha256'] for entry in pages['files']}
    www = '/usr/data/k1-control-v1/current/www/bobines/'
    for name in PAGE_FILES:
        assert before[name] == installed[www + name] == sha(
            (PACKAGES / 'spool-choice-gate-v1' / 'www' / 'bobines' / name).read_bytes())
    # Every other pin of the earlier package, the gate apart; then every page
    # file left in place and what serves the page.
    expected = dict(recovery['protected'])
    del expected[gate]
    for path, value in installed.items():
        if path.startswith(www) and Path(path).name not in PAGE_FILES:
            expected[path] = value
    for path, value in pages['protected'].items():
        if '/www/' in path:
            expected[path] = value
    assert pins['protected'] == expected and len(expected) == 32
    assert '/usr/data/k1-control-v1/current/www/mainsail/index.html' in expected


def test_les_paquets_anterieurs_refusent_tant_que_celui_ci_est_pose():
    # They pin the start or the gate at the hash this package replaces.
    pins = manifest()
    start, gate = pins['targets'][0], pins['targets'][1]
    assert all(entry['sha256'] != entry['before_sha256'] for entry in pins['targets'])
    recovery = json.loads((RECOVERY / 'manifest.json').read_text(encoding='utf-8'))
    assert recovery['sha256'] == start['before_sha256']
    assert recovery['protected'][gate['destination']] == gate['before_sha256']
    for name in ('cfs-sensor-guard-v2', 'cold-push-guard-v1', 'end-no-stock-flush-v5'):
        other = json.loads((PACKAGES / name / 'manifest.json').read_text(encoding='utf-8'))
        assert other['protected'][start['destination']] not in (
            start['sha256'], None), name


def test_l_envoi_porte_les_quatre_candidats_verifies(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location('resilience_deploy', PACKAGE / 'deploy.py')
    deploy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deploy)
    script = deploy.request('survey')
    head, installer = script.split(b'\n', 1)
    assert installer == (PACKAGE / 'remote_install.py').read_bytes()
    scope = {}
    exec(head.decode(), scope)
    body = json.loads(base64.b64decode(scope['REQUEST_B64']))
    assert body['mode'] == 'survey' and body['manifest'] == manifest()
    m = load()
    assert sorted(body['payloads']) == sorted(m.targets())
    # The installer itself accepts what the workstation built.
    entries, payloads = m.checked(body)
    assert [sha(payloads[entry['destination']]) for entry in entries] == [
        entry['sha256'] for entry in entries]
    assert deploy.RAW == ROOT / 'inventory/raw/resilience-v1'
    # A candidate edited after the manifest was built never leaves.
    changed = json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))
    changed['targets'][2]['sha256'] = '0' * 64
    other = tmp_path / 'manifest.json'
    other.write_text(json.dumps(changed), encoding='utf-8')
    monkeypatch.setattr(deploy, 'MANIFEST', other)
    with pytest.raises(SystemExit, match='logic.js differs from manifest.json'):
        deploy.request('install')
    changed = manifest()
    changed['installer_sha256'] = '0' * 64
    other.write_text(json.dumps(changed), encoding='utf-8')
    with pytest.raises(SystemExit, match='remote_install.py differs'):
        deploy.request('install')


def test_le_manifeste_est_celui_que_le_constructeur_ecrit(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('resilience_build',
                                                  PACKAGE / 'build_manifest.py')
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    written = {}
    monkeypatch.setattr(Path, 'write_bytes', lambda self, data: written.update({self.name: data}))
    build.main()
    assert written == {'manifest.json': (PACKAGE / 'manifest.json').read_bytes()}
    assert stat.S_ISREG(os.stat(str(PACKAGE / 'manifest.json')).st_mode)
