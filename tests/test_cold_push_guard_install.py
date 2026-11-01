"""Install, probe and roll back the cold push refusal entirely in a temporary tree.

The printer is replaced by a status dictionary, the service by a log of
actions, the files by temporary copies, the probe push by a fake G-code
answer (ADR-076).
"""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import types

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / 'packages/k1-control-v1/cold-push-guard-v1'
TOOLS = ['T%d' % index for index in range(16)]
SLOTS = ['T%s%s' % (box, slot) for box in '1234' for slot in 'ABCD']
WRAPPED = ['CANCEL_PRINT', 'END_PRINT', 'START_PRINT']
HEAD = 'filament_switch_sensor filament_sensor_2'
REFUSAL = ("klippy_error: {'error': 'WebRequestError', 'message': 'K1 Control: poussee de "
           "filament refusee, buse froide (24 C, minimum 170 C) sans chauffe demandee.'}")


def load():
    spec = importlib.util.spec_from_file_location('cold_push_install', PACKAGE / 'remote_install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def guard_status(code):
    value = {'revision': 'retained-start-v1', 'installed': True, 'bin_latched': False,
             'minimum_z': 30.0, 'denied': 0, 'last_error': ''}
    if code == 'after':
        value.update(cold_revision='cold-push-guard-v1', cold_installed=True,
                     cold_refused=0, cold_last='')
    return value


def status(code='before', **changes):
    value = {
        'webhooks': {'state': 'ready'},
        'print_stats': {'state': 'complete'},
        'virtual_sdcard': {'is_active': False},
        'pause_resume': {'is_paused': False},
        'idle_timeout': {'state': 'Idle'},
        'extruder': {'target': 0.0, 'temperature': 24.0, 'can_extrude': False},
        'heater_bed': {'target': 0.0},
        'toolhead': {'print_time': 93138.4, 'estimated_print_time': 93739.5,
                     'position': [200.0, 273.0, 50.0, 12.5]},
        'motion_report': {'live_velocity': 5.68e-14, 'live_extruder_velocity': 0.0},
        'gcode_move': {'absolute_extrude': True},
        'box': {'enable': 1, 'state': 'connect', 't_command': ''},
        HEAD: {'filament_detected': False},
        'kctrl_end': {'enabled': True, 'phase': 'failed', 'pending': False,
                      'wrapped': list(WRAPPED), 'retained': False,
                      'revision': 'cancel-retained-v4'},
        'kctrl_start': {'enabled': True, 'installed': True, 'phase': 'complete',
                        'revision': 'retained-start-v1'},
        'kctrl_tool_change': {'wrapped': list(TOOLS), 'missing': [], 'reloads': list(SLOTS)},
        'kctrl_purge_guard': guard_status(code),
    }
    for key, update in changes.items():
        value[key] = dict(value[key], **update)
    return value


class Machine:
    """Temporary tree, fake Klipper status, service and G-code, same paths as the module."""

    def __init__(self, tmp_path, monkeypatch, new_code_runs=True, after=None):
        self.m = m = load()
        self.target = tmp_path / 'extras/kctrl_purge_guard.py'
        self.target.parent.mkdir()
        self.original = b'installed guard retained-start-v1 c90de4c3\n'
        self.target.write_bytes(self.original)
        self.target.chmod(0o600)
        self.candidate = b'# candidate cold-push-guard-v1\n'
        protected = tmp_path / 'extras/kctrl_end.py'
        protected.write_bytes(b'retained cancel v4\n')
        self.protected = protected
        self.log = tmp_path / 'klippy.log'
        self.log.write_bytes(b'old line\n')
        self.pid = tmp_path / 'klippy.pid'
        self.pid.write_text('2210')
        for name, value in (('TARGET', str(self.target)), ('STAGE', str(self.target) + '.next'),
                            ('BACKUP', tmp_path / 'backups/cold-push-guard-v1'),
                            ('LOG', self.log), ('PIDFILE', self.pid)):
            monkeypatch.setattr(m, name, value)
        clock = [0.0]
        monkeypatch.setattr(m, 'time', types.SimpleNamespace(
            monotonic=lambda: clock[0], time=lambda: 1.0e9 + clock[0],
            sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds)))
        monkeypatch.setattr(m, 'compiles', lambda data: compile(data, 'candidate', 'exec'))
        self.actions = []
        self.scripts = []
        self.running = True
        self.new_code_runs = new_code_runs
        self.after = after or {}
        self.refuses = True
        self.status = status('before')
        self.hook = None
        monkeypatch.setattr(m, 'state', self.state)
        monkeypatch.setattr(m, 'service', self.service)
        monkeypatch.setattr(m, 'stop', self.stop)
        monkeypatch.setattr(m, 'klippy', self.klippy)
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

    def klippy(self, method, params):
        assert method == 'gcode/script'
        self.scripts.append(params['script'])
        for line in params['script'].split('\n'):
            if line in ('M82', 'M83'):
                self.status['gcode_move']['absolute_extrude'] = line == 'M82'
            elif line.startswith('G1 E'):
                guard = self.status['kctrl_purge_guard']
                if self.refuses and 'cold_revision' in guard:
                    guard['cold_refused'] += 1
                    guard['cold_last'] = 'poussee 0.50 mm a 24 C, cible 0 C'
                    raise RuntimeError(REFUSAL)
                self.status['toolhead']['position'][3] += 0.5
        return {}

    def service(self, action):
        self.actions.append(action)
        if action == 'stop':
            self.running = False
        elif action == 'start':
            self.running = True
            self.pid.write_text(str(int(self.pid.read_text()) + 1))
            new = self.target.read_bytes() == self.candidate and self.new_code_runs
            self.status = status('after' if new else 'before', print_stats={'state': 'standby'},
                                 kctrl_start={'phase': 'idle'}, kctrl_end={'phase': 'idle'})
            if new:
                self.status['kctrl_purge_guard'].update(self.after)

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
    assert machine.actions == [] and machine.scripts == []
    assert machine.target.read_bytes() == machine.original
    assert not machine.m.BACKUP.exists()


