#!/usr/bin/env python3
"""Measure the K1 flash write rate, read only, and print it in Mo/min.

    python mesure.py [samples] [interval_s]          (61 x 10 s by default)

The counters of document 103: sectors written on /usr/data (mmcblk0p10, in
/proc/diskstats), the growth of the Creality, Klipper and Moonraker logs,
the print state, the level written in log_config.json and the uptime, which
tells whether the programs have been restarted since the change. The script
travels on stdin of `ssh k1max-root nice -n 19 sh -s`: nothing is written on
the printer, no Klipper command, no redirection, and the Klipper log is only
measured by `stat`, never read (document 81). A 10 minute measure belongs in
a command started in the background.
"""

import datetime
import json
from pathlib import Path
import subprocess
import sys

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
HOST = 'k1max-root'

REMOTE = r"""
L=/usr/data/creality/userdata/log
K=/usr/data/printer_data/logs/klippy.log
F="$L/master-server.log $L/display-server.log $L/app-server.log $L/web-server.log $K /usr/data/k1-control-v1/logs/moonraker.log"
Q='http://127.0.0.1:7125/printer/objects/query?print_stats=state'
echo "== etat $(curl "$Q")"
echo "== niveau $(grep -o '"log_level":[0-9]' $L/log_config.json)"
i=0
while [ $i -lt $1 ]; do
  echo "== t $(cut -d' ' -f1 /proc/uptime)"
  grep ' mmcblk0p10 ' /proc/diskstats
  stat -c '%s %i %n' $F
  i=$((i+1))
  [ $i -lt $1 ] && sleep $2
done
echo "== etat $(curl "$Q")"
echo "== fin"
"""


def parse(text):
    samples, states, level = [], [], None
    for line in text.splitlines():
        if line.startswith('== t '):
            samples.append({'t': float(line.split()[2]), 'files': {}})
        elif line.startswith('== etat '):
            try:
                states.append(json.loads(line[8:])['result']['status']['print_stats']['state'])
            except (ValueError, KeyError, TypeError):
                states.append(None)
        elif line.startswith('== niveau '):
            digits = line.rsplit(':', 1)[-1].strip()
            level = int(digits) if digits.isdigit() else None
        elif samples:
            fields = line.split()
            if len(fields) >= 14 and fields[2] == 'mmcblk0p10':
                samples[-1]['writes'] = int(fields[7])
                samples[-1]['sectors'] = int(fields[9])
            elif len(fields) == 3 and fields[2].startswith('/usr/data/'):
                samples[-1]['files'][fields[2].rsplit('/', 1)[1]] = (int(fields[0]), int(fields[1]))
    return samples, states, level


def rates(samples):
    """Rates between the first and the last sample.

    A log that rotates between two samples counts its new size only: the
    last lines of the rotated file are lost, the rate is a lower bound.
    """
    first, last = samples[0], samples[-1]
    seconds = last['t'] - first['t']
    assert seconds > 0, 'measure_too_short'
    logs = {}
    for name in first['files']:
        grown, rotated = 0, False
        for before, after in zip(samples, samples[1:]):
            if name not in before['files'] or name not in after['files']:
                continue
            size0, inode0 = before['files'][name]
            size1, inode1 = after['files'][name]
            if inode1 == inode0:
                grown += size1 - size0
            else:
                grown += size1
                rotated = True
        logs[name] = {'ko_min': round(grown / seconds * 60 / 1000, 1), 'rotated': rotated}
    written = (last['sectors'] - first['sectors']) * 512
    text = sum(max(value['ko_min'], 0) for value in logs.values()) * 1000
    return {'seconds': round(seconds, 1),
            'uptime_s': round(first['t']),
            'flash_mo_min': round(written / seconds * 60 / 1e6, 1),
            'writes_per_s': round((last['writes'] - first['writes']) / seconds, 1),
            'logs': logs,
            'amplification': round(written / seconds * 60 / text) if text else None}


def main(argv):
    count = int(argv[1]) if len(argv) > 1 else 61
    interval = int(argv[2]) if len(argv) > 2 else 10
    assert count >= 2 and interval >= 1, 'at least two samples'
    result = subprocess.run(['ssh', HOST, 'nice -n 19 sh -s -- %d %d' % (count, interval)],
                            input=REMOTE.encode(), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=count * (interval + 5) + 60)
    text = result.stdout.decode(errors='replace')
    samples, states, level = parse(text)
    summary = (dict(rates(samples), states=states, log_level=level) if len(samples) >= 2
               else {'error': 'fewer_than_two_samples', 'samples': len(samples)})
    now = datetime.datetime.now()
    raw = ROOT / 'inventory/raw' / (now.strftime('%Y%m%d') + '-flash-log-level-v1')
    raw.mkdir(parents=True, exist_ok=True)
    (raw / ('%s-mesure.json' % now.strftime('%Y%m%d-%H%M%S'))).write_text(json.dumps(
        {'summary': summary, 'returncode': result.returncode, 'stdout': text,
         'stderr': result.stderr.decode(errors='replace')[-4000:]}, indent=1),
        encoding='utf-8')
    print(json.dumps(summary, indent=1))
    return result.returncode


if __name__ == '__main__':
    sys.exit(main(sys.argv))
