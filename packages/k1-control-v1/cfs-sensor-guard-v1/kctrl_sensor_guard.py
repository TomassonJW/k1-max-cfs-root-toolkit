"""CFS sensor guard: a contradicted slot sensor marks the job, the end stays safe.

ADR-077, document 105. Disabled by default. Enabled, it requires the owned end
of kctrl_end (end-no-stock-flush-v5) enabled too, or it refuses at
klippy:ready. Nothing is read from or written to the CFS link: the guard
listens to the CFS lines the stock module already writes to the Klipper log,
through a handler on the root logger.

Three ends went wrong on T1A (15 September, 31 October, 1 November 2026). The
CFS reported a filament error, a tension or a missing spool on the slot that
was printing normally with a loaded head; the stock refill routine then pushed
filament after the end. A real runout was proven by the connections mask or
the tail line within 33 s on 31 October (T1B); the same replies took 81 s on
13 September, a likely runout that no head trace confirms.

1. During the print, a filament report on the live slot that is still not
   proven real after episode_seconds and episode_printed_mm, head loaded,
   marks the job: the stock auto refill is switched off, proven by two reads,
   and switched off again if it comes back before the end.
2. After the end of the file, a net push above end_push_limit outside the
   pushing phases of the owned end is an emergency stop, raised before the
   move is queued. KCTRL_SENSOR_GUARD_RELEASE lifts it for a manual push.
3. The next START_PRINT puts the auto refill back, proven by two reads, or
   refuses the start.

kctrl_end fails its own end on a console line that starts with '!!' or holds
the word failed: no console line written here does either, and RELEASE and
STATUS answer without raising.
"""

import collections
import logging
import math
import re

REVISION = 'cfs-sensor-guard-v1'
BITS = {'A': 1, 'B': 2, 'C': 4, 'D': 8}
FILAMENT_ERR = 0x50
STATE_OK = 0x0
# Same as kctrl_end.ACTIVE.
END_ACTIVE = ('waiting', 'heating', 'cutting', 'rewinding', 'finalizing')
# Owned end phases that may push: BOX_CUT_MATERIAL, the separated rewind and
# END_PRINT_NO_M84 with BOX_END. A new pushing phase of kctrl_end goes here.
END_PUSH_PHASES = ('cutting', 'rewinding', 'finalizing')
END_STATES = ('complete', 'cancelled', 'error', 'standby')
QUIET_SECONDS = 15.
RECUT_SECONDS = 10.
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
NAMED = ('recode_err: filament_err', 'error: filament_err')
PREFIXES = ('msg: 0xf7 ', 'filament_err_tighten_up_event', 'Tn_inner_data[', 'extrude = ') + NAMED

TRIP_MESSAGE = "K1 Control: poussee de filament apres la fin, arret d'urgence"
WINDOW_MESSAGE = ('K1 Control: fin du fichier, garde de fin active %d min. Une poussee de filament '
                  'hors des etapes de fin arrete la machine. KCTRL_SENSOR_GUARD_RELEASE avant une '
                  'poussee a la main.')
MARK_MESSAGE = 'K1 Control: capteur du slot %s contredit (%d s, %d mm imprimes, tete chargee). %s'
MARK_OUTCOMES = {
    'confirmed': 'Auto-remplacement CFS coupe et relu a 0, retabli au prochain START_PRINT. '
                 'Une vraie fin de bobine donnera une pause.',
    'unconfirmed': "Auto-remplacement CFS commande a 0 sans relecture a 0, nouvel essai tant "
                   "qu'il est lu a 1.",
    'already': 'Auto-remplacement CFS deja coupe, laisse tel quel. '
               'Une vraie fin de bobine donnera une pause.',
    'end': "Fin deja lancee: l'auto-remplacement reste a la fin K1 Control.",
    'error': "Coupe de l'auto-remplacement CFS impossible (voir le journal), nouvel essai tant "
             "qu'il est lu a 1."}
