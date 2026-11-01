#!/usr/bin/env python3
"""Run remote_install.py on the printer in one mode; keep the answer locally.

    python deploy.py preflight|install|validate|rollback

No payload travels: the installer computes the one-digit change from the
file it reads and checks both fingerprints pinned in manifest.json, itself
checked here before anything leaves the workstation. The request travels on
stdin of `ssh k1max-root python3 -`: nothing is written on the printer by
the transport. Answers go to inventory/raw, which Git ignores.
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
HOST = 'k1max-root'
MODES = ('preflight', 'install', 'validate', 'rollback')


def request(mode):
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    installer = INSTALLER.read_bytes()
    if hashlib.sha256(installer).hexdigest() != manifest['installer_sha256']:
        raise SystemExit('remote_install.py differs from manifest.json; rebuild the manifest')
    body = {'mode': mode, 'manifest': manifest}
    encoded = base64.b64encode(json.dumps(body).encode()).decode()
    return ('REQUEST_B64 = %r\n' % encoded).encode() + installer


def main(argv):
    if len(argv) != 2 or argv[1] not in MODES:
        raise SystemExit(__doc__)
    mode = argv[1]
    script = request(mode)
    result = subprocess.run(['ssh', HOST, 'python3 -'], input=script,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    now = datetime.datetime.now()
    raw = ROOT / 'inventory/raw' / (now.strftime('%Y%m%d') + '-flash-log-level-v1')
    raw.mkdir(parents=True, exist_ok=True)
    out = raw / ('%s-%s.json' % (now.strftime('%Y%m%d-%H%M%S'), mode))
    out.write_text(json.dumps({'mode': mode, 'returncode': result.returncode,
                               'stdout': result.stdout.decode(errors='replace'),
                               'stderr': result.stderr.decode(errors='replace')[-4000:]},
                              indent=1), encoding='utf-8')
    sys.stdout.write(result.stdout.decode(errors='replace'))
    sys.stderr.write(result.stderr.decode(errors='replace')[-4000:])
    return result.returncode


if __name__ == '__main__':
    sys.exit(main(sys.argv))
