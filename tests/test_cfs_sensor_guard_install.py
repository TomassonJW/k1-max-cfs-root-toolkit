"""Add, refuse and roll back the CFS sensor guard entirely in a temporary tree.

The printer is replaced by a status dictionary, the service by a log of
actions, the files by temporary copies (ADR-077, document 105).
"""
import base64
import configparser
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import stat
import types

import pytest

import test_kctrl_sensor_guard_v1 as guard_test

PACKAGE = Path(__file__).resolve().parents[1] / 'packages/k1-control-v1/cfs-sensor-guard-v1'
TOOLS = ['T%d' % index for index in range(16)]
SLOTS = ['T%s%s' % (box, slot) for box in '1234' for slot in 'ABCD']
WRAPPED = ['CANCEL_PRINT', 'END_PRINT', 'START_PRINT']
GUARD = {'revision': 'retained-start-v1', 'installed': True, 'bin_latched': False,
         'minimum_z': 30.0, 'denied': 0, 'last_error': '',
         'cold_revision': 'cold-push-guard-v1', 'cold_installed': True, 'cold_refused': 0,
         'cold_last': ''}
BASE = (b'[kctrl_end]\nenabled: True\ntimeout: 180\ncut_proof_timeout: 5\n'
        b'rewind_settle_timeout: 20\nboxes: 2\n')
SECTION = b'# comment\n[kctrl_sensor_guard]\nenabled: True\nboxes: 2\n'
MODULE = b'# candidate cfs-sensor-guard-v1\n'


