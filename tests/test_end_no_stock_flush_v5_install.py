"""Install, refuse and roll back the stock refill switch entirely in a temporary tree.

The printer is replaced by a status dictionary, the service by a log of
actions, the files by temporary copies (ADR-076).
"""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import types

import pytest

import test_cold_push_guard_install as cold_test

PACKAGE = Path(__file__).resolve().parents[1] / 'packages/k1-control-v1/end-no-stock-flush-v5'
TOOLS = ['T%d' % index for index in range(16)]
SLOTS = ['T%s%s' % (box, slot) for box in '1234' for slot in 'ABCD']
WRAPPED = ['CANCEL_PRINT', 'END_PRINT', 'START_PRINT']
GUARD = {'revision': 'retained-start-v1', 'installed': True, 'bin_latched': False,
         'minimum_z': 30.0, 'denied': 0, 'last_error': '',
         'cold_revision': 'cold-push-guard-v1', 'cold_installed': True, 'cold_refused': 0,
         'cold_last': ''}


def load():
    spec = importlib.util.spec_from_file_location('end_no_stock_flush_install',
                                                  PACKAGE / 'remote_install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def end_status(code, **changes):
    value = {'enabled': True, 'phase': 'complete', 'reason': 'fin', 'failure': '',
             'thermal_failure': '', 'job_epoch': 4, 'pending': False, 'slot': None,
             'retained': False, 'physical_validation': False, 'wrapped': list(WRAPPED)}
    if code == 'after':
        value.update(phase='idle', reason='', job_epoch=0, auto_refill_saved=None,
                     auto_refill_restore_pending=False, revision='end-no-stock-flush-v5')
    else:
        value.update(revision='cancel-retained-v4')
    value.update(changes)
    return value


def status(code='before', refill=1, **changes):
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
        'box': {'enable': 1, 'state': 'connect', 't_command': '', 'auto_refill': refill},
        'kctrl_end': end_status(code),
        'kctrl_start': {'enabled': True, 'installed': True, 'phase': 'complete',
                        'revision': 'retained-start-v1'},
        'kctrl_tool_change': {'wrapped': list(TOOLS), 'missing': [], 'reloads': list(SLOTS)},
        'kctrl_purge_guard': dict(GUARD),
    }
    for key, update in changes.items():
        value[key] = dict(value[key], **update)
    return value


class Machine:
    """Temporary tree, fake Klipper status and service, same paths as the module."""

    def __init__(self, tmp_path, monkeypatch, new_code_runs=True, refill=1, after=None):
        self.m = m = load()
        self.target = tmp_path / 'extras/kctrl_end.py'
        self.target.parent.mkdir()
        self.original = b'installed end v4 f3656210\n'
        self.target.write_bytes(self.original)
        self.target.chmod(0o600)
        self.candidate = b'# candidate end-no-stock-flush-v5\n'
        protected = tmp_path / 'extras/kctrl_purge_guard.py'
        protected.write_bytes(b'bin guard with the cold push refusal\n')
        self.protected = protected
        self.log = tmp_path / 'klippy.log'
        self.log.write_bytes(b'old line\n')
        self.pid = tmp_path / 'klippy.pid'
        self.pid.write_text('2210')
        for name, value in (('TARGET', str(self.target)), ('STAGE', str(self.target) + '.next'),
                            ('BACKUP', tmp_path / 'backups/end-no-stock-flush-v5'),
                            ('LOG', self.log), ('PIDFILE', self.pid)):
            monkeypatch.setattr(m, name, value)
        clock = [0.0]
        monkeypatch.setattr(m, 'time', types.SimpleNamespace(
            monotonic=lambda: clock[0], time=lambda: 1.0e9 + clock[0],
            sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds)))
        monkeypatch.setattr(m, 'compiles', lambda data: compile(data, 'candidate', 'exec'))
        self.actions = []
        self.running = True
        self.new_code_runs = new_code_runs
        self.refill = refill
        self.after = after
        self.status = status('before', refill)
        self.hook = None
        monkeypatch.setattr(m, 'state', self.state)
        monkeypatch.setattr(m, 'service', self.service)
        monkeypatch.setattr(m, 'stop', self.stop)
        self.manifest = {
            'name': m.NAME, 'destination': str(self.target),
            'before_sha256': hashlib.sha256(self.original).hexdigest(),
            'sha256': hashlib.sha256(self.candidate).hexdigest(),
            'protected': {str(protected): hashlib.sha256(protected.read_bytes()).hexdigest()},
        }

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
        elif action == 'start':
            self.running = True
            self.pid.write_text(str(int(self.pid.read_text()) + 1))
            new = self.target.read_bytes() == self.candidate and self.new_code_runs
            self.status = status('after' if new else 'before', self.refill,
                                 print_stats={'state': 'standby'}, kctrl_start={'phase': 'idle'})
            if not new:
                self.status['kctrl_end'].update(phase='idle', job_epoch=0)
            elif self.after:
                self.after(self.status['kctrl_end'])
            with self.log.open('ab') as stream:
                stream.write(b'[INFO] kctrl_end: wrapped CANCEL_PRINT,END_PRINT,START_PRINT\n')

    def stop(self):
        pid = self.pid.read_text()
        self.service('stop')
        return pid

    def run(self, mode, payload=None):
        return self.m.run({'mode': mode, 'manifest': self.manifest,
                           'payload': base64.b64encode(payload or self.candidate).decode()})


