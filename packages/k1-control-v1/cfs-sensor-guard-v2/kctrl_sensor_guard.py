"""CFS sensor guard: a contradicted slot sensor never becomes a pause and a purge.

ADR-078, document 107; it replaces the cut of ADR-077 (document 105).
Disabled by default. Enabled, it requires the owned end of kctrl_end
(end-no-stock-flush-v5) enabled too, or it refuses at klippy:ready. Nothing is
read from the CFS link: the guard listens to the CFS lines the stock module
already writes to the Klipper log, through a handler on the root logger. It
writes one thing only, the stock auto refill, back to 1.

On 12 November 2026 the V1 guard marked T1B at 04:25:06 and switched the auto
refill off. At 06:04:09 the CFS reported FILAMENT_ERR on T1B again, key839
"no filament detected at box extrude position", while its connections mask
still held B. With the refill off, the stock module paused the print, pushed
3000 mm into the bin ("extrude all material") and left the CFS idle
(mode 0): no slack, nothing came out on the first resume. The same false
error with the refill on, at 04:22:06 that night, on 1 November at 07:07 and
on 31 October at 19:01, left the print running. Cutting the refill during a
print turned a harmless false error into a lost hour and a lost spool.

1. During the print, a filament report on the live slot still not proven real
   after episode_seconds and episode_printed_mm, head loaded, marks the job:
   one console line, nothing written.
2. During the print, an auto refill read at 0 for KEEP_SECONDS is put back to
   1 under the G-code mutex, proven by two reads (keep_auto_refill, on by
   default). Never in a pause, never once the file has ended: the owned end
   cuts the refill itself before its cut (ADR-076).
3. The next START_PRINT reads the auto refill at 1 or puts it back, proven by
   two reads, or refuses the start.
4. In a pause with the file open, after a key839 or a filament report on the
   slot that was printing, a connections mask that still holds the slot is a
   false end: one console line says so and how to resume. A CFS read idle
   (mode 0) in that pause gets one line with the BOX_SET_BOX_MODE that gives
   the slack back. Nothing is done to the stock routine or to the mode.
5. After the end of the file, a net push above end_push_limit outside the
   pushing phases of the owned end is an emergency stop, raised before the
   move is queued. KCTRL_SENSOR_GUARD_RELEASE lifts it for a manual push.

kctrl_end fails its own end on a console line that starts with '!!' or holds
the word failed: no console line written here does either, and RELEASE and
STATUS answer without raising.
"""

import collections
import logging
import math
import re

REVISION = 'cfs-sensor-guard-v2'
BITS = {'A': 1, 'B': 2, 'C': 4, 'D': 8}
FILAMENT_ERR = 0x50
STATE_OK = 0x0
# Same as kctrl_end.ACTIVE.
END_ACTIVE = ('waiting', 'heating', 'cutting', 'rewinding', 'finalizing')
# Owned end phases that may push: BOX_CUT_MATERIAL, the separated rewind and
# END_PRINT_NO_M84 with BOX_END. A new pushing phase of kctrl_end goes here.
END_PUSH_PHASES = ('cutting', 'rewinding', 'finalizing')
END_STATES = ('complete', 'cancelled', 'error', 'standby')
IDLE_MODES = ('0', 0)
QUIET_SECONDS = 15.
KEEP_SECONDS = 30.
KEEP_RETRY_SECONDS = 10.
# A key839 or a report this long before the pause still explains it.
PAUSE_LOOKBACK = 60.
TICK = 1.
STEP_LIMIT = 100.
FAILURE_LOG_SECONDS = 60.

HEADER = re.compile(r'^\[[A-Z]+\] \S+ \S+ \[[^\]]*\] \[[^\]]*\] ')
# State reply: header, address, size 7, status, command 0xa. Frames that carry
# identifiers have another command or size and never match.
REPLY = re.compile(r'^msg: 0xf7 0x([0-9a-f]{1,2}) 0x([0-9a-f]{1,2}) 0x([0-9a-f]{1,2}) 0x([0-9a-f]{1,2})(?: |$)')
TNN = re.compile(r"(?:^|[ {])'?tnn'?: '?(T[1-4][A-D])")
MASK = re.compile(r'^Tn_inner_data\[T([1-4])\]\[filament_sensor\]\[(connections|material)\]: (\d+)$')
# Alone on its line after a real runout; the purge forms carry a velocity.
TAIL = re.compile(r'^extrude = (-?\d+(?:\.\d+)?)$')
KEY839 = re.compile(r'"values":\s*\[\s*([1-4])\s*,\s*"([A-D])"\s*\]')
KEY839_PREFIX = '!! {"code":"key839"'
NAMED = ('recode_err: filament_err', 'error: filament_err')
PURGE_START = 'extrude all material'
PURGE_STOP = 'extrude more than'
PREFIXES = (('msg: 0xf7 ', 'filament_err_tighten_up_event', 'Tn_inner_data[', 'extrude = ',
             KEY839_PREFIX, PURGE_START, PURGE_STOP) + NAMED)

