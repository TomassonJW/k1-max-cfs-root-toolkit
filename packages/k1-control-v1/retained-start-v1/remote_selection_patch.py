"""One-file cold update after the successful retained T1B trial.

Uses the first installation's exact manifest and keeps its rollback intact.
No heating, motion, extrusion, synthetic reference or filament operation.
"""
from . import remote_install as base

TARGET = '/usr/share/klipper/klippy/extras/kctrl_start.py'
OLD_SHA = 'bd0e3cb5bcd862d5a78d4acf0f7cf48eab0633abae69bfad8df5272e0a2fabc1'
BACKUP = base.Path('/usr/data/k1-control-v1/backups/retained-start-temperature-v1')
POLICY = 'preserve-active-tool-target-v1'


def cold(s, restarted=False, patched=False):
    assert s['webhooks']['state'] == 'ready'
    assert s['print_stats']['state'] in ('standby', 'complete')
    assert s['virtual_sdcard']['is_active'] is False and s['pause_resume']['is_paused'] is False
    for name in ('extruder', 'heater_bed'):
        assert s[name]['target'] == 0 and base.finite(s[name]['temperature'])
        assert 0 <= s[name]['temperature'] <= 50
    for name in ('live_velocity', 'live_extruder_velocity'):
        value = s['motion_report'][name]
        assert base.finite(value) and abs(value) < 1.e-6
    head = s['toolhead']
    assert head['homed_axes'] == ''
    assert all(base.finite(v) for v in head['position']) and len(head['position']) == 4
    assert all(base.finite(head[k]) for k in ('print_time', 'estimated_print_time'))
    assert head['print_time'] <= head['estimated_print_time'] + .05
    assert s['filament_switch_sensor filament_sensor_2']['filament_detected'] is False
    assert type(s['filament_switch_sensor filament_sensor']['filament_detected']) is bool
    box = s['box']
    assert box['enable'] == 1 and box['state'] == 'connect'
    for unit in ('T1', 'T2'):
        assert box[unit]['state'] == 'connect' and box[unit]['filament'] == 'None'
    for unit in ('T3', 'T4'):
        assert box.get(unit, {}).get('state') in (None, 'None', 'disconnect')
    # Only the observed, completed test may leave this old selection label.
    assert box['t_command'] in (('',) if restarted else ('', 'T1A'))
    end = s['kctrl_end']
    assert end['enabled'] is True and end['pending'] is False
    assert end['phase'] == ('idle' if restarted else 'complete')
    assert not end.get('failure') and not end.get('thermal_failure')
    assert end['revision'] == 'end-rewind-confirm-v3'
    assert end['wrapped'] == ['CANCEL_PRINT', 'END_PRINT', 'START_PRINT']
    start = s['kctrl_start']
    assert start['enabled'] is True and start['installed'] is True and not start['failure']
    assert start['phase'] == ('idle' if restarted else 'complete')
    assert start['reference_valid'] is False
    if restarted:
        assert start['reference'] == 0
        assert start.get('selection_policy') == (POLICY if patched else None)
    guard = s['kctrl_purge_guard']
    assert guard['installed'] is True and guard['minimum_z'] >= 30
    assert guard['bin_latched'] is False and guard['denied'] == 0
    assert s['kctrl_bin_motion']['installed'] is True


def ready(patched):
    deadline = base.time.monotonic() + 75
    while base.time.monotonic() < deadline:
        try:
            s = base.state()
            cold(s, restarted=True, patched=patched)
            return s
        except Exception:
            base.time.sleep(1)
    raise RuntimeError('updated_runtime_not_ready')


def geometry(before, patched):
    profile = before['bed_mesh']['profile_name']
    assert base.re.fullmatch(r'[A-Za-z0-9_]+', profile)
    origin = before['gcode_move']['homing_origin'][:3]
    assert len(origin) == 3 and all(base.finite(v) and abs(v) <= 2 for v in origin)
    base.api('/printer/gcode/script', {'script': 'BED_MESH_PROFILE LOAD=' + profile
        + '\nSET_GCODE_OFFSET_BASE X=%.6f Y=%.6f Z=%.6f MOVE=0' % tuple(origin)})
    s = base.state()
    cold(s, restarted=True, patched=patched)
    assert s['bed_mesh'] == before['bed_mesh']
    assert all(abs(a-b) < 1.e-6 for a,b in zip(s['gcode_move']['homing_origin'][:3], origin))
    for sensor in ('filament_sensor', 'filament_sensor_2'):
        assert s['filament_switch_sensor ' + sensor] == before['filament_switch_sensor ' + sensor]


