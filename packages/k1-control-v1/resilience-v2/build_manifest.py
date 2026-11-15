#!/usr/bin/env python3
"""Write manifest.json from the four candidates, the installer and the pins.

Targets: kctrl_start.py (before = the start-load-recovery-v1 code), the
print gate (before = the hash start-load-recovery-v1 pins) and the two page
files (before = what spool-manager-install-v1 left installed).

Pins: those of start-load-recovery-v1 minus the gate, now a target, plus
every page file this package does not replace, the Mainsail index that
injects the overlay included.

`REPINNED` holds the pins a survey found changed on the printer and that
were reviewed since: path -> hash. Until `SURVEYED` holds the date
`deploy.py survey` found everything as written here, the manifest says
`surveyed: false` and the installer refuses everything but the survey.
"""

import hashlib
import importlib.util
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
NAME = 'packages/k1-control-v1/resilience-v2/'
RECOVERY = ROOT / 'packages/k1-control-v1/start-load-recovery-v1/manifest.json'
PAGES = ROOT / 'packages/k1-control-v1/spool-manager-install-v1/manifest.json'
SOURCES = {'kctrl_start.py': 'kctrl_start.py',
           'kctrl_print_gate.py': 'kctrl_print_gate.py',
           'logic.js': 'www/bobines/logic.js',
           'bobines.js': 'www/bobines/bobines.js'}
REPINNED = {}
SURVEYED = '2026-11-15'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def installer():
    spec = importlib.util.spec_from_file_location('resilience_install',
                                                  PACKAGE / 'remote_install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    m = installer()
    recovery = json.loads(RECOVERY.read_text(encoding='utf-8'))
    pages = json.loads(PAGES.read_text(encoding='utf-8'))
    protected = dict(recovery['protected'])
    installed = {m.START: recovery['sha256'], m.GATE: protected.pop(m.GATE)}
    for entry in pages['files']:
        installed[entry['destination']] = entry['installed_sha256']
    targets = []
    for destination, kind in m.targets().items():
        source = SOURCES[Path(destination).name]
        entry = {'source': NAME + source, 'destination': destination, 'kind': kind,
                 'before_sha256': installed.pop(destination),
                 'sha256': sha((PACKAGE / source).read_bytes())}
        if kind == 'page':
            entry['mode'] = '0644'
        targets.append(entry)
    # Every page file left in place, and what the page is served through.
    for destination, value in sorted(installed.items()):
        if destination.startswith(m.WWW + '/'):
            protected[destination] = value
    for destination, value in sorted(pages['protected'].items()):
        if '/www/' in destination:
            protected[destination] = value
    protected.update(REPINNED)
    manifest = {
        'schema': 2,
        'name': m.NAME,
        'adr': m.ADR,
        'document': 'docs/111-relais-et-reprise-sans-impasse.md',
        'surveyed': SURVEYED is not None,
        'surveyed_on': SURVEYED,
        'targets': targets,
        'installer_sha256': sha((PACKAGE / 'remote_install.py').read_bytes()),
        # as_posix: built on Windows, compared on the printer.
        'backup': m.BACKUP.as_posix(),
        'head_record': m.HEAD_FILE,
        'effects': {'klipper_restart_idle_only': True, 'heating': False, 'motion': False,
                    'filament': False, 'config_change': False, 'printer_cfg_change': False},
        'protected': protected,
    }
    (PACKAGE / 'manifest.json').write_bytes(
        (json.dumps(manifest, indent=2, sort_keys=False) + '\n').encode('utf-8'))
    print(' '.join(entry['sha256'][:12] for entry in targets), manifest['installer_sha256'],
          len(protected), 'surveyed' if SURVEYED else 'not surveyed')


if __name__ == '__main__':
    main()