def test_le_preflight_ne_touche_a_rien(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    assert machine.run('preflight') == {'status': 'PREFLIGHT_OK', 'protected': 1}
    assert machine.actions == []
    assert machine.target.read_bytes() == machine.original
    assert not machine.m.BACKUP.exists()


def test_la_pose_sauvegarde_remplace_redemarre_et_prouve_la_nouvelle_fin(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    mode = stat.S_IMODE(machine.target.stat().st_mode)
    result = machine.run('install')
    assert result['status'] == 'INSTALLED_IDLE_OK'
    assert result['revision'] == 'end-no-stock-flush-v5' and result['auto_refill'] == 1
    assert result['log']['lines'][-1].endswith('START_PRINT')
    assert result['log']['tracebacks'] == 0
    assert machine.actions == ['stop', 'start']
    assert machine.target.read_bytes() == machine.candidate
    assert stat.S_IMODE(machine.target.stat().st_mode) == mode
    backup = machine.m.BACKUP / 'kctrl_end.py.before'
    assert backup.read_bytes() == machine.original
    assert json.loads((machine.m.BACKUP / 'receipt.json').read_text())['status'] == 'INSTALLED_IDLE_OK'
    assert machine.run('validate') == {
        'status': 'VALIDATED_IDLE_OK', 'revision': 'end-no-stock-flush-v5', 'phase': 'idle',
        'retained': False, 'auto_refill': 1, 'auto_refill_saved': None,
        'auto_refill_restore_pending': False, 'print_state': 'standby'}


def test_la_pose_rapporte_un_auto_remplacement_deja_coupe(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, refill=0)
    result = machine.run('install')
    assert result['status'] == 'INSTALLED_IDLE_OK' and result['auto_refill'] == 0


def test_un_ancien_code_encore_charge_apres_redemarrage_revient_a_l_original(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, new_code_runs=False)
    result = machine.run('install')
    assert result['status'] == 'INSTALL_FAILED_ROLLED_BACK'
    assert 'end_revision_changed' in result['error']
    assert machine.target.read_bytes() == machine.original
    assert machine.actions == ['stop', 'start', 'stop', 'start']


@pytest.mark.parametrize('after', [
    lambda end: end.update(auto_refill_restore_pending=True),
    lambda end: end.update(auto_refill_saved=1),
    lambda end: end.pop('auto_refill_saved'),
    lambda end: end.update(phase='complete'),
    lambda end: end.update(retained=True),
], ids=['restauration_due', 'valeur_gardee', 'champ_absent', 'phase', 'filament_garde'])
def test_une_nouvelle_fin_qui_a_deja_bascule_quelque_chose_revient_a_l_original(
        tmp_path, monkeypatch, after):
    machine = Machine(tmp_path, monkeypatch, after=after)
    result = machine.run('install')
    assert result['status'] == 'INSTALL_FAILED_ROLLED_BACK'
    assert 'end_not_fresh' in result['error']
    assert machine.target.read_bytes() == machine.original
    assert machine.actions == ['stop', 'start', 'stop', 'start']


def test_une_impression_lancee_avant_l_arret_annule_la_pose_sans_rien_changer(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    calls = []

    def print_starts():
        calls.append(1)
        if len(calls) == 3:  # apres les deux lectures stables du preflight
            machine.status['print_stats'] = {'state': 'printing'}
    machine.hook = print_starts
    result = machine.run('install')
    assert result == {'status': 'NOT_INSTALLED_NOTHING_CHANGED', 'error': 'job_busy'}
    assert machine.actions == []
    assert machine.target.read_bytes() == machine.original
    assert not machine.m.BACKUP.exists()


@pytest.mark.parametrize('end', ['idle', 'complete', 'failed'])
def test_une_fin_au_repos_meme_echouee_permet_la_pose(tmp_path, monkeypatch, end):
    # La fin du 31 octobre reste justement en echec jusqu'au redemarrage.
    machine = Machine(tmp_path, monkeypatch)
    machine.status['kctrl_end'].update(phase=end)
    assert machine.run('install')['status'] == 'INSTALLED_IDLE_OK'


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
    ({'box': {'t_command': 'T1A'}}, 'cfs_command_present'),
    ({'box': {'state': 'disconnect'}}, 'cfs_not_ready'),
    ({'box': {'auto_refill': None}}, 'auto_refill_unknown'),
    ({'box': {'auto_refill': 2}}, 'auto_refill_unknown'),
    ({'box': {'auto_refill': True}}, 'auto_refill_unknown'),
    ({'box': {'auto_refill': '1'}}, 'auto_refill_unknown'),
    ({'kctrl_end': {'phase': 'rewinding'}}, 'end_active'),
    ({'kctrl_end': {'phase': 'finalizing'}}, 'end_active'),
    ({'kctrl_end': {'pending': True}}, 'end_busy'),
    ({'kctrl_end': {'revision': 'other'}}, 'end_revision_changed'),
    ({'kctrl_end': {'revision': 'end-rewind-confirm-v3'}}, 'end_revision_changed'),
    ({'kctrl_end': {'auto_refill_saved': None}}, 'unexpected_refill_field'),
    ({'kctrl_end': {'wrapped': ['END_PRINT']}}, 'end_wrappers_changed'),
    ({'kctrl_start': {'installed': False}}, 'start_not_installed'),
    ({'kctrl_start': {'phase': 'material'}}, 'start_busy'),
    ({'kctrl_start': {'phase': 'planned'}}, 'start_busy'),
    ({'kctrl_start': {'revision': 'other'}}, 'start_revision_changed'),
    ({'kctrl_tool_change': {'missing': ['T15']}}, 'tool_wrappers_changed'),
    ({'kctrl_tool_change': {'reloads': []}}, 'reloads_not_wrapped'),
    ({'kctrl_purge_guard': {'installed': False}}, 'bin_guard_not_installed'),
    ({'kctrl_purge_guard': {'bin_latched': True}}, 'bin_guard_not_at_rest'),
    ({'kctrl_purge_guard': {'minimum_z': 20.0}}, 'bin_guard_not_at_rest'),
    ({'kctrl_purge_guard': {'cold_installed': False}}, 'cold_guard_not_installed'),
    ({'kctrl_purge_guard': {'cold_revision': 'other'}}, 'cold_guard_not_installed'),
])
def test_la_pose_refuse_une_machine_qui_n_est_pas_au_repos(tmp_path, monkeypatch, changes, error):
    machine = Machine(tmp_path, monkeypatch)
    machine.status = status('before', **changes)
    with pytest.raises(AssertionError, match=error):
        machine.run('install')
    assert machine.actions == []
    assert machine.target.read_bytes() == machine.original
    assert not machine.m.BACKUP.exists()


@pytest.mark.parametrize('name,field,error', [
    ('box', 'auto_refill', 'auto_refill_unknown'),
    ('kctrl_purge_guard', 'cold_revision', 'cold_guard_not_installed'),
    ('kctrl_purge_guard', 'cold_installed', 'cold_guard_not_installed'),
])
def test_un_champ_absent_refuse_la_pose(tmp_path, monkeypatch, name, field, error):
    machine = Machine(tmp_path, monkeypatch)
    machine.status[name].pop(field)
    with pytest.raises(AssertionError, match=error):
        machine.run('install')
    assert machine.actions == []
    assert not machine.m.BACKUP.exists()


def test_un_fichier_protege_modifie_bloque_tout(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.protected.write_bytes(b'changed elsewhere\n')
    with pytest.raises(RuntimeError, match='protected_file_drift'):
        machine.run('preflight')


def test_une_cible_deja_differente_ou_une_charge_alteree_sont_refusees(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    with pytest.raises(AssertionError, match='payload_hash_changed'):
        machine.run('install', payload=b'something else\n')
    machine.target.write_bytes(b'foreign version\n')
    with pytest.raises(AssertionError, match='target_not_at_baseline'):
        machine.run('install')
    assert machine.actions == []


def test_une_pose_deja_faite_ne_se_rejoue_pas(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    with pytest.raises(AssertionError, match='target_not_at_baseline'):
        machine.run('install')


def test_le_retour_arriere_remet_l_original_exact(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    result = machine.run('rollback')
    assert result['status'] == 'ROLLED_BACK' and result['auto_refill'] == 1
    assert machine.target.read_bytes() == machine.original
    assert machine.actions == ['stop', 'start', 'stop', 'start']
    assert machine.status['kctrl_end']['revision'] == 'cancel-retained-v4'


def test_le_retour_arriere_refuse_une_impression_en_cours(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.status['print_stats'] = {'state': 'printing'}
    with pytest.raises(AssertionError, match='job_busy'):
        machine.run('rollback')
    assert machine.target.read_bytes() == machine.candidate


def test_le_retour_arriere_exige_encore_le_refus_de_poussee_a_froid(tmp_path, monkeypatch):
    # Ordre inverse de la pose : cette fin repart avant cold-push-guard-v1.
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.status['kctrl_purge_guard'].pop('cold_revision')
    with pytest.raises(AssertionError, match='cold_guard_not_installed'):
        machine.run('rollback')
    assert machine.target.read_bytes() == machine.candidate
    assert machine.actions == ['stop', 'start']


@pytest.mark.parametrize('code', ['before', 'after', None])
def test_le_refus_a_froid_ne_peut_plus_etre_retire_tant_que_cette_fin_tourne(code):
    cold = cold_test.load()
    running = cold_test.status('after', kctrl_end={'revision': 'end-no-stock-flush-v5'})
    with pytest.raises(AssertionError, match='end_revision_changed'):
        cold.idle(running, code)


def test_le_journal_est_lu_depuis_l_arret_par_morceaux_bornes(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.log.write_bytes(b'x' * (3 << 20) + b'\nTraceback before\n')
    offset = machine.log.stat().st_size
    with machine.log.open('ab') as stream:
        stream.write(b'y' * ((1 << 20) - 20) + b' kctrl_end: auto refill restored\n')
    result = machine.m.log_lines(offset)
    assert result['tracebacks'] == 0
    assert result['lines'] == [('y' * 240 + ' kctrl_end: auto refill restored')[-240:]]
    machine.log.unlink()
    assert machine.m.log_lines(offset)['error']


def test_le_manifeste_epingle_le_candidat_l_installateur_et_le_refus_a_froid():
    manifest = json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))
    root = PACKAGE.parents[2]
    assert hashlib.sha256((root / manifest['source']).read_bytes()).hexdigest() == manifest['sha256']
    assert hashlib.sha256((PACKAGE / 'remote_install.py').read_bytes()).hexdigest() \
        == manifest['installer_sha256']
    v4 = root / 'packages/k1-control-v1/cancel-retained-end-v4/kctrl_end.py'
    assert manifest['before_sha256'] == hashlib.sha256(v4.read_bytes()).hexdigest() == \
        'f3656210863d57b479ac9bc46dfd55852688233fc3e015838db5c23eee716c86'
    assert manifest['destination'] == '/usr/share/klipper/klippy/extras/kctrl_end.py'
    assert manifest['destination'] not in manifest['protected']
    # Same pins as the cold guard checked on the printer, the end file swapped
    # for the guard it now relies on.
    cold = json.loads((root / 'packages/k1-control-v1/cold-push-guard-v1/manifest.json')
                      .read_text(encoding='utf-8'))
    assert cold['protected'][manifest['destination']] == manifest['before_sha256']
    assert cold['sha256'] == '8c637cc4bf5724c4fb589c7e91ef0e5fc53f700934de0284fc1db20a3f7e1e9a'
    expected = dict(cold['protected'])
    del expected[manifest['destination']]
    expected[cold['destination']] = cold['sha256']
    assert manifest['protected'] == expected and len(expected) == 23
    assert manifest['effects']['klipper_restart_idle_only'] is True
    assert not any(manifest['effects'][key] for key in ('heating', 'motion', 'filament',
                                                        'config_change'))
