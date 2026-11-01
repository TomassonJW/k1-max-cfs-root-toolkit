#!/usr/bin/env python3
"""Run remote_install.py on the printer in one mode; keep the answer locally.

    python deploy.py survey|preflight|install|validate|rollback

The candidate is the four components of packages/k1-control-v1/spool-manager-v1/
and the eight Bobines pages of packages/k1-control-v1/spool-choice-gate-v1/www/
bobines/, each checked against manifest.json before anything leaves the
workstation; only preflight and install carry them. The request travels on
stdin of `ssh k1max-root python3 -`: nothing is written on the printer by the
transport. Answers go to inventory/raw, which Git ignores.
"""

import base64
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
MANIFEST = PACKAGE / 'manifest.json'
INSTALLER = PACKAGE / 'remote_install.py'
RAW = ROOT / 'inventory/raw/20261101-spool-manager-install-v1'
HOST = 'k1max-root'
MODES = ('survey', 'preflight', 'install', 'validate', 'rollback')


def request(mode):
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    installer = INSTALLER.read_bytes()
    if hashlib.sha256(installer).hexdigest() != manifest['installer_sha256']:
        raise SystemExit('remote_install.py differs from manifest.json; rebuild the manifest')
    body = {'mode': mode, 'manifest': manifest}
    if mode in ('preflight', 'install'):
        payload = {}
        for entry in manifest['files']:
            data = (ROOT / entry['source']).read_bytes()
            if hashlib.sha256(data).hexdigest() != entry['sha256']:
                raise SystemExit(entry['source'] + ' differs from manifest.json; '
                                 'rebuild the manifest')
            payload[entry['destination']] = base64.b64encode(data).decode()
        body['payload'] = payload
    encoded = base64.b64encode(json.dumps(body).encode()).decode()
    return ('REQUEST_B64 = %r\n' % encoded).encode() + installer


def main(argv):
    if len(argv) != 2 or argv[1] not in MODES:
        raise SystemExit(__doc__)
    mode = argv[1]
    script = request(mode)
    result = subprocess.run(['ssh', HOST, 'python3 -'], input=script,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    RAW.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out = RAW / ('%s-%s.json' % (stamp, mode))
    out.write_text(json.dumps({
        'mode': mode, 'returncode': result.returncode,
        'stdout': result.stdout.decode(errors='replace'),
        'stderr': result.stderr.decode(errors='replace')[-4000:],
    }, indent=1), encoding='utf-8')
    sys.stdout.write(result.stdout.decode(errors='replace'))
    sys.stderr.write(result.stderr.decode(errors='replace')[-4000:])
    return result.returncode


if __name__ == '__main__':
    sys.exit(main(sys.argv))
