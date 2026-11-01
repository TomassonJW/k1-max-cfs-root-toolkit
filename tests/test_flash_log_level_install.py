"""Install, refuse and roll back the Creality log level entirely in a temporary tree.

The printer is replaced by a status dictionary, the vendor file by a synthetic
file of the same shape (the real one is not versioned, only its fingerprints),
ssh by a recorder (document 103, option 1).
"""
import ast
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import types

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / 'packages/k1-control-v1/flash-log-level-v1'
SYNTHETIC = (b'{\n  "#log_level":"exemple synthetique, pas le fichier constructeur",\n'
             b'  "log_level":1,\n  "#log_route":"exemple synthetique",\n  "log_route":1\n}')


def load(name='remote_install'):
    spec = importlib.util.spec_from_file_location('flash_log_level_' + name, PACKAGE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


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
        'box': {'t_command': ''},
        'kctrl_end': {'phase': 'complete', 'pending': False},
        'kctrl_start': {'phase': 'complete'},
    }
    for key, update in changes.items():
        value[key] = dict(value[key], **update)
    return value


class Machine:
    """Temporary tree, fake Klipper status, same paths as the module."""

    def __init__(self, tmp_path, monkeypatch):
        self.m = m = load()
        self.target = tmp_path / 'log/log_config.json'
        self.target.parent.mkdir()
        self.original = SYNTHETIC
        self.target.write_bytes(self.original)
        self.target.chmod(0o644)
        self.candidate = SYNTHETIC.replace(b'"log_level":1,', b'"log_level":3,')
        for name, value in (('TARGET', str(self.target)), ('STAGE', str(self.target) + '.kctrl-next'),
                            ('BACKUP', tmp_path / 'backups/flash-log-level-v1')):
            monkeypatch.setattr(m, name, value)
        clock = [0.0]
        monkeypatch.setattr(m, 'time', types.SimpleNamespace(
            time=lambda: 1.0e9 + clock[0],
            sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds)))
        self.status = status()
        self.hook = None
        self.reads = 0
        monkeypatch.setattr(m, 'state', self.state)
        self.manifest = {'name': m.NAME, 'destination': str(self.target),
                         'before_sha256': sha(self.original), 'sha256': sha(self.candidate)}

    def state(self):
        self.reads += 1
        if self.hook:
            self.hook(self.reads)
        if self.status is None:
            raise RuntimeError('klippy_socket_closed')
        return json.loads(json.dumps(self.status))

    def run(self, mode):
        return self.m.run({'mode': mode, 'manifest': self.manifest})


