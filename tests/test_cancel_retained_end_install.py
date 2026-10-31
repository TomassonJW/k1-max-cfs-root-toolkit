"""Install, refuse and roll back the retained cancel entirely in a temporary tree.

The printer is replaced by a status dictionary, the service by a log of
actions, the files by temporary copies (ADR-074).
"""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import types

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / 'packages/k1-control-v1/cancel-retained-end-v4'
TOOLS = ['T%d' % index for index in range(16)]
SLOTS = ['T%s%s' % (box, slot) for box in '1234' for slot in 'ABCD']
WRAPPED = ['CANCEL_PRINT', 'END_PRINT', 'START_PRINT']


def load():
    spec = importlib.util.spec_from_file_location('cancel_retained_install', PACKAGE / 'remote_install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def end_status(code, **changes):
    value = {'enabled': True, 'phase': 'complete', 'reason': 'fin', 'failure': '',
             'thermal_failure': '', 'job_epoch': 4, 'pending': False, 'slot': None,
             'physical_validation': False, 'wrapped': list(WRAPPED)}
    if code == 'after':
        value.update(phase='idle', reason='', job_epoch=0, retained=False,
                     revision='cancel-retained-v4')
    else:
        value.update(revision='end-rewind-confirm-v3')
    value.update(changes)
    return value


def status(code='before', **changes):
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
        'box': {'enable': 1, 'state': 'connect', 't_command': ''},
        'kctrl_end': end_status(code),
        'kctrl_start': {'enabled': True, 'installed': True, 'phase': 'complete',
                        'revision': 'retained-start-v1'},
        'kctrl_tool_change': {'wrapped': list(TOOLS), 'missing': [], 'reloads': list(SLOTS)},
    }
    for key, update in changes.items():
        value[key] = dict(value[key], **update)
    return value


