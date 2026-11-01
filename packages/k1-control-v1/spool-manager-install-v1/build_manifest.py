#!/usr/bin/env python3
"""Write manifest.json from the candidate, the installer and the survey.

Twelve files: the four components of the spool manager join K1 Control's
Moonraker, four Bobines pages are replaced and four are new. The earlier
pages are those of spool-choice-gate-v1 that the end and start packages pin
(end-separated-v1, retained-start-v1 and their successors). The hashes of
moonraker.conf and of the gateway, before and after the insertion,
and the protected files come from `deploy.py survey`, read at rest; until
they are filled in, the manifest says `surveyed: false` and the installer
refuses everything but the survey.
"""

import hashlib
import importlib.util
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
SPOOLS = 'packages/k1-control-v1/spool-manager-v1/'
PAGES = 'packages/k1-control-v1/spool-choice-gate-v1/www/bobines/'
COMPONENTS = ['kctrl_spools_store.py', 'kctrl_spools_model.py', 'kctrl_spools_counter.py',
              'kctrl_spools.py']
# None: the page does not exist yet on the printer.
PAGES_BEFORE = {
    'styles.css': 'fc20dcef4e4c0c1eee0f9a301de8d8b295fa795088df57e7534e8a58ea3abaa8',
    'bobines.js': '798621ae3e65405a6d51d8e1ab68e252c9c32bf7d43e51f1eeb0d2b41635ad7d',
    'logic.js': '927de5ad17e04f69fd5e7f6a49e9a3b5d2bef152666d4bde9034be4d618ed4a8',
    'overlay.js': '575e771297e4dbff15214e05ae88e956bbfec0d75107669a152ad2628e73f7fe',
    'spools.js': None,
    'spools-logic.js': None,
    'tares.json': None,
    'LICENSE-SpoolmanDB.txt': None,
}
# Read on the printer at rest by `deploy.py survey`; None until then.
SURVEY = {
    'moonraker_conf': {'before_sha256': None, 'sha256': None},
    'nginx': {'before_sha256': None, 'sha256': None},
    'protected': {},
}
# Document 102: Moonraker at most 45 MiB, at least 70 MiB left, swap +8 MiB at most.
BUDGET = {'rss_kb': 46080, 'available_kb': 71680, 'swap_growth_kb': 8192}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def installer():
    spec = importlib.util.spec_from_file_location('spool_install', PACKAGE / 'remote_install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    m = installer()
    files = [{'source': SPOOLS + name, 'destination': m.COMPONENTS + '/' + name,
              'before_sha256': None, 'sha256': sha(ROOT / SPOOLS / name), 'mode': '0644'}
             for name in COMPONENTS]
    files += [{'source': PAGES + name, 'destination': m.WWW + '/' + name,
               'before_sha256': before, 'sha256': sha(ROOT / PAGES / name), 'mode': '0644'}
              for name, before in PAGES_BEFORE.items()]
    surveyed = all(SURVEY[key][field] for key in ('moonraker_conf', 'nginx')
                   for field in ('before_sha256', 'sha256')) and bool(SURVEY['protected'])
    manifest = {
        'schema': 1,
        'name': m.NAME,
        'adr': 'ADR-075',
        'document': 'docs/102-gestion-des-bobines-plan-v1.md',
        'surveyed': surveyed,
        'files': files,
        'moonraker_conf': dict(SURVEY['moonraker_conf'], path=m.MOONRAKER_CONF,
                               section=m.SECTION.decode(), block=m.CONF_BLOCK.decode()),
        'nginx': dict(SURVEY['nginx'], path=m.NGINX_CONF, anchor=m.NGINX_ANCHOR.decode(),
                      block=m.NGINX_BLOCK.decode()),
        'state_dir': m.STATE_DIR,
        # as_posix: built on Windows, compared on the printer.
        'backup': m.BACKUP.as_posix(),
        'budget': BUDGET,
        'installer_sha256': sha(PACKAGE / 'remote_install.py'),
        'effects': {'moonraker_restart_idle_only': True, 'gateway_reload': True,
                    'klipper_restart': False, 'gcode': False, 'heating': False,
                    'motion': False, 'filament': False, 'cfs_write': False,
                    'printer_cfg_change': False},
        'protected': SURVEY['protected'],
    }
    (PACKAGE / 'manifest.json').write_bytes(
        (json.dumps(manifest, indent=2, sort_keys=False) + '\n').encode('utf-8'))
    print(manifest['installer_sha256'], 'surveyed' if surveyed else 'not surveyed')


if __name__ == '__main__':
    main()
