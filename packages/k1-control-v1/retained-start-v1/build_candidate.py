"""Build a reviewable local candidate and pinned rollback inventory; no network.

This is not an installer. The installed end include is part of the baseline
and must survive the replacement of the start configuration.
"""

import ast
import hashlib
import json
from pathlib import Path

try:
    from .integration import render_start
except ImportError:
    from integration import render_start

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parent
START_DEST = '/usr/data/printer_data/config/k1-control-owned-start-print-v2.cfg'
END_DEST = '/usr/share/klipper/klippy/extras/kctrl_end.py'
END_INCLUDE = ('\n# ADR-069: candidate remains disabled; no command takeover.\n'
               '[include k1-control-owned-end-candidate.cfg]\n')
MODULES = ('kctrl_start_policy.py', 'kctrl_start_context.py', 'kctrl_purge_guard.py',
           'kctrl_bin_motion.py', 'kctrl_start.py')


def sha(content):
    return hashlib.sha256(content).hexdigest()


def build():
    old = json.loads((ROOT / 'packages/k1-control-v1/end-rewind-confirm-v3/manifest.json').read_text())
    before = dict(old['before'])
    before.update({entry['destination']: entry['sha256'] for entry in old['files']})
    base = (ROOT / 'packages/k1-control-v1/owned-start-print-v2/k1-control-owned-start-print-v2.cfg').read_text()
    installed = (base + END_INCLUDE).encode('utf-8')
    if sha(installed) != before[START_DEST]:
        raise ValueError('installed_start_baseline_not_reproduced')
    config = render_start(installed.decode('utf-8'))
    # Keep the include itself byte-for-byte. Its old comment is historical;
    # the included V3 owner is enabled and remains protected by its hash.
    assert config.count(END_INCLUDE) == 1
    sections = (PACKAGE / 'sections.cfg').read_text()
    assert sections.count('\nenabled: False\n') == 1
    config += '\n' + sections.replace('\nenabled: False\n', '\nenabled: True\n')
    payloads = {'k1-control-owned-start-print-v2.cfg': config.encode('utf-8')}
    files = []
    for name in (*MODULES, 'k1-control-owned-start-print-v2.cfg'):
        destination = START_DEST if name.endswith('.cfg') else '/usr/share/klipper/klippy/extras/' + name
        if name.endswith('.py'):
            payloads[name] = (PACKAGE / name).read_text().encode('utf-8')
            ast.parse(payloads[name].decode('utf-8'), feature_version=(3, 8))
            if destination in before:
                raise ValueError('candidate_module_already_in_baseline')
            before[destination] = None  # must be freshly verified absent
        files.append({'name': name, 'destination': destination,
                      'before_sha256': before[destination], 'sha256': sha(payloads[name])})
    manifest = {
        'schema': 1, 'name': 'retained-start-v1', 'local_candidate': True,
        'installed': False, 'physical_validation': False, 'installer_ready': False,
        'before': before, 'files': files,
        'protected_end_sha256': before[END_DEST],
        'backup': '/usr/data/k1-control-v1/backups/retained-start-v1',
        'pending': ['fresh_cold_preflight', 'reviewed_transactional_installer',
                    'cold_install_validation', 'fresh_manual_clean_and_physical_trial'],
        'rollback': ['stop_klipper_after_verified_idle', 'restore_exact_start_config_backup',
                     'remove_only_five_added_modules_if_their_hashes_match',
                     'start_klipper_and_confirm_new_process',
                     'restore_previous_mesh_and_offsets_with_MOVE_0',
                     'verify_all_previous_hashes_and_loaded_end_v3'],
    }
    return manifest, payloads


if __name__ == '__main__':
    manifest, payloads = build()
    (PACKAGE / 'k1-control-owned-start-print-v2.cfg').write_bytes(payloads['k1-control-owned-start-print-v2.cfg'])
    (PACKAGE / 'manifest.json').write_bytes((json.dumps(manifest, indent=2) + '\n').encode('utf-8'))
    print('RETAINED_START_LOCAL_CANDIDATE_OK files=%d installed=false installer_ready=false' % len(manifest['files']))