def test_la_pose_sauvegarde_remplace_redemarre_et_prouve_le_nouveau_crochet(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    mode = stat.S_IMODE(machine.target.stat().st_mode)
    result = machine.run('install')
    assert result['status'] == 'INSTALLED_IDLE_OK'
    assert result['cold_revision'] == 'cold-push-guard-v1'
    assert result['log']['tracebacks'] == 0
    assert machine.actions == ['stop', 'start'] and machine.scripts == []
    assert machine.target.read_bytes() == machine.candidate
    assert stat.S_IMODE(machine.target.stat().st_mode) == mode
    backup = machine.m.BACKUP / 'kctrl_purge_guard.py.before'
    assert backup.read_bytes() == machine.original
    assert json.loads((machine.m.BACKUP / 'receipt.json').read_text())['status'] == 'INSTALLED_IDLE_OK'
    validated = machine.run('validate')
    assert validated == {'status': 'VALIDATED_IDLE_OK', 'cold_revision': 'cold-push-guard-v1',
                         'cold_refused': 0, 'denied': 0}


@pytest.mark.parametrize('new_code_runs,after,error', [
    (False, None, 'cold_revision_changed'),
    (True, {'cold_installed': False}, 'cold_hook_missing'),
    (True, {'installed': False}, 'bin_guard_not_installed'),
])
def test_un_crochet_absent_apres_redemarrage_revient_a_l_original(
        tmp_path, monkeypatch, new_code_runs, after, error):
    machine = Machine(tmp_path, monkeypatch, new_code_runs=new_code_runs, after=after)
    result = machine.run('install')
    assert result['status'] == 'INSTALL_FAILED_ROLLED_BACK'
    assert error in result['error']
    assert machine.target.read_bytes() == machine.original
    assert machine.actions == ['stop', 'start', 'stop', 'start']
    assert 'cold_revision' not in machine.status['kctrl_purge_guard']


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
    # La fin du 31 octobre a justement echoue.
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
    ({'motion_report': {'live_extruder_velocity': 3.0}}, 'motion_active'),
    ({'toolhead': {'print_time': 93800.0}}, 'motion_queued'),
    ({'box': {'t_command': 'T1A'}}, 'cfs_command_present'),
    ({'box': {'state': 'disconnect'}}, 'cfs_not_ready'),
    ({'kctrl_end': {'phase': 'rewinding'}}, 'end_active'),
    ({'kctrl_end': {'pending': True}}, 'end_busy'),
    ({'kctrl_end': {'revision': 'end-rewind-confirm-v3'}}, 'end_revision_changed'),
    ({'kctrl_end': {'wrapped': ['END_PRINT']}}, 'end_wrappers_changed'),
    ({'kctrl_start': {'phase': 'material'}}, 'start_busy'),
    ({'kctrl_start': {'revision': 'other'}}, 'start_revision_changed'),
    ({'kctrl_tool_change': {'missing': ['T15']}}, 'tool_wrappers_changed'),
    ({'kctrl_tool_change': {'reloads': []}}, 'reloads_not_wrapped'),
    ({'kctrl_purge_guard': {'installed': False}}, 'bin_guard_not_installed'),
    ({'kctrl_purge_guard': {'revision': 'other'}}, 'bin_guard_not_installed'),
    ({'kctrl_purge_guard': {'bin_latched': True}}, 'bin_guard_not_at_rest'),
    ({'kctrl_purge_guard': {'minimum_z': 20.0}}, 'bin_guard_not_at_rest'),
    ({'kctrl_purge_guard': {'cold_revision': 'cold-push-guard-v1'}}, 'cold_guard_already_running'),
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
    assert 'cold_revision' not in machine.status['kctrl_purge_guard']


def test_le_retour_arriere_refuse_une_impression_en_cours(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.status['print_stats'] = {'state': 'printing'}
    with pytest.raises(AssertionError, match='job_busy'):
        machine.run('rollback')
    assert machine.target.read_bytes() == machine.candidate


def test_l_essai_pousse_une_fois_a_froid_et_prouve_le_refus(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    result = machine.run('probe')
    assert result['status'] == 'PROBE_REFUSED_OK'
    assert 'buse froide' in result['refused']
    assert result['cold_last'] == 'poussee 0.50 mm a 24 C, cible 0 C'
    assert machine.scripts == ['M83\nG1 E0.5 F60', 'M82']
    assert machine.status['gcode_move']['absolute_extrude'] is True
    assert machine.status['toolhead']['position'][3] == 12.5
    assert machine.actions == ['stop', 'start']
    # Le refus compte, la validation suivante reste verte.
    assert machine.run('validate')['cold_refused'] == 1


def test_l_essai_garde_un_mode_relatif_deja_en_place(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.status['gcode_move']['absolute_extrude'] = False
    assert machine.run('probe')['status'] == 'PROBE_REFUSED_OK'
    assert machine.scripts == ['M83\nG1 E0.5 F60']


@pytest.mark.parametrize('changes,error', [
    ({HEAD: {'filament_detected': True}}, 'head_not_empty'),
    ({'extruder': {'can_extrude': True, 'temperature': 185.0}}, 'nozzle_not_cold'),
    ({'extruder': {'target': 220.0}}, 'heater_target_set'),
    ({'print_stats': {'state': 'printing'}}, 'job_busy'),
    ({'kctrl_purge_guard': {'cold_installed': False}}, 'cold_hook_missing'),
])
def test_l_essai_ne_pousse_rien_hors_des_conditions_sures(tmp_path, monkeypatch, changes, error):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    for key, update in changes.items():
        machine.status[key].update(update)
    with pytest.raises(AssertionError, match=error):
        machine.run('probe')
    assert machine.scripts == []


def test_l_essai_refuse_l_ancien_code_ou_l_ancien_fichier(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, new_code_runs=False)
    machine.target.write_bytes(machine.candidate)
    machine.m.BACKUP.mkdir(parents=True)
    (machine.m.BACKUP / 'kctrl_purge_guard.py.before').write_bytes(machine.original)
    with pytest.raises(AssertionError, match='cold_hook_missing'):
        machine.run('probe')
    machine.target.write_bytes(machine.original)
    with pytest.raises(AssertionError, match='candidate_not_installed'):
        machine.run('probe')
    assert machine.scripts == []


def test_une_poussee_non_refusee_echoue_et_remet_le_mode(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.refuses = False
    with pytest.raises(AssertionError, match='push_not_refused'):
        machine.run('probe')
    assert machine.scripts == ['M83\nG1 E0.5 F60', 'M82']
    assert machine.status['gcode_move']['absolute_extrude'] is True


def test_le_journal_est_lu_depuis_l_arret_par_morceaux_bornes(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.log.write_bytes(b'x' * (3 << 20) + b'\nTraceback before\n')
    offset = machine.log.stat().st_size
    with machine.log.open('ab') as stream:
        stream.write(b'y' * ((1 << 20) - 20) + b' kctrl_purge_guard: cold push refused (1)\n')
    result = machine.m.log_lines(offset)
    assert result['tracebacks'] == 0
    assert result['lines'] == [('y' * 240 + ' kctrl_purge_guard: cold push refused (1)')[-240:]]
    machine.log.unlink()
    assert machine.m.log_lines(offset)['error']


def test_le_manifeste_epingle_le_candidat_l_installateur_et_la_chaine_d_impression():
    manifest = json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))
    root = PACKAGE.parents[2]
    packages = root / 'packages/k1-control-v1'
    assert hashlib.sha256((root / manifest['source']).read_bytes()).hexdigest() == manifest['sha256']
    assert hashlib.sha256((PACKAGE / 'remote_install.py').read_bytes()).hexdigest() \
        == manifest['installer_sha256']
    installed = packages / 'retained-start-v1/kctrl_purge_guard.py'
    assert manifest['before_sha256'] == hashlib.sha256(installed.read_bytes()).hexdigest() == \
        'c90de4c37c7a8762db1f5dd8509b8d5d7ae4959245c4c5ad33133cbff8573327'
    destination = manifest['destination']
    assert destination.endswith('/extras/kctrl_purge_guard.py')
    assert destination not in manifest['protected']
    # The pins read by cancel-retained-end-v4 stay, its own end file joins them.
    v4 = json.loads((packages / 'cancel-retained-end-v4/manifest.json').read_text(encoding='utf-8'))
    assert v4['protected'][destination] == manifest['before_sha256']
    for path, value in v4['protected'].items():
        if path != destination:
            assert manifest['protected'][path] == value
    assert manifest['protected']['/usr/share/klipper/klippy/extras/kctrl_end.py'] == v4['sha256']
    assert len(manifest['protected']) == 23
    assert not any(manifest['effects'][key] for key in ('heating', 'motion', 'filament',
                                                        'config_change'))
