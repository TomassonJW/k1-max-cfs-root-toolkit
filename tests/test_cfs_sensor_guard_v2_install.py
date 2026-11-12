"""Replace the CFS sensor guard V1 by V2, refuse and roll back, in a temporary tree.

The printer is replaced by a status dictionary, the service by a log of
actions, the files by temporary copies (ADR-078, document 107).
"""
import base64
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import stat
import types

import pytest

import test_kctrl_sensor_guard_v2 as guard_test

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages/k1-control-v1/cfs-sensor-guard-v2'
V1_PACKAGE = ROOT / 'packages/k1-control-v1/cfs-sensor-guard-v1'
TOOLS = ['T%d' % index for index in range(16)]
SLOTS = ['T%s%s' % (box, slot) for box in '1234' for slot in 'ABCD']
WRAPPED = ['CANCEL_PRINT', 'END_PRINT', 'START_PRINT']
GUARD = {'revision': 'retained-start-v1', 'installed': True, 'bin_latched': False,
         'minimum_z': 30.0, 'denied': 0, 'last_error': '',
         'cold_revision': 'cold-push-guard-v1', 'cold_installed': True, 'cold_refused': 0,
         'cold_last': ''}
CONFIG = b'[kctrl_end]\nenabled: True\n\n[kctrl_sensor_guard]\nenabled: True\nboxes: 2\n'
V1 = b'# installed cfs-sensor-guard-v1\n'
MODULE = b'# candidate cfs-sensor-guard-v2\n'


