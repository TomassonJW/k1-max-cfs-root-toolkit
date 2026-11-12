#!/usr/bin/env python3
"""Write manifest.json from the candidate, the installer and the live pins.

The pins are those of cfs-sensor-guard-v1, plus the end configuration at the
hash V1 left it (`config.sha256` of the V1 manifest): V2 never writes it, the
[kctrl_sensor_guard] block stays as V1 posed it. The module leaves the
pins: it is this package's only target, `before_sha256` is the V1 code.
Until `SURVEYED` holds the date `deploy.py survey` found them on the printer,
the manifest says `surveyed: false` and the installer refuses everything but
the survey.
"""

import hashlib
import importlib.util
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
NAME = 'packages/k1-control-v1/cfs-sensor-guard-v2/'
V1 = ROOT / 'packages/k1-control-v1/cfs-sensor-guard-v1/'
SURVEYED = '2026-11-12'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def installer():
    spec = importlib.util.spec_from_file_location('sensor_v2_install', PACKAGE / 'remote_install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    m = installer()
    v1 = json.loads((V1 / 'manifest.json').read_text(encoding='utf-8'))
    assert v1['destination'] == m.MODULE and v1['config']['path'] == m.CONFIG
    protected = dict(v1['protected'])
    protected[m.CONFIG] = v1['config']['sha256']
    manifest = {
        'schema': 1,
        'name': m.NAME,
        'adr': m.ADR,
        'document': 'docs/107-garde-capteur-cfs-v2-reprise-gardee.md',
        'surveyed': SURVEYED is not None,
        'surveyed_on': SURVEYED,
        'source': NAME + 'kctrl_sensor_guard.py',
        'destination': m.MODULE,
        'before_sha256': v1['sha256'],
        'sha256': sha((PACKAGE / 'kctrl_sensor_guard.py').read_bytes()),
        'installer_sha256': sha((PACKAGE / 'remote_install.py').read_bytes()),
        # as_posix: built on Windows, compared on the printer.
        'backup': m.BACKUP.as_posix(),
        'effects': {'klipper_restart_idle_only': True, 'heating': False, 'motion': False,
                    'filament': False, 'config_change': False, 'printer_cfg_change': False},
        'protected': protected,
    }
    (PACKAGE / 'manifest.json').write_bytes(
        (json.dumps(manifest, indent=2, sort_keys=False) + '\n').encode('utf-8'))
    print(manifest['sha256'], manifest['installer_sha256'],
          'surveyed' if SURVEYED else 'not surveyed')


if __name__ == '__main__':
    main()