TRIP_MESSAGE = "K1 Control: poussee de filament apres la fin, arret d'urgence"
WINDOW_MESSAGE = ('K1 Control: fin du fichier, garde de fin active %d min. Une poussee de filament '
                  'hors des etapes de fin arrete la machine. KCTRL_SENSOR_GUARD_RELEASE avant une '
                  'poussee a la main.')
MARK_MESSAGE = ('K1 Control: capteur du slot %s contredit (%d s, %d mm imprimes, tete chargee). '
                'Auto-remplacement CFS laisse actif : une coupure en impression changerait une '
                'fausse erreur en pause et purge (document 106).')
KEEP_MESSAGES = {
    'confirmed': 'K1 Control: auto-remplacement CFS lu a 0 en impression, remis a 1 et relu '
                 '(document 106).',
    'unconfirmed': 'K1 Control: auto-remplacement CFS lu a 0 en impression, commande a 1 sans '
                   'relecture a 1, nouvel essai toutes les %d s.' % KEEP_RETRY_SECONDS,
    'error': 'K1 Control: auto-remplacement CFS lu a 0 en impression, remise a 1 impossible '
             '(voir le journal), nouvel essai toutes les %d s.' % KEEP_RETRY_SECONDS}
START_REFUSED = 'K1 Control: auto-remplacement CFS lu a 0 et non remis a 1, depart refuse'
FALSE_END_MESSAGE = ('K1 Control: pause sur fausse fin probable de %s, la case reste vue par le '
                     'CFS. Si la routine stock purge au bac, attendre sa fin. Avant reprise : '
                     'lire box.T%s.mode ; s\'il vaut 0, BOX_SET_BOX_MODE ADDR=%s MODE=PRINT NUM=%s '
                     '(document 106).')
IDLE_MESSAGE = ('K1 Control: CFS %s au repos (mode 0) pendant la pause, sans mou rien ne sortira. '
                'Avant purge ou reprise : BOX_SET_BOX_MODE ADDR=%s MODE=PRINT NUM=%s '
                '(document 106).')
BLIND_MESSAGES = {
    'no_cfs_reply': 'K1 Control: garde capteur aveugle, aucune reponse du CFS depuis %d s',
    'log_level': 'K1 Control: garde capteur aveugle, niveau du journal au-dessus de INFO'}
STATUS_HELP = 'K1 Control: etat de la garde capteur CFS'
RELEASE_HELP = 'K1 Control: leve la garde de fin avant une poussee a la main'


def parse(text):
    """One log line to an event tuple, or None."""
    if text.startswith('['):
        match = HEADER.match(text)
        if match is None:
            return None
        text = text[match.end():]
    text = text.rstrip()
    if not text.startswith(PREFIXES):
        return None
    match = REPLY.match(text)
    if match:
        addr, size, status, cmd = (int(group, 16) for group in match.groups())
        if cmd != 0xa or size != 7 or not 1 <= addr <= 4:
            return None
        return ('reply', 'T%d' % addr, status)
    if text.startswith(NAMED):
        match = TNN.search(text)
        return ('named', match.group(1)) if match else None
    if text.startswith(KEY839_PREFIX):
        match = KEY839.search(text)
        return ('key839', 'T%s%s' % match.groups()) if match else None
    if text.startswith(PURGE_START):
        return ('purge', 'start')
    if text.startswith(PURGE_STOP):
        return ('purge', 'stop')
    if text.startswith('filament_err_tighten_up_event'):
        return ('tension',)
    match = MASK.match(text)
    if match:
        return ('mask', 'T' + match.group(1), match.group(2), int(match.group(3)))
    match = TAIL.match(text)
    if match:
        return ('tail', float(match.group(1)))
    return None


def engaged_route(box, boxes=2):
    """kctrl_end.live_route without raising: (route, '') or (None, reason)."""
    if not isinstance(box, dict) or box.get('enable') != 1 or box.get('state') != 'connect':
        return None, 'cfs_not_ready'
    routes = []
    for number in range(1, 5):
        unit = box.get('T%d' % number)
        if number <= boxes:
            if not isinstance(unit, dict) or unit.get('state') != 'connect':
                return None, 'cfs_unit_missing'
        elif not unit:
            continue
        elif not isinstance(unit, dict):
            return None, 'unexpected_cfs_unit'
        elif unit.get('state') in (None, 'None', 'disconnect'):
            continue
        else:
            return None, 'unexpected_cfs_unit'
        slot = unit.get('filament', '__missing__')
        if slot == 'None':
            continue
        if slot not in BITS:
            return None, 'cfs_route_unknown'
        routes.append('T%d%s' % (number, slot))
    if len(routes) > 1:
        return None, 'cfs_routes_ambiguous'
    if not routes:
        return None, 'no_route'
    return routes[0], ''


