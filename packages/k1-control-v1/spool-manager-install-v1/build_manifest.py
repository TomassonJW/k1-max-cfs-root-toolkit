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
# Read on the printer at rest by `deploy.py survey`, 1 November 2026 at 19:33.
# The live gateway is the gateway-private-lan-no-auth-v1 nginx.conf; the
# Bobines package.json is not on the printer, so it is not pinned.
MOONRAKER = '/usr/data/k1-control-v1/current/moonraker/moonraker/moonraker/'
SURVEY = {
    'moonraker_conf': {
        'before_sha256': '2dbd34d7a89c40cd6664dce47999d5917a632c97be9954127deead709af1ec5e',
        'sha256': 'ed49f72ebeecb3eb10f32ba919853b312bc4d1b6f0745f4087fedf34de6b8483'},
    'nginx': {
        'before_sha256': '6d3ef270ee81a426c59aedcaa0c07d7ee067339050f94a8b30e5abecf74b9999',
        'sha256': '1b3bab181acbaed92e5228cd0d9499ea2d3d374a3233fbc4add26d646bb87347'},
    'protected': {
        MOONRAKER + 'moonraker.py':
            'c0111c255c60b3465798e4abf70de4492e1b16e016cebffe51c252a9cec94116',
        MOONRAKER + 'server.py':
            'fdb8aa99331acbd493d31b18643d4d6f8a54857009cd097e118f407e539184df',
        MOONRAKER + 'common.py':
            '9692a592a27206db3e17df3579b6e4686830222c83ce74ea5cc450543bf0e905',
        MOONRAKER + 'confighelper.py':
            '5513d654bd7facb20c00369590661255a496c61c5097aa40e9c5aa622b4e08f6',
        MOONRAKER + 'eventloop.py':
            'ae8ca4f7bab170ead3333abebf455e9c8ce258462cd6a352489f767f0b63c1f9',
        MOONRAKER + 'components/klippy_connection.py':
            '23f8fad5fc7a83b1787587624328cd534fb90a8dc5c29c56d501afd2206737f2',
        MOONRAKER + 'utils/__init__.py':
            'f9252faa005cfb31993d48c2ef87a2f31422e9944a079d759e8a82ff1e566c3b',
        MOONRAKER + 'components/klippy_apis.py':
            '59887a8982f59b7a3be9bf5a13f7b41559b2921011e3298788fb53d3bd60f22a',
        '/etc/init.d/S56k1_control_moonraker':
            'c0ba49e10b05ea5d43a90c74413efba142ed302b2f11aeb8fc581ac675f94d4e',
        '/etc/init.d/S57k1_control_gateway':
            'ba82fb803641dd190de9909ea3270be9c2024f645c41ea59ff1411084107e34b',
        '/usr/data/k1-control-v1/state/mainsail_overlay_patch.py':
            'db2d94d17b34796373bd62e7edadf7c196daaa7772da687aa843640dd61b1c54',
        '/usr/data/k1-control-v1/current/www/mainsail/index.html':
            'ab7237694495207f7deccd1a825c0daaba8d6f1123ddfaf804c0251f9e2bf4df',
        '/usr/data/k1-control-v1/current/www/bobines/app.js':
            '520a3fc0c4329b61f4e6f82f88cd0155a422ceb4a165c0d6438cf9352b2465c7',
        '/usr/data/k1-control-v1/current/www/bobines/index.html':
            '83209ebacbbdb97ecf6fcd0db404a7f25237a25496b605b2a7748c4d45a6b309',
        '/usr/data/printer_data/config/k1-control-owned-start-print-v2.cfg':
            '61bd5f6519a5387eb233a30de6ee9a84d86de7ea88593d5c9cc35b288215d6e9',
        '/usr/share/klipper/klippy/extras/kctrl_print_gate.py':
            '69578e579409b7c4d253acb8c680ceaeb25b60b40502732530a4a786e0966516',
    },
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
