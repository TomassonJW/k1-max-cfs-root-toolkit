"""End-of-print watch of the K1, versioned from the night of 1 November 2026.

Usage: python watch_end.py HOST [--keep-on-pause | --dry-run]

Reads only, through the private web gateway: while the file prints or
pauses, one objects/query every 30 s (5 s near the end or in pause), never
an action. Once the print is over, one read every 2 s for 15 min, then every
5 s up to 45 min; a stock PAUSE after the end does not end the watch, only a
new file printing does. It sends one emergency stop, then exits, when after
the end:
  - the cold-push guard refuses a push (cold_refused grows);
  - the bin guard refuses a move (denied grows);
  - the extruder moves forward by more than 1 mm while the K1 Control end
    is not in its own cut or rewind (stock BOX_CUT_MATERIAL and
    END_PRINT_NO_M84 run inside those phases);
  - the nozzle target stays at 170 C or more for 15 min with no end running.
The stop goes to Moonraker first, then straight to the Klipper socket over
SSH when Klipper is not in shutdown 6 s later. Both skip the G-code queue,
which a stock flush loop may hold. The E it reads is the planned position,
not the filament really pushed: the README gives the trapq count.

decide() holds every rule as a pure function of one read; watch() only
reads, logs, sleeps and stops. A failed read or an unreadable reply is
logged once, with its HTTP code (503: Klipper away from Moonraker), and the
watch keeps reading every 5 s.

Exit: 0 clean end, 10 failed end but quiet, 11 no owned end seen, 12 a new
print started, 20 stop confirmed, 21 stop not confirmed, 30 paused 2 min,
40 Klipper not ready, 50 gateway lost after the end, 60 no end by the
deadline. The dry run exits 0 when both reads and both stop paths answered,
1 otherwise; a wrong command line exits 2.
"""
import ctypes
import json
import shutil
import subprocess
import sys
import time
import urllib.request

PRINT = ('webhooks=state&print_stats=state&virtual_sdcard=is_active,progress'
         '&pause_resume=is_paused&kctrl_end=phase'
         '&kctrl_purge_guard=cold_refused,denied')
END = ('webhooks=state&print_stats=state&virtual_sdcard=is_active'
       '&pause_resume=is_paused&kctrl_end=phase,failure'
       '&kctrl_purge_guard=cold_refused,denied&extruder=temperature,target'
       '&toolhead=position')
REPORT = ('webhooks=state,state_message&print_stats=state,filename,message'
          '&kctrl_end=phase,failure'
          '&kctrl_purge_guard=cold_refused,denied,cold_last,last_error'
          '&extruder=temperature,target&heater_bed=target'
          '&toolhead=position,homed_axes'
          '&box=state,t_command,filament_useup,auto_refill')
ACTIVE = ('waiting', 'heating', 'cutting', 'rewinding', 'finalizing')
OVER = ('complete', 'error', 'cancelled', 'standby')
FORWARD_MM = 1.
HOT_C, HOT_S = 170., 15 * 60.
FAST_S, WINDOW_S, LONGEST_S = 15 * 60., 45 * 60., 90 * 60.
PAUSE_S = 120.
LIFETIME_S = 10 * 3600.
EXITS = {0: 'clean end', 10: 'failed end but quiet', 11: 'no owned end seen',
         12: 'a new print started', 20: 'stop confirmed', 21: 'stop not confirmed',
         30: 'paused 2 min', 40: 'Klipper not ready', 50: 'gateway lost after the end',
         60: 'no end by the deadline'}
USAGE = 'usage: python watch_end.py HOST [--keep-on-pause | --dry-run]'
# Runs on the K1 with its own python3: one webhooks request, no G-code.
SOCKET = r'''
import json, socket
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(5)
s.connect('/tmp/klippy_uds')
s.sendall(json.dumps({'id': 1, 'method': METHOD, 'params': {}}).encode() + b'\x03')
data = b''
while not data.endswith(b'\x03'):
    chunk = s.recv(4096)
    if not chunk:
        break
    data += chunk
reply = json.loads(data.rstrip(b'\x03') or b'{}')
result = reply.get('result')
print('error' if 'error' in reply else
      result.get('state', 'ok') if isinstance(result, dict) else 'ok')
'''
# Given on the command line only: the address never lives in a tracked file.
HOST = None


def log(text):
    """One timestamped line. Never raises: a console that cannot print one
    character, or a closed output, must not take the stop with it."""
    try:
        line = '%s %s' % (time.strftime('%H:%M:%S'), text)
        encoding = getattr(sys.stdout, 'encoding', None) or 'ascii'
        print(line.encode(encoding, 'backslashreplace').decode(encoding), flush=True)
    except Exception:
        pass