def load():
    spec = importlib.util.spec_from_file_location('cfs_sensor_guard_v2_install',
                                                  PACKAGE / 'remote_install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def common(**changes):
    value = {'enabled': True, 'installed': True, 'hook': 'inside_cold_guard', 'hooked': True,
             'blind': None, 'job': 0, 'episodes': {}, 'closed': {}, 'marked': None,
             'end_armed': False, 'end_window': False, 'end_window_left': None,
             'end_level': None, 'end_closed_by': None, 'tripped': False, 'trip': None,
             'failure': '', 'route': None, 'route_reason': 'no_route', 'tap_seen': 0,
             'tap_dropped': 0}
    value.update(changes)
    return value


def v1_status(**changes):
    """V1 as the survey of 12 November found it, after the print of the night."""
    value = common(revision='cfs-sensor-guard-v1', job=3, cut='confirmed', recuts=0,
                   auto_refill_restore_pending=True,
                   marked={'slot': 'T1B', 'seconds': 180.1, 'printed': 533.8,
                           'reasons': ['filament_err', 'named', 'tension']})
    value.update(changes)
    return value


def v2_status(**changes):
    value = common(revision='cfs-sensor-guard-v2', keep_auto_refill=True, kept=0, keep=None,
                   paused=False, false_end=None, idle_told=None, stock_purge=None)
    value.update(changes)
    return value


def status(**changes):
    value = {
        'webhooks': {'state': 'ready'},
        'print_stats': {'state': 'standby'},
        'virtual_sdcard': {'is_active': False},
        'pause_resume': {'is_paused': False},
        'idle_timeout': {'state': 'Idle'},
        'extruder': {'target': 0.0},
        'heater_bed': {'target': 0.0},
        'toolhead': {'print_time': 93138.4, 'estimated_print_time': 93739.5},
        'motion_report': {'live_velocity': 5.68e-14, 'live_extruder_velocity': 0.0},
        'box': {'enable': 1, 'state': 'connect', 't_command': 'T0', 'filament': 0,
                'auto_refill': 0,
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
        'kctrl_sensor_guard': v1_status(),
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
        self.module.write_bytes(V1)
        self.module.chmod(0o644)
        self.cache = extras / '__pycache__'
        self.cache.mkdir()
        self.config = tmp_path / 'k1-control-owned-end-candidate.cfg'
        self.config.write_bytes(CONFIG)
        self.protected = extras / 'kctrl_purge_guard.py'
        self.protected.write_bytes(b'bin guard with the cold push refusal\n')
        self.log = tmp_path / 'klippy.log'
        self.log.write_bytes(b'old line\n')
        self.pid = tmp_path / 'klippy.pid'
        self.pid.write_text('2210')
        for name, value in (('MODULE', str(self.module)), ('BYTECODE', str(self.cache)),
                            ('CONFIG', str(self.config)),
                            ('BACKUP', tmp_path / 'backups/cfs-sensor-guard-v2'),
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
            'before_sha256': sha(V1), 'surveyed': surveyed,
            'protected': {str(self.protected): sha(self.protected.read_bytes()),
                          str(self.config): sha(CONFIG)},
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
        self.status = status(box={'t_command': ''})
        code = self.module.read_bytes()
        if code == MODULE:
            guard = v2_status()
            if self.loaded:
                self.loaded(guard)
        elif code == V1:
            guard = v1_status(job=0, marked=None, cut=None, auto_refill_restore_pending=False)
        else:
            self.status['webhooks'] = {'state': 'error'}
            return
        (self.cache / 'kctrl_sensor_guard.cpython-38.pyc').write_bytes(code)
        self.status['kctrl_sensor_guard'] = guard
        with self.log.open('ab') as stream:
            stream.write(b'[INFO] kctrl_sensor_guard: watching\n')

    def stop(self):
        pid = self.pid.read_text()
        self.service('stop')
        return pid

    def run(self, mode, payload=None):
        return self.m.run({'mode': mode, 'manifest': self.manifest,
                           'payload': base64.b64encode(payload or MODULE).decode()})

    def at_v1(self):
        assert self.module.read_bytes() == V1
        assert self.config.read_bytes() == CONFIG
        assert os.name == 'nt' or stat.S_IMODE(self.module.stat().st_mode) == 0o644


def test_le_releve_lit_les_epingles_sans_rien_changer(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    result = machine.run('survey')
    assert result['status'] == 'SURVEY_OK' and result['drift'] == []
    assert result['module']['sha256'] == result['module']['expected'] == sha(V1)
    assert result['config']['sha256'] == sha(CONFIG) and result['config']['section'] is True
    assert result['bytecode'] == [] and result['stage'] is False and result['backup'] is False
    rest = result['rest']
    assert rest['guard_revision'] == 'cfs-sensor-guard-v1' and rest['auto_refill'] == 0
    assert rest['guard_restore_pending'] is True and rest['guard_marked']['slot'] == 'T1B'
    assert machine.actions == [] and not machine.m.BACKUP.exists()
    machine.at_v1()


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
    assert result['status'] == 'PREFLIGHT_OK' and result['protected'] == 2
    assert machine.actions == [] and machine.writes == []
    machine.at_v1()
    assert not machine.m.BACKUP.exists()


def test_la_pose_remplace_le_seul_module_redemarre_et_prouve_v2(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.module.chmod(0o640)
    (machine.cache / 'kctrl_sensor_guard.cpython-38.pyc').write_bytes(V1)
    result = machine.run('install')
    assert result['status'] == 'INSTALLED_IDLE_OK'
    assert result['revision'] == 'cfs-sensor-guard-v2' and result['keep_auto_refill'] is True
    assert result['hook'] == 'inside_cold_guard' and result['route_reason'] == 'no_route'
    assert result['log']['lines'][-1].endswith('watching') and result['log']['tracebacks'] == 0
    # The refill read 0 at rest: reported, V2 puts it back at the next START_PRINT.
    assert result['rest']['auto_refill'] == 0
    assert machine.actions == ['stop', 'start']
    assert machine.module.read_bytes() == MODULE and machine.config.read_bytes() == CONFIG
    assert os.name == 'nt' or stat.S_IMODE(machine.module.stat().st_mode) == 0o640
    assert machine.writes == [('kctrl_sensor_guard.py', MODULE)]
    backup = machine.m.BACKUP
    assert (backup / 'module.before').read_bytes() == V1
    assert json.loads((backup / 'mode.json').read_text())['mode'] == oct(0o640) or os.name == 'nt'
    assert json.loads((backup / 'receipt.json').read_text())['status'] == 'INSTALLED_IDLE_OK'
    # The V1 bytecode went with the V1 code; the cache holds what V2 compiled.
    assert [p.read_bytes() for p in machine.cache.iterdir()] == [MODULE]
    validated = machine.run('validate')
    assert validated['status'] == 'VALIDATED_IDLE_OK'
    assert validated['revision'] == 'cfs-sensor-guard-v2' and validated['kept'] == 0


def test_la_validation_accepte_la_memoire_d_une_impression_finie(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.status['box']['t_command'] = 'T1B'
    machine.status['kctrl_sensor_guard'].update(
        job=4, end_armed=True, kept=1, keep='kept', marked={'slot': 'T1B'},
        false_end={'slot': 'T1B', 'at': 1.0, 'paused_at': 1.0},
        stock_purge={'seconds': 1536.9, 'running': False, 'paused': True})
    result = machine.run('validate')
    assert result['status'] == 'VALIDATED_IDLE_OK' and result['kept'] == 1
    assert result['false_end']['slot'] == 'T1B' and result['stock_purge']['paused'] is True


def test_la_validation_refuse_v1_encore_en_service(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.status['kctrl_sensor_guard'] = v1_status()
    with pytest.raises(AssertionError, match='guard_revision_changed'):
        machine.run('validate')


def test_les_identifiants_des_cfs_ne_sortent_jamais_de_la_machine(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch, surveyed=False)
    assert 'SERIAL' not in json.dumps(machine.run('survey'))
    machine.manifest['surveyed'] = True
    assert 'SERIAL' not in json.dumps(machine.run('preflight'))
    assert 'SERIAL' not in json.dumps(machine.run('install'))
    assert 'SERIAL' not in json.dumps(machine.run('validate'))
    assert 'SERIAL' not in json.dumps(machine.run('rollback'))


@pytest.mark.parametrize('command', ['', 'T0', 'T1', 'T15', 'T1A', 'T1D', 'T4A'])
def test_la_memoire_du_dernier_outil_n_empeche_pas_la_pose(tmp_path, monkeypatch, command):
    machine = Machine(tmp_path, monkeypatch)
    machine.status['box']['t_command'] = command
    assert machine.run('preflight')['rest']['t_command'] == command
    assert machine.run('install')['status'] == 'INSTALLED_IDLE_OK'


@pytest.mark.parametrize('command', ['T16', 'T5A', 'T1E', 'G28', ' T1', None, 1])
def test_une_valeur_inconnue_du_dernier_outil_ferme_la_pose(tmp_path, monkeypatch, command):
    machine = Machine(tmp_path, monkeypatch)
    machine.status['box']['t_command'] = command
    with pytest.raises(AssertionError, match='cfs_command_unknown'):
        machine.run('install')
    assert machine.actions == []
    machine.at_v1()


@pytest.mark.parametrize('changes,error', [
    ({'print_stats': {'state': 'printing'}}, 'job_busy'),
    ({'box': {'t_command': 'T2'}}, 'cfs_command_changed'),
    ({'kctrl_end': {'pending': True}}, 'end_busy'),
    ({'pause_resume': {'is_paused': True}}, 'paused'),
], ids=['impression', 'outil', 'fin', 'pause'])
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
    machine.at_v1()
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
    ({'box': {'auto_refill': True}}, 'auto_refill_unknown'),
    ({'kctrl_end': {'phase': 'rewinding'}}, 'end_active'),
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
    ({'kctrl_purge_guard': {'cold_installed': False}}, 'cold_guard_not_installed'),
    ({'kctrl_sensor_guard': {'revision': 'cfs-sensor-guard-v2'}}, 'guard_revision_changed'),
    ({'kctrl_sensor_guard': {'failure': 'tick_failed'}}, 'guard_failed'),
    ({'kctrl_sensor_guard': {'hook': 'direct'}}, 'guard_not_hooked'),
    ({'kctrl_sensor_guard': {'blind': 'log_level'}}, 'guard_cannot_hear_cfs'),
])
def test_la_pose_refuse_une_machine_qui_n_est_pas_au_repos(tmp_path, monkeypatch, changes, error):
    machine = Machine(tmp_path, monkeypatch)
    machine.status = status(**changes)
    with pytest.raises(AssertionError, match=error):
        machine.run('install')
    assert machine.actions == []
    machine.at_v1()
    assert not machine.m.BACKUP.exists()


def test_sans_garde_v1_chargee_la_pose_refuse(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.status['kctrl_sensor_guard'] = {}
    with pytest.raises(AssertionError, match='guard_not_loaded'):
        machine.run('preflight')


@pytest.mark.parametrize('change,error', [
    ({'enabled': False}, 'guard_not_installed'),
    ({'revision': 'cfs-sensor-guard-v1'}, 'guard_revision_changed'),
    ({'hooked': False}, 'guard_not_hooked'),
    ({'failure': 'tick_failed'}, 'guard_failed'),
    ({'blind': 'log_level'}, 'guard_cannot_hear_cfs'),
    ({'status_error': 'boom'}, 'guard_status_error'),
    ({'keep_auto_refill': False}, 'guard_keep_off'),
    ({'job': 1}, 'guard_not_fresh'),
    ({'marked': {'slot': 'T1A'}}, 'guard_not_fresh'),
    ({'kept': 1}, 'guard_not_fresh'),
    ({'paused': True}, 'guard_not_fresh'),
    ({'false_end': {'slot': 'T1B'}}, 'guard_not_fresh'),
    ({'stock_purge': {'running': True}}, 'guard_not_fresh'),
    ({'route_reason': ''}, 'guard_not_ticking'),
])
def test_une_garde_v2_qui_ne_tourne_pas_comme_prevu_revient_a_v1(
        tmp_path, monkeypatch, change, error):
    machine = Machine(tmp_path, monkeypatch, loaded=lambda guard: guard.update(change))
    result = machine.run('install')
    assert result['status'] == 'INSTALL_FAILED_ROLLED_BACK'
    assert error in result['error']
    machine.at_v1()
    assert machine.actions == ['stop', 'start', 'stop', 'start']
    assert machine.status['kctrl_sensor_guard']['revision'] == 'cfs-sensor-guard-v1'
    assert [p.read_bytes() for p in machine.cache.iterdir()] == [V1]


def test_klipper_qui_refuse_de_demarrer_revient_a_v1(tmp_path, monkeypatch):
    def refuses(guard):
        machine.status['webhooks'] = {'state': 'error'}
    machine = Machine(tmp_path, monkeypatch, loaded=refuses)
    result = machine.run('install')
    assert result['status'] == 'INSTALL_FAILED_ROLLED_BACK'
    assert 'klipper_not_ready' in result['error']
    machine.at_v1()


def test_un_fichier_protege_modifie_bloque_tout(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.protected.write_bytes(b'changed elsewhere\n')
    with pytest.raises(RuntimeError, match='protected_file_drift'):
        machine.run('preflight')


def test_la_config_de_v1_est_epinglee_jamais_ecrite(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.config.write_bytes(CONFIG + b'# edited\n')
    with pytest.raises(RuntimeError, match='protected_file_drift'):
        machine.run('preflight')
    machine.config.write_bytes(CONFIG)
    del machine.manifest['protected'][str(machine.config)]
    with pytest.raises(AssertionError, match='config_not_pinned'):
        machine.run('preflight')


def test_une_charge_alteree_est_refusee_avant_tout(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    with pytest.raises(AssertionError, match='payload_hash_changed'):
        machine.run('install', payload=b'something else\n')
    machine.manifest['protected'][str(machine.module)] = sha(V1)
    with pytest.raises(AssertionError, match='target_also_protected'):
        machine.run('install')
    assert machine.actions == []


@pytest.mark.parametrize('prepare,error', [
    (lambda machine: machine.module.write_bytes(b'other guard\n'), 'module_not_v1'),
    (lambda machine: machine.module.unlink(), 'module_not_v1'),
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
    with pytest.raises(AssertionError, match='module_not_v1'):
        machine.run('install')


def test_le_retour_arriere_remet_v1_exact(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.module.chmod(0o640)
    machine.run('install')
    machine.status['kctrl_sensor_guard'].update(job=2, kept=1)
    result = machine.run('rollback')
    assert result['status'] == 'ROLLED_BACK'
    assert result['rest']['guard_revision'] == 'cfs-sensor-guard-v1'
    assert machine.module.read_bytes() == V1 and machine.config.read_bytes() == CONFIG
    assert os.name == 'nt' or stat.S_IMODE(machine.module.stat().st_mode) == 0o640
    assert machine.actions == ['stop', 'start', 'stop', 'start']
    assert [p.read_bytes() for p in machine.cache.iterdir()] == [V1]


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
        stream.write(b'y' * ((1 << 20) - 20) + b' kctrl_sensor_guard: watching\n')
    result = machine.m.log_lines(offset)
    assert result['tracebacks'] == 0
    assert result['lines'] == [('y' * 240 + ' kctrl_sensor_guard: watching')[-240:]]


def test_les_champs_lus_sont_ceux_du_vrai_module_v2():
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
    assert set(guard) == set(v2_status())
    m.guard_fresh(guard)
    m.guard_ticking(guard)


def test_les_champs_v1_attendus_sont_ceux_du_vrai_module_v1():
    import test_kctrl_sensor_guard_v1 as v1_test
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    root.setLevel(logging.INFO)
    try:
        world = v1_test.started(order=('end', 'guard', 'cold'))
        world.run('10:00:01')
        guard = json.loads(json.dumps(world.guard.get_status()))
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)
    assert set(guard) == set(v1_status())
    load().guard_running(guard, 'cfs-sensor-guard-v1')


def manifest():
    return json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))


def test_le_manifeste_epingle_le_candidat_et_l_installateur():
    pins = manifest()
    assert sha((ROOT / pins['source']).read_bytes()) == pins['sha256']
    assert sha((PACKAGE / 'remote_install.py').read_bytes()) == pins['installer_sha256']
    assert pins['destination'] == '/usr/share/klipper/klippy/extras/kctrl_sensor_guard.py'
    assert pins['surveyed'] is True and pins['surveyed_on'] == '2026-11-12'
    effects = pins['effects']
    assert effects['klipper_restart_idle_only'] is True
    assert not any(effects[key] for key in ('heating', 'motion', 'filament', 'config_change',
                                            'printer_cfg_change'))
    assert 'config' not in pins and pins['backup'].endswith('/cfs-sensor-guard-v2')


def test_avant_c_est_le_code_v1_et_ses_epingles_plus_sa_config():
    pins = manifest()
    v1 = json.loads((V1_PACKAGE / 'manifest.json').read_text(encoding='utf-8'))
    assert pins['before_sha256'] == v1['sha256'] == sha(
        (V1_PACKAGE / 'kctrl_sensor_guard.py').read_bytes())
    expected = dict(v1['protected'], **{v1['config']['path']: v1['config']['sha256']})
    assert pins['protected'] == expected and len(expected) == 24
    assert pins['destination'] not in expected


def test_la_section_v1_suffit_a_v2():
    # V2 adds keep_auto_refill, on by default: the V1 block loads it unchanged.
    assert (PACKAGE / 'sections.cfg').read_bytes() == (V1_PACKAGE / 'sections.cfg').read_bytes()


def test_le_retour_v1_refuse_tant_que_v2_est_posee():
    # V1's rollback accepts only its own module or none: roll V2 back first.
    v1 = json.loads((V1_PACKAGE / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest()['sha256'] not in (None, v1['sha256'])