def test_le_preflight_ne_touche_a_rien(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    assert machine.run('preflight') == {'status': 'PREFLIGHT_OK', 'log_level': 1,
                                        'size': len(machine.original)}
    assert machine.target.read_bytes() == machine.original
    assert not machine.m.BACKUP.exists()


def test_la_pose_sauvegarde_puis_change_un_seul_chiffre(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    mode = stat.S_IMODE(machine.target.stat().st_mode)
    result = machine.run('install')
    assert (result['status'], result['log_level'], result['effect']) == \
        ('INSTALLED_OK', 3, 'next_power_on')
    assert machine.target.read_bytes() == machine.candidate
    assert stat.S_IMODE(machine.target.stat().st_mode) == mode
    assert not Path(machine.m.STAGE).exists()
    backup = machine.m.BACKUP
    assert (backup / 'log_config.json.before').read_bytes() == machine.original
    assert json.loads((backup / 'mode.json').read_text())['mode'] == oct(mode)
    assert json.loads((backup / 'manifest.json').read_text()) == machine.manifest
    assert json.loads((backup / 'receipt.json').read_text())['status'] == 'INSTALLED_OK'
    # La validation ne lit que le fichier : permise pendant une impression, sans Klipper.
    machine.status = status(print_stats={'state': 'printing'})
    reads = machine.reads
    assert machine.run('validate') == {'status': 'VALIDATED_OK', 'log_level': 3,
                                       'receipt': 'INSTALLED_OK'}
    assert machine.reads == reads


@pytest.mark.parametrize('change,error', [
    ({'print_stats': {'state': 'printing'}}, 'job_busy'),
    ({'extruder': {'target': 220.0}}, 'heater_target_set'),
    (None, 'klippy_socket_closed'),
])
def test_un_changement_juste_avant_l_ecriture_annule_la_pose_sans_rien_changer(
        tmp_path, monkeypatch, change, error):
    machine = Machine(tmp_path, monkeypatch)

    def third_read(reads):
        if reads == 3:  # apres les deux lectures stables, juste avant l'ecriture
            machine.status = status(**change) if change else None
    machine.hook = third_read
    assert machine.run('install') == {'status': 'NOT_INSTALLED_NOTHING_CHANGED', 'error': error}
    assert machine.target.read_bytes() == machine.original
    assert not machine.m.BACKUP.exists()


def test_klipper_injoignable_bloque_avant_toute_sauvegarde(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.status = None
    with pytest.raises(RuntimeError, match='klippy_socket_closed'):
        machine.run('install')
    assert machine.target.read_bytes() == machine.original
    assert not machine.m.BACKUP.exists()


@pytest.mark.parametrize('changes', [
    {'print_stats': {'state': 'standby'}},
    {'print_stats': {'state': 'cancelled'}},
    {'print_stats': {'state': 'error'}},
    {'kctrl_end': {'phase': 'idle'}},
    {'kctrl_end': {'phase': 'disabled'}},
    {'kctrl_end': {'phase': 'failed'}},
    {'kctrl_start': {'phase': 'idle'}},
])
def test_les_repos_connus_permettent_la_pose(tmp_path, monkeypatch, changes):
    # Une annulation laisse la fin en echec (ADR-074) : c'est un repos.
    machine = Machine(tmp_path, monkeypatch)
    machine.status = status(**changes)
    assert machine.run('install')['status'] == 'INSTALLED_OK'


@pytest.mark.parametrize('changes,error', [
    ({'webhooks': {'state': 'shutdown'}}, 'klipper_not_ready'),
    ({'print_stats': {'state': 'printing'}}, 'job_busy'),
    ({'print_stats': {'state': 'paused'}}, 'job_busy'),
    ({'pause_resume': {'is_paused': True}}, 'paused'),
    ({'virtual_sdcard': {'is_active': True}}, 'sd_active'),
    ({'idle_timeout': {'state': 'Printing'}}, 'idle_timeout_printing'),
    ({'extruder': {'target': 150.0}}, 'heater_target_set'),
    ({'heater_bed': {'target': 55.0}}, 'heater_target_set'),
    ({'motion_report': {'live_velocity': 12.0}}, 'motion_active'),
    ({'motion_report': {'live_extruder_velocity': -2.5}}, 'motion_active'),
    ({'motion_report': {'live_velocity': None}}, 'motion_active'),
    ({'toolhead': {'print_time': 93800.0}}, 'motion_queued'),
    ({'toolhead': {'print_time': None}}, 'motion_clock_unknown'),
    ({'box': {'t_command': 'T1A'}}, 'cfs_command_present'),
    ({'kctrl_end': {'phase': 'rewinding'}}, 'end_active'),
    ({'kctrl_end': {'phase': 'cutting'}}, 'end_active'),
    ({'kctrl_end': {'phase': 'une_phase_future'}}, 'end_active'),
    ({'kctrl_end': {'pending': True}}, 'end_active'),
    ({'kctrl_start': {'phase': 'material'}}, 'start_active'),
    ({'kctrl_start': {'phase': 'planned'}}, 'start_active'),
])
def test_la_pose_refuse_une_machine_qui_n_est_pas_au_repos(tmp_path, monkeypatch, changes, error):
    machine = Machine(tmp_path, monkeypatch)
    machine.status = status(**changes)
    for mode in ('preflight', 'install'):
        with pytest.raises(AssertionError, match=error):
            machine.run(mode)
    assert machine.target.read_bytes() == machine.original
    assert not machine.m.BACKUP.exists()


@pytest.mark.parametrize('name,error', [('box', 'cfs_command_present'),
                                        ('kctrl_end', 'end_active'),
                                        ('kctrl_start', 'start_active')])
def test_un_objet_absent_de_klipper_compte_comme_occupe(tmp_path, monkeypatch, name, error):
    # Klipper repond {} pour un objet inconnu : une absence ne prouve pas le repos.
    machine = Machine(tmp_path, monkeypatch)
    machine.status[name] = {}
    with pytest.raises(AssertionError, match=error):
        machine.run('install')
    assert not machine.m.BACKUP.exists()


def test_une_cible_differente_est_refusee_avec_son_empreinte(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    foreign = machine.original.replace(b'"log_route":1', b'"log_route":2')
    machine.target.write_bytes(foreign)
    with pytest.raises(AssertionError, match='target_not_at_baseline: ' + sha(foreign)):
        machine.run('preflight')
    assert machine.reads == 0


def test_la_modification_ne_change_qu_un_chiffre():
    m = load()
    after = m.edited(SYNTHETIC)
    digit = SYNTHETIC.index(m.OLD) + len(m.OLD) - 2
    assert len(after) == len(SYNTHETIC)
    assert [index for index, (a, b) in enumerate(zip(SYNTHETIC, after)) if a != b] == [digit]
    assert after[digit:digit + 1] == b'3'


@pytest.mark.parametrize('data,error', [
    (SYNTHETIC.replace(b'"log_level":1,', b'"log_level":3,'), 'level_line_not_unique'),
    (b'{"log_level":1,"log_level":1,"x":1}', 'level_line_not_unique'),
    (b'{"log_level":1,"log_level":5}', 'level_not_changed'),
    (b'{"sub":{"log_level":1,"x":2},"log_level":1}', 'level_not_changed'),
])
def test_la_modification_refuse_un_fichier_ambigu(data, error):
    with pytest.raises(AssertionError, match=error):
        load().edited(data)


def test_une_pose_deja_faite_ne_se_rejoue_pas(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    with pytest.raises(AssertionError, match='target_not_at_baseline'):
        machine.run('install')


def test_une_sauvegarde_existante_n_est_jamais_ecrasee(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.target.write_bytes(machine.original)
    with pytest.raises(AssertionError, match='backup_already_exists'):
        machine.run('install')
    assert (machine.m.BACKUP / 'log_config.json.before').read_bytes() == machine.original
    assert json.loads((machine.m.BACKUP / 'receipt.json').read_text())['status'] == 'INSTALLED_OK'


def test_un_fichier_de_transit_oublie_bloque_tout(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    Path(machine.m.STAGE).write_bytes(b'left over\n')
    with pytest.raises(AssertionError, match='stale_stage_file'):
        machine.run('preflight')


def test_une_cible_en_lien_symbolique_est_refusee(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    real = tmp_path / 'elsewhere.json'
    real.write_bytes(machine.original)
    machine.target.unlink()
    try:
        os.symlink(str(real), str(machine.target))
    except (OSError, NotImplementedError):
        pytest.skip('symbolic links unavailable here')
    with pytest.raises(AssertionError, match='unexpected_symlink'):
        machine.run('preflight')


def test_le_retour_arriere_remet_l_original_exact(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    mode = stat.S_IMODE(machine.target.stat().st_mode)
    machine.run('install')
    result = machine.run('rollback')
    assert (result['status'], result['log_level']) == ('ROLLED_BACK', 1)
    assert machine.target.read_bytes() == machine.original
    assert stat.S_IMODE(machine.target.stat().st_mode) == mode
    assert json.loads((machine.m.BACKUP / 'receipt.json').read_text())['status'] == 'ROLLED_BACK'
    with pytest.raises(AssertionError, match='candidate_not_installed'):
        machine.run('validate')


def test_le_retour_arriere_refuse_une_impression_en_cours(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.status = status(print_stats={'state': 'printing'})
    with pytest.raises(AssertionError, match='job_busy'):
        machine.run('rollback')
    assert machine.target.read_bytes() == machine.candidate


def test_le_retour_arriere_refuse_un_fichier_etranger_ou_une_sauvegarde_alteree(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    machine.run('install')
    machine.target.write_bytes(b'{"log_level":7}')
    with pytest.raises(AssertionError, match='rollback_foreign_file'):
        machine.run('rollback')
    assert machine.target.read_bytes() == b'{"log_level":7}'
    machine.target.write_bytes(machine.candidate)
    (machine.m.BACKUP / 'log_config.json.before').write_bytes(b'altered\n')
    with pytest.raises(AssertionError, match='backup_corrupt'):
        machine.run('rollback')
    assert machine.target.read_bytes() == machine.candidate


def test_un_echec_apres_l_ecriture_remet_l_original(tmp_path, monkeypatch):
    machine = Machine(tmp_path, monkeypatch)
    real = machine.m.replace
    written = []

    def fails_once(data, mode):
        real(data, mode)
        written.append(data)
        if len(written) == 1:
            raise OSError('disk_error')
    monkeypatch.setattr(machine.m, 'replace', fails_once)
    result = machine.run('install')
    assert (result['status'], result['error']) == ('INSTALL_FAILED_ROLLED_BACK', 'disk_error')
    assert written == [machine.candidate, machine.original]
    assert machine.target.read_bytes() == machine.original


def test_l_installateur_ne_redemarre_rien_et_ne_fait_que_lire_klipper():
    m = load()
    source = (PACKAGE / 'remote_install.py').read_text(encoding='utf-8')
    for word in ('subprocess', 'os.system', 'popen', 'init.d', 'reboot', 'kill', 'gcode'):
        assert word not in source.lower(), word
    assert source.count("klippy('") == 1 and "klippy('objects/query'" in source
    assert set(status()) == set(m.QUERY)


def test_le_manifeste_epingle_les_deux_empreintes_et_l_installateur():
    m = load()
    text = (PACKAGE / 'manifest.json').read_text(encoding='utf-8')
    manifest = json.loads(text)
    assert text == json.dumps(manifest, indent=2) + '\n'
    assert manifest['name'] == m.NAME and manifest['destination'] == m.TARGET
    assert manifest['backup'] == str(m.BACKUP).replace('\\', '/')
    assert sha((PACKAGE / 'remote_install.py').read_bytes()) == manifest['installer_sha256']
    # Empreintes du fichier lu le 31 octobre 2026 (document 103), 157 octets.
    assert manifest['before_sha256'] == '027ab3db2764a26e821b4db7cae7547ac1866e1711f3f089a9e5faa411d5c02d'
    assert manifest['sha256'] == 'fcd855a57588b7e61431ab9e0872fb95a55b913a3f27fb0f11383a1dd0a13586'
    assert manifest['size'] == 157
    assert (PACKAGE.parents[2] / manifest['document']).is_file()
    effects = dict(manifest['effects'])
    assert effects.pop('creality_log_level') == [1, 3]
    assert effects and not any(effects.values())
    # Le fichier constructeur n'est pas versionne : seules ses empreintes le sont.
    assert not [path.name for path in PACKAGE.iterdir() if 'log_config' in path.name]


def test_le_generateur_produit_le_manifeste_versionne_a_partir_d_une_copie(tmp_path, monkeypatch):
    build = load('build_manifest')
    package = tmp_path / 'package'
    package.mkdir()
    (package / 'remote_install.py').write_bytes((PACKAGE / 'remote_install.py').read_bytes())
    copy = tmp_path / 'log_config.json'
    copy.write_bytes(SYNTHETIC)
    monkeypatch.setattr(build, 'PACKAGE', package)
    build.main(['build_manifest.py', str(copy)])
    built = json.loads((package / 'manifest.json').read_text(encoding='utf-8'))
    committed = json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))
    measured = ('size', 'before_sha256', 'sha256')
    assert {key: value for key, value in built.items() if key not in measured} == \
        {key: value for key, value in committed.items() if key not in measured}
    assert (built['size'], built['before_sha256'], built['sha256']) == \
        (len(SYNTHETIC), sha(SYNTHETIC), sha(load().edited(SYNTHETIC)))


def test_le_lanceur_n_envoie_que_le_mode_et_le_manifeste(tmp_path, monkeypatch):
    deploy = load('deploy')
    script = deploy.request('preflight')
    head, _, installer = script.partition(b'\n')
    assert installer == (PACKAGE / 'remote_install.py').read_bytes()
    body = json.loads(base64.b64decode(ast.literal_eval(head.decode().split(' = ', 1)[1])))
    assert body == {'mode': 'preflight',
                    'manifest': json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))}
    compile(script, 'request', 'exec')
    calls = []

    def ssh(command, **options):
        calls.append((command, options['input']))
        return types.SimpleNamespace(returncode=0, stdout=b'{"status": "PREFLIGHT_OK"}\n', stderr=b'')
    monkeypatch.setattr(deploy, 'ROOT', tmp_path)
    monkeypatch.setattr(deploy.subprocess, 'run', ssh)
    assert deploy.main(['deploy.py', 'preflight']) == 0
    assert calls == [(['ssh', 'k1max-root', 'python3 -'], script)]
    saved = list((tmp_path / 'inventory/raw').glob('*-flash-log-level-v1/*-preflight.json'))
    assert len(saved) == 1
    assert 'PREFLIGHT_OK' in json.loads(saved[0].read_text(encoding='utf-8'))['stdout']


def test_le_lanceur_refuse_un_installateur_modifie_et_un_mode_inconnu(tmp_path, monkeypatch):
    deploy = load('deploy')
    monkeypatch.setattr(deploy.subprocess, 'run', lambda *args, **options: pytest.fail('ssh called'))
    with pytest.raises(SystemExit):
        deploy.main(['deploy.py', 'reboot'])
    manifest = json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))
    manifest['installer_sha256'] = '0' * 64
    stale = tmp_path / 'manifest.json'
    stale.write_text(json.dumps(manifest), encoding='utf-8')
    monkeypatch.setattr(deploy, 'MANIFEST', stale)
    with pytest.raises(SystemExit, match='rebuild the manifest'):
        deploy.main(['deploy.py', 'install'])


SAMPLE = '''== etat {"result": {"eventtime": 1.0, "status": {"print_stats": {"state": "printing"}}}}
== niveau "log_level":3
== t 1000.00
 179      10 mmcblk0p10 812 0 24113 1820 1000 0 200000 9000 0 5000 10820
60000 11 /usr/data/creality/userdata/log/master-server.log
5000 21 /usr/data/creality/userdata/log/display-server.log
100 31 /usr/data/printer_data/logs/klippy.log
400 41 /usr/data/k1-control-v1/logs/moonraker.log
== t 1030.00
 179      10 mmcblk0p10 812 0 24113 1820 1300 0 209765 9100 0 5100 10920
90000 11 /usr/data/creality/userdata/log/master-server.log
8000 21 /usr/data/creality/userdata/log/display-server.log
100 31 /usr/data/printer_data/logs/klippy.log
700 41 /usr/data/k1-control-v1/logs/moonraker.log
== t 1060.00
 179      10 mmcblk0p10 812 0 24113 1820 1600 0 219531 9200 0 5200 11020
120000 11 /usr/data/creality/userdata/log/master-server.log
2000 22 /usr/data/creality/userdata/log/display-server.log
100 31 /usr/data/printer_data/logs/klippy.log
1000 41 /usr/data/k1-control-v1/logs/moonraker.log
== etat {"result": {"eventtime": 2.0, "status": {"print_stats": {"state": "complete"}}}}
== fin
'''


def test_la_mesure_calcule_le_debit_flash_et_la_croissance_des_journaux():
    mesure = load('mesure')
    samples, states, level = mesure.parse(SAMPLE)
    assert (len(samples), states, level) == (3, ['printing', 'complete'], 3)
    # 19531 secteurs de 512 octets en 60 s ; display-server tourne au dernier releve.
    assert mesure.rates(samples) == {
        'seconds': 60.0, 'uptime_s': 1000, 'flash_mo_min': 10.0, 'writes_per_s': 10.0,
        'logs': {'master-server.log': {'ko_min': 60.0, 'rotated': False},
                 'display-server.log': {'ko_min': 5.0, 'rotated': True},
                 'klippy.log': {'ko_min': 0.0, 'rotated': False},
                 'moonraker.log': {'ko_min': 0.6, 'rotated': False}},
        'amplification': 152}
    assert mesure.parse('== etat \n== niveau \n') == ([], [None], None)


def test_la_mesure_reste_en_lecture_seule_et_garde_la_reponse_brute(tmp_path, monkeypatch, capsys):
    mesure = load('mesure')
    for word in ('>', 'tail', 'tee', ' rm ', 'printer/gcode', 'POST'):
        assert word not in mesure.REMOTE, word
    calls = []

    def ssh(command, **options):
        calls.append((command, options['input'], options['timeout']))
        return types.SimpleNamespace(returncode=0, stdout=SAMPLE.encode(), stderr=b'')
    monkeypatch.setattr(mesure, 'ROOT', tmp_path)
    monkeypatch.setattr(mesure.subprocess, 'run', ssh)
    assert mesure.main(['mesure.py', '3', '30']) == 0
    assert calls == [(['ssh', 'k1max-root', 'nice -n 19 sh -s -- 3 30'], mesure.REMOTE.encode(), 165)]
    saved = list((tmp_path / 'inventory/raw').glob('*-flash-log-level-v1/*-mesure.json'))
    summary = json.loads(saved[0].read_text(encoding='utf-8'))['summary']
    assert (summary['flash_mo_min'], summary['log_level'], summary['states']) == \
        (10.0, 3, ['printing', 'complete'])
    assert json.loads(capsys.readouterr().out) == summary
    monkeypatch.setattr(mesure.subprocess, 'run', lambda command, **options: types.SimpleNamespace(
        returncode=255, stdout=b'', stderr=b'ssh: connect failed'))
    assert mesure.main(['mesure.py']) == 255
    assert json.loads(capsys.readouterr().out) == {'error': 'fewer_than_two_samples', 'samples': 0}