def receipt(status, **details):
    value = {'status': status, 'time': base.time.time(), **details}
    (BACKUP/'receipt.json').write_text(base.json.dumps(value), encoding='utf-8')
    return value


def run(request):
    initial = request['initial_manifest']
    assert initial == base.json.loads((base.BACKUP/'manifest.json').read_text())
    assert tuple(e['name'] for e in initial['files']) == base.NAMES
    assert tuple(e['destination'] for e in initial['files']) == base.DESTINATIONS
    before = dict(initial['before'])
    before.update({e['destination']: e['sha256'] for e in initial['files']})
    assert before[TARGET] == OLD_SHA
    data = base.base64.b64decode(request['payload'], validate=True)
    assert base.hashlib.sha256(data).hexdigest() == request['sha256']
    after = dict(before)
    after[TARGET] = request['sha256']
    assert request['mode'] in ('preflight', 'install', 'validate')
    if request['mode'] == 'validate':
        base.hashes(after)
        assert base.digest(BACKUP/'kctrl_start.py.before') == OLD_SHA
        cold(base.state(), restarted=True, patched=True)
        saved = base.json.loads((BACKUP/'state.before.json').read_text())
        # Validation reads only: the geometry was restored by install.
        now = base.state()
        assert now['bed_mesh'] == saved['bed_mesh']
        assert now['gcode_move']['homing_origin'] == saved['gcode_move']['homing_origin']
        return {'status': 'TEMPERATURE_PATCH_VALIDATED_COLD_OK'}
    base.hashes(before)
    first = base.state()
    cold(first)
    base.time.sleep(.5)
    second = base.state()
    cold(second)
    for name in ('toolhead', 'box', 'kctrl_end', 'kctrl_start'):
        keys = ('position', 'homed_axes') if name == 'toolhead' else ('t_command',) if name == 'box' else ('phase',)
        assert all(first[name][k] == second[name][k] for k in keys)
    assert not BACKUP.exists() and not base.Path(TARGET + '.kctrl-retained-next').exists()
    if request['mode'] == 'preflight':
        return {'status': 'TEMPERATURE_PATCH_PREFLIGHT_OK', 'files': 1}
    BACKUP.mkdir()
    (BACKUP/'state.before.json').write_text(base.json.dumps(second), encoding='utf-8')
    (BACKUP/'kctrl_start.py.before').write_bytes(base.Path(TARGET).read_bytes())
    assert base.digest(BACKUP/'kctrl_start.py.before') == OLD_SHA
    receipt('BACKED_UP')
    stopped = False
    try:
        cold(base.state())
        oldpid = base.stop()
        stopped = True
        base.hashes(before)
        base.replace(TARGET, data)
        base.hashes(after)
        base.service('start')
        ready(True)
        assert base.PIDFILE.read_text().strip() != oldpid
        geometry(second, True)
        base.hashes(after)
        return receipt('TEMPERATURE_PATCH_INSTALLED_COLD_OK', files=1, physical_validation=False)
    except Exception as error:
        if not stopped:
            return receipt('NO_FILES_CHANGED_SERVICE_STATE_REQUIRES_CHECK', error=str(error))
        base.service('stop')
        assert base.digest(TARGET) in (OLD_SHA, request['sha256']), 'foreign_file_not_overwritten'
        assert base.digest(BACKUP/'kctrl_start.py.before') == OLD_SHA, 'backup_corrupt'
        base.replace(TARGET, (BACKUP/'kctrl_start.py.before').read_bytes())
        base.hashes(before)
        base.service('start')
        ready(False)
        geometry(second, False)
        return receipt('TEMPERATURE_PATCH_ROLLED_BACK', error=str(error), physical_validation=False)