class Machine:
    """Temporary tree, fake Klipper status and service, same paths as the module."""

    def __init__(self, tmp_path, monkeypatch, new_code_runs=True):
        self.m = m = load()
        self.target = tmp_path / 'extras/kctrl_end.py'
        self.target.parent.mkdir()
        self.original = b'installed end v3 18778298\n'
        self.target.write_bytes(self.original)
        self.target.chmod(0o600)
        self.candidate = b'# candidate cancel-retained-v4\n'
        protected = tmp_path / 'extras/kctrl_tool_change.py'
        protected.write_bytes(b'tool change with reloads\n')
        self.protected = protected
        self.log = tmp_path / 'klippy.log'
        self.log.write_bytes(b'old line\n')
        self.pid = tmp_path / 'klippy.pid'
        self.pid.write_text('2210')
        for name, value in (('TARGET', str(self.target)), ('STAGE', str(self.target) + '.next'),
                            ('BACKUP', tmp_path / 'backups/cancel-retained-end-v4'),
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
        self.status = status('before')
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
            self.status = status('after' if new else 'before', print_stats={'state': 'standby'},
                                 kctrl_start={'phase': 'idle'})
            if not new:
                self.status['kctrl_end'].update(phase='idle', job_epoch=0)
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
    assert result['revision'] == 'cancel-retained-v4'
    assert result['log']['lines'][-1].endswith('START_PRINT')
    assert result['log']['tracebacks'] == 0
    assert machine.actions == ['stop', 'start']
    assert machine.target.read_bytes() == machine.candidate
    assert stat.S_IMODE(machine.target.stat().st_mode) == mode
    backup = machine.m.BACKUP / 'kctrl_end.py.before'
    assert backup.read_bytes() == machine.original
    assert json.loads((machine.m.BACKUP / 'receipt.json').read_text())['status'] == 'INSTALLED_IDLE_OK'
    validated = machine.run('validate')
    assert validated['status'] == 'VALIDATED_IDLE_OK' and validated['retained'] is False


def test_un_ancien_code_encore_charge_apres_redemarrage_revient_a_l_original(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, new_code_runs=False)
    result = machine.run('install')
    assert result['status'] == 'INSTALL_FAILED_ROLLED_BACK'
    assert 'end_revision_changed' in result['error']
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
    # L'annulation du 2 octobre laisse justement la fin en echec.
    machine = Machine(tmp_path, monkeypatch)
    machine.status['kctrl_end'].update(phase=end)
    assert machine.run('install')['status'] == 'INSTALLED_IDLE_OK'


@pytest.mark.parametrize('changes,error', [
    ({'print_stats': {'state': 'printing'}}, 'job_busy'),
    ({'print_stats': {'state': 'paused'}}, 'job_busy'),
    ({'pause_resume': {'is_paused': True}}, 'paused'),
    ({'virtual_sdcard': {'is_active': True}}, 'sd_active'),
    ({'idle_timeout': {'state': 'Printing'}}, 'idle_timeout_printing'),
    ({'extruder': {'target': 150.0}}, 'heater_target_set'),
    ({'heater_bed': {'target': 55.0}}, 'heater_target_set'),
    ({'motion_report': {'live_velocity': 12.0}}, 'motion_active'),
    ({'toolhead': {'print_time': 93800.0}}, 'motion_queued'),
    ({'box': {'t_command': 'T1A'}}, 'cfs_command_present'),
    ({'box': {'state': 'disconnect'}}, 'cfs_not_ready'),
    ({'kctrl_end': {'phase': 'rewinding'}}, 'end_active'),
    ({'kctrl_end': {'phase': 'finalizing'}}, 'end_active'),
    ({'kctrl_end': {'pending': True}}, 'end_busy'),
    ({'kctrl_end': {'revision': 'other'}}, 'end_revision_changed'),
    ({'kctrl_end': {'wrapped': ['END_PRINT']}}, 'end_wrappers_changed'),
    ({'kctrl_start': {'phase': 'material'}}, 'start_busy'),
    ({'kctrl_start': {'phase': 'planned'}}, 'start_busy'),
    ({'kctrl_start': {'revision': 'other'}}, 'start_revision_changed'),
    ({'kctrl_tool_change': {'missing': ['T15']}}, 'tool_wrappers_changed'),
    ({'kctrl_tool_change': {'reloads': []}}, 'reloads_not_wrapped'),
])
def test_la_pose_refuse_une_machine_qui_n_est_pas_au_repos(tmp_path, monkeypatch, changes, error):
    machine = Machine(tmp_path, monkeypatch)
    machine.status = status('before', **changes)
    with pytest.raises(AssertionError, match=error):
        machine.run('install')
    assert machine.actions == []
    assert machine.target.read_bytes() == machine.original
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
    assert result['status'] == 'ROLLED_BACK'
    assert machine.target.read_bytes() == machine.original
    assert machine.actions == ['stop', 'start', 'stop', 'start']
    assert machine.status['kctrl_end']['revision'] == 'end-rewind-confirm-v3'


def test_le_retour_arriere_refuse_une_impression_en_cours(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.status['print_stats'] = {'state': 'printing'}
    with pytest.raises(AssertionError, match='job_busy'):
        machine.run('rollback')
    assert machine.target.read_bytes() == machine.candidate


def test_le_journal_est_lu_depuis_l_arret_par_morceaux_bornes(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.log.write_bytes(b'x' * (3 << 20) + b'\nTraceback before\n')
    offset = machine.log.stat().st_size
    with machine.log.open('ab') as stream:
        stream.write(b'y' * ((1 << 20) - 20) + b' kctrl_end: retained cancel phase=complete\n')
    result = machine.m.log_lines(offset)
    assert result['tracebacks'] == 0
    assert result['lines'] == [('y' * 240 + ' kctrl_end: retained cancel phase=complete')[-240:]]
    machine.log.unlink()
    assert machine.m.log_lines(offset)['error']


def test_le_manifeste_epingle_le_candidat_l_installateur_et_la_chaine_d_impression():
    manifest = json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))
    root = PACKAGE.parents[2]
    assert hashlib.sha256((root / manifest['source']).read_bytes()).hexdigest() == manifest['sha256']
    assert hashlib.sha256((PACKAGE / 'remote_install.py').read_bytes()).hexdigest() \
        == manifest['installer_sha256']
    v3 = root / 'packages/k1-control-v1/end-rewind-confirm-v3/kctrl_end.py'
    assert manifest['before_sha256'] == hashlib.sha256(v3.read_bytes()).hexdigest() == \
        '18778298360e86c9c4ddb848044de7d8d657db78c31f0becc8ee441a00d652fb'
    assert manifest['destination'].endswith('/extras/kctrl_end.py')
    assert manifest['destination'] not in manifest['protected']
    change = root / 'packages/k1-control-v1/owned-start-print-v2/kctrl_tool_change.py'
    assert manifest['protected']['/usr/share/klipper/klippy/extras/kctrl_tool_change.py'] == \
        hashlib.sha256(change.read_bytes()).hexdigest()
    assert len(manifest['protected']) == 19
    assert not any(manifest['effects'][key] for key in ('heating', 'motion', 'filament',
                                                        'config_change'))
