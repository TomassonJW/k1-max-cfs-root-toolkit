"""Read-only, bounded startup samples; no G-code or motor command is sent.

Correlate with audit_live.py and a human observation of the extruder wheel.
Positions and velocity are firmware estimates, never proof of filament motion.
"""
import argparse
import datetime
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

OBJECTS = {
    'webhooks': ['state'], 'print_stats': ['state'],
    'extruder': ['target', 'temperature', 'can_extrude'],
    'heater_bed': ['target', 'temperature'],
    'gcode_move': ['absolute_coordinates', 'absolute_extrude', 'gcode_position', 'extrude_factor'],
    'toolhead': ['position', 'homed_axes', 'print_time', 'estimated_print_time'],
    'motion_report': ['live_position', 'live_extruder_velocity'],
    'tmc2209 extruder': ['run_current', 'hold_current', 'drv_status'],
    'stepper_enable': ['steppers'],
    'filament_switch_sensor filament_sensor': ['filament_detected', 'enabled'],
    'filament_switch_sensor filament_sensor_2': ['filament_detected', 'enabled'],
    'box': None,
}
QUERY = '/printer/objects/query?' + '&'.join(
    urllib.parse.quote(name) + ('' if fields is None else '=' + ','.join(fields))
    for name, fields in OBJECTS.items())


def clean_response(payload):
    result = payload['result']
    status = result['status']
    missing = [name for name in OBJECTS if name not in status]
    if missing:
        raise ValueError('missing objects: ' + ', '.join(missing))
    out = {'eventtime': result['eventtime'], 'objects': {}, 'unavailable_fields': []}
    for name, fields in OBJECTS.items():
        value = status[name]
        if name == 'box':
            out['objects'][name] = {
                k: value.get(k) for k in ('enable', 'state', 't_command')}
            for unit in ('T1', 'T2'):
                out['objects'][name][unit] = {
                    k: value.get(unit, {}).get(k) for k in ('state', 'filament')}
        else:
            absent = [key for key in fields if key not in value]
            if absent:
                raise ValueError('missing fields in ' + name + ': ' + ', '.join(absent))
            out['objects'][name] = {key: value[key] for key in fields}
            out['unavailable_fields'].extend(name + '.' + key for key in fields if value[key] is None)
    return out


def collect(base, output, seconds=30, interval=0.5):
    if not 1 <= seconds <= 900 or not 0.5 <= interval <= 5:
        raise ValueError('duration 1..900 seconds, interval 0.5..5 seconds')
    url = urllib.parse.urlsplit(base)
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
        raise ValueError('base URL only, without credentials or path')
    start = time.monotonic()
    count = 0
    # Refuse to overwrite an earlier capture, even after a failed sample.
    with Path(output).open('x', encoding='utf-8') as stream:
        while time.monotonic() - start < seconds:
            before = time.monotonic()
            request = urllib.request.Request(base.rstrip('/') + QUERY, method='GET')
            with urllib.request.urlopen(request, timeout=5) as response:
                data = response.read(524289)
            if len(data) > 524288:
                raise ValueError('oversized status response')
            sample = clean_response(json.loads(data))
            sample.update(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                          elapsed_seconds=round(time.monotonic() - start, 3),
                          request_seconds=round(time.monotonic() - before, 3))
            stream.write(json.dumps(sample) + '\n'); stream.flush()
            count += 1
            if count == 1 or count % 20 == 0:
                print('READ_ONLY_SAMPLES=%d' % count, flush=True)
            time.sleep(max(0, interval - (time.monotonic() - before)))
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--seconds', type=float, default=30)
    args = parser.parse_args()
    print('READ_ONLY_COMPLETE=%d' % collect(args.url, args.out, args.seconds), flush=True)