def load():
    spec = importlib.util.spec_from_file_location('cfs_sensor_guard_install',
                                                  PACKAGE / 'remote_install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def guard_status(**changes):
    value = {'enabled': True, 'revision': 'cfs-sensor-guard-v1', 'installed': True,
             'hook': 'inside_cold_guard', 'hooked': True, 'blind': None, 'job': 0,
             'episodes': {}, 'closed': {}, 'marked': None, 'cut': False, 'recuts': 0,
             'auto_refill_restore_pending': False, 'end_armed': False, 'end_window': False,
             'end_window_left': None, 'end_level': None, 'end_closed_by': None,
             'tripped': False, 'trip': None, 'failure': '', 'route': None,
             'route_reason': 'no_route', 'tap_seen': 0, 'tap_dropped': 0}
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
        'box': {'enable': 1, 'state': 'connect', 't_command': 'T1', 'filament': 1,
                'auto_refill': 1,
                'T1': {'state': 'connect', 'filament': 'None', 'sn': 'SERIAL-T1'},
                'T2': {'state': 'connect', 'filament': 'None', 'uuid': 'SERIAL-T2'}},
        'filament_switch_sensor filament_sensor_2': {'filament_detected': False},
        'kctrl_end': {'enabled': True, 'phase': 'complete', 'pending': False,
                      'wrapped': list(WRAPPED), 'revision': 'end-no-stock-flush-v5',
                      'auto_refill_restore_pending': False},
        'kctrl_start': {'enabled': True, 'installed': True, 'phase': 'complete',
                        'revision': 'retained-start-v1'},
        'kctrl_tool_change': {'wrapped': list(TOOLS), 'missing': [], 'reloads': list(SLOTS)},
        'kctrl_print_gate': {'pending': False},
        'kctrl_purge_guard': dict(GUARD),
        'kctrl_sensor_guard': {},  # Klipper's answer for an object it has not loaded
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
        self.module = extras / 'kctrl_sensor_guard.py'
        self.cache = extras / '__pycache__'
        self.cache.mkdir()
        self.config = tmp_path / 'k1-control-owned-end-candidate.cfg'
        self.config.write_bytes(BASE)
        self.config.chmod(0o644)
        self.protected = extras / 'kctrl_purge_guard.py'
        self.protected.write_bytes(b'bin guard with the cold push refusal\n')
        self.log = tmp_path / 'klippy.log'
        self.log.write_bytes(b'old line\n')
        self.pid = tmp_path / 'klippy.pid'
        self.pid.write_text('2210')
        for name, value in (('MODULE', str(self.module)), ('BYTECODE', str(self.cache)),
                            ('CONFIG', str(self.config)),
                            ('BACKUP', tmp_path / 'backups/cfs-sensor-guard-v1'),
                            ('LOG', self.log), ('PIDFILE', self.pid)):
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
            self.writes.append((Path(path).name, self.module.exists()))
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
            'before_sha256': None, 'surveyed': surveyed,
            'config': {'path': str(self.config), 'section_sha256': sha(SECTION),
                       'before_sha256': sha(BASE), 'sha256': sha(BASE + b'\n' + SECTION)},
            'protected': {str(self.protected): sha(self.protected.read_bytes())},
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
            return
        if action != 'start':
            return
        self.running = True
        self.pid.write_text(str(int(self.pid.read_text()) + 1))
        self.status = status(print_stats={'state': 'standby'}, kctrl_start={'phase': 'idle'},
                             kctrl_end={'phase': 'idle'}, box={'t_command': ''})
        section = b'[kctrl_sensor_guard]' in self.config.read_bytes()
        if section and not self.module.exists():
            self.status['webhooks'] = {'state': 'error'}
        elif section:
            (self.cache / 'kctrl_sensor_guard.cpython-38.pyc').write_bytes(b'compiled')
            guard = guard_status()
            if self.loaded:
                self.loaded(guard)
            self.status['kctrl_sensor_guard'] = guard
            with self.log.open('ab') as stream:
                stream.write(b'[INFO] kctrl_sensor_guard: watching\n')

    def stop(self):
        pid = self.pid.read_text()
        self.service('stop')
        return pid

    def run(self, mode, payload=None, section=None):
        return self.m.run({'mode': mode, 'manifest': self.manifest,
                           'payload': base64.b64encode(payload or MODULE).decode(),
                           'section': base64.b64encode(section or SECTION).decode()})

    def untouched(self):
        assert self.config.read_bytes() == BASE
        assert not self.module.exists()
        assert list(self.cache.iterdir()) == []


def test_le_releve_lit_les_epingles_sans_rien_changer(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    result = machine.run('survey')
    assert result['status'] == 'SURVEY_OK' and result['drift'] == []
    found = result['protected'][str(machine.protected)]
    assert found['sha256'] == machine.manifest['protected'][str(machine.protected)]
    assert result['module'] == {'sha256': None, 'mode': None}
    assert result['bytecode'] == [] and result['stage'] is False and result['backup'] is False
    assert result['config']['sha256'] == result['config']['expected'] == sha(BASE)
    assert result['config']['section'] is False
    assert result['config']['sections'] == ['[kctrl_end]']
    assert result['rest']['t_command'] == 'T1'
    assert machine.actions == [] and not machine.m.BACKUP.exists()
    machine.untouched()


def test_le_releve_signale_un_fichier_qui_a_bouge(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    machine.protected.write_bytes(b'changed elsewhere\n')
    assert machine.run('survey')['drift'] == [str(machine.protected)]


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
    assert result['status'] == 'PREFLIGHT_OK' and result['protected'] == 1
    assert machine.actions == []
    machine.untouched()
    assert not machine.m.BACKUP.exists()


def test_la_pose_ajoute_module_et_section_redemarre_et_prouve_la_garde(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    result = machine.run('install')
    assert result['status'] == 'INSTALLED_IDLE_OK'
    assert result['revision'] == 'cfs-sensor-guard-v1'
    assert result['hook'] == 'inside_cold_guard' and result['route_reason'] == 'no_route'
    assert result['log']['lines'][-1].endswith('watching')
    assert result['log']['tracebacks'] == 0
    assert machine.actions == ['stop', 'start']
    assert machine.module.read_bytes() == MODULE
    assert machine.config.read_bytes() == BASE + b'\n' + SECTION
    assert os.name == 'nt' or stat.S_IMODE(machine.module.stat().st_mode) == 0o644
    backup = machine.m.BACKUP
    assert (backup / 'config.before').read_bytes() == BASE
    assert json.loads((backup / 'receipt.json').read_text())['status'] == 'INSTALLED_IDLE_OK'
    # Le module d'abord : une section sans son module arrete Klipper.
    assert machine.writes == [('kctrl_sensor_guard.py', False),
                              ('k1-control-owned-end-candidate.cfg', True)]
    validated = machine.run('validate')
    assert validated['status'] == 'VALIDATED_IDLE_OK'
    assert validated['t_command'] == '' and validated['tripped'] is False


def test_la_validation_accepte_la_memoire_d_une_impression_finie(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.status['box']['t_command'] = 'T3'
    machine.status['kctrl_sensor_guard'].update(job=4, end_armed=True)
    assert machine.run('validate')['status'] == 'VALIDATED_IDLE_OK'


def test_la_validation_rapporte_un_declenchement_sans_le_cacher(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.status['kctrl_sensor_guard'].update(tripped=True, job=2, marked='T1A')
    result = machine.run('validate')
    assert result['tripped'] is True and result['marked'] == 'T1A'


def test_les_identifiants_des_cfs_ne_sortent_jamais_de_la_machine(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    assert 'SERIAL' not in json.dumps(machine.run('survey'))
    machine.manifest['surveyed'] = True
    assert 'SERIAL' not in json.dumps(machine.run('preflight'))
    machine.status['box']['T1']['state'] = 'connect'
    assert 'SERIAL' not in json.dumps(machine.run('install'))
    assert 'SERIAL' not in json.dumps(machine.run('validate'))


@pytest.mark.parametrize('command', ['', 'T0', 'T1', 'T15', 'T1A', 'T1D', 'T4A'])
def test_la_memoire_du_dernier_outil_n_empeche_pas_la_pose(tmp_path, monkeypatch, command):
    # Document 105 : ce champ garde le dernier outil de la derniere impression.
    machine = Machine(tmp_path, monkeypatch)
    machine.status['box']['t_command'] = command
    assert machine.run('preflight')['rest']['t_command'] == command
    assert machine.run('install')['status'] == 'INSTALLED_IDLE_OK'


@pytest.mark.parametrize('command', ['T16', 'T5A', 'T1E', 'G28', 'BOX_LOAD', ' T1', None, 1])
def test_une_valeur_inconnue_du_dernier_outil_ferme_la_pose(tmp_path, monkeypatch, command):
    machine = Machine(tmp_path, monkeypatch)
    machine.status['box']['t_command'] = command
    with pytest.raises(AssertionError, match='cfs_command_unknown'):
        machine.run('install')
    assert machine.actions == []
    machine.untouched()


def test_le_dernier_outil_qui_change_entre_deux_lectures_ferme_la_pose(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    calls = []

    def command_arrives():
        calls.append(1)
        if len(calls) == 2:
            machine.status['box']['t_command'] = 'T2'
    machine.hook = command_arrives
    with pytest.raises(AssertionError, match='cfs_command_changed'):
        machine.run('install')
    assert machine.actions == []
    machine.untouched()


@pytest.mark.parametrize('changes,error', [
    ({'print_stats': {'state': 'printing'}}, 'job_busy'),
    ({'box': {'t_command': 'T2'}}, 'cfs_command_changed'),
    ({'kctrl_end': {'pending': True}}, 'end_busy'),
], ids=['impression', 'outil', 'fin'])
def test_ce_qui_arrive_juste_avant_l_arret_annule_la_pose_sans_rien_changer(
        tmp_path, monkeypatch, changes, error):
    machine = Machine(tmp_path, monkeypatch)
    calls = []

    def something_starts():
        calls.append(1)
        if len(calls) == 3:  # apres les deux lectures stables du preflight
            for key, update in changes.items():
                machine.status[key].update(update)
    machine.hook = something_starts
    assert machine.run('install') == {'status': 'NOT_INSTALLED_NOTHING_CHANGED', 'error': error}
    assert machine.actions == []
    machine.untouched()
    assert not machine.m.BACKUP.exists()


@pytest.mark.parametrize('end', ['idle', 'complete', 'failed'])
def test_une_fin_au_repos_meme_echouee_permet_la_pose(tmp_path, monkeypatch, end):
    machine = Machine(tmp_path, monkeypatch)
    machine.status['kctrl_end'].update(phase=end)
    assert machine.run('install')['status'] == 'INSTALLED_IDLE_OK'


@pytest.mark.parametrize('filament', [0, 1, None, 'T1A'])
def test_box_filament_est_rapporte_jamais_utilise(tmp_path, monkeypatch, filament):
    machine = Machine(tmp_path, monkeypatch)
    machine.status['box']['filament'] = filament
    assert machine.run('preflight')['rest']['box_filament'] == filament


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
    ({'box': {'auto_refill': 2}}, 'auto_refill_unknown'),
    ({'box': {'auto_refill': True}}, 'auto_refill_unknown'),
    ({'kctrl_end': {'phase': 'rewinding'}}, 'end_active'),
    ({'kctrl_end': {'phase': 'finalizing'}}, 'end_active'),
    ({'kctrl_end': {'pending': True}}, 'end_busy'),
    ({'kctrl_end': {'revision': 'cancel-retained-v4'}}, 'end_revision_changed'),
    ({'kctrl_end': {'auto_refill_restore_pending': True}}, 'end_refill_pending'),
    ({'kctrl_end': {'wrapped': ['END_PRINT']}}, 'end_wrappers_changed'),
    ({'kctrl_start': {'installed': False}}, 'start_not_installed'),
    ({'kctrl_start': {'phase': 'material'}}, 'start_busy'),
    ({'kctrl_start': {'revision': 'other'}}, 'start_revision_changed'),
    ({'kctrl_tool_change': {'missing': ['T15']}}, 'tool_wrappers_changed'),
    ({'kctrl_tool_change': {'reloads': []}}, 'reloads_not_wrapped'),
    ({'kctrl_print_gate': {'pending': True}}, 'start_waiting_for_spools'),
    ({'kctrl_purge_guard': {'installed': False}}, 'bin_guard_not_installed'),
    ({'kctrl_purge_guard': {'bin_latched': True}}, 'bin_guard_not_at_rest'),
    ({'kctrl_purge_guard': {'minimum_z': 20.0}}, 'bin_guard_not_at_rest'),
    ({'kctrl_purge_guard': {'cold_installed': False}}, 'cold_guard_not_installed'),
    ({'kctrl_purge_guard': {'cold_revision': 'other'}}, 'cold_guard_not_installed'),
])
def test_la_pose_refuse_une_machine_qui_n_est_pas_au_repos(tmp_path, monkeypatch, changes, error):
    machine = Machine(tmp_path, monkeypatch)
    machine.status = status(**changes)
    with pytest.raises(AssertionError, match=error):
        machine.run('install')
    assert machine.actions == []
    machine.untouched()
    assert not machine.m.BACKUP.exists()


def test_une_garde_deja_chargee_refuse_la_pose(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.status['kctrl_sensor_guard'] = guard_status()
    with pytest.raises(AssertionError, match='guard_already_running'):
        machine.run('preflight')


@pytest.mark.parametrize('change,error', [
    ({'enabled': False}, 'guard_not_installed'),
    ({'installed': False}, 'guard_not_installed'),
    ({'revision': 'other'}, 'guard_revision_changed'),
    ({'hook': 'direct'}, 'guard_not_hooked'),
    ({'hooked': False}, 'guard_not_hooked'),
    ({'failure': 'tick_failed'}, 'guard_failed'),
    ({'blind': 'log_level'}, 'guard_cannot_hear_cfs'),
    ({'status_error': 'boom'}, 'guard_status_error'),
    ({'job': 1}, 'guard_not_fresh'),
    ({'episodes': {'T1A': {}}}, 'guard_not_fresh'),
    ({'marked': 'T1A'}, 'guard_not_fresh'),
    ({'tripped': True}, 'guard_not_fresh'),
    ({'end_armed': True}, 'guard_not_fresh'),
    ({'end_window': True}, 'guard_not_fresh'),
    ({'auto_refill_restore_pending': True}, 'guard_not_fresh'),
    ({'route_reason': ''}, 'guard_not_ticking'),
])
def test_une_garde_qui_ne_tourne_pas_comme_prevu_revient_a_l_original(
        tmp_path, monkeypatch, change, error):
    machine = Machine(tmp_path, monkeypatch, loaded=lambda guard: guard.update(change))
    result = machine.run('install')
    assert result['status'] == 'INSTALL_FAILED_ROLLED_BACK'
    assert error in result['error']
    machine.untouched()
    assert machine.actions == ['stop', 'start', 'stop', 'start']
    assert machine.status['kctrl_sensor_guard'] == {}


def test_une_section_que_klipper_n_a_pas_chargee_revient_a_l_original(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, loaded=lambda guard: guard.clear())
    result = machine.run('install')
    assert result['status'] == 'INSTALL_FAILED_ROLLED_BACK'
    assert 'guard_not_loaded' in result['error']
    machine.untouched()


def test_klipper_qui_refuse_de_demarrer_revient_a_l_original(tmp_path, monkeypatch):
    def refuses(guard):
        machine.status['webhooks'] = {'state': 'error'}
    machine = Machine(tmp_path, monkeypatch, loaded=refuses)
    result = machine.run('install')
    assert result['status'] == 'INSTALL_FAILED_ROLLED_BACK'
    assert 'klipper_not_ready' in result['error']
    machine.untouched()


def test_le_retour_d_une_pose_ratee_remet_la_config_avant_de_retirer_le_module(
        tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, loaded=lambda guard: guard.update(failure='x'))
    machine.run('install')
    assert machine.writes[-1] == ('k1-control-owned-end-candidate.cfg', True)


def test_un_fichier_protege_modifie_bloque_tout(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.protected.write_bytes(b'changed elsewhere\n')
    with pytest.raises(RuntimeError, match='protected_file_drift'):
        machine.run('preflight')


def test_une_charge_alteree_est_refusee_avant_tout(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    with pytest.raises(AssertionError, match='payload_hash_changed'):
        machine.run('install', payload=b'something else\n')
    with pytest.raises(AssertionError, match='section_hash_changed'):
        machine.run('install', section=b'[other]\n')
    assert machine.actions == []


@pytest.mark.parametrize('prepare,error', [
    (lambda machine: machine.config.write_bytes(b'foreign version\n'), 'config_not_at_baseline'),
    (lambda machine: machine.module.write_bytes(b'old guard\n'), 'module_already_present'),
    (lambda machine: (machine.cache / 'kctrl_sensor_guard.cpython-38.pyc').write_bytes(b'x'),
     'module_already_present'),
    (lambda machine: machine.m.BACKUP.mkdir(parents=True), 'backup_already_exists'),
    (lambda machine: Path(str(machine.config) + machine.m.STAGE_SUFFIX).write_bytes(b'x'),
     'stale_stage_file'),
], ids=['config', 'module', 'pyc', 'sauvegarde', 'etape'])
def test_un_etat_de_depart_different_ferme_la_pose(tmp_path, monkeypatch, prepare, error):
    machine = Machine(tmp_path, monkeypatch)
    prepare(machine)
    with pytest.raises(AssertionError, match=error):
        machine.run('install')
    assert machine.actions == []


def test_une_pose_deja_faite_ne_se_rejoue_pas(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    with pytest.raises(AssertionError, match='module_already_present'):
        machine.run('install')


def test_la_section_ne_se_pose_jamais_deux_fois():
    m = load()
    with pytest.raises(AssertionError, match='section_already_present'):
        m.candidate(BASE + b'\n[kctrl_sensor_guard]\nenabled: False\n', SECTION)
    with pytest.raises(AssertionError, match='end_section_missing'):
        m.candidate(b'[other]\n', SECTION)
    with pytest.raises(AssertionError, match='config_without_final_newline'):
        m.candidate(BASE[:-1], SECTION)


def test_le_retour_arriere_remet_l_original_exact(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.config.chmod(0o640)
    machine.run('install')
    assert list(machine.cache.iterdir())
    result = machine.run('rollback')
    assert result['status'] == 'ROLLED_BACK'
    machine.untouched()
    assert machine.actions == ['stop', 'start', 'stop', 'start']
    assert machine.status['kctrl_sensor_guard'] == {}
    # La configuration d'abord : le module existe encore quand elle revient.
    assert machine.writes[-1] == ('k1-control-owned-end-candidate.cfg', True)
    assert os.name == 'nt' or stat.S_IMODE(machine.config.stat().st_mode) == 0o640


def test_le_retour_arriere_refuse_une_impression_en_cours(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.status['print_stats'] = {'state': 'printing'}
    with pytest.raises(AssertionError, match='job_busy'):
        machine.run('rollback')
    assert machine.module.read_bytes() == MODULE
    assert machine.actions == ['stop', 'start']


def test_le_retour_arriere_exige_encore_le_refus_de_poussee_a_froid(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.status['kctrl_purge_guard'].pop('cold_revision')
    with pytest.raises(AssertionError, match='cold_guard_not_installed'):
        machine.run('rollback')
    assert machine.module.read_bytes() == MODULE


@pytest.mark.parametrize('breakage,error', [
    (lambda machine: (machine.m.BACKUP / 'config.before').write_bytes(b'damaged'), 'backup_corrupt'),
    (lambda machine: machine.config.write_bytes(b'someone else\n'), 'rollback_foreign_file'),
    (lambda machine: machine.module.write_bytes(b'someone else\n'), 'rollback_foreign_file'),
], ids=['sauvegarde', 'config', 'module'])
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
        stream.write(b'y' * ((1 << 20) - 20) + b' kctrl_sensor_guard: watching\n')
    result = machine.m.log_lines(offset)
    assert result['tracebacks'] == 0
    assert result['lines'] == [('y' * 240 + ' kctrl_sensor_guard: watching')[-240:]]
    machine.log.unlink()
    assert machine.m.log_lines(offset)['error']


def test_les_champs_lus_sont_ceux_du_vrai_module_dans_l_ordre_de_chargement_reel():
    # La section vient apres [kctrl_end] et avant [kctrl_purge_guard].
    m = load()
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    root.setLevel(logging.INFO)  # as Klipper does; pytest leaves WARNING
    try:
        world = guard_test.started(order=('end', 'guard', 'cold'))
        world.run('10:00:01')
        guard = json.loads(json.dumps(world.guard.get_status()))
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)
    assert set(guard) == set(guard_status())
    m.guard_fresh(guard)
    m.guard_ticking(guard)
    assert guard['route_reason'] == guard_status()['route_reason']


def manifest():
    return json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))


def test_le_manifeste_epingle_les_candidats_et_l_installateur():
    pins = manifest()
    root = PACKAGE.parents[2]
    assert sha((root / pins['source']).read_bytes()) == pins['sha256']
    assert sha((root / pins['config']['section']).read_bytes()) == pins['config']['section_sha256']
    assert sha((PACKAGE / 'remote_install.py').read_bytes()) == pins['installer_sha256']
    assert pins['destination'] == '/usr/share/klipper/klippy/extras/kctrl_sensor_guard.py'
    assert pins['before_sha256'] is None
    assert pins['surveyed'] is True and pins['surveyed_on'] == '2026-11-05'
    effects = pins['effects']
    assert effects['klipper_restart_idle_only'] is True and effects['config_change'] is True
    assert not any(effects[key] for key in ('heating', 'motion', 'filament', 'printer_cfg_change'))


def test_les_epingles_sont_celles_de_v5_le_fichier_de_fin_echange_contre_son_code():
    pins = manifest()
    root = PACKAGE.parents[2]
    v5 = json.loads((root / 'packages/k1-control-v1/end-no-stock-flush-v5/manifest.json')
                    .read_text(encoding='utf-8'))
    expected = dict(v5['protected'])
    del expected[pins['config']['path']]
    expected[v5['destination']] = v5['sha256']
    assert pins['protected'] == expected and len(expected) == 23
    assert pins['destination'] not in expected and pins['config']['path'] not in expected


def test_la_config_apres_pose_est_la_config_en_service_plus_la_section():
    pins = manifest()
    root = PACKAGE.parents[2]
    base = (root / 'packages/k1-control-v1/end-separated-v1'
            / 'k1-control-owned-end-candidate.cfg').read_bytes()
    assert sha(base) == pins['config']['before_sha256']
    edited = load().candidate(base, (PACKAGE / 'sections.cfg').read_bytes())
    assert sha(edited) == pins['config']['sha256']
    parser = configparser.ConfigParser()
    parser.read_string(edited.decode())
    assert parser.sections() == ['kctrl_end', 'kctrl_sensor_guard']
    assert parser['kctrl_sensor_guard'].getboolean('enabled') is True
    assert dict(parser['kctrl_end']) == {'enabled': 'True', 'timeout': '180',
                                         'cut_proof_timeout': '5', 'rewind_settle_timeout': '20',
                                         'boxes': '2'}


@pytest.mark.parametrize('package', ['end-no-stock-flush-v5', 'cold-push-guard-v1',
                                     'resume-reload-guard-v1'])
def test_les_paquets_dessous_refusent_leur_retour_tant_que_la_garde_est_posee(package):
    # ADR-077 : la garde repart d'abord. Leurs installateurs epinglent la config d'avant.
    pins = manifest()['config']
    root = PACKAGE.parents[2]
    other = json.loads((root / 'packages/k1-control-v1' / package / 'manifest.json')
                       .read_text(encoding='utf-8'))
    assert other['protected'][pins['path']] == pins['before_sha256'] != pins['sha256']
