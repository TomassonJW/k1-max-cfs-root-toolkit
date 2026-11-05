#!/usr/bin/env python3
"""Write manifest.json from the candidates, the installer and the live pins.

The pins are those of end-no-stock-flush-v5. kctrl_end.py joins them with its
V5 hash, the only code of the print sequence that package changed, and the end
configuration leaves them: it is this package's second target, `before_sha256`
below, and end-separated-v1 holds its exact copy. Until `SURVEYED` holds the
date `deploy.py survey` found them on the printer, the manifest says
`surveyed: false` and the installer refuses everything but the survey.
"""

import hashlib
import importlib.util
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
NAME = 'packages/k1-control-v1/cfs-sensor-guard-v1/'
BASE_CONFIG = ROOT / 'packages/k1-control-v1/end-separated-v1/k1-control-owned-end-candidate.cfg'
V5 = ROOT / 'packages/k1-control-v1/end-no-stock-flush-v5/'
SURVEYED = '2026-11-05'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def installer():
    spec = importlib.util.spec_from_file_location('sensor_install', PACKAGE / 'remote_install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    m = installer()
    v5 = json.loads((V5 / 'manifest.json').read_text(encoding='utf-8'))
    protected = dict(v5['protected'])
    del protected[m.CONFIG]
    protected[v5['destination']] = v5['sha256']
    base = BASE_CONFIG.read_bytes()
    section = (PACKAGE / 'sections.cfg').read_bytes()
    manifest = {
        'schema': 1,
        'name': m.NAME,
        'adr': m.ADR,
        'document': 'docs/105-garde-capteur-cfs-contredit-et-fin-sure.md',
        'surveyed': SURVEYED is not None,
        'surveyed_on': SURVEYED,
        'source': NAME + 'kctrl_sensor_guard.py',
        'destination': m.MODULE,
        'before_sha256': None,
        'sha256': sha((PACKAGE / 'kctrl_sensor_guard.py').read_bytes()),
        'config': {
            'path': m.CONFIG,
            'section': NAME + 'sections.cfg',
            'section_sha256': sha(section),
            'before_sha256': sha(base),
            'sha256': sha(m.candidate(base, section)),
        },
        'installer_sha256': sha((PACKAGE / 'remote_install.py').read_bytes()),
        # as_posix: built on Windows, compared on the printer.
        'backup': m.BACKUP.as_posix(),
        'effects': {'klipper_restart_idle_only': True, 'heating': False, 'motion': False,
                    'filament': False, 'config_change': True, 'printer_cfg_change': False},
        'protected': protected,
    }
    (PACKAGE / 'manifest.json').write_bytes(
        (json.dumps(manifest, indent=2, sort_keys=False) + '\n').encode('utf-8'))
    print(manifest['sha256'], manifest['installer_sha256'],
          'surveyed' if SURVEYED else 'not surveyed')


if __name__ == '__main__':
    main()