RECUT_MESSAGE = "K1 Control: auto-remplacement CFS relu a 1 pendant l'impression marquee, recoupe"
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
        elif kind == 'named':
            if t >= self.job_start:
                self._open(event[1], t, 'named')
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
        self.watch = SensorWatch(episode_seconds, episode_mm, blind_seconds)
        self.tap = LineTap(self.reactor.monotonic)
        self.installed = False
        self.shutdown = False
        self.inner = None
        self.original = None
        self.timer = None
        self.job = 0
        self.cut_pending = False
        self.cut = None
        self.recuts = 0
        self.last_cut = None
        self.refill_pending = False
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
        # Without the owned end, the stock end pushes after the file: rule 2
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
        outputs = self.watch.tick(now, state == 'printing', self.route, self._head(now), self._e(),
                                  self.tap.drain(), listening)
        for kind, value in outputs:
            if kind == 'mark':
                self._schedule_cut()
            elif kind == 'blind':
                text = BLIND_MESSAGES[value]
                self._say(text % self.watch.blind_seconds if '%d' in text else text)
        self._maybe_recut(now, state)

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

    def _schedule_cut(self):
        if self.cut_pending:
            return
        self.cut_pending = True
        job = self.job
        self.reactor.register_callback(lambda eventtime: self._cut(job))

    def _cut(self, job):
        marked = None
        try:
            # The mutex orders this after any owned end or start in progress;
            # once the end has begun, the auto refill is kctrl_end's.
            with self.gcode.get_mutex():
                marked = self.watch.marked
                if job != self.job or marked is None or self.shutdown:
                    return
                now = self.reactor.monotonic()
                if (self.ended or self._ended(now)
                        or getattr(self.end_owner, 'phase', None) in END_ACTIVE):
                    outcome = 'end'
                elif self._auto_refill() == 0:
                    outcome = 'already'
                else:
                    self.refill_pending = True
                    self.gcode.run_script_from_command('BOX_ENABLE_AUTO_REFILL ENABLE=0')
                    outcome = 'sent'
            if outcome == 'sent':
                outcome = 'confirmed' if self._confirm(0) else 'unconfirmed'
        except Exception as error:
            self._failed(self.reactor.monotonic(), 'cut: %s' % error)
            outcome = 'error'
        finally:
            self.cut_pending = False
        # A START_PRINT during the read-back began another job: not this cut's.
        if marked is None or job != self.job:
            return
        self.last_cut = self.reactor.monotonic()
        if self.cut is None:
            self.cut = outcome
            self._say(MARK_MESSAGE % (marked['slot'], marked['seconds'], marked['printed'],
                                      MARK_OUTCOMES[outcome]))
        elif outcome in ('confirmed', 'unconfirmed'):
            self.cut = outcome
            self.recuts += 1
            if self.recuts == 1:
                self._say(RECUT_MESSAGE)

    def _maybe_recut(self, now, state):
        # The touchscreen sends ENABLE=1 when it connects: cut again, before
        # the end only and never more than every RECUT_SECONDS.
        if (self.watch.marked is None or self.cut_pending or self.ended
                or state not in ('printing', 'paused') or self._ended(now)
                or getattr(self.end_owner, 'phase', None) in END_ACTIVE
                or (self.last_cut is not None and now - self.last_cut < RECUT_SECONDS)
                or self._auto_refill() != 1):
            return
        self._schedule_cut()

    def _restore_refill(self):
        """Never raises: puts back only a refill this guard switched off."""
        try:
            if self._auto_refill() == 1:
                self.refill_pending = False
            else:
                self.gcode.run_script_from_command('BOX_ENABLE_AUTO_REFILL ENABLE=1')
                if self._confirm(1):
                    self.refill_pending = False
        except Exception as error:
            logging.info('kctrl_sensor_guard: auto refill restore lost: %s', error)
        return not self.refill_pending

    def cmd_START_PRINT(self, gcmd):
        end = self.end_owner
        if getattr(end, 'inflight', False) or getattr(end, 'phase', None) in END_ACTIVE:
            raise gcmd.error('K1 Control: finalisation encore en cours')
        # The new job's spare relay needs the refill back: proven before any heat.
        if self.refill_pending and not self._restore_refill():
            raise gcmd.error('K1 Control: auto-remplacement CFS coupe par la garde capteur '
                             'non retabli, depart refuse')
        now = self.reactor.monotonic()
        if self.window is not None:
            self._close_window('new_print')
        self.job += 1
        self.watch.reset(now)
        self.armed = self.ended = False
        self.cut = self.last_cut = None
        self.recuts = 0
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
        lines.append('marque: non' if marked is None else 'marque: %s apres %d s et %d mm, coupe %s, recoupes %d' % (
            marked['slot'], marked['seconds'], marked['printed'], status['cut'] or 'en cours', status['recuts']))
        lines.append('auto-remplacement a retablir au depart: %s'
                     % ('oui' if status['auto_refill_restore_pending'] else 'non'))
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
            return {'enabled': self.enabled, 'revision': REVISION, 'installed': self.installed,
                    'hook': hook, 'hooked': bool(hook), 'blind': self.watch.blind, 'job': self.job,
                    'episodes': episodes, 'closed': self.watch.closed, 'marked': marked,
                    'cut': self.cut, 'recuts': self.recuts,
                    'auto_refill_restore_pending': self.refill_pending,
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