class SensorWatch:
    """Episodes per slot from timed events; no Klipper object, no clock.

    A filament report opens an episode. A connections mask without the slot,
    or a tail line, makes it real: the spool really ran out. A material mask
    without the slot only opens one: on 31 October it said A was missing while
    T1A printed. An episode still suspect after episode_seconds and
    episode_mm printed with a loaded head marks the job, once per job.
    """

    def __init__(self, episode_seconds=180., episode_mm=400., blind_seconds=60.):
        self.episode_seconds = episode_seconds
        self.episode_mm = episode_mm
        self.blind_seconds = blind_seconds
        self.units = dict(('T%d' % number, {'reply': None, 'ok': 0, 'conn': None, 'mat': None,
                                            'lack': {}}) for number in range(1, 5))
        self.episodes = {}
        self.closed = 0
        self.route = None
        self.route_since = None
        self.printing_since = None
        self.prev = None
        self.marked = None
        self.blind = None
        self.blind_told = False
        self.job_start = 0.

    @staticmethod
    def _real(episode, t):
        if not episode['real']:
            episode['real'], episode['real_at'] = True, t

    def _open(self, slot, start, reason, seen=None):
        start = max(start, self.job_start)
        episode = self.episodes.get(slot)
        if episode is None:
            episode = self.episodes[slot] = {'start': start, 'last': start, 'reasons': set(),
                                             'real': False, 'real_at': None, 'printed': 0.}
            conn = self.units[slot[:2]]['conn']
            if conn is not None and conn[0] >= start and not conn[1] & BITS[slot[2]]:
                self._real(episode, conn[0])
        episode['last'] = max(episode['last'], start if seen is None else seen)
        episode['reasons'].add(reason)
        return episode

    def lacking(self, slot, now):
        mat = self.units[slot[:2]]['mat']
        return mat is not None and now - mat[0] <= QUIET_SECONDS and not mat[1] & BITS[slot[2]]

    def feed(self, t, event):
        kind, route = event[0], self.route
        # A slot-less report belongs to the live route only once it was seen.
        fresh = route is not None and t >= max(self.route_since, self.job_start)
        if kind == 'reply':
            unit = self.units[event[1]]
            unit['reply'] = t
            if event[2] == FILAMENT_ERR:
                unit['ok'] = 0
                if fresh and route[:2] == event[1]:
                    self._open(route, t, 'filament_err')
            elif event[2] == STATE_OK:
                unit['ok'] += 1
        elif kind in ('named', 'key839'):
            if t >= self.job_start:
                self._open(event[1], t, kind)
        elif kind == 'tension':
            if fresh:
                self._open(route, t, 'tension')
        elif kind == 'mask':
            unit, value = self.units[event[1]], event[3]
            if event[2] == 'material':
                stale = unit['mat'] is None or t - unit['mat'][0] > QUIET_SECONDS
                for letter, bit in BITS.items():
                    if value & bit:
                        unit['lack'].pop(letter, None)
                    elif stale or letter not in unit['lack']:
                        unit['lack'][letter] = t
                unit['mat'] = (t, value)
            else:
                unit['conn'] = (t, value)
                for slot, episode in self.episodes.items():
                    if slot[:2] == event[1] and t >= episode['start'] and not value & BITS[slot[2]]:
                        self._real(episode, t)
        elif kind == 'tail':
            if fresh:
                self._real(self._open(route, t, 'tail'), t)

    def tick(self, now, printing, route, head, e, events, listening=True):
        """One guard tick; returns [('mark', dict)] and [('blind', reason)] outputs."""
        out = []
        if route != self.route or self.route_since is None:
            self.route, self.route_since, self.prev = route, now, None
        if not printing:
            self.printing_since = self.prev = None
        elif self.printing_since is None:
            self.printing_since = now
        for t, event in events:
            self.feed(t, event)
        if route is not None and self.lacking(route, now):
            lack = self.units[route[:2]]['lack'].get(route[2], now)
            self._open(route, max(lack, self.route_since), 'material', now)
        live = self.episodes.get(route)
        if printing and e is not None:
            if self.prev is None or e < self.prev - STEP_LIMIT:
                self.prev = e
            elif e > self.prev:
                # High-water mark: a retraction and its recovery count once.
                if live is not None and not live['real']:
                    live['printed'] += min(e - self.prev, STEP_LIMIT)
                self.prev = e
        for slot in list(self.episodes):
            unit, episode = self.units[slot[:2]], self.episodes[slot]
            if (unit['ok'] >= 2 and now - episode['last'] > QUIET_SECONDS
                    and (unit['conn'] is None or now - unit['conn'][0] > QUIET_SECONDS)
                    and not self.lacking(slot, now)):
                del self.episodes[slot]
                self.closed += 1
        blind = None
        if not listening:
            blind = 'log_level'
        elif printing and route is not None:
            seen = [t for t in (self.units[route[:2]]['reply'], self.printing_since, self.route_since)
                    if t is not None]
            if now - max(seen) > self.blind_seconds:
                blind = 'no_cfs_reply'
        self.blind = blind
        if blind is not None and printing and not self.blind_told:
            self.blind_told = True
            out.append(('blind', blind))
        live = self.episodes.get(route)
        if (self.marked is None and printing and head is True and blind is None
                and live is not None and not live['real']
                and now - live['start'] >= self.episode_seconds
                and live['printed'] >= self.episode_mm):
            self.marked = {'slot': route, 'at': now, 'seconds': now - live['start'],
                           'printed': live['printed'], 'reasons': sorted(live['reasons'])}
            out.append(('mark', dict(self.marked)))
        return out

    def reset(self, now):
        """New job: real episodes are forgotten, suspect ones restart from zero."""
        for slot in list(self.episodes):
            if self.episodes[slot]['real']:
                del self.episodes[slot]
            else:
                self.episodes[slot] = {'start': now, 'last': now, 'reasons': {'carried'},
                                       'real': False, 'real_at': None, 'printed': 0.}
        self.job_start = now
        self.marked = None
        self.blind_told = False
        self.printing_since = self.prev = None


