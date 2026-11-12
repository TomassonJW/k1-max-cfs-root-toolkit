"""Replace the retained start by its recovering revision, refuse and roll back.

The printer is replaced by a status dictionary, the service by a log of
actions, the files by temporary copies (ADR-079, document 108).
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

import test_start_load_recovery as recovery_test

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages/k1-control-v1/start-load-recovery-v1'
RETAINED = ROOT / 'packages/k1-control-v1/retained-start-v1'
SENSOR = ROOT / 'packages/k1-control-v1/cfs-sensor-guard-v2'
TOOLS = ['T%d' % index for index in range(16)]
SLOTS = ['T%s%s' % (box, slot) for box in '1234' for slot in 'ABCD']
WRAPPED = ['CANCEL_PRINT', 'END_PRINT', 'START_PRINT']
GUARD = {'revision': 'retained-start-v1', 'installed': True, 'bin_latched': False,
         'minimum_z': 30.0, 'denied': 0, 'last_error': '',
         'cold_revision': 'cold-push-guard-v1', 'cold_installed': True, 'cold_refused': 0,
         'cold_last': ''}
SENSOR_STATUS = {'enabled': True, 'installed': True, 'revision': 'cfs-sensor-guard-v2',
                 'hook': 'inside_cold_guard', 'hooked': True, 'failure': '', 'blind': None}
BEFORE = b'# installed retained-start-v1\n'
MODULE = b'# candidate start-load-recovery-v1\n'
SIBLINGS = ['kctrl_start_policy.py', 'kctrl_start_context.py', 'kctrl_purge_guard.py',
            'kctrl_bin_motion.py', 'kctrl_sensor_guard.py']
VENDOR = {
    'virtual_sdcard.py': b'must_pause_work\ndef is_active(self):\nrecord_tn_move_z(0)\nmove_z\n',
    'pause_resume.py': b'reportInformation\npause_command_sent\nsd_paused\ninside_error\n',
    'gcode_move.py': b'def reset_last_position(self):\n',
}


def load():
    spec = importlib.util.spec_from_file_location('start_load_recovery_install',
                                                  PACKAGE / 'remote_install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def before_status(**changes):
    """The retained start as it reads at rest: no recovery fields."""
    value = {'enabled': True, 'installed': True, 'phase': 'complete',
             'revision': 'retained-start-v1', 'failure': ''}
    value.update(changes)
    return value


def after_status(**changes):
    value = {'enabled': True, 'installed': True, 'phase': 'idle',
             'revision': 'start-load-recovery-v1', 'failure': '', 'recovery': None,
             'recovery_timeout': 180.0}
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
                'T2': {'state': 'connect', 'filament': 'None', 'uuid': 'SERIAL-T2'}},
        'filament_switch_sensor filament_sensor_2': {'filament_detected': True},
        'kctrl_end': {'enabled': True, 'phase': 'complete', 'pending': False,
                      'wrapped': list(WRAPPED), 'revision': 'end-no-stock-flush-v5',
                      'auto_refill_restore_pending': False},
        'kctrl_start': before_status(),
        'kctrl_tool_change': {'wrapped': list(TOOLS), 'missing': [], 'reloads': list(SLOTS)},
        'kctrl_print_gate': {'pending': False},
        'kctrl_purge_guard': dict(GUARD),
        'kctrl_sensor_guard': dict(SENSOR_STATUS),
    }
    for key, update in changes.items():
        value[key] = dict(value[key], **update)
    return value


class Machine:
    """Temporary tree, fake Klipper status and service, same paths as the module."""

    def __init__(self, tmp_path, monkeypatch, loaded=None, surveyed=True):
        self.m = m = load()
        extras = tmp_path / 'extras'
        extras.mkdir()
        self.module = extras / 'kctrl_start.py'
        self.module.write_bytes(BEFORE)
        self.module.chmod(0o644)
        self.cache = extras / '__pycache__'
        self.cache.mkdir()
        self.log = tmp_path / 'klippy.log'
        self.log.write_bytes(b'old line\n')
        self.pid = tmp_path / 'klippy.pid'
        self.pid.write_text('2210')
        printer = m.EXTRAS
        features = {name: m.FEATURES[printer + '/' + name] for name in VENDOR}
        # The temporary tree stands for the extras directory: same file names.
        monkeypatch.setattr(m, 'EXTRAS', str(extras))
        protected = {}
        for name in SIBLINGS:
            path = extras / name
            path.write_bytes(('# %s\n' % name).encode())
            protected[m.EXTRAS + '/' + name] = sha(path.read_bytes())
        self.vendor = {}
        for name, data in VENDOR.items():
            path = extras / name
            path.write_bytes(data)
            self.vendor[name] = path
        self.cfs = extras / 'box_wrapper.so'
        self.cfs.write_bytes(b'\x00inside_error\x00record_tn_move_z\x00last_err\x00move_z\x00')
        self.extras = extras
        for name, value in (('MODULE', str(self.module)), ('BYTECODE', str(self.cache)),
                            ('BACKUP', tmp_path / 'backups/start-load-recovery-v1'),
                            ('LOG', self.log), ('PIDFILE', self.pid),
                            ('FEATURES', {str(self.vendor[name]): needles
                                          for name, needles in features.items()}),
                            ('CFS_FILES', [str(extras / 'box.py'), str(self.cfs)])):
            monkeypatch.setattr(m, name, value)
        clock = [0.0]
        monkeypatch.setattr(m, 'time', types.SimpleNamespace(
            monotonic=lambda: clock[0], time=lambda: 1.0e9 + clock[0],
            sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds)))
        monkeypatch.setattr(m, 'compiles', lambda data: compile(data, 'candidate', 'exec'))
        self.actions = []
        self.writes = []
        replace = m.replace

        def recording(path, data, mode):
            self.writes.append((Path(path).name, data))
            replace(path, data, mode)
        monkeypatch.setattr(m, 'replace', recording)
        self.running = True
        self.loaded = loaded
        self.status = status()
        self.hook = None
        monkeypatch.setattr(m, 'state', self.state)
        monkeypatch.setattr(m, 'service', self.service)
        monkeypatch.setattr(m, 'stop', self.stop)
        self.manifest = {
            'name': m.NAME, 'destination': str(self.module), 'sha256': sha(MODULE),
            'before_sha256': sha(BEFORE), 'surveyed': surveyed, 'protected': protected,
        }

    def sibling(self, name):
        return self.extras / name

    def state(self):
        if self.hook:
            self.hook()
        if not self.running:
            raise RuntimeError('klippy_socket_closed')
        return json.loads(json.dumps(self.status))

    def service(self, action):
        self.actions.append(action)
        if action == 'stop':
            self.running = False
            return
        if action != 'start':
            return
        self.running = True
        self.pid.write_text(str(int(self.pid.read_text()) + 1))
        self.status = status(print_stats={'state': 'standby'})
        code = self.module.read_bytes()
        if code == MODULE:
            start = after_status()
            if self.loaded:
                self.loaded(start)
        elif code == BEFORE:
            start = before_status(phase='idle')
        else:
            self.status['webhooks'] = {'state': 'error'}
            return
        (self.cache / 'kctrl_start.cpython-38.pyc').write_bytes(code)
        self.status['kctrl_start'] = start
        with self.log.open('ab') as stream:
            stream.write(b'[INFO] kctrl_start: ready\n')

    def stop(self):
        pid = self.pid.read_text()
        self.service('stop')
        return pid

    def run(self, mode, payload=None):
        return self.m.run({'mode': mode, 'manifest': self.manifest,
                           'payload': base64.b64encode(payload or MODULE).decode()})

    def at_before(self):
        assert self.module.read_bytes() == BEFORE
        assert os.name == 'nt' or stat.S_IMODE(self.module.stat().st_mode) == 0o644


def test_le_releve_lit_les_epingles_sans_rien_changer(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    result = machine.run('survey')
    assert result['status'] == 'SURVEY_OK' and result['drift'] == []
    assert result['module']['sha256'] == result['module']['expected'] == sha(BEFORE)
    assert result['bytecode'] == [] and result['stage'] is False and result['backup'] is False
    assert result['features'] == {'cfs': {'inside_error': True, 'record_tn_move_z': True,
                                          'last_err': True, 'move_z': True}}
    rest = result['rest']
    assert rest['start_revision'] == 'retained-start-v1' and rest['head_filament'] is True
    assert rest['sensor_revision'] == 'cfs-sensor-guard-v2'
    assert machine.actions == [] and machine.writes == [] and not machine.m.BACKUP.exists()
    machine.at_before()


def test_le_releve_signale_un_fichier_qui_a_bouge(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    machine.sibling('kctrl_purge_guard.py').write_bytes(b'changed elsewhere\n')
    assert machine.run('survey')['drift'] == [machine.m.EXTRAS + '/kctrl_purge_guard.py']


def test_le_releve_dit_un_nom_manquant_sans_refuser(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    machine.vendor['gcode_move.py'].write_bytes(b'nothing here\n')
    result = machine.run('survey')
    assert result['status'] == 'SURVEY_OK'
    assert 'gcode_move.py:def reset_last_position' in result['features']['missing']


def test_le_releve_d_une_machine_occupee_dit_occupee(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    machine.status['print_stats'] = {'state': 'printing'}
    assert machine.run('survey') == {'status': 'BUSY', 'problem': 'job_busy'}


@pytest.mark.parametrize('mode', ['preflight', 'install', 'validate', 'rollback'])
def test_sans_releve_seul_le_releve_est_permis(tmp_path, monkeypatch, mode):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    with pytest.raises(AssertionError, match='survey_not_recorded'):
        machine.run(mode)
    assert machine.actions == []


def test_le_preflight_ne_touche_a_rien(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    result = machine.run('preflight')
    assert result['status'] == 'PREFLIGHT_OK' and result['protected'] == len(SIBLINGS)
    assert all(result['cfs_features'].values())
    assert machine.actions == [] and machine.writes == []
    machine.at_before()
    assert not machine.m.BACKUP.exists()


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
    assert machine.actions == [] and machine.writes == []
    machine.at_before()


def test_un_nom_absent_du_cfs_compile_est_seulement_rapporte(tmp_path, monkeypatch):
    # The CFS object is compiled: the module refuses the recovery itself if
    # the name is really missing; the installation only reports it.
    machine = Machine(tmp_path, monkeypatch)
    machine.cfs.write_bytes(b'\x00inside_error\x00')
    result = machine.run('preflight')
    assert result['cfs_features'] == {'inside_error': True, 'record_tn_move_z': False,
                                      'last_err': False, 'move_z': False}


def test_la_pose_remplace_le_seul_module_redemarre_et_prouve_la_reprise(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.module.chmod(0o640)
    (machine.cache / 'kctrl_start.cpython-38.pyc').write_bytes(BEFORE)
    (machine.cache / 'kctrl_sensor_guard.cpython-38.pyc').write_bytes(b'other module')
    result = machine.run('install')
    assert result['status'] == 'INSTALLED_IDLE_OK'
    assert result['revision'] == 'start-load-recovery-v1' and result['recovery_timeout'] == 180
    assert result['rest']['start_phase'] == 'idle' and result['rest']['start_recovery'] is None
    assert result['log']['lines'][-1].endswith('ready') and result['log']['tracebacks'] == 0
    assert machine.actions == ['stop', 'start']
    assert machine.module.read_bytes() == MODULE
    assert os.name == 'nt' or stat.S_IMODE(machine.module.stat().st_mode) == 0o640
    assert machine.writes == [('kctrl_start.py', MODULE)]
    backup = machine.m.BACKUP
    assert (backup / 'module.before').read_bytes() == BEFORE
    assert json.loads((backup / 'mode.json').read_text())['mode'] == oct(0o640) or os.name == 'nt'
    assert json.loads((backup / 'receipt.json').read_text())['status'] == 'INSTALLED_IDLE_OK'
    # Only the start bytecode went; another module's cache is not touched.
    assert sorted(p.name for p in machine.cache.iterdir()) == [
        'kctrl_sensor_guard.cpython-38.pyc', 'kctrl_start.cpython-38.pyc']
    assert (machine.cache / 'kctrl_start.cpython-38.pyc').read_bytes() == MODULE
    for name in SIBLINGS:
        assert machine.sibling(name).read_bytes() == ('# %s\n' % name).encode()
    validated = machine.run('validate')
    assert validated['status'] == 'VALIDATED_IDLE_OK'
    assert validated['revision'] == 'start-load-recovery-v1' and validated['recovery'] is None


def test_la_validation_accepte_la_memoire_d_un_depart_repris(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    recovered = {'slot': 'T1B', 'codes': ['bin_guard', 'key837'], 'paused': True,
                 'lift': 30.14, 'bed': 55.0, 'outcome': 'purged'}
    machine.status['kctrl_start'].update(phase='complete', recovery=recovered)
    result = machine.run('validate')
    assert result['status'] == 'VALIDATED_IDLE_OK' and result['recovery'] == recovered


def test_la_validation_refuse_l_ancien_depart_encore_en_service(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.status['kctrl_start'] = before_status()
    with pytest.raises(AssertionError, match='start_revision_changed'):
        machine.run('validate')


def test_les_identifiants_des_cfs_ne_sortent_jamais_de_la_machine(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    assert 'SERIAL' not in json.dumps(machine.run('survey'))
    machine.manifest['surveyed'] = True
    assert 'SERIAL' not in json.dumps(machine.run('preflight'))
    assert 'SERIAL' not in json.dumps(machine.run('install'))
    assert 'SERIAL' not in json.dumps(machine.run('validate'))
    assert 'SERIAL' not in json.dumps(machine.run('rollback'))


@pytest.mark.parametrize('command', ['', 'T0', 'T15', 'T1A', 'T1B', 'T4D'])
def test_la_memoire_du_dernier_outil_n_empeche_pas_la_pose(tmp_path, monkeypatch, command):
    machine = Machine(tmp_path, monkeypatch)
    machine.status['box']['t_command'] = command
    assert machine.run('preflight')['rest']['t_command'] == command
    assert machine.run('install')['status'] == 'INSTALLED_IDLE_OK'


@pytest.mark.parametrize('command', ['T16', 'T5A', 'T1E', 'G28', None, 1])
def test_une_valeur_inconnue_du_dernier_outil_ferme_la_pose(tmp_path, monkeypatch, command):
    machine = Machine(tmp_path, monkeypatch)
    machine.status['box']['t_command'] = command
    with pytest.raises(AssertionError, match='cfs_command_unknown'):
        machine.run('install')
    assert machine.actions == []
    machine.at_before()


@pytest.mark.parametrize('changes,error', [
    ({'print_stats': {'state': 'printing'}}, 'job_busy'),
    ({'box': {'t_command': 'T2A'}}, 'cfs_command_changed'),
    ({'kctrl_start': {'phase': 'planned'}}, 'start_busy'),
    ({'pause_resume': {'is_paused': True}}, 'paused'),
], ids=['impression', 'outil', 'depart', 'pause'])
def test_ce_qui_arrive_juste_avant_l_arret_annule_la_pose_sans_rien_changer(
        tmp_path, monkeypatch, changes, error):
    machine = Machine(tmp_path, monkeypatch)
    calls = []

    def something_starts():
        calls.append(1)
        if len(calls) == 3:  # after the two stable readings of the preflight
            for key, update in changes.items():
                machine.status[key].update(update)
    machine.hook = something_starts
    assert machine.run('install') == {'status': 'NOT_INSTALLED_NOTHING_CHANGED', 'error': error}
    assert machine.actions == [] and machine.writes == []
    machine.at_before()
    assert not machine.m.BACKUP.exists()


@pytest.mark.parametrize('changes,error', [
    ({'webhooks': {'state': 'startup'}}, 'klipper_not_ready'),
    ({'print_stats': {'state': 'printing'}}, 'job_busy'),
    ({'print_stats': {'state': 'paused'}}, 'job_busy'),
    ({'pause_resume': {'is_paused': True}}, 'paused'),
    ({'virtual_sdcard': {'is_active': True}}, 'sd_active'),
    ({'idle_timeout': {'state': 'Printing'}}, 'idle_timeout_printing'),
    ({'extruder': {'target': 150.0}}, 'heater_target_set'),
    ({'heater_bed': {'target': 55.0}}, 'heater_target_set'),
    ({'motion_report': {'live_velocity': 12.0}}, 'motion_active'),
    ({'motion_report': {'live_extruder_velocity': 3.0}}, 'motion_active'),
    ({'toolhead': {'print_time': 93800.0}}, 'motion_queued'),
    ({'box': {'state': 'disconnect'}}, 'cfs_not_ready'),
    ({'box': {'T2': {'state': 'disconnect'}}}, 'cfs_unit_not_connected'),
    ({'box': {'auto_refill': None}}, 'auto_refill_unknown'),
    ({'kctrl_end': {'phase': 'rewinding'}}, 'end_active'),
    ({'kctrl_end': {'revision': 'cancel-retained-v4'}}, 'end_revision_changed'),
    ({'kctrl_end': {'auto_refill_restore_pending': True}}, 'end_refill_pending'),
    ({'kctrl_start': {'installed': False}}, 'start_not_installed'),
    ({'kctrl_start': {'phase': 'material'}}, 'start_busy'),
    ({'kctrl_start': {'phase': 'referenced'}}, 'start_busy'),
    ({'kctrl_start': {'revision': 'start-load-recovery-v1'}}, 'start_revision_changed'),
    ({'kctrl_tool_change': {'missing': ['T15']}}, 'tool_wrappers_changed'),
    ({'kctrl_tool_change': {'reloads': []}}, 'reloads_not_wrapped'),
    ({'kctrl_print_gate': {'pending': True}}, 'start_waiting_for_spools'),
    ({'kctrl_purge_guard': {'installed': False}}, 'bin_guard_not_installed'),
    ({'kctrl_purge_guard': {'revision': 'start-load-recovery-v1'}}, 'bin_guard_not_installed'),
    ({'kctrl_purge_guard': {'bin_latched': True}}, 'bin_guard_not_at_rest'),
    ({'kctrl_purge_guard': {'cold_installed': False}}, 'cold_guard_not_installed'),
    ({'kctrl_sensor_guard': {'revision': 'cfs-sensor-guard-v1'}}, 'sensor_guard_revision_changed'),
    ({'kctrl_sensor_guard': {'installed': False}}, 'sensor_guard_not_installed'),
    ({'kctrl_sensor_guard': {'hooked': False}}, 'sensor_guard_not_hooked'),
    ({'kctrl_sensor_guard': {'failure': 'tick_failed'}}, 'sensor_guard_failed'),
])
def test_la_pose_refuse_une_machine_qui_n_est_pas_au_repos(tmp_path, monkeypatch, changes, error):
    machine = Machine(tmp_path, monkeypatch)
    machine.status = status(**changes)
    with pytest.raises(AssertionError, match=error):
        machine.run('install')
    assert machine.actions == []
    machine.at_before()
    assert not machine.m.BACKUP.exists()


def test_un_depart_en_echec_au_repos_n_empeche_pas_la_pose(tmp_path, monkeypatch):
    # 12 November 17:11: the failed start left phase 'failed', heaters off.
    machine = Machine(tmp_path, monkeypatch)
    machine.status['kctrl_start'].update(phase='failed', failure='material_timeout')
    machine.status['print_stats'] = {'state': 'error'}
    assert machine.run('install')['status'] == 'INSTALLED_IDLE_OK'


def test_sans_depart_charge_la_pose_refuse(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.status['kctrl_start'] = {}
    with pytest.raises(AssertionError, match='start_not_loaded'):
        machine.run('preflight')


@pytest.mark.parametrize('change,error', [
    ({'enabled': False}, 'start_not_installed'),
    ({'revision': 'retained-start-v1'}, 'start_revision_changed'),
    ({'phase': 'complete'}, 'start_not_fresh'),
    ({'phase': 'disabled'}, 'start_not_fresh'),
    ({'failure': 'printer_disconnected'}, 'start_not_fresh'),
    ({'recovery': {'outcome': 'purged'}}, 'start_recovery_not_fresh'),
    ({'recovery_timeout': 120.0}, 'start_recovery_timeout_changed'),
])
def test_un_depart_qui_ne_demarre_pas_comme_prevu_revient_a_l_ancien(
        tmp_path, monkeypatch, change, error):
    machine = Machine(tmp_path, monkeypatch, loaded=lambda start: start.update(change))
    result = machine.run('install')
    assert result['status'] == 'INSTALL_FAILED_ROLLED_BACK'
    assert error in result['error']
    machine.at_before()
    assert machine.actions == ['stop', 'start', 'stop', 'start']
    assert machine.status['kctrl_start']['revision'] == 'retained-start-v1'
    assert [p.read_bytes() for p in machine.cache.iterdir()] == [BEFORE]


def test_un_depart_sans_champ_de_reprise_revient_a_l_ancien(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, loaded=lambda start: start.pop('recovery'))
    result = machine.run('install')
    assert result['status'] == 'INSTALL_FAILED_ROLLED_BACK'
    assert 'start_recovery_not_fresh' in result['error']
    machine.at_before()


def test_klipper_qui_refuse_de_demarrer_revient_a_l_ancien(tmp_path, monkeypatch):
    def refuses(start):
        machine.status['webhooks'] = {'state': 'error'}
    machine = Machine(tmp_path, monkeypatch, loaded=refuses)
    result = machine.run('install')
    assert result['status'] == 'INSTALL_FAILED_ROLLED_BACK'
    assert 'klipper_not_ready' in result['error']
    machine.at_before()


def test_un_fichier_protege_modifie_bloque_tout(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.sibling('kctrl_sensor_guard.py').write_bytes(b'changed elsewhere\n')
    with pytest.raises(RuntimeError, match='protected_file_drift'):
        machine.run('preflight')


@pytest.mark.parametrize('name', SIBLINGS)
def test_chaque_module_voisin_doit_etre_epingle(tmp_path, monkeypatch, name):
    machine = Machine(tmp_path, monkeypatch)
    del machine.manifest['protected'][machine.m.EXTRAS + '/' + name]
    with pytest.raises(AssertionError, match='sibling_not_pinned'):
        machine.run('preflight')


def test_une_charge_alteree_est_refusee_avant_tout(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    with pytest.raises(AssertionError, match='payload_hash_changed'):
        machine.run('install', payload=b'something else\n')
    machine.manifest['protected'][str(machine.module)] = sha(BEFORE)
    with pytest.raises(AssertionError, match='target_also_protected'):
        machine.run('install')
    assert machine.actions == []


@pytest.mark.parametrize('prepare,error', [
    (lambda machine: machine.module.write_bytes(b'other start\n'), 'module_not_retained_start'),
    (lambda machine: machine.module.unlink(), 'module_not_retained_start'),
    (lambda machine: machine.m.BACKUP.mkdir(parents=True), 'backup_already_exists'),
    (lambda machine: Path(str(machine.module) + machine.m.STAGE_SUFFIX).write_bytes(b'x'),
     'stale_stage_file'),
], ids=['module', 'absent', 'sauvegarde', 'etape'])
def test_un_etat_de_depart_different_ferme_la_pose(tmp_path, monkeypatch, prepare, error):
    machine = Machine(tmp_path, monkeypatch)
    prepare(machine)
    with pytest.raises(AssertionError, match=error):
        machine.run('install')
    assert machine.actions == []


def test_une_pose_deja_faite_ne_se_rejoue_pas(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    with pytest.raises(AssertionError, match='module_not_retained_start'):
        machine.run('install')


def test_le_retour_arriere_remet_l_ancien_depart_exact(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.module.chmod(0o640)
    machine.run('install')
    machine.status['kctrl_start'].update(phase='complete', recovery={'outcome': 'purged'})
    result = machine.run('rollback')
    assert result['status'] == 'ROLLED_BACK'
    assert result['rest']['start_revision'] == 'retained-start-v1'
    assert machine.module.read_bytes() == BEFORE
    assert os.name == 'nt' or stat.S_IMODE(machine.module.stat().st_mode) == 0o640
    assert machine.actions == ['stop', 'start', 'stop', 'start']
    assert [p.read_bytes() for p in machine.cache.iterdir()] == [BEFORE]


def test_le_retour_arriere_refuse_une_impression_en_cours(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.status['print_stats'] = {'state': 'printing'}
    with pytest.raises(AssertionError, match='job_busy'):
        machine.run('rollback')
    assert machine.module.read_bytes() == MODULE
    assert machine.actions == ['stop', 'start']


def test_le_retour_arriere_refuse_une_pause(tmp_path, monkeypatch):
    # Rule of 24 September: no restart during a print, even paused.
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.status['print_stats'] = {'state': 'paused'}
    machine.status['pause_resume'] = {'is_paused': True}
    with pytest.raises(AssertionError, match='job_busy'):
        machine.run('rollback')
    assert machine.module.read_bytes() == MODULE


def test_le_retour_arriere_refuse_un_depart_en_cours(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.status['kctrl_start']['phase'] = 'material'
    with pytest.raises(AssertionError, match='start_busy'):
        machine.run('rollback')
    assert machine.module.read_bytes() == MODULE


@pytest.mark.parametrize('breakage,error', [
    (lambda machine: (machine.m.BACKUP / 'module.before').write_bytes(b'damaged'), 'backup_corrupt'),
    (lambda machine: machine.module.write_bytes(b'someone else\n'), 'rollback_foreign_file'),
], ids=['sauvegarde', 'module'])
def test_un_retour_arriere_impossible_se_voit_avant_d_arreter_klipper(
        tmp_path, monkeypatch, breakage, error):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    breakage(machine)
    with pytest.raises(AssertionError, match=error):
        machine.run('rollback')
    assert machine.actions == ['stop', 'start']
    assert machine.running


def test_le_journal_est_lu_depuis_l_arret_par_morceaux_bornes(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.log.write_bytes(b'x' * (3 << 20) + b'\nTraceback before\n')
    offset = machine.log.stat().st_size
    with machine.log.open('ab') as stream:
        stream.write(b'y' * ((1 << 20) - 20) + b' kctrl_start: ready\n')
    result = machine.m.log_lines(offset)
    assert result['tracebacks'] == 0
    assert result['lines'] == [('y' * 240 + ' kctrl_start: ready')[-240:]]


def test_les_champs_lus_sont_ceux_du_vrai_module(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery_test.base, 'module', recovery_test.module)
    monkeypatch.setattr(recovery_test.base, 'policy', recovery_test.policy)
    machine = recovery_test.Machine(tmp_path)
    start = json.loads(json.dumps(machine.owner.get_status()))
    m = load()
    assert set(m.QUERY['kctrl_start']) <= set(start)
    # Fresh as the installer wants it after the restart.
    m.start_fresh({key: start[key] for key in m.QUERY['kctrl_start']})


def test_les_noms_constructeur_sont_dans_les_sources_capturees():
    # The pinned vendor files were captured: their hashes are those the
    # manifest pins, and they hold the names the preflight looks for.
    m = load()
    pins = manifest()['protected']
    sources = ROOT / 'inventory/raw/20260921-cfs-end-cold-v1/sources'
    for name in ('virtual_sdcard.py', 'pause_resume.py'):
        path = sources / name
        if not path.exists():
            pytest.skip('vendor capture not on this workstation')
        data = path.read_bytes()
        assert sha(data) == pins[m.EXTRAS + '/' + name]
        assert all(needle in data for needle in m.FEATURES[m.EXTRAS + '/' + name])


def manifest():
    return json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))


def test_le_manifeste_epingle_le_candidat_et_l_installateur():
    pins = manifest()
    assert sha((ROOT / pins['source']).read_bytes()) == pins['sha256']
    assert sha((PACKAGE / 'remote_install.py').read_bytes()) == pins['installer_sha256']
    assert pins['destination'] == '/usr/share/klipper/klippy/extras/kctrl_start.py'
    assert pins['adr'] == 'ADR-079' and pins['backup'].endswith('/start-load-recovery-v1')
    assert (ROOT / pins['document']).exists()
    effects = pins['effects']
    assert effects['klipper_restart_idle_only'] is True
    assert not any(effects[key] for key in ('heating', 'motion', 'filament', 'config_change',
                                            'printer_cfg_change'))


def test_avant_c_est_le_depart_garde_et_les_epingles_de_la_garde_v2():
    pins = manifest()
    sensor = json.loads((SENSOR / 'manifest.json').read_text(encoding='utf-8'))
    assert pins['before_sha256'] == sha((RETAINED / 'kctrl_start.py').read_bytes()) \
        == sensor['protected'][pins['destination']]
    expected = dict(sensor['protected'])
    del expected[pins['destination']]
    expected[sensor['destination']] = sensor['sha256']
    assert pins['protected'] == expected and len(expected) == 24
    assert pins['protected']['/usr/share/klipper/klippy/extras/kctrl_sensor_guard.py'] == \
        sha((SENSOR / 'kctrl_sensor_guard.py').read_bytes())


def test_les_modules_voisins_epingles_sont_ceux_du_depart_garde():
    pins = manifest()['protected']
    for name in ('kctrl_start_policy.py', 'kctrl_start_context.py', 'kctrl_bin_motion.py'):
        assert pins['/usr/share/klipper/klippy/extras/' + name] == \
            sha((RETAINED / name).read_bytes()), name


def test_les_paquets_anterieurs_refusent_tant_que_celui_ci_est_pose():
    # They pin kctrl_start.py at the retained hash: roll this one back first.
    assert manifest()['sha256'] != manifest()['before_sha256']
    for name in ('cfs-sensor-guard-v2', 'cold-push-guard-v1', 'end-no-stock-flush-v5'):
        other = json.loads((ROOT / 'packages/k1-control-v1' / name / 'manifest.json')
                           .read_text(encoding='utf-8'))
        assert other['protected']['/usr/share/klipper/klippy/extras/kctrl_start.py'] == \
            manifest()['before_sha256'], name
