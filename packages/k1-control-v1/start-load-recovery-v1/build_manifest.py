#!/usr/bin/env python3
"""Write manifest.json from the candidate, the installer and the live pins.

The pins are those of cfs-sensor-guard-v2, the end configuration included,
minus kctrl_start.py, plus kctrl_sensor_guard.py at its V2 hash: this package
needs the V2 guard and must not move it. kctrl_start.py is this package's only
target, `before_sha256` is the retained-start-v1 code the earlier packages
pin. Until `SURVEYED` holds the date `deploy.py survey` found them on the
printer, the manifest says `surveyed: false` and the installer refuses
everything but the survey.
"""

import hashlib
import importlib.util
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
NAME = 'packages/k1-control-v1/start-load-recovery-v1/'
SENSOR = ROOT / 'packages/k1-control-v1/cfs-sensor-guard-v2/'
SURVEYED = None


def sha(data):
    return hashlib.sha256(data).hexdigest()


def installer():
    spec = importlib.util.spec_from_file_location('start_recovery_install',
                                                  PACKAGE / 'remote_install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    m = installer()
    sensor = json.loads((SENSOR / 'manifest.json').read_text(encoding='utf-8'))
    protected = dict(sensor['protected'])
    before = protected.pop(m.MODULE)
    protected[sensor['destination']] = sensor['sha256']
    manifest = {
        'schema': 1,
        'name': m.NAME,
        'adr': m.ADR,
        'document': 'docs/108-depart-repris-apres-chargement-stock-rate.md',
        'surveyed': SURVEYED is not None,
        'surveyed_on': SURVEYED,
        'source': NAME + 'kctrl_start.py',
        'destination': m.MODULE,
        'before_sha256': before,
        'sha256': sha((PACKAGE / 'kctrl_start.py').read_bytes()),
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
