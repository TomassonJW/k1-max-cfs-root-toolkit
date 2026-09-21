"""Offline bundle and exact operation plan. No network or command execution.

Build copies reviewed payloads and emits plan.json for the future operator.
It never installs, restarts Klipper or changes enabled. Python 3.8 compatible.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CAPTURE = 'cfs-end-ui-disabled-v1'
BACKUP = '/usr/data/k1-control-v1/backups/' + CAPTURE
STAGING = '/usr/data/k1-control-v1/staging/' + CAPTURE
SERVICE = '/etc/init.d/S55klipper_service'
MESH = 'k1_p001_t055_r001_n11x11'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def payloads(manifest, root=ROOT):
    """Reject source drift before producing any output; inclusion is additive."""
    out = {}
    for entry in manifest['files']:
        data = (root / entry['source']).read_bytes()
        if entry.get('append'):
            data += entry['append'].encode('utf-8')
        if digest(data) != entry['sha256']:
            raise ValueError('payload drift: ' + entry['source'])
        if entry['destination'].endswith('k1-control-owned-end-candidate.cfg'):
            if b'enabled: false' not in data or b'enabled: true' in data:
                raise ValueError('activation forbidden')
        out[entry['name']] = data
    return out


def check_hashes(manifest, observed):
    """All pins, including reviewed repo baselines, must match a fresh read.

    Missing/extra data is not evidence of absence: new files explicitly use
    None as their expected value, supplied only after a successful stat.
    """
    for path, expected in manifest['before'].items():
        if path not in observed or observed[path] != expected:
            raise ValueError('baseline mismatch: ' + path)


def validate_cold(status, installed=False, reference=None):
    """Validate saved GET status only. Does not read a printer or send G-code."""
    def need(ok, label):
        if not ok:
            raise ValueError(label)
    need(status.get('webhooks', {}).get('state') == 'ready', 'Klipper not ready')
    need(status.get('print_stats', {}).get('state') in ('standby', 'complete', 'cancelled'), 'job active')
    need(status.get('pause_resume', {}).get('is_paused') is False, 'paused/unknown')
    for name in ('extruder', 'heater_bed'):
        target = status.get(name, {}).get('target')
        need(type(target) in (int, float) and target == 0, 'heater target')
    need(status.get('toolhead', {}).get('homed_axes') == '', 'axes engaged')
    need(status.get('filament_switch_sensor filament_sensor_2', {}).get('filament_detected') is False, 'head not empty')
    box = status.get('box', {})
    need(box.get('state') == 'connect' and box.get('enable') == 1, 'CFS not ready')
    for unit in ('T1', 'T2'):
        need(box.get(unit, {}).get('state') == 'connect'
             and box[unit].get('filament') == 'None', 'CFS route')
    mesh = status.get('bed_mesh', {})
    need(mesh.get('profile_name') == MESH and bool(mesh.get('mesh_matrix')), 'mesh missing')
    origin = status.get('gcode_move', {}).get('homing_origin')
    need(isinstance(origin, list) and len(origin) >= 3
         and abs(origin[2] - (-0.04)) < 1e-6, 'Z changed')
    if reference is not None:
        need(mesh['mesh_matrix'] == reference['bed_mesh']['mesh_matrix'], 'mesh changed')
        need(origin == reference['gcode_move']['homing_origin'], 'origin changed')
    gate = status.get('kctrl_print_gate', {})
    need(gate.get('wrapped') == 1 and gate.get('pending') == 0, 'gate unavailable/busy')
    if installed:
        end = status.get('kctrl_end', {})
        need(end.get('enabled') is False and end.get('phase') == 'disabled'
             and end.get('pending') is False and end.get('job_epoch') == 0
             and not end.get('failure') and not end.get('thermal_failure'), 'candidate not inert')
        need(gate.get('end') == end, 'UI status not connected')
    else:
        need('kctrl_end' not in status, 'candidate already present')
    return True


def operation_plan(manifest):
    """Shell commands are DATA for review, never executed by this module.

    A future runner must enforce checks and stop on the first failed command.
    The ordered plan is not a standalone deployer or an authorization token.
    """
    q = shlex.quote
    backup, install, rollback, verify = [], [], [], []
    for entry in manifest['files']:
        dest = entry['destination']
        saved = BACKUP + '/' + entry['name'] + '.before'
        incoming = STAGING + '/' + entry['name']
        if entry['before_sha256'] is not None:
            backup.append('cp -p ' + q(dest) + ' ' + q(saved))
            rollback.append('cp -p ' + q(saved) + ' ' + q(dest + '.kctrl-next'))
            rollback.append('mv ' + q(dest + '.kctrl-next') + ' ' + q(dest))
        else:
            rollback.append('rm -f ' + q(dest))
        # The include-bearing existing config is the LAST entry installed.
        install.extend(['cp ' + q(incoming) + ' ' + q(dest + '.kctrl-next'),
                        'chmod 0644 ' + q(dest + '.kctrl-next'),
                        'mv ' + q(dest + '.kctrl-next') + ' ' + q(dest)])
        verify.append({'path': dest, 'sha256': entry['sha256']})
    rollback += ['rm -f ' + q(path) for path, value in manifest['before'].items()
                 if value is None and path.endswith('.pyc')]
    return {
        'schema': 1, 'scope': 'disabled installation preparation only',
        'executable': False, 'activation_permitted': False,
        'backup_directory': BACKUP, 'staging_directory': STAGING,
        'preflight': {
            'fresh_hashes': manifest['before'],
            'status_validator': 'validate_cold(status, installed=False)',
            'exclusive_idle_required': True,
            'backup_and_staging_must_not_exist': True,
            'resolve_current_symlink_and_freeze_target': True,
            'save_status_and_config_and_command_registry': True,
        },
        'backup': ['mkdir ' + q(BACKUP)] + backup,
        'backup_verification': 'Compare each .before to before_sha256; save mode/uid/gid and resolved destinations; abort BEFORE stop or replacement on mismatch.',
        'install': [SERVICE + ' stop'] + install + [SERVICE + ' start'],
        'restart_verification': 'Observe old Klipper process/socket disappearance, then new process and ready (60 s maximum); HTTP success alone is insufficient.',
        'restore_mesh_once': 'BED_MESH_PROFILE LOAD=' + MESH,
        'validate': {
            'payload_hashes': verify,
            'unchanged_hashes': {p: v for p, v in manifest['before'].items()
                                 if v is not None and p not in {e['destination'] for e in manifest['files']}},
            'status_validator': 'validate_cold(status, installed=True, reference=before)',
            'repeat_independent_read': True,
            'commands_must_remain_original': ['START_PRINT', 'END_PRINT', 'CANCEL_PRINT'],
            'browser': 'Fresh reload Mainsail and /bobines/: new JS hashes over HTTP, gate.end disabled, no new start or filament command.',
        },
        'rollback': [SERVICE + ' stop'] + rollback + [SERVICE + ' start'],
        'rollback_verification': 'Compare ALL original hashes/absence and metadata; observe real restart; load previous mesh once; validate_cold(installed=False, reference=before). Remove only bytecode generated for new kctrl_end after recording its exact path. No retry of any physical command.',
        'on_failure': 'Stop the sequence. If any replacement began, restore verified backups while Klipper is stopped, then validate rollback. If rollback fails, leave Klipper stopped and report KO; do not activate or print.',
    }


def build(destination):
    manifest = json.loads((HERE / 'manifest.json').read_text(encoding='utf-8'))
    data = payloads(manifest)
    destination = Path(destination).resolve()
    # Local artifacts belong to the workspace; no overwrite of an old bundle.
    destination.relative_to(ROOT.resolve())
    destination.mkdir(parents=True, exist_ok=False)
    for name, body in data.items():
        (destination / name).write_bytes(body)
    (destination / 'plan.json').write_text(json.dumps(operation_plan(manifest), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='new local workspace directory')
    args = parser.parse_args()
    print('OFFLINE_BUNDLE_OK ' + str(build(args.output)))