def cause(error):
    """Short name of a failed request, with its HTTP code when it has one."""
    name = type(error).__name__
    code = getattr(error, 'code', None)
    reason = getattr(error, 'reason', None)
    if isinstance(code, int):
        return '%s %d' % (name, code)
    if isinstance(reason, BaseException):
        return '%s %s' % (name, type(reason).__name__)
    return name


def read(query, timeout=8):
    url = 'http://%s:4409/printer/objects/query?%s' % (HOST, query)
    with urllib.request.urlopen(url, timeout=timeout) as reply:
        status = json.load(reply)['result']['status']
    # A reply that is not a set of objects is refused, never read as "nothing".
    if not isinstance(status, dict) or not all(isinstance(o, dict) for o in status.values()):
        raise ValueError('reply is not a status of objects')
    return status


def post(path):
    request = urllib.request.Request('http://%s:4409%s' % (HOST, path),
                                     data=b'', method='POST')
    with urllib.request.urlopen(request, timeout=5) as reply:
        return reply.read(160).decode('utf-8', 'replace')


def report(why):
    try:
        log('%s: %s' % (why, json.dumps(read(REPORT), sort_keys=True)))
    except Exception as error:
        log('%s: report unreadable %s' % (why, cause(error)))


def klipper(method):
    """One request straight to the Klipper socket over SSH; returns its word."""
    ssh = shutil.which('ssh')
    if ssh is None:
        return 'no ssh'
    script = ('METHOD = %r\n' % method + SOCKET).encode()
    try:
        done = subprocess.run(
            [ssh, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
             'k1max-root', 'python3', '-'],
            input=script, capture_output=True, timeout=40)
    except Exception as error:
        return 'ssh %s' % type(error).__name__
    word = done.stdout.decode('utf-8', 'replace').strip()
    return (word or 'exit %d' % done.returncode)[-80:]


def shutdown_within(seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            if read('webhooks=state', 3).get('webhooks', {}).get('state') == 'shutdown':
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def stop(reason):
    log('EMERGENCY STOP: %s' % reason)
    try:
        answer = post('/printer/emergency_stop')
    except Exception as error:
        log('moonraker stop failed %s' % cause(error))
    else:
        log('moonraker answered %s' % answer)
    if not shutdown_within(6):
        log('klipper socket stop: %s' % klipper('emergency_stop'))
        if not shutdown_within(10):
            report('stop not confirmed')
            return 21
    report('stopped')
    return 20


def keep_awake():
    # Idle sleep would end the watch: held for this process only.
    try:
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000001))
    except Exception:
        return False


def blind(mem, now):
    """Exit code while reads fail, or None to keep reading."""
    if mem['over'] is not None and now - mem['over'] >= LONGEST_S:
        return 50
    if now - mem['started'] >= LIFETIME_S:
        return 60
    return None