class LineTap(logging.Handler):
    """Root logger handler that keeps parsed CFS events only.

    Root handlers run synchronously in the logging thread: this one parses,
    appends to a bounded queue and never raises.
    """
    kctrl_sensor_tap = True

    def __init__(self, clock, size=1000):
        logging.Handler.__init__(self, logging.INFO)
        self.clock = clock
        self.queue = collections.deque(maxlen=size)
        self.seen = 0
        self.dropped = 0

    def emit(self, record):
        try:
            for line in record.getMessage().split('\n'):
                event = parse(line)
                if event is None:
                    continue
                if len(self.queue) == self.queue.maxlen:
                    self.dropped += 1
                self.queue.append((self.clock(), event))
                self.seen += 1
        except Exception:
            pass

    def handleError(self, record):
        pass

    def drain(self):
        events = []
        while True:
            try:
                events.append(self.queue.popleft())
            except IndexError:
                return events


class KctrlSensorGuard:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        # Read every option, even disabled: Klipper refuses an unread one.
        self.enabled = config.getboolean('enabled', False)
        self.boxes = config.getint('boxes', 2, minval=1, maxval=4)
        episode_seconds = config.getfloat('episode_seconds', 180., minval=60., maxval=3600.)
        episode_mm = config.getfloat('episode_printed_mm', 400., minval=100., maxval=5000.)
        blind_seconds = config.getfloat('blind_seconds', 60., minval=20., maxval=600.)
        self.end_window = config.getfloat('end_window', 900., minval=60., maxval=3600.)
        self.push_limit = config.getfloat('end_push_limit', 1., minval=.5, maxval=10.)
        self.refill_timeout = config.getfloat('auto_refill_timeout', 3., minval=.5, maxval=10.)
        self.keep = config.getboolean('keep_auto_refill', True)
        self.watch = SensorWatch(episode_seconds, episode_mm, blind_seconds)
        self.tap = LineTap(self.reactor.monotonic)
        self.installed = False
        self.shutdown = False
        self.inner = None
        self.original = None
        self.timer = None
        self.job = 0
        self.keep_pending = False
        self.zero_since = None
        self.last_keep = None
        self.keep_outcome = None
        self.keep_told = False
        self.kept = 0
        self.pause = None
        self.false_end = None
        self.idle_told = None
        self.last_slot = None
        self.key839 = None
        self.stock_purge = None
        self.armed = False
        self.ended = False
        self.window = None
        self.until = None
        self.level = 0.
        self.closed_by = ''
        self.tripped = False
        self.trip = None
        self.failure = ''
        self.failure_logged = None
        self.route = None
        self.route_reason = ''
        self.print_stats = self.sd = self.box = self.toolhead = None
        self.extruder = self.head = self.end_owner = self.cold = None
        if not self.enabled:
            return
        self.printer.register_event_handler('klippy:ready', self._ready)
        self.printer.register_event_handler('klippy:shutdown', self._shutdown)
        self.printer.register_event_handler('klippy:disconnect', self._disconnect)

    def _ready(self):
        if self.installed:
            return
        found = {}
        for name in ('print_stats', 'virtual_sdcard', 'box', 'toolhead', 'extruder',
                     'filament_switch_sensor filament_sensor_2', 'kctrl_end'):
            found[name] = self.printer.lookup_object(name, None)
            if found[name] is None:
                raise self.printer.config_error('kctrl_sensor_guard: missing ' + name)
        # Without the owned end, the stock end pushes after the file: rule 5
        # would stop every print.
        if getattr(found['kctrl_end'], 'enabled', None) is not True:
            raise self.printer.config_error('kctrl_sensor_guard: kctrl_end not enabled')
        if not callable(self.gcode.ready_gcode_handlers.get('BOX_ENABLE_AUTO_REFILL')):
            raise self.printer.config_error('kctrl_sensor_guard: missing primitive BOX_ENABLE_AUTO_REFILL')
        self.print_stats, self.sd = found['print_stats'], found['virtual_sdcard']
        self.box, self.toolhead, self.extruder = found['box'], found['toolhead'], found['extruder']
        self.head = found['filament_switch_sensor filament_sensor_2']
        self.end_owner = found['kctrl_end']
        self.cold = self.printer.lookup_object('kctrl_purge_guard', None)
        # Atomic: any failure undoes every earlier step, in reverse.
        undo = []
        try:
            original = self.gcode.register_command('START_PRINT', None)
            if original is None:
                raise self.printer.config_error('kctrl_sensor_guard: missing START_PRINT')
            undo.append(lambda: self.gcode.register_command('START_PRINT', original))
            self.gcode.register_command('START_PRINT', self.cmd_START_PRINT)
            undo.append(lambda: self.gcode.register_command('START_PRINT', None))
            self.original = original
            self._hook()
            undo.append(self._unhook)
            for name, handler, desc in (
                    ('KCTRL_SENSOR_GUARD_STATUS', self.cmd_KCTRL_SENSOR_GUARD_STATUS, STATUS_HELP),
                    ('KCTRL_SENSOR_GUARD_RELEASE', self.cmd_KCTRL_SENSOR_GUARD_RELEASE, RELEASE_HELP)):
                self.gcode.register_command(name, handler, desc=desc)
                undo.append(lambda name=name: self.gcode.register_command(name, None))
            root = logging.getLogger()
            # A RESTART keeps the process and its root handlers.
            for handler in list(root.handlers):
                if getattr(handler, 'kctrl_sensor_tap', False):
                    root.removeHandler(handler)
            root.addHandler(self.tap)
            undo.append(lambda: root.removeHandler(self.tap))
            self.timer = self.reactor.register_timer(self._tick, self.reactor.NOW)
        except Exception:
            for step in reversed(undo):
                try:
                    step()
                except Exception:
                    logging.exception('kctrl_sensor_guard: undo step lost')
            self.original = None
            raise
        self.installed = True

    def _hook(self):
        # Inside the cold guard when it is already there: its own status keeps
        # reading cold_installed, and this check runs before its cold check.
        cold = self.cold
        if cold is not None and self.extruder.check_move == getattr(cold, 'check_extrude', None):
            self.inner = cold.original_extrude_check
            cold.original_extrude_check = self.check_extrude
        else:
            self.inner = self.extruder.check_move
            self.extruder.check_move = self.check_extrude

    def _unhook(self):
        cold = self.cold
        if cold is not None and getattr(cold, 'original_extrude_check', None) == self.check_extrude:
            cold.original_extrude_check = self.inner
        elif self.extruder.check_move == self.check_extrude:
            self.extruder.check_move = self.inner

    def _hook_state(self):
        if self.extruder is None or self.toolhead.get_extruder() is not self.extruder:
            return ''
        if self.extruder.check_move == self.check_extrude:
            return 'direct'
        cold = self.cold
        if (cold is not None and self.extruder.check_move == getattr(cold, 'check_extrude', None)
                and getattr(cold, 'original_extrude_check', None) == self.check_extrude):
            return 'inside_cold_guard'
        return ''

    def check_extrude(self, move):
        self.inner(move)
        push = move.axes_d[3]
        if self.tripped:
            if push > 0.:
                raise self.printer.command_error(TRIP_MESSAGE)
            return
        if self.sd.is_active():
            if self.window is not None:
                self._close_window('new_print')
            self.armed = True
            return
        now = self.reactor.monotonic()
        if self.window is None:
            if not self.armed or not self._ended(now):
                return
            self._open_window(now, 'push')
        phase = getattr(self.end_owner, 'phase', None)
        if phase in END_PUSH_PHASES:
            self.level = 0.
            return
        # Net push since the window or the last pushing phase; a retraction
        # never buys credit for a later push.
        self.level = max(0., self.level + push)
        if self.level > self.push_limit:
            self._trip(now, push, phase)

    def _trip(self, now, push, phase):
        self.tripped = True
        self.trip = {'at': round(now, 3), 'push': round(push, 3), 'level': round(self.level, 3),
                     'phase': phase}
        logging.error('kctrl_sensor_guard: push %.3f mm after the end (net %.3f mm, phase %s), '
                      'emergency stop', push, self.level, phase)
        try:
            self.printer.invoke_shutdown(TRIP_MESSAGE)
        except Exception:
            logging.exception('kctrl_sensor_guard: shutdown request lost')
        # Raised before toolhead.move queues anything: 0 mm of this push.
        raise self.printer.command_error(TRIP_MESSAGE)

    def _ended(self, now):
        state = self.print_stats.get_status(now).get('state')
        if state in END_STATES:
            return True
        # A stock PAUSE after the end shows 'paused' without an open file.
        return state == 'paused' and self.sd.get_status(now).get('file_path') is None

    def _tick(self, eventtime):
        if self.shutdown:
            return self.reactor.NEVER
        now = self.reactor.monotonic()
        for name, step in (('window', self._tick_window), ('watch', self._tick_watch)):
            try:
                step(now)
            except Exception as error:
                self._failed(now, '%s: %s' % (name, error))
        return now + TICK

    def _failed(self, now, text):
        self.failure = text[:120]
        if self.failure_logged is None or now - self.failure_logged >= FAILURE_LOG_SECONDS:
            self.failure_logged = now
            logging.exception('kctrl_sensor_guard: %s', self.failure)

    def _tick_window(self, now):
        if self.tripped:
            return
        if self.sd.is_active():
            if self.window is not None:
                self._close_window('new_print')
            self.armed = True
            return
        if self.window is None:
            if self.armed and self._ended(now):
                self._open_window(now, 'end')
            return
        # The window lasts end_window after the owned end leaves its phases.
        if getattr(self.end_owner, 'phase', None) in END_ACTIVE:
            self.until = max(self.until, now + self.end_window)
        elif now >= self.until:
            self._close_window('expired')
            self.armed = False

    def _open_window(self, now, cause):
        self.window = {'opened': now, 'cause': cause}
        self.until = now + self.end_window
        self.level = 0.
        self.ended = True
        self._say(WINDOW_MESSAGE % (self.end_window // 60))

    def _close_window(self, cause):
        self.window = self.until = None
        self.level = 0.
        self.closed_by = cause

    def _head(self, now):
        try:
            value = self.head.get_status(now).get('filament_detected')
        except Exception:
            return None
        return value if type(value) is bool else None

    def _e(self):
        try:
            value = float(self.toolhead.get_position()[3])
        except Exception:
            return None
        return value if math.isfinite(value) else None

    def _tick_watch(self, now):
        state = self.print_stats.get_status(now).get('state')
        try:
            box = self.box.get_status(now)
        except Exception:
            box = None
        self.route, self.route_reason = engaged_route(box, self.boxes)
        listening = logging.getLogger().isEnabledFor(logging.INFO)
        events = self.tap.drain()
        for t, event in events:
            if event[0] == 'key839' and t >= self.watch.job_start:
                self.key839 = (t, event[1])
            elif event[0] == 'purge':
                self._purge_line(t, event[1])
        outputs = self.watch.tick(now, state == 'printing', self.route, self._head(now), self._e(),
                                  events, listening)
        for kind, value in outputs:
            if kind == 'mark':
                self._say(MARK_MESSAGE % (value['slot'], value['seconds'], value['printed']))
            elif kind == 'blind':
                text = BLIND_MESSAGES[value]
                self._say(text % self.watch.blind_seconds if '%d' in text else text)
        if state == 'printing' and self.route is not None:
            self.last_slot = self.route
        self._tick_pause(now, state, box)
        self._tick_keep(now, state)

    def _purge_line(self, t, kind):
        if kind == 'start':
            self.stock_purge = {'start': t, 'stop': None, 'paused': self.pause is not None}
        elif self.stock_purge is not None and self.stock_purge['stop'] is None:
            self.stock_purge['stop'] = t

    # Rule 4: a pause on a false end says how to resume, and acts on nothing.

    def _tick_pause(self, now, state, box):
        if state != 'paused' or self.sd.get_status(now).get('file_path') is None:
            self.pause = None
            return
        if self.pause is None:
            self.pause = {'at': now, 'slot': self.route or self.last_slot, 'told': False,
                          'idle_told': False}
        pause = self.pause
        slot = pause['slot']
        if slot is None:
            return
        number, letter = slot[1], slot[2]
        episode = self.watch.episodes.get(slot)
        # Latched: the episode of the report may close during a long pause.
        if self._reported(slot, pause['at'], real=True) is not None:
            pause['reported'] = True
        if not pause['told']:
            suspect = self._reported(slot, pause['at'], real=False)
            conn = self.watch.units[slot[:2]]['conn']
            if (suspect is not None and conn is not None and conn[0] >= suspect
                    and conn[1] & BITS[letter] and not (episode is not None and episode['real'])):
                pause['told'] = True
                self.false_end = {'slot': slot, 'at': round(now, 3),
                                  'paused_at': round(pause['at'], 3)}
                self._say(FALSE_END_MESSAGE % (slot, number, number, letter))
        # Only in a pause the CFS explained: a plain pause says nothing.
        unit = box.get('T' + number) if isinstance(box, dict) else None
        mode = unit.get('mode') if isinstance(unit, dict) else None
        if mode in IDLE_MODES and pause.get('reported') and not pause['idle_told']:
            pause['idle_told'] = True
            self.idle_told = slot
            self._say(IDLE_MESSAGE % (number, number, letter))

    def _reported(self, slot, paused_at, real):
        """The last report on slot recent enough to explain the pause, or None.

        A key839 names the slot; an episode counts while it is open, and a
        real one only when real is True.
        """
        times = []
        if self.key839 is not None and self.key839[1] == slot:
            times.append(self.key839[0])
        episode = self.watch.episodes.get(slot)
        if episode is not None and (real or not episode['real']):
            times.append(episode['last'])
        times = [t for t in times if t >= paused_at - PAUSE_LOOKBACK]
        return min(times) if times else None

    # Rules 2 and 3: the auto refill stays on during the print.

    def _keep_allowed(self, now, state):
        end = self.end_owner
        return (state == 'printing' and self.sd.is_active() and not self.ended
                and not self._ended(now) and not getattr(end, 'inflight', False)
                and getattr(end, 'phase', None) not in END_ACTIVE)

    def _tick_keep(self, now, state):
        if not self.keep or self.keep_pending:
            return
        if not self._keep_allowed(now, state) or self._auto_refill() != 0:
            self.zero_since = None
            return
        if self.zero_since is None:
            self.zero_since = now
        if now - self.zero_since < KEEP_SECONDS:
            return
        if self.last_keep is not None and now - self.last_keep < KEEP_RETRY_SECONDS:
            return
        self.keep_pending = True
        job = self.job
        self.reactor.register_callback(lambda eventtime: self._keep_on(job))

    def _keep_on(self, job):
        outcome = None
        try:
            # The mutex orders this after any owned end or start in progress:
            # once the end has begun, the auto refill is kctrl_end's.
            with self.gcode.get_mutex():
                if job != self.job or self.shutdown:
                    return
                now = self.reactor.monotonic()
                state = self.print_stats.get_status(now).get('state')
                if not self._keep_allowed(now, state) or self._auto_refill() != 0:
                    outcome = 'skipped'
                else:
                    self.gcode.run_script_from_command('BOX_ENABLE_AUTO_REFILL ENABLE=1')
                    outcome = 'sent'
            if outcome == 'sent':
                outcome = 'confirmed' if self._confirm(1) else 'unconfirmed'
        except Exception as error:
            self._failed(self.reactor.monotonic(), 'keep: %s' % error)
            outcome = 'error'
        finally:
            self.keep_pending = False
        # A START_PRINT during the read-back began another job: not this one's.
        if outcome is None or job != self.job:
            return
        if outcome == 'skipped':
            self.zero_since = None
            return
        self.last_keep = self.reactor.monotonic()
        self.keep_outcome = outcome
        if outcome == 'confirmed':
            self.kept += 1
            self.zero_since = None
        if not self.keep_told:
            self.keep_told = True
            self._say(KEEP_MESSAGES[outcome])

    def _auto_refill(self):
        try:
            value = self.box.get_status(self.reactor.monotonic()).get('auto_refill')
        except Exception:
            return None
        return value if type(value) is int and value in (0, 1) else None

    def _confirm(self, value):
        # A returned command proves nothing (document 48): two fresh reads do.
        deadline = self.reactor.monotonic() + self.refill_timeout
        seen = 0
        while True:
            seen = seen + 1 if self._auto_refill() == value else 0
            if seen >= 2:
                return True
            now = self.reactor.monotonic()
            if now >= deadline:
                return False
            self.reactor.pause(min(now + .1, deadline))

    def _refill_on(self):
        """Never raises: True once the auto refill is read at 1 twice."""
        try:
            if self._auto_refill() == 1:
                return True
            self.gcode.run_script_from_command('BOX_ENABLE_AUTO_REFILL ENABLE=1')
            return self._confirm(1)
        except Exception as error:
            logging.info('kctrl_sensor_guard: auto refill on lost: %s', error)
            return False

    def cmd_START_PRINT(self, gcmd):
        end = self.end_owner
        if getattr(end, 'inflight', False) or getattr(end, 'phase', None) in END_ACTIVE:
            raise gcmd.error('K1 Control: finalisation encore en cours')
        # A false error with the refill off pauses and purges (document 106):
        # proven on before any heat.
        if self.keep and not self._refill_on():
            raise gcmd.error(START_REFUSED)
        now = self.reactor.monotonic()
        if self.window is not None:
            self._close_window('new_print')
        self.job += 1
        self.watch.reset(now)
        self.armed = self.ended = False
        self.zero_since = self.last_keep = self.keep_outcome = None
        self.keep_told = False
        self.kept = 0
        self.pause = self.false_end = self.idle_told = None
        self.last_slot = self.key839 = self.stock_purge = None
        try:
            self.original(gcmd)
        except Exception:
            # A refused or broken start leaves the end window armed.
            self.armed = True
            raise

    def cmd_KCTRL_SENSOR_GUARD_RELEASE(self, gcmd):
        # respond_info only: a raised error prints '!!', which fails an owned end.
        if getattr(self.end_owner, 'phase', None) in END_ACTIVE:
            gcmd.respond_info('K1 Control: garde de fin maintenue pendant la fin K1 Control')
            return
        self.armed = False
        if self.window is None:
            gcmd.respond_info('K1 Control: aucune fenetre de fin ouverte')
            return
        self._close_window('release')
        gcmd.respond_info('K1 Control: garde de fin levee, poussee a la main permise')

    def cmd_KCTRL_SENSOR_GUARD_STATUS(self, gcmd):
        try:
            text = self._status_text()
        except Exception:
            logging.exception('kctrl_sensor_guard: status text lost')
            text = 'K1 Control: garde capteur %s, etat illisible (voir le journal)' % REVISION
        gcmd.respond_info(text)

    def _status_text(self):
        status = self.get_status()
        phase = getattr(self.end_owner, 'phase', None)
        lines = ['K1 Control: garde capteur %s, %s' % (REVISION, 'posee' if status['installed'] else 'non posee'),
                 'crochet: %s ; aveugle: %s' % (status['hook'] or 'aucun', status['blind'] or 'non'),
                 'route: %s%s' % (status['route'] or 'aucune',
                                  ' (%s)' % status['route_reason'] if status['route_reason'] else '')]
        for slot, episode in sorted(status['episodes'].items()):
            lines.append('episode %s: %d s, %d mm, %s (%s)' % (
                slot, episode['seconds'], episode['printed'], 'reel' if episode['real'] else 'suspect',
                ', '.join(episode['reasons'])))
        marked = status['marked']
        lines.append('marque: non' if marked is None else 'marque: %s apres %d s et %d mm' % (
            marked['slot'], marked['seconds'], marked['printed']))
        lines.append('auto-remplacement tenu a 1: %s ; remises a 1: %d%s' % (
            'oui' if status['keep_auto_refill'] else 'non', status['kept'],
            ' (derniere: %s)' % status['keep'] if status['keep'] else ''))
        false_end = status['false_end']
        lines.append('fausse fin en pause: %s' % (false_end['slot'] if false_end else 'non'))
        lines.append('fenetre de fin: %s' % (
            'ouverte, %d s restantes, %.1f mm nets' % (status['end_window_left'], status['end_level'])
            if status['end_window'] else 'fermee'))
        lines.append("fin K1 Control: %s ; arret d'urgence: %s ; erreur interne: %s" % (
            'echec' if phase == 'failed' else phase, 'oui' if status['tripped'] else 'non',
            'oui (voir le journal)' if status['failure'] else 'non'))
        return '\n'.join(lines)

    def _say(self, msg):
        try:
            self.gcode.respond_info(msg)
        except Exception:
            logging.exception('kctrl_sensor_guard: console message lost')

    def _shutdown(self, *args):
        self.shutdown = True

    def _disconnect(self, *args):
        self.shutdown = True
        try:
            logging.getLogger().removeHandler(self.tap)
        except Exception:
            pass

    def get_status(self, eventtime=None):
        try:
            now = self.reactor.monotonic()
            episodes = dict((slot, {'seconds': round(now - episode['start'], 1),
                                    'printed': round(episode['printed'], 1),
                                    'real': episode['real'], 'reasons': sorted(episode['reasons'])})
                            for slot, episode in self.watch.episodes.items())
            marked = self.watch.marked
            if marked is not None:
                marked = {'slot': marked['slot'], 'seconds': round(marked['seconds'], 1),
                          'printed': round(marked['printed'], 1), 'reasons': list(marked['reasons'])}
            hook = self._hook_state() if self.installed else ''
            purge = self.stock_purge
            if purge is not None:
                purge = {'seconds': round((purge['stop'] or now) - purge['start'], 1),
                         'running': purge['stop'] is None, 'paused': purge['paused']}
            return {'enabled': self.enabled, 'revision': REVISION, 'installed': self.installed,
                    'hook': hook, 'hooked': bool(hook), 'blind': self.watch.blind, 'job': self.job,
                    'episodes': episodes, 'closed': self.watch.closed, 'marked': marked,
                    'keep_auto_refill': self.keep, 'kept': self.kept, 'keep': self.keep_outcome,
                    'paused': self.pause is not None,
                    'false_end': dict(self.false_end) if self.false_end else None,
                    'idle_told': self.idle_told, 'stock_purge': purge,
                    'end_armed': self.armed, 'end_window': self.window is not None,
                    'end_window_left': (round(max(0., self.until - now), 1)
                                        if self.until is not None else None),
                    'end_level': round(self.level, 3), 'end_closed_by': self.closed_by,
                    'tripped': self.tripped, 'trip': dict(self.trip) if self.trip else None,
                    'failure': self.failure, 'route': self.route, 'route_reason': self.route_reason,
                    'tap_seen': self.tap.seen, 'tap_dropped': self.tap.dropped}
        except Exception as error:
            return {'enabled': self.enabled, 'revision': REVISION, 'installed': self.installed,
                    'status_error': str(error)[:120]}


def load_config(config):
    return KctrlSensorGuard(config)
