#!/usr/bin/env python3
"""Write manifest.json from a local copy of the printer file and the installer.

    python build_manifest.py <local copy of log_config.json>

The copy comes from the read-only capture of 31 October 2026 (document 103,
`20261031-flash-writes-audit-v1`, outside Git): the vendor file itself is not
versioned, only its fingerprints. The candidate is computed by the installer's
own edit, so the pinned result is exactly what the printer will compute.
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def installer():
    spec = importlib.util.spec_from_file_location('flash_log_level_install',
                                                  PACKAGE / 'remote_install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv):
    if len(argv) != 2:
        raise SystemExit(__doc__)
    before = Path(argv[1]).read_bytes()
    module = installer()
    after = module.edited(before)
    manifest = {
        'schema': 1,
        'name': module.NAME,
        'document': 'docs/103-ecritures-flash-cause-usure-parade.md',
        'destination': module.TARGET,
        'size': len(before),
        'before_sha256': sha(before),
        'sha256': sha(after),
        'installer_sha256': sha((PACKAGE / 'remote_install.py').read_bytes()),
        'backup': str(module.BACKUP).replace('\\', '/'),
        'effects': {'klipper_restart': False, 'service_restart': False, 'reboot': False,
                    'heating': False, 'motion': False, 'filament': False,
                    'klipper_config_change': False, 'creality_log_level': [1, 3]},
    }
    (PACKAGE / 'manifest.json').write_bytes(
        (json.dumps(manifest, indent=2, sort_keys=False) + '\n').encode('utf-8'))
    print(manifest['before_sha256'], manifest['sha256'], manifest['installer_sha256'])


if __name__ == '__main__':
    main(sys.argv)