def decide(s, mem, now, keep_on_pause=False):
    """Every rule on one read, without any transport.

    Returns the new memory, the status line and the actions to run in order:
    ('report', why), ('log', line), ('stop', reason), ('exit', code) or
    ('sleep', seconds). The memory given is never changed.
    """
    mem = dict(mem)
    hooks = s.get('webhooks', {}).get('state')
    state = s.get('print_stats', {}).get('state')
    sd = s.get('virtual_sdcard', {}).get('is_active')
    is_paused = s.get('pause_resume', {}).get('is_paused') is True or state == 'paused'
    end = s.get('kctrl_end', {})
    phase = end.get('phase')
    guard = s.get('kctrl_purge_guard', {})
    counts = (guard.get('cold_refused'), guard.get('denied'))
    target = s.get('extruder', {}).get('target')
    key = 'klippy=%s print=%s sd=%s paused=%s end=%s/%s cold=%s denied=%s target=%s' % (
        hooks, state, sd, is_paused, phase, end.get('failure'), counts[0], counts[1],
        target)
    if hooks != 'ready':
        return mem, key, [('report', 'klipper not ready'), ('exit', 40)]
    actions = []
    # Unknown or missing fields keep the print running: never act on doubt.
    if mem['over'] is None:
        if state not in OVER or sd is not False:
            mem['base'] = counts
            if is_paused:
                if mem['paused'] is None:
                    mem['paused'] = now
                if not keep_on_pause and now - mem['paused'] >= PAUSE_S:
                    return mem, key, [('report', 'paused'), ('exit', 30)]
            else:
                mem['paused'] = None
            if now - mem['started'] >= LIFETIME_S:
                return mem, key, [('exit', 60)]
            progress = s.get('virtual_sdcard', {}).get('progress') or 0
            return mem, key, [('sleep', 5 if progress >= .97 or is_paused else 30)]
        mem['over'] = now
        if mem['base'] is None:
            mem['base'] = counts
        actions.append(('report', 'print over'))
    elif state in ('printing', 'paused') or sd is True:
        return mem, key, [('report', 'new print'), ('exit', 12)]
    active = phase in ACTIVE
    base = mem['base']
    reason = None
    if None not in counts and None not in base:
        if counts[0] > base[0]:
            # The END query has no cold_last: the report after the stop gives it.
            reason = 'cold push refused %d time(s)' % (counts[0] - base[0])
        elif counts[1] > base[1]:
            reason = 'bin move refused %d time(s)' % (counts[1] - base[1])
    position = s.get('toolhead', {}).get('position')
    e = position[3] if isinstance(position, list) and len(position) > 3 else None
    if active or type(e) not in (int, float):
        mem['e_ref'] = None
    elif mem['e_ref'] is None:
        mem['e_ref'] = e
    elif e > mem['e_ref'] + FORWARD_MM:
        reason = reason or 'extruder forward %.1f mm, end %s' % (e - mem['e_ref'], phase)
    else:
        mem['e_ref'] = min(mem['e_ref'], e)
    if not active and type(target) in (int, float) and target >= HOT_C:
        if mem['hot'] is None:
            mem['hot'] = now
            actions.append(('log', 'nozzle target %.0f C with no end running: 15 min count'
                            % target))
        elif now - mem['hot'] >= HOT_S:
            reason = reason or 'nozzle held at %.0f C for 15 min, end %s' % (target, phase)
    else:
        mem['hot'] = None
    if reason:
        return mem, key, actions + [('stop', reason)]
    elapsed = now - mem['over']
    if (elapsed >= WINDOW_S and not active) or elapsed >= LONGEST_S:
        code = 0 if phase == 'complete' else 10 if phase == 'failed' else 11
        return mem, key, actions + [('report', 'window over'), ('exit', code)]
    return mem, key, actions + [('sleep', 2 if elapsed < FAST_S else 5)]


def dry_run():
    """Both reads and both stop paths, without stopping anything."""
    failed = []
    for name, query in (('print', PRINT), ('end', END)):
        try:
            log('%s query: %s' % (name, json.dumps(read(query), sort_keys=True)))
        except Exception as error:
            log('%s query failed %s' % (name, cause(error)))
            failed.append('%s query' % name)
    report('report query')
    try:
        log('gateway POST: %s' % post('/printer/objects/query?webhooks=state'))
    except Exception as error:
        log('gateway POST: %s' % cause(error))
        failed.append('gateway POST')
    word = klipper('info')
    log('klipper socket over ssh (info): %s' % word)
    if word != 'ready':
        failed.append('klipper socket')
    log('dry run %s' % ('failed: ' + ', '.join(failed) if failed else 'ok'))
    return 1 if failed else 0


def watch(keep_on_pause):
    awake = keep_awake()
    log('start ssh=%s awake=%s keep_on_pause=%s' % (shutil.which('ssh'), awake, keep_on_pause))
    mem = {'started': time.time(), 'base': None, 'over': None, 'e_ref': None,
           'hot': None, 'paused': None}
    last = None
    while True:
        now = time.time()
        try:
            mem, key, actions = decide(read(PRINT if mem['over'] is None else END),
                                       mem, now, keep_on_pause)
        except Exception as error:
            # Blind: said once, never acted on, read again in 5 s.
            key = '%s %s' % ('unreachable' if isinstance(error, OSError) else 'unreadable',
                             cause(error))
            code = blind(mem, now)
            actions = [('sleep', 5)] if code is None else [('exit', code)]
        if key != last:
            log(key)
            last = key
        for action, value in actions:
            if action == 'report':
                report(value)
            elif action == 'log':
                log(value)
            elif action == 'stop':
                return stop(value)
            elif action == 'exit':
                return value
            else:
                time.sleep(value)


def main(argv):
    global HOST
    options = list(argv[2:])
    if len(argv) < 2 or not argv[1] or argv[1].startswith('-') or options not in (
            [], ['--keep-on-pause'], ['--dry-run']):
        print(USAGE, file=sys.stderr)
        return 2
    HOST = argv[1]
    if options == ['--dry-run']:
        return dry_run()
    code = watch(options == ['--keep-on-pause'])
    log('exit %d: %s' % (code, EXITS[code]))
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv))
